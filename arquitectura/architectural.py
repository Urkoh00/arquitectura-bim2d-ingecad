# SPDX-License-Identifier: GPL-3.0-or-later
"""Architectural wall/opening entities for IngeCAD.

DXF is authoritative; app-specific data lives in XDATA under ARQINGECAD.
Opening markers are explicit DXF POINTs so they remain editable/undoable.
All dimensions are in metres in this experimental version.
"""
from __future__ import annotations

import json
import math
import uuid
from pathlib import Path

APPID = 'ARQINGECAD'
WALL_LAYER = 'ARQ-MUROS3D'
OPENING_LAYER = 'ARQ-HUECOS3D'


def finite(value, positive=False):
    n = float(value)
    if not math.isfinite(n) or (positive and n <= 0):
        raise ValueError('Se requiere una medida finita y positiva' if positive else 'Medida no válida')
    return n


def _xdata(msp, entity, obj):
    doc = msp.doc
    if APPID not in doc.appids:
        doc.appids.new(APPID)
    # El grupo 1000 permite como máximo 255 bytes. ensure_ascii mantiene
    # cada fragmento en ASCII (también cuando hay nombres con acentos).
    payload = json.dumps(obj, ensure_ascii=True, separators=(',', ':'))
    parts = [payload[i:i+200] for i in range(0, len(payload), 200)]
    entity.set_xdata(APPID, [(1000, part) for part in parts])
    return entity


def metadata(entity):
    try:
        tags = entity.get_xdata(APPID)
        parts = [tag.value for tag in tags if tag.code == 1000]
        if parts:
            # Lectura retrocompatible: acepta JSON anterior en un único 1000
            # y JSON fragmentado en varios registros consecutivos.
            value = json.loads(''.join(parts))
            return value if isinstance(value, dict) else None
    except (ValueError, TypeError, KeyError):
        pass
    return None


def segment_corners(a, b, thickness):
    thickness = finite(thickness, True)
    ax, ay = map(float, a[:2]); bx, by = map(float, b[:2])
    length = math.hypot(bx-ax, by-ay)
    if length < 1e-5:
        raise ValueError('El segmento del muro debe medir al menos 0,01 mm')
    dx, dy = (bx-ax)/length, (by-ay)/length
    nx, ny = -dy*thickness/2, dx*thickness/2
    return [(ax+nx,ay+ny),(bx+nx,by+ny),(bx-nx,by-ny),(ax-nx,ay-ny)]


def wall_command(a, b, thickness=0.25, height=2.70, base=0.0):
    from core.actions import AddEntityCommand
    corners = segment_corners(a, b, thickness)
    height = finite(height, True); base = finite(base)
    record = {'kind':'wall','schema':1,'id':uuid.uuid4().hex,
              'a':list(map(float,a[:2])), 'b':list(map(float,b[:2])),
              'thickness':float(thickness),'height':height,'base':base}
    def factory(msp):
        ent = msp.add_lwpolyline(corners, close=True)
        return _xdata(msp, ent, record)
    return AddEntityCommand('ARQ MURO3D', factory, layer=WALL_LAYER)


def opening_command(wall, offset, width=0.80, sill=0, height=2.10, kind='door'):
    from core.actions import AddEntityCommand
    meta = metadata(wall)
    if not meta or meta.get('kind') != 'wall':
        raise ValueError('Seleccione un muro creado con MURO3D')
    offset=finite(offset); width=finite(width,True); sill=finite(sill); height=finite(height,True)
    length=math.dist(meta['a'],meta['b'])
    if offset < 0 or offset + width > length + 1e-8:
        raise ValueError('El hueco supera la longitud del muro')
    if sill < 0 or sill + height > meta['height'] + 1e-8:
        raise ValueError('El hueco supera la altura del muro')
    a,b=meta['a'],meta['b']; t=(offset+width/2)/length
    pos=(a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t)
    record={'kind':'opening','schema':1,'id':uuid.uuid4().hex,'wall_id':meta['id'],
            'offset':offset,'width':width,'sill':sill,'height':height,'type':kind}
    def factory(msp):
        return _xdata(msp,msp.add_point(pos),record)
    return AddEntityCommand('ARQ HUECO3D',factory,layer=OPENING_LAYER)


def collect(document):
    """Read only real tagged entities; never infer walls from ordinary lines."""
    drawing=getattr(document,'doc',document)
    walls={}; openings=[]; columns={}
    for ent in drawing.modelspace():
        dat=metadata(ent)
        if not dat: continue
        if dat.get('kind')=='wall' and ent.dxftype() in ('POINT','LWPOLYLINE'):
            if dat['id'] in walls: raise ValueError('Identificador de muro duplicado: '+dat['id'])
            walls[dat['id']]=dat
        elif dat.get('kind')=='column' and ent.dxftype()=='LWPOLYLINE':
            if dat['id'] in columns:raise ValueError('Identificador de pilar duplicado: '+dat['id'])
            columns[dat['id']]=dat
        elif dat.get('kind')=='opening' and ent.dxftype() in ('POINT','LWPOLYLINE'):
            openings.append(dat)
    for opening in openings:
        if opening['wall_id'] not in walls:
            raise ValueError('Hueco huérfano: '+opening['id'])
    output=[]
    for ident,wall in walls.items():
        w={**wall,'openings':sorted((o for o in openings if o['wall_id']==ident),key=lambda x:x['offset'])}
        validate_wall(w)
        output.append(w)
    return {'schema':1,'units':'m','walls':output,'columns':list(columns.values())}


def validate_wall(w):
    length=math.dist(w['a'],w['b']); prev=0.0
    bulge=float(w.get('bulge') or 0.0)
    if bulge:                       # a curved wall: the length along its arc
        sweep=4*math.atan(bulge)
        length=length/(2*math.sin(abs(sweep)/2))*abs(sweep)
    finite(w['thickness'],True); finite(w['height'],True)
    for o in w.get('openings',[]):
        x=finite(o['offset']); width=finite(o['width'],True)
        sill=finite(o['sill']); height=finite(o['height'],True)
        if x < prev-1e-8 or x+width>length+1e-8:
            raise ValueError('Huecos solapados o fuera del muro '+str(w['id']))
        if sill < 0 or sill+height>w['height']+1e-8:
            raise ValueError('Hueco fuera de altura '+str(o['id']))
        prev=x+width


def partition_solids(wall):
    """Return non-overlapping local bricks (start,end,zmin,zmax).

    Does not perform boolean CAD operations; leaves coplanar seams where
    consecutive bricks meet. Suitable for initial geometry validation.
    """
    validate_wall(wall)
    length=math.dist(wall['a'],wall['b']); out=[]; cur=0
    for hole in wall.get('openings',[]):
        left=hole['offset']; right=left+hole['width']
        if left>cur+1e-9:out.append((cur,left,0,wall['height']))
        if hole['sill']>1e-9:out.append((left,right,0,hole['sill']))
        top=hole['sill']+hole['height']
        if top<wall['height']-1e-9:out.append((left,right,top,wall['height']))
        cur=right
    if length>cur+1e-9:out.append((cur,length,0,wall['height']))
    return out


def export_spec(document, dest):
    p=Path(dest); data=collect(document)
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    return data

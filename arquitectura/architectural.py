# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: Lectura y escritura de los datos BIM de una entidad en XDATA (metadata, _xdata) y
#   comprobación de un muro con sus huecos (validate_wall). Base de todos los elementos.
#   (Guía del código: docs/GUIA_DEL_CODIGO.md)
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


def reenlazar(espacio, entidad):
    """Devuelve al espacio una entidad retirada con ``unlink_entity``. Si
    sigue enlazada (una transacción falló antes de retirarla), no hace nada:
    ezdxf la añadiría dos veces sin avisar (revisión del 24-11)."""
    if entidad is not None and entidad.is_alive and entidad.dxf.owner is None:
        espacio.add_entity(entidad)


def _xdata(msp, entity, obj):
    doc = msp.doc
    if not entity.has_xdata(APPID):
        from .levels import bind
        obj=bind(doc,obj)
    if APPID not in doc.appids:
        doc.appids.new(APPID)
    # El grupo 1000 permite como máximo 255 bytes. ensure_ascii mantiene
    # cada fragmento en ASCII (también cuando hay nombres con acentos).
    payload = json.dumps(obj, ensure_ascii=True, separators=(',', ':'))
    parts = [payload[i:i+200] for i in range(0, len(payload), 200)]
    entity.set_xdata(APPID, [(1000, part) for part in parts])
    if obj.get('kind')=='wall' and obj.get('wall_category'):
        from .wall_categories import category,layer_name
        target=layer_name(category(obj),doc.layers)
        from .levels import load
        if load(doc).get('layer_managed') and obj.get('level_id'):
            from .level_layers import suffix
            full=target+suffix(obj['level_id'])
            if full in doc.layers:target=full
        if target in doc.layers:entity.dxf.layer=target
        if entity.dxftype()=='LWPOLYLINE' and not entity.closed:
            entity.dxf.invisible=1
    if isinstance(obj, dict) and obj.get('kind') in ('wall', 'column', 'opening', 'space','slab'):
        # the data is current: reset the frame that records IngeCAD's own
        # transformations of the element (frame.py)
        from .frame import set_frame
        set_frame(entity)
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
    from .capas_envolvente import validar_orden_y_cara
    validar_orden_y_cara(w)
    length=math.dist(w['a'],w['b']); prev=0.0
    bulge=float(w.get('bulge') or 0.0)
    if bulge:                       # a curved wall: the length along its arc
        sweep=4*math.atan(bulge)
        length=length/(2*math.sin(abs(sweep)/2))*abs(sweep)
    finite(w['thickness'],True); finite(w['height'],True)
    from . import defensas
    defensas.validate(w)           # una defensa no admite huecos
    existing=[]
    for o in w.get('openings',[]):
        for prev_o in existing:
            if not(o.get('cabinet_mode')=='adosado' or prev_o.get('cabinet_mode')=='adosado'):continue
            if o.get('cabinet_mode')==prev_o.get('cabinet_mode')=='adosado' and o.get('side')!=prev_o.get('side'):continue
            overlap=min(o['offset']+o['width'],prev_o['offset']+prev_o['width'])-max(o['offset'],prev_o['offset'])
            vertical=min(o['sill']+o['height'],prev_o['sill']+prev_o['height'])-max(o['sill'],prev_o['sill'])
            if overlap>1e-8 and vertical>1e-8:raise ValueError('Armario solapado con otra carpintería o armario')
        existing.append(o)
        x=finite(o['offset']); width=finite(o['width'],True)
        sill=finite(o['sill']); height=finite(o['height'],True)
        furniture=o.get('cabinet_mode')=='adosado'
        if (not furniture and x < prev-1e-8) or x < -1e-8 or x+width>length+1e-8:
            raise ValueError('Huecos solapados o fuera del muro '+str(w['id']))
        if sill < 0 or sill+height>w['height']+1e-8:
            raise ValueError('Hueco fuera de altura '+str(o['id']))
        if not furniture:prev=x+width


def ensure_arch_layers(ctx):
    """Crea las capas básicas de muros y carpinterías si faltan (orden deshacible)."""
    from core.layers import NewLayerCommand
    from .compat import require_document
    doc = require_document(ctx)
    for name, color in ((WALL_LAYER, 8), (OPENING_LAYER, 3)):
        if name not in doc.doc.layers:
            ctx.execute(NewLayerCommand(name, color=color))

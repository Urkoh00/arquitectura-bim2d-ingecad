# SPDX-License-Identifier: GPL-3.0-or-later
"""Extend IngeCAD architectural entities with reference faces, safe editing and join diagnostics.

DXF is authoritative; all edits are undoable through the official IngeCAD Command interface.
No third-party proprietary code is used.
"""
from __future__ import annotations

import copy
import math
from .architectural import (APPID, WALL_LAYER, OPENING_LAYER, finite,
                             metadata, _xdata, validate_wall)

REFERENCE = ('eje', 'izquierda', 'derecha')


def wall_corners(a, b, thickness, reference='eje'):
    thickness = finite(thickness, True)
    if reference not in REFERENCE:
        raise ValueError('Referencia desconocida: eje/izquierda/derecha')
    ax, ay = float(a[0]), float(a[1]); bx, by = float(b[0]), float(b[1])
    length=math.hypot(bx-ax, by-ay)
    if length < 1e-5:
        raise ValueError('Los extremos del muro deben ser diferentes')
    nx, ny = -(by-ay)/length, (bx-ax)/length
    if reference == 'eje': lo, hi = -thickness/2, thickness/2
    elif reference == 'izquierda': lo, hi = 0.0, thickness
    else: lo, hi = -thickness, 0.0
    return [(ax+nx*hi,ay+ny*hi),(bx+nx*hi,by+ny*hi),
            (bx+nx*lo,by+ny*lo),(ax+nx*lo,ay+ny*lo)]


def create_wall(a, b, thickness=0.15, height=2.7, base=0.0, reference='eje', **bim):
    from core.actions import AddEntityCommand
    import uuid
    corners=wall_corners(a,b,thickness,reference)
    height=finite(height,True);base=finite(base)
    rec={'kind':'wall','schema':2,'id':uuid.uuid4().hex,'a':list(map(float,a[:2])),
         'b':list(map(float,b[:2])),'thickness':float(thickness),
         'height':height,'base':base,'reference':reference,
         'ifc_class':'IfcWall',**{k:v for k,v in bim.items() if k in ('name','type_name','material','level','layers')}}
    def factory(msp):
        # Native CAD axis (as in Carreteras): single authoritative, open
        # polyline. The visible wall footprint is derived, never a second
        # independent source footprint. Earlier POINT walls remain readable.
        e=msp.add_lwpolyline([rec['a'], rec['b']])
        return _xdata(msp,e,rec)
    return AddEntityCommand('ARQ MURO',factory,layer=WALL_LAYER)


def _find_openings(drawing, wall_id):
    return [metadata(e) for e in drawing.modelspace()
            if e.dxftype() in ('POINT','LWPOLYLINE') and (metadata(e) or {}).get('wall_id')==wall_id]


def opening_record(wall, offset, width, sill, height, kind, existing=None, **bim):
    meta=metadata(wall)
    if not meta or meta.get('kind')!='wall':
        raise ValueError('Seleccione un muro arquitectónico (MURO)')
    kind=str(kind).lower()
    from . import openings as OP
    typ=OP.kind_of(kind)
    if typ is None:
        raise ValueError('Tipo de carpintería no admitido')
    length=math.dist(meta['a'],meta['b'])
    offset=finite(offset);width=finite(width,True)
    sill=finite(sill);height=finite(height,True)
    if offset < -1e-8 or offset+width>length+1e-8:
        raise ValueError('El hueco sobresale de la longitud del muro')
    if sill < -1e-8 or sill+height>meta['height']+1e-8:
        raise ValueError('El hueco sobresale de la altura del muro')
    import uuid
    rec={'kind':'opening','schema':2,'id':existing or uuid.uuid4().hex,
         'wall_id':meta['id'],'offset':offset,'width':width,'sill':sill,
         'height':height,'type':typ,
         **{k:v for k,v in bim.items() if k in ('name','type_name','material','operation')+OP.V3_KEYS}}
    rec=OP.normalise(rec)
    drawing=wall.doc
    openings=[p for p in _find_openings(drawing,meta['id']) if p.get('id')!=rec['id']]
    validate_wall({**meta,'openings':sorted(openings+[rec],key=lambda o:o['offset'])})
    t=(offset+width/2)/length
    pt=(meta['a'][0]+(meta['b'][0]-meta['a'][0])*t,
        meta['a'][1]+(meta['b'][1]-meta['a'][1])*t)
    return rec,pt


def opening_symbol(wall,record):
    """Points of the DXF entity carrying an opening record: since schema 3
    the 2-point carrier along the middle of the wall (the drawn symbol is
    derived by UNIONESARQ); older records kept a simplified symbol."""
    meta=metadata(wall)
    if int(record.get('schema') or 2)>=3:
        from .geom import junctions as J
        from . import openings as OP
        spec=J.walls_from_records([(meta['id'],meta)])[0]
        return OP.carrier_points(spec,record)
    a,b=meta['a'],meta['b']
    length=math.dist(a,b)
    ux,uy=(b[0]-a[0])/length,(b[1]-a[1])/length
    nx,ny=-uy,ux
    t=meta['thickness'];s=record['offset'];w=record['width']
    start=(a[0]+ux*s,a[1]+uy*s)
    end=(start[0]+ux*w,start[1]+uy*w)
    def off(p,dist):return (p[0]+nx*dist,p[1]+ny*dist)
    if record['type']=='door':
        # Door leaf shown perpendicular to wall, as a simplified CAD symbol.
        return [off(start,-t/2),start,off(start,w),start,end,off(end,t/2)]
    # Window glazing represented by two parallel inner mullion lines.
    return [off(start,-t/3),off(end,-t/3),off(end,t/3),off(start,t/3)]


def create_opening(wall,offset,width=0.8,sill=0.0,height=2.1,kind='puerta',**bim):
    from core.actions import AddEntityCommand
    rec,pt=opening_record(wall,offset,width,sill,height,kind,**bim)
    def factory(msp):
        return _xdata(msp,msp.add_lwpolyline(opening_symbol(wall,rec)),rec)
    return AddEntityCommand('ARQ '+kind.upper(),factory,layer=OPENING_LAYER)


class EditArchitecturalCommand:
    """Undoable edit for tagged wall/opening, keeping its DXF handle stable."""
    name='EDITARARQ'
    def __init__(self,entity,record,points=None,position=None):
        self.entity=entity
        self.new_record=copy.deepcopy(record)
        self.new_points=copy.deepcopy(points)
        self.new_position=position
        self.old_record=copy.deepcopy(metadata(entity))
        if self.old_record is None:raise ValueError('Entidad sin datos ARQ')
        self.old_points=list(entity.get_points('xy')) if entity.dxftype()=='LWPOLYLINE' else None
        self.old_position=tuple(entity.dxf.location) if entity.dxftype()=='POINT' else None
    def _apply(self,document,record,points,position):
        from .architectural import _xdata
        if points is not None:self.entity.set_points(points,format='xy')
        if position is not None:self.entity.dxf.location=position
        _xdata(document.doc.modelspace(),self.entity,record)
        document.dirty=True
    def do(self,document):self._apply(document,self.new_record,self.new_points,self.new_position)
    def undo(self,document):self._apply(document,self.old_record,self.old_points,self.old_position)


def edit_wall(entity,*,thickness=None,height=None,base=None,reference=None,
              name=None,type_name=None,material=None,level=None):
    d=metadata(entity)
    if not d or d.get('kind')!='wall':raise ValueError('Entidad no es un muro ARQ')
    d=copy.deepcopy(d)
    if thickness is not None:d['thickness']=finite(thickness,True)
    if height is not None:d['height']=finite(height,True)
    if base is not None:d['base']=finite(base)
    if reference is not None:d['reference']=reference
    for k,v in (('name',name),('type_name',type_name),('material',material),('level',level)):
        if v is not None:d[k]=str(v)
    pts=wall_corners(d['a'],d['b'],d['thickness'],d.get('reference','eje'))
    for hole in _find_openings(entity.doc,d['id']):
        validate_wall({**d,'openings':[hole]})
    if entity.dxftype() == 'POINT':
        return EditArchitecturalCommand(entity,d)
    return EditArchitecturalCommand(entity,d,points=[d['a'],d['b']] if (entity.dxftype()=='LWPOLYLINE' and not entity.closed and len(entity)==2) else pts)


def edit_opening(entity,*,offset=None,width=None,sill=None,height=None,
                 name=None,type_name=None,material=None,operation=None,**v3):
    from . import openings as OP
    d=metadata(entity)
    if not d or d.get('kind')!='opening':raise ValueError('Entidad no es una carpintería ARQ')
    wall=next((e for e in entity.doc.modelspace() if (metadata(e) or {}).get('id')==d['wall_id']),None)
    if wall is None:raise ValueError('No se encuentra el muro asociado')
    rec,pt=opening_record(wall,offset if offset is not None else d['offset'],
                          width if width is not None else d['width'],
                          sill if sill is not None else d['sill'],
                          height if height is not None else d['height'],
                          v3.get('type') or d['type'],existing=d['id'],
                          **{k:(v if v is not None else d.get(k,''))
            for k,v in (('name',name),('type_name',type_name),('material',material),('operation',operation))},
                          **{k:(v3[k] if v3.get(k) is not None else d.get(k)) for k in OP.V3_KEYS
                             if v3.get(k) is not None or d.get(k) is not None})
    if entity.dxftype()=='LWPOLYLINE':
        return EditArchitecturalCommand(entity,rec,points=opening_symbol(wall,rec))
    return EditArchitecturalCommand(entity,rec,position=(pt[0],pt[1],0.0))


def junction_report(walls,tol=1e-7):
    """Detect centre-line L/T/X junctions, without claiming a full boolean union."""
    def cross(a,b):return a[0]*b[1]-a[1]*b[0]
    result=[]
    for i,a in enumerate(walls):
        for b in walls[i+1:]:
            p=a['a'];r=(a['b'][0]-p[0],a['b'][1]-p[1]);q=b['a'];s=(b['b'][0]-q[0],b['b'][1]-q[1])
            den=cross(r,s)
            if abs(den)<tol:continue
            qp=(q[0]-p[0],q[1]-p[1]);t=cross(qp,s)/den;u=cross(qp,r)/den
            if not -tol<=t<=1+tol or not -tol<=u<=1+tol:continue
            aend=(abs(t)<tol or abs(t-1)<tol);bend=(abs(u)<tol or abs(u-1)<tol)
            typ='L' if aend and bend else 'T' if aend or bend else 'X'
            result.append({'a':a['id'],'b':b['id'],'type':typ,
                           'point':[p[0]+t*r[0],p[1]+t*r[1]]})
    return result

# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: Forjados horizontales: el sombreado nativo de IngeCAD es su geometría.
#   (Guía del código: docs/GUIA_DEL_CODIGO.md)
"""Horizontal slabs: native HATCH boundaries are the authoritative geometry."""
from __future__ import annotations
import copy,math,uuid
from core.commands import Command
from core.actions import AddEntityCommand
from .architectural import metadata,_xdata
from .geom import polygon as P,solids as S

LAYER='ARQ-FORJADOS'

# Clase del forjado (v1.34): decide su tipo IFC y si da al exterior o al
# terreno, que es lo que leen los programas de cálculo energético.
#   clave -> (nombre visible, PredefinedType, IsExternal, contacto con el terreno)
KINDS={'forjado':('Forjado entre plantas','FLOOR',False,False),
       'solera':('Solera (apoyada en el terreno)','BASESLAB',True,True),
       'cubierta':('Cubierta plana','ROOF',True,False)}
DEFAULT_KIND='forjado'
#: nombre corto de cada clase, para el tipo IFC por defecto
SHORT={'forjado':'Forjado','solera':'Solera','cubierta':'Cubierta plana'}


def _crosses(a,b,c,d,tol=1e-9):
    def orient(p,q,r):return P.cross(P.sub(q,p),P.sub(r,p))
    def on(p,q,r):return abs(orient(p,q,r))<=tol and min(p[0],q[0])-tol<=r[0]<=max(p[0],q[0])+tol and min(p[1],q[1])-tol<=r[1]<=max(p[1],q[1])+tol
    aa,bb,cc,dd=orient(a,b,c),orient(a,b,d),orient(c,d,a),orient(c,d,b)
    return aa*bb<0 and cc*dd<0 or on(a,b,c)or on(a,b,d)or on(c,d,a)or on(c,d,b)


def ring(points):
    pts=[tuple(map(float,p[:2]))for p in points]
    if pts and pts[0]==pts[-1]:pts.pop()
    if not 3<=len(pts)<=2048 or not all(len(p)==2 and all(math.isfinite(v)for v in p)for p in pts):raise ValueError('Contorno: entre 3 y 2048 vértices XY finitos')
    edges=list(zip(pts,pts[1:]+pts[:1]))
    for i,(a,b)in enumerate(edges):
        if math.dist(a,b)<1e-8:raise ValueError('Contorno con arista nula')
        for j,(c,d)in enumerate(edges[:i]):
            if (i-j)%len(edges)in (1,len(edges)-1):continue
            if _crosses(a,b,c,d):raise ValueError('Contorno autointersecado o con contacto no adyacente')
    pts=P.dedupe(P.ccw(pts))
    if abs(P.area(pts))<1e-8:raise ValueError('Contorno sin superficie')
    return pts


def region(outer,holes=()):
    outer=ring(outer);holes=[ring(h)for h in holes];pieces=P.convex_parts(outer)
    if abs(sum(P.area(p)for p in pieces)-P.area(outer))>1e-7:raise ValueError('No se pudo descomponer el contorno')
    previous=[]
    for h in holes:
        for loop in [outer,*previous]:
            if any(_crosses(a,b,c,d)for a,b in zip(h,h[1:]+h[:1])for c,d in zip(loop,loop[1:]+loop[:1])):raise ValueError('Hueco que toca o cruza otro contorno')
        after=P.subtract(pieces,h);removed=sum(P.area(p)for p in pieces)-sum(P.area(p)for p in after)
        if abs(removed-P.area(h))>1e-7:raise ValueError('Hueco exterior, superpuesto o anidado')
        pieces=after;previous.append(h)
    area=sum(P.area(p)for p in pieces)
    if area<1e-8:raise ValueError('Forjado sin superficie neta')
    return {'outer':outer,'holes':holes,'pieces':pieces,'area':area,'gross_area':P.area(outer)}


def validate(record):
    record=copy.deepcopy(record)
    record.setdefault('slab_kind',DEFAULT_KIND)
    if record['slab_kind']not in KINDS:raise ValueError('Clase de forjado no válida: '+str(record['slab_kind']))
    for key in ('base','thickness'):
        record[key]=float(record[key])
        if not math.isfinite(record[key])or(key=='thickness'and record[key]<=0):raise ValueError('Cota finita y espesor positivo requeridos')
    region(record['outer'],record.get('holes',[]))
    record.setdefault('hole_ids',[]);ids=record['hole_ids']
    if len(ids)!=len(record.get('holes',[])):
        record['hole_ids']=[uuid.uuid5(uuid.NAMESPACE_URL,record['id']+':hole:'+str(i)).hex for i in range(len(record.get('holes',[])))]
    elif len(set(ids))!=len(ids)or not all(isinstance(v,str)and v for v in ids):raise ValueError('Identidades de hueco no válidas')
    return record


def read(entity):
    m=metadata(entity)or{}
    if m.get('kind')!='slab'or entity.dxftype()!='HATCH':raise ValueError('Seleccione un forjado BIM')
    from . import frame as FR
    frame=FR.read_frame(entity)
    if frame is not None and frame[3][2]<=1e-12:raise ValueError('Escala/reflexión vertical no admitida para el forjado')
    m=FR.reconcile(entity,m)
    loops=[];zs=[]
    for path in entity.paths:
        if not hasattr(path,'vertices')or any(abs(p[2])>1e-10 for p in path.vertices):raise ValueError('Forjado horizontal: no se admiten bordes curvos')
        pts=[]
        for x,y,b in path.vertices:
            p=entity.ocs().to_wcs((x,y,entity.dxf.elevation.z));pts.append((p.x,p.y));zs.append(p.z)
        loops.append(pts)
    if not loops or not zs or max(zs)-min(zs)>1e-7:raise ValueError('Forjado inclinado no admitido en esta etapa')
    geo=region(loops[0],loops[1:]);out={**m,'outer':geo['outer'],'holes':geo['holes'],'base':zs[0]-float(m['thickness'])}
    from .levels import bind
    return bind(entity.doc,validate(out))


def _geometry(entity,record):
    entity.paths.clear()
    entity.dxf.extrusion=(0,0,1);entity.dxf.elevation=(0,0,record['base']+record['thickness'])
    entity.paths.add_polyline_path(record['outer'],is_closed=True,flags=1)
    for h in record.get('holes',[]):entity.paths.add_polyline_path(h,is_closed=True,flags=0)


def create(outer,holes=(),*,thickness=.2,top=0.,level_id=None,level=None,name='Forjado',material='Sin definir',slab_kind=DEFAULT_KIND):
    geo=region(outer,holes)
    record=validate({'kind':'slab','schema':1,'id':uuid.uuid4().hex,'ifc_class':'IfcSlab','name':name,'slab_kind':slab_kind,
        'material':material,'outer':geo['outer'],'holes':geo['holes'],'thickness':thickness,'base':float(top)-float(thickness),
        **({'level_id':level_id}if level_id else{}),**({'level':level}if level else{})})
    def factory(msp):
        e=msp.add_hatch(color=8);e.transparency=.85;_geometry(e,record);return _xdata(msp,e,record)
    from .level_layers import tagged
    return tagged(AddEntityCommand('ARQ FORJADO',factory,layer=LAYER),record)


class EditSlab(Command):
    name='ARQ EDITAR FORJADO';needs_regen=True
    def __init__(self,entity,record):
        self.entity=entity;self.before=read(entity);self.old_metadata=copy.deepcopy(metadata(entity));record=copy.deepcopy(record)
        if len(record.get('hole_ids',[]))!=len(record.get('holes',[])):
            old={tuple(map(tuple,h)):ident for h,ident in zip(self.before['holes'],self.before['hole_ids'])}
            record['hole_ids']=[old.get(tuple(map(tuple,h)),uuid.uuid4().hex)for h in record.get('holes',[])]
        self.after=validate(record)
        self.after['id']=self.before['id']
    def do(self,document):
        from .level_layers import require_unlocked
        require_unlocked(document,self.entity)
        from .levels import bind
        _geometry(self.entity,self.after);_xdata(document.doc.modelspace(),self.entity,bind(document.doc,self.after));document.dirty=True
    def undo(self,document):_geometry(self.entity,self.before);_xdata(document.doc.modelspace(),self.entity,self.old_metadata);document.dirty=True


def apply_new(ctx,outer,holes=(),**values):
    from .levels import load,catalog_steps
    from .compat import require_document
    from .transactions import SafeArchitecturalCommand,apply_architectural_change
    from core.layers import NewLayerCommand
    doc=require_document(ctx)
    if int(doc.doc.header.get('$INSUNITS',0))not in (0,6):raise ValueError('FORJADO exige metros; convierta las unidades del dibujo explícitamente')
    catalog=load(doc);lv=next(v for v in catalog['levels']if v['id']==catalog['active'])
    offset=float(values.pop('top_offset',0));values.pop('level_id',None);values.pop('level',None)
    cmd=create(outer,holes,top=lv['elevation']+offset,level_id=lv['id'],level=lv['name'],**values)
    steps=[*catalog_steps(doc,catalog),NewLayerCommand(LAYER,color=8),cmd]
    apply_architectural_change(ctx,SafeArchitecturalCommand('ARQ forjado y niveles',steps))
    return cmd


def elements(drawing,skip=()):
    from .exchange import ifc_guid,_faces_json
    out=[]
    for e in drawing.modelspace():
        if e.dxf.handle in skip or(metadata(e)or{}).get('kind')!='slab':continue
        m=read(e);geo=region(m['outer'],m['holes']);faces,volume=S.wall_solid(geo['pieces'],(0,0),(1,0),m['base'],m['thickness'])
        openings=[]
        for h,ident in zip(geo['holes'],m['hole_ids']):
            faces_h,vol_h=S.prism_solid(h,m['base'],m['thickness'])
            openings.append({'id':ident,'guid':ifc_guid(ident),'name':'Hueco de '+m['name'],'kind':'void',
                'params':{'base':m['base'],'height':m['thickness']},'faces':_faces_json(faces_h)})
        label,predefined,external,ground=KINDS[m.get('slab_kind',DEFAULT_KIND)]
        # tipo IFC del forjado: el generador del modelo analítico agrupa por
        # tipo y lo exige en todos los elementos; si el registro no trae uno,
        # se nombra por su clase y su canto («Solera 20 cm»)
        type_name=m.get('type_name') or f"{SHORT[m.get('slab_kind',DEFAULT_KIND)]} {m['thickness']*100:.0f} cm"
        out.append({'id':m['id'],'guid':ifc_guid(m['id']),'ifc_class':'IfcSlab','name':m['name'],'material':m.get('material',''),
          'type_name':type_name,
          'level':m.get('level','Planta baja'),'level_id':m.get('level_id'),'params':{'base':m['base'],'height':m['thickness'],'thickness':m['thickness']},
          'enums':{'PredefinedType':predefined},'faces':_faces_json(faces),'volume':volume,'plan_area':geo['area'],
          'psets':{'Pset_SlabCommon':{'Reference':m['name'],'IsExternal':external},
                   'ARQ_Forjado':{'SourceId':m['id'],'HoleCount':len(geo['holes']),'Tipo':label,'ContactoTerreno':ground}},
          'quantities':{'GrossArea':geo['gross_area'],'NetArea':geo['area'],'Width':m['thickness'],'NetVolume':volume},
          'footprint':[[geo['outer'],geo['holes']]],'openings':openings})
    return out

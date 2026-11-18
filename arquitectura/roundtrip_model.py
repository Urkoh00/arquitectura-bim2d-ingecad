# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: Propuestas de cambio en JSON (validación, huella de revisión, aplicación a una copia de los
#   registros). Sin dependencias del anfitrión: se usa en IngeCAD y, copiado, en IngeTrazo.
#   (Guía del código: docs/GUIA_DEL_CODIGO.md)
"""JSON proposals and shared geometry. No host imports or independent modeller."""
from __future__ import annotations
import copy, hashlib, json, math
from . import openings as OP
from .architectural import validate_wall
from .geom import junctions as J

WALL_FIELDS = frozenset('type_name material thickness height layers wall_category'.split())
OPEN_FIELDS = frozenset(('type_name','material','width','height','sill','operation') + OP.V3_KEYS)
PLAN_FIELDS = frozenset('thickness width height sill offset reference side niche_depth cabinet_mode wall_category'.split())


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def finite_tree(value):
    if isinstance(value,float) and not math.isfinite(value):raise ValueError('Número no finito')
    if isinstance(value,dict):
        for v in value.values():finite_tree(v)
    elif isinstance(value,list):
        for v in value:finite_tree(v)


def propose(snapshot, ident, values):
    """Validate with the plugin's normaliser, solids, junctions and fit rules."""
    snapshot=copy.deepcopy(snapshot);records=snapshot['records'];old=records[ident]
    allowed=WALL_FIELDS if old['kind']=='wall' else OPEN_FIELDS if old['kind']=='opening' else frozenset()
    if set(values)-allowed:raise ValueError('Campo no editable en esta clase')
    if not values:return snapshot,False
    finite_tree(values)
    new={**old,**copy.deepcopy(values)}
    if old['kind']=='wall':
        if old.get('height_constraint')=='level' and 'height' in values:raise ValueError('La altura entre niveles es derivada')
        if 'thickness' in values and 'layers' not in values and new.get('layers') and abs(sum(float(t)for t,_ in new['layers'])-new['thickness'])>5e-4:new.pop('layers')
    if old['kind']=='opening':
        if 'operation' in values and values['operation'] not in OP.OPERATIONS[old['type']]:raise ValueError('Apertura no válida')
        for key in ('frame_width','frame_depth','leaf_thickness'):
            if key in new and (type(new[key]) not in (int,float) or new[key]<0):raise ValueError('Medida de perfil no válida: '+key)
        leaves=new.get('leaves',1)
        if type(leaves)is not int or not 1<=leaves<=(128 if new.get('cabinet')else 6 if new['type']=='window'else 2):
            if new['type']!='gap':raise ValueError('Número de hojas no válido')
        new=OP.normalise(new)
    if new==old:return snapshot,False
    records[ident]=new
    walls=[(i,r) for i,r in records.items() if r['kind']=='wall']
    specs=J.walls_from_records(walls);byid={s.id:s for s in specs}
    for wid,w in walls:
        ops=sorted([r for r in records.values() if r.get('wall_id')==wid],key=lambda r:r['offset'])
        validate_wall({**w,'openings':ops})
        if w.get('layers') and abs(sum(float(t)for t,_ in w['layers'])-w['thickness'])>5e-4:raise ValueError('Las capas no suman el espesor')
        for o in ops:
            OP.cut_band(byid[wid],o)
            if o['type']!='gap':OP.carpentry_parts(byid[wid],o,w.get('base',0))
    if old['kind']=='opening':
        from .geom.bands import solve_records
        columns=[(i,r)for i,r in records.items()if r['kind']=='column']
        bands=solve_records(walls,columns)
        spec=byid[new['wall_id']];station=new['offset']+new['width']/2
        z0=float(records[new['wall_id']].get('base',0))+new['sill'];z1=z0+new['height']
        checked=False
        for (lo,hi),network in bands.vertical_networks:
            if hi<=z0+1e-8 or lo>=z1-1e-8:continue
            segs=[]
            for a,b,ids in J.plan_outline(network):
                if new['wall_id']in ids:segs.append((a,b))
            _,_,span=OP.free_span(spec,segs,station,new.get('side',1))
            if span is None or new['offset']<span[0]-1e-6 or new['offset']+new['width']>span[1]+1e-6:raise ValueError('La carpintería no cabe en el tramo libre')
            checked=True
        if not checked:raise ValueError('No se encuentra el tramo vertical del muro')
    pending=any(old.get(k)!=new.get(k) for k in PLAN_FIELDS)
    if old['kind']=='wall' and old.get('height')!=new.get('height'):pending=True
    return snapshot,pending


def changes(origin, current):
    items=[]
    for ident,old in origin['records'].items():
        new=current['records'][ident]
        fields={k:{'old':old.get(k),'new':new.get(k)}for k in (WALL_FIELDS if old['kind']=='wall' else OPEN_FIELDS if old['kind']=='opening' else ())if old.get(k)!=new.get(k)}
        if fields:items.append({'id':ident,'before':old,'fields':fields})
    return {'format':'arqcambios','version':1,'source_id':origin['source_id'],'fingerprint':digest(origin),
            'changes':items,'catalog':{'old':origin['catalog'],'new':current['catalog']}}


def validate_changes(data):
    if not isinstance(data,dict)or data.get('format')!='arqcambios'or type(data.get('version'))is not int or data['version']!=1:raise ValueError('Formato arqcambios no compatible')
    finite_tree(data);seen=set()
    if not isinstance(data.get('changes'),list)or len(data['changes'])>200000:raise ValueError('Lista de cambios no válida')
    for c in data['changes']:
        ident=c['id'];old=c['before'];allowed=WALL_FIELDS if old.get('kind')=='wall' else OPEN_FIELDS if old.get('kind')=='opening' else frozenset()
        if ident in seen or ident!=old.get('id')or not c['fields']or set(c['fields'])-allowed:raise ValueError('Cambio duplicado o campo no permitido')
        seen.add(ident)
        for k,pair in c['fields'].items():
            if set(pair)!={'old','new'}or pair['old']!=old.get(k):raise ValueError('Valor de origen incoherente')
    if not isinstance(data.get('source_id'),str)or not isinstance(data.get('fingerprint'),str)or len(data['fingerprint'])!=64:raise ValueError('Revisión de origen ausente')
    if not isinstance(data.get('catalog'),dict):raise ValueError('Catálogo ausente')
    return data


def preview_contract(contract,snapshot,ident):
    """Non-plan preview uses the exact exporter and carpentry implementation."""
    from . import exchange as E
    from . import cabinets as C
    out=copy.deepcopy(contract);r=snapshot['records'][ident]
    if r['kind']=='wall':
        for el in out['elements']:
            if el['id']==ident:
                E.wall_type_data(el,r,r['thickness'])
        return out
    wall=snapshot['records'][r['wall_id']];spec=J.walls_from_records([(wall['id'],wall)])[0]
    original=next((e for e in out['elements']if e['id']==ident),None)
    if r['type']=='gap':return out
    if original is None:raise ValueError('No se encuentra la geometría del elemento')
    host=next(e for e in out['elements']if e['id']==wall['id'])
    front=E._filling(r,spec,{**wall,'_external':host.get('is_external',False)},original['level'],original.get('fills'),wall['id'])
    if 'level_offset'in original.get('params',{}):front['params']['level_offset']=original['params']['level_offset']
    if original.get('level_id'):front['level_id']=original['level_id']
    if r.get('cabinet_mode')=='adosado':
        front.pop('fills',None);front['params'].update(body_id=ident+'-cuerpo')
        body=C.body_element(spec,r,wall,original['level'])
        if original.get('level_id'):body['level_id']=original['level_id']
        out['elements']=[body if e['id']==body['id']else e for e in out['elements']]
    out['elements']=[front if e['id']==ident else e for e in out['elements']]
    return out

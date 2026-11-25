# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: ARMARIOBIM: armarios adosados a un muro (por defecto) o empotrados como nicho, con sus
#   frentes como puertas.
#   (Guía del código: docs/GUIA_DEL_CODIGO.md)
"""Partial wall niches using the existing opening and door pipeline."""
from . import openings as OP


def fronts(spec,rec):
    OP.cut_band(spec,rec)
    n=int(rec['leaves']);fw=float(rec['frame_width']);step=(rec['width']-2*fw)/n
    if step<=.06:raise ValueError('Ancho insuficiente para las hojas del armario')
    for i in range(n):
        yield {**rec,'cabinet':False,'_cabinet_front':True,'offset':rec['offset']+fw+i*step+.002,'width':step-.004,
               'leaves':1,'hinge':i%2,'face':'distancia','setback_from':'interior',
               'setback':0.,'frame_depth':min(.05,rec['niche_depth']),
               'frame_width':0.,'leaf':step-.004,'leaf2':0.,
               '_track':rec['side']*.03*(i%2)if rec['operation']=='SLIDING'else 0.}


def _niche_symbols(spec,rec):
    result=[];fw=float(rec['frame_width'])
    full={**rec,'cabinet':False,'leaves':1,'face':'interior','frame_depth':min(.05,rec['niche_depth'])}
    lo,hi=OP.frame_band(spec,full);h=hi if rec['side']>0 else lo
    if fw:result.extend(OP._jambs(spec.point,rec['offset'],rec['offset']+rec['width'],fw,lo,hi,h,float(rec.get('leaf_thickness')or OP.LEAF_THICKNESS)))
    for front in fronts(spec,rec):
        shift=front['_track']
        def pt(p,shift=shift):return(p[0]+spec.n[0]*shift,p[1]+spec.n[1]*shift)
        for g in OP.plan_symbol(spec,front):
            if g[0]=='poly':result.append(('poly',[pt(p)for p in g[1]],g[2]))
            elif g[0]=='line':result.append(('line',pt(g[1]),pt(g[2])))
            else:result.append(('arc',pt(g[1]),*g[2:]))
    return result


def _niche_parts(spec,rec,base):
    full={**rec,'cabinet':False,'leaves':1,'face':'interior','frame_depth':min(.05,rec['niche_depth'])}
    result=[p for p in OP.carpentry_parts(spec,full,base)if p['role']=='frame']
    for i,front in enumerate(fronts(spec,rec)):
        for piece in OP.carpentry_parts(spec,front,base):
            piece=dict(piece);a,b,lo,hi,z0,z1=piece['box'];shift=front['_track']
            piece['box']=(a,b,lo+shift,hi+shift,z0,z1);piece['name']=OP.PART_NAMES[piece['role']] + f' {i+1}'
            result.append(piece)
    return result


def create(wall,offset,width,depth,height,leaves=2,operation='SLIDING',side=1,base=0.,mode='nicho',body_material='Madera',mark=''):
    from .architectural_v10 import create_opening
    command=create_opening(wall,offset,width,base,height,kind='door',cabinet=True,
        niche_depth=depth,cabinet_mode=mode,body_material=body_material,leaves=leaves,operation=operation,side=side,
        name='Armario',type_name='ARMARIO',mark=mark,frame_width=.02,frame_depth=min(.05,depth))
    from .architectural import metadata
    from .geom.junctions import walls_from_records
    m=metadata(wall);spec=walls_from_records([(m['id'],m)])[0]
    parts(spec,command.arq_record,float(m.get('base',0)))
    return command


#: categorías de muro en las que un armario empotrado (nicho) quita espesor a
#: la envolvente: debilita su aislamiento térmico y acústico (propietario,
#: 19-11-2026; por la misma razón ya no se empotran radiadores)
_ENVOLVENTE = ('fachada', 'medianera', 'sotano')


def niche_warning(wall_record, mode):
    """Aviso para un armario empotrado en un muro de la envolvente, o None."""
    if mode != 'nicho':
        return None
    from .wall_categories import category
    try:
        cat = category(wall_record)
    except ValueError:
        return None
    if cat not in _ENVOLVENTE:
        return None
    return (f'armario empotrado en un muro de {cat}: el nicho reduce el espesor y debilita '
            'su aislamiento térmico y acústico; considere un armario adosado')


def form(ctx,record=None):
    from PySide6.QtWidgets import QFormLayout,QDoubleSpinBox,QSpinBox,QComboBox,QMessageBox,QLineEdit
    from .bim_dialogs import _dialog
    rec=record or {};dlg,layout,buttons=_dialog(ctx,'Arquitectura — Armario (adosado o empotrado)',
        'Adosado: ocupa espacio delante del muro sin cortarlo. Empotrado: nicho parcial que conserva 0,01 m de muro. Designe la cara de acceso y la jamba.')
    rows=QFormLayout();edit={}
    mode=QComboBox();mode.addItem('Adosado (por defecto)','adosado');mode.addItem('Empotrado / nicho','nicho')
    mode.setCurrentIndex(max(0,mode.findData(rec.get('cabinet_mode','nicho' if rec.get('cabinet')else 'adosado'))));rows.addRow('Modo',mode)
    material=QLineEdit(rec.get('body_material','Madera'));rows.addRow('Material del cuerpo',material)
    marca=QLineEdit(rec.get('mark',''));rows.addRow('Marca de los frentes',marca)
    for key,label,value in [('width','Ancho (m)',1.2),('niche_depth','Fondo (m)',.6),('height','Altura (m)',2.1),('sill','Base sobre el muro (m)',0.)]:
        w=QDoubleSpinBox();w.setDecimals(4);w.setRange(0 if key=='sill'else .001,1000);w.setValue(rec.get(key,value));rows.addRow(label,w);edit[key]=w
    leaves=QSpinBox();leaves.setRange(1,128);leaves.setValue(rec.get('leaves',2));rows.addRow('Hojas',leaves)
    operation=QComboBox();operation.addItem('Corredera','SLIDING');operation.addItem('Abatible','SWINGING');operation.setCurrentIndex(max(0,operation.findData(rec.get('operation','SLIDING'))));rows.addRow('Apertura',operation)
    layout.insertLayout(1,rows);layout.addWidget(buttons)
    def read():return {**{k:w.value()for k,w in edit.items()},'leaves':leaves.value(),'operation':operation.currentData(),'cabinet_mode':mode.currentData(),'body_material':material.text().strip(),'mark':marca.text().strip().upper()}
    dlg._arq={**edit,'leaves':leaves,'operation':operation,'cabinet_mode':mode,'body_material':material,'mark':marca}
    return dlg,read


def _front_record(spec, rec):
    return {**rec, 'cabinet':False, 'cabinet_mode':'nicho', 'niche_depth':.05}


def symbols(spec, rec):
    if rec.get('cabinet_mode')!='adosado': return _niche_symbols(spec,rec)
    lo,hi=OP.cut_band(spec,rec);delta=rec['side']*rec['niche_depth']
    def moved(p):return (p[0]+spec.n[0]*delta,p[1]+spec.n[1]*delta)
    out=[('poly',footprint(spec,rec),True)]
    for g in _niche_symbols(spec,_front_record(spec,rec)):
        if g[0]=='line':out.append(('line',moved(g[1]),moved(g[2])))
        elif g[0]=='poly':out.append(('poly',[moved(p) for p in g[1]],g[2]))
        else:out.append(('arc',moved(g[1]),*g[2:]))
    return out


def parts(spec, rec, base):
    if rec.get('cabinet_mode')!='adosado':return _niche_parts(spec,rec,base)
    OP.cut_band(spec,rec)
    delta=rec['side']*rec['niche_depth'];out=[]
    for part in _niche_parts(spec,_front_record(spec,rec),base):
        if 'prism' in part:
            outer,holes,p,q=part['prism']
            out.append({**part,'prism':(outer,holes,p+delta,q+delta)})
        else:
            a,b,p,q,z0,z1=part['box']
            out.append({**part,'box':(a,b,p+delta,q+delta,z0,z1)})
    return out


def footprint(spec, rec):
    from .geom import polygon as P
    lo,hi=OP.cut_band(spec,rec);s=rec['offset'];end=s+rec['width']
    return P.ccw([spec.point(s,lo),spec.point(end,lo),spec.point(end,hi),spec.point(s,hi)])


def body_parts(spec,rec,base):
    """Five disjoint panels; fronts are separate IfcDoor geometry."""
    lo,hi=OP.cut_band(spec,rec);t=min(.018,rec['width']/8,rec['height']/8)
    if rec['side']>0: hi-=.05
    else:lo+=.05
    a,b=rec['offset'],rec['offset']+rec['width'];z0=base+rec['sill'];z1=z0+rec['height']
    back=(lo,lo+t) if rec['side']>0 else (hi-t,hi)
    return [(a,a+t,lo,hi,z0,z1),(b-t,b,lo,hi,z0,z1),
            (a+t,b-t,lo,hi,z0,z0+t),(a+t,b-t,lo,hi,z1-t,z1),
            (a+t,b-t,*back,z0+t,z1-t)]


def body_element(spec, rec, wall, level):
    from .exchange import _element
    from .geom import solids as S, polygon as P
    cells=[];volume=0.;base=float(wall.get('base',0))
    for a,b,lo,hi,z0,z1 in body_parts(spec,rec,base):
        poly=P.ccw([spec.point(a,lo),spec.point(b,lo),spec.point(b,hi),spec.point(a,hi)])
        cells.append((poly,(z0,z1)));volume+=(b-a)*(hi-lo)*(z1-z0)
    faces=S.boundary(cells)
    m={'name':'Cuerpo de '+(rec.get('name')or'Armario fijo'), 'base':base+rec['sill'],
       'height':rec['height'],'material':rec.get('body_material')or'Madera'}
    area=abs(P.area(footprint(spec,rec)))
    el=_element(rec['id']+'-cuerpo','IfcBuildingElementProxy',m,faces,volume,area,level)
    el.update(host=wall['id'],enums={'PredefinedType':'USERDEFINED'},attributes={'ObjectType':'ARMARIO_FIJO'})
    el['params'].update(cabinet_id=rec['id'],cabinet_mode='adosado',width=rec['width'],depth=rec['niche_depth'])
    el['psets']['ARQ_Armario']={'ArmarioFijo':True,'Muro':wall['id'],'SourceId':rec['id'],'SuperficieOcupada':area}
    el['quantities']={'NetVolume':volume,'Height':rec['height'],'NetFloorArea':area}
    el['footprint']=[[footprint(spec,rec),[]]]
    return el


def placed(drawing,skip=()):
    from .architectural import metadata
    if not any((metadata(e)or{}).get('cabinet_mode')=='adosado' for e in drawing.modelspace()):return []
    from .exchange import read_model
    from .geom.junctions import walls_from_records
    walls,_,openings,_=read_model(drawing,skip=skip,strict=False)
    records=dict(walls);specs={w.id:w for w in walls_from_records(walls)};out=[]
    for rec in openings:
        if rec.get('cabinet_mode')!='adosado' or rec['wall_id']not in specs:continue
        wall=records[rec['wall_id']];poly=footprint(specs[rec['wall_id']],rec)
        z0=float(wall.get('base',0))+rec['sill']
        out.append((poly,z0,z0+rec['height'],rec['id']))
    return out


def obstacles(drawing,record,room,items=None):
    """Fixed furniture occupying this space, in absolute coordinates."""
    from .geom import polygon as P
    items=placed(drawing) if items is None else items
    out=[]
    for poly,z0,z1,ident in items:
        if z1<=float(record.get('base',0))+1e-8 or z0>=float(record.get('base',0))+float(record['height'])-1e-8:continue
        if P.overlap_area(room['pieces'],[poly])>1e-9:out.append((poly,z0,z1,ident))
    return out


def useful_room(room, obstacles):
    """Subtract a union, so adjoining/overlapping cabinets never double count."""
    from .geom import polygon as P
    if not obstacles:return room
    pieces=room['pieces']
    for poly,*_ in obstacles:pieces=P.subtract(pieces,poly)
    from .geom.spaces import _perimeter
    perimeter=sum(_perimeter(loop)for outer,holes in P.merge(pieces)for loop in [outer,*holes])
    return {**room,'pieces':pieces,'area':sum(P.area(p)for p in pieces),'perimeter':perimeter}


def useful_by_criterion(room, obstacles, criterio):
    """La superficie útil del recinto según el criterio del proyecto
    (PARAMETROSARQ > General): sin la planta de los armarios si
    «descuentan», entera si «computan»."""
    return room if criterio == 'computan' else useful_room(room, obstacles)


def occupied_area(room, obstacles):
    """Planta de los armarios dentro del recinto (m²), sin contar dos veces
    los que se tocan o se solapan."""
    return room['area'] - useful_room(room, obstacles)['area'] if obstacles else 0.0


def clip_air(envelope, obstacles):
    """Remove occupied envelopes using the same cell boundary engine as R16-3."""
    from .geom import polygon as P, solids as S
    if not obstacles:return envelope
    cells=envelope['cells']
    for poly,z0,z1,_ in obstacles:
        out=[]
        for piece,(lo,hi) in cells:
            inter=P.convex_intersection(piece,poly)
            if not inter or z1<=lo or z0>=hi:out.append((piece,(lo,hi)));continue
            out.extend((p,(lo,hi))for p in P.convex_difference(piece,poly))
            out.extend((inter,interval)for interval in S._minus([(lo,hi)],z0,z1))
        cells=out
    if not cells:raise ValueError('El armario ocupa todo el volumen del recinto')
    return {**envelope,'cells':cells,'faces':S.boundary(cells),
            'volume':sum(P.area(p)*(hi-lo)for p,(lo,hi)in cells)}


def __getattr__(name):
    if name=="CabinetTool":
        from .cabinet_tools import CabinetTool
        return CabinetTool
    raise AttributeError(name)

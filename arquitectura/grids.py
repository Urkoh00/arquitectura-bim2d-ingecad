# SPDX-License-Identifier: GPL-3.0-or-later
"""Structural reference grids: native CAD entities, stable links and commands.

Grid axes are references, never solid IFC proxies. Dimensions and symbols
are derived, while user-created annotations are never erased here.
"""
from __future__ import annotations
import copy,math,re,uuid
from core.commands import Command
from core.actions import AddEntityCommand,AddDimensionCommand,EraseCommand
from core.layers import NewLayerCommand
from .architectural import metadata,_xdata
from .transactions import SafeArchitecturalCommand
from .sections import column_points

LAYER='ARQ-EJES'
ALPHABET='ABCDEFGHJKLMNPQRSTUVWXYZ'

def linetype_scale(drawing,scale):
    entry=drawing.linetypes.get('DASHDOT')
    length=sum(abs(float(t.value)) for t in entry.pattern_tags.tags if t.code==49)
    global_scale=float(drawing.header.get('$LTSCALE',1.)or 1.)
    if length<=0 or not math.isfinite(length*global_scale) or global_scale<=0:
        raise ValueError('DASHDOT o LTSCALE sin patrón positivo; revise el tipo de línea del dibujo')
    return .01*float(scale)/max(length*global_scale,1e-9)

def letter(number):
    if type(number) is not int or number<1:raise ValueError('Índice de letra positivo')
    result=''
    while number:
        number,rem=divmod(number-1,len(ALPHABET));result=ALPHABET[rem]+result
    return result

def letter_index(text):
    n=0
    for c in str(text).upper():
        if c not in ALPHABET:raise ValueError('Letra de eje no válida (se omiten I, O y Ñ)')
        n=n*len(ALPHABET)+ALPHABET.index(c)+1
    if not n:raise ValueError('Falta la letra inicial')
    return n

def distances(text):
    values=[0.]
    for token in str(text).lower().replace('×','x').replace(';',' ').split():
        m=re.fullmatch(r'(?:(\d+)x)?(\d+(?:[.,]\d+)?)',token)
        if not m:raise ValueError('Distancias: lista o n x d sin espacios internos, en metros')
        count=int(m.group(1) or 1);d=float(m.group(2).replace(',','.'))
        if count<1 or count>100 or len(values)+count>101 or not math.isfinite(d) or d<=0:
            raise ValueError('Separaciones positivas; máximo 100 intervalos')
        for _ in range(count):values.append(values[-1]+d)
    if len(values)<2:raise ValueError('Indique al menos un intervalo')
    return values

def axes(drawing):
    return [(e,metadata(e)) for e in drawing.modelspace() if (metadata(e)or{}).get('kind')=='grid_axis']

def endpoints(entity):return [tuple(map(float,p)) for p in entity.get_points('xy')]

def intersect(e,f):
    from .geom.drafting import line_intersection
    a,b=endpoints(e);c,d=endpoints(f)
    return line_intersection(a,(b[0]-a[0],b[1]-a[1]),c,(d[0]-c[0],d[1]-c[1]))

def basis(u_points,v_points):
    def unit(points):
        a,b=points;length=math.dist(a,b)
        if length<1e-9:raise ValueError('Eje de longitud nula')
        return ((b[0]-a[0])/length,(b[1]-a[1])/length)
    x,y=unit(v_points),unit(u_points)
    det=x[0]*y[1]-x[1]*y[0]
    if abs(det)<1e-8:raise ValueError('Ejes paralelos en vínculo de pilar')
    return x,y,det

def local_offset(delta,u_points,v_points):
    x,y,det=basis(u_points,v_points)
    return [(delta[0]*y[1]-delta[1]*y[0])/det,(x[0]*delta[1]-x[1]*delta[0])/det]

def intersections(drawing):
    result=[];aa=axes(drawing)
    for e,m in aa:
        if m['family']!='U':continue
        for f,n in aa:
            if n['family']!='V' or n['grid_id']!=m['grid_id']:continue
            p=intersect(e,f)
            if p is not None:
                result.append((p,{'grid_id':m['grid_id'],'u':m['id'],'v':n['id'],
                                   'mark':n['label']+'-'+m['label'],'offset':[0.,0.]}))
    return result

def binding(drawing,point,tol=.02):
    hits=[(math.dist(point,p),p,link) for p,link in intersections(drawing) if math.dist(point,p)<=tol]
    if not hits:return None
    hits.sort(key=lambda h:h[0])
    if len(hits)>1 and abs(hits[0][0]-hits[1][0])<1e-8:return None
    _,p,link=hits[0];lookup={m['id']:e for e,m in axes(drawing)}
    link['offset']=local_offset((point[0]-p[0],point[1]-p[1]),endpoints(lookup[link['u']]),endpoints(lookup[link['v']]))
    return link

def current_link(drawing,record):
    link=copy.deepcopy(record.get('grid_link'))
    if not link:return None
    lookup={m['id']:(e,m) for e,m in axes(drawing)}
    if link['u'] not in lookup or link['v'] not in lookup:return link
    e,u=lookup[link['u']];f,v=lookup[link['v']];p=intersect(e,f)
    if p is None:return link
    link.update(mark=v['label']+'-'+u['label'],offset=local_offset(
        (record['center'][0]-p[0],record['center'][1]-p[1]),endpoints(e),endpoints(f)))
    return link

def validate_axes(drawing):
    seen=set();labels=set()
    for e,m in axes(drawing):
        if m['id'] in seen:raise ValueError('Identidad de eje duplicada; no copie ejes sin crear otra rejilla')
        seen.add(m['id']);key=(m['grid_id'],m['family'],m['label'])
        if key in labels:raise ValueError('Etiqueta repetida en la familia de rejilla')
        labels.add(key)
        if not m['label'] or len(m['label'])>64:raise ValueError('Etiqueta de eje no válida')
        if len(endpoints(e))!=2 or math.dist(*endpoints(e))<1e-6:raise ValueError('Eje sin longitud')

class SetAxis(Command):
    name='ARQ EDITAR EJE';needs_regen=True
    def __init__(self,entity,points=None,**changes):
        self.handle=entity.dxf.handle;self.old=copy.deepcopy(metadata(entity));self.before=endpoints(entity)
        if not self.old or self.old.get('kind')!='grid_axis':raise ValueError('Seleccione un eje de rejilla')
        self.new={**self.old,**changes,'id':self.old['id']};self.after=points or self.before
        if len(self.after)!=2 or not all(math.isfinite(float(x)) for p in self.after for x in p):raise ValueError('Extremos no válidos')
        if math.dist(*self.after)<1e-6:raise ValueError('Eje de longitud nula')
    def apply(self,doc,rec,points):
        e=doc.doc.entitydb.get(self.handle);e.set_points(points);_xdata(doc.doc.modelspace(),e,rec);doc.dirty=True
    def do(self,doc):self.apply(doc,self.new,self.after)
    def undo(self,doc):self.apply(doc,self.old,self.before)

class SetColumn(Command):
    name='ARQ VINCULAR PILAR';needs_regen=True
    def __init__(self,e,rec):
        self.handle=e.dxf.handle;self.old=copy.deepcopy(metadata(e));self.new=copy.deepcopy(rec)
        self.before=[tuple(p) for p in e.get_points('xy')];self.after=column_points(rec['center'],rec)
    def apply(self,doc,rec,points):
        e=doc.doc.entitydb.get(self.handle);e.set_points(points);_xdata(doc.doc.modelspace(),e,rec);doc.dirty=True
    def do(self,doc):self.apply(doc,self.new,self.after)
    def undo(self,doc):self.apply(doc,self.old,self.before)

def create_grid(origin,values):
    xs=distances(values.get('x','3x5'));ys=distances(values.get('y','2x4'))
    if len(xs)*len(ys)>2500:raise ValueError('Máximo 2500 intersecciones')
    angle=math.radians(float(values.get('angle',0)));u=(math.cos(angle),math.sin(angle));v=(-u[1],u[0])
    if not all(math.isfinite(float(x)) for x in (*origin,angle)):raise ValueError('Origen o ángulo no finito')
    scale=float(values.get('scale',100));text=float(values.get('text_mm',2.5))*scale/1000
    radius=float(values.get('radius_mm',4))*scale/1000;extension=float(values.get('extension',1.))
    if not all(math.isfinite(x) and x>0 for x in (scale,text,radius,extension)):raise ValueError('Escala y tamaños positivos')
    first=int(values.get('first_number',1));first_l=letter_index(values.get('first_letter','A'))
    if first<1:raise ValueError('Numeración positiva')
    if values.get('bubble','circle') not in ('circle','hexagon'):raise ValueError('Burbuja no válida')
    if len(str(values.get('prefix','')))+len(str(values.get('suffix','')))>40:raise ValueError('Prefijo/sufijo demasiado largos')
    grid_id=uuid.uuid4().hex;commands=[]
    def pt(x,y):return (origin[0]+u[0]*x+v[0]*y,origin[1]+u[1]*x+v[1]*y)
    for family,positions in (('U',xs),('V',ys)):
        for i,position in enumerate(positions):
            a,b=(pt(position,-extension),pt(position,ys[-1]+extension)) if family=='U' else (pt(-extension,position),pt(xs[-1]+extension,position))
            rec={'kind':'grid_axis','id':uuid.uuid4().hex,'grid_id':grid_id,'family':family,'index':i,
                 'label':str(values.get('prefix',''))+(str(first+i) if family=='U' else letter(first_l+i))+str(values.get('suffix','')),
                 'prefix':str(values.get('prefix','')),'suffix':str(values.get('suffix','')),
                 'text_height':text,'radius':radius,'scale':scale,'linetype':'DASHDOT','lineweight_mm':.13,
                 'bubble':values.get('bubble','circle'),
                 'ends':[bool(values.get('start',True)),bool(values.get('end',True))],
                 'dimensions':bool(values.get('dimensions',True))}
            def factory(msp,a=a,b=b,rec=rec):
                return _xdata(msp,msp.add_lwpolyline([a,b],dxfattribs={'linetype':'DASHDOT',
                    'ltscale':linetype_scale(msp.doc,rec['scale']),'color':8,'lineweight':13}),rec)
            commands.append(AddEntityCommand('ARQ EJE',factory,layer=LAYER))
    from core.linetypes import LoadLinetypesCommand
    return SafeArchitecturalCommand('ARQ REJILLA',[LoadLinetypesCommand(['DASHDOT']),NewLayerCommand(LAYER,color=8),*commands,RegenerateGrid()])

class RegenerateGrid(Command):
    name='ARQ ACTUALIZAR REJILLA';needs_regen=True
    def __init__(self,before_axes=None,before_centers=None):
        self.inner=None;self.before_axes=before_axes;self.before_centers=before_centers or {}
    def do(self,doc):
        if self.inner is None:self.inner=self.build(doc)
        self.inner.do(doc)
    def undo(self,doc):
        if self.inner:self.inner.undo(doc)
    def build(self,doc):
        from .frame import reconcile
        validate_axes(doc.doc)
        msp=doc.doc.modelspace();aa=axes(doc.doc);byid={m['id']:(e,m) for e,m in aa}
        commands=[]
        generated=[e for e in msp if (metadata(e)or{}).get('kind')=='grid_symbol']
        # Dimensions own anonymous blocks, so use native EraseCommand only
        # on this plugin's derived entities. Other annotations are untouched.
        if generated:commands.append(EraseCommand(generated))
        for entity in list(msp):
            m=metadata(entity)or{}
            if m.get('kind')!='column' or not m.get('grid_link'):continue
            rec=reconcile(entity,m,[]);link=copy.deepcopy(rec['grid_link'])
            if link['u'] not in byid or link['v'] not in byid:continue
            e,mu=byid[link['u']];f,mv=byid[link['v']];p=intersect(e,f)
            if p is None:continue
            offset=link.get('offset',[0.,0.])
            # Preserve an explicit manual pillar displacement before the
            # current axis gesture. Geometry read through the native frame.
            if self.before_axes and link['u'] in self.before_axes and link['v'] in self.before_axes:
                from .geom.drafting import line_intersection
                a,b=self.before_axes[link['u']];c,d=self.before_axes[link['v']]
                old=line_intersection(a,(b[0]-a[0],b[1]-a[1]),c,(d[0]-c[0],d[1]-c[1]))
                source=self.before_centers.get(rec['id'],rec['center'])
                if old is not None:offset=local_offset((source[0]-old[0],source[1]-old[1]),self.before_axes[link['u']],self.before_axes[link['v']])
            link.update(mark=mv['label']+'-'+mu['label'],offset=offset)
            x,y,_=basis(endpoints(e),endpoints(f))
            new={**rec,'center':[p[0]+x[0]*offset[0]+y[0]*offset[1],p[1]+x[1]*offset[0]+y[1]*offset[1]],'grid_link':link}
            if new!=m:commands.append(SetColumn(entity,new))
        for entity,rec in aa:
            for enabled,p in zip(rec['ends'],endpoints(entity)):
                if not enabled:continue
                def circle(msp,p=p,rec=rec):
                    tag={'kind':'grid_symbol','grid_id':rec['grid_id'],'axis_id':rec['id']}
                    if rec['bubble']=='hexagon':
                        pts=[(p[0]+rec['radius']*math.cos(i*math.tau/6),p[1]+rec['radius']*math.sin(i*math.tau/6)) for i in range(6)]
                        e=msp.add_lwpolyline(pts,close=True)
                    else:e=msp.add_circle(p,rec['radius'])
                    return _xdata(msp,e,tag)
                def text(msp,p=p,rec=rec):
                    from ezdxf.enums import TextEntityAlignment
                    e=msp.add_text(rec['label'],dxfattribs={'height':rec['text_height']});e.set_placement(p,align=TextEntityAlignment.MIDDLE_CENTER)
                    return _xdata(msp,e,{'kind':'grid_symbol','grid_id':rec['grid_id'],'axis_id':rec['id']})
                commands.extend([AddEntityCommand('ARQ BURBUJA',circle,layer=LAYER),AddEntityCommand('ARQ MARCA',text,layer=LAYER)])
        for gid in {m['grid_id'] for e,m in aa}:
            members=[(e,m) for e,m in aa if m['grid_id']==gid]
            if not any(m['dimensions'] for e,m in members):continue
            for family,other in (('U','V'),('V','U')):
                lines=sorted([(e,m) for e,m in members if m['family']==family],key=lambda z:z[1]['index'])
                cross=next((e for e,m in members if m['family']==other),None)
                points=[intersect(e,cross) for e,m in lines] if cross is not None else []
                if len(points)<2 or any(p is None for p in points):continue
                for j,(a,b) in enumerate(list(zip(points,points[1:]))+[(points[0],points[-1])]):
                    base=((a[0]+b[0])/2,(a[1]+b[1])/2)
                    rec=lines[0][1]
                    margin=max(math.dist(p,endpoints(e)[0]) for (e,m),p in zip(lines,points))
                    distance=margin+rec['radius']*(3 if j<len(points)-1 else 5)
                    if family=='U':distance=-distance
                    def dim(msp,document,a=a,b=b,base=base,rec=rec,distance=distance,gid=gid):
                        result=msp.add_aligned_dim(p1=a,p2=b,distance=distance,
                              override={'dimtxt':rec['text_height'],'dimasz':rec['text_height']*.7,'dimscale':1})
                        _xdata(msp,result.dimension,{'kind':'grid_symbol','grid_id':gid,'role':'dimension'})
                        return result
                    command=AddDimensionCommand(dim);command.layer=LAYER;commands.append(command)
        if aa:
            digest=axis_digest(doc.doc)
            where=endpoints(aa[0][0])[0]
            def stamp(msp):return _xdata(msp,msp.add_point(where,dxfattribs={'invisible':1}),
                                         {'kind':'grid_symbol','role':'sync','axis_digest':digest})
            commands.append(AddEntityCommand('ARQ ESTADO REJILLA',stamp,layer=LAYER))
        return SafeArchitecturalCommand('ARQ REJILLA DERIVADA',commands)

def snapshot(drawing):
    return {m['id']:endpoints(e) for e,m in axes(drawing)}

def axis_digest(drawing):
    import hashlib,json
    return hashlib.sha256(json.dumps(snapshot(drawing),sort_keys=True).encode()).hexdigest()

class GridReactor:
    name='arquitectura_rejillas'
    def before(self,doc):
        from .frame import reconcile
        aa=snapshot(doc.doc)
        if not aa:return {'axes':{},'centers':{}}
        centers={m['id']:reconcile(e,m,[])['center'] for e in doc.doc.modelspace()
                 if (m:=metadata(e)or{}).get('kind')=='column' and m.get('grid_link')}
        return {'axes':aa,'centers':centers}
    def react(self,doc,state):
        state=state or {'axes':{},'centers':{}}
        if snapshot(doc.doc)==state['axes']:return None
        digest=axis_digest(doc.doc)
        if any((metadata(e)or{}).get('axis_digest')==digest for e in doc.doc.modelspace()
               if (metadata(e)or{}).get('role')=='sync'):return None
        from .transactions import ArchitecturalRegeneration
        return SafeArchitecturalCommand('ARQ EJES Y ENCUENTROS',[
            RegenerateGrid(state['axes'],state['centers']),ArchitecturalRegeneration()])

def update(ctx):
    from .transactions import apply_architectural_change
    apply_architectural_change(ctx,RegenerateGrid(),kind='column')

def place_columns(ctx,values,selected=None):
    from .compat import require_document
    from .columns import column_command
    from .transactions import apply_architectural_change
    d=require_document(ctx).doc;points=intersections(d)
    existing={(m['grid_link']['u'],m['grid_link']['v']) for e in d.modelspace()
              if (m:=metadata(e)or{}).get('kind')=='column' and m.get('grid_link')}
    commands=[]
    for i,(p,link) in enumerate(points):
        if selected is not None and i not in selected:continue
        if (link['u'],link['v']) not in existing:commands.append(column_command(p,{**values,'grid_link':link}))
    if not commands:return False
    apply_architectural_change(ctx,SafeArchitecturalCommand('ARQ PILARES EN EJES',commands),kind='column');return True

def contract(drawing):
    validate_axes(drawing)
    groups={}
    for e,m in axes(drawing):
        groups.setdefault(m['grid_id'],{'id':m['grid_id'],'axes':[]})['axes'].append({**m,'points':[list(p) for p in endpoints(e)]})
    from .frame import reconcile
    links=[{'column_id':m['id'],**current_link(drawing,reconcile(e,m,[]))} for e in drawing.modelspace()
           if (m:=metadata(e)or{}).get('kind')=='column' and m.get('grid_link')]
    lookup={m['id']:e for e,m in axes(drawing)}
    for link in links:
        if link['u'] not in lookup or link['v'] not in lookup or intersect(lookup[link['u']],lookup[link['v']]) is None:
            raise ValueError('Un pilar conserva un vínculo con ejes ausentes o paralelos; repare la rejilla antes de exportar')
    return {'grids':list(groups.values()),'column_links':links,'ifc_grid_exported':False}

class GridGrips:
    def grips(self,e):
        if (metadata(e)or{}).get('kind')!='grid_axis':return None
        a,b=endpoints(e);return [(a[0],a[1],'endpoint'),(b[0],b[1],'endpoint')]
    def move(self,e,index,role,point):return True
    def drop(self,ctx,e,index,role,point):
        before=snapshot(e.doc);pts=endpoints(e);pts[index]=tuple(point[:2])
        from .transactions import ArchitecturalRegeneration
        return SafeArchitecturalCommand('ARQ PINZAMIENTO EJE',[SetAxis(e,pts),RegenerateGrid(before),ArchitecturalRegeneration()])

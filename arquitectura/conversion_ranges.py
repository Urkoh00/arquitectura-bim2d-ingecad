# SPDX-License-Identifier: GPL-3.0-or-later
"""Category ranges by composing existing read-only conversion plans."""
import math
from .conversion_plan import Classification,WALLS,analyse,Plan,fingerprint


def analyse_ranges(drawing,lo,hi,classification,tmin,tmax,height,parallel,origin,selected_handles):
    bounds={}
    for role in WALLS:
        v=classification.thickness_ranges.get(role,(tmin,tmax))
        if len(v)!=2 or not all(math.isfinite(float(x))for x in v)or not 0<float(v[0])<=float(v[1]):
            raise ValueError('Rango de espesores inválido: '+role)
        bounds[role]=tuple(map(float,v))
    unknown=set(classification.thickness_ranges)-WALLS
    if unknown:raise ValueError('Categoría sin rango de muro')
    plans=[]
    for i,role in enumerate(sorted(WALLS)):
        def keep(r):return r not in WALLS or r==role
        layers={k:v for k,v in classification.layers.items()if keep(v)and(i==0 or v!='pilares')}
        handles={k:v for k,v in classification.handles.items()if keep(v)and(i==0 or v!='pilares')}
        selected=set(selected_handles)if selected_handles is not None else{e.dxf.handle for e in drawing.modelspace()}
        selected-={k for k,v in classification.handles.items()if not keep(v)or(i>0 and v=='pilares')}
        c=Classification(layers,handles,True)
        plans.append(analyse(drawing,lo,hi,c,*bounds[role],height,parallel,origin,selected))
    walls=[];ops=[];curves=[];curved_ops=[];columns=[];loose=[];blocks=0;sources=[];roles=[];details=[];review=[];warnings=[]
    for p in plans:
        w,o,raw,c,col,unpaired,b=p.result
        ops.extend((k+len(walls),*rest)for k,*rest in o)
        curved_ops.extend((k+len(curves),*rest)for k,*rest in p.curved_openings)
        walls.extend(w);curves.extend(c);columns.extend(col);loose.extend(unpaired);blocks+=b
        sources.extend(e for e in p.sources if e not in sources)
        roles.extend(p.wall_roles);details.extend(p.opening_details);review.extend(p.review_segments);warnings.extend(p.warnings)
    from .conversion_evidence import recover_terminal_doors
    from . import convert_tools as C
    reader=plans[0].opening_reader
    old_count=len(ops)
    walls,ops,recovered=recover_terminal_doors(walls,ops,reader)
    details.extend(reader.attributes(walls,ops[old_count:]))
    from .conversion_evidence import exterior_side,window_frame
    for number,(k,pos,width,kind,hinge,side)in enumerate(ops):
        if kind!='window':continue
        a,b,t=walls[k];length=math.dist(a,b);u=((b[0]-a[0])/length,(b[1]-a[1])/length);mid=(a[0]+u[0]*pos,a[1]+u[1]*pos)
        interior,placement=window_frame(reader,mid,width,u,t,exterior_side(walls,k,pos))
        if placement:
            details[number]=placement;ops[number]=(k,pos,width,kind,hinge,interior)
    # Terminal evidence may need a transverse wall from another category.
    # Keep source removal in the same final plan and undo transaction.
    consumed=set()
    for e in drawing.modelspace():
        if e.dxftype()=='INSERT'or classification.role(e)not in ('puertas','ventanas','carpinteria','vanos'):continue
        if selected_handles is not None and e.dxf.handle not in selected_handles:continue
        segments=C._segments(e)
        if not segments or not all(min(lo[0],hi[0])<=x<=max(lo[0],hi[0])and min(lo[1],hi[1])<=y<=max(lo[1],hi[1])for s in segments for x,y in(s[:2],s[2:])):continue
        for number,(k,pos,width,kind,hinge,side)in enumerate(ops):
            a,b,t=walls[k];length=math.dist(a,b);u=((b[0]-a[0])/length,(b[1]-a[1])/length);mid=(a[0]+u[0]*pos,a[1]+u[1]*pos)
            reader.swings(mid,width,u,t)or reader.sliding(mid,width,u,t)
            if reader.owns(e,mid,width,u,t,kind,details[number]):
                if e not in sources:sources.append(e)
                consumed.update(((s[0],s[1]),(s[2],s[3]))for s in segments)
                break
    review=[s for s in review if s not in consumed]
    warnings=[w for w in warnings if not w.startswith('Carpintería:')]
    if review:warnings.append('Carpintería: trazos sin lectura completa conservados y resaltados para revisión')
    if all(details[i].get('face')=='distancia'for i,o in enumerate(ops)if o[3]=='window'):
        warnings=[w for w in warnings if not w.startswith('Ventana sin posición')]
    return Plan((walls,ops,[],curves,columns,loose,blocks),sources,list(dict.fromkeys(warnings)),
        drawing,fingerprint(drawing),(lo,hi),height,origin,roles,curved_ops,details,list(dict.fromkeys(review)))

# SPDX-License-Identifier: GPL-3.0-or-later
"""Circular carpentry from the existing straight piece definition.

The common station list is used by both plan sections and closed 3D cells.
No generator is invoked in the receiving application.
"""
import math
from .geom import polygon as P,solids as S
from .geom.junctions import Wall

def validate(rec):
    mode=rec.get('curve_mode','plana')
    if mode not in ('plana','curva'):raise ValueError('Modo de carpintería no válido')
    ref=rec.get('width_reference','cuerda' if mode=='plana' else 'eje')
    if ref not in ('cuerda','eje','interior','exterior'):raise ValueError('Referencia de ancho no válida')
    if mode=='curva' and ref=='cuerda':raise ValueError('Seleccione una referencia de arco para carpintería curva')
    sag=float(rec.get('facet_sagitta',.005))
    if not math.isfinite(sag) or not .0001<=sag<=.02:
        raise ValueError('Flecha de facetado entre 0,0001 y 0,02 m')
    if mode=='curva' and rec['type']!='gap' and rec.get('operation') not in ('FIXED','SLIDING'):
        raise ValueError('Carpintería curva: use fija o corredera; hojas abatibles planas en polígono pendientes')

def pieces(spec,rec,base):
    from . import openings as O
    validate(rec)
    fake=Wall(spec.id,(0.,0.),(spec.length,0.),spec.thickness,spec.reference)
    plain={**rec,'curve_mode':'plana','chord':float(rec['width'])}
    template=O.carpentry_parts(fake,plain,base)
    # A sill flush with the exterior frame would touch it along an edge:
    # two closed pieces then produce valence four in the single mesh.
    # Preserve the existing assembly gap, also in the developed preview.
    for part in template:
        if part['role']=='sill' and 'box' in part:
            a,b,p,q,z0,z1=part['box']
            part['box']=(a,b,p,q,z0-O.PART_GAP,z1-O.PART_GAP)
    boxes=[]
    for part in template:
        if 'box' in part:
            boxes.append([part['box']]);continue
        outer,holes,lo,hi=part['prism']
        a,b=min(x for x,z in outer),max(x for x,z in outer)
        z0,z1=min(z for x,z in outer),max(z for x,z in outer)
        if not holes:boxes.append([(a,b,lo,hi,z0,z1)]);continue
        inner=holes[0];c,d=min(x for x,z in inner),max(x for x,z in inner)
        p,q=min(z for x,z in inner),max(z for x,z in inner)
        boxes.append([(a,c,lo,hi,z0,z1),(d,b,lo,hi,z0,z1),
                      (c,d,lo,hi,z0,p),(c,d,lo,hi,q,z1)])
    offsets=[x for group in boxes for a,b,p,q,z0,z1 in group for x in (p,q)]
    rmax=max([spec.r]+[spec.r-spec.d*x for x in offsets])
    if min([spec.r]+[spec.r-spec.d*x for x in offsets])<=1e-6:
        raise ValueError('Radio insuficiente para las piezas de carpintería')
    edges=sorted({x for group in boxes for a,b,p,q,z0,z1 in group for x in (a,b)})
    sag=min(float(rec.get('facet_sagitta',.005)),.002)
    step=2*math.acos(max(-1.,1-sag/rmax))*spec.r
    if len(edges)>1000 or (edges and (edges[-1]-edges[0])/step>10000):
        raise ValueError('Facetado excesivo; aumente la flecha')
    stations=[]
    for a,b in zip(edges,edges[1:]):
        n=max(1,math.ceil((b-a)/step))
        stations.extend(a+(b-a)*i/n for i in range(n))
    if edges:stations.append(edges[-1])
    result=[]
    for source,group in zip(template,boxes):
        cells=[];sections=[]
        for a,b,p,q,z0,z1 in group:
            if min(b-a,q-p,z1-z0)<=1e-8:continue
            ss=[s for s in stations if a-1e-9<=s<=b+1e-9]
            polygon=P.ccw([spec.point(s,p) for s in ss]+[spec.point(s,q) for s in reversed(ss)])
            sections.append({'polygon':polygon,'base':z0,'height':z1-z0})
            for x,y in zip(ss,ss[1:]):
                quad=P.ccw([spec.point(x,p),spec.point(y,p),spec.point(y,q),spec.point(x,q)])
                cells.append((quad,(z0,z1)))
        faces=S.boundary(cells)
        volume=math.fsum(P.area(poly)*(z1-z0) for poly,(z0,z1) in cells)
        result.append({'name':source['name'],'role':source['role'],'material':source['material'],
                       'faces':faces,'volume':volume,'sections':sections,
                       'stations':stations,'unrolled':source})
    return result

def symbol(spec,rec):
    base=0.;z=float(rec['sill'])+float(rec['height'])/2
    out=[]
    for part in pieces(spec,rec,base):
        for section in part['sections']:
            if section['base']-1e-9<=z<=section['base']+section['height']+1e-9:
                out.append(('poly',section['polygon'],True))
    return out

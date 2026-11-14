# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent small drafting conventions. No private geometry is imported."""
import math
import ezdxf
from shapely.geometry import Polygon
from shapely.ops import unary_union
from arquitectura.geom.junctions import Wall

WALL='Muros ensayo'; CARP='Carpinteria ensayo'


def document():
    d=ezdxf.new();d.header['$INSUNITS']=6
    for name in (WALL,CARP):d.layers.new(name)
    return d


def faces(d,intervals,t=.2):
    for y in (-t/2,t/2):
        for a,b in intervals:d.modelspace().add_line((a,y),(b,y),dxfattribs={'layer':WALL})


def panels(d):
    # Two closed panels offset on their tracks; exactly the same lines may
    # depict a sliding WINDOW. Category must disambiguate the height/use.
    for a,b,y in ((1.,1.65,-.035),(1.55,2.2,.035)):
        d.modelspace().add_lwpolyline([(a,y),(b,y),(b,y+.02),(a,y+.02)],close=True,dxfattribs={'layer':CARP})


def network(kind,angle=30):
    d=document();r=math.radians(angle);p=(4*math.cos(r),4*math.sin(r))
    if kind=='L':ws=[Wall('a',(-4,0),(0,0),.2),Wall('b',(0,0),p,.3)]
    elif kind=='T':ws=[Wall('a',(-4,0),(4,0),.2),Wall('b',p,(0,0),.3)]
    elif kind=='X':ws=[Wall('a',(-4,0),(4,0),.2),Wall('b',(-p[0],-p[1]),p,.3)]
    else:raise ValueError(kind)
    from arquitectura.geom import junctions as J
    # Independent union of the intended network for T/X; L has the native
    # mitred corner footprint rather than an arbitrary square-ended union.
    if kind=='L':
        from tests.test_junctions import ideal_L
        shape=ideal_L(*ws)
    elif kind=='T':
        from tests.test_junctions import ideal_T
        shape=ideal_T(*ws)
    else:shape=unary_union([Polygon(w.strip()) for w in ws])
    for ring in [shape.exterior,*shape.interiors]:
        pts=list(ring.coords)
        for a,b in zip(pts,pts[1:]):d.modelspace().add_line(a,b,dxfattribs={'layer':WALL})
    return d,shape


def case(name):
    d=document();m=d.modelspace()
    if name=='doble_desigual':
        faces(d,[(0,1),(2.5,4)])
        m.add_arc((1,.1),.6,0,90,dxfattribs={'layer':CARP})
        m.add_arc((2.5,.1),.9,90,180,dxfattribs={'layer':CARP})
    elif name=='doble_reducida':
        faces(d,[(0,1),(2.2,4)])
        m.add_arc((1,.1),.6,0,90,dxfattribs={'layer':CARP})
        m.add_arc((2.2,.1),.6,90,180,dxfattribs={'layer':CARP})
    elif name=='jambas_desfasadas':
        for y,iv in ((-.1,[(0,1),(2.4,4)]),(.1,[(0,1.15),(2.35,4)])):
            for a,b in iv:m.add_line((a,y),(b,y),dxfattribs={'layer':WALL})
        m.add_arc((1.15,.1),1.2,0,90,dxfattribs={'layer':CARP})
    elif name=='corredera':
        faces(d,[(0,1),(2.2,4)]);panels(d)
    elif name=='bolsillo_ambiguo':
        faces(d,[(0,1),(2.2,4)])
        m.add_lwpolyline([(2.25,-.03),(3.45,-.03),(3.45,.01),(2.25,.01)],close=True,dxfattribs={'layer':CARP})
    else:raise ValueError(name)
    return d

CASES=('doble_desigual','doble_reducida','jambas_desfasadas','corredera','bolsillo_ambiguo')

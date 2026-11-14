# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent synthetic conventions; no coordinates read from private files."""
import math
import ezdxf

def setup():
    d=ezdxf.new();d.header['$INSUNITS']=6
    for n in ('Muro ensayo','Carpinteria ensayo'):d.layers.new(n)
    return d

def line(m,a,b,carp=False):
    return m.add_line(a,b,dxfattribs={'layer':'Carpinteria ensayo' if carp else 'Muro ensayo'})

def wall(m,intervals,thickness=.2,y=0.,short=False):
    for yy in (y,y+thickness):
        for a,b in intervals:
            n=math.ceil((b-a)/.08) if short else 1
            for i in range(n):line(m,(a+(b-a)*i/n,yy),(a+(b-a)*(i+1)/n,yy))

def double(m,a,b,y):
    r=(b-a)/2
    for x,start,end in ((a,0,90),(b,90,180)):
        m.add_arc((x,y),r,start,end,dxfattribs={'layer':'Carpinteria ensayo'})
        # Open four-vertex frame, not a continuous drawn door leaf.
        m.add_lwpolyline([(x-.025,y-.2),(x+.025,y-.2),(x+.025,y+.05),(x-.025,y+.05)],
                         dxfattribs={'layer':'Carpinteria ensayo'})

def case(name):
    d=setup();m=d.modelspace()
    if name=='doble':
        wall(m,[(0,1),(2.8,4.)]);double(m,1,2.8,.2)
    elif name=='tabique_fragmentado':
        wall(m,[(0,.32),(1.22,1.54)],.1,short=True)
        m.add_arc((.32,.1),.9,0,90,dxfattribs={'layer':'Carpinteria ensayo'})
    elif name=='machones':
        wall(m,[(0,.4),(2.4,2.8)])
        # A nearby stroke is not anchored in BOTH jambs of the empty passage.
        line(m,(.2,.1),(2.,.1),carp=True)
    elif name=='retranqueo':
        wall(m,[(0,1.8),(3.6,5.4)],.2)
        wall(m,[(1.8,2.1),(3.3,3.6)],.2,y=1.)
        for x in (1.7,1.9,3.5,3.7):line(m,(x,0),(x,1.2))
        double(m,2.1,3.3,1.2)
    elif name=='ventana_alfeizar':
        wall(m,[(0,1.2),(2.4,4.)])
        for y in (.04,.10,.16):line(m,(1.2,y),(2.4,y),carp=True)
        line(m,(1.1,-.15),(2.5,-.15),carp=True)
        for x in (1.2,2.4):
            m.add_lwpolyline([(x,-.15),(x+.05,-.15),(x+.05,.25),(x,.25)],dxfattribs={'layer':'Carpinteria ensayo'})
    else:raise ValueError(name)
    return d

CASES=('doble','tabique_fragmentado','machones','retranqueo','ventana_alfeizar')

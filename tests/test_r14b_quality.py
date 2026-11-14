# SPDX-License-Identifier: GPL-3.0-or-later
import math
import pytest
from ezdxf.math import Matrix44
from ezdxf import transform
from tests.synthetic_office import case,CASES,setup,wall,double
from tests.test_ingecad_integration import plugin
from tests.test_wall_tools import Session
from tests.test_r12_conversion import module

EXPECTED={
 'doble':(1,[(1.9,.1,1.8,'door')]),
 'tabique_fragmentado':(1,[(.77,.05,.9,'door')]),
 'machones':(2,[]),
 'retranqueo':(5,[(2.7,1.1,1.2,'door')]),
 'ventana_alfeizar':(1,[(1.8,.1,1.2,'window')]),
}

def analyse(s,d):
    P=module(s,'conversion_plan')
    return P,P.analyse(d,(-20,-20),(20,20),P.Classification({'Muro ensayo':'muros','Carpinteria ensayo':'carpinteria'}))

def centres(plan):
    out=[]
    for k,pos,width,kind,_h,_s in plan.result[1]:
        a,b,t=plan.result[0][k];L=math.dist(a,b)
        out.append((a[0]+(b[0]-a[0])*pos/L,a[1]+(b[1]-a[1])*pos/L,width,kind))
    return out

@pytest.mark.parametrize('name',CASES)
@pytest.mark.parametrize('angle',[0,37,90])
def test_independent_synthetic_patterns_at_real_scale(plugin,name,angle):
    s=Session(plugin);d=case(name);matrix=Matrix44.z_rotate(math.radians(angle))
    transform.inplace(d.modelspace(),matrix)
    P,p=analyse(s,d);count,expected=EXPECTED[name]
    assert len(p.result[0])==count and len(p.result[1])==len(expected)
    assert all(t==pytest.approx(.1 if name=='tabique_fragmentado' else .2) for a,b,t in p.result[0])
    for x,y,width,kind in expected:
        point=matrix.transform((x,y,0))
        assert any(math.dist((xx,yy),(point.x,point.y))<1e-6 and w==pytest.approx(width) and k==kind
                   for xx,yy,w,k in centres(p))

@pytest.mark.parametrize('thickness',[.10,.12,.20,.25,.38])
def test_double_swing_without_leaf_is_not_lost_at_wall_thicknesses(plugin,thickness):
    s=Session(plugin);d=setup();m=d.modelspace()
    wall(m,[(0,1),(2.8,4)],thickness);double(m,1,2.8,thickness)
    _,p=analyse(s,d);assert len(p.result[0])==1
    assert len(p.result[1])==1 and p.result[1][0][3]=='door'

def test_unrelated_arcs_on_opposite_sides_do_not_make_double_door(plugin):
    s=Session(plugin);d=setup();m=d.modelspace();wall(m,[(0,1),(2.8,4)])
    m.add_arc((1,.2),.9,0,90,dxfattribs={'layer':'Carpinteria ensayo'})
    m.add_arc((2.8,0),.9,180,270,dxfattribs={'layer':'Carpinteria ensayo'})
    _,p=analyse(s,d)
    assert all(o[3]!='door' for o in p.result[1])

def test_preview_has_different_native_symbols_without_mutating_source(plugin):
    s=Session(plugin);P,p=analyse(s,case('doble'));before=P.fingerprint(p.drawing)
    assert p.opening_symbols()['door'] and not p.opening_symbols()['window']
    assert len(p.segments)>len(p.result[0]);assert P.fingerprint(p.drawing)==before
    _,v=analyse(s,case('ventana_alfeizar'));assert v.opening_symbols()['window']
    # A long wall with a genuine plain opening is not a row of short piers.
    d=setup();wall(d.modelspace(),[(0,2),(3,5)])
    _,g=analyse(s,d);assert len(g.result[1])==1 and g.result[1][0][3]=='void'
    assert len(g.opening_symbols()['void'])==2

def test_short_strokes_are_not_bridged_across_an_opening(plugin):
    s=Session(plugin);d=case('tabique_fragmentado');_,p=analyse(s,d)
    assert p.result[1][0][2]==pytest.approx(.9)

def test_commit_with_double_door_retains_identity_and_one_undo(plugin):
    s=Session(plugin);d=s.document.doc;generated=case('doble')
    for layer in ('Muro ensayo','Carpinteria ensayo'):d.layers.new(layer)
    for e in generated.modelspace():d.modelspace().add_entity(e.copy())
    P,p=analyse(s,d);before=P.fingerprint(d);P.commit(s.tool('LINEASAMURO').ctx,p)
    ids={s.meta(e)['id'] for e in d.modelspace() if (s.meta(e)or{}).get('kind')=='opening'}
    assert len(ids)==1 and len(s.walls())==1
    s.history.undo();assert not s.walls()
    s.history.redo();assert ids=={s.meta(e)['id'] for e in d.modelspace() if (s.meta(e)or{}).get('kind')=='opening'}

def test_fragmented_window_glazing_is_still_anchored(plugin):
    s=Session(plugin);d=setup();m=d.modelspace();wall(m,[(0,1),(2.2,4)])
    for y in (.05,.1,.15):
        for i in range(4):
            m.add_line((1+i*.3,y),(1+(i+1)*.3,y),dxfattribs={'layer':'Carpinteria ensayo'})
    _,p=analyse(s,d);assert len(p.result[1])==1 and p.result[1][0][3]=='window'

def test_double_swing_pivots_inset_inside_wider_frame(plugin):
    s=Session(plugin);d=setup();m=d.modelspace();wall(m,[(0,1),(2.9,4)])
    double(m,1.13,2.77,.2)
    _,p=analyse(s,d);assert len(p.result[0])==1 and p.result[1][0][3]=='door'
    assert p.result[1][0][2]==pytest.approx(1.9)

def test_multi_line_glazing_with_inset_frame_is_not_lost(plugin):
    s=Session(plugin);d=setup();m=d.modelspace();wall(m,[(0,1),(2.8,4)])
    for y in (.04,.10,.16):
        m.add_line((1.23,y),(2.57,y),dxfattribs={'layer':'Carpinteria ensayo'})
    _,p=analyse(s,d);assert len(p.result[1])==1 and p.result[1][0][3]=='window'

def test_piers_of_different_thickness_are_not_bridged(plugin):
    s=Session(plugin);d=setup();m=d.modelspace()
    wall(m,[(0,.4)],.2);wall(m,[(2.4,2.8)],.25)
    m.add_line((.2,.1),(2,.1),dxfattribs={'layer':'Carpinteria ensayo'})
    _,p=analyse(s,d);assert len(p.result[0])==2 and not p.result[1]
    assert sorted(w[2] for w in p.result[0])==pytest.approx([.2,.25])

def test_combined_real_scale_synthetic_sheet(plugin):
    s=Session(plugin);d=setup();m=d.modelspace()
    for i,name in enumerate(CASES):
        other=case(name)
        for e in other.modelspace():
            copied=e.copy();copied.translate(2,i*3+1,0);m.add_entity(copied)
    d.layers.new('Referencia ensayo');m.add_lwpolyline([(0,0),(11,0),(11,16),(0,16)],close=True,dxfattribs={'layer':'Referencia ensayo'})
    _,p=analyse(s,d)
    assert len(p.result[0])==10
    assert sorted(o[3] for o in p.result[1])==['door','door','door','window']

def test_short_unpaired_wall_source_is_not_hidden_on_commit(plugin):
    s=Session(plugin);d=s.document.doc
    for layer in ('Muro ensayo','Carpinteria ensayo'):d.layers.new(layer)
    for e in case('doble').modelspace():d.modelspace().add_entity(e.copy())
    orphan=d.modelspace().add_line((5,2),(5.25,2),dxfattribs={'layer':'Muro ensayo'})
    P,p=analyse(s,d);assert orphan not in p.sources
    P.commit(s.tool('LINEASAMURO').ctx,p);assert orphan.dxf.layer=='Muro ensayo'

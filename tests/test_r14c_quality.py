# SPDX-License-Identifier: GPL-3.0-or-later
import math
import pytest
from ezdxf import transform
from ezdxf.math import Matrix44
from shapely.geometry import Polygon
from shapely.ops import unary_union
from tests.test_ingecad_integration import plugin
from tests.test_wall_tools import Session
from tests.test_r12_conversion import module
from tests.synthetic_r14c import case,network,CARP,WALL


def analyse(s,d,carp='carpinteria'):
    P=module(s,'conversion_plan')
    return P,P.analyse(d,(-20,-20),(20,20),P.Classification({WALL:'muros',CARP:carp}))


def load(s,d):
    target=s.document.doc
    for name in (WALL,CARP):
        if name not in target.layers:target.layers.new(name)
    for e in d.modelspace():target.modelspace().add_entity(e.copy())
    return target


@pytest.mark.parametrize('angle',[0,37,90,147])
@pytest.mark.parametrize('name',['doble_desigual','doble_reducida'])
def test_double_leaf_semantics_reach_preview_commit_and_exchange(plugin,name,angle,tmp_path):
    s=Session(plugin);d=case(name);transform.inplace(d.modelspace(),Matrix44.z_rotate(math.radians(angle)))
    d=load(s,d);P,p=analyse(s,d);before=P.fingerprint(d)
    assert len(p.result[1])==1 and p.result[1][0][3]=='door'
    assert p.opening_details[0]['leaves']==2
    # Both hands must be drawn, not one oversized leaf. The public symbol
    # engine and preview receive the same record attributes.
    assert p.opening_symbols()['door'];assert P.fingerprint(d)==before
    assert P.commit(s.tool('LINEASAMURO').ctx,p)
    records=[s.meta(e) for e in d.modelspace() if (s.meta(e)or{}).get('kind')=='opening']
    assert len(records)==1;rec=records[0];assert rec['leaves']==2 and rec['operation']=='SWINGING'
    if name=='doble_desigual':assert rec['leaf']/rec['leaf2']==pytest.approx(2/3)
    O=module(s,'openings');J=module(s,'geom.junctions');host=next(iter(s.walls().values()))
    spec=J.walls_from_records([(s.meta(host)['id'],s.meta(host))])[0]
    assert sum(g[0]=='arc' for g in O.plan_symbol(spec,rec))==2
    element=next(e for e in s.export(tmp_path)['elements'] if e['ifc_class']=='IfcDoor')
    assert element['params']['leaves']==2 and element['enums']['OperationType']=='DOUBLE_DOOR_SINGLE_SWING'
    ident=rec['id'];s.history.undo();assert not s.walls();s.history.redo()
    assert next(s.meta(e) for e in d.modelspace() if (s.meta(e)or{}).get('kind')=='opening')['id']==ident


@pytest.mark.parametrize('angle',[0,37,90,147])
def test_jambs_width_centre_and_area_not_overlap_gap(plugin,angle,tmp_path):
    s=Session(plugin);d=case('jambas_desfasadas');matrix=Matrix44.z_rotate(math.radians(angle))
    transform.inplace(d.modelspace(),matrix);d=load(s,d);P,p=analyse(s,d)
    assert len(p.result[1])==1
    k,pos,width,*_=p.result[1][0];a,b,t=p.result[0][k];u=((b[0]-a[0])/math.dist(a,b),(b[1]-a[1])/math.dist(a,b))
    centre=(a[0]+u[0]*pos,a[1]+u[1]*pos);expected=matrix.transform((1.75,0,0))
    assert width==pytest.approx(1.2,abs=.005);assert math.dist(centre,(expected.x,expected.y))<=.005
    P.commit(s.tool('LINEASAMURO').ctx,p)
    # Plan-level removal must be exactly width*thickness, using the same
    # cut polygons as the native preview/solid pipeline, never swing radius.
    J=module(s,'geom.junctions');O=module(s,'openings')
    rec=next(s.meta(e) for e in d.modelspace() if (s.meta(e)or{}).get('kind')=='opening')
    host=next(iter(s.walls().values()));spec=J.walls_from_records([(s.meta(host)['id'],s.meta(host))])[0]
    solid=Polygon(spec.strip());cut=Polygon(O.cut_polygon(spec,rec,0.))
    after=solid.difference(cut);assert solid.area-after.area==pytest.approx(1.2*.2,abs=1e-8)
    assert after.intersection(cut).area<1e-12
    exported=next(e for e in s.export(tmp_path)['elements'] if e['ifc_class']=='IfcWall')
    assert exported['volume']==pytest.approx(solid.area*3.0-1.2*.2*2.1,abs=1e-7)
    for lo,hi in ((0,1.15),(2.35,4)):
        retained=Polygon([spec.point(lo,spec.lo),spec.point(hi,spec.lo),spec.point(hi,spec.hi),spec.point(lo,spec.hi)])
        assert retained.difference(after).area<1e-8


@pytest.mark.parametrize('angle',[0,37,90,147])
def test_sliding_requires_semantics_and_preserves_two_panels(plugin,angle,tmp_path):
    s=Session(plugin);d=case('corredera');transform.inplace(d.modelspace(),Matrix44.z_rotate(math.radians(angle)))
    P,p=analyse(s,d);assert p.result[1][0][3]=='void'
    assert any('ambiguos' in w for w in p.warnings)
    d=load(s,d);P,p=analyse(s,d,'puertas');assert p.result[1][0][3]=='door'
    assert p.opening_details[0]=={'operation':'SLIDING','leaves':2}
    assert not any('ambiguos' in w for w in p.warnings)
    P.commit(s.tool('LINEASAMURO').ctx,p)
    rec=next(s.meta(e) for e in d.modelspace() if (s.meta(e)or{}).get('kind')=='opening')
    assert rec['operation']=='SLIDING' and rec['leaves']==2 and rec['width']==pytest.approx(1.2)
    element=next(e for e in s.export(tmp_path)['elements'] if e['ifc_class']=='IfcDoor')
    assert element['enums']['OperationType']=='DOUBLE_DOOR_SLIDING'


@pytest.mark.parametrize('kind',['T','L','X'])
@pytest.mark.parametrize('angle',[20,30,45,90])
def test_conversion_junction_network_has_no_false_voids_or_lost_area(plugin,kind,angle):
    s=Session(plugin);d,ideal=network(kind,angle);P,p=analyse(s,d)
    assert len(p.result[0])==2 and not p.result[1]
    J=module(s,'geom.junctions');specs=[J.Wall(str(i),a,b,t) for i,(a,b,t) in enumerate(p.result[0])]
    result=J.solve(specs)
    # Native ownership and contour union, independent Shapely comparison.
    polys=[Polygon(piece) for v in result.walls.values() for piece in v['pieces']]
    union=unary_union(polys)
    assert abs(sum(p.area for p in polys)-union.area)<1e-7
    assert union.symmetric_difference(ideal).area<1e-7
    assert not result.warnings


def test_unrelated_swings_on_opposite_sides_never_become_double(plugin):
    s=Session(plugin);d=case('doble_reducida')
    arcs=list(d.modelspace().query('ARC'));arcs[1].dxf.start_angle=180;arcs[1].dxf.end_angle=270
    _,p=analyse(s,d)
    assert all(a.get('leaves',1)!=2 for a in p.opening_details)


def test_single_leaf_remains_single(plugin):
    s=Session(plugin);d=case('doble_reducida');d.modelspace().delete_entity(list(d.modelspace().query('ARC'))[1])
    _,p=analyse(s,d);assert all(a.get('leaves',1)!=2 for a in p.opening_details)

@pytest.mark.parametrize('role,kind,leaves',[('carpinteria','void',None),('puertas','door',1),('ventanas','window',None)])
def test_pocket_panel_does_not_invent_height_from_width(plugin,role,kind,leaves):
    s=Session(plugin);d=case('bolsillo_ambiguo');_,p=analyse(s,d,role)
    assert len(p.result[1])==1 and p.result[1][0][3]==kind
    if leaves:assert p.opening_details[0]=={'operation':'SLIDING','leaves':leaves}
    elif role=='carpinteria':assert any('bolsillo' in w for w in p.warnings)


@pytest.mark.parametrize('angle',[0,37,90])
def test_real_door_close_to_tee_not_filled_as_junction(plugin,angle):
    from tests.synthetic_r14c import document
    from arquitectura.geom.junctions import Wall
    s=Session(plugin);d,solid=network('T',90)
    hole=Polygon([(.4,-.2),(1.3,-.2),(1.3,.2),(.4,.2)])
    shape=solid.difference(hole)
    d=document()
    for poly in shape.geoms:
        pts=list(poly.exterior.coords)
        for a,b in zip(pts,pts[1:]):d.modelspace().add_line(a,b,dxfattribs={'layer':WALL})
    d.modelspace().add_arc((.4,.1),.9,0,90,dxfattribs={'layer':CARP})
    transform.inplace(d.modelspace(),Matrix44.z_rotate(math.radians(angle)))
    _,p=analyse(s,d)
    assert len(p.result[1])==1 and p.result[1][0][3]=='door'
    assert p.result[1][0][2]==pytest.approx(.9,abs=.005)

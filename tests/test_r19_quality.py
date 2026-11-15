# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent small drafting patterns, with no project geometry."""
import math
import pytest
import ezdxf
from ezdxf import transform
from ezdxf.math import Matrix44
from tests.test_ingecad_integration import plugin
from tests.test_wall_tools import Session
from tests.test_r12_conversion import module
from tests.synthetic_r14c import document,faces,case,WALL,CARP
from tests.test_r14c_quality import load,analyse


@pytest.mark.parametrize('angle',[0,37,90,147])
def test_only_recognised_door_arcs_move_and_one_undo(plugin,angle):
    s=Session(plugin);d=case('doble_reducida')
    unknown=d.modelspace().add_arc((7,6),.6,0,90,dxfattribs={'layer':CARP})
    transform.inplace(d.modelspace(),Matrix44.z_rotate(math.radians(angle)))
    d=load(s,d);arcs=list(d.modelspace().query('ARC'));P,p=analyse(s,d)
    assert arcs[0] in p.sources and arcs[1] in p.sources and arcs[2] not in p.sources
    before=[e.dxf.layer for e in arcs];P.commit(s.tool('LINEASAMURO').ctx,p)
    origin=module(s,'convert_tools').ORIGIN_LAYER
    assert [e.dxf.layer for e in arcs]==[origin,origin,CARP]
    s.history.undo();assert [e.dxf.layer for e in arcs]==before and not s.walls()


@pytest.mark.parametrize('angle',[0,37,90,147])
def test_window_frame_recess_and_sill_side_rotate_together(plugin,angle):
    s=Session(plugin);d=document();m=d.modelspace();faces(d,[(0,1),(2.2,4)],t=.3)
    m.add_lwpolyline([(1,-.08),(2.2,-.08),(2.2,-.02),(1,-.02)],close=True,dxfattribs={'layer':CARP})
    m.add_line((1,-.23),(2.2,-.23),dxfattribs={'layer':CARP})
    transform.inplace(m,Matrix44.z_rotate(math.radians(angle)));d=load(s,d);P,p=analyse(s,d,'ventanas')
    assert len(p.result[1])==1
    attrs=p.opening_details[0]
    assert attrs['frame_depth']==pytest.approx(.06)
    assert attrs['face']=='distancia' and attrs['setback_from']=='exterior'
    assert attrs['setback']==pytest.approx(.07)
    k,pos,width,kind,hinge,side=p.result[1][0];a,b,t=p.result[0][k]
    normal=(-(b[1]-a[1])/math.dist(a,b),(b[0]-a[0])/math.dist(a,b))
    expected=Matrix44.z_rotate(math.radians(angle)).transform_direction((0,1,0))
    assert side*(normal[0]*expected.x+normal[1]*expected.y)==pytest.approx(1)
    P.commit(s.tool('LINEASAMURO').ctx,p)
    rec=next(s.meta(e)for e in d.modelspace()if(s.meta(e)or{}).get('kind')=='opening')
    assert rec['setback']==pytest.approx(.07) and rec['width']==pytest.approx(1.2)


@pytest.mark.parametrize('explicit',[False,True])
@pytest.mark.parametrize('angle',[0,37,90])
def test_external_parked_double_slider_requires_category(plugin,explicit,angle):
    s=Session(plugin);d=document();faces(d,[(0,1),(2.2,4)])
    for a,b in ((.4,1),(2.2,2.8)):
        d.modelspace().add_lwpolyline([(a,.13),(b,.13),(b,.17),(a,.17)],close=True,dxfattribs={'layer':CARP})
    transform.inplace(d.modelspace(),Matrix44.z_rotate(math.radians(angle)))
    P,p=analyse(s,d,'puertas'if explicit else'carpinteria')
    assert p.result[1][0][3]==('door'if explicit else'void')
    if explicit:
        assert p.opening_details[0]['leaves']==2 and p.opening_details[0]['operation']=='SLIDING'
        d=load(s,d);P,p=analyse(s,d,'puertas');P.commit(s.tool('LINEASAMURO').ctx,p)
        rec=next(s.meta(e)for e in d.modelspace()if(s.meta(e)or{}).get('kind')=='opening')
        wall=next(iter(s.walls().values()));J=module(s,'geom.junctions');O=module(s,'openings')
        spec=J.walls_from_records([(s.meta(wall)['id'],s.meta(wall))])[0]
        leaves=[part for part in O.carpentry_parts(spec,rec,0)if part['role']=='leaf']
        assert len(leaves)==2
        for leaf in leaves:
            lo,hi=leaf['box'][2:4]
            assert lo>spec.hi if rec['side']>0 else hi<spec.lo
        leaf_polys=[g for g in O.plan_symbol(spec,rec)if g[0]=='poly'and
                    all(spec.local(pt)[1]>spec.hi+1e-8 if rec['side']>0 else
                        spec.local(pt)[1]<spec.lo-1e-8 for pt in g[1])]
        assert len(leaf_polys)==2
    else:assert p.review_segments and any('Corredera exterior ambigua'in w for w in p.warnings)


def test_canonical_roles_manual_stairs_and_cabinet_remain_visible(plugin):
    s=Session(plugin);P=module(s,'conversion_plan');d=s.document.doc
    names={'ARQ-MUROS':'muros','ARQ-TABIQUES':'tabiques','ARQ-PUERTAS':'puertas','ARQ-VENTANAS':'ventanas','ARQ-PILARES':'pilares','ARQ-ARMARIOS':'armarios','ARQ-ESCALERAS':'escaleras'}
    assert P.guess_roles(names)==names
    for n in names:
        if n not in d.layers:d.layers.new(n)
    stair=d.modelspace().add_line((1,1),(2,1),dxfattribs={'layer':'ARQ-ESCALERAS'})
    cabinet=d.modelspace().add_lwpolyline([(3,1),(4,1),(4,1.5),(3,1.5)],close=True,dxfattribs={'layer':'ARQ-ARMARIOS'})
    p=P.analyse(d,(0,0),(6,6),P.Classification(names))
    assert any('Escaleras: 1 objetos clasificados'in w for w in p.warnings)
    assert cabinet not in p.sources and stair not in p.sources and not p.result[1]


def test_partition_is_not_just_a_label(plugin,tmp_path):
    s=Session(plugin);d=document();faces(d,[(0,4)],t=.1);d=load(s,d);P=module(s,'conversion_plan')
    p=P.analyse(d,(-1,-1),(6,2),P.Classification({WALL:'tabiques'}),tmin=.07,tmax=.15)
    P.commit(s.tool('LINEASAMURO').ctx,p)
    wall=next(e for e in s.export(tmp_path)['elements']if e['ifc_class']=='IfcWall')
    assert wall['enums']['PredefinedType']=='PARTITIONING'
    assert wall['params']['thickness']==pytest.approx(.1)


def test_explicit_cabinet_never_creates_a_through_opening(plugin):
    s=Session(plugin);d=document();faces(d,[(0,1),(2.2,4)])
    d.layers.new('ARQ-ARMARIOS')
    cabinet=d.modelspace().add_lwpolyline([(1,-.2),(2.2,-.2),(2.2,.7),(1,.7)],close=True,dxfattribs={'layer':'ARQ-ARMARIOS'})
    P=module(s,'conversion_plan');p=P.analyse(d,(-1,-1),(5,2),P.Classification({WALL:'muros','ARQ-ARMARIOS':'armarios'}))
    assert len(p.result[0])==1 and not p.result[1] and cabinet not in p.sources
    assert any('cortes pasantes evitados'in w for w in p.warnings)


def test_grid_dimension_size_is_editable_in_native_sheet(plugin):
    from PySide6.QtWidgets import QApplication
    app=QApplication.instance()or QApplication([])
    s=Session(plugin);G=module(s,'grids');F=module(s,'grid_tools')
    s.history.execute(G.create_grid((0,0),{'x':'3 4','y':'2 3','scale':50}))
    entity=G.axes(s.document.doc)[0][0];dlg,read=F.axis_form(None,entity)
    assert dlg._arq['sizes'][2].value()==pytest.approx(3.5)
    dlg._arq['sizes'][2].setValue(4);values,points=read()
    assert values['dim_text_height']==pytest.approx(.2)
    dlg.close()


def test_old_pillar_layer_native_migration_and_undo(plugin):
    s=Session(plugin);d=s.document.doc
    if 'ARQ-PILAres' not in d.layers:d.layers.new('ARQ-PILAres')
    old=d.layers.get('ARQ-PILAres').dxf.name
    if old!='ARQ-PILAres':
        d.layers.rename(old,'TEMP');d.layers.rename('TEMP','ARQ-PILAres')
    e=d.modelspace().add_circle((1,2),.2,dxfattribs={'layer':'ARQ-PILAres'})
    M=module(s,'migration');s.history.execute(M.CanonicalPillarLayer())
    assert d.layers.get('ARQ-PILARES').dxf.name=='ARQ-PILARES' and e.dxf.layer=='ARQ-PILARES'
    s.history.undo();assert d.layers.get('ARQ-PILAres').dxf.name=='ARQ-PILAres' and e.dxf.layer=='ARQ-PILAres'
    s.history.redo();assert e.dxf.layer=='ARQ-PILARES'


def test_hyperlink_layer_is_lazy_and_existing_entities_untouched(plugin):
    import importlib
    s=Session(plugin);A=importlib.import_module(plugin.tools['MURO'].__module__.rsplit('.',1)[0])
    ctx=s.tool('MURO').ctx;d=s.document.doc
    A._ensure_layers(ctx);assert 'ARQ-HIPERVINCULOS'not in d.layers
    A._set_layer(ctx,'ARQ-HIPERVINCULOS');assert 'ARQ-HIPERVINCULOS'in d.layers
    e=d.modelspace().add_point((1,2),dxfattribs={'layer':'ARQ-HIPERVINCULOS'})
    A._ensure_layers(ctx);assert e.is_alive and e.dxf.layer=='ARQ-HIPERVINCULOS'


@pytest.mark.parametrize('angle',[0,37,90,147])
def test_terminal_opening_needs_both_network_and_swing(plugin,angle):
    s=Session(plugin);E=module(s,'conversion_evidence');R=module(s,'conversion_openings')
    mat=Matrix44.z_rotate(math.radians(angle))
    def p(x,y):
        q=mat.transform((x,y,0));return(q.x,q.y)
    walls=[(p(0,0),p(3,0),.2),(p(4,-2),p(4,2),.2)]
    d=document();arc=d.modelspace().add_arc((3,.1),.9,0,90,dxfattribs={'layer':CARP});transform.inplace([arc],mat)
    reader=R.Reader([],[],[(arc,'puertas')]);new,ops,count=E.recover_terminal_doors(walls,[],reader)
    assert count==1 and len(ops)==1 and ops[0][3]=='door' and ops[0][2]==pytest.approx(.9)
    assert math.dist(new[0][1],p(4,0))<1e-7
    new,ops,count=E.recover_terminal_doors(walls,[],R.Reader([],[],[]));assert count==0 and new==walls
    new,ops,count=E.recover_terminal_doors(walls[:1],[],reader);assert count==0 and new==walls[:1]


def test_short_return_requires_two_distinct_host_walls(plugin):
    s=Session(plugin);E=module(s,'conversion_evidence')
    walls=[((0,-2),(0,2),.2),((.4,-2),(.4,2),.2)]
    faces=[(.1,-.1,.3,-.1),(.1,.1,.3,.1)]
    new,count=E.recover_short_links(walls,faces,.07,.3)
    assert count==1 and len(new)==3 and math.dist(new[-1][0],new[-1][1])==pytest.approx(.4)
    assert E.recover_short_links(walls[:1],faces,.07,.3)[1]==0
    assert E.recover_short_links([],faces,.07,.3)[1]==0


@pytest.mark.parametrize('scale',[50,100])
@pytest.mark.parametrize('angle',[0,37,90])
def test_grid_dimension_extensions_clear_bubbles_and_preserve_measures(plugin,scale,angle):
    s=Session(plugin);G=module(s,'grids');s.history.execute(G.create_grid((0,0),{'x':'3 4','y':'2 3','scale':scale,'angle':angle,'dim_text_mm':3.5}))
    d=s.document.doc;dims=list(d.modelspace().query('DIMENSION'));circles=list(d.modelspace().query('CIRCLE'))
    assert len(dims)==6
    from shapely.geometry import LineString,Point
    for dim in dims:
        override=dim.override();assert override.get('dimtxt')==pytest.approx(.0035*scale)
        assert override.get('dimexo')>=1+.004*scale
        assert any(dim.get_measurement()==pytest.approx(x)for x in (2,3,4,5,7))
        for entity in dim.virtual_entities():
            if entity.dxftype()!='LINE':continue
            segment=LineString([tuple(entity.dxf.start)[:2],tuple(entity.dxf.end)[:2]])
            assert all(segment.distance(Point(tuple(c.dxf.center)[:2]))>=c.dxf.radius-1e-7 for c in circles)
    s.history.undo();assert not list(d.modelspace())

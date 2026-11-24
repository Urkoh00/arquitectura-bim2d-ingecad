# SPDX-License-Identifier: GPL-3.0-or-later
import math
import pytest
from tests.test_ingecad_integration import plugin
from tests.test_wall_tools import Session
from tests.test_r12_conversion import module


def test_mixed_categories_have_separate_ranges_and_one_undo(plugin,tmp_path):
    s=Session(plugin);d=s.document.doc;P=module(s,'conversion_plan')
    for layer,y,t in [('ARQ-MUROS',0,.3),('ARQ-TABIQUES',3,.08)]:
        if layer not in d.layers:d.layers.new(layer)
        for off in (-t/2,t/2):d.modelspace().add_line((0,y+off),(4,y+off),dxfattribs={'layer':layer})
    roles={'ARQ-MUROS':'muros','ARQ-TABIQUES':'tabiques'}
    c=P.Classification(roles,thickness_ranges={'muros':(.2,.4),'tabiques':(.06,.12)})
    p=P.analyse(d,(-1,-1),(6,5),c)
    assert len(p.result[0])==2 and sorted(t for a,b,t in p.result[0])==pytest.approx([.08,.3])
    P.commit(s.tool('LINEASAMURO').ctx,p);out=s.export(tmp_path)
    assert len([e for e in out['elements']if e.get('enums',{}).get('PredefinedType')=='PARTITIONING'])==1
    s.history.undo();assert not s.walls()
    # Exclusion uses the declared category's range, not the other category.
    c.thickness_ranges['tabiques']=(.1,.15);p=P.analyse(d,(-1,-1),(6,5),c)
    assert len(p.result[0])==1 and p.wall_roles==['muros']


def test_invalid_ranges_do_not_modify_the_document(plugin):
    s=Session(plugin);P=module(s,'conversion_plan');d=s.document.doc;before=P.fingerprint(d)
    for bad in [(1,.1),(0,.1),(.1,float('nan'))]:
        with pytest.raises(ValueError):P.analyse(d,(0,0),(5,5),P.Classification(thickness_ranges={'tabiques':bad}))
    assert P.fingerprint(d)==before


def test_terminal_door_may_join_a_different_wall_category(plugin):
    s=Session(plugin);P=module(s,'conversion_plan');d=s.document.doc
    for layer in ('ARQ-MUROS','ARQ-TABIQUES','ARQ-PUERTAS'):
        if layer not in d.layers:d.layers.new(layer)
    m=d.modelspace()
    for y in (-.15,.15):m.add_line((0,y),(3,y),dxfattribs={'layer':'ARQ-MUROS'})
    for x in (3.9,4.1):m.add_line((x,-2),(x,2),dxfattribs={'layer':'ARQ-TABIQUES'})
    arc=m.add_arc((3,.15),.9,0,90,dxfattribs={'layer':'ARQ-PUERTAS'})
    c=P.Classification({'ARQ-MUROS':'muros','ARQ-TABIQUES':'tabiques','ARQ-PUERTAS':'puertas'},
        thickness_ranges={'muros':(.25,.4),'tabiques':(.15,.25)})
    p=P.analyse(d,(-1,-3),(6,3),c)
    assert len(p.result[0])==2 and len(p.result[1])==1 and p.result[1][0][3]=='door'
    assert arc in p.sources
    P.commit(s.tool('LINEASAMURO').ctx,p);s.history.undo();assert arc.dxf.layer=='ARQ-PUERTAS'


@pytest.mark.parametrize('angle',[0,37,90])
def test_stepped_facade_short_overlap_recovers_join_without_filling_void(plugin,angle):
    s=Session(plugin);J=module(s,'geom.junctions');C=module(s,'convert_tools');P=module(s,'conversion_plan')
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    from ezdxf import transform
    from ezdxf.math import Matrix44
    ws=[J.Wall('a',(-3,0),(.05,0),.4),J.Wall('b',(.05,.45),(3,.45),.4),J.Wall('c',(.05,0),(.05,.45),.4)]
    expected=J.solve(ws)
    shape=unary_union([Polygon(poly)for w in expected.walls.values()for poly in w['pieces']]);d=s.document.doc
    if 'ARQ-MUROS'not in d.layers:d.layers.new('ARQ-MUROS')
    for ring in [shape.exterior,*shape.interiors]:
        pts=list(ring.coords)
        for a,b in zip(pts,pts[1:]):d.modelspace().add_line(a,b,dxfattribs={'layer':'ARQ-MUROS'})
    transform.inplace(d.modelspace(),Matrix44.z_rotate(math.radians(angle)))
    p=P.analyse(d,(-10,-10),(10,10),P.Classification({'ARQ-MUROS':'muros'}))
    assert len(p.result[0])==3 and not p.result[1]
    specs=[J.Wall(str(i),a,b,t)for i,(a,b,t)in enumerate(p.result[0])];solved=J.solve(specs)
    actual=unary_union([Polygon(poly)for w in solved.walls.values()for poly in w['pieces']])
    from shapely.affinity import rotate
    assert actual.symmetric_difference(rotate(shape,angle,origin=(0,0))).area<1e-7


def test_range_and_cabinet_sheets_are_readable(plugin):
    from PySide6.QtWidgets import QApplication
    app=QApplication.instance()or QApplication([])
    s=Session(plugin);P=module(s,'conversion_plan');D=module(s,'conversion_dialog');C=module(s,'cabinets')
    dlg,read=D.classification_form(None,s.document.doc,P.Classification())
    dlg._arq['separate_ranges'].setChecked(True);c=read();assert c.thickness_ranges['particiones']==pytest.approx((.05,.15));dlg.close()
    dlg,read=C.form(None);dlg._arq['leaves'].setValue(4);assert read()['leaves']==4;dlg.close()


def test_native_cabinet_tool_places_one_undoable_niche(plugin):
    s=Session(plugin);A=module(s,'architectural_v10');T=module(s,'transactions')
    cmd=A.create_wall((0,0),(4,0),.5,3);T.apply_architectural_change(s.tool('MURO').ctx,cmd)
    t=s.tool('ARMARIOBIM');t.on_point((1,.25))
    records=[s.meta(e)for e in s.document.doc.modelspace()if(s.meta(e)or{}).get('kind')=='opening']
    assert len(records)==1 and records[0]['cabinet']
    s.history.undo();assert not any((s.meta(e)or{}).get('kind')=='opening'for e in s.document.doc.modelspace())

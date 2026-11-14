# SPDX-License-Identifier: GPL-3.0-or-later
import copy
import pytest
import ezdxf
from tests.test_ingecad_integration import plugin
from tests.test_wall_tools import Session


def module(s,name):
    import importlib
    return importlib.import_module(s.plugin.tools['MURO'].__module__.rsplit('.',1)[0]+'.'+name)


def fixture(s,kind='LINE'):
    doc=s.document.doc;doc.layers.new('Muros antiguos');doc.layers.new('Rejas');msp=doc.modelspace()
    if kind=='LINE':
        src=[msp.add_line((0,y),(4,y),dxfattribs={'layer':'Muros antiguos'}) for y in (0,.2)]
    elif kind=='HATCH':
        e=msp.add_hatch(dxfattribs={'layer':'Muros antiguos'});e.paths.add_polyline_path([(0,0),(4,0),(4,.2),(0,.2)],is_closed=True);src=[e]
    else:
        src=[msp.add_solid([(0,0),(4,0),(0,.2),(4,.2)],dxfattribs={'layer':'Muros antiguos'})]
    bar=msp.add_line((0,2),(3,2),dxfattribs={'layer':'Rejas'})
    return src,bar


@pytest.mark.parametrize('typ',['LINE','HATCH','SOLID'])
def test_preview_commit_one_undo(plugin,typ):
    s=Session(plugin);src,bar=fixture(s,typ);P=module(s,'conversion_plan');c=P.Classification({'Muros antiguos':'muros','Rejas':'rejas'})
    before=P.fingerprint(s.document.doc);plan=P.analyse(s.document.doc,(-1,-1),(5,3),c)
    assert P.fingerprint(s.document.doc)==before and not s.walls()
    assert len(plan.result[0])==1 and plan.warnings
    t=s.tool('LINEASAMURO');assert P.commit(t.ctx,plan);assert len(s.walls())==1
    assert all(e.dxf.layer=='ARQ-PLANO-ORIGEN' for e in src) and bar.dxf.layer=='Rejas'
    s.history.undo();assert not s.walls();assert all(e.dxf.layer=='Muros antiguos' for e in src)
    s.history.redo();assert len(s.walls())==1


def test_explicit_empty_does_not_fallback_to_all(plugin):
    s=Session(plugin);fixture(s);P=module(s,'conversion_plan');plan=P.analyse(s.document.doc,(-1,-1),(5,3),P.Classification())
    assert not plan.result[0]


def test_graphical_handles_override_layers_and_stale_plan(plugin):
    s=Session(plugin);src,bar=fixture(s);P=module(s,'conversion_plan');c=P.Classification()
    c.assign([e.dxf.handle for e in src],'muros');c.layers['Muros antiguos']='escaleras'
    plan=P.analyse(s.document.doc,(-1,-1),(5,3),c);assert len(plan.result[0])==1
    bar.dxf.end=(4,2,0)
    with pytest.raises(ValueError,match='cambió'):P.commit(s.tool('LINEASAMURO').ctx,plan)
    assert not s.walls()


def test_holes_in_hatch_are_not_filled(plugin):
    s=Session(plugin);src,_bar=fixture(s,'HATCH');src[0].paths.add_polyline_path([(1,.05),(2,.05),(2,.15),(1,.15)],is_closed=True)
    P=module(s,'conversion_plan');plan=P.analyse(s.document.doc,(-1,-1),(5,3),P.Classification({'Muros antiguos':'muros'}))
    assert not plan.result[0] and not plan.sources and plan.warnings


def test_mm_rejected(plugin):
    s=Session(plugin);fixture(s);s.document.doc.header['$INSUNITS']=4;P=module(s,'conversion_plan')
    with pytest.raises(ValueError,match='metros'):P.analyse(s.document.doc,(-1,-1),(5,3),P.Classification({'Muros antiguos':'muros'}))


def test_tool_preview_cancel_and_confirm(plugin):
    s=Session(plugin);src,_bar=fixture(s);P=module(s,'conversion_plan');t=s.tool('LINEASAMURO');t.classification=P.Classification({'Muros antiguos':'muros'})
    t.on_point((-1,-1));t.on_point((5,3));assert not s.walls() and t.preview_segments(None)
    assert t.on_option('Cancelar');assert not s.walls()
    t.on_point((-1,-1));t.on_point((5,3));t.on_enter();assert len(s.walls())==1
    s.history.undo();assert not s.walls()


def test_block_context_not_modified(plugin):
    s=Session(plugin);d=s.document.doc;d.layers.new('Muros');d.layers.new('Puertas');b=d.blocks.new('Puerta antigua')
    b.add_arc((1,0),.9,0,90);insert=d.modelspace().add_blockref('Puerta antigua',(0,0),dxfattribs={'layer':'Puertas'})
    for y in (0,.2):
        for x0,x1 in ((0,1),(1.9,4)):d.modelspace().add_line((x0,y),(x1,y),dxfattribs={'layer':'Muros'})
    P=module(s,'conversion_plan');plan=P.analyse(d,(-1,-1),(5,3),P.Classification({'Muros':'muros','Puertas':'puertas'}))
    assert plan.result[0] and plan.result[1] and insert not in plan.sources
    assert any(o[3]=='door' for o in plan.result[1])


def test_party_wall_type_preserved(plugin):
    s=Session(plugin);fixture(s);P=module(s,'conversion_plan');plan=P.analyse(s.document.doc,(-1,-1),(5,3),P.Classification({'Muros antiguos':'medianeras'}))
    P.commit(s.tool('LINEASAMURO').ctx,plan);assert {s.meta(w)['type_name'] for w in s.walls().values()}=={'Medianeras'}


def test_mid_conversion_failure_is_atomic(plugin):
    s=Session(plugin);d=s.document.doc;d.layers.new('Muros');d.layers.new('Ventanas')
    for y in (0,.2):
        for a,b in ((0,1),(2,4)):d.modelspace().add_line((a,y),(b,y),dxfattribs={'layer':'Muros'})
    d.modelspace().add_line((1,.1),(2,.1),dxfattribs={'layer':'Ventanas'})
    P=module(s,'conversion_plan');plan=P.analyse(d,(-1,-1),(5,2),P.Classification({'Muros':'muros','Ventanas':'ventanas'}),height=.5)
    assert any(op[3]=='window' for op in plan.result[1])
    with pytest.raises(ValueError,match='Altura insuficiente'):P.commit(s.tool('LINEASAMURO').ctx,plan)
    assert not s.walls() and all(e.dxf.layer in ('Muros','Ventanas') for e in d.modelspace())


def test_native_pick_service_assigns_graphical_object(plugin):
    s=Session(plugin);src,_bar=fixture(s);P=module(s,'conversion_plan');t=s.tool('LINEASAMURO')
    t.classification=P.Classification();t.pick_role='muros';t.entity_picker=True
    t.on_point((2,0));assert t.classification.handles[src[0].dxf.handle]=='muros'
    assert not s.walls()


def test_elevated_hatch_is_not_projected_silently(plugin):
    s=Session(plugin);src,_bar=fixture(s,'HATCH');src[0].dxf.elevation=(0,0,3)
    P=module(s,'conversion_plan');plan=P.analyse(s.document.doc,(-1,-1),(5,3),P.Classification({'Muros antiguos':'muros'}))
    assert not plan.result[0] and not plan.sources and any('elevación' in w for w in plan.warnings)

# SPDX-License-Identifier: GPL-3.0-or-later
import math
import pytest
from tests.test_ingecad_integration import plugin
from tests.test_wall_tools import Session
from tests.test_r12_conversion import module


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def circular_case(s,start=20,glyph='arc',block=False):
    d=s.document.doc
    for layer in ('Muro original','Carpinterias','Plano'):
        if layer not in d.layers:d.layers.new(layer)
    m=d.blocks.new('Ensayo circular') if block else d.modelspace()
    for r in (5.85,6.15):
        for lo,hi in ((start,start+20),(start+30,start+60)):
            m.add_arc((0,0),r,lo%360,hi%360,dxfattribs={'layer':'Muro original'})
    if glyph=='arc':
        m.add_arc((0,0),6.,(start+20)%360,(start+30)%360,dxfattribs={'layer':'Carpinterias'})
    elif glyph=='swing':
        a=math.radians(start+20);b=math.radians(start+30)
        p=(6*math.cos(a),6*math.sin(a));q=(6*math.cos(b),6*math.sin(b))
        direction=math.degrees(math.atan2(q[1]-p[1],q[0]-p[0]))
        m.add_arc(p,math.dist(p,q),direction,direction+90,dxfattribs={'layer':'Carpinterias'})
    if block:d.modelspace().add_blockref('Ensayo circular',(0,0),dxfattribs={'layer':'Plano'})
    P=module(s,'conversion_plan')
    c=P.Classification({'Muro original':'muros','Carpinterias':'carpinteria'})
    return P,c


@pytest.mark.parametrize('start',[20,330])
@pytest.mark.parametrize('block',[False,True])
def test_curved_gap_uses_arc_distance_and_one_undo(plugin,start,block):
    s=Session(plugin);P,c=circular_case(s,start,block=block)
    before=P.fingerprint(s.document.doc);p=P.analyse(s.document.doc,(-8,-8),(8,8),c)
    assert P.fingerprint(s.document.doc)==before
    assert len(p.result[3])==1 and len(p.curved_openings)==1
    k,pos,w,kind,_,_=p.curved_openings[0]
    assert (pos,w)==pytest.approx((6*math.radians(25),6*math.radians(10)))
    assert kind=='window' and len(p.segments)>2
    t=s.tool('LINEASAMURO');P.commit(t.ctx,p)
    ops=[s.meta(e) for e in s.document.doc.modelspace() if (s.meta(e)or{}).get('kind')=='opening']
    assert len(s.walls())==1 and len(ops)==1
    assert ops[0]['offset']==pytest.approx(6*math.radians(20))
    identity=ops[0]['id'];s.history.undo();assert not s.walls()
    s.history.redo();assert len(s.walls())==1
    assert any((s.meta(e)or{}).get('id')==identity for e in s.document.doc.modelspace())
    if block:assert next(iter(s.document.doc.modelspace().query('INSERT'))).dxf.layer=='Plano'


def test_generic_carpentry_does_not_force_window_on_swing(plugin):
    s=Session(plugin);P,c=circular_case(s,glyph='swing')
    p=P.analyse(s.document.doc,(-8,-8),(8,8),c)
    assert len(p.curved_openings)==1 and p.curved_openings[0][3]=='door'


def test_no_glyph_does_not_join_circular_fragments(plugin):
    s=Session(plugin);P,c=circular_case(s,glyph=None)
    p=P.analyse(s.document.doc,(-8,-8),(8,8),c)
    assert len(p.result[3])==2 and not p.curved_openings
    assert any('no se une' in w for w in p.warnings)


def test_conflicting_curved_labels_do_not_join(plugin):
    s=Session(plugin);P,c=circular_case(s)
    d=s.document.doc;d.layers.new('Puertas');d.layers.new('Ventanas')
    for layer in ('Puertas','Ventanas'):
        d.modelspace().add_arc((0,0),6.,40,50,dxfattribs={'layer':layer})
    c.layers.update(Puertas='puertas',Ventanas='ventanas')
    p=P.analyse(d,(-8,-8),(8,8),c)
    assert not p.curved_openings and any('contradictorias' in w for w in p.warnings)


def test_block_definition_edit_invalidates_preview(plugin):
    s=Session(plugin);P,c=circular_case(s,block=True)
    p=P.analyse(s.document.doc,(-8,-8),(8,8),c)
    first=next(iter(s.document.doc.blocks.get('Ensayo circular')));first.dxf.radius+=.01
    with pytest.raises(ValueError,match='cambió'):P.commit(s.tool('LINEASAMURO').ctx,p)
    assert not s.walls()


def test_unit_change_invalidates_preview(plugin):
    s=Session(plugin);P,c=circular_case(s);p=P.analyse(s.document.doc,(-8,-8),(8,8),c)
    s.document.doc.header['$INSUNITS']=4
    with pytest.raises(ValueError,match='cambió'):P.commit(s.tool('LINEASAMURO').ctx,p)
    assert not s.walls()


def test_edge_hatch_rectangle_converts_without_flattening(plugin):
    s=Session(plugin);d=s.document.doc;d.layers.new('Muro');h=d.modelspace().add_hatch(dxfattribs={'layer':'Muro'})
    path=h.paths.add_edge_path();v=[(0,0),(4,0),(4,.2),(0,.2)]
    for a,b in zip(v,v[1:]+v[:1]):path.add_line(a,b)
    P=module(s,'conversion_plan');p=P.analyse(d,(-1,-1),(5,2),P.Classification({'Muro':'muros'}))
    assert len(p.result[0])==1
    P.commit(s.tool('LINEASAMURO').ctx,p);assert len(s.walls())==1
    s.history.undo();assert h.dxf.layer=='Muro' and not s.walls()


def test_edge_hatch_open_contour_rejected(plugin):
    s=Session(plugin);d=s.document.doc;d.layers.new('Muro');h=d.modelspace().add_hatch(dxfattribs={'layer':'Muro'})
    path=h.paths.add_edge_path();path.add_line((0,0),(4,0));path.add_line((4,0),(4,.2))
    P=module(s,'conversion_plan');p=P.analyse(d,(-1,-1),(5,2),P.Classification({'Muro':'muros'}))
    assert not p.result[0] and not p.sources and any('abierto' in w for w in p.warnings)


def test_unpaired_arc_stays_visible_even_when_other_walls_convert(plugin):
    s=Session(plugin);P,c=circular_case(s)
    orphan=s.document.doc.modelspace().add_arc((0,0),4.,20,80,dxfattribs={'layer':'Muro original'})
    p=P.analyse(s.document.doc,(-8,-8),(8,8),c)
    assert orphan not in p.sources
    P.commit(s.tool('LINEASAMURO').ctx,p)
    assert orphan.dxf.layer=='Muro original'


def test_straight_opening_identity_survives_redo(plugin):
    from tests.test_lineas_carpinteria_una_capa import capas,planta
    s=Session(plugin);d=s.document.doc;capas(d);planta(d.modelspace())
    P=module(s,'conversion_plan');p=P.analyse(d,(-1,-1),(7,3),P.Classification({'Gpared':'muros','Fcarp':'carpinteria'}))
    P.commit(s.tool('LINEASAMURO').ctx,p)
    def ids():return {s.meta(e)['id'] for e in d.modelspace() if (s.meta(e)or{}).get('kind')=='opening'}
    before=ids();assert len(before)==2
    for _ in range(2):
        s.history.undo();assert not ids();s.history.redo();assert ids()==before


def test_curved_conversion_exports_existing_radial_hole(plugin,tmp_path):
    s=Session(plugin);P,c=circular_case(s);p=P.analyse(s.document.doc,(-8,-8),(8,8),c)
    P.commit(s.tool('LINEASAMURO').ctx,p);data=s.export(tmp_path)
    wall=next(e for e in data['elements'] if e['ifc_class']=='IfcWall')
    window=next(e for e in data['elements'] if e['ifc_class']=='IfcWindow')
    assert window['host']==wall['id'] and len(wall['openings'])==1
    assert window['fills']==wall['openings'][0]['guid']
    import importlib.util
    from pathlib import Path
    spec=importlib.util.spec_from_file_location('r14_contract',Path(__file__).parents[1]/'ingetrazo_ext/arquitectura_bim.py')
    bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
    bridge.validate_contract(data)


def test_impossible_planar_frame_keeps_fragments(plugin):
    s=Session(plugin);d=s.document.doc;d.layers.new('Muro');d.layers.new('Carp')
    for r in (.95,1.05):
        for lo,hi in ((0,20),(90,110)):
            d.modelspace().add_arc((0,0),r,lo,hi,dxfattribs={'layer':'Muro'})
    d.modelspace().add_arc((0,0),1.,20,90,dxfattribs={'layer':'Carp'})
    P=module(s,'conversion_plan');p=P.analyse(d,(-2,-2),(2,2),P.Classification({'Muro':'muros','Carp':'carpinteria'}))
    assert len(p.result[3])==2 and not p.curved_openings
    assert any('no cabe' in w for w in p.warnings)


def test_confirmed_empty_layers_are_not_guessed_again(plugin,qapp):
    s=Session(plugin);P,c=circular_case(s);D=module(s,'conversion_dialog')
    dlg,read=D.classification_form(None,s.document.doc,P.Classification())
    table=dlg._arq['table']
    for row in range(table.rowCount()):table.cellWidget(row,1).setCurrentIndex(0)
    empty=read();assert empty.layers=={} and empty.layers_confirmed
    dlg.deleteLater()
    again,read_again=D.classification_form(None,s.document.doc,empty)
    assert read_again().layers=={}
    again.deleteLater()


@pytest.mark.parametrize('parallel',[-.001,float('nan'),float('inf'),.6])
def test_parallel_tolerance_validated_before_conversion(plugin,parallel):
    s=Session(plugin);P,c=circular_case(s)
    with pytest.raises(ValueError,match='Dimensiones'):
        P.analyse(s.document.doc,(-8,-8),(8,8),c,parallel=parallel)
    assert not s.walls()


def test_misaligned_circular_jambs_remain_manual(plugin):
    s=Session(plugin);P,c=circular_case(s)
    arc=next(e for e in s.document.doc.modelspace().query('ARC')
             if e.dxf.layer=='Muro original' and e.dxf.radius>6 and e.dxf.end_angle==40)
    arc.dxf.end_angle=42
    p=P.analyse(s.document.doc,(-8,-8),(8,8),c)
    assert not p.curved_openings and any('desalineadas' in w for w in p.warnings)

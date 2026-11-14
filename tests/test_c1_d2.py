# SPDX-License-Identifier: GPL-3.0-or-later
import math,importlib.util
from pathlib import Path
import pytest
from tests.test_ingecad_integration import plugin
from tests.test_wall_tools import Session
from tests.test_r12_conversion import module

def bridge():
    spec=importlib.util.spec_from_file_location('c1_contract',Path(__file__).parents[1]/'ingetrazo_ext/arquitectura_bim.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

@pytest.mark.parametrize('radius',[1.5,8.])
@pytest.mark.parametrize('kind,operation',[('window','FIXED'),('window','SLIDING'),('door','SLIDING')])
@pytest.mark.parametrize('face',['interior','centrada','exterior','distancia'])
def test_curved_carpentry_plan_and_3d_share_vertices(plugin,tmp_path,radius,kind,operation,face):
    s=Session(plugin);A=module(s,'architectural_v10');T=module(s,'transactions');O=module(s,'openings')
    angle=1.8;a=(radius,0);b=(radius*math.cos(angle),radius*math.sin(angle))
    w=A.create_wall(a,b,.3,3.,0.,'eje',bulge=math.tan(angle/4))
    ctx=s.tool('MURO').ctx;T.apply_architectural_change(ctx,w)
    op=A.create_opening(w.entity,.35,.8,.5 if kind=='window' else 0.,1.2 if kind=='window' else 2.1,
                        kind=kind,curve_mode='curva',operation=operation,facet_sagitta=.005,
                        face=face,frame_depth=.05,setback=.03,setback_from='exterior')
    T.apply_architectural_change(ctx,op,kind='opening')
    data=s.export(tmp_path);bridge().validate_contract(data)
    filling=next(e for e in data['elements'] if e['ifc_class']==O.IFC[kind]);assert filling['params']['curve_mode']=='curva'
    spec=module(s,'geom.junctions').walls_from_records([(s.meta(w.entity)['id'],s.meta(w.entity))])[0]
    rec=s.meta(op.entity);parts=O.carpentry_parts(spec,rec,0.);symbol=O.plan_symbol(spec,rec)
    points={tuple(round(c,7) for c in p[:2]) for part in parts for face in part['faces'] for loop in (face[0],*face[1]) for p in loop}
    assert symbol and all(tuple(round(c,7) for c in p) in points for typ,poly,closed in symbol for p in poly)
    assert all(p['volume']>0 for p in parts)
    for piece in parts:
        rmax=max(math.dist(p[:2],spec.c) for outer,holes in piece['faces'] for loop in (outer,*holes) for p in loop)
        assert all(rmax*(1-math.cos((b-a)/spec.r/2))<=.005+1e-9 for a,b in zip(piece['stations'],piece['stations'][1:]))
    identity=rec['id'];s.history.undo();s.history.redo();assert s.meta(op.entity)['id']==identity

def test_curved_hinged_rejected_before_mutation(plugin):
    O=module(Session(plugin),'openings')
    with pytest.raises(ValueError,match='abatibles'):O.normalise({'type':'door','width':1.,'height':2.,'sill':0.,'curve_mode':'curva'})

def test_grid_naming_and_exact_intervals(plugin):
    G=module(Session(plugin),'grids')
    assert [G.letter(i) for i in (8,9,13,14,24,25)]==['H','J','N','P','Z','AA']
    assert G.distances('3x5,40 4,20')==pytest.approx([0,5.4,10.8,16.2,20.4])
    for text in ('0x5','2x0','nan','101x1','1x-2'):
        with pytest.raises(ValueError):G.distances(text)

def test_grid_bulk_columns_move_undo_and_contract(plugin,tmp_path):
    s=Session(plugin);G=module(s,'grids');T=module(s,'transactions');ctx=s.tool('MURO').ctx
    T.apply_architectural_change(ctx,G.create_grid((0.,0.),{'x':'2x4','y':'1x3','prefix':'R','dimensions':True}),kind='column')
    assert len(G.axes(s.document.doc))==5 and len(G.intersections(s.document.doc))==6
    e,m=G.axes(s.document.doc)[0]
    length=sum(abs(float(t.value)) for t in s.document.doc.linetypes.get('DASHDOT').pattern_tags.tags if t.code==49)
    assert length*e.dxf.ltscale*float(s.document.doc.header.get('$LTSCALE',1))==pytest.approx(.01*m['scale'])
    assert len(list(s.document.doc.modelspace().query('DIMENSION')))==5
    assert G.place_columns(ctx,{'shape':'rect','width':.3,'depth':.3,'height':3.,'base':0.,'rotation':0.})
    cols=[e for e in s.document.doc.modelspace() if (s.meta(e)or{}).get('kind')=='column'];assert len(cols)==6
    s.history.undo();assert not [e for e in s.document.doc.modelspace() if (s.meta(e)or{}).get('kind')=='column']
    s.history.redo();cols=[e for e in s.document.doc.modelspace() if (s.meta(e)or{}).get('kind')=='column']
    entity,m=next((e,m) for e,m in G.axes(s.document.doc) if m['family']=='U' and m['index']==1)
    before=G.snapshot(s.document.doc);a,b=G.endpoints(entity)
    linked=[e for e in cols if s.meta(e)['grid_link']['u']==m['id']];identities={s.meta(e)['id'] for e in linked}
    old=[s.meta(e)['center'] for e in linked]
    change=T.SafeArchitecturalCommand('test move',[G.SetAxis(entity,[(a[0]+1,a[1]),(b[0]+1,b[1])]),G.RegenerateGrid(before)])
    T.apply_architectural_change(ctx,change,kind='column')
    assert [s.meta(e)['center'][0] for e in linked]==pytest.approx([p[0]+1 for p in old])
    assert {s.meta(e)['id'] for e in linked}==identities
    s.history.undo();assert [s.meta(e)['center'][0] for e in linked]==pytest.approx([p[0] for p in old])
    s.history.redo();data=s.export(tmp_path);assert len(data['reference_grids']['grids'][0]['axes'])==5
    assert data['version']==2
    assert len(data['reference_grids']['column_links'])==6
    assert all(e['name'].endswith('['+e['params']['grid_link']['mark']+']') and e['params']['source_name']
               for e in data['elements'] if e['ifc_class']=='IfcColumn')
    assert bridge().definition(data)['reference_grids']==data['reference_grids']
    bridge().validate_contract(data)

def test_grid_native_reactor_moves_linked_columns_only(plugin):
    from core import commands,actions
    if not hasattr(commands,'register_reactor'):pytest.skip('IngeCAD 0.7: usar ACTUALIZAEJES')
    s=Session(plugin);G=module(s,'grids');T=module(s,'transactions');ctx=s.tool('MURO').ctx
    T.apply_architectural_change(ctx,G.create_grid((0.,0.),{'x':'1x4','y':'1x3','dimensions':False}),kind='column')
    G.place_columns(ctx,{'shape':'rect','width':.3,'depth':.3,'height':3.,'base':0.})
    C=module(s,'columns');free=C.column_command((20,20),{'shape':'rect','width':.3,'depth':.3,'height':3.,'base':0.})
    T.apply_architectural_change(ctx,free,kind='column')
    entity,rec=next((e,m) for e,m in G.axes(s.document.doc) if m['family']=='U' and m['index']==0)
    linked=[e for e in s.document.doc.modelspace() if (s.meta(e)or{}).get('grid_link',{}).get('u')==rec['id']]
    commands.register_reactor(G.GridReactor(),'grid-test')
    try:
        s.history.execute(actions.move_entities([entity],1.,0.))
        assert all(s.meta(e)['center'][0]==pytest.approx(1.) for e in linked)
        assert s.meta(free.entity)['center']==[20.,20.]
        s.history.undo();assert all(s.meta(e)['center'][0]==pytest.approx(0.) for e in linked)
        s.history.redo();assert all(s.meta(e)['center'][0]==pytest.approx(1.) for e in linked)
    finally:commands.unregister_reactors('grid-test')

def test_grid_renumber_preserves_ids_and_updates_marks(plugin,tmp_path):
    s=Session(plugin);G=module(s,'grids');T=module(s,'transactions');ctx=s.tool('MURO').ctx
    T.apply_architectural_change(ctx,G.create_grid((0.,0.),{'x':'1x4','y':'1x3','prefix':'P','suffix':'s'}),kind='column')
    G.place_columns(ctx,{'shape':'rect','width':.3,'depth':.3,'height':3.,'base':0.})
    e,m=next((e,m) for e,m in G.axes(s.document.doc) if m['family']=='U' and m['index']==0)
    ids=set(G.snapshot(s.document.doc));tool=s.tool('EDITAREJE');tool.entity=e
    assert tool.on_option('Renumerar 3')
    assert set(G.snapshot(s.document.doc))==ids
    assert {n['label'] for a,n in G.axes(s.document.doc) if n['family']=='U'}=={'P3s','P4s'}
    links=G.contract(s.document.doc)['column_links'];assert all(l['mark'].endswith(('-P3s','-P4s')) for l in links)
    s.history.undo();assert G.metadata(e)['label']=='P1s'
    s.history.redo();bridge().validate_contract(s.export(tmp_path))

def test_grid_auto_binding_at_manual_pillar_placement(plugin):
    s=Session(plugin);G=module(s,'grids');T=module(s,'transactions');ctx=s.tool('MURO').ctx
    T.apply_architectural_change(ctx,G.create_grid((0.,0.),{'x':'1x4','y':'1x3'}),kind='column')
    t=s.tool('PILAR');t.on_point((4,3))
    cols=[s.meta(e) for e in s.document.doc.modelspace() if (s.meta(e)or{}).get('kind')=='column']
    assert len(cols)==1 and cols[0]['grid_link']['mark']=='B-2'

def test_grid_grip_changes_one_axis_and_retains_column_ids(plugin):
    s=Session(plugin);G=module(s,'grids');T=module(s,'transactions');ctx=s.tool('MURO').ctx
    T.apply_architectural_change(ctx,G.create_grid((0.,0.),{'x':'1x4','y':'1x3'}),kind='column')
    e,m=G.axes(s.document.doc)[0];old=G.endpoints(e);grip=G.GridGrips()
    assert len(grip.grips(e))==2
    command=grip.drop(ctx,e,1,'endpoint',(old[1][0]+.2,old[1][1]))
    s.history.execute(command);assert G.endpoints(e)[1][0]==pytest.approx(old[1][0]+.2)
    s.history.undo();assert G.endpoints(e)==old

@pytest.mark.parametrize('damage',['duplicate','missing','offset'])
def test_reference_contract_rejects_damaged_links(plugin,tmp_path,damage):
    import copy
    s=Session(plugin);G=module(s,'grids');T=module(s,'transactions');ctx=s.tool('MURO').ctx
    T.apply_architectural_change(ctx,G.create_grid((0.,0.),{'x':'1x4','y':'1x3'}),kind='column')
    G.place_columns(ctx,{'shape':'rect','width':.3,'depth':.3,'height':3.,'base':0.})
    d=s.export(tmp_path)
    if damage=='duplicate':d['reference_grids']['grids'][0]['axes'].append(copy.deepcopy(d['reference_grids']['grids'][0]['axes'][0]))
    elif damage=='missing':d['reference_grids']['column_links'][0]['u']='absent'
    else:d['reference_grids']['column_links'][0]['offset']=['x',0]
    with pytest.raises(ValueError):bridge().validate_contract(d)

def test_curve_width_reference_and_legacy_migration(plugin):
    s=Session(plugin);O=module(s,'openings');J=module(s,'geom.junctions');M=module(s,'migration')
    spec=J.Wall('s',(4,0),(0,4),.4,'eje',bulge=math.tan(math.pi/8))
    assert O.span_of(spec,1.,{'curve_mode':'curva','width_reference':'interior'},1)==pytest.approx(4/3.8)
    old={'type':'window','offset':.3,'width':1.,'height':1.2,'sill':.9,'face':'exterior'}
    assert M.migrate_opening_position(old)['curve_mode']=='plana'
    assert O.plan_symbol(spec,O.normalise(old))==O.plan_symbol(spec,M.migrate_opening_position(old))

def test_curvamuro_with_curved_carpentry_preserves_identity(plugin):
    s=Session(plugin);A=module(s,'architectural_v10');T=module(s,'transactions');ctx=s.tool('MURO').ctx
    w=A.create_wall((0,0),(5,0),.3,3.,0.,'eje');T.apply_architectural_change(ctx,w)
    opening=A.create_opening(w.entity,1.,1.,.9,1.2,kind='window',operation='FIXED',curve_mode='curva')
    T.apply_architectural_change(ctx,opening,kind='opening');rec=s.meta(opening.entity)
    tool=s.tool('CURVAMURO');tool.wall=w.entity;tool._apply(.3)
    new=s.meta(opening.entity);assert new['id']==rec['id'] and new['width']==pytest.approx(1.)
    s.history.undo();assert s.meta(opening.entity)['offset']==pytest.approx(1.)
    s.history.redo();assert s.meta(opening.entity)['id']==rec['id']

def test_curved_opening_volume_conservation(plugin,tmp_path):
    s=Session(plugin);A=module(s,'architectural_v10');T=module(s,'transactions');O=module(s,'openings');P=module(s,'geom.polygon')
    ctx=s.tool('MURO').ctx;w=A.create_wall((4,0),(0,4),.3,3.,0.,'eje',bulge=math.tan(math.pi/8));T.apply_architectural_change(ctx,w)
    before=next(e for e in s.export(tmp_path)['elements'] if e['ifc_class']=='IfcWall')
    op=A.create_opening(w.entity,.6,1.,.9,1.2,kind='window',operation='FIXED',curve_mode='curva');T.apply_architectural_change(ctx,op,kind='opening')
    after=next(e for e in s.export(tmp_path)['elements'] if e['ifc_class']=='IfcWall')
    spec=module(s,'geom.junctions').walls_from_records([(s.meta(w.entity)['id'],s.meta(w.entity))])[0]
    void=abs(P.area(O.cut_polygon(spec,s.meta(op.entity),0.)))*1.2
    assert before['volume']-after['volume']==pytest.approx(void,abs=.002)

def test_curved_width_beyond_diameter_uses_arc_not_chord(plugin):
    s=Session(plugin);J=module(s,'geom.junctions');O=module(s,'openings')
    spec=J.Wall('s',(1,0),(math.cos(2.9),math.sin(2.9)),.2,'eje',bulge=math.tan(2.9/4))
    rec=O.normalise({'type':'window','offset':.3,'width':2.3,'height':1.2,'sill':.8,'operation':'FIXED','curve_mode':'curva'})
    assert O.span_of(spec,2.3,rec)==pytest.approx(2.3)
    assert O.carpentry_parts(spec,rec,0.) and O.plan_symbol(spec,rec)
    with pytest.raises(ValueError,match='diámetro'):O.span_of(spec,2.3)

def test_curve_properties_reference_does_not_change_nominal_width(plugin):
    s=Session(plugin);A=module(s,'architectural_v10');T=module(s,'transactions');O=module(s,'openings');ctx=s.tool('MURO').ctx
    w=A.create_wall((4,0),(0,4),.3,3,0,'eje',bulge=math.tan(math.pi/8));T.apply_architectural_change(ctx,w)
    op=A.create_opening(w.entity,.5,1.,.9,1.2,kind='window',operation='FIXED',curve_mode='curva');T.apply_architectural_change(ctx,op,kind='opening')
    spec=module(s,'geom.junctions').walls_from_records([(s.meta(w.entity)['id'],s.meta(w.entity))])[0]
    rec=s.meta(op.entity);values={**rec,'width_reference':'interior'}
    values['width']=O.measure_of(spec,1.,values,rec['side'])
    change=module(s,'arq_properties').opening_change(op.entity,values)
    T.apply_architectural_change(ctx,change,kind='opening');assert s.meta(op.entity)['width']==pytest.approx(1.)

def test_grid_link_offset_is_measured_in_rotated_grid_frame(plugin):
    s=Session(plugin);G=module(s,'grids');T=module(s,'transactions');ctx=s.tool('MURO').ctx
    T.apply_architectural_change(ctx,G.create_grid((0,0),{'x':'1x4','y':'1x3','angle':90}),kind='column')
    link=G.binding(s.document.doc,(.01,.015),.03)
    assert link['offset']==pytest.approx([.015,-.01])

def test_c1_d2_forms_and_preview_widgets(plugin):
    from PySide6.QtWidgets import QApplication
    q=QApplication.instance() or QApplication([]);s=Session(plugin);D=module(s,'bim_dialogs');F=module(s,'grid_tools')
    dlg,read=D.carpentry_form(None,{'type':'window','width':1.,'height':1.2,'sill':.8,'operation':'FIXED','curve_mode':'curva'})
    assert read()['curve_mode']=='curva';dlg.show();q.processEvents();assert not dlg._arq['preview'].error;assert not dlg.grab().isNull();dlg.close()
    gd,gr=F.grid_form(None,{'x':'2x4','y':'2x3'});assert gr()['x']=='2x4'
    gd.show();q.processEvents();assert not gd.grab().isNull();gd.close()

def test_carpentry_tool_places_curved_window_by_face_arc(plugin):
    s=Session(plugin);A=module(s,'architectural_v10');T=module(s,'transactions');ctx=s.tool('MURO').ctx
    w=A.create_wall((4,0),(0,4),.3,3,0,'eje',bulge=math.tan(math.pi/8));T.apply_architectural_change(ctx,w)
    spec=module(s,'geom.junctions').walls_from_records([(s.meta(w.entity)['id'],s.meta(w.entity))])[0]
    c=s.tool('CARPINTERIA');c.apply_sheet({'type':'window','operation':'FIXED','curve_mode':'curva',
       'width_reference':'interior','width':1.,'height':1.2,'sill':.8})
    c.on_point(spec.point(.5,.15));c.on_point(spec.point(1.6,.4))
    records=[s.meta(e) for e in s.document.doc.modelspace() if (s.meta(e)or{}).get('kind')=='opening']
    assert len(records)==1 and records[0]['curve_mode']=='curva'
    assert records[0]['width']==pytest.approx(4/3.85)

def test_contract_legacy_reader_version_is_preserved_without_new_features(plugin,tmp_path):
    s=Session(plugin);data=s.export(tmp_path);assert data['version']==1
    bridge().validate_contract(data)
    data['version']=3
    with pytest.raises(ValueError,match='versión'):bridge().validate_contract(data)

@pytest.mark.parametrize('native',['own','both'])
def test_grid_with_all_reactors_never_moves_pillars_twice(plugin,native):
    from core import commands,actions
    if not hasattr(commands,'register_reactor'):pytest.skip('IngeCAD 0.7: actualización explícita')
    s=Session(plugin);G=module(s,'grids');T=module(s,'transactions');ctx=s.tool('MURO').ctx
    T.apply_architectural_change(ctx,G.create_grid((0,0),{'x':'1x4','y':'1x3','dimensions':False}),kind='column')
    G.place_columns(ctx,{'shape':'rect','width':.3,'depth':.3,'height':3.,'base':0.})
    e,m=next((e,m) for e,m in G.axes(s.document.doc) if m['family']=='U' and m['index']==0)
    linked=[e for e in s.document.doc.modelspace() if (s.meta(e)or{}).get('grid_link',{}).get('u')==m['id']]
    for reactor in plugin.reactors:commands.register_reactor(reactor,'grid-both-test')
    try:
        if native=='own':
            tool=s.tool('EDITAREJE');tool.entity=e;a,b=G.endpoints(e)
            tool.on_point(((a[0]+b[0])/2+1,(a[1]+b[1])/2))
        else:s.history.execute(actions.move_entities([e,*linked],1.,0.))
        assert all(s.meta(c)['center'][0]==pytest.approx(1.) for c in linked)
        s.history.undo();assert all(s.meta(c)['center'][0]==pytest.approx(0.) for c in linked)
        s.history.redo();assert all(s.meta(c)['center'][0]==pytest.approx(1.) for c in linked)
    finally:commands.unregister_reactors('grid-both-test')

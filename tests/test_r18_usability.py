# SPDX-License-Identifier: GPL-3.0-or-later
import math
from types import SimpleNamespace
import pytest
from tests.test_ingecad_integration import plugin
from tests.test_wall_tools import Session
from tests.test_r12_conversion import module

@pytest.fixture
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def source(s):
    d=s.document.doc
    for n in ('Muros ensayo','Sin clasificar','Oculta'):d.layers.new(n)
    d.layers.get('Oculta').off();m=d.modelspace()
    inside=m.add_line((1,1),(2,1),dxfattribs={'layer':'Muros ensayo'})
    crossed=m.add_line((-2,2),(4,2),dxfattribs={'layer':'Muros ensayo'})
    other=m.add_line((1,1.5),(2,1.5),dxfattribs={'layer':'Sin clasificar'})
    hidden=m.add_line((1,2.5),(2,2.5),dxfattribs={'layer':'Oculta'})
    t=s.tool('LINEASAMURO');P=module(s,'conversion_plan');t.classification=P.Classification({'Muros ensayo':'muros','Oculta':'muros'})
    return t,inside,crossed,other,hidden


def test_zone_preview_each_phase_and_native_highlight(plugin):
    s=Session(plugin);t,inside,crossed,other,hidden=source(s);P=module(s,'conversion_plan')
    before=P.fingerprint(s.document.doc);assert not t.preview_segments((3,3)) and not t.overlay((3,3))
    t.on_point((0,0));assert t.preview_segments((3,3))[:4]==[((0.,0.),(3.,0.)),((3.,0.),(3.,3.)),((3.,3.),(0.,3.)),((0.,3.),(0.,0.))]
    assert t._candidates((0,0),(3,3))==[inside.dxf.handle]
    assert t.overlay((3,3))['chosen']==[((1.,1.),(2.,1.))]
    assert set(t._candidates((3,0),(0,3)))=={inside.dxf.handle,crossed.dxf.handle}
    t.on_option('Altura');assert not t.preview_segments((3,3));t.on_option('3');assert t.preview_segments((3,3))
    assert P.fingerprint(s.document.doc)==before
    t.on_cancel();assert not t.preview_segments((3,3)) and not t.overlay((3,3))


def test_crossing_uses_real_native_geometry_not_only_bbox(plugin):
    s=Session(plugin);d=s.document.doc;d.layers.new('Muros ensayo')
    e=d.modelspace().add_line((0,0),(5,5),dxfattribs={'layer':'Muros ensayo'})
    C=module(s,'convert_tools')
    assert e.dxf.handle not in C.entities_in_rect(d,(1,4),(0,5),crossing=True)


def test_crossing_conversion_reads_whole_selected_entities_and_one_undo(plugin):
    s=Session(plugin);d=s.document.doc;d.layers.new('Muros ensayo')
    for y in (0,.2):d.modelspace().add_line((-1,y),(5,y),dxfattribs={'layer':'Muros ensayo'})
    P=module(s,'conversion_plan');t=s.tool('LINEASAMURO');t.classification=P.Classification({'Muros ensayo':'muros'})
    before=P.fingerprint(d);t.on_point((2,-1));t.on_point((1,1))
    assert t.conversion_preview is not None and len(t.conversion_preview.result[0])==1
    a,b,_=t.conversion_preview.result[0][0];assert math.dist(a,b)==pytest.approx(6.)
    assert t.preview_segments((0,0)) and P.fingerprint(d)==before and not s.walls()
    t.on_enter();assert len(s.walls())==1;s.history.undo();assert not s.walls()


def test_graphical_window_and_crossing_agree_with_preview(plugin):
    s=Session(plugin);t,inside,crossed,other,hidden=source(s)
    t.pick_role='muros';t.entity_picker=True;t.ctx.services.pick_entity=lambda p:None
    t.on_point((3,0));assert len(t.preview_segments((0,3)))>=4
    handles=set(t._candidates((3,0),(0,3),graphical=True));assert other.dxf.handle in handles
    t.on_point((0,3));assert set(t.classification.handles)==handles
    assert hidden.dxf.handle not in handles and not t.overlay((0,3))


def test_wall_type_sum_live_column_and_detail(plugin,app):
    from PySide6.QtWidgets import QLabel
    s=Session(plugin);D=module(s,'bim_dialogs');types=[{'name':'Ensayo','layers':[[.02,'A'],[.18,'B']]}]
    dlg,read=D.wall_types_form(None,types);w=dlg._arq
    assert '0,2' in w['total'].text()
    w['layers'].item(1,0).setText('0,28')
    assert '0,3' in w['total'].text()
    widget=w['list'].itemWidget(w['list'].currentItem())
    assert any('0,3 m'==label.text() for label in widget.findChildren(QLabel))
    assert read()[0]['thickness']==pytest.approx(.3)
    w['layers'].item(1,0).setText('nan')
    with pytest.raises(ValueError):read()
    dlg.close()


def test_wall_tool_context_loads_actual_drawing_catalog(plugin):
    s=Session(plugin);D=module(s,'bim_dialogs');P=module(s,'parameters_arq')
    values=P.load_defaults(s.document);values['wall_types']=[{'name':'Solo en este dibujo','layers':[[.22,'A']]}]
    s.history.execute(P.SetArchitecturalDefaults(values))
    assert D._types_of(s.tool('MURO').ctx,None)[0]['name']=='Solo en este dibujo'


@pytest.mark.parametrize('resolution',['restore','variant','detach'])
def test_wall_mismatch_requires_explicit_resolution(plugin,app,resolution):
    s=Session(plugin);D=module(s,'bim_dialogs');types=[{'name':'Ensayo','layers':[[.02,'A'],[.18,'B']]}]
    dlg,read=D.wall_form(None,{'type_name':'Ensayo','thickness':.2},types);w=dlg._arq
    assert not w['thickness'].isEnabled()
    w['manual_thickness'].setChecked(True);w['thickness'].setValue(.3)
    assert 'no coincide' in w['mismatch'].text() and w['resolution'].isEnabled()
    w['resolution'].setCurrentIndex(w['resolution'].findData(resolution));data=read()
    if resolution=='restore':assert data['thickness']==pytest.approx(.2)
    elif resolution=='variant':
        assert data['thickness']==pytest.approx(.3) and sum(a for a,b in data['layers'])==pytest.approx(.3)
        assert data['type_name']!='Ensayo' and data['layers'][0][0]/data['layers'][1][0]==pytest.approx(1/9)
    else:assert data['thickness']==pytest.approx(.3) and data['layers']==[] and data['type_name']!='Ensayo'
    assert types[0]['layers']==[[.02,'A'],[.18,'B']]
    dlg.close()


def test_record_local_type_keeps_sum_on_reopen(plugin,app):
    s=Session(plugin);D=module(s,'bim_dialogs')
    dlg,read=D.wall_form(None,{'type_name':'Tipo local','thickness':.3,'layers':[[.1,'A'],[.2,'B']]},[])
    assert read()['thickness']==pytest.approx(.3) and len(read()['layers'])==2
    dlg.close()


def test_wall_width_and_type_width_export_together(plugin,tmp_path):
    s=Session(plugin);A=module(s,'architectural_v10');T=module(s,'transactions')
    c=A.create_wall((0,0),(4,0),.3,2.7,0,'eje',type_name='Ensayo',layers=[[.02,'A'],[.28,'B']])
    T.apply_architectural_change(s.tool('MURO').ctx,c)
    e=next(e for e in s.export(tmp_path)['elements'] if e['ifc_class']=='IfcWall')
    assert e['quantities']['Width']==pytest.approx(.3)
    assert e['params']['wall_type']['width']==pytest.approx(.3) and e['psets']['ARQ_IngeCAD']['TypeThickness']==pytest.approx(.3)


def set_intervals(widget,values):
    w=widget._arq;w['count'].setValue(len(values)+1)
    for i,value in enumerate(values):w['table'].item(i,1).setText(str(value).replace('.',','))


def test_grid_form_counts_heterogeneous_intervals_totals_and_buttons(plugin,app):
    from PySide6.QtWidgets import QDialogButtonBox
    s=Session(plugin);F=module(s,'grid_tools');G=module(s,'grids')
    dlg,read=F.grid_form(None,{});w=dlg._arq
    set_intervals(w['x'],[2.,4.,3.]);set_intervals(w['y'],[1.5,2.5]);data=read()
    assert G.distances(data['x'])==[0.,2.,6.,9.] and G.distances(data['y'])==[0.,1.5,4.]
    assert '9 m' in w['x']._arq['total'].text() and '4 m' in w['y']._arq['total'].text()
    assert dlg.layout().indexOf(dlg._buttons)>=0 and dlg._buttons.button(QDialogButtonBox.Ok)
    w['x']._arq['equal'].setValue(3.5);w['x']._arq['fill'].click();assert G.distances(read()['x'])==[0.,3.5,7.,10.5]
    w['x']._arq['table'].item(0,1).setText('0')
    with pytest.raises(ValueError):read()
    dlg.close()


def test_grid_real_modal_then_point_then_model(plugin,app,monkeypatch):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QMainWindow,QApplication,QDialogButtonBox
    s=Session(plugin);D=module(s,'bim_dialogs');G=module(s,'grids');F=module(s,'grid_tools');P=module(s,'conversion_plan')
    ctx=s.tool('LINEASAMURO').ctx
    win=QMainWindow();win.document=s.document;s.services.window=win
    monkeypatch.setattr(D,'available',lambda ctx:True)
    caught=[]
    def accept():
        dlg=QApplication.activeModalWidget()
        try:
            assert dlg.layout().indexOf(dlg._buttons)>=0
            set_intervals(dlg._arq['x'],[2,4,3]);set_intervals(dlg._arq['y'],[1.5,2.5]);dlg._arq['angle'].setValue(30)
            dlg._buttons.button(QDialogButtonBox.Ok).click()
        except Exception as exc:caught.append(exc);dlg.reject()
    QTimer.singleShot(0,accept);tool=F.GridTool(ctx);tool.start();assert not caught
    assert tool.phase=='origin' and not G.axes(s.document.doc)
    before=P.fingerprint(s.document.doc);preview=tool.preview_segments((10,20));assert len(preview)==7
    assert P.fingerprint(s.document.doc)==before
    tool.on_point((10,20));assert tool.phase=='finished' and len(G.intersections(s.document.doc))==12
    assert [G.endpoints(e) for e,m in G.axes(s.document.doc)]==[list(seg) for seg in preview]
    s.history.undo();assert not G.axes(s.document.doc);s.history.redo();assert len(G.axes(s.document.doc))==7
    win.close()


def test_grid_optional_rotation_uses_cursor_and_enter(plugin):
    s=Session(plugin);G=module(s,'grids');t=s.tool('EJES')
    t.values={'x':'2 4 3','y':'1.5 2.5','interactive_angle':True}
    t.on_point((10,20));assert not G.axes(s.document.doc) and t.phase=='angle'
    preview=t.preview_segments((10,25));t.on_point((10,25))
    for (e,m),(a,b) in zip(G.axes(s.document.doc),preview):
        actual=G.endpoints(e);assert actual[0]==pytest.approx(a) and actual[1]==pytest.approx(b)
    assert t.values['angle']==pytest.approx(90.)


@pytest.mark.parametrize('reactors',[False,True])
def test_edit_one_gap_moves_following_axes_and_bound_pillars_one_undo(plugin,reactors):
    from core import commands
    if reactors and not hasattr(commands,'register_reactor'):pytest.skip('El anfitrión 0.7 no expone reactores')
    s=Session(plugin);G=module(s,'grids');T=module(s,'transactions');ctx=s.tool('MURO').ctx
    T.apply_architectural_change(ctx,G.create_grid((10,20),{'x':'2 4 3','y':'1.5 2.5','angle':30}),kind='column')
    assert G.place_columns(ctx,{'shape':'rect','width':.3,'depth':.3,'height':3,'base':0})
    user=s.document.doc.modelspace().add_text('Anotación sintética ajena')
    axes={m['id']:(e,m) for e,m in G.axes(s.document.doc)}
    cols=[e for e in s.document.doc.modelspace() if (s.meta(e)or{}).get('kind')=='column']
    old={s.meta(e)['id']:s.meta(e)['center'][:] for e in cols}
    tool=s.tool('EDITAREJE');tool.entity=next(iter(axes.values()))[0]
    if reactors:
        for reactor in plugin.reactors:commands.register_reactor(reactor,'r18-test')
    try:
        tool.apply_spacing({'x':'2 6 3','y':'1.5 2.5'})
        for e in cols:
            rec=s.meta(e);u=axes[rec['grid_link']['u']][1];move=2 if u['index']>=2 else 0
            assert rec['center']==pytest.approx([old[rec['id']][0]+move*math.cos(math.pi/6),old[rec['id']][1]+move*.5])
        assert user.is_alive and len(G.axes(s.document.doc))==7
        assert len(list(s.document.doc.modelspace().query('DIMENSION')))==7
        s.history.undo();assert all(s.meta(e)['center']==pytest.approx(old[s.meta(e)['id']]) for e in cols)
        s.history.redo();assert G.spacing_values(s.document.doc,G.metadata(tool.entity)['grid_id'])[0]['x']=='2.000000 6.000000 3.000000'
    finally:
        if reactors:commands.unregister_reactors('r18-test')


def test_skewed_grid_or_invalid_interval_never_partially_edits(plugin):
    s=Session(plugin);G=module(s,'grids');T=module(s,'transactions');P=module(s,'conversion_plan');ctx=s.tool('MURO').ctx
    T.apply_architectural_change(ctx,G.create_grid((0,0),{'x':'2 4 3','y':'1.5 2.5'}),kind='column')
    e,m=G.axes(s.document.doc)[0];before=P.fingerprint(s.document.doc)
    with pytest.raises(ValueError):G.resize_grid(s.document.doc,m['grid_id'],{'x':'2 0 3','y':'1.5 2.5'})
    assert before==P.fingerprint(s.document.doc)
    a,b=G.endpoints(e);s.history.execute(G.SetAxis(e,[a,(b[0]+.5,b[1])]))
    with pytest.raises(ValueError):G.spacing_values(s.document.doc,m['grid_id'])


def test_native_overlay_geometry_and_nested_layer_classification(plugin,app):
    from core.select import GeometryIndex
    from views.tool_controller import ToolController
    s=Session(plugin);d=s.document.doc;d.layers.new('Muros ensayo')
    block=d.blocks.new('Ensayo');block.add_line((0,0),(2,0),dxfattribs={'layer':'Muros ensayo'})
    e=d.modelspace().add_blockref('Ensayo',(1,1));circle=d.modelspace().add_circle((4,2),.5,dxfattribs={'layer':'Muros ensayo'})
    t=s.tool('LINEASAMURO');P=module(s,'conversion_plan');t.classification=P.Classification({'Muros ensayo':'muros'})
    index=GeometryIndex(s.document);s.services.index=index
    s.services.edges_geometry=lambda handles:ToolController.edges_geometry(SimpleNamespace(index=index),handles)
    t.on_point((0,0));assert set(t._candidates((0,0),(6,4)))=={e.dxf.handle,circle.dxf.handle}
    lines=t.overlay((6,4))['chosen'];assert ((1.,1.),(3.,1.)) in lines
    assert any(a[0]>3 and b[0]>3 for a,b in lines)


def test_grid_cancelled_modal_ignores_points(plugin,app,monkeypatch):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QMainWindow,QApplication
    s=Session(plugin);ctx=s.tool('MURO').ctx;D=module(s,'bim_dialogs');F=module(s,'grid_tools');G=module(s,'grids')
    win=QMainWindow();win.document=s.document;s.services.window=win
    monkeypatch.setattr(D,'available',lambda ctx:True)
    QTimer.singleShot(0,lambda:QApplication.activeModalWidget().reject())
    t=F.GridTool(ctx);t.start();t.on_point((10,20))
    assert t.phase=='finished' and not G.axes(s.document.doc);win.close()


def test_grid_rotation_enter_uses_fixed_angle(plugin):
    s=Session(plugin);G=module(s,'grids');t=s.tool('EJES')
    t.values={'x':'2 4 3','y':'1.5 2.5','interactive_angle':True,'angle':30}
    t.on_point((10,20));preview=G.grid_geometry((10,20),t.values);t.on_enter()
    assert [G.endpoints(e) for e,m in G.axes(s.document.doc)]==[list(seg) for seg in preview]


def test_edit_spacing_real_modal_updates_grid(plugin,app):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication,QDialogButtonBox
    s=Session(plugin);G=module(s,'grids');T=module(s,'transactions');ctx=s.tool('MURO').ctx
    T.apply_architectural_change(ctx,G.create_grid((0,0),{'x':'2 4 3','y':'1.5 2.5'}),kind='column')
    t=s.tool('EDITAREJE');t.entity=G.axes(s.document.doc)[0][0];errors=[]
    def accept():
        dlg=QApplication.activeModalWidget()
        try:
            dlg._arq['x']._arq['table'].item(1,1).setText('6')
            dlg._buttons.button(QDialogButtonBox.Ok).click()
        except Exception as exc:errors.append(exc);dlg.reject()
    QTimer.singleShot(0,accept);assert t.on_option('Separaciones');assert not errors
    assert G.spacing_values(s.document.doc,G.metadata(t.entity)['grid_id'])[0]['x']=='2.000000 6.000000 3.000000'
    s.history.undo();assert G.spacing_values(s.document.doc,G.metadata(t.entity)['grid_id'])[0]['x']=='2.000000 4.000000 3.000000'

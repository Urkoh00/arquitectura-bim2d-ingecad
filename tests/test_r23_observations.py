# SPDX-License-Identifier: GPL-3.0-or-later
"""R23: native UI/state/history contracts and independent geometric checks."""
import copy
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from tests.test_ingecad_integration import plugin
from tests.test_fichas import qt, _Ctx
from tests.test_wall_tools import Session, draw
from tests.test_r12_conversion import module
from tests.test_recintos import _cmd_ctx, _vivienda
from tests.test_solids import watertight


def items(menu):
    from core.plugins import MenuItem, Submenu
    for entry in menu:
        if isinstance(entry, MenuItem): yield entry
        elif isinstance(entry, Submenu): yield from items(entry.items)


def test_every_menu_item_has_existing_valid_svg(plugin):
    entries=list(items(plugin.menu))
    assert entries                      # el recuento cambia con las versiones; lo que importa es el icono
    for entry in entries:
        assert entry.icon and Path(entry.icon).is_file(), entry.command
        root=ET.parse(entry.icon).getroot()
        assert root.attrib['viewBox']=='0 0 24 24'


def test_lineasamuro_immediately_before_exchange(plugin):
    from core.plugins import Submenu
    index=next(i for i,m in enumerate(plugin.menu)if isinstance(m,Submenu)and m.label=='Intercambio BIM')
    assert plugin.menu[index-1].command=='LINEASAMURO'
    assert sum(m.command=='LINEASAMURO' for m in items(plugin.menu))==1


@pytest.mark.parametrize('record', [
    {'type':'door','sill':0.,'width':.9,'height':2.1,'operation':'SWINGING'},
    {'type':'door','sill':0.,'width':3.8,'height':2.4,'leaves':2,'operation':'SWINGING'},
    {'type':'window','width':2.4,'height':1.1,'sill':1.2,'operation':'SIDEHUNG'},
    {'type':'window','width':.5,'height':3.,'sill':.2,'operation':'SLIDING'},
    {'type':'window','width':1.8,'height':1.1,'sill':1.2,'operation':'FIXED','curve_mode':'curva'}])
def test_preview_shared_metric_scale_and_reserved_footer(plugin, qt, record):
    s=Session(plugin);B=module(s,'bim_dialogs');source=copy.deepcopy(record)
    view=B.carpentry_preview(lambda:record);view.resize(340,380);view.show();qt.processEvents();view.grab()
    assert not view.error
    m=view.metrics
    assert m['elevation_scale']==m['plan_scale']
    assert m['elevation_bottom']<m['plan_top']<m['plan_bottom']<m['footer_top']
    assert source==record
    view.close()


def make_wall(s, **values):
    A=module(s,'architectural_v10');T=module(s,'transactions')
    command=A.create_wall((0,0),(6,0),.3,values.pop('height',2.7),values.pop('base',0),**values)
    T.apply_architectural_change(s.tool('MURO').ctx,command)
    return command.entity


@pytest.mark.parametrize('category,layer,predefined,external', [
    ('fachada','ARQ-MUROS','USERDEFINED/EXTERNALWALL',True),('tabique','ARQ-TABIQUES','PARTITIONING',False),
    ('medianera','ARQ-MEDIANERAS','USERDEFINED/PARTYWALL',True),('sotano','ARQ-SOTANO','USERDEFINED/BASEMENTWALL',True)])
def test_categories_layers_export_and_identity(plugin, category, layer, predefined, external):
    s=Session(plugin);wall=make_wall(s,wall_category='fachada');old=s.meta(wall)
    command=module(s,'architectural_v10').edit_wall(wall,wall_category=category)
    module(s,'transactions').apply_architectural_change(s.tool('MURO').ctx,command)
    assert wall.dxf.layer==layer and s.meta(wall)['id']==old['id']
    el=s.export(None)['elements'][0]
    pre, _, obj = predefined.partition('/')
    assert el['enums']['PredefinedType']==pre
    assert (el.get('attributes') or {}).get('ObjectType') == (obj or None)
    assert el['psets']['Pset_WallCommon']['IsExternal'] is external
    assert el['psets']['ARQ_IngeCAD']['Medianera'] is (category=='medianera')
    assert el['psets']['ARQ_IngeCAD']['ContactoTerreno'] is (category=='sotano')
    assert any(e.dxf.layer==layer and (s.meta(e)or{}).get('kind')=='junction_edge'for e in s.document.doc.modelspace())
    s.history.undo();assert s.meta(wall)==old and wall.dxf.layer=='ARQ-MUROS'


def test_category_in_wall_and_type_sheets(plugin, qt):
    s=Session(plugin);B=module(s,'bim_dialogs')
    dlg,read=B.wall_form(_Ctx(),{'height':2.7,'wall_category':'medianera'},[])
    assert read()['wall_category']=='medianera';dlg.close()
    dlg,read=B.wall_types_form(_Ctx(),[{'name':'Ensayo','layers':[[.2,'Material']],'wall_category':'tabique'}])
    box=dlg._arq['wall_category'];box.setCurrentIndex(box.findData('sotano'))
    assert read()[0]['wall_category']=='sotano';dlg.close()


def test_legacy_category_migration_explicit_reversible(plugin):
    s=Session(plugin);wall=make_wall(s,wall_role='medianeras');A=module(s,'architectural')
    rec=s.meta(wall);rec.pop('wall_category');rec['wall_role']='medianeras';wall.dxf.layer='ARQ-MUROS3D'
    A._xdata(s.document.doc.modelspace(),wall,rec)
    before=s.meta(wall)
    module(s,'migration').migrar_arq(_cmd_ctx(s))
    assert s.meta(wall)['wall_category']=='medianera' and wall.dxf.layer=='ARQ-MEDIANERAS'
    assert any('Categorías' in text for text in s.out)
    s.history.undo();assert s.meta(wall)==before and wall.dxf.layer=='ARQ-MUROS3D'


def catalog(s, upper=3.2):
    import uuid
    L=module(s,'levels');data=L.load(s.document)
    high={'id':uuid.uuid4().hex,'name':'Planta primera','elevation':upper}
    data['levels'].append(high);L.apply(s.tool('MURO').ctx,data)
    return L,L.load(s.document),high


def test_level_state_is_native_and_one_undo(plugin):
    s=Session(plugin);wall=make_wall(s);L,data,high=catalog(s);N=module(s,'level_layers')
    ident=data['active'];name=wall.dxf.layer
    assert name.endswith(N.suffix(ident)) and wall.dxf.invisible==1
    for prop in ('on','frozen','locked'):
        value=prop!='on'
        N.set_state(s.tool('MURO').ctx,ident,prop,value)
        assert N.state(s.document,ident)[prop] is value
        getter={'on':'is_on','frozen':'is_frozen','locked':'is_locked'}[prop]
        assert getattr(s.document.doc.layers.get(name),getter)() is value
        s.history.undo();assert N.state(s.document,ident)[prop] is (prop=='on')
        s.history.redo();assert N.state(s.document,ident)[prop] is value
        N.set_state(s.tool('MURO').ctx,ident,prop,not value)


def test_locked_level_rejects_plugin_edit_creation_and_erase(plugin):
    from core.actions import EraseCommand
    s=Session(plugin);wall=make_wall(s);L,data,_=catalog(s);N=module(s,'level_layers');T=module(s,'transactions')
    N.set_state(s.tool('MURO').ctx,data['active'],'locked',True)
    P=module(s,'conversion_plan');before=P.fingerprint(s.document.doc)
    edit=module(s,'architectural_v10').edit_wall(wall,height=3)
    with pytest.raises(ValueError):T.apply_architectural_change(s.tool('MURO').ctx,edit)
    assert P.fingerprint(s.document.doc)==before
    with pytest.raises(ValueError):make_wall(s)
    assert P.fingerprint(s.document.doc)==before
    with pytest.raises(ValueError):T.apply_architectural_change(s.tool('MURO').ctx,EraseCommand([wall]))
    assert P.fingerprint(s.document.doc)==before


def test_public_toolbar_or_graceful_07_fallback(plugin, qt):
    from PySide6.QtWidgets import QToolBar
    from core.plugins import PluginContext
    s=Session(plugin);L,data,high=catalog(s);bar=QToolBar()
    class Host:
        document=s.document
        tools=type('Tools',(),{'_execute':staticmethod(s.history.execute)})()
        def plugin_toolbar(self,*_):return bar
    ctx=PluginContext(host=Host(),echo=s.out.append);N=module(s,'level_layers')
    N.install_toolbar(ctx)
    if not callable(getattr(ctx,'toolbar',None)):
        assert not bar.property('arq_levels_installed');return
    controls=bar._arq_level_controls
    assert 'Capa: 0'==controls['current_layer'].text()
    assert controls['active'].currentText()=='Planta baja'
    controls['active'].setCurrentIndex(controls['active'].findData(high['id']))
    assert L.load(s.document)['active']==high['id']
    controls['locked'].click();assert N.state(s.document,high['id'])['locked'] is True
    assert controls['locked'].text()=='Bloqueado'
    bar.close()


def test_wall_to_level_recalculates_quantities_undo_redo(plugin):
    s=Session(plugin);L,data,high=catalog(s)
    wall=make_wall(s,height_constraint='level',level_id=data['active'],base_offset=.1,top_level_id=high['id'],top_offset=-.2)
    fixed=make_wall(s,base=10,height=2.4)
    assert s.meta(wall)['base']==pytest.approx(.1) and s.meta(wall)['height']==pytest.approx(2.9)
    data=L.load(s.document);data['levels'][1]['elevation']=4.2;L.apply(s.tool('MURO').ctx,data)
    assert s.meta(wall)['height']==pytest.approx(3.9) and s.meta(fixed)['height']==2.4
    el=next(e for e in s.export(None)['elements']if e['id']==s.meta(wall)['id'])
    assert el['quantities']['Height']==pytest.approx(3.9)
    assert el['volume']==pytest.approx(6*.3*3.9)
    s.history.undo();assert s.meta(wall)['height']==pytest.approx(2.9)
    s.history.redo();assert s.meta(wall)['height']==pytest.approx(3.9)


@pytest.mark.parametrize('operation',['delete','zero','negative'])
def test_invalid_top_level_change_rejected_without_mutation(plugin,operation):
    s=Session(plugin);L,data,high=catalog(s)
    make_wall(s,height_constraint='level',level_id=data['active'],top_level_id=high['id'])
    P=module(s,'conversion_plan');before=P.fingerprint(s.document.doc);old=L.load(s.document)
    data=copy.deepcopy(old)
    if operation=='delete':data['levels']=data['levels'][:1]
    else:data['levels'][1]['elevation']=0 if operation=='zero'else -1
    with pytest.raises(ValueError):L.apply(s.tool('MURO').ctx,data)
    assert L.load(s.document)==old and P.fingerprint(s.document.doc)==before


def test_wall_constraint_sheet_is_explicit_and_height_read_only(plugin,qt):
    s=Session(plugin);L,data,high=catalog(s);B=module(s,'bim_dialogs')
    ctx=type('Context',(),{'document':s.document,'services':None})()
    dlg,read=B.wall_form(ctx,{'level_id':data['active'],'height':2.7},[])
    assert read()['height_constraint']=='fixed'
    controls=dlg._arq;controls['height_constraint'].setCurrentIndex(controls['height_constraint'].findData('level'))
    controls['top_level'].setCurrentIndex(controls['top_level'].findData(high['id']))
    controls['base_offset'].setValue(.1);controls['top_offset'].setValue(-.2)
    assert read()['height']==pytest.approx(2.9) and not controls['height'].isEnabled()
    assert '2.9000' in controls['resulting_height'].text();dlg.close()


@pytest.mark.parametrize('leaves,operation',[(1,'SWINGING'),(3,'SLIDING'),(6,'SWINGING')])
def test_adosado_preserves_wall_and_reduces_space(plugin,leaves,operation):
    s=Session(plugin);_vivienda(s);s.tool('RECINTO').on_point((2,2))
    before=s.export(None);wall=next(w for w in s.walls().values()if s.meta(w)['a']==[0.,0.])
    ident=s.meta(wall)['id'];old=next(e['volume']for e in before['elements']if e['id']==ident)
    C=module(s,'cabinets');T=module(s,'transactions');cmd=C.create(wall,1,1.2,.6,2.1,leaves,operation,mode='adosado')
    T.apply_architectural_change(s.tool('MURO').ctx,cmd,kind='opening')
    data=s.export(None);out=next(e for e in data['elements']if e['id']==ident)
    assert out['volume']==pytest.approx(old) and not out['openings']
    body=next(e for e in data['elements']if e['ifc_class']=='IfcBuildingElementProxy')
    front=next(e for e in data['elements']if e['id']==s.meta(cmd.entity)['id'])
    assert front['ifc_class']=='IfcDoor' and 'fills'not in front
    assert body['host']==ident and front['host']==ident
    room=next(e for e in data['elements']if e['ifc_class']=='IfcSpace')
    # criterio de los programas de cálculo (19-11-2026): el IfcSpace llega a los muros y sus
    # cantidades no descuentan el armario; la superficie útil, sí
    assert room['quantities']['NetFloorArea']==pytest.approx(17.86)
    assert room['volume']==pytest.approx(17.86*3.0)
    # por defecto, Decreto 10/2019 de Extremadura: el armario computa
    recinto=room['psets']['ARQ_Recinto']
    assert recinto['SuperficieUtil']==pytest.approx(17.86)
    assert recinto['SuperficieArmarios']==pytest.approx(.72)
    assert recinto['ArmariosEnSuperficieUtil']=='computan'
    assert body['params']['space_ids']==[room['id']]
    S=module(s,'geom.solids')
    for el in (body,room):
        faces=[(f['outer'],f['holes'])for f in el['faces']]
        assert watertight(faces) and S.face_volume(faces)==pytest.approx(el['volume'])
    from ingetrazo_ext import arquitectura_bim as X
    X.validate_contract(data)
    s.history.undo()
    room=next(e for e in s.export(None)['elements']if e['ifc_class']=='IfcSpace')
    assert room['psets']['ARQ_Recinto']['SuperficieArmarios']==pytest.approx(0)
    s.history.redo();assert any(e['ifc_class']=='IfcBuildingElementProxy'for e in s.export(None)['elements'])


def test_cabinet_default_and_legacy_niche_modes(plugin,qt):
    s=Session(plugin);tool=s.tool('ARMARIOBIM')
    assert tool.values['cabinet_mode']=='adosado'
    C=module(s,'cabinets');dlg,read=C.form(_Ctx(),{'cabinet':True,'niche_depth':.2})
    assert read()['cabinet_mode']=='nicho'
    dlg._arq['cabinet_mode'].setCurrentIndex(dlg._arq['cabinet_mode'].findData('adosado'))
    dlg._arq['leaves'].setValue(8)
    assert read()['leaves']==8;dlg.close()


def multilevel_room(s):
    import uuid
    L=module(s,'levels');data=L.load(s.document)
    for name,z in [('Primera',3.2),('Coronación',6.4)]:
        data['levels'].append({'id':uuid.uuid4().hex,'name':name,'elevation':z})
    L.apply(s.tool('MURO').ctx,data);data=L.load(s.document)
    T=module(s,'transactions');A=module(s,'architectural_v10');S=module(s,'slabs')
    poly=[(0,0),(6,0),(6,4),(0,4)]
    for level in data['levels']:
        cmd=S.create(poly,thickness=.2,top=level['elevation'],level_id=level['id'],level=level['name'])
        T.apply_architectural_change(s.tool('MURO').ctx,cmd)
    for a,b in zip(poly,poly[1:]+poly[:1]):
        cmd=A.create_wall(a,b,.3,2.7,0,height_constraint='level',level_id=data['levels'][0]['id'],
                          top_level_id=data['levels'][2]['id'])
        T.apply_architectural_change(s.tool('MURO').ctx,cmd)
    s.tool('RECINTO').on_point((2,2))
    data['active']=data['levels'][1]['id'];L.apply(s.tool('MURO').ctx,data)
    s.tool('RECINTO').on_point((2,2))
    return L,L.load(s.document)


def test_spanning_wall_rooms_quantities_single_undo_redo(plugin):
    s=Session(plugin);L,data=multilevel_room(s)
    old=L.load(s.document);out=s.export(None)
    assert sorted(e['quantities']['Height']for e in out['elements']if e['ifc_class']=='IfcSpace')==pytest.approx([3,3])
    ids=sorted(e['id']for e in out['elements'])
    data['levels'][2]['elevation']=7.4;L.apply(s.tool('MURO').ctx,data)
    out=s.export(None)
    assert sorted(e['quantities']['Height']for e in out['elements']if e['ifc_class']=='IfcSpace')==pytest.approx([3,4])
    assert all(e['quantities']['Height']==pytest.approx(7.4)for e in out['elements']if e['ifc_class']=='IfcWall')
    for e in out['elements']:
        if e['ifc_class']=='IfcSpace':assert e['volume']==pytest.approx(21.09*e['quantities']['Height'])
    s.history.undo();assert L.load(s.document)==old
    assert sorted(e['quantities']['Height']for e in s.export(None)['elements']if e['ifc_class']=='IfcSpace')==pytest.approx([3,3])
    s.history.redo();assert sorted(e['id']for e in s.export(None)['elements'])==ids


def test_upper_floor_projection_lock_protects_spanning_wall(plugin):
    s=Session(plugin);L,data=multilevel_room(s);N=module(s,'level_layers')
    ident=data['levels'][1]['id']
    edges=[e for e in s.document.doc.modelspace()if(s.meta(e)or{}).get('display_level_id')==ident]
    assert edges and all(e.dxf.layer.endswith(N.suffix(ident))for e in edges)
    N.set_state(s.tool('MURO').ctx,ident,'locked',True)
    wall=next(iter(s.walls().values()))
    edit=module(s,'architectural_v10').edit_wall(wall,top_offset=.1)
    with pytest.raises(ValueError):module(s,'transactions').apply_architectural_change(s.tool('MURO').ctx,edit)


def test_shrinking_constrained_wall_rejects_carpentry_that_would_not_fit(plugin):
    s=Session(plugin);L,data,high=catalog(s);A=module(s,'architectural_v10');T=module(s,'transactions')
    wall=make_wall(s,height_constraint='level',level_id=data['active'],top_level_id=high['id'])
    T.apply_architectural_change(s.tool('MURO').ctx,A.create_opening(wall,1,.9,0,2.1),kind='opening')
    old=L.load(s.document);data=copy.deepcopy(old);data['levels'][1]['elevation']=2
    with pytest.raises(ValueError):L.apply(s.tool('MURO').ctx,data)
    assert L.load(s.document)==old and s.meta(wall)['height']==pytest.approx(3.2)


def test_old_fixed_wall_does_not_gain_a_constraint(plugin):
    s=Session(plugin);wall=make_wall(s);A=module(s,'architectural')
    rec=s.meta(wall);rec.pop('height_constraint');A._xdata(s.document.doc.modelspace(),wall,rec)
    L,data,high=catalog(s);data['levels'][1]['elevation']=5;L.apply(s.tool('MURO').ctx,data)
    assert s.meta(wall)['height']==pytest.approx(2.7)
    assert 'height_constraint'not in s.meta(wall)


def test_adosado_opposite_side_and_regeneration_do_not_cut_wall(plugin):
    s=Session(plugin);wall=make_wall(s);C=module(s,'cabinets');T=module(s,'transactions')
    for side in (-1,1):
        T.apply_architectural_change(s.tool('MURO').ctx,C.create(wall,1,1.2,.6,2.1,mode='adosado',side=side),kind='opening')
    data=s.export(None)
    assert len([e for e in data['elements']if e['ifc_class']=='IfcBuildingElementProxy'])==2
    assert next(e['volume']for e in data['elements']if e['ifc_class']=='IfcWall')==pytest.approx(6*.3*2.7)
    assert not module(s,'integrity').audit(s.document.doc)


def test_cabinet_edit_depth_updates_usable_area_and_undo(plugin):
    s=Session(plugin);_vivienda(s);s.tool('RECINTO').on_point((2,2))
    wall=next(w for w in s.walls().values()if s.meta(w)['a']==[0.,0.]);C=module(s,'cabinets');T=module(s,'transactions')
    cmd=C.create(wall,1,1.2,.6,2.1,mode='adosado');T.apply_architectural_change(s.tool('MURO').ctx,cmd,kind='opening')
    before=s.meta(cmd.entity)
    edit=module(s,'arq_properties').opening_change(cmd.entity,{'width':1.2,'height':2.1,'sill':0,'niche_depth':.8,'cabinet_mode':'adosado'})
    T.apply_architectural_change(s.tool('MURO').ctx,edit,kind='opening')
    room=next(e for e in s.export(None)['elements']if e['ifc_class']=='IfcSpace')
    assert room['quantities']['NetFloorArea']==pytest.approx(17.86)
    assert room['psets']['ARQ_Recinto']['SuperficieArmarios']==pytest.approx(.96)
    s.history.undo();assert s.meta(cmd.entity)==before


def test_hidden_level_is_not_a_geometric_pick_fallback(plugin):
    s=Session(plugin);make_wall(s);L,data,_=catalog(s);N=module(s,'level_layers')
    N.set_state(s.tool('MURO').ctx,data['active'],'on',False)
    tool=s.tool('ARMARIOBIM')
    assert tool._wall_at((2,.15))==(None,None)


def test_assigning_into_locked_level_is_rejected(plugin):
    s=Session(plugin);wall=make_wall(s);L,data,high=catalog(s);N=module(s,'level_layers')
    N.set_state(s.tool('MURO').ctx,high['id'],'locked',True)
    before=s.meta(wall)
    with pytest.raises(ValueError):L.assign(s.tool('MURO').ctx,[wall],high['id'])
    assert s.meta(wall)==before


def test_public_veto_callback_installs_available_toolbar(plugin,qt):
    from PySide6.QtWidgets import QToolBar
    from core.plugins import PluginContext
    s=Session(plugin);bar=QToolBar();current=[None]
    class Host:
        document=s.document
        tools=type('Tools',(),{'_execute':staticmethod(s.history.execute)})()
        def plugin_toolbar(self,*_):return current[0]
    ctx=PluginContext(host=Host(),echo=s.out.append);N=module(s,'level_layers')
    N.install_toolbar(ctx);assert not bar.property('arq_levels_installed')
    current[0]=bar
    assert N.before_command(ctx,None)is None
    assert bool(bar.property('arq_levels_installed')) is callable(getattr(ctx,'toolbar',None))
    bar.close()


def test_real_qt_host_toolbar_enabled_after_document_open(plugin,qt):
    from PySide6.QtWidgets import QMainWindow,QToolBar
    from PySide6.QtTest import QTest
    from core.plugins import PluginContext
    s=Session(plugin)
    class Host(QMainWindow):
        def __init__(self):
            super().__init__();self.document=s.document;self.bar=None
            self.tools=type('Tools',(),{'_execute':staticmethod(s.history.execute)})()
        def plugin_toolbar(self,*_):return self.bar
    host=Host();ctx=PluginContext(host=host,echo=s.out.append)
    plugin.on_document_open(ctx,s.document)
    host.bar=QToolBar(host);host.addToolBar(host.bar)
    QTest.qWait(650)
    assert bool(host.bar.property('arq_levels_installed')) is callable(getattr(ctx,'toolbar',None))
    if getattr(plugin,'on_regen_done',None):plugin.on_regen_done(ctx,'Model')
    host.deleteLater();qt.processEvents()


def test_upper_floor_cabinet_has_own_native_layer_and_export_level(plugin):
    s=Session(plugin);L,data=multilevel_room(s);N=module(s,'level_layers')
    N.set_state(s.tool('MURO').ctx,data['levels'][0]['id'],'on',False)
    wall=next(w for w in s.walls().values()if s.meta(w)['a']==[0.,0.])
    C=module(s,'cabinets');T=module(s,'transactions')
    cmd=C.create(wall,1,1.2,.6,2.1,base=3.2,mode='adosado')
    T.apply_architectural_change(s.tool('MURO').ctx,cmd,kind='opening')
    assert cmd.entity.dxf.layer.endswith(N.suffix(data['levels'][1]['id']))
    elements=s.export(None)['elements']
    for e in elements:
        if e['ifc_class']in('IfcDoor','IfcBuildingElementProxy'):assert e['level_id']==data['levels'][1]['id']
    rooms={e['params']['base']:e for e in elements if e['ifc_class']=='IfcSpace'}
    assert rooms[0]['quantities']['NetFloorArea']==pytest.approx(21.09)
    assert rooms[3.2]['quantities']['NetFloorArea']==pytest.approx(21.09)
    assert rooms[3.2]['psets']['ARQ_Recinto']['SuperficieArmarios']==pytest.approx(.72)


def test_criterio_armarios_descuentan_la_superficie_util(plugin):
    """Con «descuentan» (división interior fija) la planta del armario adosado
    no es superficie útil; el IfcSpace es el mismo en los dos criterios."""
    s=Session(plugin);_vivienda(s);s.tool('RECINTO').on_point((2,2))
    wall=next(w for w in s.walls().values()if s.meta(w)['a']==[0.,0.])
    C=module(s,'cabinets');T=module(s,'transactions');P=module(s,'parameters_arq')
    T.apply_architectural_change(s.tool('MURO').ctx,C.create(wall,1,1.2,.6,2.1,mode='adosado'),kind='opening')
    antes=next(e for e in s.export(None)['elements']if e['ifc_class']=='IfcSpace')
    assert antes['psets']['ARQ_Recinto']['ArmariosEnSuperficieUtil']=='computan'   # por defecto
    values=P.load_defaults(s.document);values['general']['armarios_superficie_util']='descuentan'
    s.history.execute(P.SetArchitecturalDefaults(values))
    room=next(e for e in s.export(None)['elements']if e['ifc_class']=='IfcSpace')
    assert room['psets']['ARQ_Recinto']['SuperficieUtil']==pytest.approx(17.14)
    assert room['psets']['ARQ_Recinto']['ArmariosEnSuperficieUtil']=='descuentan'
    assert room['quantities']==antes['quantities'] and room['volume']==pytest.approx(antes['volume'])
    with pytest.raises(ValueError,match='armarios_superficie_util'):
        P.validate_defaults({**values,'general':{**values['general'],'armarios_superficie_util':'a veces'}})


@pytest.mark.parametrize('categoria,avisa',[('fachada',True),('medianera',True),('sotano',True),('tabique',False)])
def test_armario_empotrado_en_la_envolvente_avisa(plugin,categoria,avisa):
    """Un nicho en fachada, medianera o muro de sótano debilita el aislamiento
    térmico y acústico (como los radiadores empotrados): se avisa al crearlo y
    al exportar. El armario adosado no avisa."""
    s=Session(plugin);wall=make_wall(s)
    A=module(s,'architectural');rec=s.meta(wall);rec['wall_category']=categoria;A._xdata(s.document.doc.modelspace(),wall,rec)
    C=module(s,'cabinets');T=module(s,'transactions')
    T.apply_architectural_change(s.tool('MURO').ctx,C.create(wall,1,1.2,.2,2.1,mode='nicho'),kind='opening')
    issues=[i for i in s.export(None)['issues'] if 'armario empotrado' in i]
    assert bool(issues) is avisa
    assert C.niche_warning({'wall_category':categoria},'adosado') is None

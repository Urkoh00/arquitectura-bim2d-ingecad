# SPDX-License-Identifier: GPL-3.0-or-later
import copy,math,uuid
import pytest
from tests.test_ingecad_integration import plugin
from tests.test_wall_tools import Session
from tests.test_r12_conversion import module

OUTER=[(0,0),(6,0),(6,4),(0,4)]
HOLE=[(1,1),(2,1),(2,2),(1,2)]


def wall(s,base=0,level='Planta baja'):
    A=module(s,'architectural_v10');T=module(s,'transactions');w=A.create_wall((0,0),(4,0),.3,2.7,base,level=level)
    T.apply_architectural_change(s.tool('MURO').ctx,w);return w.entity


def catalog(s):
    L=module(s,'levels');data=L.load(s.document)
    pa={'id':uuid.uuid4().hex,'name':'Planta primera','elevation':3.}
    data['levels'].append(pa);return L,data,pa


def test_legacy_migration_no_movement_one_undo_and_exact_registry_restore(plugin):
    s=Session(plugin);w=wall(s,1.25,'Nombre anterior');P=module(s,'conversion_plan');L=module(s,'levels')
    before=s.meta(w);fingerprint=P.fingerprint(s.document.doc);assert L.KEY not in s.document.doc.rootdict
    data=L.load(s.document);assert L.KEY not in s.document.doc.rootdict
    L.apply(s.tool('MURO').ctx,data);m=s.meta(w)
    assert m['id']==before['id']and m['base']==1.25 and m['level']=='Planta baja'and m['legacy_level']=='Nombre anterior'
    assert m['level_id']==data['active']and m['level_offset']==1.25
    s.history.undo();assert L.KEY not in s.document.doc.rootdict and s.meta(w)==before
    assert P.fingerprint(s.document.doc)==fingerprint
    s.history.redo();assert s.meta(w)['level_id']==data['active']


def test_levels_rename_move_only_associated_sources_and_new_wall_defaults(plugin):
    s=Session(plugin);w=wall(s);L,data,pa=catalog(s);L.apply(s.tool('MURO').ctx,data)
    L.assign(s.tool('MURO').ctx,[w],pa['id'],keep_absolute=False);assert s.meta(w)['base']==3
    low=wall(s);assert s.meta(low)['base']==0
    data=L.load(s.document);data['active']=pa['id'];data['levels'][1].update(name='Alta renombrada',elevation=4.5)
    L.apply(s.tool('MURO').ctx,data);assert s.meta(w)['base']==4.5 and s.meta(low)['base']==0
    assert s.meta(w)['level_id']==pa['id']and s.meta(w)['level']=='Alta renombrada'
    params=module(s,'parameters_arq').load_defaults(s.document);assert params['wall']['base']==4.5 and params['column']['level']=='Alta renombrada'
    t=s.tool('MURO');t.on_point((0,3));t.on_point((4,3));new=[e for e in s.walls().values()if e is not w and e is not low]
    assert new and s.meta(new[0])['level_id']==pa['id']and s.meta(new[0])['base']==4.5


def test_referenced_level_delete_rejected_without_document_change(plugin):
    s=Session(plugin);w=wall(s);L,data,pa=catalog(s);L.apply(s.tool('MURO').ctx,data)
    P=module(s,'conversion_plan');before=P.fingerprint(s.document.doc);data['levels']=data['levels'][1:];data['active']=pa['id']
    with pytest.raises(ValueError):L.apply(s.tool('MURO').ctx,data)
    assert P.fingerprint(s.document.doc)==before


@pytest.mark.parametrize('holes',[[],[HOLE],[HOLE,[(3,1),(5,1),(5,3),(3,3)]]])
def test_slab_native_geometry_quantities_and_single_undo(plugin,holes,tmp_path):
    s=Session(plugin);S=module(s,'slabs');L=module(s,'levels');P=module(s,'conversion_plan');before=P.fingerprint(s.document.doc)
    cmd=S.apply_new(s.tool('MURO').ctx,OUTER,holes,thickness=.25)
    rec=S.read(cmd.entity);assert rec['base']==pytest.approx(-.25)and rec['level_id']==L.load(s.document)['active']
    out=s.export(tmp_path);slab=next(e for e in out['elements']if e['ifc_class']=='IfcSlab')
    area=24-sum(abs(module(s,'geom.polygon').area(h))for h in holes)
    assert slab['volume']==pytest.approx(area*.25)and slab['quantities']['NetArea']==pytest.approx(area)
    assert len(slab['openings'])==len(holes)and out['version']==3
    assert out['levels'][0]['elevation']==0 and out['levels'][0]['guid']
    faces=[(f['outer'],f['holes'])for f in slab['faces']];assert abs(module(s,'geom.solids').face_volume(faces))==pytest.approx(slab['volume'])
    s.history.undo();assert not list(s.document.doc.modelspace())and L.KEY not in s.document.doc.rootdict
    assert P.fingerprint(s.document.doc)==before
    s.history.redo();assert S.read(cmd.entity)['id']==rec['id']


@pytest.mark.parametrize('bad',[
 [(0,0),(4,4),(0,4),(4,0)],[(0,0),(1,0),(1,0)],[(0,0),(float('nan'),1),(1,0)]])
def test_invalid_outer_rejected_before_any_mutation(plugin,bad):
    s=Session(plugin);S=module(s,'slabs');P=module(s,'conversion_plan');before=P.fingerprint(s.document.doc)
    with pytest.raises(ValueError):S.apply_new(s.tool('MURO').ctx,bad)
    assert P.fingerprint(s.document.doc)==before


@pytest.mark.parametrize('holes',[
 [[(-1,1),(2,1),(2,2),(-1,2)]],[[(-3,-3),(-2,-3),(-2,-2),(-3,-2)]],
 [[(0,1),(1,1),(1,2),(0,2)]],[HOLE,HOLE],
 [HOLE,[(1.2,1.2),(1.8,1.2),(1.8,1.8),(1.2,1.8)]]])
def test_invalid_holes_rejected(plugin,holes):
    s=Session(plugin);S=module(s,'slabs')
    with pytest.raises(ValueError):S.region(OUTER,holes)


def test_forjado_tool_preview_hole_confirm_cancel_and_undo(plugin):
    s=Session(plugin);P=module(s,'conversion_plan');before=P.fingerprint(s.document.doc);t=s.tool('FORJADO')
    for p in OUTER:t.on_point(p)
    assert t.preview_segments((0,1));t.on_enter();assert t.phase=='confirm'and P.fingerprint(s.document.doc)==before
    assert t.on_option('Hueco')
    for p in HOLE:t.on_point(p)
    t.on_enter();t.on_enter();slabs=[e for e in s.document.doc.modelspace()if(s.meta(e)or{}).get('kind')=='slab']
    assert len(slabs)==1 and len(module(s,'slabs').read(slabs[0])['holes'])==1
    s.history.undo();assert P.fingerprint(s.document.doc)==before
    t=s.tool('FORJADO');t.on_point((0,0));t.on_cancel();assert not t.preview_segments((1,1))and P.fingerprint(s.document.doc)==before


def test_slab_level_move_save_reload_edit_and_hole_ids(plugin,tmp_path):
    from core.document import Document
    s=Session(plugin);S=module(s,'slabs');L,data,pa=catalog(s);L.apply(s.tool('MURO').ctx,data)
    data=L.load(s.document);data['active']=pa['id'];L.apply(s.tool('MURO').ctx,data)
    slab=S.apply_new(s.tool('MURO').ctx,OUTER,[HOLE],thickness=.2);before=S.read(slab.entity)
    data=L.load(s.document);data['levels'][1]['elevation']=4;L.apply(s.tool('MURO').ctx,data)
    assert S.read(slab.entity)['base']==pytest.approx(3.8)
    s.history.undo();assert S.read(slab.entity)['base']==pytest.approx(2.8)
    assert S.read(slab.entity)['hole_ids']==before['hole_ids']
    path=tmp_path/'sintetico.dxf';s.document.doc.saveas(path);doc=Document.load(path)
    el=next(e for e in doc.doc.modelspace()if(s.meta(e)or{}).get('kind')=='slab')
    assert S.read(el)['id']==before['id']and S.read(el)['hole_ids']==before['hole_ids']


def test_native_move_mirror_copy_slab_uses_actual_hatch_boundaries(plugin,tmp_path):
    from ezdxf.math import Matrix44
    s=Session(plugin);S=module(s,'slabs');slab=S.apply_new(s.tool('MURO').ctx,OUTER,[HOLE])
    slab.entity.transform(Matrix44.translate(10,20,0));rec=S.read(slab.entity)
    assert min(p[0]for p in rec['outer'])==pytest.approx(10)and min(p[1]for p in rec['holes'][0])==pytest.approx(21)
    slab.entity.transform(Matrix44.scale(-1,1,1));rec=S.read(slab.entity);assert S.region(rec['outer'],rec['holes'])['area']==pytest.approx(23)
    clone=slab.entity.copy();s.document.doc.modelspace().add_entity(clone)
    s.history.execute(module(s,'wall_network').RegenerateContoursCommand())
    assert s.meta(clone)['id']!=s.meta(slab.entity)['id']
    data=s.export(tmp_path);ids=[o['guid']for e in data['elements']for o in e.get('openings',[])]
    assert len(ids)==2 and len(set(ids))==2


def test_hole_tool_and_property_edit_keep_identity_and_undo(plugin):
    s=Session(plugin);S=module(s,'slabs');T=module(s,'transactions');F=module(s,'slab_tools')
    slab=S.apply_new(s.tool('MURO').ctx,OUTER);ident=S.read(slab.entity)['id']
    t=s.tool('HUECOFORJADO');t.ctx.services.pick_entity=lambda p:slab.entity;t.on_point((0,0))
    for p in HOLE:t.on_point(p)
    t.on_enter();assert len(S.read(slab.entity)['holes'])==1
    hole_id=S.read(slab.entity)['hole_ids'][0]
    change=F.edit_change(s.tool('MURO').ctx,slab.entity,{'name':'Losa editada','material':'Hormigón','thickness':.3,'top_offset':.1,'clear_holes':False})
    T.apply_architectural_change(s.tool('MURO').ctx,change);m=S.read(slab.entity)
    assert m['id']==ident and m['hole_ids']==[hole_id]and m['base']==pytest.approx(-.2)
    s.history.undo();assert S.read(slab.entity)['name']=='Forjado'
    s.history.undo();assert not S.read(slab.entity)['holes']


def test_invalid_saved_slab_reported_and_omitted_without_losing_walls(plugin,tmp_path):
    s=Session(plugin);w=wall(s);S=module(s,'slabs');slab=S.apply_new(s.tool('MURO').ctx,OUTER)
    m=s.meta(slab.entity);m['thickness']=-.2;module(s,'architectural')._xdata(s.document.doc.modelspace(),slab.entity,m)
    problems=module(s,'integrity').audit(s.document.doc);assert any(p['code']=='datos'and slab.entity.dxf.handle in p['handles']for p in problems)
    data=s.export(tmp_path);assert not any(e['ifc_class']=='IfcSlab'for e in data['elements'])and any(e['ifc_class']=='IfcWall'for e in data['elements'])


def test_tilted_hatch_is_rejected_instead_of_flattened(plugin):
    from ezdxf.math import Matrix44
    s=Session(plugin);S=module(s,'slabs');slab=S.apply_new(s.tool('MURO').ctx,OUTER)
    slab.entity.transform(Matrix44.x_rotate(.2))
    with pytest.raises(ValueError,match='inclinado'):S.read(slab.entity)


def test_level_catalog_validation_and_invalid_assignment_are_atomic(plugin):
    s=Session(plugin);L,data,pa=catalog(s);w=wall(s);P=module(s,'conversion_plan');before=P.fingerprint(s.document.doc)
    invalid=copy.deepcopy(data);invalid['levels'][1]['name']='PLANTA BAJA'
    with pytest.raises(ValueError):L.apply(s.tool('MURO').ctx,invalid)
    invalid=copy.deepcopy(data);invalid['levels'][1]['elevation']=float('nan')
    with pytest.raises(ValueError):L.apply(s.tool('MURO').ctx,invalid)
    with pytest.raises(ValueError):L.assign(s.tool('MURO').ctx,[w],'no-existe')
    assert P.fingerprint(s.document.doc)==before and L.KEY not in s.document.doc.rootdict


def test_native_level_and_slab_sheets_offscreen(plugin):
    from PySide6.QtWidgets import QApplication
    app=QApplication.instance()or QApplication([]);s=Session(plugin);L,data,pa=catalog(s)
    dlg,read=L.form(s.tool('MURO').ctx,data);dlg.show();app.processEvents();assert not dlg.grab().isNull()
    dlg._arq['table'].item(1,0).setText('Alta');assert read()['levels'][1]['name']=='Alta';dlg.close()
    F=module(s,'slab_tools');dlg,read=F.form(s.tool('MURO').ctx);dlg.show();app.processEvents();assert not dlg.grab().isNull()
    dlg._arq['thickness'].setValue(.35);assert read()['thickness']==pytest.approx(.35);dlg.close()


def test_native_plugin_context_selection_and_modal_assignment(plugin):
    from types import SimpleNamespace
    from core.plugins import PluginContext
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    app=QApplication.instance()or QApplication([]);s=Session(plugin);w=wall(s);L,data,pa=catalog(s)
    data['active']=pa['id'];L.apply(s.tool('MURO').ctx,data)
    host=SimpleNamespace(document=s.document,tools=SimpleNamespace(_execute=s.history.execute,selected_entities=lambda:[w]))
    ctx=PluginContext(host,s.out.append)
    QTimer.singleShot(0,lambda:app.activeModalWidget().accept())
    L.asignar(ctx)
    assert s.meta(w)['level_id']==pa['id']and s.meta(w)['base']==0
    s.history.undo();assert s.meta(w)['level_id']==data['levels'][0]['id']


def test_v3_contract_validates_level_identity_slab_and_legacy_v1(plugin,tmp_path):
    from tests.test_c1_d2 import bridge
    s=Session(plugin);X=bridge();legacy=s.export(tmp_path);assert legacy['version']==1;X.validate_contract(legacy)
    S=module(s,'slabs');S.apply_new(s.tool('MURO').ctx,OUTER,[HOLE]);data=s.export(tmp_path);X.validate_contract(data)
    broken=copy.deepcopy(data);broken['elements'][0]['level_id']='inexistente'
    with pytest.raises(ValueError):X.validate_contract(broken)
    broken=copy.deepcopy(data);broken['levels'][0]['guid']=broken['elements'][0]['guid']
    with pytest.raises(ValueError):X.validate_contract(broken)
    broken=copy.deepcopy(data);broken['active_level_id']='inexistente'
    with pytest.raises(ValueError):X.validate_contract(broken)


def test_migration_includes_columns_and_spaces_without_changing_ids_or_cotas(plugin):
    from tests.test_recintos import _vivienda,_spaces
    s=Session(plugin);_vivienda(s);s.tool('RECINTO').on_point((2,2));C=module(s,'columns');T=module(s,'transactions')
    T.apply_architectural_change(s.tool('MURO').ctx,C.column_command((2,2),{'shape':'rect','width':.3,'depth':.3,'height':2.7,'base':.15}),kind='column')
    L=module(s,'levels');before={s.meta(e)['id']:s.meta(e)for e in s.document.doc.modelspace()if(s.meta(e)or{}).get('kind')in L.KINDS}
    L.apply(s.tool('MURO').ctx,L.load(s.document))
    after={s.meta(e)['id']:s.meta(e)for e in s.document.doc.modelspace()if(s.meta(e)or{}).get('kind')in L.KINDS}
    assert set(before)==set(after)
    assert {'column','space','wall'}<={m['kind']for m in after.values()}
    assert all(after[k]['base']==m['base']and after[k]['level']=='Planta baja'for k,m in before.items())


def test_invalid_registry_and_unregistered_name_reported_before_export(plugin,tmp_path):
    s=Session(plugin);w=wall(s);L=module(s,'levels');L.apply(s.tool('MURO').ctx,L.load(s.document))
    m=s.meta(w);m['level']='Nombre ajeno';module(s,'architectural')._xdata(s.document.doc.modelspace(),w,m)
    assert any(p['code']=='nivel'for p in module(s,'integrity').audit(s.document.doc))
    assert not s.export(tmp_path)['elements']
    s.document.doc.rootdict.get(L.KEY).reset([(1,'{malformado')])
    data=s.export(tmp_path);assert not data['elements']and any('Catálogo'in p for p in data['issues'])


@pytest.mark.parametrize('angle',[0,37,90])
def test_concave_slab_rotated_with_hole_has_closed_volume(plugin,angle,tmp_path):
    from ezdxf.math import Matrix44
    s=Session(plugin);S=module(s,'slabs');outer=[(0,0),(6,0),(6,2),(3,2),(3,5),(0,5)]
    slab=S.apply_new(s.tool('MURO').ctx,outer,[HOLE],thickness=.3)
    slab.entity.transform(Matrix44.z_rotate(math.radians(angle)))
    data=s.export(tmp_path);el=next(e for e in data['elements']if e['ifc_class']=='IfcSlab')
    assert el['volume']==pytest.approx(20*.3)
    assert abs(module(s,'geom.solids').face_volume([(f['outer'],f['holes'])for f in el['faces']]))==pytest.approx(6.)


def test_native_scale_thickness_regeneration_and_undo(plugin):
    from core.actions import TransformCommand
    from ezdxf.math import Matrix44
    s=Session(plugin);S=module(s,'slabs');slab=S.apply_new(s.tool('MURO').ctx,OUTER,[HOLE])
    s.history.execute(TransformCommand('SCALE',[slab.entity],Matrix44.scale(2)))
    assert S.read(slab.entity)['thickness']==pytest.approx(.4)
    s.history.execute(module(s,'wall_network').RegenerateContoursCommand())
    assert S.read(slab.entity)['thickness']==pytest.approx(.4)
    s.history.undo();assert S.read(slab.entity)['thickness']==pytest.approx(.4)
    s.history.undo();assert S.read(slab.entity)['thickness']==pytest.approx(.2)
    assert S.region(S.read(slab.entity)['outer'],S.read(slab.entity)['holes'])['area']==pytest.approx(23)


def test_repeated_level_move_keeps_only_live_selection_group_reactors(plugin):
    s=Session(plugin);w=wall(s);L,data,pa=catalog(s);L.apply(s.tool('MURO').ctx,data)
    for z in (1,2,0):
        data=L.load(s.document);data['levels'][0]['elevation']=z;L.apply(s.tool('MURO').ctx,data)
        for e in s.document.doc.modelspace():
            for handle in e.get_reactors():
                target=s.document.doc.entitydb.get(handle)
                assert target is not None and target.is_alive
        s.history.undo();s.history.redo()


def test_forjado_rejects_nonmetre_drawing_before_migration(plugin):
    s=Session(plugin);s.document.doc.header['$INSUNITS']=4;L=module(s,'levels');S=module(s,'slabs')
    with pytest.raises(ValueError,match='metros'):S.apply_new(s.tool('MURO').ctx,OUTER)
    assert L.KEY not in s.document.doc.rootdict and not list(s.document.doc.modelspace())

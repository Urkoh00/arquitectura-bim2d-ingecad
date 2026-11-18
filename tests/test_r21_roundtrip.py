# SPDX-License-Identifier: GPL-3.0-or-later
import copy,json
import pytest
from tests.test_ingecad_integration import plugin
from tests.test_wall_tools import Session,draw
from tests.test_fichas import qt
from tests.test_r12_conversion import module


def fixture(plugin,kind='window',**extra):
 s=Session(plugin);A=module(s,'architectural_v10');T=module(s,'transactions')
 c=A.create_wall((0,0),(6,0),.3,3);ctx=s.tool('MURO').ctx;T.apply_architectural_change(ctx,c)
 o=A.create_opening(c.entity,1,1.2,.9 if kind=='window'else 0,1.1 if kind=='window'else 2.1,kind=kind,**extra);T.apply_architectural_change(ctx,o,kind='opening')
 return s,ctx,c.entity,o.entity


def test_window_roundtrip_and_one_undo(plugin):
 s,ctx,w,o=fixture(plugin);R=module(s,'roundtrip');M=module(s,'roundtrip_model');E=module(s,'exchange')
 before=E.build(s.document.doc);origin=before['roundtrip'];ident=s.meta(o)['id'];current,pending=M.propose(origin,ident,{'operation':'SLIDING'})
 assert not pending
 preview=M.preview_contract(before,current,ident)
 original=next(e for e in before['elements']if e['id']==ident);changed=next(e for e in preview['elements']if e['id']==ident)
 assert changed['faces']!=original['faces']
 data=M.changes(origin,current);assert not R.conflicts(s.document.doc,data)
 R.accept(ctx,data);assert s.meta(o)['operation']=='SLIDING'
 after=E.build(s.document.doc);actual=next(e for e in after['elements']if e['id']==ident)
 assert actual==changed and actual['guid']==original['guid']
 s.history.undo();assert E.build(s.document.doc)==before
 s.history.redo();assert E.build(s.document.doc)==after


def test_conflict_and_keep(plugin):
 s,ctx,w,o=fixture(plugin);R=module(s,'roundtrip');M=module(s,'roundtrip_model');A=module(s,'architectural_v10');T=module(s,'transactions')
 origin=R.snapshot(s.document.doc);ident=s.meta(w)['id'];current,pending=M.propose(origin,ident,{'thickness':.4});assert pending
 data=M.changes(origin,current);T.apply_architectural_change(ctx,A.edit_wall(w,height=3.2))
 with pytest.raises(ValueError,match='Conflictos'):R.accept(ctx,data)
 assert R.accept(ctx,data,{ident:'keep'})is None
 R.accept(ctx,data,{ident:'apply'});assert s.meta(w)['thickness']==.4 and s.meta(w)['height']==3.2


def test_wrong_source_and_invalid_fit_are_read_only(plugin):
 s,ctx,w,o=fixture(plugin);R=module(s,'roundtrip');M=module(s,'roundtrip_model');origin=R.snapshot(s.document.doc);ident=s.meta(o)['id']
 with pytest.raises(ValueError):M.propose(origin,ident,{'width':12})
 with pytest.raises(ValueError):M.propose(origin,ident,{'height':float('nan')})
 current,_=M.propose(origin,ident,{'operation':'SLIDING'});data=M.changes(origin,current);data['source_id']='otro'
 with pytest.raises(ValueError,match='origen'):R.accept(ctx,data)
 assert R.snapshot(s.document.doc)==origin


def test_cabinet_changes_with_same_geometry_code(plugin):
 s,ctx,w,o=fixture(plugin,'door',cabinet=True,niche_depth=.2,cabinet_mode='nicho',leaves=2,operation='SLIDING')
 R=module(s,'roundtrip');M=module(s,'roundtrip_model');E=module(s,'exchange');before=E.build(s.document.doc);ident=s.meta(o)['id']
 current,pending=M.propose(before['roundtrip'],ident,{'operation':'SWINGING'});assert not pending
 preview=M.preview_contract(before,current,ident);R.accept(ctx,M.changes(before['roundtrip'],current))
 assert next(e for e in preview['elements']if e['id']==ident)['faces']==next(e for e in E.build(s.document.doc)['elements']if e['id']==ident)['faces']


def test_bundle_is_exact_source():
 from pathlib import Path
 import hashlib
 root=Path(__file__).resolve().parents[1];folder=root/'ingetrazo_ext/arq_shared';manifest=json.loads((folder/'MANIFEST.json').read_text())
 for name,sha in manifest.items():
  assert hashlib.sha256((root/'arquitectura'/name).read_bytes()).hexdigest()==sha
  assert (root/'arquitectura'/name).read_bytes()==(folder/name).read_bytes()


def test_wall_thickness_recomputes_room_and_one_undo(plugin):
 from tests.test_revision_persistencia_y_escala import _building
 s=Session(plugin);_building(s,k=1);R=module(s,'roundtrip');M=module(s,'roundtrip_model');E=module(s,'exchange');before=E.build(s.document.doc)
 origin=before['roundtrip'];ident=next(i for i,r in origin['records'].items()if r['kind']=='wall');new,_=M.propose(origin,ident,{'thickness':.3})
 room=next(e for e in before['elements']if e['ifc_class']=='IfcSpace');R.accept(s.tool('MURO').ctx,M.changes(origin,new))
 after=E.build(s.document.doc);changed=next(e for e in after['elements']if e['id']==room['id'])
 assert changed['quantities']['NetFloorArea']!=room['quantities']['NetFloorArea']
 s.history.undo();assert E.build(s.document.doc)==before
 s.history.redo();assert E.build(s.document.doc)==after


def test_new_type_catalog_persists_and_is_available_in_existing_cad_sheet(plugin,qt,tmp_path):
 s,ctx,w,o=fixture(plugin);R=module(s,'roundtrip');M=module(s,'roundtrip_model');P=module(s,'parameters_arq');B=module(s,'bim_dialogs')
 origin=R.snapshot(s.document.doc);current=copy.deepcopy(origin);ident=s.meta(o)['id']
 values={'type_name':'CORREDERA NUEVA','operation':'SLIDING','width':1.2,'height':1.1,'sill':.9}
 current,_=M.propose(current,ident,values)
 current['catalog']['opening'].append({'name':'CORREDERA NUEVA','type':'window','cabinet':False,'values':values})
 R.accept(ctx,M.changes(origin,current))
 assert P.load_defaults(s.document)['opening_types'][-1]['name']=='CORREDERA NUEVA'
 dlg,read=B.carpentry_form(ctx,s.meta(o));selector=dlg._arq['catalog_choice'];selector.setCurrentIndex(selector.count()-1)
 assert read()['operation']=='SLIDING'and read()['type_name']=='CORREDERA NUEVA'
 path=tmp_path/'catalog.dxf';s.document.save_as(path)
 from core.document import Document
 assert P.load_defaults(Document.load(path))['opening_types']==P.load_defaults(s.document)['opening_types']


def test_atomic_rollback_when_live_regeneration_fails(plugin,monkeypatch):
 s,ctx,w,o=fixture(plugin);R=module(s,'roundtrip');M=module(s,'roundtrip_model');T=module(s,'transactions');origin=R.snapshot(s.document.doc);ident=s.meta(o)['id'];current,_=M.propose(origin,ident,{'operation':'SLIDING'})
 real=T.ArchitecturalRegeneration.do
 def fail_live(self,document):
  if document is s.document:raise ValueError('Fallo de regeneración simulado')
  return real(self,document)
 monkeypatch.setattr(T.ArchitecturalRegeneration,'do',fail_live)
 with pytest.raises(ValueError,match='simulado'):R.accept(ctx,M.changes(origin,current))
 assert R.snapshot(s.document.doc)==origin


def test_negative_profile_and_forbidden_geometry_fields_rejected(plugin):
 s,ctx,w,o=fixture(plugin);R=module(s,'roundtrip');M=module(s,'roundtrip_model');origin=R.snapshot(s.document.doc);ident=s.meta(o)['id']
 for values in ({'frame_width':-.05},{'leaves':100000},{'wall_id':'otra'},{'id':'otra'}):
  with pytest.raises(ValueError):M.propose(origin,ident,values)
 assert R.snapshot(s.document.doc)==origin


def test_catalog_only_change_is_one_undo(plugin):
 s,ctx,w,o=fixture(plugin);R=module(s,'roundtrip');M=module(s,'roundtrip_model');origin=R.snapshot(s.document.doc);new=copy.deepcopy(origin)
 new['catalog']['wall'].append({'name':'Tipo nuevo','layers':[[.2,'Ladrillo']], 'thickness':.2,'material':'Ladrillo','wall_category':'tabique'})
 data=M.changes(origin,new);assert not data['changes'];R.accept(ctx,data)
 assert any(t['name']=='Tipo nuevo'for t in R.snapshot(s.document.doc)['catalog']['wall'])
 s.history.undo();assert R.snapshot(s.document.doc)==origin


def test_same_thickness_wall_type_has_identical_preview_and_source_data(plugin):
 s,ctx,w,o=fixture(plugin);R=module(s,'roundtrip');M=module(s,'roundtrip_model');E=module(s,'exchange');before=E.build(s.document.doc);origin=before['roundtrip'];ident=s.meta(w)['id']
 values={'type_name':'DOS CAPAS','material':'Ladrillo','layers':[[.2,'Ladrillo'],[.1,'Aislante']]}
 current,pending=M.propose(origin,ident,values);assert not pending
 preview=M.preview_contract(before,current,ident);R.accept(ctx,M.changes(origin,current))
 assert next(e for e in preview['elements']if e['id']==ident)==next(e for e in E.build(s.document.doc)['elements']if e['id']==ident)


def test_conflict_dialog_shows_values_and_defaults_to_keep(plugin,qt,tmp_path,monkeypatch):
 from PySide6.QtWidgets import QDialog,QTableWidget,QMessageBox
 s,ctx,w,o=fixture(plugin);R=module(s,'roundtrip');M=module(s,'roundtrip_model');A=module(s,'architectural_v10');T=module(s,'transactions')
 origin=R.snapshot(s.document.doc);ident=s.meta(o)['id'];new,_=M.propose(origin,ident,{'operation':'SLIDING'});path=tmp_path/'proposal.arqcambios';path.write_text(json.dumps(M.changes(origin,new)))
 T.apply_architectural_change(ctx,A.edit_wall(w,height=3.2))
 def review(dialog):
  table=dialog.findChild(QTableWidget);assert table.columnCount()==4
  assert 'SIDEHUNG'in table.item(0,2).text()and 'SLIDING'in table.item(0,2).text()
  assert table.cellWidget(0,3).currentData()=='keep';table.cellWidget(0,3).setCurrentIndex(1)
  return QDialog.Accepted
 monkeypatch.setattr(QDialog,'exec',review)
 monkeypatch.setattr(QMessageBox,'warning',lambda *args:pytest.fail(str(args)))
 assert R.sincronizar_arq(ctx,str(path))is not None
 assert s.meta(o)['operation']=='SLIDING'and s.meta(w)['height']==3.2


def test_upper_storey_opening_validates_its_own_height_band(plugin):
 s,ctx,lower,o=fixture(plugin);A=module(s,'architectural_v10');T=module(s,'transactions');R=module(s,'roundtrip');M=module(s,'roundtrip_model')
 wall=A.create_wall((0,0),(6,0),.3,3,3);T.apply_architectural_change(ctx,wall)
 opening=A.create_opening(wall.entity,1,1.2,.9,1.1,kind='window');T.apply_architectural_change(ctx,opening,kind='opening')
 origin=R.snapshot(s.document.doc);ident=s.meta(opening.entity)['id'];new,pending=M.propose(origin,ident,{'operation':'SLIDING'})
 assert not pending;R.accept(ctx,M.changes(origin,new));assert s.meta(opening.entity)['operation']=='SLIDING'

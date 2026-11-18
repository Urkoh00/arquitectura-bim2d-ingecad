# SPDX-License-Identifier: GPL-3.0-or-later
"""Run in the official IngeTrazo interpreter, isolated from IngeCAD core."""
import copy,json,sys
from pathlib import Path
from types import SimpleNamespace
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'ingetrazo_ext'))
import arquitectura_bim as X
import _arq_edit as ED
import _arqbim_sync as SY
from core.history import History
from core.scene import Scene
from formats.igz import save_scene,load_into
from PySide6.QtWidgets import QApplication,QMainWindow,QDockWidget
appqt=QApplication.instance()or QApplication([])
source=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
data=X.read_contract(source);scene=Scene();incoming=X.build_scene(data)
command=SY.prepare(scene,incoming,data,'synthetic.arqbim',X.definition(data));h=History(scene);h.execute(command);assert not h.last_error
class App:
 def __init__(self):
  self.scene=scene;self.window=QMainWindow();self.viewport=SimpleNamespace(history=h,update=lambda:None,notify_scene_changed=lambda:None)
 def document_data(self,default=None):return copy.deepcopy(self.scene.plugin_data.get('arquitectura',default))
 def add_panel(self,title,widget):
  self.widget=widget;dock=QDockWidget(title,self.window);dock.setWidget(widget);self.window.addDockWidget(__import__('PySide6.QtCore',fromlist=['Qt']).Qt.RightDockWidgetArea,dock);return dock
 def add_menu_action(self,*args):pass
 def on_document_changed(self,fn):self.callback=fn
app=App();state=app.document_data()['models']['synthetic.arqbim']['editing'];records=state['current']['records']
window=next(i for i,r in records.items()if r.get('type')=='window');wall=records[window]['wall_id'];rootgroup=scene.groups[0]
group=next(g for g in rootgroup.children if g.ext['arquitectura']['source_id']==window)
scene.selection={group};widget=ED.setup(app,X);app.window.resize(700,900);app.window.show();appqt.processEvents();widget.grab().save(str(out/'panel_window.png'))
from PySide6.QtWidgets import QPushButton,QLineEdit
apply_button=next(b for b in widget.findChildren(QPushButton)if b.text()=='Aplicar propuesta')
steps=len(h.undo_stack);apply_button.click();assert len(h.undo_stack)==steps
from PySide6.QtWidgets import QFormLayout
form=next(f for f in widget.findChildren(QFormLayout)if any(f.itemAt(i,QFormLayout.LabelRole)and f.itemAt(i,QFormLayout.LabelRole).widget().text()=='Material del marco'for i in range(f.rowCount())))
row=next(i for i in range(form.rowCount())if form.itemAt(i,QFormLayout.LabelRole)and form.itemAt(i,QFormLayout.LabelRole).widget().text()=='Material del marco')
frame_entry=form.itemAt(row,QFormLayout.FieldRole).widget();assert frame_entry.isEnabled()
frame_entry.setText('PVC');apply_button.click();assert len(h.undo_stack)==steps+1
assert any(p['material']=='PVC'for p in group.ext['arquitectura']['parts'])
h.undo();app.callback();assert len(h.undo_stack)==steps
before=copy.deepcopy(scene.plugin_data);mesh=group.mesh;n=len(h.undo_stack)
ED.edit(app,'synthetic.arqbim',window,{'operation':'SLIDING'},X)
assert len(h.undo_stack)==n+1 and group.mesh is not mesh
assert group.ext['arquitectura']['params']['operation']=='SLIDING'
h.undo();assert group.mesh is mesh and scene.plugin_data==before
h.redo();assert group.mesh is not mesh
changes=ED.export_changes(app,'synthetic.arqbim',out/'window.arqcambios');assert changes['changes'][0]['id']==window
state=app.document_data()['models']['synthetic.arqbim']['editing'];X.check_scene(X.build_scene(state['contract']),state['contract'])
# Thickness proposal changes no mesh until the source recomputes joins/rooms.
wallgroup=next(g for g in rootgroup.children if g.ext['arquitectura']['source_id']==wall);oldmesh=wallgroup.mesh
ED.edit(app,'synthetic.arqbim',wall,{'thickness':.4},X)
assert wallgroup.mesh is oldmesh and wallgroup.ext['arquitectura_pending']
state=app.document_data()['models']['synthetic.arqbim']['editing'];assert wall in state['pending']
ED.export_changes(app,'synthetic.arqbim',out/'all.arqcambios')
scene.selection={wallgroup};app.callback();appqt.processEvents();widget.grab().save(str(out/'panel_pending.png'))
# IGZ serialises origin, changes, pending status and native geometry together.
path=out/'pending.igz';save_scene(scene,path);restored=Scene();load_into(restored,path)
assert restored.plugin_data==scene.plugin_data
cab=next((i for i,r in records.items()if r.get('cabinet')),None)
if cab:
 ED.edit(app,'synthetic.arqbim',cab,{'operation':'SWINGING'},X)
 ED.export_changes(app,'synthetic.arqbim',out/'all.arqcambios')
print(json.dumps({'host':sys.argv[3],'window_undo_redo':True,'panel_apply_material':True,'panel_noop':True,'wall_pending':True,'igz_persistence':True,'cabinet':bool(cab),'commands':len(h.undo_stack)},indent=2))
app.window.close()

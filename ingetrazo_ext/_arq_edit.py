# SPDX-License-Identifier: GPL-3.0-or-later
"""Extension-owned property panel and proposals; host source remains untouched."""
from __future__ import annotations
import copy,importlib.util,json,sys
from pathlib import Path


def shared():
    name='_arquitectura_shared'
    if name not in sys.modules:
        p=Path(__file__).with_name('arq_shared')
        spec=importlib.util.spec_from_file_location(name,p/'__init__.py',submodule_search_locations=[str(p)])
        module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return __import__(name+'.roundtrip_model',fromlist=['propose'])


def initialise(data):
    origin=copy.deepcopy(data.get('roundtrip'))
    if not origin:return None
    return {'origin':origin,'current':copy.deepcopy(origin),'contract':copy.deepcopy(data),'pending':[]}


def walk(groups):
    for g in groups:
        yield g
        yield from walk(g.children or [])


def selected(app):
    # Build an ownership index only when the document changes, not every tick.
    stamp=(id(app.scene),getattr(app.scene,'version',0))
    cached=getattr(app,'_arq_selection_index',None)
    if cached is None or cached[0]!=stamp:
        index={}
        for root in app.scene.groups:
            key=((root.ext or {}).get('arquitectura_import')or{}).get('model_key')
            if not key:continue
            for g in walk([root]):
                rec=(g.ext or {}).get('arquitectura')or{}
                ident=(rec.get('params')or{}).get('cabinet_id')or rec.get('source_id')
                if ident:index[g]=(key,ident)
        cached=(stamp,index);app._arq_selection_index=cached
    chosen={cached[1][g]for g in app.scene.selection if g in cached[1]}
    return next(iter(chosen))if len(chosen)==1 else (None,None)


def edit(app,key,ident,values,api,catalog=None):
    M=shared();before=app.document_data({});stored=copy.deepcopy(before)
    model=stored['models'][key];state=model.get('editing')
    if state is None:raise ValueError('Reimporte el modelo con EXPORTARBIM actualizado para editarlo')
    current,pending=M.propose(state['current'],ident,values)
    if catalog is not None:current['catalog']=copy.deepcopy(catalog)
    if current==state['current']:return None
    pending=pending or ident in state['pending']
    contract=state['contract'] if pending else M.preview_contract(state['contract'],current,ident)
    replacements={};materials={}
    if not pending:
        scene=api.build_scene(contract,offset=stored.get('survey_offset'))
        replacements={g.ext['arquitectura']['source_id']:g for g in scene.groups if g.ext['arquitectura']['source_id']in(ident,ident+'-cuerpo')}
        materials=scene.materials
    state['current']=current;state['contract']=contract
    if pending and ident not in state['pending']:state['pending'].append(ident)
    from core.history import Command
    class Edit(Command):
        def do(self,scene):
            self.before=copy.deepcopy(scene.plugin_data);self.groups=[];self.materials=dict(scene.materials)
            try:
                roots=[g for g in scene.groups if((g.ext or {}).get('arquitectura_import')or{}).get('model_key')==key]
                if len(roots)!=1:raise ValueError('Contenedor de origen ausente o duplicado')
                for g in walk(roots):
                    source=((g.ext or {}).get('arquitectura')or{}).get('source_id')
                    if source in replacements or source==ident or (current['records'][ident]['kind']=='opening'and source==current['records'][ident]['wall_id']):
                        self.groups.append((g,g.mesh,copy.deepcopy(g.ext),g.ifc))
                        if source in replacements:
                            new=replacements[source];g.mesh=new.mesh;g.ifc=new.ifc;g.ext={**g.ext,**new.ext}
                        if pending:g.ext={**g.ext,'arquitectura_pending':True}
                scene.materials.update(materials);scene.plugin_data['arquitectura']=copy.deepcopy(stored);scene.version+=1
            except Exception:
                self.undo(scene);raise
        def undo(self,scene):
            for g,mesh,ext,ifc in self.groups:g.mesh,g.ext,g.ifc=mesh,ext,ifc
            scene.plugin_data=copy.deepcopy(self.before);scene.materials=dict(self.materials);scene.version+=1
    command=Edit();app.viewport.history.execute(command)
    if app.viewport.history.last_error:raise ValueError(app.viewport.history.last_error)
    notify=getattr(app.viewport,'notify_scene_changed',None)
    if callable(notify):notify()
    app.viewport.update();return command


def export_changes(app,key,path):
    state=app.document_data({})['models'][key]['editing']
    payload=shared().changes(state['origin'],state['current']);shared().validate_changes(payload)
    path=Path(path);tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(payload,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8');tmp.replace(path)
    return payload


def setup(app,api):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QWidget,QVBoxLayout,QLabel,QComboBox,QFormLayout,QDoubleSpinBox,QSpinBox,QLineEdit,QPushButton,QFileDialog,QMessageBox,QInputDialog,QScrollArea
    widget=QWidget();box=QVBoxLayout(widget);status=QLabel('Seleccione un elemento de Arquitectura.');status.setWordWrap(True);box.addWidget(status)
    element=QComboBox();box.addWidget(element);typ=QComboBox();box.addWidget(typ)
    form=QFormLayout();box.addLayout(form);fields={};active=[None,None];last=[None]
    for name,label in [('width','Ancho (m)'),('height','Alto (m)'),('sill','Antepecho (m)'),('thickness','Espesor (m)'),('frame_width','Perfil (m)'),('frame_depth','Fondo de marco (m)'),('leaves','Hojas')]:
        spin=QSpinBox() if name=='leaves'else QDoubleSpinBox()
        if name!='leaves':spin.setDecimals(4)
        spin.setRange(0,128 if name=='leaves'else 10000);form.addRow(label,spin);fields[name]=spin
    operation=QComboBox();form.addRow('Apertura',operation);material=QLineEdit();form.addRow('Material',material)
    materials={}
    for k,label in [('frame_material','Material del marco'),('leaf_material','Material de las hojas'),('glass_material','Material del vidrio'),('body_material','Material del cuerpo')]:
        entry=QLineEdit();materials[k]=entry;form.addRow(label,entry)
    apply=QPushButton('Aplicar propuesta');save_type=QPushButton('Guardar como tipo…');export=QPushButton('Exportar cambios a IngeCAD…')
    for b in(apply,save_type,export):box.addWidget(b)
    box.addStretch(1)
    def state():
        key,ident=active
        if not key:return None
        return (app.document_data({}).get('models',{}).get(key)or{}).get('editing')
    def read():
        st=state();r=st['current']['records'][active[1]]
        allowed=shared().WALL_FIELDS if r['kind']=='wall'else shared().OPEN_FIELDS
        vals={k:spin.value()for k,spin in fields.items()if k in allowed and k in r and spin.isEnabled() and spin.value()!=spin.property('original')}
        if 'leaves'in vals:vals['leaves']=int(vals['leaves'])
        if material.text()!=material.property('original'):vals['material']=material.text()
        vals.update({k:e.text()for k,e in materials.items()if e.isEnabled() and e.text()!=e.property('original')})
        if operation.currentData()is not None and operation.currentData()!=r.get('operation'):vals['operation']=operation.currentData()
        return vals
    def populate(*_):
        st=state();ident=element.currentData()
        if not st or ident not in st['current']['records']:return
        active[1]=ident;r=st['current']['records'][ident];kind=r['kind']
        status.setText(('Armario'if r.get('cabinet')else r.get('type','Muro'))+' · '+('IfcWall'if kind=='wall'else shared().OP.IFC[r['type']])+' · '+ident+ ('\nPendiente de sincronizar en IngeCAD: se actualizarán planta, encuentros y recintos.'if ident in st['pending']else ''))
        typ.blockSignals(True);typ.clear();typ.addItem('Tipo actual: '+(r.get('type_name')or 'sin nombre'),None)
        for t in st['current']['catalog']['wall'if kind=='wall'else 'opening']:
            if kind=='wall'or(t.get('type')==r.get('type')and bool(t.get('cabinet'))==bool(r.get('cabinet'))):typ.addItem(t['name'],t)
        typ.blockSignals(False)
        for k,spin in fields.items():spin.setEnabled(k in r and (k!='height'or r.get('height_constraint','fixed')=='fixed'));spin.setValue(float(r.get(k)or 0));spin.setProperty('original',spin.value())
        material.setText(r.get('material',''));material.setProperty('original',material.text());operation.clear()
        for k,e in materials.items():
            e.setEnabled(kind=='opening' and r.get('type')!='gap' and (k!='body_material'or bool(r.get('cabinet'))))
            role=k.removesuffix('_material');value=(r.get(k)or 'Madera')if role=='body'else shared().OP.part_material(r,role)
            e.setText(value);e.setProperty('original',e.text())
        if kind=='opening':
            M=shared()
            for op in M.OP.OPERATIONS[r['type']]:operation.addItem(M.OP.OPERATION_NAMES.get(op,op).capitalize(),op)
            operation.setCurrentIndex(max(0,operation.findData(r.get('operation'))))
    def refresh():
        key,ident=selected(app);token=(id(app.scene),key,ident,getattr(app.scene,'version',0))
        if token==last[0]:return
        last[0]=token;active[:]=[key,ident];st=state();element.blockSignals(True);element.clear()
        valid=bool(st and ident in st['current']['records']and st['current']['records'][ident]['kind']in('wall','opening'))
        for b in(apply,save_type,export):b.setEnabled(valid)
        if valid:
            r=st['current']['records'][ident];choices=[ident]
            if r['kind']=='wall':choices += [i for i,v in st['current']['records'].items()if v.get('wall_id')==ident]
            for i in choices:
                v=st['current']['records'][i];element.addItem(v.get('name')or v.get('type')or 'Muro',i)
        else:status.setText('Seleccione un muro o carpintería importados con la extensión actualizada.')
        element.blockSignals(False)
        if valid:populate()
    def choose(*_):
        t=typ.currentData()
        if not t:return
        vals={k:t[k]for k in('thickness','material')if k in t}if 'layers'in t else t['values']
        for k,v in vals.items():
            if k in fields:fields[k].setValue(float(v))
        material.setText(vals.get('material',material.text()))
        for k,e in materials.items():
            if k in vals:e.setText(vals[k])
        if vals.get('operation'):operation.setCurrentIndex(operation.findData(vals['operation']))
    def commit(new_type=False):
        try:
            vals=read();t=typ.currentData();st=state();r=st['current']['records'][active[1]];cat=None
            if t:
                vals['type_name']=t['name']
                if r['kind']=='wall':vals.update(layers=t['layers'],wall_category=t.get('wall_category','fachada'))
                else:vals={**t['values'],**vals}
            if new_type:
                name,ok=QInputDialog.getText(widget,'Guardar tipo','Nombre del tipo')
                if not ok or not name.strip():return
                vals['type_name']=name.strip();candidate,_=shared().propose(st['current'],active[1],vals);r=candidate['records'][active[1]];cat=copy.deepcopy(st['current']['catalog']);group='wall'if r['kind']=='wall'else 'opening'
                entry={'name':name.strip(),'layers':r.get('layers')or [[vals.get('thickness',r['thickness']),vals.get('material',r.get('material',''))]],'thickness':vals.get('thickness',r['thickness']),'material':vals.get('material',r.get('material',''))}if group=='wall'else {'name':name.strip(),'type':r['type'],'cabinet':bool(r.get('cabinet')),'values':{k:v for k,v in {**r,**vals}.items()if k in shared().OPEN_FIELDS}}
                cat[group]=[v for v in cat[group]if v['name']!=entry['name']]+[entry]
            edit(app,*active,vals,api,catalog=cat);last[0]=None;refresh()
        except Exception as exc:QMessageBox.warning(widget,'Propuesta de Arquitectura',str(exc))
    def export_file():
        try:
            path,_=QFileDialog.getSaveFileName(widget,'Exportar cambios a IngeCAD','','Cambios (*.arqcambios)')
            if path:export_changes(app,active[0],str(Path(path).with_suffix('.arqcambios')))
        except Exception as exc:QMessageBox.warning(widget,'Exportar cambios',str(exc))
    element.currentIndexChanged.connect(populate);typ.currentIndexChanged.connect(choose);apply.clicked.connect(lambda:commit());save_type.clicked.connect(lambda:commit(True));export.clicked.connect(export_file)
    scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(widget);scroll.setMinimumWidth(280)
    dock=app.add_panel('Propiedades de Arquitectura',scroll)
    app.on_document_changed(refresh)
    # Public API has no selection subscription in 0.6.1/0.6.2: a parented
    # timer reads public scene.selection; stops with the extension widget.
    timer=QTimer(widget);timer.setInterval(250);timer.timeout.connect(lambda:refresh()if widget.isVisible()else None);timer.start()
    app.add_menu_action('Exportar cambios a IngeCAD…',export_file)
    refresh();return widget

# SPDX-License-Identifier: GPL-3.0-or-later
"""Document-owned BIM levels, native commands and stable references."""
from __future__ import annotations
import copy,json,math,uuid
from core.commands import Command
from .architectural import metadata

KEY='ARQ_BIM_LEVELS'
KINDS=('wall','column','space','slab')


def default_catalog(drawing):
    seed=str(drawing.header.get('$FINGERPRINTGUID',''))
    ident=uuid.uuid5(uuid.NAMESPACE_URL,'arqbim:'+seed+':ground').hex
    return {'schema':1,'active':ident,'levels':[{'id':ident,'name':'Planta baja','elevation':0.}]}


def validate(data):
    data=copy.deepcopy(data)
    if not isinstance(data,dict)or type(data.get('schema'))is not int or data['schema']!=1 or not isinstance(data.get('levels'),list)or not data['levels']:raise ValueError('Catálogo de niveles no válido')
    ids=set();names=set()
    for v in data['levels']:
        if not isinstance(v,dict)or not isinstance(v.get('name'),str):raise ValueError('Registro de nivel no válido')
        ident=v.get('id');name=str(v.get('name','')).strip();z=float(v.get('elevation',float('nan')))
        if not isinstance(ident,str)or not ident or ident in ids or not name or name.casefold()in names or not math.isfinite(z):raise ValueError('Nivel duplicado, sin nombre/ID o cota no finita')
        ids.add(ident);names.add(name.casefold());v.update(name=name,elevation=z)
    if data.get('active')not in ids:raise ValueError('Nivel activo inexistente')
    return data


def load(drawing):
    drawing=getattr(drawing,'doc',drawing);record=drawing.rootdict.get(KEY)
    return validate(json.loads(''.join(str(t.value)for t in record.tags if t.code==1)))if record else default_catalog(drawing)


def bind(drawing,record):
    """Optional linkage; reading an old document never writes a registry."""
    if record.get('kind')not in KINDS or KEY not in drawing.rootdict:return record
    data=load(drawing);byid={v['id']:v for v in data['levels']}
    level=byid.get(record.get('level_id'))
    if level is None:level=next((v for v in data['levels']if v['name']==record.get('level')),None)
    if level is None and not record.get('level'):level=byid[data['active']]
    if level:
        record={**record,'level_id':level['id'],'level':level['name'],
                'level_offset':float(record.get('base',0))-level['elevation']}
    return record


class StoreCatalog(Command):
    name='ARQ CATÁLOGO DE NIVELES'
    def __init__(self,data):self.data=validate(data);self.before=None;self.first=True
    def do(self,document):
        d=document.doc;r=d.rootdict.get(KEY)
        if self.first:self.before=list(r.tags)if r else None;self.first=False
        if r is None:r=d.rootdict.add_xrecord(KEY)
        text=json.dumps(self.data,ensure_ascii=True,separators=(',',':'))
        r.reset([(1,text[i:i+240])for i in range(0,len(text),240)]);document.dirty=True
    def undo(self,document):
        d=document.doc;r=d.rootdict.get(KEY)
        if self.before is None:
            if r is not None:d.rootdict.discard(KEY);d.entitydb.delete_entity(r)
        else:
            if r is None:r=d.rootdict.add_xrecord(KEY)
            r.reset(self.before)
        document.dirty=True


def catalog_steps(document,data):
    from .architectural_v10 import EditArchitecturalCommand
    from .parameters_arq import load_defaults,SetArchitecturalDefaults
    data=validate(data);old=load(document.doc);oldids={v['id']:v for v in old['levels']};newids={v['id']:v for v in data['levels']}
    ground=next((v for v in data['levels']if v['name']=='Planta baja'),None)
    edits=[]
    for e in document.doc.modelspace():
        m=metadata(e)or{}
        if m.get('kind')not in KINDS:continue
        if m['kind']=='slab':
            from .slabs import read
            m=read(e)
        else:
            from .frame import reconcile
            m=reconcile(e,m)
        new=copy.deepcopy(m);ident=m.get('level_id')
        if ident:
            if ident not in oldids or ident not in newids:raise ValueError('No se puede eliminar un nivel con elementos asociados')
            level=newids[ident];offset=float(m.get('base',0))-oldids[ident]['elevation']
            new.update(base=level['elevation']+offset,level_offset=offset)
        else:
            if ground is None:raise ValueError('La migración inicial necesita Planta baja')
            level=ground;new['level_offset']=float(m.get('base',0))-level['elevation']
            if m.get('level')and m['level']!=level['name']:new.setdefault('legacy_level',m['level'])
        new.update(level_id=level['id'],level=level['name'])
        if new['kind']=='wall':
            from .wall_constraints import resolve,validate_openings
            new=resolve(new,data);validate_openings(document.doc,new)
        if new!=m:
            if m['kind']=='slab':
                from .slabs import read,EditSlab
                edits.append(EditSlab(e,new))
            else:edits.append(EditArchitecturalCommand(e,new))
    active=newids[data['active']];defaults=load_defaults(document)
    for kind in ('wall','column'):defaults[kind].update(level=active['name'],base=active['elevation'])
    return [StoreCatalog(data),*edits,SetArchitecturalDefaults(defaults)]


def apply(ctx,data):
    from .compat import require_document
    from .transactions import SafeArchitecturalCommand,apply_architectural_change
    document=require_document(ctx)
    data=copy.deepcopy(data);old_catalog=load(document);was_managed=old_catalog.get('layer_managed',False);data['layer_managed']=True
    levels_changed={v['id']for v in old_catalog['levels']}!={v['id']for v in data['levels']}
    from .level_layers import RouteLevels
    steps=[*catalog_steps(document,data),RouteLevels()];change=SafeArchitecturalCommand('ARQ niveles y migración',steps)
    def base_changed(command):
        before=getattr(command,'old_record',getattr(command,'before',None))
        after=getattr(command,'new_record',getattr(command,'after',None))
        return isinstance(before,dict)and isinstance(after,dict)and (float(before.get('base',0))!=float(after.get('base',0))or float(before.get('height',0))!=float(after.get('height',0)))
    moved=any(base_changed(c)for c in steps)
    if moved or levels_changed:apply_architectural_change(ctx,change)
    else:ctx.execute(change)


def form(ctx,data):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QTableWidget,QTableWidgetItem,QDoubleSpinBox,QComboBox,QPushButton,QHBoxLayout,QMessageBox
    from .bim_dialogs import _dialog
    dlg,layout,buttons=_dialog(ctx,'Arquitectura — Niveles',
        'Al aceptar se vinculan los elementos antiguos a Planta baja sin moverlos. Cambiar una cota desplaza solo sus elementos asociados. El nivel activo configura los nuevos muros y pilares.')
    table=QTableWidget(0,2);table.setHorizontalHeaderLabels(['Nombre','Cota nominal (m)']);layout.addWidget(table)
    active=QComboBox();layout.addWidget(active)
    def refresh():
        current=active.currentData()or data['active'];active.clear()
        for i in range(table.rowCount()):active.addItem(table.item(i,0).text(),table.item(i,0).data(Qt.UserRole))
        active.setCurrentIndex(max(0,active.findData(current)))
    def row(v):
        i=table.rowCount();table.insertRow(i);item=QTableWidgetItem(v['name']);item.setData(Qt.UserRole,v['id']);table.setItem(i,0,item)
        z=QDoubleSpinBox();z.setRange(-1e6,1e6);z.setDecimals(4);z.setValue(v['elevation']);table.setCellWidget(i,1,z)
    for v in data['levels']:row(v)
    refresh();table.itemChanged.connect(lambda *_:refresh())
    toolbar=QHBoxLayout();add=QPushButton('Añadir nivel');delete=QPushButton('Quitar nivel');toolbar.addWidget(add);toolbar.addWidget(delete);layout.addLayout(toolbar)
    def add_row():
        z=table.cellWidget(table.rowCount()-1,1).value()+3 if table.rowCount()else 0
        row({'id':uuid.uuid4().hex,'name':f'Nivel {table.rowCount()}','elevation':z});refresh()
    def remove():
        if table.currentRow()>=0:table.removeRow(table.currentRow());refresh()
    add.clicked.connect(add_row);delete.clicked.connect(remove)
    def read():return validate({'schema':1,'active':active.currentData(),'levels':[{'id':table.item(i,0).data(Qt.UserRole),'name':table.item(i,0).text(),'elevation':table.cellWidget(i,1).value()}for i in range(table.rowCount())]})
    def accept():
        try:read()
        except ValueError as exc:QMessageBox.warning(dlg,'Niveles',str(exc));return
        dlg.accept()
    buttons.accepted.disconnect();buttons.accepted.connect(accept);layout.addWidget(buttons)
    dlg._arq={'table':table,'active':active,'add':add,'remove':delete};dlg.resize(650,480)
    return dlg,read


def niveles(ctx,*args):
    from .level_layers import install_toolbar
    install_toolbar(ctx)
    from .compat import require_document
    document=require_document(ctx)
    if args and str(args[0]).upper()=='ESTADO':
        from .level_layers import set_state
        if len(args)!=4:raise ValueError('NIVELES ESTADO id on|frozen|locked 0|1')
        set_state(ctx,str(args[1]),str(args[2]).lower(),str(args[3])=='1');return
    if args and str(args[0]).upper()=='MIGRAR':apply(ctx,load(document));return
    dlg,read=form(ctx,load(document))
    if dlg.exec()==1:apply(ctx,read())


def assign(ctx,entities,level_id,keep_absolute=True):
    from .compat import require_document
    from .architectural_v10 import EditArchitecturalCommand
    from .transactions import SafeArchitecturalCommand,apply_architectural_change
    doc=require_document(ctx);data=load(doc);target=next((v for v in data['levels']if v['id']==level_id),None)
    if target is None:raise ValueError('Nivel de destino inexistente')
    changes=[]
    for e in entities:
        m=metadata(e)or{}
        if m.get('kind')not in KINDS:continue
        if m['kind']=='slab':
            from .slabs import read,EditSlab
            m=read(e)
        else:
            from .frame import reconcile
            m=reconcile(e,m)
        base=float(m.get('base',0))if keep_absolute else target['elevation']-(m['thickness']if m['kind']=='slab'else 0.)
        new={**m,'base':base,'level_id':target['id'],'level':target['name'],'level_offset':base-target['elevation']}
        if m['kind']=='wall' and m.get('height_constraint')=='level':
            from .wall_constraints import resolve,validate_openings
            new['base_offset']=base-target['elevation'];new=resolve(new,data);validate_openings(doc.doc,new)
        changes.append(EditSlab(e,new)if m['kind']=='slab'else EditArchitecturalCommand(e,new))
    if not changes:raise ValueError('Seleccione fuentes BIM de muros, pilares, recintos o forjados')
    apply_architectural_change(ctx,SafeArchitecturalCommand('ARQ asignar nivel',changes))


def asignar(ctx,*args):
    from .compat import require_document
    from .bim_dialogs import _dialog
    from PySide6.QtWidgets import QComboBox,QCheckBox
    data=load(require_document(ctx));selection=getattr(ctx,'selection',None)
    if callable(selection):selection=selection()
    if selection is None:
        tools=getattr(getattr(ctx,'host',None),'tools',None)
        selection=list(tools.selected_entities())if tools else[]
    dlg,layout,buttons=_dialog(ctx,'Arquitectura — Asignar nivel','Seleccione fuentes BIM antes de ejecutar la orden. Los huecos siguen a su muro anfitrión.')
    box=QComboBox()
    for v in data['levels']:box.addItem(v['name'],v['id'])
    box.setCurrentIndex(max(0,box.findData(data['active'])));layout.addWidget(box)
    keep=QCheckBox('Conservar cota absoluta (desactivado: alinear la base/cara superior al nivel)');keep.setChecked(True);layout.addWidget(keep);layout.addWidget(buttons)
    if dlg.exec()==1:assign(ctx,selection,box.currentData(),keep.isChecked())

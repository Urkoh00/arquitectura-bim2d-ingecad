# SPDX-License-Identifier: GPL-3.0-or-later
"""Native PySide6 BIM property sheets. No custom theme: inherit IngeCAD's Qt palette.

Imports are intentionally delayed: CLI/headless tools keep working without Qt.
"""
from __future__ import annotations


def _parent(ctx):
    services = getattr(ctx, 'services', None)
    parent = getattr(services, 'window', None)
    return parent if parent is not None else None


def _widgets():
    from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QDoubleSpinBox,
       QFormLayout, QGroupBox, QVBoxLayout, QComboBox, QLineEdit, QLabel)
    return (QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
            QGroupBox, QVBoxLayout, QComboBox, QLineEdit, QLabel)


def _spin(value, *, positive=False):
    _,_,QDoubleSpinBox,*_ = _widgets()
    w = QDoubleSpinBox()
    w.setRange(0.001 if positive else -100000., 100000.)
    w.setDecimals(4)
    w.setSingleStep(0.05)
    w.setSuffix(' m')
    w.setValue(float(value))
    return w


def _choice(items, current):
    QComboBox=_widgets()[6]
    widget=QComboBox()
    for label, data in items: widget.addItem(label,data)
    pos=widget.findData(current)
    if pos>=0:widget.setCurrentIndex(pos)
    return widget


def _dialog(ctx, title, help_text):
    QDialog,QDialogButtonBox,_,_,_,QVBoxLayout,_,_,QLabel=_widgets()
    dlg=QDialog(_parent(ctx))
    dlg.setWindowTitle(title)
    dlg.setMinimumWidth(405)
    layout=QVBoxLayout(dlg)
    text=QLabel(help_text)
    text.setWordWrap(True)
    layout.addWidget(text)
    buttons=QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel,dlg)
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    return dlg,layout,buttons


def wall_properties(ctx, record=None):
    """Return validated parameters, or None on Cancel; does not mutate the drawing."""
    QDialog,_,_,QFormLayout,QGroupBox,_,_,QLineEdit,_=_widgets()
    d=record or {}
    dlg,layout,buttons=_dialog(ctx,'Arquitectura — Muro',
        'Propiedades del elemento arquitectónico 2D. Los datos se conservarán en el DXF y se prepararán para IGZ.')
    group=QGroupBox('Geometría y colocación',dlg)
    form=QFormLayout(group)
    thickness=_spin(d.get('thickness',0.15),positive=True)
    height=_spin(d.get('height',2.70),positive=True)
    base=_spin(d.get('base',0.0))
    reference=_choice([('Eje','eje'),('Cara izquierda','izquierda'),('Cara derecha','derecha')],d.get('reference','eje'))
    for label,widget in [('Espesor:',thickness),('Altura:',height),('Cota base:',base),('Referencia de dibujo:',reference)]:form.addRow(label,widget)
    layout.addWidget(group)
    group2=QGroupBox('Identificación BIM',dlg)
    frm2=QFormLayout(group2)
    name=QLineEdit(str(d.get('name','Muro')))
    type_name=QLineEdit(str(d.get('type_name','Muro genérico')))
    material=QLineEdit(str(d.get('material','Sin definir')))
    level=QLineEdit(str(d.get('level','Planta baja')))
    frm2.addRow('Nombre:',name);frm2.addRow('Tipo:',type_name)
    frm2.addRow('Material principal:',material);frm2.addRow('Nivel:',level)
    frm2.addRow('Clase IFC:',QLineEdit('IfcWall'))
    frm2.itemAt(frm2.count()-1).widget().setReadOnly(True)
    layout.addWidget(group2);layout.addWidget(buttons)
    if dlg.exec()!=QDialog.Accepted:return None
    return {'thickness':thickness.value(),'height':height.value(),'base':base.value(),
            'reference':reference.currentData(),'name':name.text().strip() or 'Muro',
            'type_name':type_name.text().strip() or 'Muro genérico',
            'material':material.text().strip(),'level':level.text().strip(),
            'ifc_class':'IfcWall'}


def opening_properties(ctx,kind, record=None, wall_length=None, wall_height=None):
    QDialog,_,_,QFormLayout,QGroupBox,_,_,QLineEdit,_=_widgets()
    d=record or {};door=kind in ('puerta','door')
    label='Puerta' if door else 'Ventana'
    dlg,layout,buttons=_dialog(ctx,'Arquitectura — '+label,
       'La carpintería queda vinculada al muro seleccionado. Posición y dimensiones en metros.')
    section=QGroupBox('Geometría del hueco',dlg)
    form=QFormLayout(section)
    offset=_spin(d.get('offset',0.50))
    width=_spin(d.get('width',0.90 if door else 1.20),positive=True)
    sill=_spin(d.get('sill',0.0 if door else 1.00))
    ht=_spin(d.get('height',2.10 if door else 1.20),positive=True)
    for caption,widget in [('Distancia desde inicio:',offset),('Anchura:',width),('Antepecho:',sill),('Altura:',ht)]:form.addRow(caption,widget)
    layout.addWidget(section)
    identity=QGroupBox('Identificación BIM',dlg)
    form2=QFormLayout(identity)
    name=QLineEdit(str(d.get('name',label)))
    typ=QLineEdit(str(d.get('type_name','Carpintería genérica')))
    material=QLineEdit(str(d.get('material','Sin definir')))
    form2.addRow('Nombre:',name);form2.addRow('Tipo:',typ)
    form2.addRow('Material:',material)
    if door:
        operation=_choice([('Batiente','SWINGING'),('Corredera','SLIDING'),('Sin definir','NOTDEFINED')],d.get('operation','NOTDEFINED'))
    else:
        operation=_choice([('Abatible','SIDEHUNG'),('Corredera','SLIDING'),('Fija','FIXED'),('Sin definir','NOTDEFINED')],d.get('operation','NOTDEFINED'))
    form2.addRow('Apertura:',operation)
    form2.addRow('Clase IFC:',QLineEdit('IfcDoor' if door else 'IfcWindow'))
    form2.itemAt(form2.count()-1).widget().setReadOnly(True)
    layout.addWidget(identity);layout.addWidget(buttons)
    while dlg.exec()==QDialog.Accepted:
        vals={'offset':offset.value(),'width':width.value(),'sill':sill.value(),'height':ht.value(),
              'name':name.text().strip() or label,'type_name':typ.text().strip(),
              'material':material.text().strip(),'operation':operation.currentData(),
              'ifc_class':'IfcDoor' if door else 'IfcWindow'}
        from PySide6.QtWidgets import QMessageBox
        if vals['offset']<0 or vals['sill']<0 or (wall_length is not None and vals['offset']+vals['width']>wall_length+1e-8) or (wall_height is not None and vals['sill']+vals['height']>wall_height+1e-8):
            QMessageBox.warning(dlg,'Dimensiones del hueco','El hueco no cabe dentro de la longitud y altura del muro.')
            continue
        return vals
    return None


def available(ctx):
    """True only for a real Qt application, never for a headless test harness."""
    try:
        from PySide6.QtWidgets import QApplication
        return QApplication.instance() is not None and _parent(ctx) is not None
    except ImportError:
        return False


def column_properties(ctx, record=None):
    """Native IngeCAD-style BIM column dialog: 2D geometry + future IFC data."""
    QDialog,_,_,QFormLayout,QGroupBox,_,_,QLineEdit,_=_widgets()
    d=record or {}
    dlg,layout,buttons=_dialog(ctx,'Arquitectura — Pilar',
       'Defina la sección en planta y las propiedades BIM del pilar. La posición se marcará con el ratón.')
    geo=QGroupBox('Sección y posición',dlg)
    form=QFormLayout(geo)
    shape=_choice([('Rectangular','rect'),('Circular','circ'),('Hexagonal regular','hex'),('Octogonal regular','oct')],d.get('shape','rect'))
    w=_spin(d.get('width',.30),positive=True)
    h=_spin(d.get('depth',.30),positive=True)
    radius=_spin(d.get('radius',.15),positive=True)
    rotation=_spin(d.get('rotation',0))
    rotation.setSuffix(' °')
    rotation.setRange(-360.,360.)
    rotation.setSingleStep(15.)
    height=_spin(d.get('height',2.70),positive=True)
    z=_spin(d.get('base',0))
    for name,widget in [('Sección:',shape),('Anchura (X):',w),('Fondo (Y):',h),
                        ('Radio circunscrito:',radius),('Giro de sección:',rotation),('Altura:',height),('Cota base:',z)]:
        form.addRow(name,widget)
    def update(*_):
        regular=shape.currentData() in ('circ','hex','oct')
        w.setEnabled(not regular);h.setEnabled(not regular);radius.setEnabled(regular)
        rotation.setEnabled(shape.currentData() in ('hex','oct'))
    shape.currentIndexChanged.connect(update);update()
    layout.addWidget(geo)
    identity=QGroupBox('Identificación BIM',dlg)
    props=QFormLayout(identity)
    name=QLineEdit(str(d.get('name','Pilar')))
    typ=QLineEdit(str(d.get('type_name','Pilar genérico')))
    material=QLineEdit(str(d.get('material','Hormigón armado')))
    level=QLineEdit(str(d.get('level','Planta baja')))
    for k,v in [('Nombre:',name),('Tipo:',typ),('Material principal:',material),('Nivel:',level)]:
        props.addRow(k,v)
    cls=QLineEdit('IfcColumn');cls.setReadOnly(True)
    props.addRow('Clase IFC:',cls)
    layout.addWidget(identity);layout.addWidget(buttons)
    if dlg.exec()!=QDialog.Accepted:return None
    return dict(shape=shape.currentData(),width=w.value(),depth=h.value(),radius=radius.value(),rotation=rotation.value(),
                height=height.value(),base=z.value(),name=name.text().strip() or 'Pilar',
                type_name=typ.text().strip() or 'Pilar genérico',material=material.text().strip(),
                level=level.text().strip(),ifc_class='IfcColumn')


def architectural_defaults_dialog(ctx, current):
    """One native Qt sheet for drawing-scoped defaults. No custom stylesheet."""
    from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QTabWidget, QWidget,
                                   QFormLayout, QVBoxLayout, QLineEdit, QLabel)
    from copy import deepcopy
    data=deepcopy(current)
    dlg=QDialog(getattr(ctx,'host',None))
    dlg.setWindowTitle('Arquitectura — Parámetros iniciales (PARAMETROSARQ)')
    dlg.resize(450,510)
    main=QVBoxLayout(dlg)
    info=QLabel('Valores por defecto para elementos NUEVOS. Se guardan en el dibujo DXF; no modifican los ya dibujados.')
    info.setWordWrap(True);main.addWidget(info)
    tabs=QTabWidget(dlg);main.addWidget(tabs)
    numeric={'thickness','height','base','width','depth','radius','rotation','sill'}
    labels={'thickness':'Espesor (m)','height':'Altura (m)','base':'Cota base (m)',
            'reference':'Referencia','name':'Nombre','type_name':'Tipo',
            'material':'Material','level':'Nivel','shape':'Sección',
            'width':'Anchura (m)','depth':'Fondo (m)','radius':'Radio circunscrito (m)','rotation':'Giro (°)',
            'sill':'Antepecho (m)'}
    editors={}
    for kind,title in [('wall','Muros'),('column','Pilares'),('door','Puertas'),('window','Ventanas')]:
        widget=QWidget();form=QFormLayout(widget)
        for key,value in data[kind].items():
            if key in numeric:
                editor=_spin(value,positive=key not in ('base','sill','rotation'))
                if key=='rotation':
                    editor.setSuffix(' °');editor.setRange(-360,360);editor.setSingleStep(15)
            elif key=='reference':
                editor=_choice([('Eje','eje'),('Izquierda','izquierda'),('Derecha','derecha')],value)
            elif key=='shape':
                editor=_choice([('Rectangular','rect'),('Circular','circ'),('Hexagonal regular','hex'),('Octogonal regular','oct')],value)
            else:
                editor=QLineEdit(str(value))
            form.addRow(labels.get(key,key),editor)
            editors[(kind,key)]=editor
        tabs.addTab(widget,title)
    main.addWidget(QLabel('Nota: puertas y ventanas permanecen en fase experimental.'))
    buttons=QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    buttons.accepted.connect(dlg.accept);buttons.rejected.connect(dlg.reject)
    main.addWidget(buttons)
    if dlg.exec()!=QDialog.Accepted:return None
    for (kind,key),editor in editors.items():
        if key in numeric: data[kind][key]=editor.value()
        elif key in ('reference','shape'):data[kind][key]=editor.currentData()
        else:data[kind][key]=editor.text().strip()
    from .parameters_arq import validate_defaults
    return validate_defaults(data)

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
    # General: the way of working with this drawing (user, 9-11-2026)
    from PySide6.QtWidgets import QCheckBox
    general=QWidget();gform=QFormLayout(general)
    usos=QCheckBox('Trabajar con usos de recinto')
    usos.setChecked(bool(data.get('general',{}).get('usar_usos',False)))
    usos.setToolTip('Sí: la ficha de recinto pide el uso y el uso decide la clasificación '
                    '(altura habitable de baños, pasillos...). No: decide el nombre.')
    minimo=_spin(data.get('general',{}).get('cota_minima',0.0))
    minimo.setRange(0.0,10.0)
    minimo.setToolTip('COTAMUROS no acota distancias menores (0 = todas)')
    gform.addRow('',usos);gform.addRow('Cota mínima (m)',minimo)
    tabs.insertTab(0,general,'General');tabs.setCurrentIndex(0)
    editors[('general','usar_usos')]=usos;editors[('general','cota_minima')]=minimo
    main.addWidget(QLabel('Nota: puertas y ventanas permanecen en fase experimental.'))
    buttons=QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    buttons.accepted.connect(dlg.accept);buttons.rejected.connect(dlg.reject)
    main.addWidget(buttons)
    dlg._arq=editors
    if dlg.exec()!=QDialog.Accepted:return None
    return read_defaults_dialog(data,editors,numeric)


def read_defaults_dialog(data,editors,numeric=('thickness','height','base','width','depth','radius','rotation','sill')):
    data.setdefault('general',{})
    for (kind,key),editor in editors.items():
        if key=='usar_usos': data[kind][key]=editor.isChecked()
        elif key=='cota_minima': data[kind][key]=editor.value()
        elif key in numeric: data[kind][key]=editor.value()
        elif key in ('reference','shape'):data[kind][key]=editor.currentData()
        else:data[kind][key]=editor.text().strip()
    from .parameters_arq import validate_defaults
    return validate_defaults(data)


# --- carpentry (doors, windows, plain holes) ---------------------------------

def _int_spin(value, lo, hi):
    from PySide6.QtWidgets import QSpinBox
    w = QSpinBox()
    w.setRange(lo, hi)
    w.setValue(int(value))
    return w


def carpentry_form(ctx, record, *, editing=False):
    """(dialog, read) of the carpentry sheet: the model (type, opening, leaves,
    sizes, frame, sill) and its BIM identity; ``editing`` adds the position
    in the wall and the side it opens to. ``read()`` returns the values."""
    from PySide6.QtWidgets import QLabel, QLineEdit
    from . import openings as OP
    QDialog, _, _, QFormLayout, QGroupBox, *_ = _widgets()
    d = OP.normalise({"type": record.get("type", "door"), "width": record.get("width", 0.9),
                      "sill": record.get("sill", 0.0), "height": record.get("height", 2.1),
                      "offset": record.get("offset", 0.0),
                      **{k: v for k, v in record.items() if k not in ("width", "sill", "height", "offset")}})
    dlg, layout, buttons = _dialog(ctx, "Arquitectura — Carpintería",
                                   "Modelo de puerta, ventana o hueco. Las medidas de hoja son las de la "
                                   "hoja; el hueco se calcula con el cerco.")
    model = QGroupBox("Modelo", dlg)
    f = QFormLayout(model)
    typ = _choice([("Puerta", "door"), ("Ventana", "window"), ("Hueco (sin carpintería)", "gap")], d["type"])
    operation = _choice([], None)
    leaves = _int_spin(d.get("leaves") or 1, 1, 6)
    preset = _choice([("625 mm (UNE 56803)", 0.625), ("725 mm (UNE 56803)", 0.725),
                      ("825 mm (UNE 56803)", 0.825), ("925 mm (comercial)", 0.925),
                      ("Otra medida", None)], None)
    leaf = _spin(d.get("leaf") or 0.825, positive=True)
    leaf2 = _spin(d.get("leaf2") or 0.0)
    width = _spin(float(record.get("chord") or d["width"]), positive=True)
    height = _spin(d["height"], positive=True)
    sill = _spin(d["sill"])
    face = _choice([("Interior (plano hacia el que abre)", "interior"), ("Medio", "centrada"),
                    ("Exterior", "exterior")], d.get("face", "interior"))
    frame_w = _spin(d.get("frame_width") or 0.0)
    frame_d = _spin(d.get("frame_depth") or 0.0)
    sill_kind = _choice([("Alféizar", "alfeizar"), ("Vierteaguas", "vierteaguas"), ("Ventanal", "ventanal")],
                        d.get("sill_kind") or "alfeizar")
    clear = QLabel("")
    rows = [("Tipo:", typ), ("Apertura:", operation), ("Hojas:", leaves), ("Hoja normalizada:", preset),
            ("Hoja principal:", leaf), ("Segunda hoja (0 = igual):", leaf2), ("Ancho del hueco:", width),
            ("Altura:", height), ("Antepecho:", sill), ("Ajuste del cerco:", face),
            ("Cerco, ancho de jamba:", frame_w), ("Cerco, profundidad (0 = automática):", frame_d),
            ("Remate inferior:", sill_kind), ("Paso libre (DB-SUA):", clear)]
    for label, w in rows:
        f.addRow(label, w)
    layout.addWidget(model)
    place = None
    if editing:
        place = QGroupBox("Posición en el muro", dlg)
        pf = QFormLayout(place)
        offset = _spin(d.get("offset", 0.0))
        side = _choice([("Hacia la cara izquierda del muro", 1), ("Hacia la cara derecha del muro", -1)],
                       d.get("side", 1))
        hinge = _choice([("En la jamba del inicio", 0), ("En la jamba del final", 1)], d.get("hinge", 0))
        pf.addRow("Distancia desde el inicio:", offset)
        pf.addRow("Abre:", side)
        pf.addRow("Bisagra:", hinge)
        layout.addWidget(place)
    ident = QGroupBox("Identificación BIM", dlg)
    g = QFormLayout(ident)
    name = QLineEdit(str(record.get("name") or ""))
    type_name = QLineEdit(str(record.get("type_name") or ""))
    material = QLineEdit(str(record.get("material") or ""))
    ifc = QLineEdit("")
    ifc.setReadOnly(True)
    for label, w in (("Nombre:", name), ("Tipo:", type_name), ("Material:", material), ("Clase IFC:", ifc)):
        g.addRow(label, w)
    layout.addWidget(ident)
    layout.addWidget(buttons)

    def show(widget, on):
        widget.setVisible(on)
        lab = f.labelForField(widget)
        if lab is not None:
            lab.setVisible(on)

    def fill_operations():
        kind = typ.currentData()
        current = operation.currentData() or d.get("operation")
        operation.blockSignals(True)
        operation.clear()
        for op in OP.OPERATIONS[kind]:
            if op:
                operation.addItem(OP.OPERATION_NAMES.get(op, op).capitalize(), op)
        pos = operation.findData(current)
        operation.setCurrentIndex(pos if pos >= 0 else 0)
        operation.blockSignals(False)

    def refresh(*_):
        kind = typ.currentData()
        door, window = kind == "door", kind == "window"
        show(operation, kind != "gap")
        show(leaves, kind != "gap")
        leaves.setMaximum(2 if door else 6)
        for w in (preset, leaf, leaf2):
            show(w, door)
        show(leaf2, door and leaves.value() == 2)
        show(width, not door)
        show(sill_kind, window)
        show(frame_w, kind != "gap")
        show(frame_d, kind != "gap")
        show(face, kind != "gap")
        show(clear, door)
        ifc.setText(OP.IFC[kind] if kind != "gap" else "IfcOpeningElement")
        if door:
            v = read()
            fr, op = OP.clear_width(v)
            ok = OP.sua_accessible(v)
            clear.setText(f"{fr:.3f} m en el marco, {op:.3f} m abierta: "
                          f"{'válida' if ok else 'NO válida'} para itinerario accesible".replace(".", ","))

    def on_preset(*_):
        val = preset.currentData()
        if val is not None:
            leaf.setValue(val)

    def read():
        kind = typ.currentData()
        v = {"type": kind, "operation": operation.currentData() or "", "height": height.value(),
             "sill": sill.value(), "face": face.currentData(), "frame_width": frame_w.value(),
             "frame_depth": frame_d.value(), "name": name.text().strip(),
             "type_name": type_name.text().strip(), "material": material.text().strip()}
        if kind == "door":
            v.update(leaves=leaves.value(), leaf=leaf.value(),
                     leaf2=leaf2.value() if leaves.value() == 2 else 0.0)
            v["width"] = OP.door_width(v["leaf"], v["leaves"], v["leaf2"], v["frame_width"])
            v["leaf2"] = v["leaf2"] or (v["leaf"] if v["leaves"] == 2 else 0.0)
        else:
            v.update(leaves=leaves.value() if kind == "window" else 0, width=width.value())
            if kind == "window":
                v["sill_kind"] = sill_kind.currentData()
            if kind == "gap":
                v.update(face="centrada", frame_width=0.0, frame_depth=0.0, operation="")
        if place is not None:
            v.update(offset=offset.value(), side=side.currentData(), hinge=hinge.currentData())
        return v

    fill_operations()
    typ.currentIndexChanged.connect(lambda *_: (fill_operations(), refresh()))
    for w in (leaves, leaf, leaf2, frame_w):
        w.valueChanged.connect(refresh)
    operation.currentIndexChanged.connect(refresh)
    preset.currentIndexChanged.connect(on_preset)
    refresh()
    dlg._arq = dict(typ=typ, operation=operation, leaves=leaves, preset=preset, leaf=leaf, leaf2=leaf2,
                    width=width, height=height, sill=sill, face=face, sill_kind=sill_kind, name=name,
                    clear=clear, ifc=ifc)
    return dlg, read


def carpentry_properties(ctx, record, *, editing=False):
    """The carpentry sheet; the values, or None on Cancel."""
    QDialog = _widgets()[0]
    dlg, read = carpentry_form(ctx, record, editing=editing)
    return read() if dlg.exec() == QDialog.Accepted else None


# --- spaces -----------------------------------------------------------------------

def space_form(ctx, record, by_use=None):
    """(dialog, read) of the space (IfcSpace) sheet.  The «Uso» field is
    shown when the drawing works with uses (general options)."""
    if by_use is None:
        from .parameters_arq import general_options
        by_use = general_options(getattr(ctx, 'document', None))['usar_usos']
    from PySide6.QtWidgets import QCheckBox, QLineEdit
    QDialog, _, _, QFormLayout, QGroupBox, *_ = _widgets()
    d = record or {}
    dlg, layout, buttons = _dialog(ctx, "Arquitectura — Recinto",
                                   "Espacio BIM (IfcSpace). Su contorno lo dan los muros que lo cierran; "
                                   "aquí se definen su nombre, uso y alturas.")
    group = QGroupBox("Recinto", dlg)
    f = QFormLayout(group)
    name = QLineEdit(str(d.get("name") or ""))
    name.setPlaceholderText("Recinto n (automático)")
    number = QLineEdit(str(d.get("number") or ""))
    use = QLineEdit(str(d.get("use") or ""))
    use.setPlaceholderText("Dormitorio, Baño, Pasillo, Cocina…")
    enclosure = _choice([("Interior", "interior"),
                         ("Exterior cubierto (terraza, balcón, porche): computa el 50 %", "exterior_cubierto")],
                        d.get("enclosure") or "interior")
    height = _spin(d.get("height", 2.70), positive=True)
    ceiling = QCheckBox("Hay falso techo (la altura es la libre bajo él)")
    ceiling.setChecked(bool(d.get("ceiling")))
    level = QLineEdit(str(d.get("level") or "Planta baja"))
    ifc = QLineEdit("IfcSpace")
    ifc.setReadOnly(True)
    rows = [("Nombre:", name), ("Número:", number), ("Uso:", use), ("Tipo:", enclosure),
            ("Altura libre:", height), ("", ceiling), ("Nivel:", level), ("Clase IFC:", ifc)]
    if not by_use:
        use.setVisible(False)
        rows = [r for r in rows if r[1] is not use]
    for label, w in rows:
        f.addRow(label, w)
    layout.addWidget(group)
    layout.addWidget(buttons)

    def read():
        return {"name": name.text().strip(), "number": number.text().strip(), "use": use.text().strip(),
                "enclosure": enclosure.currentData(), "height": height.value(),
                "ceiling": ceiling.isChecked(), "level": level.text().strip() or "Planta baja"}
    dlg._arq = dict(name=name, number=number, use=use, enclosure=enclosure, height=height, ceiling=ceiling)
    return dlg, read


def space_properties(ctx, record):
    QDialog = _widgets()[0]
    dlg, read = space_form(ctx, record)
    return read() if dlg.exec() == QDialog.Accepted else None


def problems_form(ctx, problems):
    """(dialog, list widget) of the export problems: each line says what is
    wrong; selecting it highlights its elements in the drawing.  The
    operator decides: export without them, or cancel and fix them."""
    from PySide6.QtWidgets import QListWidget, QListWidgetItem, QPushButton, QDialogButtonBox
    from . import integrity as IG
    QDialog, _, _, _, _, QVBoxLayout, _, _, QLabel = _widgets()
    dlg = QDialog(_parent(ctx))
    dlg.setWindowTitle("Arquitectura — Comprobación antes de exportar")
    dlg.setMinimumWidth(620)
    layout = QVBoxLayout(dlg)
    head = QLabel(f"Se han encontrado {len(problems)} problemas ({IG.summary(problems)}). "
                  "Seleccione uno para verlo resaltado en el dibujo. Puede exportar sin los "
                  "elementos marcados o cancelar para corregirlos.")
    head.setWordWrap(True)
    layout.addWidget(head)
    lst = QListWidget(dlg)
    for p in problems:
        item = QListWidgetItem(p["text"])
        item.setToolTip(p["text"])
        lst.addItem(item)
    lst.currentRowChanged.connect(lambda row: IG.highlight(ctx, problems[row]["handles"]) if row >= 0 else None)
    layout.addWidget(lst)
    every = QPushButton("Resaltar todos")
    every.clicked.connect(lambda: IG.highlight(ctx, [h for p in problems for h in p["handles"]]))
    buttons = QDialogButtonBox(dlg)
    go = buttons.addButton("Exportar sin los elementos marcados", QDialogButtonBox.AcceptRole)
    buttons.addButton("Cancelar y corregir", QDialogButtonBox.RejectRole)
    buttons.addButton(every, QDialogButtonBox.ActionRole)
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    layout.addWidget(buttons)
    dlg._arq = dict(list=lst, export=go)
    return dlg, lst


def problems_dialog(ctx, problems):
    """True: export without the marked elements; False: cancel."""
    QDialog = _widgets()[0]
    dlg, _lst = problems_form(ctx, problems)
    return dlg.exec() == QDialog.Accepted

# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: Fichas de propiedades (ventanas Qt): muro, carpintería, recinto, pilar… Usan la paleta de
#   IngeCAD, sin tema propio.
#   (Guía del código: docs/GUIA_DEL_CODIGO.md)
"""Native PySide6 BIM property sheets. No custom theme: inherit IngeCAD's Qt palette.

Imports are intentionally delayed: CLI/headless tools keep working without Qt.
"""
from __future__ import annotations
import math


def _parent(ctx):
    """The window a sheet hangs from: a tool's context reaches it through
    its services, a command's (PluginContext) is the host itself."""
    from .compat import dialog_parent
    return dialog_parent(ctx)


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


def _types_of(ctx, types):
    if types is not None:
        return types
    try:
        from .parameters_arq import load_defaults
        from .compat import document_of
        return load_defaults(document_of(ctx))['wall_types']
    except Exception:  # noqa: BLE001
        return []


def _layers_table(layers, editable=False):
    """A table of the layers of a wall type, from the drawn face inward."""
    from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView
    table = QTableWidget(0, 2)
    table.setHorizontalHeaderLabels(['Espesor (m)', 'Material'])
    table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
    table.verticalHeader().setVisible(True)
    if not editable:
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setMinimumHeight(110)

    def fill(rows):
        table.setRowCount(0)
        for th, mat in rows or []:
            r = table.rowCount()
            table.insertRow(r)
            table.setItem(r, 0, QTableWidgetItem(str(float(th)).replace('.', ',')))
            table.setItem(r, 1, QTableWidgetItem(str(mat)))
    table._fill = fill
    fill(layers)
    return table


def _read_layers(table):
    rows = []
    for r in range(table.rowCount()):
        th = table.item(r, 0)
        mat = table.item(r, 1)
        text = (th.text() if th else '').strip().replace(',', '.')
        if not text:
            continue
        try:
            v = float(text)
        except ValueError:
            raise ValueError(f'Capa {r + 1}: espesor no válido «{th.text()}»') from None
        if not math.isfinite(v) or not v > 0:
            raise ValueError(f'Capa {r + 1}: el espesor debe ser mayor que cero')
        rows.append([v, (mat.text() if mat else '').strip()])
    return rows


def wall_form(ctx, record=None, types=None):
    """(dialog, read) of the wall sheet. The «Tipo de muro» list holds the
    drawing's catalogue: a type sets the thickness, the material and the
    layers (shown below); «Genérico» leaves them free."""
    QDialog,_,_,QFormLayout,QGroupBox,_,QComboBox,QLineEdit,QLabel=_widgets()
    from .parameters_arq import sort_types, normalise_type, _num
    d=record or {}
    types=[normalise_type(t) for t in _types_of(ctx, types)]
    if d.get('type_name') and d.get('layers') and not any(t['name']==d['type_name'] for t in types):
        types.append(normalise_type({**d, 'name': d['type_name']}))
    dlg,layout,buttons=_dialog(ctx,'Arquitectura — Muro',
        'Elija un tipo de muro del catálogo del dibujo (TIPOSMURO) o defina uno genérico. '
        'Los datos se guardan en el DXF y viajan al modelo BIM.')
    tgroup=QGroupBox('Tipo de muro',dlg)
    tform=QFormLayout(tgroup)
    kind=QComboBox()
    kind.addItem('Genérico (espesor libre)', None)
    for t in sort_types(types):
        kind.addItem(f"{_num(t['thickness'])} m — {t['name']}", t['name'])
    current=d.get('type_name')
    pos=kind.findData(current) if current else -1
    kind.setCurrentIndex(pos if pos>=0 else 0)
    table=_layers_table(d.get('layers') or [])
    total=QLabel('')
    tform.addRow('Tipo:',kind)
    tform.addRow(table)
    total.setMinimumWidth(180)
    tform.addRow('Espesor total del tipo:',total)
    layout.addWidget(tgroup)
    group=QGroupBox('Geometría y colocación',dlg)
    form=QFormLayout(group)
    thickness=_spin(d.get('thickness',0.15),positive=True)
    height=_spin(d.get('height',3.00),positive=True)
    base=_spin(d.get('base',0.0))
    reference=_choice([('Eje','eje'),('Cara izquierda','izquierda'),('Cara derecha','derecha')],d.get('reference','eje'))
    cara_exterior = _choice([
        ('Automática según el contorno', 'auto'),
        ('Izquierda del sentido de dibujo', 'izquierda'),
        ('Derecha del sentido de dibujo', 'derecha'),
    ], d.get('cara_exterior', 'auto'))
    from .wall_categories import CATEGORIES,category
    wall_category=_choice(CATEGORIES,category(d))
    form.addRow('Categoría:',wall_category)
    for label,widget in [('Espesor:',thickness),('Altura:',height),('Cota base:',base),('Referencia de dibujo:',reference)]:form.addRow(label,widget)
    form.addRow('Cara exterior:', cara_exterior)
    from .levels import load as load_levels
    from .compat import require_document
    try:catalog=load_levels(require_document(ctx))
    except (ValueError,AttributeError,RuntimeError):catalog={'levels':[],'active':None}
    height_constraint=_choice([('Altura fija','fixed'),('Hasta un nivel','level')],d.get('height_constraint','fixed'))
    base_level=_choice([(lv['name'],lv['id']) for lv in catalog['levels']],d.get('level_id',catalog['active']))
    higher=[lv for lv in catalog['levels'] if lv['elevation']>float(d.get('base',0))]
    top_default=higher[0]['id'] if higher else None
    top_level=_choice([(lv['name'],lv['id']) for lv in catalog['levels']],d.get('top_level_id',top_default))
    base_offset=_spin(d.get('base_offset',d.get('level_offset',0)))
    top_offset=_spin(d.get('top_offset',0))
    resulting_height=QLabel()
    for label,w in [('Restricción superior:',height_constraint),('Nivel base:',base_level),
                    ('Desfase de base:',base_offset),('Nivel superior:',top_level),
                    ('Desfase de coronación:',top_offset),('Altura resultante (solo lectura):',resulting_height)]:form.addRow(label,w)
    def constrained_values():
        from .wall_constraints import resolve
        return resolve({**d,'height_constraint':'level','level_id':base_level.currentData(),
                        'base_offset':base_offset.value(),'top_level_id':top_level.currentData(),
                        'top_offset':top_offset.value()},catalog)
    def update_constraint(*_):
        fixed=height_constraint.currentData()=='fixed'
        height.setEnabled(fixed);base.setEnabled(fixed)
        for w in (base_level,base_offset,top_level,top_offset):w.setEnabled(not fixed)
        try:
            value=height.value() if fixed else constrained_values()['height']
            resulting_height.setText(f'{value:.4f} m');valid=True
        except ValueError as exc:resulting_height.setText(str(exc));valid=False
        from PySide6.QtWidgets import QDialogButtonBox
        buttons.button(QDialogButtonBox.Ok).setEnabled(valid)
    for w in (height_constraint,base_level,top_level):w.currentIndexChanged.connect(update_constraint)
    for w in (base_offset,top_offset,height):w.valueChanged.connect(update_constraint)
    update_constraint()
    from PySide6.QtWidgets import QCheckBox
    manual=QCheckBox('Modificar espesor respecto al tipo elegido')
    mismatch=QLabel();mismatch.setWordWrap(True);mismatch.setMinimumHeight(3*mismatch.fontMetrics().height())
    resolution=_choice([('Reajustar el muro al espesor del tipo','restore'),
        ('Reajustar capas como variante local del tipo','variant'),('Desvincular este muro del tipo','detach')],'restore')
    form.addRow(manual);form.addRow('Discrepancia:',mismatch);form.addRow('Resolver antes de aceptar:',resolution)
    layout.addWidget(group)
    group2=QGroupBox('Identificación BIM',dlg)
    frm2=QFormLayout(group2)
    name=QLineEdit(str(d.get('name','Muro')))
    material=QLineEdit(str(d.get('material','Sin definir')))
    level=QLineEdit(str(d.get('level','Planta baja')))
    level.setReadOnly(bool(catalog['levels']))
    frm2.addRow('Nombre:',name)
    frm2.addRow('Material principal:',material);frm2.addRow('Nivel:',level)
    frm2.addRow('Clase IFC:',QLineEdit('IfcWall'))
    frm2.itemAt(frm2.count()-1).widget().setReadOnly(True)
    layout.addWidget(group2);layout.addWidget(buttons)
    by_name={t['name']:t for t in types}

    def chosen():
        return by_name.get(kind.currentData())

    def discrepancy(*_):
        t=chosen();different=bool(t and abs(thickness.value()-t['thickness'])>5e-7)
        mismatch.setText('El espesor del muro no coincide con el tipo: elija cómo resolverlo.' if different else 'Espesor coherente con el tipo.' if t else 'Muro sin vínculo al catálogo.')
        resolution.setEnabled(different);manual.setEnabled(t is not None)
        thickness.setEnabled(t is None or manual.isChecked())
    manual.toggled.connect(discrepancy);thickness.valueChanged.connect(discrepancy)
    def update(*_):
        t=chosen()
        if t is None:
            table._fill(d.get('layers') if not d.get('type_name') in by_name else [])
            thickness.setEnabled(True)
            total.setText('el del campo Espesor')
        else:
            wall_category.setCurrentIndex(wall_category.findData(t['wall_category']))
            table._fill(t['layers'])
            thickness.setValue(t['thickness'])
            thickness.setEnabled(False)
            if t.get('material'):
                material.setText(t['material'])
            if name.text().strip() in ('', 'Muro') or name.text().strip() in by_name:
                name.setText(t['name'])
            total.setText(f"{_num(t['thickness'])} m ({len(t['layers'])} capa"
                          + ('s' if len(t['layers'])!=1 else '') + ')')
        discrepancy()
    kind.currentIndexChanged.connect(update);update()
    wall_category.setCurrentIndex(wall_category.findData(category(d)))
    if chosen() is not None and abs(float(d.get('thickness',chosen()['thickness']))-chosen()['thickness'])>5e-7:
        manual.setChecked(True);thickness.setValue(float(d['thickness']));discrepancy()

    def read():
        from .linea_fichas import normalizar_muro
        out = {'thickness': thickness.value(), 'height': height.value(), 'base': base.value(),
               'cara_exterior': cara_exterior.currentData(),
               'reference': reference.currentData(), 'name': name.text().strip() or 'Muro',
               'material': material.text().strip(), 'level': level.text().strip(),
               'ifc_class': 'IfcWall', 'wall_category': wall_category.currentData(),
               'height_constraint': height_constraint.currentData(),
               'level_id': base_level.currentData(), 'top_level_id': top_level.currentData(),
               'base_offset': base_offset.value(), 'top_offset': top_offset.value(),
               'type_name': current, 'layers': d.get('layers') or [],
               '_tipo_elegido': kind.currentData(), '_resolucion': resolution.currentData()}
        if 'orden_capas' in d:
            out['orden_capas'] = d['orden_capas']
        return normalizar_muro(ctx, out, types, catalog)
    dlg._arq={'cara_exterior':cara_exterior,'height_constraint':height_constraint,'base_level':base_level,'top_level':top_level,'base_offset':base_offset,'top_offset':top_offset,'resulting_height':resulting_height,'height':height,'wall_category':wall_category,'type':kind,'thickness':thickness,'layers':table,'name':name,'material':material,'total':total,'manual_thickness':manual,'mismatch':mismatch,'resolution':resolution}
    return dlg,read


def wall_properties(ctx, record=None, types=None):
    """Return validated parameters, or None on Cancel; does not mutate the drawing."""
    QDialog=_widgets()[0]
    dlg,read=wall_form(ctx,record,types)
    if dlg.exec()!=QDialog.Accepted:return None
    return read()


def wall_types_form(ctx, types):
    """(dialog, read) of TIPOSMURO: the catalogue of wall types of the
    drawing, each a list of layers from the drawn face inward; its
    thickness is their sum. read() -> the new list of types."""
    from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QListWidget,
                                   QListWidgetItem, QPushButton, QLineEdit, QLabel, QFormLayout,
                                   QGroupBox, QMessageBox)
    from PySide6.QtCore import Qt
    from .parameters_arq import normalise_type, sort_types, _num
    data=[normalise_type(t) for t in types]
    dlg=QDialog(_parent(ctx))
    dlg.setWindowTitle('Arquitectura — Tipos de muro (TIPOSMURO)')
    dlg.resize(720,460)
    main=QVBoxLayout(dlg)
    info=QLabel('Tipos nuevos de envolvente: capas de exterior a interior. Particiones: desde la cara '
                'dibujada. Los tipos anteriores sin orden requieren revisión; el espesor es la suma. MURO ofrece '
                'los tipos con el espesor que se escriba.')
    info.setWordWrap(True);main.addWidget(info)
    row=QHBoxLayout();main.addLayout(row)
    left=QVBoxLayout();row.addLayout(left,2)
    headers=QHBoxLayout();headers.addWidget(QLabel('Tipo'),1);headers.addWidget(QLabel('Espesor total (m)'));left.addLayout(headers)
    lst=QListWidget();left.addWidget(lst)
    lbuttons=QHBoxLayout();left.addLayout(lbuttons)
    b_new=QPushButton('Nuevo');b_copy=QPushButton('Duplicar');b_del=QPushButton('Eliminar')
    for b in (b_new,b_copy,b_del):lbuttons.addWidget(b)
    edit=QGroupBox('Tipo seleccionado');row.addWidget(edit,3)
    eform=QFormLayout(edit)
    name=QLineEdit()
    from .wall_categories import CATEGORIES
    wall_category=_choice(CATEGORIES,'fachada')
    eform.addRow('Categoría:',wall_category)
    orden_capas = _choice([
        ('Anterior: pendiente de revisión', None),
        ('De exterior a interior', 'exterior-interior'),
        ('Desde la cara dibujada (particiones)', 'cara-dibujada'),
    ], None)
    eform.addRow('Orden de las capas:', orden_capas)

    table=_layers_table([],editable=True)
    total=QLabel('')
    cbuttons=QHBoxLayout()
    b_add=QPushButton('Añadir capa');b_rm=QPushButton('Quitar capa')
    b_up=QPushButton('Subir');b_down=QPushButton('Bajar')
    for b in (b_add,b_rm,b_up,b_down):cbuttons.addWidget(b)
    eform.addRow('Nombre:',name);eform.addRow(table);eform.addRow(cbuttons);eform.addRow('Espesor total:',total)
    buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
    main.addWidget(buttons)
    state={'row':-1,'busy':False}

    def label(t):return t['name']
    def decorate(item,t):
        from PySide6.QtWidgets import QWidget,QHBoxLayout,QLabel
        w=QWidget();w.setAutoFillBackground(True);line=QHBoxLayout(w);line.setContentsMargins(3,2,3,2)
        title=QLabel(t['name']);title.setWordWrap(True);width=QLabel(_num(t['thickness'])+' m');width.setMinimumWidth(80);width.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        line.addWidget(title,1);line.addWidget(width);lst.setItemWidget(item,w);item.setSizeHint(w.sizeHint())


    def select(i):
        """Select row i in the list and show it, without storing anything."""
        state['busy']=True
        lst.setCurrentRow(i)
        state['busy']=False
        show(i)

    def store():
        """Put the editor back into the type shown (raises on bad data)."""
        i=state['row']
        if not 0<=i<len(data):
            return
        layers=_read_layers(table)
        nm=name.text().strip()
        if not nm:
            raise ValueError('El tipo necesita un nombre')
        if not layers:
            raise ValueError(f'El tipo «{nm}» necesita al menos una capa')
        if any(t['name'].lower()==nm.lower() for k,t in enumerate(data) if k!=i):
            raise ValueError(f'Ya existe un tipo «{nm}»')
        valores = {**data[i], 'name': nm, 'layers': layers,
                   'wall_category': wall_category.currentData()}
        orden = orden_capas.currentData()
        if orden is None:
            valores.pop('orden_capas', None)
        else:
            valores['orden_capas'] = orden
        data[i] = normalise_type(valores)
        item=lst.item(i)
        if item is not None:
            item.setText(label(data[i]));decorate(item,data[i])

    def show(i):
        state['row']=i
        t=data[i] if 0<=i<len(data) else None
        state['busy']=True
        name.setText(t['name'] if t else '')
        wall_category.setCurrentIndex(wall_category.findData(t['wall_category'] if t else 'fachada'))
        table._fill(t['layers'] if t else [])
        orden_capas.setCurrentIndex(max(0, orden_capas.findData(t.get('orden_capas') if t else None)))
        state['busy']=False
        update_total()

    def update_total(*_):
        try:
            layers=_read_layers(table)
            total.setText(f"{_num(sum(l[0] for l in layers))} m" if layers else '—')
            i=state['row']
            if not state['busy'] and 0<=i<len(data) and layers:
                item=lst.item(i)
                if item is not None:decorate(item,normalise_type({'name':name.text() or data[i]['name'],'layers':layers}))
        except ValueError as exc:
            total.setText(str(exc))

    def on_row(i):
        if state['busy'] or i==state['row']:
            return
        try:
            store()
        except ValueError as exc:
            QMessageBox.warning(dlg,'Tipo de muro',str(exc))
            back=state['row']
            state['busy']=True;lst.setCurrentRow(back);state['busy']=False
            return
        show(i)

    def new(copy_of=None):
        try:
            store()
        except ValueError as exc:
            QMessageBox.warning(dlg,'Tipo de muro',str(exc));return
        from .parameters_arq import nuevo_tipo
        t=nuevo_tipo(data,copy_of)
        data.append(t)
        item=QListWidgetItem(label(t),lst);decorate(item,t)
        select(len(data)-1)

    def delete():
        i=state['row']
        if 0<=i<len(data):
            data.pop(i)
            state['busy']=True;lst.takeItem(i);state['busy']=False
            state['row']=-1
            select(min(i,len(data)-1) if data else -1)

    def add_layer():
        from PySide6.QtWidgets import QTableWidgetItem
        r=table.currentRow()+1 if table.currentRow()>=0 else table.rowCount()
        table.insertRow(r)
        table.setItem(r,0,QTableWidgetItem('0,010'));table.setItem(r,1,QTableWidgetItem(''))
        update_total()

    def remove_layer():
        r=table.currentRow()
        if r>=0:table.removeRow(r);update_total()

    def move(step):
        r=table.currentRow();t=r+step
        if r<0 or not 0<=t<table.rowCount():return
        rows=[[table.item(k,c).text() if table.item(k,c) else '' for c in (0,1)] for k in range(table.rowCount())]
        rows[r],rows[t]=rows[t],rows[r]
        from PySide6.QtWidgets import QTableWidgetItem
        for k,(a,b) in enumerate(rows):
            table.setItem(k,0,QTableWidgetItem(a));table.setItem(k,1,QTableWidgetItem(b))
        table.setCurrentCell(t,0)

    def cambiar_categoria(*_):
        if state['busy'] or orden_capas.currentData() is None:
            return
        orden = 'cara-dibujada' if wall_category.currentData() == 'particion' else 'exterior-interior'
        orden_capas.setCurrentIndex(orden_capas.findData(orden))

    wall_category.currentIndexChanged.connect(cambiar_categoria)
    lst.currentRowChanged.connect(on_row)
    table.itemChanged.connect(update_total)
    b_new.clicked.connect(lambda:new())
    b_copy.clicked.connect(lambda:new(data[state['row']]) if 0<=state['row']<len(data) else None)
    b_del.clicked.connect(delete)
    b_add.clicked.connect(add_layer);b_rm.clicked.connect(remove_layer)
    b_up.clicked.connect(lambda:move(-1));b_down.clicked.connect(lambda:move(1))

    def accept():
        try:
            store()
        except ValueError as exc:
            QMessageBox.warning(dlg,'Tipo de muro',str(exc));return
        dlg.accept()
    buttons.accepted.connect(accept);buttons.rejected.connect(dlg.reject)
    data.sort(key=lambda t:(t['thickness'],t['name'].lower()))
    for t in data:
        item=QListWidgetItem(label(t),lst);decorate(item,t)
    select(0 if data else -1)

    def read():
        store()
        return [dict(t) for t in sort_types(data)]
    dlg._arq={'orden_capas':orden_capas,'wall_category':wall_category,'list':lst,'name':name,'layers':table,'new':new,'delete':delete,'add_layer':add_layer,
              'total':total}
    return dlg,read


def wall_types_dialog(ctx, types):
    QDialog=_widgets()[0]
    dlg,read=wall_types_form(ctx,types)
    if dlg.exec()!=QDialog.Accepted:return None
    return read()


# uses of the building according to the CTE (user, 10-11-2026)
USOS_DBSI = ('Residencial Vivienda', 'Administrativo', 'Comercial', 'Residencial Público', 'Docente',
             'Hospitalario', 'Pública Concurrencia', 'Aparcamiento')
CEE_NAMES = {'ViviendaUnifamiliar': 'Vivienda unifamiliar',
             'BloqueDeViviendaCompleto': 'Bloque de viviendas completo',
             'ViviendaIndividualEnBloque': 'Vivienda individual en bloque',
             'EdificioUsoTerciario': 'Edificio de uso terciario',
             'LocalUsoTerciario': 'Local de uso terciario'}


def usos_form(ctx, usos):
    """(dialog, read) of USOSARQ: the three classifications of the building,
    each on its own (they are never deduced from one another)."""
    QDialog,_,_,QFormLayout,QGroupBox,_,QComboBox,_,QLabel=_widgets()
    from .parameters_arq import TIPOS_EDIFICIO_CEE
    u=dict(usos or {})
    dlg,layout,buttons=_dialog(ctx,'Arquitectura — Usos del edificio (USOSARQ)',
        'Tres clasificaciones independientes del Código Técnico y del certificado energético. '
        'Se guardan en el dibujo y se exportan al proyecto IFC y a cada espacio.')
    g1=QGroupBox('Certificado de eficiencia energética',dlg);f1=QFormLayout(g1)
    cee=_choice([(CEE_NAMES.get(t,t),t) for t in TIPOS_EDIFICIO_CEE],u.get('tipo_edificio_cee','ViviendaUnifamiliar'))
    f1.addRow('Tipo de edificio:',cee);layout.addWidget(g1)
    g2=QGroupBox('DB-HE (ahorro de energía)',dlg);f2=QFormLayout(g2)
    dbhe=_choice([('Residencial privado','residencial privado'),('Otros usos','otros usos')],u.get('uso_dbhe','residencial privado'))
    carga=_choice([('Baja','baja'),('Media','media'),('Alta','alta')],u.get('carga_dbhe') or 'media')
    horario=_choice([('8 h','8'),('12 h','12'),('16 h','16'),('24 h','24')],str(u.get('horario_dbhe') or '12'))
    f2.addRow('Uso:',dbhe);f2.addRow('Carga interna:',carga);f2.addRow('Horario de uso:',horario)
    def upd(*_):
        other=dbhe.currentData()=='otros usos'
        carga.setEnabled(other);horario.setEnabled(other)
    dbhe.currentIndexChanged.connect(upd);upd()
    layout.addWidget(g2)
    g3=QGroupBox('DB-SI y DB-SUA (seguridad)',dlg);f3=QFormLayout(g3)
    dbsi=QComboBox();dbsi.setEditable(True)
    for name in USOS_DBSI:dbsi.addItem(name)
    dbsi.setCurrentText(str(u.get('uso_dbsi') or 'Residencial Vivienda'))
    f3.addRow('Uso:',dbsi)
    note=QLabel('Puede escribir otro uso si el proyecto lo requiere.');note.setWordWrap(True)
    f3.addRow(note);layout.addWidget(g3);layout.addWidget(buttons)

    def read():
        other=dbhe.currentData()=='otros usos'
        return {'tipo_edificio_cee':cee.currentData(),'uso_dbhe':dbhe.currentData(),
                'carga_dbhe':carga.currentData() if other else '',
                'horario_dbhe':horario.currentData() if other else '',
                'uso_dbsi':dbsi.currentText().strip() or 'Residencial Vivienda'}
    dlg._arq={'cee':cee,'dbhe':dbhe,'carga':carga,'horario':horario,'dbsi':dbsi}
    return dlg,read


def usos_dialog(ctx, usos):
    QDialog=_widgets()[0]
    dlg,read=usos_form(ctx,usos)
    if dlg.exec()!=QDialog.Accepted:return None
    return read()


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
    if getattr(ctx, 'sin_dialogos', False):
        return False
    try:
        from PySide6.QtWidgets import QApplication
        return QApplication.instance() is not None and _parent(ctx) is not None
    except ImportError:
        return False


ANCHORS = ((7, '↖', 'Esquina superior izquierda'), (8, '↑', 'Mitad de la cara superior'),
           (9, '↗', 'Esquina superior derecha'), (4, '←', 'Mitad de la cara izquierda'),
           (5, '·', 'Centro'), (6, '→', 'Mitad de la cara derecha'),
           (1, '↙', 'Esquina inferior izquierda'), (2, '↓', 'Mitad de la cara inferior'),
           (3, '↘', 'Esquina inferior derecha'))


def anchor_picker(current=5):
    """3 x 3 buttons, as the numeric keypad: the point of the column that
    goes where the user clicks (corners, middles of the faces, centre)."""
    from PySide6.QtWidgets import QWidget, QGridLayout, QToolButton, QButtonGroup
    box = QWidget()
    grid = QGridLayout(box)
    grid.setSpacing(2)
    group = QButtonGroup(box)
    group.setExclusive(True)
    for i, (key, mark, tip) in enumerate(ANCHORS):
        b = QToolButton()
        b.setText(mark)
        b.setToolTip(f'{tip} (tecla {key})')
        b.setCheckable(True)
        b.setFixedSize(30, 30)
        b.setChecked(key == int(current or 5))
        group.addButton(b, key)
        grid.addWidget(b, i // 3, i % 3)
    box._group = group
    return box


def column_form(ctx, record=None, anchor=None):
    """The column sheet -> (dialog, read): read() gives the values, with
    ``anchor`` the insertion point (1..9, as the numeric keypad) when one
    is given: placing a new column; editing one has nothing to insert."""
    QDialog,_,_,QFormLayout,QGroupBox,_,_,QLineEdit,QLabel=_widgets()
    d=record or {}
    dlg,layout,buttons=_dialog(ctx,'Arquitectura — Pilar',
       'Defina la sección, el punto de inserción y las propiedades BIM del pilar. '
       'La posición se marca con el ratón, con las referencias a objetos de IngeCAD.')
    geo=QGroupBox('Sección',dlg)
    form=QFormLayout(geo)
    shape=_choice([('Rectangular','rect'),('Circular','circ'),('Hexagonal regular','hex'),
                   ('Octogonal regular','oct'),('Perfil metálico','steel')],d.get('shape','rect'))
    w=_spin(d.get('width',.30),positive=True)
    h=_spin(d.get('depth',.30),positive=True)
    radius=_spin(d.get('radius',.15),positive=True)
    profile=QLineEdit(str(d.get('profile') or 'HEB 160'))
    profile.setToolTip('IPE 200, HEB 160, UPN 120, 2UPN 160 cajon, 2UPN 160 empresillado 0,10...')
    rotation=_spin(d.get('rotation',0))
    rotation.setSuffix(' °')
    rotation.setRange(-360.,360.)
    rotation.setSingleStep(15.)
    cover=_spin(d.get('cover',0))
    cover.setRange(0.,1.)
    cover.setSingleStep(.01)
    cover.setToolTip('Recubrimiento o forro alrededor de la sección (0 = sin recubrimiento). '
                     'Donde el pilar está dentro de un muro, el muro ocupa ese espacio.')
    height=_spin(d.get('height',3.00),positive=True)
    z=_spin(d.get('base',0))
    for name,widget in [('Sección:',shape),('Anchura (X):',w),('Fondo (Y):',h),
                        ('Radio circunscrito:',radius),('Perfil:',profile),('Giro de sección:',rotation),
                        ('Recubrimiento:',cover),('Altura:',height),('Cota base:',z)]:
        form.addRow(name,widget)
    def update(*_):
        kind=shape.currentData()
        regular=kind in ('circ','hex','oct')
        w.setEnabled(kind=='rect');h.setEnabled(kind=='rect');radius.setEnabled(regular)
        profile.setEnabled(kind=='steel')
    shape.currentIndexChanged.connect(update);update()
    layout.addWidget(geo)
    where=QGroupBox('Punto de inserción',dlg)
    wform=QFormLayout(where)
    picker=anchor_picker(anchor or 5)
    hint=QLabel('El punto del pilar que se coloca donde hace clic:\n'
                'esquinas, mitad de las caras o centro.')
    hint.setWordWrap(True)
    wform.addRow(picker,hint)
    layout.addWidget(where)
    where.setVisible(anchor is not None)
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
    link=d.get('grid_link')or{}
    props.addRow('Ubicación en rejilla:',QLabel(link.get('mark')or'Sin vínculo'))
    if link:
        props.addRow('Desfase (m):',QLabel(', '.join(f'{float(v):.3f}' for v in link.get('offset',[0,0]))))
    layout.addWidget(identity);layout.addWidget(buttons)

    def read():
        from .linea_fichas import normalizar_pilar
        out = dict(shape=shape.currentData(), width=w.value(), depth=h.value(), radius=radius.value(),
                   rotation=rotation.value(), cover=cover.value(), height=height.value(),
                   base=z.value(), name=name.text().strip() or 'Pilar',
                   type_name=typ.text().strip() or 'Pilar genérico', material=material.text().strip(),
                   level=level.text().strip(), ifc_class='IfcColumn')
        if anchor is not None:
            out['anchor'] = picker._group.checkedId() if picker._group.checkedId() > 0 else 5
        if out['shape'] == 'steel':
            out['profile'] = profile.text()
        return normalizar_pilar(out)
    dlg._arq={'shape':shape,'width':w,'depth':h,'profile':profile,'cover':cover,'anchor':picker}
    return dlg,read


def column_properties(ctx, record=None, anchor=None):
    """Native IngeCAD-style BIM column dialog: 2D geometry + future IFC data."""
    QDialog=_widgets()[0]
    dlg,read=column_form(ctx,record,anchor)
    while True:
        if dlg.exec()!=QDialog.Accepted:
            return None
        try:
            return read()
        except ValueError as exc:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(dlg,'Pilar',str(exc))


def architectural_defaults_dialog(ctx, current):
    """One native Qt sheet for drawing-scoped defaults. No custom stylesheet."""
    from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QTabWidget, QWidget,
                                   QFormLayout, QVBoxLayout, QLineEdit, QLabel, QComboBox)
    from copy import deepcopy
    data=deepcopy(current)
    dlg=QDialog(_parent(ctx))
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
    minimo=_spin(data.get('general',{}).get('cota_minima',0.05))
    minimo.setRange(0.0,10.0)
    minimo.setToolTip('COTAMUROS no acota distancias menores (0 = todas)')
    # norte del proyecto: lo necesitan los programas de cálculo energético
    norte=_spin(data.get('general',{}).get('norte',0.0))
    norte.setRange(-360.0,360.0)
    norte.setToolTip('Dirección del norte geográfico, en grados en sentido horario desde el eje +Y '
                     'del dibujo (0 = norte arriba). Se transmite a IngeTrazo y al IFC.')
    armarios=QComboBox()
    armarios.addItem('Computan (Decreto 10/2019 de Extremadura; Baleares)','computan')
    armarios.addItem('Descuentan (división interior fija)','descuentan')
    armarios.setCurrentIndex(max(0,armarios.findData(data.get('general',{}).get('armarios_superficie_util','computan'))))
    armarios.setToolTip('Si la planta de los armarios adosados cuenta como superficie útil del recinto. '
                        'El espacio IFC llega siempre hasta los muros, como piden los programas de cálculo.')
    gform.addRow('',usos);gform.addRow('Cota mínima (m)',minimo);gform.addRow('Norte (°, horario desde +Y)',norte)
    gform.addRow('Armarios en la superficie útil',armarios)
    escala = _choice([('1:20', 20), ('1:25', 25), ('1:50', 50)], data.get('general', {}).get('escala', 50))
    gform.addRow('Escala de documentación', escala)
    editors[('general', 'escala')] = escala
    # secciones y alzados (v1.48.3)
    from .vistas_arq import RELLENOS, GAMA, GROSORES
    gd = data.get('general', {})
    relleno = _choice([(n, v) for v, n in RELLENOS.items()], gd.get('vista_relleno', 'color'))
    color = _choice(list(GAMA), gd.get('vista_color', 9))
    gform.addRow('Relleno de lo cortado (secciones)', relleno)
    gform.addRow('Gris del relleno', color)
    editors[('general', 'vista_relleno')] = relleno
    editors[('general', 'vista_color')] = color
    for clave, titulo, defecto in (('grosor_corte', 'Grosor de lo cortado (mm)', 0.50),
                                   ('grosor_tierra', 'Grosor de la línea de tierra (mm)', 0.70),
                                   ('grosor_visto', 'Grosor de lo visto (mm)', 0.18)):
        control = _choice([(f"{x:g}".replace('.', ','), x) for x in GROSORES], gd.get(clave, defecto))
        gform.addRow(titulo, control)
        editors[('general', clave)] = control
    precision = _choice([('Centímetros', 'cm'), ('Milímetros', 'mm')], data.get('general', {}).get('precision_medidas', 'cm'))
    gform.addRow('Precisión de las medidas', precision)
    editors[('general', 'precision_medidas')] = precision
    tabs.insertTab(0,general,'General');tabs.setCurrentIndex(0)
    editors[('general','usar_usos')]=usos;editors[('general','cota_minima')]=minimo
    editors[('general','norte')]=norte
    editors[('general','armarios_superficie_util')]=armarios
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
        elif key in ('cota_minima','norte'): data[kind][key]=editor.value()
        elif key in numeric: data[kind][key]=editor.value()
        elif key in ('reference','shape','armarios_superficie_util','escala','precision_medidas','vista_relleno',
                     'vista_color','grosor_corte','grosor_tierra','grosor_visto'):data[kind][key]=editor.currentData()
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


# --- carpentry ------------------------------------------------------------------

CARPENTRY_MATERIALS = ("Madera", "Aluminio", "PVC", "Acero", "Vidrio", "Vidrio laminar",
                       "Piedra", "Mármol", "Hormigón polímero")
PREVIEW_COLORS = {"frame": (138, 90, 51), "leaf": (176, 122, 72), "glass": (158, 195, 230),
                  "sill": (216, 210, 196), "handle": (140, 146, 153)}


MATERIAL_COLORS = (("vidrio", (158, 195, 230)), ("madera", (176, 122, 72)), ("alumin", (178, 183, 189)),
                   ("acero", (140, 146, 153)), ("pvc", (240, 240, 236)), ("piedra", (216, 210, 196)),
                   ("mármol", (232, 229, 222)), ("marmol", (232, 229, 222)), ("hormig", (200, 198, 192)))


def _material_color(material, role):
    """The colour a piece is drawn with: by its material's name (as in
    IngeTrazo), or by its role when the material says nothing."""
    low = str(material or "").lower()
    for key, rgb in MATERIAL_COLORS:
        if key in low:
            return rgb
    return PREVIEW_COLORS[role]


def carpentry_preview(get_record, wall_thickness=0.25):
    """A small drawing of the carpentry being defined, from the SAME code
    that draws it in the plan (``openings.plan_symbol``) and builds its
    pieces in 3D (``openings.carpentry_parts``): elevation above, plan
    below, on a sample wall. ``get_record()`` gives the sheet's values."""
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygonF
    from PySide6.QtWidgets import QWidget
    from . import openings as OP
    from .geom import junctions as J

    class Preview(QWidget):
        def __init__(self):
            super().__init__()
            self.setMinimumSize(300, 340)
            self.error = ""

        def sample(self):
            rec = OP.normalise({**get_record(), "offset": 0.4})
            width = float(rec.get("width") or 0.9)
            spec = J.walls_from_records([("muestra", {"id": "muestra", "kind": "wall",
                                                      "a": [0.0, 0.0], "b": [width + 0.8, 0.0],
                                                      "thickness": wall_thickness, "height": 3.0,
                                                      "reference": "eje", "bulge": .2 if rec.get("curve_mode")=="curva" else 0.})])[0]
            return spec, rec, width

        def paintEvent(self, _event):
            qp = QPainter(self)
            qp.setRenderHint(QPainter.Antialiasing)
            qp.fillRect(self.rect(), QColor(250, 250, 248))
            try:
                spec, rec, width = self.sample()
                pieces = OP.carpentry_parts(spec, rec, 0.0)
                plan = OP.plan_symbol(spec, rec)
                self.error = ""
            except Exception as exc:          # noqa: BLE001 - the sheet keeps working
                self.error = str(exc)
                qp.drawText(self.rect(), Qt.AlignCenter | Qt.TextWordWrap,
                            "Sin vista previa: " + self.error)
                return
            W, H = self.width(), self.height()
            z1 = float(rec["sill"]) + float(rec["height"])
            top = max(z1 + 0.2, 2.4)
            span = width + 0.8
            # One metric scale for both views; each has a reserved vertical band.
            import math
            points = [(0, spec.lo), (span, spec.hi)]
            points += spec.run(spec.lo, spec.point(0,spec.lo), spec.point(span,spec.lo))
            points += spec.run(spec.hi, spec.point(0,spec.hi), spec.point(span,spec.hi))
            for item in plan:
                if item[0] == 'line': points.extend(item[1:3])
                elif item[0] == 'poly': points.extend(item[1])
                elif item[0] == 'arc':
                    c, radius, a0, a1 = item[1:5]
                    sweep = (a1-a0) % 360
                    points.extend((c[0]+radius*math.cos(math.radians(a0+sweep*i/72)),
                                   c[1]+radius*math.sin(math.radians(a0+sweep*i/72))) for i in range(73))
            xmin, xmax = min(p[0] for p in points), max(p[0] for p in points)
            ymin, ymax = min(p[1] for p in points), max(p[1] for p in points)
            k = min((W-24)/max(span,xmax-xmin), (H-112)/max(.01,top+ymax-ymin))
            ox = (W-(xmax-xmin)*k)/2-xmin*k
            elev_h = 42+top*k
            plan_top = elev_h+4
            kp = k
            px = ox
            py = plan_top+22+ymax*k
            self.metrics = {'elevation_scale': k, 'plan_scale': kp,
                            'elevation_bottom': elev_h-18,
                            'plan_top': plan_top+22, 'plan_bottom': py-ymin*k,
                            'footer_top': H-38}

            def E(s_, z):
                if rec["side"] < 0:
                    s_ = span - s_
                return QPointF(ox + s_ * k, elev_h - 18 - z * k)
            # the wall in elevation, with its hole
            wall = QPolygonF([E(0, 0), E(span, 0), E(span, top), E(0, top)])
            qp.setPen(QPen(QColor(150, 150, 150), 1))
            qp.setBrush(QBrush(QColor(226, 223, 216)))
            qp.drawPolygon(wall)
            s0, s1 = float(rec["offset"]), float(rec["offset"]) + width
            z0 = float(rec["sill"])
            qp.setBrush(QBrush(QColor(250, 250, 248)))
            qp.drawPolygon(QPolygonF([E(s0, z0), E(s1, z0), E(s1, z1), E(s0, z1)]))
            # its pieces, seen from the face it opens to
            order = {"sill": 0, "frame": 1, "leaf": 2, "glass": 3, "handle": 4}
            for part in sorted(pieces, key=lambda p: order[p["role"]]):
                part=part.get("unrolled",part)
                c = QColor(*_material_color(part["material"], part["role"]))
                if part["role"] == "glass":
                    c.setAlpha(170)
                qp.setBrush(QBrush(c))
                qp.setPen(QPen(QColor(70, 60, 50), 0.8))
                if "prism" in part:
                    outline, holes, *_ = part["prism"]
                    path = QPolygonF([E(*v) for v in outline])
                    from PySide6.QtGui import QPainterPath
                    pp = QPainterPath()
                    pp.addPolygon(path)
                    pp.closeSubpath()
                    for h in holes:
                        hp = QPainterPath()
                        hp.addPolygon(QPolygonF([E(*v) for v in h]))
                        hp.closeSubpath()
                        pp = pp.subtracted(hp)
                    qp.drawPath(pp)
                else:
                    a, b, _p, _q, lo, hi = part["box"]
                    qp.drawPolygon(QPolygonF([E(a, lo), E(b, lo), E(b, hi), E(a, hi)]))
            # La ficha reutiliza el símbolo puro que podrán usar los alzados de memoria.
            qp.setPen(QPen(QColor(90, 90, 90), 0.8, Qt.DashLine))
            for trazo in OP.simbolos_apertura_alzado(rec):
                qp.drawPolyline(QPolygonF([E(*punto) for punto in trazo]))
            # sizes
            qp.setPen(QPen(QColor(40, 40, 40)))
            qp.setFont(QFont(qp.font().family(), 8))

            def m(v):
                return f"{v:.3f}".replace(".", ",")
            qp.drawText(QRectF(4, 2, W-8, 16), Qt.AlignLeft, "Alzado (vista desde el exterior)")
            qp.drawText(QRectF(8, H-36, W-16, 32), Qt.AlignLeft | Qt.TextWordWrap,
                        f"Ancho {m(width)} m · Alto {m(z1-z0)} m · Antepecho {m(z0)} m")

            def Q(p):
                return QPointF(px + p[0] * kp, py - p[1] * kp)
            qp.drawText(QRectF(4, plan_top, W, 14), Qt.AlignLeft, "Planta (como en el dibujo)")
            lo, hi = spec.lo, spec.hi
            qp.setPen(QPen(QColor(90, 90, 90), 1))
            qp.setBrush(QBrush(QColor(226, 223, 216)))
            for a, b in ((0, s0), (s1, span)):
                pts=spec.run(lo,spec.point(a,lo),spec.point(b,lo))+spec.run(hi,spec.point(b,hi),spec.point(a,hi))
                qp.drawPolygon(QPolygonF([Q(point) for point in pts]))
            qp.setBrush(Qt.NoBrush)
            qp.setPen(QPen(QColor(120, 70, 40), 1))
            for item in plan:
                if item[0] == "line":
                    qp.drawLine(Q(item[1]), Q(item[2]))
                elif item[0] == "poly":
                    poly = QPolygonF([Q(p) for p in item[1]])
                    qp.drawPolygon(poly) if item[2] else qp.drawPolyline(poly)
                elif item[0] == "arc":
                    import math
                    c, r, a0, a1 = item[1], item[2], item[3], item[4]
                    steps = 24
                    sweep = (a1 - a0) % 360.0
                    pts = [Q((c[0] + r * math.cos(math.radians(a0 + sweep * t / steps)),
                              c[1] + r * math.sin(math.radians(a0 + sweep * t / steps))))
                           for t in range(steps + 1)]
                    qp.drawPolyline(QPolygonF(pts))
            qp.end()

    return Preview()


def carpentry_form(ctx, record, *, editing=False):
    """(dialog, read) of the carpentry sheet: the model (type, opening, leaves,
    sizes, frame, sill), the material of each piece and its BIM identity,
    beside a live drawing of it (elevation and plan, from the same code
    that draws and builds it); ``editing`` adds the position in the wall and
    the side it opens to. ``read()`` returns the values. Organised after the
    opening dialog of a free BIM editor studied in audit R10 (S2): groups,
    the result seen while it is defined, what each figure means."""
    from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget
    from . import openings as OP
    QDialog, _, _, QFormLayout, QGroupBox, *_ = _widgets()
    d = OP.normalise({"type": record.get("type", "door"), "width": record.get("width", 0.9),
                      "sill": record.get("sill", 0.0), "height": record.get("height", 2.1),
                      "offset": record.get("offset", 0.0),
                      **{k: v for k, v in record.items() if k not in ("width", "sill", "height", "offset")}})
    dlg, layout, buttons = _dialog(ctx, "Arquitectura — Carpintería",
                                   "Modelo de puerta, ventana o hueco. Las medidas de hoja son las de la "
                                   "hoja; el hueco se calcula con el cerco. El dibujo de la derecha es el "
                                   "que se obtendrá en planta y en 3D.")
    body = QHBoxLayout()
    left = QVBoxLayout()
    body.addLayout(left, 3)
    model = QGroupBox("Modelo y medidas", dlg)
    f = QFormLayout(model)
    typ = _choice([("Puerta", "door"), ("Ventana", "window"), ("Hueco (sin carpintería)", "gap")], d["type"])
    operation = _choice([], None)
    hinge = _choice([("En la jamba del inicio", 0), ("En la jamba del final", 1)], d.get("hinge", 0))
    leaves = _int_spin(d.get("leaves") or 1, 1, 6)
    preset = _choice([("625 mm (UNE 56803)", 0.625), ("725 mm (UNE 56803)", 0.725),
                      ("825 mm (UNE 56803)", 0.825), ("925 mm (comercial)", 0.925),
                      ("Otra medida", None)], None)
    leaf = _spin(d.get("leaf") or 0.825, positive=True)
    leaf2 = _spin(d.get("leaf2") or 0.0)
    width = _spin(float(record.get('_display_width',record.get("chord") or d["width"])), positive=True)
    height = _spin(d["height"], positive=True)
    sill = _spin(d["sill"])
    face = _choice([("Cara hacia la que abre (interior relativo)", "interior"), ("Centrada en el espesor", "centrada"),
                    ("Cara opuesta (exterior relativo)", "exterior"), ("A distancia de una cara", "distancia")], d.get("face", "interior"))
    curve_mode=_choice([('Plana (cuerda)','plana'),('Curva (facetada)','curva')],d['curve_mode'])
    width_reference=_choice([('Cuerda (registros antiguos)','cuerda'),('Arco del eje','eje'),
                             ('Arco de cara interior','interior'),('Arco de cara exterior','exterior')],d['width_reference'])
    facet=_spin(d['facet_sagitta']);facet.setRange(.0001,.02);facet.setDecimals(4)
    facet.setToolTip('Separación máxima entre el arco y los tramos rectos que lo representan. '
                     'Solo interviene cuando la geometría de la carpintería es curva.')
    principal = _choice([('Izquierda', 'left'), ('Derecha', 'right')], d['main_leaf'])
    hojas_manillas = _choice([('Solo la activa', 'activa'), ('Ambas hojas', 'ambas')], d['handles_mode'])
    from PySide6.QtWidgets import QSpinBox
    cantidad_manillas = QSpinBox()
    cantidad_manillas.setRange(1, 2)
    cantidad_manillas.setValue(d['handles'])
    cantidad_manillas.setToolTip('Manillas en la cara interior de la hoja principal de la ventana.')
    altura_manilla = _spin(d['handle_height'])
    altura_manilla.setRange(0.0, 1000.0)
    altura_manilla.setToolTip('Desde el suelo del nivel; 0 = 1,05 m en puertas y centro de la hoja en ventanas. '
                             'Con dos manillas indica el centro de la pareja, repartida en vertical.')
    setback = _spin(d.get("setback", 0.0)); setback.setRange(0., 1000.); setback.setSuffix(" m")
    setback_from = _choice([("Cara hacia la que abre", "interior"), ("Cara opuesta", "exterior")], d.get("setback_from", "exterior"))
    frame_w = _spin(d.get("frame_width") or 0.0)
    frame_d = _spin(d.get("frame_depth") or 0.0)
    sill_kind = _choice([("Alféizar", "alfeizar"), ("Vierteaguas", "vierteaguas"), ("Ventanal", "ventanal")],
                        d.get("sill_kind") or "alfeizar")
    hole = QLabel("")
    rows = [("Tipo:", typ),("Geometría curva:",curve_mode),("Referencia del ancho:",width_reference),("Precisión de la curva (flecha máxima):",facet), ("Apertura:", operation), ("Hojas:", leaves), ("Hoja normalizada:", preset),
            ("Hoja principal (exterior):", principal), ("Primera hoja desde el inicio (m):", leaf), ("Segunda hoja (0 = igual):", leaf2), ("Ancho del hueco:", width),
            ("Hueco resultante:", hole), ("Altura:", height), ("Antepecho:", sill),
            ("Hojas con manillas por ambas caras:", hojas_manillas),
            ("Manillas interiores en la hoja principal:", cantidad_manillas),
            ("Altura de manilla (m; 0 = automática):", altura_manilla)]
    for label, w in rows:
        f.addRow(label, w)
    if not editing:
        f.addRow("Bisagra oscilobatiente:", hinge)
    left.addWidget(model)
    frame_box = QGroupBox("Cerco y remate", dlg)
    ff = QFormLayout(frame_box)
    for label, w in (("Ajuste del cerco:", face), ("Cara desde la que se mide:", setback_from), ("Retranqueo desde esa cara:", setback), ("Ancho de jamba:", frame_w),
                     ("Profundidad (0 = automática):", frame_d), ("Remate inferior:", sill_kind)):
        ff.addRow(label, w)
    left.addWidget(frame_box)
    mats = QGroupBox("Materiales de las piezas", dlg)
    mf = QFormLayout(mats)

    def mat_box(key, role):
        box = QComboBox()
        box.setEditable(True)
        box.addItems(CARPENTRY_MATERIALS)
        box.setCurrentText(str(record.get(key) or OP.part_material(d, role)))
        return box
    m_frame, m_leaf = mat_box("frame_material", "frame"), mat_box("leaf_material", "leaf")
    m_glass, m_sill = mat_box("glass_material", "glass"), mat_box("sill_material", "sill")
    m_manilla = mat_box("handle_material", "handle")
    for label, w in (("Marco:", m_frame), ("Hojas:", m_leaf), ("Vidrio:", m_glass), ("Alféizar:", m_sill), ("Manilla:", m_manilla)):
        mf.addRow(label, w)
    left.addWidget(mats)
    place = None
    if editing:
        place = QGroupBox("Posición en el muro", dlg)
        pf = QFormLayout(place)
        offset = _spin(d.get("offset", 0.0))
        side = _choice([("Hacia la cara izquierda del muro", 1), ("Hacia la cara derecha del muro", -1)],
                       d.get("side", 1))
        pf.addRow("Distancia desde el inicio:", offset)
        pf.addRow("Abre:", side)
        pf.addRow("Bisagra:", hinge)
        left.addWidget(place)
    ident = QGroupBox("Identificación BIM", dlg)
    g = QFormLayout(ident)
    name = QLineEdit(str(record.get("name") or ""))
    type_name = QLineEdit(str(record.get("type_name") or ""))
    mark = QLineEdit(str(record.get("mark") or ""))
    g.addRow("Marca de memoria:", mark)
    material = QLineEdit(str(record.get("material") or ""))
    material.setPlaceholderText("material principal (opcional)")
    ifc = QLineEdit("")
    ifc.setReadOnly(True)
    for label, w in (("Nombre:", name), ("Tipo:", type_name), ("Material:", material), ("Clase IFC:", ifc)):
        g.addRow(label, w)
    left.addWidget(ident)
    right = QVBoxLayout()
    status = QLabel("")
    status.setWordWrap(True)
    rightw = QWidget()
    rightw.setLayout(right)
    layout.addLayout(body)
    layout.addWidget(buttons)

    def show(widget, on, form=f):
        widget.setVisible(on)
        lab = form.labelForField(widget)
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

    def problems(v):
        """Blocking problems of the values (a message each)."""
        out = [p[0].upper() + p[1:] + "." for p in OP.dimension_problems(v)]
        if v["type"] != "gap":
            fw = float(v.get("frame_width") or 0.0)
            if 2 * fw >= float(v["width"]) - 1e-6:
                out.append("El cerco es más ancho que el hueco.")
            if fw >= float(v["height"]) / 2:
                out.append("El cerco es más alto que la mitad del hueco.")
        if v["type"] == "door" and v.get("leaves") == 2 and float(v.get("leaf2") or 0) <= 0:
            out.append("Falta la segunda hoja.")
        if v["type"] != "gap":
            try:
                from .curved_carpentry import validate
                validate(v)
                OP.frame_band(_sample_spec(v), OP.normalise(v))
            except ValueError as exc:
                out.append(str(exc))
        return out

    def refresh(*_):
        kind = typ.currentData()
        door, window = kind == "door", kind == "window"
        # En una geometría plana este dato se conserva, pero no interviene.
        facet.setEnabled(curve_mode.currentData() == 'curva')
        show(operation, kind != "gap")
        if not editing:
            show(hinge, window and operation.currentData() == "TILTANDTURN")
        show(leaves, kind != "gap")
        principal.setEnabled(kind != "gap" and leaves.value() == 2)
        con_manilla = kind != "gap" and operation.currentData() != "FIXED"
        show(altura_manilla, con_manilla)
        show(hojas_manillas, door and operation.currentData() == 'SWINGING' and leaves.value() == 2)
        show(cantidad_manillas, window and operation.currentData() not in ('FIXED', 'SLIDING'))
        show(m_manilla, con_manilla, mf)
        leaves.setMaximum(2 if door else 6)
        for w in (preset, leaf, leaf2):
            show(w, door)
        show(leaf2, door and leaves.value() == 2)
        show(width, not door or curve_mode.currentData()=='curva')
        show(hole, door)
        show(sill_kind, window, ff)
        for w in (frame_w, frame_d, face):
            show(w, kind != "gap", ff)
        show(setback, kind != "gap" and face.currentData() == "distancia", ff)
        show(setback_from, kind != "gap" and face.currentData() == "distancia", ff)
        frame_box.setVisible(kind != "gap")
        mats.setVisible(kind != "gap")
        show(m_glass, window, mf)
        show(m_sill, window and sill_kind.currentData() != "ventanal", mf)
        ifc.setText(OP.IFC[kind] if kind != "gap" else "IfcOpeningElement")
        try:
            v = read()
        except ValueError as exc:
            # p. ej. una marca de otro tipo tras cambiarlo: se avisa y no se
            # puede aceptar; antes el error escapaba de la señal de Qt
            status.setText(str(exc) + ".")
            ok = buttons.button(buttons.StandardButton.Ok)
            if ok is not None:
                ok.setEnabled(False)
            return
        if door:
            hole.setText(f"{v['width']:.3f} m de ancho (hojas + cerco)".replace(".", ","))
        notes = problems(v)
        if door and v.get('curve_mode')=='curva':
            notes.append('Paso libre en carpintería curva: comprobación específica pendiente; no certifica accesibilidad.')
        elif door and not problems(v):
            notes.append(OP.sua_text(v))
        if kind == "gap":
            notes.append("Hueco sin carpintería: en 3D, el vano abierto en el muro.")
        else:
            pieces = [] if problems(v) else OP.carpentry_parts(_sample_spec(v), {**v, "offset": 0.4}, 0.0)
            roles = {p["role"] for p in pieces}
            names = [n for r, n in (("frame", "marco"), ("leaf", "hojas"), ("glass", "vidrio"),
                                    ("sill", "alféizar"), ("handle", "manilla")) if r in roles]
            notes.append("En 3D: " + ", ".join(names) + ".")
        status.setText("\n".join(n for n in notes if n))
        ok = buttons.button(buttons.StandardButton.Ok) if hasattr(buttons, "StandardButton") else None
        if ok is not None:
            ok.setEnabled(not problems(v))
        preview.update()

    def _sample_spec(v):
        from .geom import junctions as J
        w = float(v.get("width") or 0.9)
        return J.walls_from_records([("muestra", {"id": "muestra", "kind": "wall", "a": [0.0, 0.0],
                                                  "b": [w + 0.8, 0.0], "thickness": float(record.get("_wall_thickness") or 0.25),
                                                  "height": 3.0, "reference": "eje"})])[0]

    def on_preset(*_):
        val = preset.currentData()
        if val is not None:
            leaf.setValue(val)

    def read():
        from .linea_fichas import normalizar_carpinteria
        values = dict(type=typ.currentData(), operation=operation.currentData() or '',
                      height=height.value(), curve_mode=curve_mode.currentData(),
                      width_reference=width_reference.currentData(), facet_sagitta=facet.value(),
                      sill=sill.value(), face=face.currentData(), setback=setback.value(),
                      setback_from=setback_from.currentData(), frame_width=frame_w.value(),
                      frame_depth=frame_d.value(), name=name.text().strip(), mark=mark.text().strip(),
                      type_name=type_name.text().strip(), material=material.text().strip(),
                      leaves=leaves.value(), main_leaf=principal.currentData(), handle_height=altura_manilla.value(),
                      handles_mode=hojas_manillas.currentData(), handles=cantidad_manillas.value(),
                      handle_material=m_manilla.currentText().strip(), leaf=leaf.value(), leaf2=leaf2.value(), width=width.value(),
                      sill_kind=sill_kind.currentData(), frame_material=m_frame.currentText().strip(),
                      leaf_material=m_leaf.currentText().strip(), glass_material=m_glass.currentText().strip(),
                      sill_material=m_sill.currentText().strip())
        if values["type"] == "window" and values["operation"] == "TILTANDTURN":
            values["hinge"] = hinge.currentData()
        if place is not None:
            values.update(offset=offset.value(), side=side.currentData(), hinge=hinge.currentData())
        return normalizar_carpinteria(values, validar=False)

    preview = carpentry_preview(read, float(record.get("_wall_thickness") or 0.25))
    right.addWidget(preview, 1)
    right.addWidget(status)
    body.addWidget(rightw, 2)
    fill_operations()
    last = {"kind": d["type"]}

    def kind_changed(*_):
        # a material still at the old kind's usual value takes the new one's
        old, new = last["kind"], typ.currentData()
        for box, role in ((m_frame, "frame"), (m_leaf, "leaf"), (m_glass, "glass"), (m_sill, "sill")):
            if box.currentText().strip() in ("", OP.MATERIALS.get(old, {}).get(role, "")):
                box.setCurrentText(OP.MATERIALS.get(new, {}).get(role, ""))
        last["kind"] = new
        fill_operations()
        refresh()
    typ.currentIndexChanged.connect(kind_changed)
    for w in (leaves, leaf, leaf2, frame_w, frame_d, width, height, sill, setback, altura_manilla, cantidad_manillas):
        w.valueChanged.connect(refresh)
    ref_state={'curve_mode':d['curve_mode'],'width_reference':d['width_reference']}
    def reference_changed(*_):
        spec=record.get('_wall_spec')
        now={'curve_mode':curve_mode.currentData(),'width_reference':width_reference.currentData()}
        if spec is not None:
            ancho_actual = width.value()
            if typ.currentData() == 'door' and ref_state['curve_mode'] != 'curva':
                # La puerta plana se mide por sus hojas y cerco; el ancho oculto
                # conserva el valor inicial aunque el usuario haya editado las hojas.
                ancho_actual = OP.door_width(
                    leaf.value(), leaves.value(), leaf2.value(), frame_w.value()
                )
            # En edición manda la cara elegida ahora, no la guardada al abrir.
            cara_actual = side.currentData() if place is not None else int(d.get('side', 1))
            ancho_eje = OP.span_of(spec, ancho_actual, ref_state, cara_actual)
            ancho_convertido = OP.measure_of(spec, ancho_eje, now, cara_actual)
            bloqueado = width.blockSignals(True)
            width.setValue(ancho_convertido)
            width.blockSignals(bloqueado)
        ref_state.update(now)
    curve_mode.currentIndexChanged.connect(reference_changed)
    width_reference.currentIndexChanged.connect(reference_changed)
    for w in (operation, hinge, principal, face, sill_kind, setback_from,curve_mode,width_reference):
        w.currentIndexChanged.connect(refresh)
    facet.valueChanged.connect(refresh)
    m_manilla.currentTextChanged.connect(refresh)
    hojas_manillas.currentIndexChanged.connect(refresh)
    preset.currentIndexChanged.connect(on_preset)
    refresh()
    catalog_choice=QComboBox();catalog_choice.addItem('Parámetros actuales',None)
    try:
        from .parameters_arq import load_defaults
        from .compat import require_document
        for item in load_defaults(require_document(ctx))['opening_types']:
            if not item.get('cabinet'):catalog_choice.addItem(item['name'],item)
    except (RuntimeError,ValueError,AttributeError):pass
    f.insertRow(0,'Tipo del dibujo:',catalog_choice)
    def select_catalog(*_):
        item=catalog_choice.currentData()
        if not item:return
        v=item['values'];typ.setCurrentIndex(typ.findData(item['type']))
        for key,control in [('height',height),('sill',sill),('leaves',leaves),('leaf',leaf),('leaf2',leaf2),('width',width),('frame_width',frame_w),('frame_depth',frame_d),('setback',setback),('handle_height',altura_manilla),('handles',cantidad_manillas)]:
            if key in v:control.setValue(v[key])
        for key,control in [('operation',operation),('main_leaf',principal),('handles_mode',hojas_manillas),('face',face),('sill_kind',sill_kind),('setback_from',setback_from),('curve_mode',curve_mode),('width_reference',width_reference)]:
            if key in v:control.setCurrentIndex(control.findData(v[key]))
        for key,control in [('frame_material',m_frame),('leaf_material',m_leaf),('glass_material',m_glass),('sill_material',m_sill),('handle_material',m_manilla)]:
            if key in v:control.setCurrentText(v[key])
        type_name.setText(item['name']);material.setText(v.get('material',''));refresh()
    catalog_choice.currentIndexChanged.connect(select_catalog)
    dlg._arq = dict(catalog_choice=catalog_choice,typ=typ, operation=operation, hinge=hinge, main_leaf=principal,
                    handle_height=altura_manilla, handle_material=m_manilla, handles_mode=hojas_manillas,
                    handles=cantidad_manillas, leaves=leaves, preset=preset, leaf=leaf, leaf2=leaf2,
                    width=width, height=height, sill=sill, face=face, sill_kind=sill_kind, name=name, mark=mark,
                    clear=status, status=status, ifc=ifc, preview=preview, frame_width=frame_w,
                    curve_mode=curve_mode,width_reference=width_reference,facet_sagitta=facet,
                    frame_material=m_frame, leaf_material=m_leaf, glass_material=m_glass,
                    sill_material=m_sill, setback=setback, setback_from=setback_from, problems=problems)
    return dlg, read


def carpentry_properties(ctx, record, *, editing=False):
    """The carpentry sheet; the values, or None on Cancel."""
    QDialog = _widgets()[0]
    dlg, read = carpentry_form(ctx, record, editing=editing)
    return read() if dlg.exec() == QDialog.Accepted else None


# --- spaces -----------------------------------------------------------------------

# usual uses of a room; the list is a help, any text is accepted. Baño,
# aseo, vestíbulo, pasillo and distribuidor need 2,20 m of free height to
# count as habitable (Decreto 10/2019, art. 2.4), the rest 2,50 m.
ROOM_USES = ("", "Estar", "Comedor", "Estar-comedor", "Cocina", "Dormitorio", "Baño", "Aseo",
             "Vestíbulo", "Pasillo", "Distribuidor", "Lavadero", "Tendedero", "Despensa",
             "Trastero", "Garaje", "Terraza", "Porche", "Despacho", "Escalera")


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
                                   "Espacio BIM (IfcSpace). Contorno por caras interiores de muros o por polilínea; "
                                   "aquí se definen su nombre, uso y alturas.")
    group = QGroupBox("Recinto", dlg)
    f = QFormLayout(group)
    name = QLineEdit(str(d.get("name") or ""))
    name.setPlaceholderText("Recinto n (automático)")
    number = QLineEdit(str(d.get("number") or ""))
    from PySide6.QtWidgets import QComboBox
    use = QComboBox()
    use.setEditable(True)
    use.addItems(ROOM_USES)
    use.setCurrentText(str(d.get("use") or ""))
    use.lineEdit().setPlaceholderText("Dormitorio, Baño, Pasillo, Cocina…")
    use.text = use.currentText                     # read and set like the line edit it was
    use.setText = use.setCurrentText
    enclosure = _choice([("Interior", "interior"),
                         ("Exterior cubierto (terraza, balcón, porche): computa el 50 %", "exterior_cubierto")],
                        d.get("enclosure") or "interior")
    height = _spin(d.get("height", 3.00), positive=True)
    height_mode = _choice([('Automática por envolvente', 'auto'), ('Manual', 'manual')],
                          d.get('height_mode', 'manual'))
    ceiling = QCheckBox("Hay falso techo (la altura es la libre bajo él)")
    ceiling.setChecked(bool(d.get("ceiling")))
    level = QLineEdit(str(d.get("level") or "Planta baja"))
    ifc = QLineEdit("IfcSpace")
    ifc.setReadOnly(True)
    rows = [("Nombre:", name), ("Número:", number), ("Uso:", use), ("Tipo:", enclosure),
            ("Cálculo de altura:", height_mode), ("Altura manual / reserva (m):", height),
            ("", ceiling), ("Nivel:", level), ("Clase IFC:", ifc)]
    if not by_use:
        use.setVisible(False)
        rows = [r for r in rows if r[1] is not use]
    for label, w in rows:
        f.addRow(label, w)
    from PySide6.QtWidgets import QLabel
    f.addRow('Límite superior:', QLabel(str(d.get('upper_limit') or
                ('se calcula al crear el recinto' if d.get('height_mode') == 'auto' else
                 'falso techo' if d.get('ceiling') else 'manual'))))
    if 'free_height' in d:
        f.addRow('Altura libre máxima (m):', QLabel(f"{d['free_height']:.3f}"))
    if 'net_volume' in d:
        f.addRow('Volumen neto (m³):', QLabel(f"{d['net_volume']:.3f}"))
    layout.addWidget(group)
    # normative classification: one label per document of the code (CTE, ITC-BT-25)
    from PySide6.QtWidgets import QPushButton, QLabel
    from . import cte_usos as CU
    cte_group = QGroupBox("Clasificación normativa (CTE e ITC-BT-25)", dlg)
    cf = QFormLayout(cte_group)
    note = QLabel("Una etiqueta por documento. Clasifica el recinto; no comprueba el cumplimiento.")
    note.setWordWrap(True)
    cf.addRow(note)
    current = dict(d.get("cte") or {})
    cte = {}
    for key, title, labels in CU.CONJUNTOS:
        box = QComboBox()
        box.addItem("—", "")
        for lab in labels:
            box.addItem(lab, lab)
        box.setCurrentIndex(max(0, box.findData(current.get(key, ""))))
        box.setToolTip(title)
        box.setMinimumContentsLength(28)
        cf.addRow(CU.SHORT[key] + ":", box)
        cte[key] = box
    propose = QPushButton("Proponer según el uso (vivienda)")
    cf.addRow(propose)

    def proposed():
        for key, lab in CU.propose(use.text()).items():
            cte[key].setCurrentIndex(max(0, cte[key].findData(lab)))
    propose.clicked.connect(proposed)
    if not by_use:
        cte_group.setVisible(False)
    layout.addWidget(cte_group)
    layout.addWidget(buttons)

    def read():
        return {"name": name.text().strip(), "number": number.text().strip(), "use": use.text().strip(),
                "enclosure": enclosure.currentData(), "height": height.value(),
                "height_mode": height_mode.currentData(),
                "ceiling": ceiling.isChecked(), "level": level.text().strip() or "Planta baja",
                "cte": CU.validate({k: b.currentData() for k, b in cte.items()})}
    dlg._arq = dict(name=name, number=number, use=use, enclosure=enclosure, height=height, ceiling=ceiling,
                    cte=cte, propose=propose, height_mode=height_mode)
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

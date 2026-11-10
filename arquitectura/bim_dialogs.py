# SPDX-License-Identifier: GPL-3.0-or-later
"""Native PySide6 BIM property sheets. No custom theme: inherit IngeCAD's Qt palette.

Imports are intentionally delayed: CLI/headless tools keep working without Qt.
"""
from __future__ import annotations


def _parent(ctx):
    """The window a sheet hangs from: a tool's context reaches it through
    its services, a command's (PluginContext) is the host itself."""
    services = getattr(ctx, 'services', None)
    parent = getattr(services, 'window', None)
    if parent is None:
        host = getattr(ctx, 'host', None)
        try:
            from PySide6.QtWidgets import QWidget
            parent = host if isinstance(host, QWidget) else None
        except ImportError:
            parent = None
    return parent


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
        return load_defaults(getattr(ctx, 'document', None))['wall_types']
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
            table.setItem(r, 0, QTableWidgetItem(f'{float(th):.3f}'.replace('.', ',')))
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
        if not v > 0:
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
    tform.addRow('Espesor total:',total)
    layout.addWidget(tgroup)
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
    material=QLineEdit(str(d.get('material','Sin definir')))
    level=QLineEdit(str(d.get('level','Planta baja')))
    frm2.addRow('Nombre:',name)
    frm2.addRow('Material principal:',material);frm2.addRow('Nivel:',level)
    frm2.addRow('Clase IFC:',QLineEdit('IfcWall'))
    frm2.itemAt(frm2.count()-1).widget().setReadOnly(True)
    layout.addWidget(group2);layout.addWidget(buttons)
    by_name={t['name']:t for t in types}

    def chosen():
        return by_name.get(kind.currentData())

    def update(*_):
        t=chosen()
        if t is None:
            table._fill(d.get('layers') if not d.get('type_name') in by_name else [])
            thickness.setEnabled(True)
            total.setText('el del campo Espesor')
        else:
            table._fill(t['layers'])
            thickness.setValue(t['thickness'])
            thickness.setEnabled(False)
            if t.get('material'):
                material.setText(t['material'])
            if name.text().strip() in ('', 'Muro') or name.text().strip() in by_name:
                name.setText(t['name'])
            total.setText(f"{_num(t['thickness'])} m ({len(t['layers'])} capa"
                          + ('s' if len(t['layers'])!=1 else '') + ')')
    kind.currentIndexChanged.connect(update);update()

    def read():
        t=chosen()
        out={'thickness':thickness.value(),'height':height.value(),'base':base.value(),
             'reference':reference.currentData(),'name':name.text().strip() or 'Muro',
             'material':material.text().strip(),'level':level.text().strip(),
             'ifc_class':'IfcWall'}
        if t is not None:
            out.update(thickness=t['thickness'],type_name=t['name'],layers=[list(l) for l in t['layers']])
        else:
            keep=current and current not in by_name
            out.update(type_name=str(current) if keep else f"Muro {_num(thickness.value())}",
                       layers=[list(l) for l in (d.get('layers') or [])] if keep else [])
        return out
    dlg._arq={'type':kind,'thickness':thickness,'layers':table,'name':name,'material':material}
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
    info=QLabel('Catálogo de tipos de muro de este dibujo. Las capas se cuentan desde la cara '
                'dibujada hacia el interior del muro; el espesor total es su suma. MURO ofrece '
                'los tipos con el espesor que se escriba.')
    info.setWordWrap(True);main.addWidget(info)
    row=QHBoxLayout();main.addLayout(row)
    left=QVBoxLayout();row.addLayout(left,2)
    lst=QListWidget();left.addWidget(lst)
    lbuttons=QHBoxLayout();left.addLayout(lbuttons)
    b_new=QPushButton('Nuevo');b_copy=QPushButton('Duplicar');b_del=QPushButton('Eliminar')
    for b in (b_new,b_copy,b_del):lbuttons.addWidget(b)
    edit=QGroupBox('Tipo seleccionado');row.addWidget(edit,3)
    eform=QFormLayout(edit)
    name=QLineEdit()
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

    def label(t):
        return f"{_num(t['thickness'])} m — {t['name']}"

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
        data[i]=normalise_type({'name':nm,'layers':layers})
        item=lst.item(i)
        if item is not None:
            item.setText(label(data[i]))

    def show(i):
        state['row']=i
        t=data[i] if 0<=i<len(data) else None
        state['busy']=True
        name.setText(t['name'] if t else '')
        table._fill(t['layers'] if t else [])
        state['busy']=False
        update_total()

    def update_total(*_):
        try:
            layers=_read_layers(table)
            total.setText(f"{_num(sum(l[0] for l in layers))} m" if layers else '—')
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
        base=copy_of or {'name':'Tipo nuevo','layers':[[0.10,'Material']]}
        nm=base['name'] if copy_of is None else base['name']+' (copia)'
        stem,k=nm,2
        while any(t['name'].lower()==nm.lower() for t in data):
            nm=f"{stem} {k}";k+=1
        t=normalise_type({'name':nm,'layers':[list(l) for l in base['layers']]})
        data.append(t)
        QListWidgetItem(label(t),lst)
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
        QListWidgetItem(label(t),lst)
    select(0 if data else -1)

    def read():
        store()
        return [dict(t) for t in sort_types(data)]
    dlg._arq={'list':lst,'name':name,'layers':table,'new':new,'delete':delete,'add_layer':add_layer,
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
    height=_spin(d.get('height',2.70),positive=True)
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
    layout.addWidget(identity);layout.addWidget(buttons)

    def read():
        out=dict(shape=shape.currentData(),width=w.value(),depth=h.value(),radius=radius.value(),
                 rotation=rotation.value(),cover=cover.value(),
                 height=height.value(),base=z.value(),name=name.text().strip() or 'Pilar',
                 type_name=typ.text().strip() or 'Pilar genérico',material=material.text().strip(),
                 level=level.text().strip(),ifc_class='IfcColumn')
        if anchor is not None:
            out['anchor']=picker._group.checkedId() if picker._group.checkedId() > 0 else 5
        if out['shape']=='steel':
            from .sections import parse_section
            parsed=parse_section(profile.text())
            if parsed.get('shape')!='steel':
                raise ValueError(f'Perfil no reconocido: {profile.text()}')
            out['profile']=parsed['profile']
            if material.text().strip() in ('','Hormigón armado'):
                out['material']=parsed.get('material','Acero')
        return out
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
                                   "Espacio BIM (IfcSpace). Su contorno lo dan los muros que lo cierran; "
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

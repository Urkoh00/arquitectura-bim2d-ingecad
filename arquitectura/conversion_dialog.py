# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: LINEASAMURO: cuadro de clasificación de capas y previsualización.
#   (Guía del código: docs/GUIA_DEL_CODIGO.md)
"""Classification sheet; graph picking is delegated back to the native tool."""
def classification_form(ctx, drawing, current):
    from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QComboBox, QLabel, QPushButton, QHeaderView,QCheckBox,QDoubleSpinBox,QFormLayout,QHBoxLayout
    from .bim_dialogs import _dialog
    from .conversion_plan import Classification, ROLES, layers_present, guess_roles
    dlg,layout,buttons=_dialog(ctx,'Arquitectura — LINEASAMURO',
        'Clasifique por capas o designe objetos en el plano. Después delimite el área, revise '
        'la previsualización y confirme. Rejas, barandillas y escaleras se conservan pendientes.')
    present=layers_present(drawing)   # también las capas dentro de los bloques
    table=QTableWidget(len(present),2);table.setHorizontalHeaderLabels(['Capa de origen','Categoría BIM']);table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);table.setMaximumHeight(400)
    combos=[]
    proposed=(current.layers if current.layers_confirmed or current.layers
              else guess_roles(present))   # explicit empty choice is not a new first visit
    for row,name in enumerate(present):
        table.setItem(row,0,QTableWidgetItem(name));box=QComboBox();box.addItem('No convertir',None)
        for key,label in ROLES.items():box.addItem(label,key)
        box.setCurrentIndex(max(0,box.findData(proposed.get(name))));table.setCellWidget(row,1,box);combos.append(box)
    layout.addWidget(table)
    separate=QCheckBox('Usar rangos independientes por categoría (m)');separate.setChecked(bool(current.thickness_ranges));layout.addWidget(separate)
    range_form=QFormLayout();range_edit={}
    for key,label,default in [('muros','Muros',(.07,.50)),('medianeras','Medianeras',(.07,.50)),('tabiques','Tabiques',(.05,.15))]:
        row=QHBoxLayout();edit=[]
        for value in current.thickness_ranges.get(key,default):
            box=QDoubleSpinBox();box.setDecimals(4);box.setRange(.001,5.);box.setValue(value);box.setEnabled(separate.isChecked());separate.toggled.connect(box.setEnabled);row.addWidget(box);edit.append(box)
        range_form.addRow(label+' mín./máx.',row);range_edit[key]=edit
    layout.addLayout(range_form)
    info=QLabel(f'{len(current.handles)} asignaciones gráficas; prevalecen sobre la capa.');layout.addWidget(info)
    role=QComboBox()
    for key,label in ROLES.items():role.addItem(label,key)
    layout.addWidget(role)
    pick=QPushButton('Designar gráficamente en el plano…');layout.addWidget(pick)
    dlg._pick_role=None
    def read():
        ranges={k:tuple(b.value()for b in boxes)for k,boxes in range_edit.items()}if separate.isChecked()else{}
        if any(a>b for a,b in ranges.values()):raise ValueError('El mínimo de espesor supera al máximo')
        return Classification({name:box.currentData() for name,box in zip(present,combos) if box.currentData()},
                              dict(current.handles),layers_confirmed=True,thickness_ranges=ranges)
    def validate_and_accept(status):
        from PySide6.QtWidgets import QMessageBox
        try:read()
        except ValueError as exc:
            QMessageBox.warning(dlg,'LINEASAMURO',str(exc));return
        if status==2:dlg._pick_role=role.currentData()
        dlg.done(status)
    buttons.accepted.disconnect();buttons.accepted.connect(lambda:validate_and_accept(1))
    def graphical():validate_and_accept(2)
    pick.clicked.connect(graphical)
    # Button box remains the last row, coherent with the existing sheets.
    layout.removeWidget(buttons);layout.addWidget(buttons)
    dlg._arq={'table':table,'role':role,'pick':pick,'separate_ranges':separate,'ranges':range_edit}
    dlg.resize(850,760)
    return dlg,read

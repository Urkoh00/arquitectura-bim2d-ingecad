# SPDX-License-Identifier: GPL-3.0-or-later
"""Classification sheet; graph picking is delegated back to the native tool."""
def classification_form(ctx, drawing, current):
    from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QComboBox, QLabel, QPushButton, QHeaderView
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
    info=QLabel(f'{len(current.handles)} asignaciones gráficas; prevalecen sobre la capa.');layout.addWidget(info)
    role=QComboBox()
    for key,label in ROLES.items():role.addItem(label,key)
    layout.addWidget(role)
    pick=QPushButton('Designar gráficamente en el plano…');layout.addWidget(pick)
    dlg._pick_role=None
    def read():
        return Classification({name:box.currentData() for name,box in zip(present,combos) if box.currentData()},
                              dict(current.handles),layers_confirmed=True)
    def graphical():
        dlg._pick_role=role.currentData();dlg.done(2)
    pick.clicked.connect(graphical)
    # Button box remains the last row, coherent with the existing sheets.
    layout.removeWidget(buttons);layout.addWidget(buttons)
    dlg._arq={'table':table,'role':role,'pick':pick}
    dlg.resize(850,620)
    return dlg,read

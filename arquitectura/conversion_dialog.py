# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: cuadro de clasificación de LINEASAMURO y carga de procedencia revisada.
"""El cuadro clasifica; la selección gráfica permanece en la herramienta CAD."""


def classification_form(ctx, drawing, current):
    from PySide6.QtWidgets import (
        QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout,
        QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton,
        QTableWidget, QTableWidgetItem,
    )
    from .bim_dialogs import _dialog
    from .conversion_plan import Classification, ROLES, guess_roles, layers_present
    from .entrada_revisada import cargar_procedencia, es_capa_revisada

    dialogo, disposicion, botones = _dialog(
        ctx,
        "Arquitectura — LINEASAMURO",
        "Clasifique por capas o designe objetos. Las capas REV-* necesitan "
        "procedencia válida y confirmación por entidad. Revise la vista previa antes de convertir.",
    )
    capas = layers_present(drawing)
    tabla = QTableWidget(len(capas), 2)
    tabla.setHorizontalHeaderLabels(["Capa de origen", "Categoría BIM"])
    tabla.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    tabla.setMaximumHeight(400)
    selectores = []
    procedencia = [current.reviewed_source]
    informacion_procedencia = QLabel()
    informacion_procedencia.setWordWrap(True)
    cargar = QPushButton("Cargar procedencia de entrada revisada…")
    disposicion.addWidget(informacion_procedencia)
    disposicion.addWidget(cargar)
    if current.layers_confirmed or current.layers:
        propuestas = current.layers
    else:
        propuestas = guess_roles(capas)
    for numero, nombre in enumerate(capas):
        tabla.setItem(numero, 0, QTableWidgetItem(nombre))
        selector = QComboBox()
        selector.addItem("No convertir", None)
        for clave, etiqueta in ROLES.items():
            selector.addItem(etiqueta, clave)
        selector.setCurrentIndex(max(0, selector.findData(propuestas.get(nombre))))
        tabla.setCellWidget(numero, 1, selector)
        selectores.append(selector)
    disposicion.addWidget(tabla)

    separar = QCheckBox("Usar rangos independientes por categoría (m)")
    separar.setChecked(bool(current.thickness_ranges))
    disposicion.addWidget(separar)
    formulario_rangos = QFormLayout()
    rangos = {}
    categorias = [
        ("muros", "Muros", (.07, .50)),
        ("medianeras", "Medianeras", (.07, .50)),
        ("particiones", "Particiones", (.05, .15)),
    ]
    for clave, etiqueta, valores_iniciales in categorias:
        fila = QHBoxLayout()
        controles = []
        for valor in current.thickness_ranges.get(clave, valores_iniciales):
            control = QDoubleSpinBox()
            control.setDecimals(4)
            control.setRange(.001, 5.)
            control.setValue(valor)
            control.setEnabled(separar.isChecked())
            separar.toggled.connect(control.setEnabled)
            fila.addWidget(control)
            controles.append(control)
        formulario_rangos.addRow(etiqueta + " mín./máx.", fila)
        rangos[clave] = controles
    disposicion.addLayout(formulario_rangos)
    informacion_grafica = QLabel(f"{len(current.handles)} asignaciones gráficas; prevalecen sobre la capa.")
    disposicion.addWidget(informacion_grafica)
    categoria_grafica = QComboBox()
    for clave, etiqueta in ROLES.items():
        categoria_grafica.addItem(etiqueta, clave)
    disposicion.addWidget(categoria_grafica)
    designar = QPushButton("Designar gráficamente en el plano…")
    disposicion.addWidget(designar)
    dialogo._pick_role = None

    def actualizar_procedencia():
        revision = procedencia[0]
        for nombre, selector in zip(capas, selectores):
            if revision is not None:
                selector.clear()
                selector.addItem(revision.resumen_capa(drawing, nombre), None)
                selector.setEnabled(False)
            else:
                selector.clear()
                selector.addItem("No convertir", None)
                for clave, etiqueta in ROLES.items():
                    selector.addItem(etiqueta, clave)
                selector.setCurrentIndex(max(0, selector.findData(propuestas.get(nombre))))
                selector.setEnabled(not es_capa_revisada(nombre))
                if es_capa_revisada(nombre):
                    selector.setCurrentIndex(0)
        if revision is None:
            informacion_procedencia.setText("Entrada normal. REV-*: No convertir sin procedencia válida.")
        else:
            cantidad = len(revision.asignaciones)
            informacion_procedencia.setText(
                f"Entrada revisada: {cantidad} entidades confirmadas. "
                "Ejes, pendientes, rechazadas, candidatos y entidades no incluidas: No convertir."
            )
        if revision is None:
            informacion_grafica.setText(f"{len(current.handles)} asignaciones gráficas; prevalecen sobre la capa.")
        else:
            informacion_grafica.setText("Las asignaciones gráficas no alteran los estados de revisión.")
        designar.setEnabled(revision is None)
        categoria_grafica.setEnabled(revision is None)

    def elegir_procedencia():
        ruta, _filtro = QFileDialog.getOpenFileName(
            dialogo, "Procedencia de entrada revisada", "", "Procedencia (*.procedencia.json)",
        )
        if not ruta:
            return
        try:
            revision = cargar_procedencia(ruta, drawing)
        except ValueError as error:
            procedencia[0] = None
            actualizar_procedencia()
            QMessageBox.warning(dialogo, "Entrada revisada", str(error))
            return
        procedencia[0] = revision
        actualizar_procedencia()

    def leer():
        limites = {}
        if separar.isChecked():
            limites = {clave: tuple(control.value() for control in controles) for clave, controles in rangos.items()}
        if any(minimo > maximo for minimo, maximo in limites.values()):
            raise ValueError("El mínimo de espesor supera al máximo")
        revision = procedencia[0]
        if revision is not None:
            revision.comprobar(drawing)
        asignaciones = {
            nombre: selector.currentData()
            for nombre, selector in zip(capas, selectores)
            if selector.currentData() is not None and not es_capa_revisada(nombre)
        }
        return Classification(
            asignaciones,
            dict(current.handles),
            layers_confirmed=True,
            thickness_ranges=limites,
            reviewed_source=revision,
        )

    def aceptar(estado):
        try:
            leer()
        except ValueError as error:
            QMessageBox.warning(dialogo, "LINEASAMURO", str(error))
            return
        if estado == 2:
            dialogo._pick_role = categoria_grafica.currentData()
        dialogo.done(estado)

    botones.accepted.disconnect()
    botones.accepted.connect(lambda: aceptar(1))
    designar.clicked.connect(lambda: aceptar(2))
    cargar.clicked.connect(elegir_procedencia)
    actualizar_procedencia()
    disposicion.removeWidget(botones)
    disposicion.addWidget(botones)
    dialogo._arq = {
        "table": tabla,
        "role": categoria_grafica,
        "pick": designar,
        "separate_ranges": separar,
        "ranges": rangos,
        "review_info": informacion_procedencia,
        "load_review": cargar,
    }
    dialogo.resize(850, 800)
    return dialogo, leer

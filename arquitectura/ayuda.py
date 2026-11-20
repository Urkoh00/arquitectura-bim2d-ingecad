# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: AYUDAARQ: todas las órdenes del plugin, agrupadas por tema, en un
#   cuadro de diálogo con buscador y detalle; sin ventana, el mismo texto
#   ordenado en la línea de órdenes.
#   (Guía del código: docs/GUIA_DEL_CODIGO.md)
"""Ayuda de órdenes del plugin.

Una sola tabla, ``SECCIONES``, alimenta el cuadro de diálogo y la versión de
texto. Cada entrada es ``(órdenes, resumen, opciones)``: las órdenes que
comparten ayuda van juntas («PUERTAARQ / VENTANAARQ / HUECOARQ»), el resumen
cabe en una línea y las opciones se muestran en el detalle. Una prueba
comprueba que toda orden registrada por el plugin aparece aquí y que aquí no
hay ninguna orden que no exista, para que la ayuda no se quede atrás.
"""
from __future__ import annotations

import html
import textwrap

#: aviso general que encabeza la ayuda
INTRODUCCION = (
    "Las órdenes de IngeCAD mover, girar, escalar, simetría y copiar valen para los "
    "elementos BIM: sus datos se ajustan al regenerar (cualquier orden del plugin o "
    "UNIONESARQ). El manual completo va en el ZIP como MANUAL_v<versión>.md."
)

_SECCIONES_BASE = (
    ("Muros", (
        (("MURO",), "Muro BIM encadenado", (
            "I o F5 cambia la cara de referencia; G toma las propiedades de otro muro",
            "Antes del primer punto, un número es el ESPESOR TOTAL (ofrece los tipos que lo tienen)",
            "T elige un tipo del catálogo (Termoarcilla, PYL, multicapa...; ver TIPOSMURO)",
            "Tab recorre las cotas temporales (longitud, ángulo); un valor escrito y Tab la "
            "fija (verde, entre corchetes); Intro o clic coloca el tramo; Mayús+Tab vuelve",
            "Terminar en la cara próxima de otro muro = encuentro en T; en la alejada = en L "
            "(lo recorta)")),
        (("MUROCURVO",), "Muro curvo por inicio, fin y punto de paso", (
            "Punto inicial, punto final y punto de paso (o flecha en m)",
            "Encadena el siguiente desde el final; E/A/C/R como MURO",
            "O circular: centro y punto (o radio) = dos medias circunferencias")),
        (("CURVAMURO",), "Curva o endereza un muro existente", (
            "Por un punto de paso o una flecha; 0 lo endereza",
            "Sus extremos y encuentros se mantienen (hasta media circunferencia)",
            "Sus carpinterías conservan su ancho real y su posición relativa",
            "En un muro curvo las puertas y ventanas son planas, sobre la cuerda entre sus "
            "jambas radiales; su ancho es el de la carpintería (la cuerda)")),
        (("MUROPARALELO",), "Muro paralelo a una cara", (
            "Distancia, línea base, lado y lado del espesor",
            "Un clic en vacío encadena otro")),
        (("ESTIRAMURO",), "Alarga o acorta un muro", (
            "Hasta un punto, una línea o la cara de otro muro (encuentro en T o en L)",
            "Un muro curvo sigue su circunferencia")),
        (("PIVOTAMURO",), "Mueve un extremo de un muro", (
            "Un muro curvo conserva su ángulo de arco",)),
        (("DIVIDEMURO",), "Divide un tramo en partes iguales", (
            "N partes con muros perpendiculares",)),
        (("BORRATRAMO",), "Borra el tramo de muro entre cruces", (
            "O hasta su extremo; también en muros curvos",)),
        (("PARTEMURO", "UNIRMURO"), "Abre un vano en un muro / une dos muros alineados", (
            "UNIRMURO une también dos muros curvos de la misma circunferencia",
            "PARTEMURO funciona también en muros curvos")),
        (("DEFENSA",), "Barandilla, balaustrada o antepecho", (
            "Primer punto y siguientes (o longitud)",
            "Altura, Espesor, Huecos (proporción de huecos del alzado), Invertir, Fin")),
        (("PARTICIONVIRTUAL",), "Límite de recinto sin muro", (
            "Dos puntos, en un muro o más allá; separa recintos sin construir nada",)),
        (("TIPOSMURO",), "Catálogo de tipos de muro", (
            "Espesor total y capas de cada tipo; lo usan MURO (opción T) y la ficha del muro",)),
        (("LINEASAMURO",), "Convierte las líneas de un plano antiguo en muros, puertas, "
                           "ventanas y vanos", (
            "Dos clics enmarcan la zona; E espesores mín./máx., A altura",
            "O líneas de origen: ocultar en capa apagada / borrar / conservar",
            "Dos arcos concéntricos a un espesor de muro = muro curvo",
            "Reconoce las capas por su nombre (pared/muro, pilar, carpintería) o K/L/R las fija",
            "Lee dentro de los bloques sin cambiarlos; medianeras con una sola cara",
            "P paralelismo de muros antiguos; las líneas sin pareja quedan seleccionadas")),
    )),
    ("Pilares y rejillas", (
        (("PILAR",), "Pilar BIM rectangular, circular o metálico", (
            "S sección (0,30x0,30 · D0,35 · IPE/IPN/HEA/HEB/UPN · 2UPN cajón/empresillado)",
            "E enganche 1-9, G girar 90°, A autorrotación",
            "P a distancia de dos paramentos, U de un paramento, C recubrimiento")),
        (("EJES", "REJILLA"), "Rejilla estructural", (
            "Origen de la rejilla; X e Y intervalos, Ángulo en grados, Suelto, Fin",)),
        (("EDITAREJE",), "Edita o renumera un eje", (
            "Designe un eje; después nuevo punto medio, Separaciones, Ficha o Renumerar",)),
        (("PILARESENEJES",), "Pilares en las intersecciones de la rejilla", (
            "Primera esquina de la zona, o Todos",)),
        (("ACTUALIZAEJES",), "Actualiza las rejillas", (
            "También las dibujadas con versiones 0.7",)),
    )),
    ("Puertas, ventanas y armarios", (
        (("CARPINTERIA",), "Puertas, ventanas y huecos en muros y tabiques", (
            "Clic en la cara hacia la que abre",
            "P/V/H tipo; un número o N = ancho de hoja (puerta; 62/72/82/92 = hojas "
            "normalizadas) o de hueco",
            "Hojas 1/2 (2 0,625), T apertura abatible/corredera/fija, I punto de inserción "
            "lateral/medio",
            "M colocación: Libre (2.º clic: sentido) / Distancia d a la esquina / Centrada / "
            "Exterior (centrada en la otra cara) / Máxima",
            "C ajuste interior/medio/exterior, E cerco (ancho y profundidad), "
            "R alféizar/vierteaguas/ventanal",
            "B bisagra y S sentido de la última",
            "Cotas temporales: un número coloca a esa distancia de la cota activa; F6 la "
            "cambia, F4 mide a la jamba o al centro",
            "Tab recorre izquierda, derecha y ancho; un valor y Tab la fija; Intro o clic "
            "coloca (izquierda y derecha fijadas dan el ancho)",
            "Pinchar una carpintería sustituye su modelo (misma identidad)",
            "Al empezar se abre su ficha (modelo, hojas, cerco, remate, identificación); "
            "D la vuelve a abrir")),
        (("PUERTAARQ", "VENTANAARQ", "HUECOARQ"), "CARPINTERIA con ese tipo de partida", ()),
        (("MOVERCARP",), "Mueve una puerta, ventana o hueco con cotas temporales", (
            "Un número la coloca a esa distancia de la cota activa; F6 o Tab pasan a la otra",
            "Un valor y Tab la mueve y activa la otra cota")),
        (("ARMARIOBIM",), "Armario adosado o empotrado", (
            "Cara de acceso y jamba del armario; Intro para terminar",
            "Computa en la superficie útil según PARAMETROSARQ")),
    )),
    ("Forjados y niveles", (
        (("FORJADO",), "Forjado horizontal con huecos", (
            "Puntos del contorno; Intro para cerrar",
            "Forjado / Solera / Cubierta; después, los huecos")),
        (("HUECOFORJADO",), "Añade un hueco a un forjado", (
            "Seleccione el forjado y dibuje el perímetro del hueco; Intro para confirmar",)),
        (("NIVELES",), "Niveles del edificio y planta activa", ()),
        (("NIVELASIGNAR",), "Asigna la selección a un nivel", ()),
    )),
    ("Recintos y superficies", (
        (("RECINTO",), "Espacio BIM (IfcSpace) con un clic dentro de la estancia", (
            "Sigue a los muros",
            "F falso techo (altura libre bajo él; 0 = hasta el forjado)",
            "T tipo: interior / exterior cubierto (terraza, balcón, porche: 50 %)",
            "Al empezar se abre su ficha; D la vuelve a abrir")),
        (("SUPERFICIES",), "Cuadro de superficies útiles (Decreto 10/2019 de Extremadura)", (
            "Lo escribe y lo dibuja en la planta donde se indique",
            "A actualiza el existente; T altura del texto")),
        (("USOSARQ",), "Usos del edificio", (
            "Certificado energético, DB-HE y DB-SI, por separado",)),
    )),
    ("Cotas y capas", (
        (("COTAMUROS",), "Cotas automáticas a través de los muros", (
            "Dos clics a través de los muros acotan todas sus caras, pilares y jambas en cadena",
            "Con la cota total (O la quita); T altura del texto",
            "Capa ARQ-COTAS, estilo ARQ (cotas normales de IngeCAD)")),
        (("CAPASARQ",), "Crea las capas ARQ-*", ()),
        (("CAPASAUTO",), "Distribuye lo seleccionado en las capas ARQ-*", ()),
    )),
    ("Datos BIM y comprobación", (
        (("PROPIEDADESARQ",), "Ficha BIM de muros, pilares, carpinterías y recintos", (
            "Designe su contorno, su símbolo o su rótulo",)),
        (("EDITARARQ",), "Edita una entidad arquitectónica", ()),
        (("UNIONESARQ",), "Regenera las uniones de muros y pilares", (
            "Actualiza los datos BIM después de mover, girar, copiar... con órdenes de IngeCAD",)),
        (("DIAGNOSTICOARQ",), "Diagnostica los encuentros de muros", ()),
        (("ARQVALIDAR",), "Valida la integridad CAD y BIM del dibujo", ()),
        (("ARQMIGRAR",), "Convierte muros de versiones anteriores del plugin", ()),
        (("ARQDIAG",), "Diagnóstico del plugin", ()),
    )),
    ("Intercambio BIM y energía", (
        (("EXPORTARBIM",), "Modelo para IngeTrazo (.arqbim)", (
            "Antes comprueba el dibujo; si hay problemas, los muestra resaltados y usted "
            "decide exportar sin ellos o corregir",)),
        (("SINCRONIZARARQ",), "Trae al dibujo los cambios hechos en IngeTrazo", ()),
        (("BIBLIOTECAHE",), "Biblioteca térmica del usuario", (
            "importar [ruta]: el BDCatalogo.bdc de la Herramienta Unificada "
            "(no se distribuye con el plugin)",
            "buscar texto: materiales que lo contienen",
            "u Composición [/ techo|suelo]: transmitancia U (DA DB-HE/1)")),
    )),
    ("Configuración y ayuda", (
        (("PARAMETROSARQ",), "Opciones generales y valores de partida", (
            "General: usos de recinto, cota mínima de COTAMUROS, norte del proyecto, "
            "armarios en la superficie útil",
            "Valores de partida de muros, pilares, puertas y ventanas")),
        (("AYUDAARQ",), "Esta ayuda", ()),
    )),
    ("Herramientas antiguas (sin datos BIM; no se exportan)", (
        (("PUERTA", "VENTANA"), "Puerta o ventana como bloque", ()),
        (("ARMARIO",), "Armario (pendiente)", ()),
        (("SUPERFICIE",), "Área en m² con etiqueta", ()),
        (("CAMARA",), "Eje o cámara de muro", ()),
        (("ESCALERA",), "Escalera en alzado", ()),
        (("ELEMENTOS",), "Activa o desactiva grupos", ()),
        (("BLOQUE",), "Mobiliario", ()),
        (("MEMORIACARP",), "Memoria de carpintería", ()),
        (("SELATRIB",), "Selección por atributos (árbol de elementos)", ()),
        (("TRAMA",), "Tramas (hatch)", ()),
        (("HIPERVINCULO", "URL"), "Hipervínculo a un fichero externo", ()),
        (("CURVAS3D",), "Eleva curvas de nivel a 3D", ()),
        (("VERTPOLY", "VERTICES"), "Vértices y coordenadas de parcela", ()),
        (("LISTATEXTOS",), "Listado de textos y áreas para el portapapeles", ()),
    )),
)


from .linea_fichas import CREACION
from .linea_configuracion import NOMBRES_CONFIGURACION
from .linea_edicion import NOMBRES_EDICION

SECCIONES = _SECCIONES_BASE + (("Órdenes sin cuadros de diálogo", tuple(
    (("-" + nombre,), "La misma orden sin cuadros de diálogo",
     ("-" + nombre + ": la misma orden sin cuadros de diálogo",
      "Intro acepta el valor entre <>; Anterior vuelve al campo anterior; Esc cancela."))
    for nombre in (*CREACION, *NOMBRES_CONFIGURACION, *NOMBRES_EDICION)
)),)


def ordenes():
    """Todas las órdenes que aparecen en la ayuda."""
    return {o for _t, entradas in SECCIONES for nombres, _r, _d in entradas for o in nombres}


def _etiqueta(nombres):
    return " / ".join(nombres)


def texto(version: str) -> list[str]:
    """La ayuda en líneas de texto, ordenada por secciones y con columnas alineadas."""
    lineas = [f"=== Plugin Arquitectura {version} — órdenes ===",
              *textwrap.wrap(INTRODUCCION, 100)]
    ancho = 22
    for titulo, entradas in SECCIONES:
        lineas.append("")
        lineas.append(f"--- {titulo} ---")
        for nombres, resumen, opciones in entradas:
            etiqueta = _etiqueta(nombres)
            if len(etiqueta) > ancho:
                lineas.append(etiqueta)
                lineas.append(" " * ancho + "— " + resumen)
            else:
                lineas.append(f"{etiqueta:<{ancho}}— {resumen}")
            for opcion in opciones:
                lineas.extend(textwrap.wrap(opcion, 100, initial_indent=" " * (ancho + 2) + "· ",
                                            subsequent_indent=" " * (ancho + 4)))
    return lineas


def _detalle_html(titulo, nombres, resumen, opciones):
    partes = [f"<h3>{html.escape(_etiqueta(nombres))}</h3>",
              f"<p><b>{html.escape(resumen)}</b></p>",
              f"<p style='color:gray'>{html.escape(titulo)}</p>"]
    if opciones:
        partes.append("<ul>" + "".join(f"<li>{html.escape(o)}</li>" for o in opciones)
                      + "</ul>")
    return "".join(partes)


def dialogo(ctx, version: str):
    """Cuadro de ayuda: buscador, árbol por secciones y detalle de la orden elegida."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QLabel, QLineEdit, QSplitter,
                                   QTextBrowser, QTreeWidget, QTreeWidgetItem, QVBoxLayout)
    from .compat import dialog_parent

    dlg = QDialog(dialog_parent(ctx))
    dlg.setWindowTitle(f"Ayuda de Arquitectura {version}")
    dlg.resize(900, 600)
    principal = QVBoxLayout(dlg)
    intro = QLabel(INTRODUCCION)
    intro.setWordWrap(True)
    principal.addWidget(intro)
    buscador = QLineEdit()
    buscador.setPlaceholderText("Buscar una orden o una palabra (p. ej. «muro», «hueco», «IFC»)")
    buscador.setClearButtonEnabled(True)
    principal.addWidget(buscador)
    division = QSplitter(Qt.Horizontal)
    arbol = QTreeWidget()
    arbol.setHeaderLabels(["Orden", "Para qué sirve"])
    arbol.setColumnWidth(0, 250)
    detalle = QTextBrowser()
    division.addWidget(arbol)
    division.addWidget(detalle)
    division.setStretchFactor(0, 3)
    division.setStretchFactor(1, 2)
    principal.addWidget(division, 1)
    botones = QDialogButtonBox(QDialogButtonBox.Close)
    botones.rejected.connect(dlg.reject)
    principal.addWidget(botones)

    elementos = []
    for titulo, entradas in SECCIONES:
        seccion = QTreeWidgetItem([titulo, ""])
        fuente = seccion.font(0)
        fuente.setBold(True)
        seccion.setFont(0, fuente)
        arbol.addTopLevelItem(seccion)
        for nombres, resumen, opciones in entradas:
            hijo = QTreeWidgetItem([_etiqueta(nombres), resumen])
            hijo.setData(0, Qt.UserRole, _detalle_html(titulo, nombres, resumen, opciones))
            hijo.setToolTip(0, _etiqueta(nombres))
            hijo.setToolTip(1, resumen)
            buscable = " ".join((*nombres, resumen, *opciones, titulo)).casefold()
            seccion.addChild(hijo)
            elementos.append((seccion, hijo, buscable))
        seccion.setExpanded(True)

    def mostrar(actual, _anterior=None):
        contenido = actual.data(0, Qt.UserRole) if actual is not None else None
        detalle.setHtml(contenido or "<p>Elija una orden para ver sus opciones.</p>")

    def filtrar(texto_buscado):
        palabras = texto_buscado.casefold().split()
        visibles = {}
        for seccion, hijo, buscable in elementos:
            ver = all(p in buscable for p in palabras)
            hijo.setHidden(not ver)
            visibles[id(seccion)] = visibles.get(id(seccion), False) or ver
        for i in range(arbol.topLevelItemCount()):
            seccion = arbol.topLevelItem(i)
            seccion.setHidden(not visibles.get(id(seccion), False))
            seccion.setExpanded(True)

    arbol.currentItemChanged.connect(mostrar)
    buscador.textChanged.connect(filtrar)
    mostrar(None)
    dlg.buscador, dlg.arbol, dlg.detalle = buscador, arbol, detalle   # para las pruebas
    return dlg


def mostrar_ayuda(ctx, version: str) -> None:
    """Abre el cuadro de ayuda; sin ventana (o si falla), escribe la ayuda ordenada."""
    from .bim_dialogs import available
    if available(ctx):
        try:
            dialogo(ctx, version).exec()
            return
        except Exception as exc:                       # la ayuda nunca debe dejar sin texto
            ctx.echo(f"AYUDAARQ: no se pudo abrir el cuadro ({type(exc).__name__}); "
                     "se muestra en la línea de órdenes.")
    for linea in texto(version):
        ctx.echo(linea)

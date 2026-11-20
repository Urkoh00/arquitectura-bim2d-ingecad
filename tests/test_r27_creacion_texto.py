# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: variantes de creación terminadas solo con texto, valores por defecto y Deshacer.
import copy
import pytest
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session

ORDENES = [
    "MURO",
    "PILAR",
    "PILARESENEJES",
    "CARPINTERIA",
    "PUERTAARQ",
    "VENTANAARQ",
    "HUECOARQ",
    "ARMARIOBIM",
    "FORJADO",
    "RECINTO",
    "EJES",
    "REJILLA",
]


def responder(herramienta, valores=None):
    valores = valores or {}
    for _ in range(100):
        if herramienta._campos_texto is None:
            return
        campo = herramienta._campos_texto[herramienta._indice_texto]
        if campo.clave in valores:
            herramienta.on_option(valores[campo.clave])
        else:
            herramienta.on_enter()
    pytest.fail("La ficha de texto no terminó: " + herramienta._prompt_source)


def preparar(sesion, orden):
    if orden in ("CARPINTERIA", "PUERTAARQ", "VENTANAARQ", "HUECOARQ", "ARMARIOBIM"):
        muro = sesion.tool("MURO")
        muro.thickness = 0.3
        muro.on_point((0.0, 0.0))
        muro.on_point((10.0, 0.0))
        muro.on_enter()
    if orden == "PILARESENEJES":
        rejilla = sesion.tool("EJES")
        rejilla.on_option("x 1x3")
        rejilla.on_option("y 1x4")
        rejilla.on_point((20.0, 20.0))


@pytest.mark.parametrize("orden", ORDENES)
def test_variante_creacion_acepta_valores_por_defecto_y_dibuja(plugin, orden):
    sesion = Session(plugin)
    preparar(sesion, orden)
    antes = len(sesion.document.doc.modelspace())
    profundidad = sesion.history.depth
    herramienta = sesion.tool("-" + orden)
    responder(herramienta)
    if orden == "PILARESENEJES":
        herramienta.on_option("todos")
    elif orden in ("CARPINTERIA", "PUERTAARQ", "VENTANAARQ", "HUECOARQ"):
        herramienta.on_point((2.0, 0.15))
        herramienta.on_point((4.0, 0.15))
        herramienta.on_enter()
    elif orden == "ARMARIOBIM":
        herramienta.on_point((2.0, 0.15))
        herramienta.on_enter()
    elif orden == "MURO":
        herramienta.on_point((20.0, 20.0))
        herramienta.on_point((25.0, 20.0))
        herramienta.on_enter()
    elif orden in ("FORJADO", "RECINTO"):
        if orden == "RECINTO":
            herramienta.on_option("polilinea")
        for punto in [(20.0, 20.0), (25.0, 20.0), (25.0, 24.0), (20.0, 24.0)]:
            herramienta.on_point(punto)
        herramienta.on_enter()
        if orden == "FORJADO":
            herramienta.on_enter()
    else:
        herramienta.on_point((20.0, 20.0))
    assert len(sesion.document.doc.modelspace()) > antes, sesion.out
    assert not any(
        "Traceback" in texto or "NameError" in texto or "AttributeError" in texto
        for texto in sesion.out
    )
    despues = len(sesion.document.doc.modelspace())
    assert sesion.history.depth == profundidad + 1
    sesion.history.undo()
    assert len(sesion.document.doc.modelspace()) == antes
    sesion.history.redo()
    assert len(sesion.document.doc.modelspace()) == despues


@pytest.mark.parametrize("orden", ORDENES)
def test_cancelar_ficha_texto_no_cambia_dibujo_ni_identidades(plugin, orden):
    sesion = Session(plugin)
    preparar(sesion, orden)
    antes = copy.deepcopy([sesion.meta(e) for e in sesion.document.doc.modelspace()])
    profundidad = sesion.history.depth
    herramienta = sesion.tool("-" + orden)
    herramienta.on_enter()
    herramienta.on_cancel()
    assert [sesion.meta(e) for e in sesion.document.doc.modelspace()] == antes
    assert sesion.history.depth == profundidad


@pytest.mark.parametrize("entrada", ["0", "-1", "texto", "nan", "inf"])
def test_campo_numerico_invalido_permanece_y_permite_reintentar(plugin, entrada):
    sesion = Session(plugin)
    herramienta = sesion.tool("-PILAR")
    herramienta.on_enter()
    assert herramienta._campos_texto[herramienta._indice_texto].clave == "width"
    herramienta.on_option(entrada)
    assert herramienta._campos_texto[herramienta._indice_texto].clave == "width"
    herramienta.on_option("250mm")
    responder(herramienta, {"depth": "25cm"})
    assert herramienta.values["width"] == 0.25
    assert herramienta.values["depth"] == 0.25


def test_carpinteria_texto_usa_la_misma_flecha_de_facetado_que_la_ficha(plugin):
    import importlib
    from PySide6.QtWidgets import QApplication
    aplicacion = QApplication.instance() or QApplication([])
    sesion = Session(plugin)
    herramienta = sesion.tool('-CARPINTERIA')
    responder(herramienta)
    paquete = plugin.tools['MURO'].__module__.rsplit('.', 1)[0]
    fichas = importlib.import_module(paquete + '.bim_dialogs')
    contexto = type('ContextoFicha', (), {'host': None, 'services': None})()
    dialogo, leer = fichas.carpentry_form(contexto, {'type': 'door', 'width': .885, 'height': 2.1, 'sill': 0.})
    assert herramienta.v['facet_sagitta'] == leer()['facet_sagitta']
    dialogo.close()
    assert aplicacion is not None

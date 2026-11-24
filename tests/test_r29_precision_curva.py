# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: la precisión de facetado solo se ofrece para carpinterías curvas.
import importlib

import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session


def modulo(plugin, nombre):
    paquete = plugin.tools["MURO"].__module__.rsplit(".", 1)[0]
    return importlib.import_module(paquete + "." + nombre)


@pytest.mark.parametrize("orden", ["CARPINTERIA", "PUERTAARQ", "VENTANAARQ", "HUECOARQ"])
def test_ficha_activa_la_precision_solo_al_elegir_curva(plugin, orden):
    from PySide6.QtWidgets import QApplication, QLabel

    aplicacion = QApplication.instance() or QApplication([])
    sesion = Session(plugin)
    herramienta = sesion.tool(orden)
    ficha, leer = modulo(plugin, "bim_dialogs").carpentry_form(
        herramienta.ctx, {**herramienta.v, **herramienta.bim}
    )
    try:
        controles = ficha._arq
        precision = controles["facet_sagitta"]
        assert not precision.isEnabled()
        assert "arco" in precision.toolTip().lower()
        assert any("Precisión de la curva" in etiqueta.text() for etiqueta in ficha.findChildren(QLabel))
        controles["curve_mode"].setCurrentIndex(controles["curve_mode"].findData("curva"))
        assert precision.isEnabled()
        precision.setValue(0.003)
        assert leer()["facet_sagitta"] == pytest.approx(0.003)
        controles["curve_mode"].setCurrentIndex(controles["curve_mode"].findData("plana"))
        assert not precision.isEnabled()
    finally:
        ficha.close()


def test_texto_omite_la_precision_en_plana_y_la_pregunta_en_curva(plugin):
    from tests.test_r27_creacion_texto import responder

    sesion = Session(plugin)
    plana = sesion.tool("-VENTANAARQ")
    responder(plana)
    assert not any("flecha máxima" in linea.lower() for linea in sesion.out)
    sesion.out.clear()
    curva = sesion.tool("-VENTANAARQ")
    responder(curva, {"curve_mode": "Curva", "facet_sagitta": "0,003"})
    assert any("flecha máxima" in linea.lower() for linea in sesion.out)
    assert curva.v["facet_sagitta"] == pytest.approx(0.003)

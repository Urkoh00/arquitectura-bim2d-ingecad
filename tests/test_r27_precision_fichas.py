# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: los valores escritos conservan la misma precisión que sus controles reales de la ficha.
from types import SimpleNamespace
import pytest
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_fichas_tipos_usos import qapp  # noqa: F401
from tests.test_r27_configuracion_texto import modulo
from tests.test_r27_creacion_texto import responder
from tests.test_wall_tools import Session


def test_editar_eje_coordenadas_y_tamano_con_precision_de_ficha(plugin, qapp):
    sesion = Session(plugin)
    rejilla = sesion.tool("EJES")
    rejilla.on_point((0.0, 0.0))
    geometria = modulo(plugin, "grids")
    entidad = geometria.axes(sesion.document.doc)[0][0]
    dialogo, leer = modulo(plugin, "grid_tools").axis_form(
        SimpleNamespace(host=None, services=None), entidad
    )
    dialogo._arq["coordinates"][0][0].setValue(0.123456)
    dialogo._arq["sizes"][0].setValue(2.3456)
    valores_esperados, puntos_esperados = leer()
    herramienta = sesion.tool("-EDITAREJE")
    herramienta.on_point((0.0, 2.0))
    herramienta.on_option("ficha")
    responder(herramienta, {"p0.x": "0,123456", "text_height": "2,3456"})
    puntos = geometria.endpoints(herramienta.entity)
    assert puntos[0][0] == puntos_esperados[0][0]
    assert sesion.meta(herramienta.entity)["text_height"] == valores_esperados["text_height"]
    dialogo.close()


def test_prolongacion_de_rejilla_tiene_los_tres_decimales_de_la_ficha(plugin, qapp):
    sesion = Session(plugin)
    dialogo, leer = modulo(plugin, "grid_tools").grid_form(
        SimpleNamespace(host=None, services=None), {}
    )
    dialogo._arq["extension"].setValue(1.23456)
    esperado = leer()
    herramienta = sesion.tool("-EJES")
    responder(herramienta, {"extension": "1,23456"})
    assert herramienta.values["extension"] == esperado["extension"]
    dialogo.close()


def test_intervalos_no_pierden_cifras_significativas(plugin):
    campos = modulo(plugin, "linea_campos")
    geometria = modulo(plugin, "grids")
    resultado = geometria.distances(campos.intervalos("2x12345,123456"))
    assert resultado == pytest.approx([0.0, 12345.123456, 24690.246912], abs=1e-9)


def test_valor_por_defecto_legible_sin_artefactos_de_float(plugin):
    campo = modulo(plugin, "linea_campos").Campo("altura", "Altura", "numero")
    assert campo.mostrar(0.15) == "0,15"

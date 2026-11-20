# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: un nombre vacío conserva los mismos valores de reserva en ficha y variante por texto.
import pytest
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session
from tests.test_r27_creacion_texto import responder


@pytest.mark.parametrize(
    "orden,esperado,tipo_esperado",
    [("MURO", "Muro", None), ("PILAR", "Pilar", "Pilar genérico"), ("FORJADO", "Forjado", None)],
)
def test_nombre_vacio_usa_la_misma_reserva_que_la_ficha(plugin, orden, esperado, tipo_esperado):
    sesion = Session(plugin)
    herramienta = sesion.tool("-" + orden)
    responder(herramienta, {"name": '""', "type_name": '""'})
    datos = herramienta.bim if orden == "MURO" else herramienta.values
    assert datos["name"] == esperado
    if tipo_esperado is not None:
        assert datos["type_name"] == tipo_esperado

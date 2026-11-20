# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: TRAMA entrega un contorno completo a HATCH y no deja rellenos fuera del historial.
import pytest
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session


@pytest.mark.parametrize("patron", list("1234567"))
def test_trama_crea_un_hatch_con_contorno_y_deshace_todo(plugin, patron):
    sesion = Session(plugin)
    herramienta = sesion.tool("TRAMA")
    herramienta.on_option(patron)
    herramienta.on_option("1")
    for punto in [(0.0, 0.0), (5.0, 0.0), (5.0, 4.0), (0.0, 4.0)]:
        herramienta.on_point(punto)
    herramienta.on_enter()
    entidades = list(sesion.document.doc.modelspace())
    assert len(entidades) == 1
    trama = entidades[0]
    assert trama.dxftype() == "HATCH"
    assert len(trama.paths) == 1
    assert trama.dxf.layer == "ARQ-TRAMAS"
    assert not any("aproximado" in mensaje for mensaje in sesion.out)
    manejador = trama.dxf.handle
    assert sesion.history.depth == 1
    sesion.history.undo()
    assert not list(sesion.document.doc.modelspace())
    sesion.history.redo()
    assert list(sesion.document.doc.modelspace())[0].dxf.handle == manejador

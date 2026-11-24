# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: las vistas usan las manillas de los mismos sólidos del contrato.
import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session
from tests.escenarios_r27 import modulo


@pytest.mark.parametrize("seccion", [False, True])
def test_la_manilla_se_ve_y_se_corta_desde_el_contrato(plugin, seccion):
    sesion = Session(plugin)
    herramienta = sesion.tool("MURO")
    herramienta.on_point((0, 0))
    herramienta.on_point((8, 0))
    herramienta.on_enter()
    muro = next(iter(sesion.walls().values()))
    cambio = modulo(plugin, "architectural_v10").create_opening(muro, 1, 1, 0, 2.1, kind="door")
    sesion.history.execute(cambio)
    puerta = next(e for e in sesion.export(None)["elements"] if e["ifc_class"] == "IfcDoor")
    geometria = modulo(plugin, "geom.vistas")
    if seccion:
        # La palanca está junto al extremo libre de la hoja: se corta por ella.
        camara = geometria.Camara((1.86, -1), (1.86, 1), (2, 0), seccion=True)
        resultado = geometria.vista([puerta], camara)
        anillos = [anillo for corte in resultado["cortes"] for anillo in corte["anillos"]]
        assert any(min(p[1] for p in anillo) == pytest.approx(1.044)
                   and max(p[1] for p in anillo) == pytest.approx(1.056) for anillo in anillos)
    else:
        camara = geometria.Camara((0, -1), (4, -1), (2, 0), seccion=False)
        resultado = geometria.vista([puerta], camara)
        assert any(abs(a[1] - 1.044) < 1e-7 or abs(a[1] - 1.056) < 1e-7
                   for a, b, identificador in resultado["vistos"])

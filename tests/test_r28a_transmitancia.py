# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: las áreas térmicas comparten la referencia del desarrollo y requieren valores físicos.
import pytest
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.escenarios_r27 import modulo


def test_u_curva_usa_la_misma_referencia_en_area_de_vidrio_y_hueco(plugin):
    geometria = modulo(plugin, "geom.junctions")
    muro = geometria.Wall("curvo", (0, 0), (6, 0), 0.3, "eje", bulge=0.3)
    memoria = modulo(plugin, "memoria_carpinteria")
    modelo = modulo(plugin, "memoria_modelo")
    registro = {
        "id": "ventana",
        "type": "window",
        "operation": "FIXED",
        "offset": 1.0,
        "width": 1.2,
        "height": 1.2,
        "sill": 0.9,
        "curve_mode": "curva",
        "width_reference": "eje",
    }
    eje = next(memoria.unidades(muro, registro))
    cara = next(memoria.unidades(muro, {**registro, "width_reference": "interior"}))
    assert cara["medidas"]["factor_s"] != 1.0
    biblioteca = {"vidrios": {"Vidrio": {"u": 1.0}}, "marcos": {"Aluminio": {"u": 2.0}}}
    assert modelo.transmitancia(eje, biblioteca) == pytest.approx(
        modelo.transmitancia(cara, biblioteca)
    )


@pytest.mark.parametrize("valor", [True, 0, -1, float("nan"), float("inf")])
def test_no_se_inventa_u_con_un_valor_no_fisico(plugin, valor):
    geometria = modulo(plugin, "geom.junctions")
    muro = geometria.Wall("muro", (0, 0), (8, 0), 0.3, "eje")
    registro = {
        "id": "ventana",
        "type": "window",
        "operation": "FIXED",
        "offset": 1.0,
        "width": 1.2,
        "height": 1.2,
        "sill": 0.9,
    }
    pieza = next(modulo(plugin, "memoria_carpinteria").unidades(muro, registro))
    biblioteca = {"vidrios": {"Vidrio": {"u": valor}}, "marcos": {"Aluminio": {"u": 2.0}}}
    assert modulo(plugin, "memoria_modelo").transmitancia(pieza, biblioteca) is None

# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: contrasta las manos que existen y las áreas térmicas en la referencia del desarrollo.
import pytest
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session
from tests.escenarios_r27 import modulo


def test_una_ventana_fija_y_un_hueco_no_tienen_mano(plugin):
    sesion = Session(plugin)
    herramienta = sesion.tool("MURO")
    herramienta.on_point((0, 0))
    herramienta.on_point((8, 0))
    herramienta.on_enter()
    muro = next(iter(sesion.walls().values()))
    arquitectura = modulo(plugin, "architectural_v10")
    sesion.history.execute(
        arquitectura.create_opening(muro, 1, 1.2, 0.9, 1.2, kind="window", operation="FIXED")
    )
    sesion.history.execute(arquitectura.create_opening(muro, 4, 1.0, 0.0, 2.1, kind="gap"))
    piezas = modulo(plugin, "memoria_modelo").leer(sesion.document.doc)
    assert len(piezas) == 2
    assert {pieza["mano"] for pieza in piezas} == {"sin mano"}


def test_las_manos_del_armario_se_cuentan_por_cada_frente(plugin):
    from collections import Counter

    sesion = Session(plugin)
    herramienta = sesion.tool("MURO")
    herramienta.on_point((0, 0))
    herramienta.on_point((8, 0))
    herramienta.on_enter()
    muro = next(iter(sesion.walls().values()))
    sesion.history.execute(
        modulo(plugin, "cabinets").create(
            muro, 1, 2.4, 0.6, 2.3, leaves=3, operation="SLIDING", mode="adosado", side=1
        )
    )
    piezas = modulo(plugin, "memoria_modelo").leer(sesion.document.doc)
    assert len(piezas) == 3
    assert Counter(pieza["mano"] for pieza in piezas) == {"izquierda": 2, "derecha": 1}

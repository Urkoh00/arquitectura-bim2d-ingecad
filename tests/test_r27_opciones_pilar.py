# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: las opciones anunciadas de PILAR se aceptan y no guardan números no finitos.
import pytest
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session


@pytest.mark.parametrize('opcion', ['Enganche', 'Rotación', 'Rotacion', 'Paramentos', 'Un paramento', 'Recubrimiento', 'Sección'])
def test_pilar_acepta_el_nombre_anunciado(plugin, opcion):
    sesion = Session(plugin)
    herramienta = sesion.tool('PILAR')
    assert herramienta.on_option(opcion) is True
    assert herramienta.pending is not None

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


@pytest.mark.parametrize('opcion', ['r', 'p', 'u'])
@pytest.mark.parametrize('entrada', ['nan', 'inf', '-inf'])
def test_pilar_no_conserva_valores_no_finitos(plugin, opcion, entrada):
    sesion = Session(plugin)
    herramienta = sesion.tool('PILAR')
    antes = (herramienta.values['rotation'], herramienta.d1, herramienta.d2, herramienta.mode)
    herramienta.on_option(opcion)
    herramienta.on_option(entrada)
    assert (herramienta.values['rotation'], herramienta.d1, herramienta.d2, herramienta.mode) == antes


def test_distancia_paramento_acepta_unidades(plugin):
    herramienta = Session(plugin).tool('PILAR')
    herramienta.on_option('p')
    herramienta.on_option('5cm 60mm')
    assert herramienta.mode == 'paramentos'
    assert herramienta.d1 == pytest.approx(.05)
    assert herramienta.d2 == pytest.approx(.06)

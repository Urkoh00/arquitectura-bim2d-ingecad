# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: las entradas inválidas de rejillas se avisan y permiten reintentar.
import copy
import pytest
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session


@pytest.mark.parametrize('orden', ['EJES', 'REJILLA'])
@pytest.mark.parametrize('entrada', ['x texto', 'x 0', 'x -1', 'y texto',
                                   'angulo texto', 'angulo nan', 'angulo inf'])
def test_rejilla_rechaza_entrada_sin_excepcion(plugin, orden, entrada):
    sesion = Session(plugin)
    herramienta = sesion.tool(orden)
    antes = copy.deepcopy(herramienta.values)
    assert herramienta.on_option(entrada)
    assert herramienta.values == antes
    assert len(sesion.document.doc.modelspace()) == 0
    assert herramienta.on_option('x 2x3')
    assert herramienta.on_option('y 1x4')
    herramienta.on_point((0., 0.))
    assert any(entidad.has_xdata('ARQINGECAD') for entidad in sesion.document.doc.modelspace())


@pytest.mark.parametrize('orden', ['EJES', 'REJILLA'])
def test_eje_suelto_nulo_permite_reintentar(plugin, orden):
    sesion = Session(plugin)
    herramienta = sesion.tool(orden)
    herramienta.on_option('suelto')
    herramienta.on_point((1., 2.))
    herramienta.on_point((1., 2.))
    assert len(sesion.document.doc.modelspace()) == 0
    herramienta.on_point((4., 2.))
    assert any(entidad.has_xdata('ARQINGECAD') for entidad in sesion.document.doc.modelspace())


@pytest.mark.parametrize('entrada', ['renumerar 0', 'renumerar -1', 'renumerar ?'])
def test_editar_eje_rechaza_numeracion_y_conserva_referencia(plugin, entrada):
    sesion = Session(plugin)
    rejilla = sesion.tool('EJES')
    rejilla.on_option('x 2x3')
    rejilla.on_option('y 1x4')
    rejilla.on_point((0., 0.))
    herramienta = sesion.tool('EDITAREJE')
    herramienta.on_point((0., 1.))
    assert herramienta.entity is not None
    entidad = herramienta.entity
    antes = copy.deepcopy(sesion.meta(entidad))
    assert herramienta.on_option(entrada)
    assert sesion.meta(entidad) == antes
    assert herramienta.entity is entidad
    assert herramienta.on_option('renumerar 2')
    assert sesion.meta(entidad)['id'] == antes['id']

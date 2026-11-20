# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: las herramientas antiguas dejan llegar las coordenadas al controlador y validan las medidas.
import pytest
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session


@pytest.mark.parametrize('orden', ['ARMARIO', 'PUERTA', 'VENTANA', 'ESCALERA', 'SUPERFICIE', 'CAMARA', 'VERTPOLY'])
def test_coordenada_escrita_no_es_una_palabra_clave(plugin, orden):
    sesion = Session(plugin)
    herramienta = sesion.tool(orden)
    assert herramienta.on_option('70,20') is False
    herramienta.on_point((70., 20.))


def test_medida_con_unidad_y_reintento_en_orden_antigua(plugin):
    sesion = Session(plugin)
    herramienta = sesion.tool('VENTANA')
    herramienta.on_option('ancho')
    herramienta.on_option('texto incorrecto')
    assert herramienta._arq_mode == 'number'
    herramienta.on_option('125cm')
    assert herramienta.width == 1.25
    assert herramienta._arq_mode == 'point'

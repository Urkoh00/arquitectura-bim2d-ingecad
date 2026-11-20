# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: los ejemplos de hipervínculo utilizan una ruta sintética sin productos ni lectores concretos.
import pytest
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session


@pytest.mark.parametrize('orden', ['HIPERVINCULO', 'URL'])
@pytest.mark.parametrize('opcion', ['ejemplo', 'archivo'])
def test_ejemplo_de_vinculo_es_generico_y_sintetico(plugin, orden, opcion):
    herramienta = Session(plugin).tool(orden)
    herramienta.on_option(opcion)
    assert herramienta.path == r'C:\Documentacion\producto_ejemplo.pdf'

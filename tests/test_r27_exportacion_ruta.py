# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: una ruta de exportación no escribible se informa sin interrumpir IngeCAD.
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session
from tests.test_r27_configuracion_texto import modulo
from types import SimpleNamespace


def test_exportar_ruta_inexistente_no_propaga_excepcion(plugin, tmp_path):
    sesion = Session(plugin)
    herramienta = sesion.tool('MURO')
    herramienta.on_point((0., 0.))
    herramienta.on_point((5., 0.))
    herramienta.on_enter()
    contexto = SimpleNamespace(document=sesion.document, echo=sesion.out.append, host=None, services=None)
    ruta = tmp_path / 'carpeta inexistente' / 'modelo.arqbim'
    assert modulo(plugin, 'bim_export').exportar_bim(contexto, str(ruta)) is None
    assert any('EXPORTARBIM:' in linea for linea in sesion.out)
    assert not ruta.exists()

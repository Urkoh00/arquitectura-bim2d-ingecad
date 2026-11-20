# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: BLOQUE conserva su pregunta si se pulsa el dibujo antes de elegir tipo.
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session


def test_bloque_punto_sin_tipo_no_modifica_el_dibujo(plugin):
    sesion = Session(plugin)
    herramienta = sesion.tool('BLOQUE')
    herramienta.on_point((2., 3.))
    assert len(sesion.document.doc.modelspace()) == 0
    assert sesion.history.depth == 0
    assert any('tipo' in texto.lower() for texto in sesion.out[-2:])
    herramienta.on_option('1')
    herramienta.on_point((2., 3.))
    assert len(sesion.document.doc.modelspace()) == 5

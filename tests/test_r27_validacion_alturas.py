# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: ARQVALIDAR compara el contorno por bandas de altura con el mismo motor que lo dibuja.
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_r27_configuracion_texto import modulo
from tests.test_wall_tools import Session


def test_alturas_distintas_no_producen_falsos_contornos_huerfanos(plugin):
    sesion = Session(plugin)
    herramienta = sesion.tool('MURO')
    for punto in [(0., 0.), (10., 0.), (10., 8.), (0., 8.), (0., 0.)]:
        herramienta.on_point(punto)
    herramienta.on_enter()
    assert not sesion.issues()
    entidad = next(iter(sesion.walls().values()))
    cambio = modulo(plugin, 'architectural_v10').edit_wall(entidad, height=3.5)
    modulo(plugin, 'transactions').apply_architectural_change(herramienta.ctx, cambio)
    assert not sesion.issues()
    sesion.history.undo()
    assert not sesion.issues()
    sesion.history.redo()
    assert not sesion.issues()

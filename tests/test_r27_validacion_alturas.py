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


def test_contornos_de_plantas_distintas_no_se_cuentan_como_duplicados(plugin):
    import uuid
    sesion = Session(plugin)
    herramienta = sesion.tool('MURO')
    herramienta.height = 7.
    herramienta.on_point((0., 0.))
    herramienta.on_point((5., 0.))
    herramienta.on_enter()
    niveles = modulo(plugin, 'levels')
    catalogo = niveles.load(sesion.document)
    catalogo['levels'].append({'id': uuid.uuid4().hex, 'name': 'Planta alta', 'elevation': 3.})
    niveles.apply(herramienta.ctx, catalogo)
    assert not sesion.issues()
    sesion.history.undo()
    assert not sesion.issues()
    sesion.history.redo()
    assert not sesion.issues()

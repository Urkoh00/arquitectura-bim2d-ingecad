# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: activar los niveles deja listos sus contornos sin necesitar una segunda regeneración.
from copy import deepcopy
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session
from tests.test_r27_configuracion_texto import modulo


def test_primera_activacion_de_niveles_regenera_y_se_deshace_en_un_paso(plugin):
    sesion = Session(plugin)
    muro = sesion.tool('MURO')
    muro.on_point((0., 0.))
    muro.on_point((5., 0.))
    muro.on_enter()
    niveles = modulo(plugin, 'levels')
    antes = deepcopy([sesion.meta(e) for e in sesion.document.doc.modelspace()])
    profundidad = sesion.history.depth
    niveles.apply(muro.ctx, niveles.load(sesion.document))
    despues = deepcopy([sesion.meta(e) for e in sesion.document.doc.modelspace()])
    assert sesion.history.depth == profundidad + 1
    nivel = niveles.load(sesion.document)['active']
    contornos = [r for r in despues if r and r.get('kind') == 'junction_edge']
    assert contornos
    assert all(r.get('display_level_id') == nivel for r in contornos)
    sesion.history.undo()
    assert [sesion.meta(e) for e in sesion.document.doc.modelspace()] == antes
    sesion.history.redo()
    assert [sesion.meta(e) for e in sesion.document.doc.modelspace()] == despues

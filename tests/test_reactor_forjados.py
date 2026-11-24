# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: con los reactores de IngeCAD 0.8, mover o copiar un forjado con las
#   órdenes de IngeCAD regenera al momento, igual que un muro (revisión del 24-11).
import pytest

from tests.test_ingecad_integration import plugin, reactor_on  # noqa: F401  (fixtures)
from tests.test_wall_tools import Session
from tests.test_r12_conversion import module

OUTER = [(0, 0), (6, 0), (6, 4), (0, 4)]


def _forjados(s):
    return [e for e in s.document.doc.modelspace() if (s.meta(e) or {}).get('kind') == 'slab']


def test_copiar_un_forjado_le_da_identidad_propia_al_momento(plugin, reactor_on):  # noqa: F811
    from core import actions
    s = Session(plugin)
    S = module(s, 'slabs')
    S.apply_new(s.tool('MURO').ctx, OUTER)
    forjado, = _forjados(s)
    s.history.execute(actions.copy_entities([forjado], 0.0, 20.0))
    ids = [s.meta(e)['id'] for e in _forjados(s)]
    assert len(ids) == 2 and len(set(ids)) == 2          # sin esperar a otra orden
    s.history.undo()
    assert len(_forjados(s)) == 1


def test_el_reactor_ve_los_forjados():
    """El reactor solo vigilaba polilíneas; un forjado es un sombreado."""
    import importlib
    R = importlib.import_module('arquitectura.reactor')
    assert 'slab' in R.KINDS


def test_un_muro_con_un_nivel_inexistente_no_impide_regenerar(plugin):  # noqa: F811
    """Revisión del 24-11: un muro restringido a un nivel que no existe (pegado
    desde otro dibujo) hacía fallar la regeneración de todo el dibujo."""
    s = Session(plugin)
    t = s.tool('MURO')
    for p in ((0, 0), (4, 0), (4, 3)):
        t.on_point(p)
    t.on_enter()
    arch = module(s, 'architectural')
    msp = s.document.doc.modelspace()
    muro = next(iter(s.walls().values()))
    m = dict(arch.metadata(muro))
    alto = m['height']
    m.update(height_constraint='level', level_id=m.get('level_id') or 'ninguno',
             top_level_id='nivel-de-otro-dibujo', top_offset=0.0)
    arch._xdata(msp, muro, m)
    regenerar = module(s, 'wall_network').RegenerateContoursCommand()
    s.history.execute(regenerar)                        # antes: ValueError
    nuevo = arch.metadata(muro)
    assert nuevo['height_constraint'] == 'fixed' and nuevo['height'] == pytest.approx(alto)
    assert 'top_level_id' not in nuevo
    assert any('inexistente' in n for n in regenerar.sync_notes)

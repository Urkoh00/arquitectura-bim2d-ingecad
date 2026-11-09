# SPDX-License-Identifier: GPL-3.0-or-later
"""LINEASAMURO on real plans (the user's old plans, 9-11-2026): layers that
say what each line is, the plan inside a block, party walls drawn with one
face, columns as closed outlines, cavity lines inside the walls, stairs
and dimensions that are not walls."""
import pytest

from arquitectura import convert_tools as CT
from tests.test_ingecad_integration import plugin  # noqa: F401  (fixture)
from tests.test_wall_tools import Session


def _plano(doc, target):
    """A narrow house between party walls, the way an office draws it:
    wall faces on Gpared (the party walls with their inner face only, the
    neighbour's boundary on Freferencia), a cavity on Fcamara inside the
    façade, a door on Fcarp, a column on Mpilar, stair treads on Fescalera
    (parallel lines 0,28 apart: not walls) and a dimension line."""
    for name in ('Gpared', 'Freferencia', 'Fcamara', 'Fcarp', 'Mpilar', 'Fescalera', 'Fcotas'):
        if name not in doc.layers:
            doc.layers.add(name)

    def line(a, b, layer):
        target.add_line(a, b, dxfattribs={'layer': layer})
    # rear wall 0,29 (both faces) and façade 0,30 with a 0,90 door at x 2,0–2,9
    line((0, 10.0), (5.0, 10.0), 'Gpared')
    line((0, 10.29), (5.0, 10.29), 'Gpared')
    for y in (0.0, 0.30):
        line((0, y), (2.0, y), 'Gpared')
        line((2.9, y), (5.0, y), 'Gpared')
    line((2.0, 0.0), (2.0, 0.30), 'Gpared')
    line((2.9, 0.0), (2.9, 0.30), 'Gpared')
    line((0.2, 0.18), (1.8, 0.18), 'Fcamara')        # the façade's cavity
    line((2.0, 0.30), (2.0, 1.20), 'Fcarp')           # door leaf
    target.add_arc((2.0, 0.30), 0.90, 0, 90, dxfattribs={'layer': 'Fcarp'})
    # party walls: inner face only on Gpared, the boundary 0,15 beyond
    line((0.15, 0.30), (0.15, 10.0), 'Gpared')
    line((0.0, 0.0), (0.0, 10.29), 'Freferencia')
    line((4.85, 0.30), (4.85, 10.0), 'Gpared')
    line((5.0, 0.0), (5.0, 10.29), 'Freferencia')
    # a column and a stair (treads 0,28 apart) and a dimension line
    target.add_lwpolyline([(2.3, 5.0), (2.6, 5.0), (2.6, 5.3), (2.3, 5.3)], close=True, dxfattribs={'layer': 'Mpilar'})
    for k in range(6):
        line((3.0, 6.0 + 0.28 * k), (4.5, 6.0 + 0.28 * k), 'Fescalera')
    line((0.0, -0.8), (5.0, -0.8), 'Fcotas')


def test_capas_reconocidas_por_su_nombre():
    present = {'Gpared': 9, 'Freferencia': 2, 'Fcamara': 1, 'Fcarp': 2, 'Mpilar': 1, 'Fescalera': 6}
    walls, cols, carp = CT.choose_layers(present)
    assert walls == {'Gpared'} and cols == {'Mpilar'} and carp == {'Fcarp'}
    assert CT.choose_layers({'0': 10})[0] is None                    # nada dice qué es: todas, como antes
    assert CT.choose_layers(present, walls=['gpared', 'Freferencia'])[0] == {'Gpared', 'Freferencia'}


@pytest.mark.parametrize('en_bloque', [False, True])
def test_vivienda_entre_medianeras(plugin, en_bloque):
    s = Session(plugin)
    doc = s.document.doc
    if en_bloque:                                       # the plan inside a block, as in the user's drawings
        blk = doc.blocks.new('PLANTA')
        _plano(doc, blk)
        doc.modelspace().add_blockref('PLANTA', (0, 0))
    else:
        _plano(doc, doc.modelspace())
    lo, hi = (-1, -1.5), (6, 11)
    wl, cl, kl = CT.choose_layers(CT.layers_in(doc, lo, hi))
    walls, ops, sources, curved, cols, unpaired, in_blocks = CT.detect_all(doc, lo, hi, 0.07, 0.5, wl, cl, kl)
    thick = sorted(round(t, 2) for _a, _b, t in walls)
    assert thick == [0.15, 0.15, 0.29, 0.30]             # 2 medianeras, fondo y fachada (con la puerta)
    assert [o[3] for o in ops] == ['door'] and len(cols) == 1
    assert not [f for f in unpaired if abs(f[2] - f[0]) + abs(f[3] - f[1]) > 1.0]
    assert (in_blocks > 0) == en_bloque and (not sources) == en_bloque   # a block is never changed


def test_la_orden_crea_muros_pilar_y_puerta_y_guarda_las_capas(plugin):
    s = Session(plugin)
    _plano(s.document.doc, s.document.doc.modelspace())
    t = s.tool('LINEASAMURO')
    t.on_option('p')
    t.on_option('0,02')
    t.on_point((-1, -1.5))
    t.on_point((6, 11))
    kinds = [(s.meta(e) or {}).get('kind') for e in s.document.doc.modelspace()]
    assert kinds.count('wall') >= 4 and kinds.count('column') == 1 and kinds.count('opening') == 1
    from arquitectura.parameters_arq import general_options
    assert general_options(s.document)['lineas']['paralelismo'] == pytest.approx(0.02)
    stairs = [e for e in s.document.doc.modelspace() if e.dxf.layer == 'Fescalera']
    assert len(stairs) == 6                              # the stair stays where it was

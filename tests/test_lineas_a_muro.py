# SPDX-License-Identifier: GPL-3.0-or-later
"""LINEASAMURO: un plano antiguo de líneas se convierte en muros y huecos BIM, sobre IngeCAD real."""
import math

import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401  (fixture)
from tests.test_recintos import _spaces
from tests.test_wall_tools import Session


def _plano(msp):
    """Vivienda de 8 × 5 m al eje, muros de 0,30, tabique de 0,10 en x = 4,
    una puerta de 0,885 en el muro sur (x 1,0–1,885, con su giro) y una
    ventana de 1,20 en el muro norte (x 5,35–6,55, con su vidrio)."""
    L = []

    def line(a, b):
        L.append(msp.add_line(a, b))
    # muro sur, cara exterior y = -0,15 e interior y = 0,15, con el hueco de la puerta
    for y in (-0.15, 0.15):
        x0 = -0.15 if y < 0 else 0.15
        x1 = 8.15 if y < 0 else 3.95
        line((x0, y), (1.0, y))
        line((1.885, y), (x1, y))
    line((4.05, 0.15), (7.85, 0.15))
    line((1.0, -0.15), (1.0, 0.15))
    line((1.885, -0.15), (1.885, 0.15))
    # muro norte con la ventana
    for y in (4.85, 5.15):
        x0 = -0.15 if y > 5 else 0.15
        x1 = 8.15 if y > 5 else 7.85
        if y < 5:
            line((x0, y), (3.95, y))
            line((4.05, y), (5.35, y))
            line((6.55, y), (x1, y))
        else:
            line((x0, y), (5.35, y))
            line((6.55, y), (x1, y))
    line((5.35, 4.85), (5.35, 5.15))
    line((6.55, 4.85), (6.55, 5.15))
    for y in (4.95, 5.0, 5.05):
        line((5.35, y), (6.55, y))
    # muros este y oeste
    line((-0.15, -0.15), (-0.15, 5.15))
    line((0.15, 0.15), (0.15, 4.85))
    line((8.15, -0.15), (8.15, 5.15))
    line((7.85, 0.15), (7.85, 4.85))
    # tabique
    line((3.95, 0.15), (3.95, 4.85))
    line((4.05, 0.15), (4.05, 4.85))
    # giro de la puerta: hoja y arco desde la bisagra (1,0; 0,15), abre hacia el interior
    line((1.0, 0.15), (1.0, 0.15 + 0.885))
    L.append(msp.add_arc((1.0, 0.15), 0.885, 0, 90))
    return L


def test_lineas_a_muros_y_huecos(plugin):
    s = Session(plugin)
    msp = s.document.doc.modelspace()
    origen = _plano(msp)
    t = s.tool('LINEASAMURO')
    t.on_point((-1, -1))
    t.on_point((9, 6))
    walls = s.walls()
    th = sorted(round(s.meta(w)['thickness'], 3) for w in walls.values())
    assert th == [0.1, 0.3, 0.3, 0.3, 0.3], s.out
    ops = [s.meta(e) for e in msp if (s.meta(e) or {}).get('kind') == 'opening']
    kinds = sorted(o['type'] for o in ops)
    assert kinds == ['door', 'window'], s.out
    door = next(o for o in ops if o['type'] == 'door')
    assert door['width'] == pytest.approx(0.885, abs=1e-6) and door['side'] == 1
    win = next(o for o in ops if o['type'] == 'window')
    assert win['width'] == pytest.approx(1.20, abs=1e-6)
    # las líneas de origen quedan en una capa apagada; el contorno nuevo está limpio
    assert all(e.dxf.layer == 'ARQ-PLANO-ORIGEN' for e in origen)
    assert s.document.doc.layers.get('ARQ-PLANO-ORIGEN').is_off()
    assert not [i for i in s.issues() if 'Contorno' in i], s.issues()
    # los muros detectados cierran estancias: el recinto mide lo mismo que dibujado a mano
    r = s.tool('RECINTO')
    r.on_point((2, 2))
    assert s.meta(_spaces(s)[0])['area'] == pytest.approx(3.8 * 4.7)
    # un solo deshacer devuelve el plano original
    s.history.undo()            # el recinto
    s.history.undo()            # la conversión
    assert not s.walls() and all(e.dxf.layer == '0' for e in origen)
    assert not math.isnan(0.0)

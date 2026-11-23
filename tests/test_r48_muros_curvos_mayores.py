# SPDX-License-Identifier: GPL-3.0-or-later
"""v1.48: muros curvos de más de media circunferencia, comprobados de punta a punta
(encuentros, sólidos, carpinterías, contrato) y las órdenes sobre arcos ejecutadas en
la sesión de IngeCAD. Complementa tests/test_muros_curvos_v2.py, que es de geometría pura."""
import math

import pytest
from shapely.geometry import Polygon
from shapely.ops import unary_union

from arquitectura.geom import curves as CV, junctions as J, solids as S, spaces as SP
from tests.test_c1_d2 import bridge
from tests.test_ingecad_integration import plugin  # noqa: F401  (fixture)
from tests.test_r12_conversion import module
from tests.test_solids import watertight
from tests.test_wall_tools import Session, draw


@pytest.mark.parametrize("grados", [200, 270, 340])
@pytest.mark.parametrize("signo", [1, -1])
def test_bahia_mayor_que_media_circunferencia(grados, signo):
    b = signo * math.tan(math.radians(grados) / 4)
    walls = [J.Wall("s", (0, 0), (4, 0), 0.2), J.Wall("arc", (4, 0), (0, 0), 0.25, bulge=b)]
    r = J.solve(walls)
    assert not r.warnings
    polys = [Polygon(pc) for g in r.walls.values() for pc in g["pieces"]]
    assert unary_union(polys).area == pytest.approx(sum(p.area for p in polys), abs=1e-9)
    c, rad, _t0, sweep = CV.arc_of((4, 0), (0, 0), b)
    room, why = SP.space_at(r, c)
    assert not why and room["area"] > 0
    assert r.walls["arc"]["area"] == pytest.approx(
        abs(sweep) / 2 * ((rad + .125) ** 2 - (rad - .125) ** 2), rel=5e-3)
    for w in walls:
        faces, vol = S.wall_solid(r.walls[w.id]["pieces"], w.a, w.u, 0.0, 2.7)
        assert watertight(faces) and vol == pytest.approx(r.walls[w.id]["area"] * 2.7)


@pytest.mark.parametrize("grados", [270, 340])
@pytest.mark.parametrize("fraccion", [0.15, 0.6, 0.85])
@pytest.mark.parametrize("modo", ["curva", "plana"])
def test_carpinteria_en_un_arco_mayor(plugin, tmp_path, grados, fraccion, modo):
    s = Session(plugin)
    A, T = module(s, 'architectural_v10'), module(s, 'transactions')
    P, O = module(s, 'geom.polygon'), module(s, 'openings')
    ctx = s.tool('MURO').ctx
    w = A.create_wall((4, 0), (0, 0), .3, 3., 0., 'eje', bulge=math.tan(math.radians(grados) / 4))
    T.apply_architectural_change(ctx, w)
    T.apply_architectural_change(ctx, A.create_wall((0, 0), (4, 0), .2, 3.))
    antes = {e['guid']: e for e in s.export(tmp_path)['elements'] if e['ifc_class'] == 'IfcWall'}
    spec = module(s, 'geom.junctions').walls_from_records([(s.meta(w.entity)['id'], s.meta(w.entity))])[0]
    op = A.create_opening(w.entity, spec.length * fraccion, 1.0, .9, 1.2, kind='window',
                          operation='FIXED' if modo == 'curva' else 'SLIDING', curve_mode=modo)
    T.apply_architectural_change(ctx, op, kind='opening')
    data = s.export(tmp_path)
    bridge().validate_contract(data)
    assert len([e for e in data['elements'] if e['ifc_class'] == 'IfcWindow']) == 1
    hueco = abs(P.area(O.cut_polygon(spec, s.meta(op.entity), 0.))) * 1.2
    despues = {e['guid']: e for e in data['elements'] if e['ifc_class'] == 'IfcWall'}
    assert sum(antes[g]['volume'] - despues[g]['volume'] for g in despues) == pytest.approx(hueco, abs=.003)


def _curvo(s, grados=120, r=4.0):
    A, T = module(s, 'architectural_v10'), module(s, 'transactions')
    t = math.radians(grados)
    w = A.create_wall((r, 0), (r * math.cos(t), r * math.sin(t)), .3, 3., 0., 'eje', bulge=math.tan(t / 4))
    T.apply_architectural_change(s.tool('MURO').ctx, w)
    return w


def _muros(s):
    return [s.meta(e) for e in s.walls().values()]


def test_muroparalelo_sobre_un_muro_curvo(plugin):
    s = Session(plugin)
    _curvo(s)
    t = s.tool('MUROPARALELO')
    for radio in (4.15, 6, 7):
        t.on_point((radio * math.cos(.5), radio * math.sin(.5)))
    muros = _muros(s)
    assert len(muros) == 2 and all(abs(m.get('bulge') or 0) > 0 for m in muros)
    assert any('radio 5.150' in o for o in s.out)


def test_muroparalelo_sobre_un_circulo(plugin):
    s = Session(plugin)
    c = s.document.doc.modelspace().add_circle((0, 0), 3.0)
    s.services.pick_entity = lambda p, radius=.05: c if abs(math.hypot(*p[:2]) - 3) < radius else None
    t = s.tool('MUROPARALELO')
    for x in (3.0, 5, 6):
        t.on_point((x, 0))
    muros = _muros(s)
    assert len(muros) == 2 and all(m['bulge'] == pytest.approx(1.0) for m in muros)


def test_dividemuro_radial_sobre_un_arco(plugin):
    s = Session(plugin)
    _curvo(s, 120, 4.0)
    t = s.tool('DIVIDEMURO')
    t.on_option('L')
    t.on_option('1.5')
    t.on_point((3.85 * math.cos(.2), 3.85 * math.sin(.2)))
    t.on_point((3.85 * math.cos(1.9), 3.85 * math.sin(1.9)))
    nuevo = next(m for m in _muros(s) if not m.get('bulge'))
    a, b = nuevo['a'], nuevo['b']
    assert math.atan2(a[1], a[0]) == pytest.approx(1.05, abs=1e-6)        # radial, en el centro del arco
    assert math.atan2(b[1], b[0]) == pytest.approx(1.05, abs=1e-6)
    assert math.dist(a, b) == pytest.approx(1.5)


def test_muro_en_l_contra_un_muro_curvo(plugin):
    s = Session(plugin)
    _curvo(s, 120, 4.0)
    draw(s.tool('MURO'), (0, 0), (4.15 * math.cos(1.0), 4.15 * math.sin(1.0)))
    curvo = next(m for m in _muros(s) if m.get('bulge'))
    assert abs(curvo['bulge']) < math.tan(math.radians(120) / 4)            # recortado en la L

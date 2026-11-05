# SPDX-License-Identifier: GPL-3.0-or-later
"""Fase 2 — geometría de los gestos de dibujo, contrastada con el motor de
encuentros y con shapely como oráculo independiente."""
import math

import pytest
from shapely.geometry import Polygon, box
from shapely.affinity import rotate
from shapely.ops import unary_union

from arquitectura.geom import drafting as D
from arquitectura.geom import junctions as J

REFS = ("eje", "izquierda", "derecha")


def _rec(i, a, b, t, ref):
    return (i, {"a": list(a), "b": list(b), "thickness": t, "reference": ref, "height": 2.7})


def _solve(*recs):
    return J.solve(J.walls_from_records(list(recs)), [])


def _union(result):
    polys = []
    for g in result.walls.values():
        for outer, holes in g["loops"]:
            polys.append(Polygon(outer, holes))
    return unary_union(polys), sum(p.area for p in polys)


def _strip(frame, s0, s1):
    """Shapely polygon of the wall strip between s0 and s1 (any order)."""
    s0, s1 = sorted((s0, s1))
    return Polygon([frame.point(s0, frame.lo), frame.point(s1, frame.lo),
                    frame.point(s1, frame.hi), frame.point(s0, frame.hi)])


# --- T / L ---------------------------------------------------------------------

def test_cara_proxima_es_T():
    host = ((0, 0), (10, 0), 0.30, "eje")
    g = D.end_gesture((5, 4), (5, 0.15), 0.20, "eje", host, "hi")
    assert g == {"kind": "T"}


@pytest.mark.parametrize("ref_h", REFS)
@pytest.mark.parametrize("ref_n", REFS)
@pytest.mark.parametrize("angle", [90, 60, 120, 45])
def test_cara_alejada_es_L_exacta(ref_h, ref_n, angle):
    th, tn = 0.30, 0.20
    host = ((0.0, 0.0), (10.0, 0.0), th, ref_h)
    hf = D.Frame(*host)
    # the new wall comes from above (positive o side) and ends on the FAR face
    far_side, far_off = ("lo", hf.lo)
    x_axis = hf.axis_point(6.0)
    ang = math.radians(angle)
    start = (x_axis[0] + 4 * math.cos(ang), x_axis[1] + 4 * math.sin(ang))
    # a point of the far face along the new direction (what the user clicks)
    end = D.line_intersection(start, (math.cos(ang), math.sin(ang)), hf.point(0, far_off), hf.u)
    # the user draws the REFERENCE line: shift start/end to the reference of the new wall
    nf0 = D.Frame(start, end, tn, "eje")
    shift = D._mul(nf0.n, -D.offsets(tn, ref_n)[0] - tn / 2) if ref_n != "eje" else (0.0, 0.0)
    start_r, end_r = D._add(start, shift), D._add(end, shift)
    g = D.end_gesture(start_r, end_r, tn, ref_n, host, far_side)
    assert g["kind"] == "L" and g["kept"] == "start"            # 6 m > 4 m
    r = _solve(_rec("H", g["host_a"], g["host_b"], th, ref_h),
               _rec("N", start_r, g["new_end"], tn, ref_n))
    assert not r.tees and not r.warnings, (r.tees, r.warnings)
    assert any(set(n["walls"]) == {"H", "N"} for n in r.nodes)
    union, total = _union(r)
    assert total == pytest.approx(union.area, abs=1e-9)          # sin solapes
    # L ideal (oráculo independiente con shapely): franja del anfitrión desde
    # su inicio hasta la cara EXTERIOR del nuevo muro (la más lejana del
    # tramo conservado) y franja del nuevo hasta la cara alejada del anfitrión.
    nf = D.Frame(start_r, g["new_end"], tn, ref_n)
    o_keep = nf.local(hf.a)[1]
    outer = nf.hi if abs(nf.hi - o_keep) > abs(nf.lo - o_keep) else nf.lo
    host_part = _strip(hf, 0.0, 50.0).intersection(_halfplane(nf.point(0, outer), nf.u, hf.a))
    new_part = _strip(nf, 0.0, 50.0).intersection(_halfplane(hf.point(0, far_off), hf.u, start_r))
    ideal = unary_union([host_part, new_part])
    assert union.symmetric_difference(ideal).area < 1e-7


def _halfplane(p, d, keep):
    """Half-plane bounded by the line p + λd, on the side of ``keep``."""
    n = (-d[1], d[0])
    if (keep[0] - p[0]) * n[0] + (keep[1] - p[1]) * n[1] < 0:
        n = (-n[0], -n[1])
    big = 200.0
    return Polygon([(p[0] - d[0] * big, p[1] - d[1] * big), (p[0] + d[0] * big, p[1] + d[1] * big),
                    (p[0] + d[0] * big + n[0] * big, p[1] + d[1] * big + n[1] * big),
                    (p[0] - d[0] * big + n[0] * big, p[1] - d[1] * big + n[1] * big)])


def test_L_conserva_la_parte_mas_larga():
    host = ((0, 0), (10, 0), 0.30, "eje")
    g = D.end_gesture((2, 4), (2, -0.15), 0.20, "eje", host, "lo")
    assert g["kind"] == "L" and g["kept"] == "end"
    assert g["host_a"] == pytest.approx((2, 0)) and g["host_b"] == pytest.approx((10, 0))
    assert g["new_end"] == pytest.approx((2, 0))


def test_L_rasante_rechazada():
    """Por debajo de 5° no hay esquina posible: se rechaza con un mensaje."""
    host = ((0, 0), (20, 0), 0.30, "eje")
    with pytest.raises(ValueError):
        D.end_gesture((0, 0.3), (10, -0.15), 0.2, "eje", host, "lo")


def test_huecos_se_desplazan_o_impiden_el_corte():
    ops = [{"offset": 6.0, "width": 0.8}]
    assert D.shift_openings(ops, 2.0, 8.0)[0]["offset"] == pytest.approx(4.0)
    with pytest.raises(ValueError):
        D.shift_openings([{"offset": 1.0, "width": 0.8}], 2.0, 8.0)


# --- alargar / recortar / pivotar ---------------------------------------------

def test_alargar_hasta_linea_y_recortar():
    a, b = D.extend_to_line((0, 0), (4, 0), 1, (6, -1), (6, 1))
    assert b == pytest.approx((6, 0)) and a == (0, 0)
    a, b = D.extend_to_line((0, 0), (4, 0), 1, (3, -1), (3, 1))   # recorta
    assert b == pytest.approx((3, 0))
    with pytest.raises(ValueError):
        D.extend_to_line((0, 0), (4, 0), 1, (-1, -1), (-1, 1))      # cruzaría el extremo fijo
    with pytest.raises(ValueError):
        D.extend_to_line((0, 0), (4, 0), 1, (0, 1), (5, 1))         # paralela


def test_alargar_hasta_cara_produce_T():
    host = _rec("H", (0, 0), (10, 0), 0.3, "eje")
    a, b = D.extend_to_line((5, 4), (5, 2), 1, (0, 0.15), (10, 0.15))
    r = _solve(host, _rec("N", a, b, 0.2, "eje"))
    assert r.tees and r.walls["N"]["area"] == pytest.approx(0.2 * (4 - 0.15))


def test_pivotar_un_extremo():
    assert D.move_end((0, 0), (4, 0), 1, (4, 3)) == ((0, 0), (4, 3))
    with pytest.raises(ValueError):
        D.move_end((0, 0), (4, 0), 1, (0, 0))


# --- muro paralelo --------------------------------------------------------------

@pytest.mark.parametrize("side_y,ref", [(1.0, "izquierda"), (-1.0, "derecha")])
def test_paralelo_a_distancia(side_y, ref):
    a, b, r = D.parallel_wall((0, 0), (5, 0), 1.2, (2.0, side_y), 0.1)
    assert r == ref
    f = D.Frame(a, b, 0.1, r)
    near = min(abs(f.local((2.5, 0))[1] - f.lo), abs(f.local((2.5, 0))[1] - f.hi))
    assert near == pytest.approx(1.2)                       # cara próxima a 1,20 m
    far = max(abs(f.local((2.5, 0))[1] - f.lo), abs(f.local((2.5, 0))[1] - f.hi))
    assert far == pytest.approx(1.3)


def test_paralelo_dentro_de_recinto_con_T_en_ambos_extremos():
    """Recinto 5 x 4 m de muros de 0,30 al eje; tabique de 0,10 paralelo a la
    cara interior del muro sur, a 1,50 m. Sus extremos tocan las caras
    interiores de los muros este y oeste (también si éstos son oblicuos)."""
    walls = {"S": ((0, 0), (5, 0), 0.3, "eje"), "E": ((5, 0), (5.6, 4), 0.3, "eje"),
             "N": ((5.6, 4), (0, 4), 0.3, "eje"), "O": ((0, 4), (0, 0), 0.3, "eje")}
    recs = [_rec(k, *v) for k, v in walls.items()]
    base = _solve(*recs)
    face = next((a, b) for a, b, w in J.plan_outline(base)
                if w == ["S"] and abs(a[1] - 0.15) < 1e-9 and abs(b[1] - 0.15) < 1e-9)
    a, b, ref = D.parallel_wall(face[0], face[1], 1.5, (2.5, 2.0), 0.10)
    a, b = D.extend_to_faces(a, b, walls, max_gap=0.5)
    r = _solve(*recs, _rec("P", a, b, 0.10, ref))
    assert len([t for t in r.tees if t["wall"] == "P"]) == 2, r.tees
    union, total = _union(r)
    assert total == pytest.approx(union.area, abs=1e-9)
    # el tabique llena exactamente el ancho interior a esa altura: sin huecos
    inner = Polygon([(0.15, 0.15), (4.85 + 0.15 * 0, 0.15), (5.6 - 0.15 * 4 / math.hypot(0.6, 4) * 0, 3.85),
                     (0.15, 3.85)])
    assert r.walls["P"]["area"] > 0
    strip = Polygon([(-1, 1.65), (10, 1.65), (10, 1.75), (-1, 1.75)])
    room = unary_union([Polygon(o, h) for g in base.walls.values() for o, h in g["loops"]])
    hull = Polygon([(-0.15, -0.15), (5.15 + 0.0, -0.15), (5.75, 4.15), (-0.15, 4.15)])
    free = strip.difference(room)
    free = free.intersection(Polygon([(0, 0), (5, 0), (5.6, 4), (0, 4)]))
    assert union.intersection(strip).area == pytest.approx(
        room.intersection(strip).area + free.area, abs=1e-7)

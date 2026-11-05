"""Parametric junction tests. Oracle: shapely (independent implementation).

Every case checks: (1) footprints never overlap (sum of areas == area of the
union), (2) the union equals the ideal plan built independently with
shapely, (3) no warnings."""
import math
import sys

import pytest

from shapely.geometry import LineString, Polygon          # noqa: E402
from shapely.ops import unary_union                       # noqa: E402

from arquitectura.geom import junctions as J              # noqa: E402
from tests.oracle import check                            # noqa: E402

W = J.Wall


def pol(deg, r):
    return (r * math.cos(math.radians(deg)), r * math.sin(math.radians(deg)))


def face(w, off):
    """Shapely line of a face, long enough to intersect anything nearby."""
    lo, hi = J.offsets(w.thickness, w.reference)
    p0 = w.point(-100, off)
    p1 = w.point(w.length + 100, off)
    return LineString([p0, p1])


def meet(l1, l2):
    q = l1.intersection(l2)
    return (q.x, q.y)


def ideal_L(wa, wb):
    """wa ends at N, wb starts at N. Corner polygon built from face lines."""
    inner = meet(face(wa, wa.hi), face(wb, wb.hi))
    outer = meet(face(wa, wa.lo), face(wb, wb.lo))
    # orientation-agnostic: the L polygon is a's start, the two corners, b's end
    poly = [wa.point(0, wa.lo), outer, wb.point(wb.length, wb.lo),
            wb.point(wb.length, wb.hi), inner, wa.point(0, wa.hi)]
    p = Polygon(poly)
    if not p.is_valid:
        p = p.buffer(0)
    return p


# turn angle at the corner; interior angle = 180 - turn (170 -> 10° acute)
ANGLES = [90, 45, 30, 10, 120, 135, 150, 160, 165, 170]
THICK = [(0.30, 0.30), (0.15, 0.30), (0.45, 0.15)]


@pytest.mark.parametrize("ang", ANGLES)
@pytest.mark.parametrize("ta,tb", THICK)
def test_L(ang, ta, tb):
    N = (0.0, 0.0)
    A = (-5.0, 0.0)
    B = pol(ang, 4.0)
    wa = W("a", A, N, ta, order=0)
    wb = W("b", N, B, tb, order=1)
    r = J.solve([wa, wb])
    ok, msg, U = check(r, ideal_L(wa, wb), f"L {ang}° {ta}/{tb}")
    assert ok, msg
    assert not r.warnings, r.warnings


@pytest.mark.parametrize("ang", [90, 60, 45, 30, 20, 15])
@pytest.mark.parametrize("th,tb", [(0.30, 0.30), (0.45, 0.15), (0.15, 0.45)])
def test_T_on_axis(ang, th, tb):
    host = W("h", (-6, 0), (6, 0), th, order=0)
    tip = (0.7, 0.0)
    far = (tip[0] + 5 * math.cos(math.radians(ang)), 5 * math.sin(math.radians(ang)))
    br = W("b", far, tip, tb, order=1)
    r = J.solve([host, br])
    ideal = ideal_T(host, br)
    ok, msg, _ = check(r, ideal, f"T {ang}° {th}/{tb}")
    assert ok, msg
    assert r.tees and r.tees[0]["host"] == "h"
    # the through wall keeps its whole strip
    assert abs(r.walls["h"]["area"] - host.length * th) < 1e-9


@pytest.mark.parametrize("ang", [90, 60, 30])
def test_T_to_face(ang):
    """Branch drawn to the host's near face (common when snapping to a line)."""
    host = W("h", (-6, 0), (6, 0), 0.30, order=0)
    tip = (0.0, 0.15)
    far = (5 * math.cos(math.radians(ang)), 0.15 + 5 * math.sin(math.radians(ang)))
    br = W("b", far, tip, 0.20, order=1)
    r = J.solve([host, br])
    ideal = ideal_T(host, br)
    ok, msg, _ = check(r, ideal, f"T-cara {ang}°")
    assert ok, msg


def ideal_T(host, br):
    """Host strip + branch strip prolonged through the host, cut at the
    host's FAR face (a T never pokes out on the other side)."""
    long = Polygon([br.point(0, br.lo), br.point(br.length + 50, br.lo),
                    br.point(br.length + 50, br.hi), br.point(0, br.hi)])
    # half-plane on the branch side of the far face (host here is along +x)
    side = 1 if br.a[1] > 0 else -1
    far_y = host.lo if side > 0 else host.hi
    half = Polygon([(-1e3, far_y), (1e3, far_y), (1e3, side * 1e3), (-1e3, side * 1e3)])
    return unary_union([Polygon(host.strip()), long.intersection(half)])


def _wedge_to_face(br, host):
    """Region between the branch's square tip and the host's near face."""
    near = face(host, host.hi)
    q1 = meet(face(br, br.lo), near)
    q2 = meet(face(br, br.hi), near)
    return Polygon([br.point(br.length, br.lo), q1, q2, br.point(br.length, br.hi)]).buffer(0)


@pytest.mark.parametrize("ang", [90, 60, 30])
@pytest.mark.parametrize("ta,tb", [(0.30, 0.30), (0.45, 0.15)])
def test_X(ang, ta, tb):
    w1 = W("1", (-5, 0), (5, 0), ta, order=0)
    d = pol(ang, 5)
    w2 = W("2", (-d[0], -d[1]), d, tb, order=1)
    r = J.solve([w1, w2])
    ideal = unary_union([Polygon(w1.strip()), Polygon(w2.strip())])
    ok, msg, _ = check(r, ideal, f"X {ang}°")
    assert ok, msg
    # the thicker (or first) wall keeps its whole strip
    assert abs(r.walls["1"]["area"] - 10 * ta) < 1e-9


@pytest.mark.parametrize("angles", [(0, 120, 240), (0, 90, 180), (0, 90, 180, 270), (10, 100, 225)])
def test_star_node(angles):
    walls = [W(str(i), (0, 0), pol(a, 4), 0.25, order=i) for i, a in enumerate(angles)]
    r = J.solve(walls)
    # ideal hub: polygon of face-line corners between angular neighbours
    corners = []
    for i, a in enumerate(angles):
        b = angles[(i + 1) % len(angles)]
        wi, wj = walls[i], walls[(i + 1) % len(angles)]
        if (b - a) % 360 == 180:
            continue
        corners.append(meet(face(wi, wi.hi), face(wj, wj.lo)))
    parts = [Polygon(w.strip()) for w in walls]
    if len(corners) >= 3:
        parts.append(Polygon(corners).convex_hull)
    ideal = unary_union(parts)
    ok, msg, _ = check(r, ideal, f"nodo {angles}")
    assert ok, msg


def test_collinear_step():
    """Two collinear walls of different thickness meeting end to end."""
    w1 = W("1", (0, 0), (5, 0), 0.30, order=0)
    w2 = W("2", (5, 0), (10, 0), 0.15, order=1)
    r = J.solve([w1, w2])
    ideal = unary_union([Polygon(w1.strip()), Polygon(w2.strip())])
    ok, msg, _ = check(r, ideal, "colineal escalón")
    assert ok, msg


def test_face_references():
    """Rectangle drawn on the INNER faces (reference izquierda, ccw)."""
    pts = [(0, 0), (10, 0), (10, 8), (0, 8)]
    walls = [W(str(i), pts[i], pts[(i + 1) % 4], 0.3, "derecha", order=i) for i in range(4)]
    r = J.solve(walls)
    ideal = Polygon([(-.3, -.3), (10.3, -.3), (10.3, 8.3), (-.3, 8.3)],
                    [[(0, 0), (10, 0), (10, 8), (0, 8)]])
    ok, msg, _ = check(r, ideal, "referencia cara")
    assert ok, msg


def test_no_proximity_join():
    """Two walls 5 cm apart must NOT be joined."""
    w1 = W("1", (0, 0), (5, 0), 0.3, order=0)
    w2 = W("2", (5.2, 0.5), (5.2, 4), 0.3, order=1)
    r = J.solve([w1, w2])
    assert not r.nodes and not r.tees
    assert abs(r.walls["1"]["area"] - 1.5) < 1e-12


def test_column_inside_wall():
    w = W("1", (0, 0), (6, 0), 0.30)
    col = [(2.85, -0.15), (3.15, -0.15), (3.15, 0.15), (2.85, 0.15)]
    r = J.solve([w], [("c", col)])
    assert abs(r.walls["1"]["area"] - (1.8 - 0.09)) < 1e-12
    assert len(r.walls["1"]["loops"]) == 2      # wall split in two parts


def test_column_bigger_than_wall_is_hole_free():
    w = W("1", (0, 0), (6, 0), 0.20)
    col = [(2.8, -0.2), (3.2, -0.2), (3.2, 0.2), (2.8, 0.2)]
    r = J.solve([w], [("c", col)])
    ok, msg, U = check(r, None, "pilar")
    assert ok, msg
    assert abs(U.area - (1.2 - 0.08 + 0.16)) < 1e-12

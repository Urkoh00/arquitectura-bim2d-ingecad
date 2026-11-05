"""3D solids built from the SAME footprints as the plan: watertight, exact
volume, no internal faces, holes for windows."""
import sys
import pytest
from arquitectura.geom import junctions as J, solids as S, polygon as P

def edge_counts(faces):
    c = {}
    k = lambda v: tuple(round(x, 9) for x in v)
    for o, hs in faces:
        for l in (o, *hs):
            for i in range(len(l)):
                a, b = k(l[i]), k(l[(i+1) % len(l)])
                c[(a, b)] = c.get((a, b), 0) + 1
    return c

def watertight(faces):
    c = edge_counts(faces)
    # every directed edge used once and matched by its reverse once
    return all(n == 1 and c.get((b, a)) == 1 for (a, b), n in c.items())

def rect(t=0.3, H=2.7):
    pts = [(0,0),(10,0),(10,8),(0,8)]
    return [J.Wall(str(i), pts[i], pts[(i+1)%4], t, order=i) for i in range(4)]

def test_room_volume_equals_plan_area_times_height():
    walls = rect(); r = J.solve(walls)
    total = 0
    for w in walls:
        faces, vol = S.wall_solid(r.walls[w.id]['pieces'], w.a, w.u, 0, 2.7)
        assert watertight(faces)
        assert abs(S.face_volume(faces) - vol) < 1e-9
        assert abs(vol - r.walls[w.id]['area'] * 2.7) < 1e-9
        total += vol
    # R1 of the audit: 2D 10.80 m2 vs 3D 10.71 m2 -> now identical
    assert abs(total - 10.8 * 2.7) < 1e-9

@pytest.mark.parametrize('openings', [
    [dict(offset=2, width=0.9, sill=0, height=2.1)],                     # door
    [dict(offset=2, width=1.2, sill=0.9, height=1.2)],                   # window
    [dict(offset=1, width=0.8, sill=0, height=2.1), dict(offset=4, width=1.5, sill=1.0, height=1.0)],
    [dict(offset=1, width=0.8, sill=0, height=2.7)],                     # full-height gap
])
def test_wall_with_openings(openings):
    walls = rect(); r = J.solve(walls); w = walls[0]
    faces, vol = S.wall_solid(r.walls[w.id]['pieces'], w.a, w.u, 0.0, 2.7, openings)
    assert watertight(faces)
    voids = sum(o['width'] * o['height'] * w.thickness for o in openings)
    assert abs(vol - (r.walls[w.id]['area'] * 2.7 - voids)) < 1e-9
    assert abs(S.face_volume(faces) - vol) < 1e-9
    # windows produce a face with a hole on each side of the wall
    if any(o['sill'] > 0 for o in openings):
        assert sum(1 for _o, hs in faces if hs) >= 2

def test_oblique_L_watertight():
    import math
    wa = J.Wall('a', (-5, 0), (0, 0), 0.3)
    wb = J.Wall('b', (0, 0), (4*math.cos(math.radians(30)), 4*math.sin(math.radians(30))), 0.15, order=1)
    r = J.solve([wa, wb])
    for w in (wa, wb):
        faces, vol = S.wall_solid(r.walls[w.id]['pieces'], w.a, w.u, 0.5, 3.0)
        assert watertight(faces)
        assert abs(S.face_volume(faces) - vol) < 1e-9

def test_column_prism():
    faces, vol = S.prism_solid([(0,0),(0.3,0),(0.3,0.3),(0,0.3)], 0, 3)
    assert watertight(faces) and abs(vol - 0.27) < 1e-12 and len(faces) == 6

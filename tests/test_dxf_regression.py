"""Regression on the user's real DXF files, read with the plugin's own
metadata() and solved with the new engine."""
from pathlib import Path
import sys
import ezdxf, pytest
from shapely.geometry import Polygon
from arquitectura.architectural import metadata
from arquitectura.geom import junctions as J
from tests.oracle import check

D = str(Path(__file__).resolve().parent / 'dxf') + '/'

def load(name):
    doc = ezdxf.readfile(D + name)
    walls, cols = [], []
    for e in doc.modelspace():
        m = metadata(e) or {}
        if m.get('kind') == 'wall':
            walls.append((m['id'], m))
        elif m.get('kind') == 'column':
            cols.append((m['id'], [tuple(p) for p in e.get_points('xy')]))
    return J.walls_from_records(walls), cols

def ring(x0, y0, x1, y1, t):
    h = t / 2
    return Polygon([(x0-h,y0-h),(x1+h,y0-h),(x1+h,y1+h),(x0-h,y1+h)],
                   [[(x0+h,y0+h),(x1-h,y0+h),(x1-h,y1-h),(x0+h,y1-h)]])

@pytest.mark.parametrize('name,rings,nwalls,ncols', [
    ('34.dxf', [(15,5,35,20)], 4, 6),
    ('35.dxf', [(10,5,25,25),(35,5,50,25)], 8, 0),
    ('36.dxf', [(10,5,25,25),(35,5,50,25)], 8, 0),
])
def test_real(name, rings, nwalls, ncols):
    walls, cols = load(name)
    assert len(walls) == nwalls and len(cols) == ncols
    r = J.solve(walls, cols)
    from shapely.ops import unary_union
    ideal = unary_union([ring(*q, 0.3) for q in rings] + [Polygon(c) for _i, c in cols])
    ok, msg, U = check(r, ideal, name)
    print(msg, '| nodos', len(r.nodes), '| T', len(r.tees), '| avisos', r.warnings)
    assert ok, msg
    assert not r.warnings
    segs = J.plan_outline(r)
    # 4 outer + 4 inner lines per enclosure: the case validated in v1.4.2
    assert len(segs) == 8 * len(rings), len(segs)
    assert all(len(ids) == 1 for _a, _b, ids in segs)

"""Independent checks with shapely (test-only dependency, never shipped)."""
import math
from shapely.geometry import Polygon, LineString
from shapely.ops import unary_union

def wall_polys(res):
    out={}
    for wid,g in res.walls.items():
        out[wid]=unary_union([Polygon(p) for p in g['pieces']])
    return out

def check(res, expected_union=None, label=''):
    polys=wall_polys(res)
    cols=[Polygon(p) for p in res.columns.values()]
    allp=list(polys.values())+cols
    total=sum(p.area for p in allp)
    U=unary_union(allp)
    overl=total-U.area
    ok=abs(overl)<1e-7
    msg=f"{label}: suma={total:.6f} union={U.area:.6f} solape={overl:.2e}"
    if expected_union is not None:
        sym=U.symmetric_difference(expected_union).area
        msg+=f" difsim_vs_esperado={sym:.2e}"
        ok=ok and sym<1e-7
    return ok,msg,U

def strip(a,b,t):
    return LineString([a,b]).buffer(t/2,cap_style=2,join_style=2)

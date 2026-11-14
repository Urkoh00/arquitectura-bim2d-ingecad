# SPDX-License-Identifier: GPL-3.0-or-later
import math
import pytest
from shapely.geometry import Polygon
from shapely.ops import unary_union
from arquitectura.geom import polygon as P


@pytest.mark.parametrize('poly',[
 [(0,0),(5,0),(5,1),(1,1),(1,4),(0,4)],
 [(0,0),(5,0),(5,4),(4,4),(4,1),(1,1),(1,4),(0,4)],
 [(0,0),(2,0),(2,1e-8),(1,1e-8),(1,2),(0,2)],
 [(500000,4200000),(500005,4200000),(500005,4200001),(500001,4200001),(500001,4200004),(500000,4200004)],
 [(0,0),(2,0),(4,0),(4,2),(0,2),(0,0)],
])
def test_convex_parts_preserve_area_and_orientation(poly):
    pieces=P.triangulate(poly)
    assert pieces and all(P.area(p)>0 for p in pieces)
    combined=unary_union([Polygon(p) for p in pieces]);expected=Polygon(poly)
    assert combined.symmetric_difference(expected).area<1e-7
    assert sum(Polygon(p).area for p in pieces)==pytest.approx(expected.area,abs=1e-7)


def test_hole_is_subtraction_not_triangulate_argument():
    outer=[(0,0),(6,0),(6,4),(0,4)];hole=[(2,1),(4,1),(4,3),(2,3)]
    pieces=P.subtract([outer],hole);combined=unary_union([Polygon(p) for p in pieces])
    assert combined.area==pytest.approx(20.) and not combined.covers(Polygon(hole).representative_point())

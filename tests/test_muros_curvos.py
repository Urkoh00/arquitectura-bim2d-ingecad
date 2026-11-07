# SPDX-License-Identifier: GPL-3.0-or-later
"""Curved walls: the same footprint for plan, rooms and 3D; true arcs in the
plan; MUROCURVO, CURVAMURO and the drawing as the authority (bulge)."""
import math

import pytest
from shapely.geometry import Polygon
from shapely.ops import unary_union

from arquitectura.geom import curves as CV
from arquitectura.geom import junctions as J
from arquitectura.geom import solids as S
from arquitectura.geom import spaces as SP
from tests.test_ingecad_integration import plugin  # noqa: F401  (fixture)
from tests.test_solids import watertight
from tests.test_wall_tools import Session, draw


def _tiles(r):
    polys = [Polygon(pc) for g in r.walls.values() for pc in g["pieces"]]
    return sum(p.area for p in polys), unary_union(polys), unary_union([p.buffer(1e-9) for p in polys])


def _bay():
    return [J.Wall("a", (0, 0), (4, 0), 0.2), J.Wall("b", (4, 0), (4, 3), 0.2),
            J.Wall("c", (4, 3), (0, 3), 0.2), J.Wall("d", (0, 3), (0, 0), 0.2, bulge=1.0)]


def test_arco_desde_bulge_y_punto_de_paso():
    c, r, _t0, sweep = CV.arc_of((0, 3), (0, 0), 1.0)
    assert c == pytest.approx((0, 1.5)) and r == pytest.approx(1.5) and sweep == pytest.approx(math.pi)
    assert CV.bulge_through((0, 3), (0, 0), (-1.5, 1.5)) == pytest.approx(1.0)
    assert CV.bulge_through((0, 0), (4, 0), (2, 1)) == pytest.approx(-0.5)       # to the left: clockwise
    assert CV.bulge_from_sagitta((0, 0), (4, 0), 1.0) == pytest.approx(-0.5)
    assert CV.bulge_through((0, 0), (4, 0), (2, 0)) == 0.0
    w = J.Wall("x", (0, 0), (4, 0), 0.3, bulge=-0.5)
    s, off = w.local(w.point(1.234, 0.1))
    assert (s, off) == pytest.approx((1.234, 0.1))
    with pytest.raises(ValueError):
        J.Wall("x", (0, 0), (0.2, 0), 0.3, bulge=1.0)          # radius 0,10 < half thickness


def test_mirador_semicircular_huella_unica():
    walls = _bay()
    r = J.solve(walls)
    assert not r.warnings and [n["degree"] for n in r.nodes] == [2, 2, 2, 2]
    tot, union, joined = _tiles(r)
    assert union.area == pytest.approx(tot, abs=1e-9)                     # no overlap
    half_annulus = math.pi / 2 * (1.6 ** 2 - 1.4 ** 2)
    assert r.walls["d"]["area"] == pytest.approx(half_annulus, rel=2e-3)   # chords of ≤ 1 mm
    room, why = SP.space_at(r, (2, 1.5))
    assert not why
    assert room["area"] == pytest.approx(3.9 * 2.8 + math.pi / 2 * 1.4 ** 2, rel=1e-3)
    items = J.plan_items(r)
    arcs = [it for it in items if it[0] == "arc"]
    assert sorted(round(it[2], 6) for it in arcs) == [1.4, 1.6]
    assert all(it[5] == ["d"] for it in arcs)
    for w in walls:                                                        # 3D from the same pieces
        faces, vol = S.wall_solid(r.walls[w.id]["pieces"], w.a, w.u, 0.0, 2.7)
        assert watertight(faces)
        assert vol == pytest.approx(r.walls[w.id]["area"] * 2.7)


@pytest.mark.parametrize("walls", [
    [J.Wall("arc", (-3, 0), (3, 0), 0.3, bulge=-0.5), J.Wall("t", (0, -3), (0, 1.5), 0.15)],   # T into a curve
    [J.Wall("p", (0, 0), (4, 0), 0.25, bulge=0.3), J.Wall("q", (4, 0), (4, 4), 0.25, bulge=-0.3)],  # two curves
    [J.Wall("p", (0, 0), (4, 0), 0.25, "izquierda", bulge=0.4), J.Wall("q", (4, 0), (4, 4), 0.25, "izquierda")],
    [J.Wall("a", (0, 0), (3, 0), 0.2), J.Wall("b", (3, 0), (5, 2), 0.2, bulge=0.3),
     J.Wall("c", (3, 0), (3, -3), 0.2)],                                                       # three walls
])
def test_encuentros_curvos_sin_solapes_ni_huecos(walls):
    r = J.solve(walls)
    assert not r.warnings
    tot, union, joined = _tiles(r)
    assert union.area == pytest.approx(tot, abs=1e-9)
    assert joined.geom_type == "Polygon"                     # one connected body: no gap at the joins
    for g in r.walls.values():
        assert len(g["loops"]) == 1


def test_cruce_de_recto_y_curvo():
    walls = [J.Wall("a", (0, 0), (4, 0), 0.2, bulge=0.5), J.Wall("b", (2, -3), (2, 1), 0.2)]
    r = J.solve(walls)
    tot, union, joined = _tiles(r)
    assert union.area == pytest.approx(tot, abs=1e-9) and joined.geom_type == "Polygon"
    assert len(r.walls["a"]["loops"]) == 1 and len(r.walls["b"]["loops"]) == 2     # the crossing owns the hub


def test_muro_curvo_dibujado_validado_y_exportado(plugin, tmp_path):
    s = Session(plugin)
    m = s.tool("MURO")
    m.thickness, m.reference = 0.2, "eje"
    draw(m, (0, 3), (4, 3), (4, 0), (0, 0))
    c = s.tool("MUROCURVO")
    c.thickness = 0.2
    c.on_point((0, 0))
    c.on_point((0, 3))
    c.on_point((-1.5, 1.5))                       # through: a half circle to the left
    assert any("radio 1,5 m" in o for o in s.out)
    from importlib import import_module
    a = import_module(s.plugin.tools["PILAR"].__module__.rsplit(".", 1)[0] + ".architectural")
    curved = [e for e in s.walls().values() if s.meta(e).get("bulge")]
    assert len(curved) == 1 and s.meta(curved[0])["bulge"] == pytest.approx(-1.0)
    assert curved[0].get_points("xyb")[0][2] == pytest.approx(-1.0)          # a true arc in the axis
    edges = [e for e in s.document.doc.modelspace() if (a.metadata(e) or {}).get("kind") == "junction_edge"]
    assert sum(1 for e in edges if e.dxftype() == "ARC") == 2
    assert not s.issues()
    data = s.export(tmp_path)
    w = next(e for e in data["elements"] if e["params"].get("bulge"))
    assert w["quantities"]["Length"] == pytest.approx(math.pi * 1.5)
    assert w["params"]["radius"] == pytest.approx(1.5)
    assert w["quantities"]["NetVolume"] == pytest.approx(w["quantities"]["GrossFootprintArea"] * 2.7)
    r = s.tool("RECINTO")
    r.on_point((2, 1.5))
    data = s.export(tmp_path)
    sp = next(e for e in data["elements"] if e["ifc_class"] == "IfcSpace")
    assert sp["quantities"]["NetFloorArea"] == pytest.approx(3.9 * 2.8 + math.pi / 2 * 1.4 ** 2, rel=1e-3)


def test_curvamuro_curva_endereza_y_deshace(plugin):
    s = Session(plugin)
    m = s.tool("MURO")
    m.thickness, m.reference = 0.2, "eje"
    draw(m, (0, 0), (6, 0))
    wall = next(iter(s.walls().values()))
    t = s.tool("CURVAMURO")
    t.on_point((3, 0.1))                                  # pick the wall by its face
    t.on_option("1,2")                                    # 1,20 m to the left
    meta = s.meta(wall)
    assert meta["bulge"] == pytest.approx(-0.4)
    assert J.walls_from_records([(meta["id"], meta)])[0].point(3.0 * 0 + J.walls_from_records(
        [(meta["id"], meta)])[0].length / 2, 0) == pytest.approx((3, 1.2))
    t.on_point((3, 1.3))                                  # its outer face, now an arc
    t.on_option("0")                                      # straight again
    assert "bulge" not in s.meta(wall) and wall.get_points("xyb")[0][2] == 0
    s.history.undo()
    assert s.meta(wall)["bulge"] == pytest.approx(-0.4)
    assert wall.get_points("xyb")[0][2] == pytest.approx(-0.4)


def test_edicion_de_extremos_rechazada_en_curvos(plugin):
    s = Session(plugin)
    c = s.tool("MUROCURVO")
    c.on_point((0, 0))
    c.on_point((6, 0))
    c.on_option("1")
    assert len(s.walls()) == 1
    e = s.tool("ESTIRAMURO")
    e.on_point((3, 0.85))
    assert any("ESTIRAMURO: aún no trabaja con muros curvos" in o for o in s.out)


def _curved_room(s):
    m = s.tool("MURO")
    m.thickness, m.reference = 0.3, "eje"
    draw(m, (0, 0), (0, -4), (8, -4), (8, 0))
    c = s.tool("MUROCURVO")
    c.thickness = 0.3
    c.on_point((8, 0))
    c.on_point((0, 0))
    c.on_point((4, 2))                    # radius 5, sweep 106°; axis top at (4, 2)
    return next(e for e in s.walls().values() if s.meta(e).get("bulge"))


def test_carpinterias_en_muro_curvo(plugin, tmp_path):
    """A planar door and window on the chord between radial jambs: plan hole,
    symbols, 3D and IFC from the same record."""
    from importlib import import_module
    s = Session(plugin)
    wall = _curved_room(s)
    meta = s.meta(wall)
    spec = J.walls_from_records([(meta["id"], meta)])[0]
    v = s.tool("VENTANAARQ")
    v.on_option("n")
    v.on_option("1,20")
    v.on_option("m")
    v.on_option("c")                      # centred on the face clicked
    v.on_point(spec.point(spec.length / 2, spec.hi))     # centred on the outer (convex) face
    p = s.tool("PUERTAARQ")
    p.on_point(spec.point(1.5, spec.lo))
    p.on_point(spec.point(3.0, spec.lo))
    ops = [s.meta(e) for e in s.document.doc.modelspace() if (s.meta(e) or {}).get("kind") == "opening"]
    assert sorted(o["type"] for o in ops) == ["door", "window"], s.out[-6:]
    win = next(o for o in ops if o["type"] == "window")
    door = next(o for o in ops if o["type"] == "door")
    assert win["chord"] == pytest.approx(1.20) and win["width"] > 1.20         # along the arc
    assert door["chord"] == pytest.approx(0.885) and door["leaf"] == pytest.approx(0.825)
    assert not s.issues(), s.issues()
    arqm = import_module(s.plugin.tools["PILAR"].__module__.rsplit(".", 1)[0] + ".architectural")
    sym = [e for e in s.document.doc.modelspace() if (arqm.metadata(e) or {}).get("kind") == "opening_symbol"]
    assert sym
    data = s.export(tmp_path)
    w = next(e for e in data["elements"] if e["params"].get("bulge"))
    assert len(w["openings"]) == 2
    voids = sum(o["width"] * o["height"] * 0.3 for o in ops)             # radial sector ≈ arc × t
    assert w["quantities"]["NetVolume"] == pytest.approx(w["quantities"]["GrossVolume"] - voids, rel=2e-3)
    fills = [e for e in data["elements"] if e["ifc_class"] in ("IfcDoor", "IfcWindow")]
    assert sorted(round(f["quantities"]["Width"], 3) for f in fills) == [0.885, 1.2]
    # the planar body lies inside the curved wall (within the 1 mm chord tolerance)
    body = unary_union([Polygon(pc) for pc in J.solve(
        J.walls_from_records([(meta["id"], meta)])).walls[meta["id"]]["pieces"]]).buffer(1e-3)
    from shapely.geometry import MultiPoint
    for f in fills:
        pts = [(x, y) for fc in f["faces"] for x, y, _z in fc["outer"]]
        assert body.contains(MultiPoint(pts).convex_hull)


def test_carpinteria_demasiado_ancha_para_la_curva(plugin):
    s = Session(plugin)
    c = s.tool("MUROCURVO")
    c.thickness = 0.1
    c.on_point((0, 0))
    c.on_point((2, 0))
    c.on_point((1, 1))                    # a half circle of radius 1
    wall = next(iter(s.walls().values()))
    spec = J.walls_from_records([(s.meta(wall)["id"], s.meta(wall))])[0]
    v = s.tool("VENTANAARQ")
    v.on_option("n")
    v.on_option("1,20")
    v.on_option("m")
    v.on_option("c")
    v.on_point(spec.point(spec.length / 2, spec.hi))
    assert any("demasiado ancha para la curvatura" in o for o in s.out), s.out[-4:]


def test_simetria_del_eje_invierte_la_curva(plugin):
    """The CAD axis is the authority: an axis whose arc was reversed by a
    generic edit (MIRROR) gives the wall the new curve on UNIONESARQ."""
    s = Session(plugin)
    c = s.tool("MUROCURVO")
    c.on_point((0, 0))
    c.on_point((6, 0))
    c.on_option("1")
    wall = next(iter(s.walls().values()))
    wall.set_points([(0, 0, 0.3333), (6, 0, 0)], format="xyb")
    s.plugin.commands["UNIONESARQ"](_ctx(s))
    assert s.meta(wall)["bulge"] == pytest.approx(0.3333)


def _ctx(s):
    from tests.test_recintos import _cmd_ctx
    return _cmd_ctx(s)

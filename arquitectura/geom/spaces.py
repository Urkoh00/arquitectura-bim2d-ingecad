# SPDX-License-Identifier: GPL-3.0-or-later
"""Spaces (rooms) from the junction engine's footprints.

The footprints of walls and columns tile without overlaps (junctions.solve).
Their union is one or more components; each HOLE of a component is a room,
closed by the very faces of the walls around it (doors do not open a room:
openings cut the 3D wall, not its footprint). Islands (a free-standing
column, an inner core) are the other components lying inside a hole.

A space is identified by a SEED point the user clicked inside the room, so
it is associative: when walls move, the space is recomputed from its seed.
Pure Python, no dependencies; the same polygons feed the plan and the IFC.
"""
from __future__ import annotations

import math

from . import polygon as P


def _all_pieces(result):
    pieces = [pc for g in result.walls.values() for pc in g["pieces"]]
    for poly in result.columns.values():
        pieces.extend(P.convex_parts(poly))
    return pieces


def components(result):
    """[(outer_ccw, [holes_cw])] of the union of every footprint."""
    return P.merge(_all_pieces(result))


def _inside(pt, poly):
    return P.point_in_polygon(pt, poly)


def _perimeter(loop):
    return sum(math.dist(a, b) for a, b in zip(loop, loop[1:] + loop[:1]))


def space_at(result, seed, comps=None):
    """The room containing ``seed``: a dict with ``outer`` (ccw), ``holes``
    (islands, cw), ``pieces`` (convex, for solids), ``area`` and
    ``perimeter``; or ``(None, reason)`` with reason "muro" (the seed lies
    inside a wall or column) or "abierto" (it is not enclosed)."""
    comps = comps if comps is not None else components(result)
    seed = (float(seed[0]), float(seed[1]))
    for outer, holes in comps:
        if _inside(seed, outer) and not any(_inside(seed, h) for h in holes):
            return None, "muro"
    best = None
    for outer, holes in comps:
        for h in holes:
            if _inside(seed, h):
                a = abs(P.area(h))
                if best is None or a < best[0]:          # the innermost hole
                    best = (a, h)
    if best is None:
        return None, "abierto"
    room = P.ccw(list(best[1]))
    islands = [o for o, _hs in comps if o is not room and _inside(P._interior_probe(o), room)
               and abs(P.area(o)) < abs(P.area(room))]
    pieces = P.convex_parts(room)
    for isl in islands:
        pieces = P.subtract(pieces, isl)
    area = sum(P.area(x) for x in pieces)
    holes = [list(reversed(P.ccw(list(i)))) for i in islands]
    return {"outer": room, "holes": holes, "pieces": pieces, "area": area,
            "perimeter": _perimeter(room) + sum(_perimeter(h) for h in holes)}, ""


def external_walls(result, outline=None, tol=1e-7):
    """Ids of the walls that have a face on the OUTER boundary of a
    component: the building envelope (IsExternal). Holes are rooms or
    courtyards and do not make a wall external by themselves."""
    from .junctions import plan_outline
    outline = outline if outline is not None else plan_outline(result)
    rings = [o for o, _hs in components(result)]
    segs = [(a, b) for r in rings for a, b in zip(r, r[1:] + r[:1])]
    out = set()
    for a, b, owners in outline:
        m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        if any(_on_segment(m, p, q, tol) for p, q in segs):
            out.update(owners)
    return out


def _on_segment(m, p, q, tol):
    d = P.sub(q, p)
    L2 = P.dot(d, d)
    if L2 == 0:
        return math.dist(m, p) <= tol
    t = P.dot(P.sub(m, p), d) / L2
    if t < -1e-9 or t > 1 + 1e-9:
        return False
    return abs(P.cross(d, P.sub(m, p))) / math.sqrt(L2) <= tol

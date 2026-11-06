# SPDX-License-Identifier: GPL-3.0-or-later
"""Wall junction engine: ONE constructive footprint per element.

Pure Python, no IngeCAD/IngeTrazo imports, so the same module computes the
plan outline (IngeCAD) and the solids sent to IngeTrazo: the 2D drawing and
the 3D model cannot disagree because they are the same polygons.

Pipeline (each step explicit and testable):

1. **Topology.** Wall ends are grouped into *nodes*: ends closer than
   ``tol`` (on the reference lines or on the axes) and pairs of ends that lie in each other's strip near their tips
   (the drawn-to-the-face corner of ``35.dxf``). An end that lands inside
   another wall's strip away from a node is a **T** into that host. Every
   other end is free. Nothing is joined by mere proximity: ``tol`` is 1 mm
   by default and only identifies the same point.
2. **Corners.** At a node the incident walls are sorted by angle and each
   pair of neighbours meets at the intersection of their facing faces (exact
   for any angle, thickness and axis reference). Every wall's cap passes
   through the node point, so the hub is shared without gaps or overlaps.
   A corner farther than ``miter_limit`` times the thickness (very acute
   angles) falls back to a square cut. A T end is extended to the host's
   far face. A free end is cut square.
3. **Ownership.** Remaining overlaps (T ends, X crossings, columns) are
   given to exactly one element: column > wall; in a T the through wall
   wins; otherwise ``join_priority``, then thickness, then drawing order.
   The loser is clipped. Result: footprints that tile without overlap, so
   areas and volumes add up and nothing is counted twice.

Units are metres; the wall axis stored in BIM is never modified.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import polygon as P

DEFAULT_TOL = 1e-3          # m: same-point tolerance (1 mm)
DEFAULT_MIN_ANGLE = 5.0     # degrees: below this two walls are treated as parallel
DEFAULT_MITER_LIMIT = 6.0   # corner distance / thickness before a square cut


def offsets(thickness, reference="eje"):
    t = float(thickness)
    if reference == "izquierda":
        return 0.0, t
    if reference == "derecha":
        return -t, 0.0
    return -t / 2.0, t / 2.0


@dataclass
class Wall:
    id: str
    a: tuple
    b: tuple
    thickness: float
    reference: str = "eje"
    priority: int = 0
    order: int = 0

    def __post_init__(self):
        self.a = (float(self.a[0]), float(self.a[1]))
        self.b = (float(self.b[0]), float(self.b[1]))
        d = P.sub(self.b, self.a)
        self.length = math.hypot(*d)
        if self.length < 1e-6:
            raise ValueError(f"Muro {self.id}: extremos coincidentes")
        self.u = (d[0] / self.length, d[1] / self.length)
        self.n = (-self.u[1], self.u[0])
        self.lo, self.hi = offsets(self.thickness, self.reference)

    def point(self, s, off):
        return (self.a[0] + self.u[0] * s + self.n[0] * off,
                self.a[1] + self.u[1] * s + self.n[1] * off)

    def local(self, p):
        r = P.sub(p, self.a)
        return P.dot(r, self.u), P.dot(r, self.n)

    def face_line(self, off):
        return self.point(0.0, off), self.u

    def strip(self):
        return [self.point(0, self.lo), self.point(self.length, self.lo),
                self.point(self.length, self.hi), self.point(0, self.hi)]


@dataclass
class End:
    w: int
    which: int          # 0 = start (a), 1 = end (b)
    p: tuple
    e: tuple            # unit direction from the tip INTO the wall body


@dataclass
class Result:
    walls: dict = field(default_factory=dict)      # id -> {"pieces", "loops", "area"}
    columns: dict = field(default_factory=dict)    # id -> polygon
    nodes: list = field(default_factory=list)      # report
    tees: list = field(default_factory=list)
    clips: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def walls_from_records(records):
    """[(id, info)] as stored in XDATA -> [Wall]; order kept as drawing order."""
    out = []
    for i, (ident, info) in enumerate(records):
        out.append(Wall(ident, tuple(info["a"][:2]), tuple(info["b"][:2]),
                        float(info["thickness"]), info.get("reference", "eje") or "eje",
                        int(info.get("join_priority", 0) or 0), i))
    return out


class _DSU:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, i):
        while self.p[i] != i:
            self.p[i] = self.p[self.p[i]]
            i = self.p[i]
        return i

    def union(self, i, j):
        self.p[self.find(i)] = self.find(j)


def _sin(u, v):
    return abs(P.cross(u, v))


def solve(walls, columns=(), tol=DEFAULT_TOL, min_angle=DEFAULT_MIN_ANGLE,
          miter_limit=DEFAULT_MITER_LIMIT):
    """Compute non-overlapping footprints. ``columns`` = [(id, polygon)]."""
    res = Result()
    sin_min = math.sin(math.radians(min_angle))
    ends = []
    for i, w in enumerate(walls):
        ends.append(End(i, 0, w.a, w.u))
        ends.append(End(i, 1, w.b, (-w.u[0], -w.u[1])))

    # ---- 1. topology -------------------------------------------------------------------
    dsu = _DSU(len(ends))
    # the same point, measured on the drawn reference lines OR on the axes:
    # two walls drawn by different faces meet in a corner when their AXES
    # end at the same point (that is how the L drawing gesture writes them)
    axis_end = [walls[e.w].point(0.0 if e.which == 0 else walls[e.w].length,
                                 (walls[e.w].lo + walls[e.w].hi) / 2) for e in ends]
    for i in range(len(ends)):
        for j in range(i + 1, len(ends)):
            if ends[i].w != ends[j].w and (math.dist(ends[i].p, ends[j].p) <= tol
                                           or math.dist(axis_end[i], axis_end[j]) <= tol):
                dsu.union(i, j)
    # corners drawn to the face (each tip inside the other's strip, near its tip)
    for i in range(len(ends)):
        for j in range(i + 1, len(ends)):
            ei, ej = ends[i], ends[j]
            if ei.w == ej.w or dsu.find(i) == dsu.find(j):
                continue
            wi, wj = walls[ei.w], walls[ej.w]
            s = _sin(wi.u, wj.u)
            if s < sin_min:
                continue
            reach = (wi.thickness + wj.thickness) / s + tol
            if math.dist(ei.p, ej.p) > reach:
                continue
            if _in_strip(ei.p, wj, tol) and _in_strip(ej.p, wi, tol) \
                    and _near_tip(ei.p, ej, wj, reach) and _near_tip(ej.p, ei, wi, reach):
                dsu.union(i, j)
    clusters = {}
    for i in range(len(ends)):
        clusters.setdefault(dsu.find(i), []).append(i)

    cap = {}           # (w, which) -> dict(left=, right=, hub=[...])
    node_of = {}
    for members in clusters.values():
        if len(members) < 2 or len({ends[k].w for k in members}) < 2:
            continue
        node = _node_point([ends[k] for k in members], walls, tol, sin_min)
        for k in members:
            node_of[k] = node
        _node_corners([ends[k] for k in members], walls, node, miter_limit, cap)
        res.nodes.append({"point": node, "walls": sorted({walls[ends[k].w].id for k in members}),
                          "degree": len(members)})

    tee_host = {}
    for k, en in enumerate(ends):
        if k in node_of:
            continue
        w = walls[en.w]
        best = None
        for v_i, v in enumerate(walls):
            if v_i == en.w or _sin(w.u, v.u) < sin_min:
                continue
            s, off = v.local(en.p)
            if not (v.lo - tol <= off <= v.hi + tol and -tol <= s <= v.length + tol):
                continue
            corners = _tee_corners(en, w, v, miter_limit)
            if corners is None:
                continue
            rank = (v.priority, v.thickness, -v.order)
            if best is None or rank > best[0]:
                best = (rank, v_i, corners)
        if best is not None:
            _rank, v_i, (left, right) = best
            cap[(en.w, en.which)] = {"left": left, "right": right, "hub": []}
            tee_host[(en.w, en.which)] = v_i
            res.tees.append({"wall": w.id, "end": en.which, "host": walls[v_i].id})

    # ---- 2. raw footprints -------------------------------------------------------------
    raw = []
    for i, w in enumerate(walls):
        c0 = cap.get((i, 0)) or {"left": w.point(0, w.hi), "right": w.point(0, w.lo), "hub": []}
        c1 = cap.get((i, 1)) or {"left": w.point(w.length, w.hi),
                                 "right": w.point(w.length, w.lo), "hub": []}
        poly = [c0["right"], c1["right"], *c1["hub"], c1["left"], c0["left"], *c0["hub"]]
        poly = P.dedupe(poly)
        if len(poly) < 3 or P.area(poly) <= P.EPS_AREA or not _simple(poly):
            res.warnings.append(f"Muro {w.id}: encuentro degenerado, se usa corte recto")
            poly = w.strip()
        raw.append(P.dedupe(P.ccw(poly)))

    # ---- 3. ownership ------------------------------------------------------------------
    pieces = [P.convex_parts(p) for p in raw]
    for cid, cpoly in columns:
        cpoly = P.dedupe(P.ccw([tuple(map(float, q[:2])) for q in cpoly]))
        res.columns[cid] = cpoly
        for i in range(len(walls)):
            before = sum(P.area(x) for x in pieces[i])
            pieces[i] = P.subtract(pieces[i], cpoly)
            lost = before - sum(P.area(x) for x in pieces[i])
            if lost > 1e-9:
                res.clips.append({"loser": walls[i].id, "winner": cid, "area": lost})
    hosts = {(w_i, v_i) for (w_i, _), v_i in tee_host.items()}
    for i in range(len(walls)):
        for j in range(i + 1, len(walls)):
            ov = P.overlap_area(pieces[i], pieces[j])
            if ov <= 1e-9:
                continue
            if (i, j) in hosts:
                win, lose = j, i
            elif (j, i) in hosts:
                win, lose = i, j
            else:
                ri = (walls[i].priority, walls[i].thickness, -walls[i].order)
                rj = (walls[j].priority, walls[j].thickness, -walls[j].order)
                win, lose = (i, j) if ri >= rj else (j, i)
            for wp in pieces[win]:
                nxt = []
                for lp in pieces[lose]:
                    nxt.extend(P.convex_difference(lp, wp))
                pieces[lose] = nxt
            res.clips.append({"loser": walls[lose].id, "winner": walls[win].id, "area": ov})

    for i, w in enumerate(walls):
        loops = P.merge(pieces[i])
        a = sum(P.area(x) for x in pieces[i])
        if a <= P.EPS_AREA:
            res.warnings.append(f"Muro {w.id}: queda sin superficie propia")
        res.walls[w.id] = {"pieces": pieces[i], "loops": loops, "area": a}
    return res


def _in_strip(p, wall, tol):
    _s, off = wall.local(p)
    return wall.lo - tol <= off <= wall.hi + tol


def _near_tip(p, tip_end, wall, reach):
    s, _off = wall.local(p)
    tip_s = 0.0 if tip_end.which == 0 else wall.length
    return abs(s - tip_s) <= reach


def _node_point(members, walls, tol, sin_min):
    pts = [m.p for m in members]
    if max(math.dist(pts[0], q) for q in pts) <= tol:
        return pts[0]
    for x in range(len(members)):
        for y in range(x + 1, len(members)):
            wx, wy = walls[members[x].w], walls[members[y].w]
            if _sin(wx.u, wy.u) >= sin_min:
                # The hub is where the AXES cross, never where the reference
                # lines cross: with a face reference that point lies ON a
                # face, the cap folds back along it and the footprint breaks
                # (found 2026-11-06 with an L drawn by its faces).
                q = P.line_intersection(wx.point(0, (wx.lo + wx.hi) / 2), wx.u,
                                        wy.point(0, (wy.lo + wy.hi) / 2), wy.u)
                if q is not None:
                    return q
    return pts[0]


def _faces_in_end_frame(en, w, node):
    """(m, left_line_point, right_line_point) in the frame looking from the
    node INTO the wall body; left/right are the wall's own hi/lo faces."""
    e = en.e
    m = (-e[1], e[0])                      # left of e
    c0 = P.dot(m, P.sub(w.a, node))        # axis offset from the node, along m
    # m == n at the start of the wall and m == -n at its end
    left_off, right_off = (w.hi, w.lo) if en.which == 0 else (-w.lo, -w.hi)
    left = P.add(node, P.mul(m, left_off + c0))
    right = P.add(node, P.mul(m, right_off + c0))
    return e, left, right


def _node_corners(members, walls, node, miter_limit, cap):
    frames = []
    for en in members:
        w = walls[en.w]
        e, left, right = _faces_in_end_frame(en, w, node)
        frames.append((math.atan2(e[1], e[0]), en, w, e, left, right))
    frames.sort(key=lambda f: f[0])
    n = len(frames)
    corner_left = {}
    corner_right = {}
    for idx in range(n):
        _ang, en_k, w_k, e_k, left_k, _r = frames[idx]
        _ang2, en_j, w_j, e_j, _l, right_j = frames[(idx + 1) % n]
        if en_k is en_j:
            continue
        q = P.line_intersection(left_k, e_k, right_j, e_j)
        limit = miter_limit * max(w_k.thickness, w_j.thickness)
        if q is None or math.dist(q, node) > limit:
            corner_left[id(en_k)] = left_k
            corner_right[id(en_j)] = right_j
        else:
            corner_left[id(en_k)] = q
            corner_right[id(en_j)] = q
    for _ang, en, w, e, left, right in frames:
        lft = corner_left.get(id(en), left)
        rgt = corner_right.get(id(en), right)
        # translate end-frame left/right back to the wall's u-frame (hi/lo)
        if en.which == 0:
            cap[(en.w, 0)] = {"left": lft, "right": rgt, "hub": [node]}
        else:
            cap[(en.w, 1)] = {"left": rgt, "right": lft, "hub": [node]}


def _tee_corners(en, w, host, miter_limit):
    """Extend the end of ``w`` to the far face of ``host`` (returned in the
    wall's u-frame as (left=hi, right=lo)), or None if too oblique."""
    side = P.dot(en.e, host.n)
    far = host.lo if side > 0 else host.hi
    q0, d = host.face_line(far)
    left = P.line_intersection(w.point(0, w.hi), w.u, q0, d)
    right = P.line_intersection(w.point(0, w.lo), w.u, q0, d)
    if left is None or right is None:
        return None
    limit = miter_limit * max(w.thickness, host.thickness)
    if math.dist(left, en.p) > limit + host.thickness or math.dist(right, en.p) > limit + host.thickness:
        return None
    return left, right


def _simple(poly):
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            c, d = poly[j], poly[(j + 1) % n]
            if _seg_cross(a, b, c, d):
                return False
    return True


def _seg_cross(a, b, c, d):
    d1 = P.cross(P.sub(b, a), P.sub(c, a))
    d2 = P.cross(P.sub(b, a), P.sub(d, a))
    d3 = P.cross(P.sub(d, c), P.sub(a, c))
    d4 = P.cross(P.sub(d, c), P.sub(b, c))
    eps = 1e-12
    return ((d1 > eps and d2 < -eps) or (d1 < -eps and d2 > eps)) and \
           ((d3 > eps and d4 < -eps) or (d3 < -eps and d4 > eps))


# -- plan outline --------------------------------------------------------------------------

def plan_outline(result, cuts=None):
    """Visible plan lines: boundary of walls+columns, minus column edges
    (columns keep their own outline). Each segment carries its wall id(s):
    [(a, b, [wall_id])]. Collinear pieces of the same wall are merged.

    ``cuts`` {wall id: [polygon]}: the holes of its doors/windows. They are
    removed from that wall only, so its faces stop at the hole and the
    jambs («mochetas») appear; rooms and 3D keep the uncut footprint."""
    pieces, tags = [], []
    cuts = cuts or {}
    for wid, g in result.walls.items():
        own = list(g["pieces"])
        for poly in cuts.get(wid, ()):
            own = P.subtract(own, P.ccw(list(poly)))
        for pc in own:
            pieces.append(pc)
            tags.append(("wall", wid))
    for cid, poly in result.columns.items():
        for pc in P.convex_parts(poly):
            pieces.append(pc)
            tags.append(("column", cid))
    edges = [e for e in P.boundary_edges(pieces, tags) if e[2][0] == "wall"]
    # merge collinear contiguous edges with the same owner
    groups = {}
    for a, b, tag in edges:
        d = P.sub(b, a)
        ln = math.hypot(*d)
        u = (d[0] / ln, d[1] / ln)
        if u[0] < -1e-12 or (abs(u[0]) <= 1e-12 and u[1] < 0):
            u = (-u[0], -u[1])
            a, b = b, a
        off = round(P.cross(u, a), 7)
        k = (tag, round(u[0], 7), round(u[1], 7), off)
        groups.setdefault(k, []).append((P.dot(a, u), P.dot(b, u), a, b))
    out = []
    for (tag, *_), segs in groups.items():
        segs.sort()
        cur = list(segs[0])
        for s0, s1, a, b in segs[1:]:
            if s0 <= cur[1] + 1e-9:
                if s1 > cur[1]:
                    cur[1], cur[3] = s1, b
            else:
                out.append((cur[2], cur[3], [tag[1]]))
                cur = [s0, s1, a, b]
        out.append((cur[2], cur[3], [tag[1]]))
    return out

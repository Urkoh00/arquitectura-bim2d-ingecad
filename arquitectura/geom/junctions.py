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

Curved walls (``bulge`` ≠ 0) go through the same three steps: their
faces are concentric circles, a corner is where two faces really cross (a
line and a circle, or two circles: ``geom.curves``), and the footprint
follows each curved face between its corners in chords of at most
``curves.CHORD`` from the arc.

Units are metres; the wall axis stored in BIM is never modified.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import curves as CV
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
    bulge: float = 0.0

    def __post_init__(self):
        self.a = (float(self.a[0]), float(self.a[1]))
        self.b = (float(self.b[0]), float(self.b[1]))
        d = P.sub(self.b, self.a)
        chord = math.hypot(*d)
        if chord < 1e-6:
            raise ValueError(f"Muro {self.id}: extremos coincidentes")
        self.u = (d[0] / chord, d[1] / chord)     # of the chord, for a curved wall
        self.n = (-self.u[1], self.u[0])
        self.lo, self.hi = offsets(self.thickness, self.reference)
        self.bulge = float(self.bulge or 0.0)
        if abs(self.bulge) < 1e-9:
            self.bulge = 0.0
            self.length = chord
            return
        if abs(self.bulge) > CV.MAX_BULGE + 1e-9:
            raise ValueError(f"Muro {self.id}: curvatura mayor que media circunferencia")
        self.c, self.r, self.t0, self.sweep = CV.arc_of(self.a, self.b, self.bulge)
        self.d = 1.0 if self.bulge > 0 else -1.0
        self.length = self.r * abs(self.sweep)
        if min(self.r - self.d * self.lo, self.r - self.d * self.hi) <= 1e-6:
            raise ValueError(f"Muro {self.id}: la curva es demasiado cerrada para su espesor")

    @property
    def curved(self):
        return self.bulge != 0.0

    def _angle(self, s):
        return self.t0 + self.d * s / self.r

    def point(self, s, off):
        if not self.bulge:
            return (self.a[0] + self.u[0] * s + self.n[0] * off,
                    self.a[1] + self.u[1] * s + self.n[1] * off)
        t = self._angle(s)
        rr = self.r - self.d * off
        return (self.c[0] + rr * math.cos(t), self.c[1] + rr * math.sin(t))

    def local(self, p):
        """(distance along the reference line, offset to its left)."""
        if not self.bulge:
            r = P.sub(p, self.a)
            return P.dot(r, self.u), P.dot(r, self.n)
        v = P.sub(p, self.c)
        delta = self.d * (math.atan2(v[1], v[0]) - self.t0)
        mid = abs(self.sweep) / 2.0
        while delta <= mid - math.pi:
            delta += 2 * math.pi
        while delta > mid + math.pi:
            delta -= 2 * math.pi
        return delta * self.r, self.d * (self.r - math.hypot(*v))

    def tangent(self, s):
        if not self.bulge:
            return self.u
        t = self._angle(s)
        return (-self.d * math.sin(t), self.d * math.cos(t))

    def face(self, off):
        """The face at ``off``: ("line", point, direction) | ("circle", centre, radius)."""
        if not self.bulge:
            return ("line", self.point(0.0, off), self.u)
        return ("circle", self.c, self.r - self.d * off)

    def face_line(self, off):
        return self.point(0.0, off), self.u

    def run(self, off, p, q, through=()):
        """Points along the face ``off`` from p to q (both on it), ends
        included, passing exactly through the ``through`` points that lie
        between them (where the end of another wall meets this face)."""
        if not self.bulge:
            return [p, q]
        rr = self.r - self.d * off
        s0, s1 = self.local(p)[0], self.local(q)[0]
        lo_s, hi_s = min(s0, s1), max(s0, s1)
        stops = sorted((x for x in through if lo_s + 1e-7 < self.local(x)[0] < hi_s - 1e-7),
                       key=lambda x: self.local(x)[0], reverse=s1 < s0)
        out = [p]
        for a, b in zip([p] + stops, stops + [q]):
            ta = math.atan2(a[1] - self.c[1], a[0] - self.c[0])
            tb = ta + self.d * (self.local(b)[0] - self.local(a)[0]) / self.r
            seg = CV.run(self.c, rr, ta, tb)
            out.extend(seg[1:-1])
            out.append(b)
        return out

    def strip(self):
        if not self.bulge:
            return [self.point(0, self.lo), self.point(self.length, self.lo),
                    self.point(self.length, self.hi), self.point(0, self.hi)]
        right = self.run(self.lo, self.point(0, self.lo), self.point(self.length, self.lo))
        left = self.run(self.hi, self.point(self.length, self.hi), self.point(0, self.hi))
        return right + left


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
    specs: dict = field(default_factory=dict)      # id -> Wall


def walls_from_records(records):
    """[(id, info)] as stored in XDATA -> [Wall]; order kept as drawing order."""
    out = []
    for i, (ident, info) in enumerate(records):
        out.append(Wall(ident, tuple(info["a"][:2]), tuple(info["b"][:2]),
                        float(info["thickness"]), info.get("reference", "eje") or "eje",
                        int(info.get("join_priority", 0) or 0), i, float(info.get("bulge") or 0.0)))
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
    """Compute non-overlapping footprints. ``columns`` = [(id, polygon)] or
    [(id, polygon, core, cover)]: a column with a covering («recubrimiento»)
    gives the wall back the part of the covering inside it (or against its
    end), since a covering only wraps what is outside the walls."""
    res = Result()
    res.specs = {w.id: w for w in walls}
    sin_min = math.sin(math.radians(min_angle))
    ends = []
    for i, w in enumerate(walls):
        t1 = w.tangent(w.length)
        ends.append(End(i, 0, w.a, w.tangent(0.0)))
        ends.append(End(i, 1, w.b, (-t1[0], -t1[1])))

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
            s = _sin(ei.e, ej.e)
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
    through = {}
    for k, en in enumerate(ends):
        if k in node_of:
            continue
        w = walls[en.w]
        best = None
        for v_i, v in enumerate(walls):
            if v_i == en.w:
                continue
            s, off = v.local(en.p)
            if not (v.lo - tol <= off <= v.hi + tol and -tol <= s <= v.length + tol):
                continue
            if _sin(en.e, v.tangent(min(max(s, 0.0), v.length))) < sin_min:
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
            host = walls[v_i]
            if host.curved:
                # the host's curved face passes through the stem's corners, so
                # that the stem stops exactly on it (no sliver beyond a chord)
                s_h = min(max(host.local(en.p)[0], 0.0), host.length)
                t = host.tangent(s_h)
                far = host.lo if P.dot(en.e, (-t[1], t[0])) > 0 else host.hi
                through.setdefault((v_i, far), []).extend([left, right])
            tee_host[(en.w, en.which)] = v_i
            res.tees.append({"wall": w.id, "end": en.which, "host": walls[v_i].id})

    # ---- 2. raw footprints -------------------------------------------------------------
    raw = []
    for i, w in enumerate(walls):
        c0 = cap.get((i, 0)) or {"left": w.point(0, w.hi), "right": w.point(0, w.lo), "hub": []}
        c1 = cap.get((i, 1)) or {"left": w.point(w.length, w.hi),
                                 "right": w.point(w.length, w.lo), "hub": []}
        poly = [*w.run(w.lo, c0["right"], c1["right"], through.get((i, w.lo), ())), *c1["hub"],
                *w.run(w.hi, c1["left"], c0["left"], through.get((i, w.hi), ())), *c0["hub"]]
        poly = P.dedupe(poly)
        if len(poly) < 3 or P.area(poly) <= P.EPS_AREA or not _simple(poly):
            res.warnings.append(f"Muro {w.id}: encuentro degenerado, se usa corte recto")
            poly = w.strip()
        raw.append(P.dedupe(P.ccw(poly)))

    # ---- 3. ownership ------------------------------------------------------------------
    pieces = [P.convex_parts(p) for p in raw]
    covered = []
    for entry in columns:
        cid, cpoly = entry[0], entry[1]
        cpoly = P.dedupe(P.ccw([tuple(map(float, q[:2])) for q in cpoly]))
        res.columns[cid] = cpoly
        for i in range(len(walls)):
            before = sum(P.area(x) for x in pieces[i])
            pieces[i] = P.subtract(pieces[i], cpoly)
            lost = before - sum(P.area(x) for x in pieces[i])
            if lost > 1e-9:
                res.clips.append({"loser": walls[i].id, "winner": cid, "area": lost})
        if len(entry) >= 4 and entry[2] and float(entry[3] or 0.0) > 1e-9:
            covered.append((cid, cpoly, entry[2], float(entry[3])))
    for cid, cpoly, core, cover in covered:
        _give_back_covering(res, cid, cpoly, core, cover, walls, raw, pieces)
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


def _wall_zone(w, raw_poly, reach):
    """Where a wall claims a column's covering: its own footprint and, at
    each end, a strip ``reach`` long (a wall that stops against the covered
    column has no covering between its end and the column)."""
    zone = P.convex_parts(raw_poly)
    for s0, s1 in ((-reach, 0.0), (w.length, w.length + reach)):
        quad = [w.point(s0, w.lo), w.point(s1, w.lo), w.point(s1, w.hi), w.point(s0, w.hi)]
        quad = P.dedupe(P.ccw(quad))
        if len(quad) >= 3 and P.area(quad) > P.EPS_AREA:
            zone.extend(P.convex_parts(quad))
    return zone


def _give_back_covering(res, cid, cpoly, core, cover, walls, raw, pieces):
    core = P.dedupe(P.ccw([tuple(map(float, q[:2])) for q in core]))
    ring = P.subtract(P.convex_parts(cpoly), core)
    if not ring:
        return
    reach = cover + 1e-6
    box = P.bbox(ring)
    for i, w in enumerate(walls):
        near = P.bbox([raw[i]])
        if near is not None:
            near = (near[0] - reach, near[1] - reach, near[2] + reach, near[3] + reach)
        if P.boxes_apart(box, near):
            continue                  # a wall far from the column takes nothing
        zone = _wall_zone(w, raw[i], reach)
        taken = []
        for r in ring:
            for z in zone:
                inter = P.convex_intersection(r, z)
                if inter and P.area(inter) > P.EPS_AREA:
                    taken.append(P.dedupe(P.ccw(inter)))
        if not taken:
            continue
        # give each bit once: take it out of the ring and of what is left
        new = []
        for t in taken:
            frags = [t]
            for q in new:
                frags = [f for g in frags for f in P.convex_difference(g, q)]
            new.extend(f for f in frags if P.area(f) > P.EPS_AREA)
        for t in new:
            ring = [f for r in ring for f in P.convex_difference(r, t)]
        pieces[i].extend(new)
    loops = P.merge(P.convex_parts(core) + ring)
    if len(loops) == 1 and not loops[0][1] and P.area(loops[0][0]) > P.EPS_AREA:
        res.columns[cid] = P.dedupe(P.ccw(loops[0][0]))


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
            mx, my = members[x], members[y]
            wx, wy = walls[mx.w], walls[my.w]
            if _sin(mx.e, my.e) >= sin_min:
                # The hub is where the AXES cross, never where the reference
                # lines cross: with a face reference that point lies ON a
                # face, the cap folds back along it and the footprint breaks
                # (found 2026-11-06 with an L drawn by its faces).
                q = P.line_intersection(_axis_end(mx, wx), mx.e, _axis_end(my, wy), my.e)
                if q is not None:
                    return q
    return pts[0]


def _axis_end(en, w):
    return w.point(0.0 if en.which == 0 else w.length, (w.lo + w.hi) / 2)


def _faces_in_end_frame(en, w, node):
    """(m, left_line_point, right_line_point) in the frame looking from the
    node INTO the wall body; left/right are the wall's own hi/lo faces."""
    e = en.e
    if w.curved:
        s_end = 0.0 if en.which == 0 else w.length
        left_off, right_off = (w.hi, w.lo) if en.which == 0 else (w.lo, w.hi)
        return e, w.point(s_end, left_off), w.point(s_end, right_off)
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
        q = _corner(en_k, w_k, left_k, e_k, "left", en_j, w_j, right_j, e_j, node)
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


def _end_face(en, w, side, point, e):
    """The face of the end ``en`` on its ``side`` (in the end frame), as a
    line through ``point`` along ``e`` or the wall's own circle."""
    if not w.curved:
        return ("line", point, e)
    off = (w.hi if side == "left" else w.lo) if en.which == 0 else (w.lo if side == "left" else w.hi)
    return w.face(off)


def _corner(en_k, w_k, left_k, e_k, _side, en_j, w_j, right_j, e_j, node):
    if not (w_k.curved or w_j.curved):
        return P.line_intersection(left_k, e_k, right_j, e_j)
    f = _end_face(en_k, w_k, "left", left_k, e_k)
    g = _end_face(en_j, w_j, "right", right_j, e_j)
    return CV.nearest(CV.intersect(f, g), node)


def _tee_corners(en, w, host, miter_limit):
    """Extend the end of ``w`` to the far face of ``host`` (returned in the
    wall's u-frame as (left=hi, right=lo)), or None if too oblique."""
    s_host = min(max(host.local(en.p)[0], 0.0), host.length)
    t = host.tangent(s_host)
    side = P.dot(en.e, (-t[1], t[0]))
    far = host.lo if side > 0 else host.hi
    if not (w.curved or host.curved):
        q0, d = host.face_line(far)
        left = P.line_intersection(w.point(0, w.hi), w.u, q0, d)
        right = P.line_intersection(w.point(0, w.lo), w.u, q0, d)
    else:
        s_end = 0.0 if en.which == 0 else w.length
        hf = host.face(far)
        left = CV.nearest(CV.intersect(_own_face(w, w.hi, s_end), hf), w.point(s_end, w.hi))
        right = CV.nearest(CV.intersect(_own_face(w, w.lo, s_end), hf), w.point(s_end, w.lo))
    if left is None or right is None:
        return None
    limit = miter_limit * max(w.thickness, host.thickness)
    if math.dist(left, en.p) > limit + host.thickness or math.dist(right, en.p) > limit + host.thickness:
        return None
    return left, right


def _own_face(w, off, s_end):
    if w.curved:
        return w.face(off)
    return ("line", w.point(s_end, off), w.u)


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

def plan_items(result, cuts=None):
    """The plan outline as it is drawn: ("line", a, b, ids) items, and the
    chords of a curved face joined back into ("arc", centre, r, start°,
    end°, ids, a, b) items (``curves.arcs_in``)."""
    segments = plan_outline(result, cuts)
    circles = {w.id: [(w.c, w.r - w.d * w.lo), (w.c, w.r - w.d * w.hi)]
               for w in result.specs.values() if w.curved}
    if not circles:
        return [("line", a, b, ids) for a, b, ids in segments]
    return CV.arcs_in(segments, circles)


def plan_outline(result, cuts=None):
    """Visible plan lines: boundary of walls+columns, minus column edges
    (columns keep their own outline). Each segment carries its wall id(s):
    [(a, b, [wall_id])]. Collinear pieces of the same wall are merged.

    ``cuts`` {wall id: [polygon]}: the holes of its doors/windows. They are
    removed from that wall only, so its faces stop at the hole and the
    jambs («mochetas») appear; rooms and 3D keep the uncut footprint."""
    networks=getattr(result,'vertical_networks',None)
    if networks is not None:
        edges={}
        for _z,part in networks:
            for a,b,owners in plan_outline(part,cuts):
                k=(tuple(round(v,7) for v in a),tuple(round(v,7) for v in b),tuple(owners))
                edges[k]=(a,b,owners)
        return list(edges.values())
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

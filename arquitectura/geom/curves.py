# SPDX-License-Identifier: GPL-3.0-or-later
"""Circular arcs for curved walls (pure Python).

A curved wall is stored as a DXF polyline does it: its two end points and a
**bulge** (``tan(sweep / 4)``; positive = counter-clockwise from ``a`` to
``b``, i.e. the arc bulges to the RIGHT of the chord; 1 = half circle). Its
faces are concentric arcs, true circles: they are only turned into chords
(``CHORD``) where a polygon is needed, the same polygon for the plan, the
rooms and the 3D model.

The approach (a curve kept as a curve; corners found where the faces of two
walls really cross, a line and a circle or two circles) follows the curved
walls of ArchXQ IT Lite (https://github.com/equipexq/archxq-it-lite,
GPL-3.0), written anew for this engine: no code is copied.
"""
from __future__ import annotations

import math

CHORD = 0.001            # m: greatest distance from a chord to its arc
MAX_BULGE = 1.0          # half a circle; larger sweeps are not accepted yet


def arc_of(a, b, bulge):
    """(centre, radius, start angle, signed sweep) of the arc a→b."""
    chord = math.dist(a, b)
    sweep = 4.0 * math.atan(bulge)
    r = chord / (2.0 * math.sin(abs(sweep) / 2.0))
    ux, uy = (b[0] - a[0]) / chord, (b[1] - a[1]) / chord
    mx, my = (a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0
    h = math.copysign(1.0, bulge) * r * math.cos(abs(sweep) / 2.0)
    c = (mx - uy * h, my + ux * h)
    return c, r, math.atan2(a[1] - c[1], a[0] - c[0]), sweep


def bulge_through(a, b, p):
    """Bulge of the arc from ``a`` to ``b`` passing through ``p`` (0 when
    ``p`` is on the chord)."""
    va = (a[0] - p[0], a[1] - p[1])
    vb = (b[0] - p[0], b[1] - p[1])
    la, lb = math.hypot(*va), math.hypot(*vb)
    if la < 1e-9 or lb < 1e-9:
        raise ValueError("el punto de paso coincide con un extremo")
    cosang = max(-1.0, min(1.0, (va[0] * vb[0] + va[1] * vb[1]) / (la * lb)))
    ang = math.acos(cosang)                       # angle a-p-b
    if ang > math.pi - 1e-9:
        return 0.0
    # p on the right of a→b: the arc runs counter-clockwise (positive)
    side = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
    return math.copysign(1.0 / math.tan(ang / 2.0), -side)


def bulge_from_sagitta(a, b, sagitta):
    """Bulge from the rise of the arc at mid chord (positive: to the left
    of a→b, the side a point picked there would give)."""
    return -2.0 * float(sagitta) / math.dist(a, b)


def steps(sweep, r, chord=CHORD):
    """Number of chords for ``sweep`` radians on radius ``r``."""
    if r <= chord:
        return max(1, int(math.ceil(abs(sweep) / (math.pi / 8))))
    step = 2.0 * math.acos(1.0 - chord / r)
    return max(1, int(math.ceil(abs(sweep) / step - 1e-9)))


def run(c, r, t0, t1, chord=CHORD):
    """Points on the circle (c, r) from angle t0 to t1 (either way), both
    ends included."""
    n = steps(t1 - t0, r, chord)
    return [(c[0] + r * math.cos(t0 + (t1 - t0) * k / n), c[1] + r * math.sin(t0 + (t1 - t0) * k / n))
            for k in range(n + 1)]


# -- intersections of faces: ("line", point, unit direction) | ("circle", centre, radius) -------

def intersect(f, g):
    """Points where two faces cross (0, 1 or 2)."""
    if f[0] == "line" and g[0] == "line":
        return _line_line(f, g)
    if f[0] == "circle" and g[0] == "circle":
        return _circle_circle(f, g)
    line, circ = (f, g) if f[0] == "line" else (g, f)
    return _line_circle(line, circ)


def _line_line(f, g):
    (_k, p, d), (_k2, q, e) = f, g
    den = d[0] * e[1] - d[1] * e[0]
    if abs(den) < 1e-12:
        return []
    t = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / den
    return [(p[0] + d[0] * t, p[1] + d[1] * t)]


def _line_circle(line, circ):
    _k, p, d = line
    _k2, c, r = circ
    fx, fy = p[0] - c[0], p[1] - c[1]
    b = fx * d[0] + fy * d[1]
    cc = fx * fx + fy * fy - r * r
    disc = b * b - cc
    if disc < -1e-12:
        return []
    disc = math.sqrt(max(0.0, disc))
    return [(p[0] + d[0] * t, p[1] + d[1] * t) for t in (-b - disc, -b + disc)]


def _circle_circle(f, g):
    (_k, c0, r0), (_k2, c1, r1) = f, g
    dx, dy = c1[0] - c0[0], c1[1] - c0[1]
    dd = math.hypot(dx, dy)
    if dd < 1e-12 or dd > r0 + r1 + 1e-9 or dd < abs(r0 - r1) - 1e-9:
        return []
    a = (r0 * r0 - r1 * r1 + dd * dd) / (2 * dd)
    h = math.sqrt(max(0.0, r0 * r0 - a * a))
    mx, my = c0[0] + dx * a / dd, c0[1] + dy * a / dd
    return [(mx - dy * h / dd, my + dx * h / dd), (mx + dy * h / dd, my - dx * h / dd)]


def nearest(points, to):
    return min(points, key=lambda q: math.dist(q, to)) if points else None


# -- chains of chords back to arcs (for the plan drawing) ---------------------------------------

def arcs_in(segments, circles, chord=CHORD, tol=1e-6):
    """Split ``segments`` [(a, b, ids)] into plain lines and arcs.

    ``circles`` {wall id: [(centre, radius)]}: the curved faces. Consecutive
    chords of the same wall on the same circle whose rise is a chord's
    (never a long straight edge that happens to end on it) become one arc.
    Returns [("line", a, b, ids) | ("arc", centre, r, start°, end°, ids, a, b)]
    with the arc counter-clockwise from start° to end° (DXF ARC)."""
    out, pending = [], {}
    for a, b, ids in segments:
        hit = None
        if len(ids) == 1:
            for c, r in circles.get(ids[0], ()):
                if abs(math.dist(a, c) - r) < tol and abs(math.dist(b, c) - r) < tol:
                    half = math.dist(a, b) / 2.0
                    rise = r - math.sqrt(max(0.0, r * r - half * half))
                    if rise <= 1.5 * chord + 1e-9:
                        hit = (c, r)
                        break
        if hit is None:
            out.append(("line", a, b, ids))
        else:
            k = (ids[0], round(hit[0][0], 6), round(hit[0][1], 6), round(hit[1], 6))
            pending.setdefault(k, (hit, ids, []))[2].append((a, b))
    for (_wid, *_c), ((c, r), ids, segs) in pending.items():
        for chain in _chains(segs):
            t = [math.atan2(p[1] - c[1], p[0] - c[0]) for p in chain]
            # counter-clockwise along the chain?
            turn = sum(_wrap(t[i + 1] - t[i]) for i in range(len(t) - 1))
            if turn < 0:
                chain = chain[::-1]
            a, b = chain[0], chain[-1]
            t0 = math.degrees(math.atan2(a[1] - c[1], a[0] - c[0]))
            t1 = math.degrees(math.atan2(b[1] - c[1], b[0] - c[0]))
            out.append(("arc", c, r, t0 % 360.0, t1 % 360.0, ids, a, b))
    return out


def _wrap(t):
    while t <= -math.pi:
        t += 2 * math.pi
    while t > math.pi:
        t -= 2 * math.pi
    return t


def _chains(segs):
    """Undirected segments → ordered point chains (open or closed)."""
    def k(p):
        return (round(p[0], 7), round(p[1], 7))
    adj = {}
    for a, b in segs:
        adj.setdefault(k(a), []).append((a, b))
        adj.setdefault(k(b), []).append((b, a))
    used, chains = set(), []
    starts = [p for p, lst in adj.items() if len(lst) == 1] + list(adj)
    for s in starts:
        for first in adj[s]:
            key = frozenset((k(first[0]), k(first[1])))
            if key in used:
                continue
            chain = [first[0], first[1]]
            used.add(key)
            while True:
                nxt = [e for e in adj[k(chain[-1])] if frozenset((k(e[0]), k(e[1]))) not in used]
                if not nxt:
                    break
                used.add(frozenset((k(nxt[0][0]), k(nxt[0][1]))))
                chain.append(nxt[0][1])
            chains.append(chain)
    return chains

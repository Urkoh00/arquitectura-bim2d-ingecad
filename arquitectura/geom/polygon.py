# SPDX-License-Identifier: GPL-3.0-or-later
"""Planar polygon kernel for Arquitectura (pure Python, no host imports).

Small and deterministic on purpose: architectural footprints are built from
straight wall strips, so every boolean needed here reduces to clipping CONVEX
pieces by half-planes (Sutherland-Hodgman). Non-convex inputs are first cut
into triangles (ear clipping), results are glued back into loops by edge
cancellation. No fuzzy snapping: coordinates are compared with an explicit
``KEY`` precision (1e-9 m) only to recognise the SAME computed point.

All polygons are lists of (x, y) tuples; outer loops counter-clockwise,
holes clockwise.
"""
from __future__ import annotations

import math

EPS_AREA = 1e-12   # m2: pieces smaller than this are numerical dust
KEY = 9            # decimals used to identify coincident points (1 nm)


def key(p):
    return (round(p[0], KEY) + 0.0, round(p[1], KEY) + 0.0)


def cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def add(a, b):
    return (a[0] + b[0], a[1] + b[1])


def mul(a, s):
    return (a[0] * s, a[1] * s)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def area(poly):
    """Signed area (positive when counter-clockwise)."""
    s = 0.0
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        s += x0 * y1 - x1 * y0
    return s / 2.0


def ccw(poly):
    return list(poly) if area(poly) >= 0 else list(reversed(poly))


def dedupe(poly):
    """Drop repeated consecutive points and collinear middle points."""
    pts = []
    for p in poly:
        if not pts or key(p) != key(pts[-1]):
            pts.append(p)
    if len(pts) > 1 and key(pts[0]) == key(pts[-1]):
        pts.pop()
    changed = True
    while changed and len(pts) >= 3:
        changed = False
        for i in range(len(pts)):
            a, b, c = pts[i - 1], pts[i], pts[(i + 1) % len(pts)]
            ab, bc = sub(b, a), sub(c, b)
            lab, lbc = math.hypot(*ab), math.hypot(*bc)
            degenerate = lab < 1e-12 or lbc < 1e-12
            straight = abs(cross(ab, bc)) <= 1e-9 * lab * lbc and dot(ab, bc) > 0
            if degenerate or straight:
                pts.pop(i)
                changed = True
                break
    return pts


def is_convex(poly):
    n = len(poly)
    if n < 3:
        return False
    sign = 0
    for i in range(n):
        c = cross(sub(poly[(i + 1) % n], poly[i]), sub(poly[(i + 2) % n], poly[(i + 1) % n]))
        if abs(c) < 1e-14:
            continue
        s = 1 if c > 0 else -1
        if sign == 0:
            sign = s
        elif s != sign:
            return False
    return True


def clip_halfplane(poly, p, d):
    """Part of convex ``poly`` on the LEFT of the directed line p + t*d
    (boundary included). Intersection points are computed from the clipped
    edge's own endpoints, so two clips by the same line agree exactly."""
    out = []
    n = len(poly)
    if n == 0:
        return out
    side = [cross(d, sub(q, p)) for q in poly]
    scale = math.hypot(*d) * 1e-12
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        sa, sb = side[i], side[(i + 1) % n]
        ina, inb = sa >= -scale, sb >= -scale
        if ina:
            out.append(a)
        if ina != inb and abs(sa - sb) > 0:
            t = sa / (sa - sb)
            if 0.0 < t < 1.0:
                out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    out = dedupe(out)
    return out if len(out) >= 3 and area(out) > EPS_AREA else []


def convex_intersection(a, b):
    """Intersection of two convex counter-clockwise polygons."""
    out = list(a)
    n = len(b)
    for i in range(n):
        if not out:
            return []
        p, q = b[i], b[(i + 1) % n]
        out = clip_halfplane(out, p, sub(q, p))
    return out


def convex_difference(subject, clipper):
    """``subject - clipper`` for convex ccw polygons, as convex pieces that
    do not overlap each other."""
    pieces = []
    remaining = list(subject)
    n = len(clipper)
    for i in range(n):
        if not remaining:
            break
        p, q = clipper[i], clipper[(i + 1) % n]
        d = sub(q, p)
        outside = clip_halfplane(remaining, q, mul(d, -1.0))   # right side
        if outside:
            pieces.append(outside)
        remaining = clip_halfplane(remaining, p, d)
    return pieces


def triangulate(poly):
    """Ear clipping of a simple polygon (ccw result triangles)."""
    pts = dedupe(ccw(poly))
    if len(pts) < 3:
        return []
    if is_convex(pts):
        return [pts]
    tris = []
    idx = list(range(len(pts)))
    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        for k in range(len(idx)):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            a, b, c = pts[i0], pts[i1], pts[i2]
            if cross(sub(b, a), sub(c, b)) <= 1e-14:
                continue
            tri = [a, b, c]
            if any(_inside_tri(pts[j], tri) for j in idx if j not in (i0, i1, i2)):
                continue
            tris.append(tri)
            idx.pop(k)
            break
        else:
            break
    if len(idx) == 3:
        tri = [pts[i] for i in idx]
        if area(tri) > EPS_AREA:
            tris.append(tri)
    return tris


def _inside_tri(p, tri):
    a, b, c = tri
    return (cross(sub(b, a), sub(p, a)) > 1e-14 and cross(sub(c, b), sub(p, b)) > 1e-14
            and cross(sub(a, c), sub(p, c)) > 1e-14)


def convex_parts(poly):
    poly = dedupe(ccw(poly))
    return [poly] if is_convex(poly) else triangulate(poly)


def subtract(pieces, clipper_poly):
    """Convex ``pieces`` minus an arbitrary simple polygon."""
    for part in convex_parts(clipper_poly):
        nxt = []
        for piece in pieces:
            nxt.extend(convex_difference(piece, part))
        pieces = nxt
    return pieces


def overlap_area(pieces_a, pieces_b):
    s = 0.0
    for a in pieces_a:
        for b in pieces_b:
            inter = convex_intersection(a, b)
            if inter:
                s += area(inter)
    return s


# -- gluing pieces back into loops --------------------------------------------------------

def _split_edges(edges, points):
    """Split directed edges at any of ``points`` lying strictly inside them."""
    out = []
    for a, b in edges:
        d = sub(b, a)
        ll = dot(d, d)
        if ll < 1e-24:
            continue
        cuts = []
        length = math.sqrt(ll)
        for p in points:
            t = dot(sub(p, a), d) / ll
            if 1e-9 < t < 1 - 1e-9 and abs(cross(d, sub(p, a))) / length < 1e-9:
                cuts.append((t, p))
        cuts.sort()
        prev = a
        for _t, p in cuts:
            if key(p) != key(prev):
                out.append((prev, p))
            prev = p
        if key(b) != key(prev):
            out.append((prev, b))
    return out


def boundary_edges(pieces, tags=None):
    """Directed boundary edges of the union of NON-OVERLAPPING pieces.

    ``tags`` (one per piece) travel with each edge; an edge shared by two
    pieces cancels whatever their tags. Returns [(a, b, tag), ...]."""
    tags = tags if tags is not None else [None] * len(pieces)
    allpts = {key(p): p for pc in pieces for p in pc}
    pts = list(allpts.values())
    edges = {}
    for pc, tag in zip(pieces, tags):
        raw = [(pc[i], pc[(i + 1) % len(pc)]) for i in range(len(pc))]
        for a, b in _split_edges(raw, pts):
            ka, kb = key(a), key(b)
            if (kb, ka) in edges:
                edges[(kb, ka)].pop()
                if not edges[(kb, ka)]:
                    del edges[(kb, ka)]
            else:
                edges.setdefault((ka, kb), []).append((a, b, tag))
    return [e for lst in edges.values() for e in lst]


def loops_from_edges(edges):
    """Chain directed edges into closed loops (each edge used once)."""
    nxt = {}
    for a, b, *_ in edges:
        nxt.setdefault(key(a), []).append((a, b))
    loops = []
    while nxt:
        k0 = next(iter(nxt))
        a, b = nxt[k0].pop()
        if not nxt[k0]:
            del nxt[k0]
        loop = [a]
        cur = b
        guard = 0
        while key(cur) != key(loop[0]) and guard < 100000:
            guard += 1
            loop.append(cur)
            cand = nxt.get(key(cur))
            if not cand:
                break
            # at a vertex used twice, take the sharpest left turn
            if len(cand) > 1:
                din = sub(cur, loop[-2])
                cand.sort(key=lambda e: -math.atan2(cross(din, sub(e[1], e[0])),
                                                   dot(din, sub(e[1], e[0]))))
            a2, b2 = cand.pop(0)
            if not cand:
                del nxt[key(cur)]
            cur = b2
        loop = dedupe(loop)
        if len(loop) >= 3 and abs(area(loop)) > EPS_AREA:
            loops.append(loop)
    return loops


def merge(pieces):
    """Union of non-overlapping pieces -> [(outer_ccw, [holes_cw])]."""
    loops = loops_from_edges(boundary_edges(pieces))
    outers = [l for l in loops if area(l) > 0]
    holes = [l for l in loops if area(l) < 0]
    result = [(o, []) for o in outers]
    for h in holes:
        probe = _interior_probe(h)
        best = None
        for i, (o, _hs) in enumerate(result):
            if point_in_polygon(probe, o) and (best is None or area(o) < area(result[best][0])):
                best = i
        if best is not None:
            result[best][1].append(h)
    return result


def _interior_probe(loop):
    a, b = loop[0], loop[1]
    m = mul(add(a, b), 0.5)
    d = sub(b, a)
    n = (-d[1], d[0])
    ln = math.hypot(*n) or 1.0
    s = 1e-7 / ln
    # for a cw hole the material side is on the left of its edges
    return (m[0] + n[0] * s, m[1] + n[1] * s) if area(loop) > 0 else (m[0] - n[0] * s, m[1] - n[1] * s)


def point_in_polygon(pt, poly):
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        if (a[1] > y) != (b[1] > y):
            xx = a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if xx > x:
                inside = not inside
    return inside


def line_intersection(p, d, q, e):
    """Intersection of p + s*d and q + t*e, or None when parallel."""
    den = cross(d, e)
    if abs(den) < 1e-12 * math.hypot(*d) * math.hypot(*e):
        return None
    s = cross(sub(q, p), e) / den
    return (p[0] + d[0] * s, p[1] + d[1] * s)

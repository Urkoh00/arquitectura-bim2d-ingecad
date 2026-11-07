# SPDX-License-Identifier: GPL-3.0-or-later
"""Closed boundary solids from the junction footprints (pure Python).

A wall is a 2.5D cell complex: its footprint pieces are cut by the opening
jambs (planes across the axis) and each cell keeps the z-intervals of
material left by the openings above/below it. The boundary of the union is
built face by face: coplanar faces of neighbouring cells are glued, faces
shared by two cells cancel (no internal faces), and T-junctions are fixed so
every edge borders exactly two faces. The output is what IngeTrazo's
``core.bim.face_set_volume`` calls *watertight*.

The volume is known exactly (sum of cell area x height) and is returned to
check the mesh against.
"""
from __future__ import annotations

import math

from . import polygon as P

R = 9


def _cells(pieces, wall_frame, base, height, openings, spec=None):
    """[(convex_polygon, [(z0, z1), ...])] for one wall (``spec``: the
    junctions.Wall, needed for a curved wall: its jambs are radial)."""
    a, u = wall_frame
    curved = getattr(spec, "curved", False)
    cuts = sorted({float(o["offset"]) for o in openings} |
                  {float(o["offset"]) + float(o["width"]) for o in openings})
    regions = list(pieces)
    for s in cuts:
        if curved:
            p = spec.point(s, 0.0)
            t = spec.tangent(s)
            d = (-t[1], t[0])                  # the radius through the jamb
        else:
            p = (a[0] + u[0] * s, a[1] + u[1] * s)
            d = (-u[1], u[0])                  # line across the axis
        nxt = []
        for reg in regions:
            left = P.clip_halfplane(reg, p, d)                 # s <= cut
            right = P.clip_halfplane(reg, p, (-d[0], -d[1]))   # s >= cut
            nxt.extend(x for x in (left, right) if x)
        regions = nxt
    cells = []
    for reg in regions:
        cx = sum(q[0] for q in reg) / len(reg)
        cy = sum(q[1] for q in reg) / len(reg)
        s_mid = spec.local((cx, cy))[0] if curved else (cx - a[0]) * u[0] + (cy - a[1]) * u[1]
        intervals = [(0.0, height)]
        for o in openings:
            s0 = float(o["offset"])
            s1 = s0 + float(o["width"])
            if s0 < s_mid < s1:
                z0 = float(o["sill"])
                z1 = z0 + float(o["height"])
                intervals = _minus(intervals, z0, z1)
        for z0, z1 in intervals:
            if z1 - z0 > 1e-9:
                cells.append((reg, (base + z0, base + z1)))
    return cells


def _minus(intervals, z0, z1):
    out = []
    for a, b in intervals:
        if z1 <= a or z0 >= b:
            out.append((a, b))
            continue
        if z0 > a:
            out.append((a, z0))
        if z1 < b:
            out.append((z1, b))
    return out


def _prism_faces(reg, z0, z1):
    """(plane_key, orientation, 2D convex polygon in plane coords)."""
    out = [(("z", round(z0, R)), -1, list(reg)),
           (("z", round(z1, R)), +1, list(reg))]
    n = len(reg)
    for i in range(n):
        p, q = reg[i], reg[(i + 1) % n]
        dx, dy = q[0] - p[0], q[1] - p[1]
        ln = math.hypot(dx, dy)
        if ln < 1e-12:
            continue
        nx, ny = dy / ln, -dx / ln               # outward for a ccw region
        sign = 1
        if nx < -1e-12 or (abs(nx) <= 1e-12 and ny < 0):
            nx, ny, sign = -nx, -ny, -1          # canonical normal
        c = nx * p[0] + ny * p[1]
        e1 = (-ny, nx)                            # e1 x z == canonical normal
        t0 = e1[0] * p[0] + e1[1] * p[1]
        t1 = e1[0] * q[0] + e1[1] * q[1]
        lo, hi = sorted((t0, t1))
        rect = [(lo, z0), (hi, z0), (hi, z1), (lo, z1)]
        out.append((("v", round(nx, R), round(ny, R), round(c, R), nx, ny, c), sign, rect))
    return out


def _to3d(plane, pt):
    if plane[0] == "z":
        return (pt[0], pt[1], plane[1])
    _v, _kx, _ky, _kc, nx, ny, c = plane
    e1 = (-ny, nx)
    return (nx * c + e1[0] * pt[0], ny * c + e1[1] * pt[0], pt[1])


def boundary(cells):
    """Watertight faces of the union of cells: [(outer, [holes])], each loop
    a list of (x, y, z), counter-clockwise seen from outside."""
    planes = {}
    exact = {}
    for reg, (z0, z1) in cells:
        for plane, sign, poly in _prism_faces(reg, z0, z1):
            k = plane[:4]
            exact.setdefault(k, plane)            # first exact normal wins
            planes.setdefault(k, ([], []))[0 if sign > 0 else 1].append(P.ccw(poly))
    faces = []
    registry = {}

    def canon(v):
        return registry.setdefault(tuple(round(c, 7) for c in v), v)
    for k, (plus, minus) in planes.items():
        plane = exact[k]
        net_p = plus
        for m in minus:
            net_p = [x for pc in net_p for x in P.convex_difference(pc, m)]
        net_m = minus
        for p in plus:
            net_m = [x for pc in net_m for x in P.convex_difference(pc, p)]
        for pieces, sign in ((net_p, 1), (net_m, -1)):
            if not pieces:
                continue
            for outer, holes in P.merge(pieces):
                loops = [outer] + holes
                if sign < 0:
                    loops = [list(reversed(l)) for l in loops]
                loops3 = [[canon(_to3d(plane, q)) for q in l] for l in loops]
                faces.append((loops3[0], loops3[1:]))
    return _fix_tjunctions(faces)


def _fix_tjunctions(faces):
    verts = {}
    for outer, holes in faces:
        for loop in (outer, *holes):
            for v in loop:
                verts[tuple(round(c, R) for c in v)] = v
    vlist = list(verts.values())

    def refine(loop):
        out = []
        n = len(loop)
        for i in range(n):
            a, b = loop[i], loop[(i + 1) % n]
            out.append(a)
            d = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
            ll = d[0] ** 2 + d[1] ** 2 + d[2] ** 2
            if ll < 1e-24:
                continue
            mids = []
            for v in vlist:
                w = (v[0] - a[0], v[1] - a[1], v[2] - a[2])
                t = (w[0] * d[0] + w[1] * d[1] + w[2] * d[2]) / ll
                if not 1e-9 < t < 1 - 1e-9:
                    continue
                cx = w[1] * d[2] - w[2] * d[1]
                cy = w[2] * d[0] - w[0] * d[2]
                cz = w[0] * d[1] - w[1] * d[0]
                if (cx * cx + cy * cy + cz * cz) / ll < 1e-18:
                    mids.append((t, v))
            out.extend(v for _t, v in sorted(mids))
        return out

    return [(refine(o), [refine(h) for h in hs]) for o, hs in faces]


def face_volume(faces):
    """Divergence-theorem volume of closed faces with holes."""
    vol = 0.0
    for outer, holes in faces:
        n, a = _newell(outer)
        if a < 1e-18:
            continue
        net = a - sum(_newell(h)[1] for h in holes)
        p0 = outer[0]
        vol += (n[0] * p0[0] + n[1] * p0[1] + n[2] * p0[2]) * net / 3.0
    return vol


def _newell(loop):
    nx = ny = nz = 0.0
    m = len(loop)
    for i in range(m):
        x0, y0, z0 = loop[i]
        x1, y1, z1 = loop[(i + 1) % m]
        nx += (y0 - y1) * (z0 + z1)
        ny += (z0 - z1) * (x0 + x1)
        nz += (x0 - x1) * (y0 + y1)
    ln = math.sqrt(nx * nx + ny * ny + nz * nz)
    if ln == 0:
        return (0.0, 0.0, 0.0), 0.0
    return (nx / ln, ny / ln, nz / ln), ln / 2.0


def wall_solid(pieces, a, u, base, height, openings=(), spec=None):
    """(faces, exact_volume) of one wall from its junction footprint."""
    cells = _cells(pieces, (a, u), float(base), float(height), list(openings), spec)
    vol = sum(P.area(reg) * (z1 - z0) for reg, (z0, z1) in cells)
    return boundary(cells), vol


def prism_solid(polygon, base, height):
    poly = P.dedupe(P.ccw([tuple(map(float, q[:2])) for q in polygon]))
    cells = [(pc, (float(base), float(base) + float(height))) for pc in P.convex_parts(poly)]
    return boundary(cells), P.area(poly) * float(height)


def opening_box(a, u, n, lo, hi, opening, base):
    """Void volume of an opening as a closed box (IfcOpeningElement body)."""
    s0 = float(opening["offset"])
    s1 = s0 + float(opening["width"])
    z0 = float(base) + float(opening["sill"])
    z1 = z0 + float(opening["height"])

    def pt(s, off):
        return (a[0] + u[0] * s + n[0] * off, a[1] + u[1] * s + n[1] * off)
    reg = P.ccw([pt(s0, lo), pt(s1, lo), pt(s1, hi), pt(s0, hi)])
    return boundary([(reg, (z0, z1))])

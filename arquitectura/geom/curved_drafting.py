# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: Gestos de dibujo de muros con referencias curvas: esquina en L contra un muro curvo,
#   paralela a un arco, división en partes iguales sobre un arco, alargar hasta cualquier cara
#   (recta o curva) y unión de arcos de más de media circunferencia. (Python puro.)
"""Wall drafting on curves (pure Python, no IngeCAD, no Qt).

``drafting.py`` decides the drawing gestures of STRAIGHT walls from the
tuples ``(a, b, thickness, reference)``. This module does the same for
references that are circles. It reuses, and does not duplicate:

* ``junctions.Wall``  — one description of a wall, straight or curved
  (``point``, ``local``, ``face``, ``tangent``, ``length``);
* ``curves.intersect`` — where two faces (line or circle) cross;
* ``drafting.Frame``  — the frame of the NEW straight wall being drawn.

Every function takes ``specs`` = ``{id: junctions.Wall}`` (straight AND
curved walls together), so a straight gesture also sees the curved walls
and the other way round.
"""
from __future__ import annotations

import math

from . import curves as CV
from . import drafting as D
from . import junctions as J

EPS = 1e-9
MIN_SIN = math.sin(math.radians(5.0))      # same minimum angle as the junction engine


# --- sub-walls -------------------------------------------------------------------------------

def sub_wall_of_spec(w, s1, s2):
    """(a, b, bulge) of the part of ``w`` between ``s1`` and ``s2`` (metres
    along its reference line; beyond its ends a curved wall goes on along
    its circle). A straight wall: bulge 0. Up to ``curves.MAX_SWEEP``."""
    a, b = w.point(s1, 0.0), w.point(s2, 0.0)
    if not w.curved:
        return a, b, 0.0
    sweep = w.sweep * (s2 - s1) / w.length
    if abs(sweep) > CV.MAX_SWEEP + 1e-9:
        raise ValueError(f"El muro curvo pasaría de {math.degrees(CV.MAX_SWEEP):g}°: "
                         "divídalo en dos muros")
    return a, b, math.tan(sweep / 4.0)


# --- which face was clicked ---------------------------------------------------------------------

def face_at(specs, point, tol=1e-3):
    """[(wall_id, 'lo'|'hi', s)] of the faces of the CURVED walls that pass
    through ``point`` (same answer as ``drafting.face_at`` for straight ones)."""
    hits = []
    for wid, w in specs.items():
        if not w.curved:
            continue
        s, o = w.local(point)
        if -tol <= s <= w.length + tol:
            for side, off in (("lo", w.lo), ("hi", w.hi)):
                if abs(o - off) <= tol:
                    hits.append((wid, side, s))
    return hits


def nearest_face_offset(w, point):
    """The offset (lo, axis or hi) of ``w`` that lies closest to ``point``."""
    _s, o = w.local(point)
    mid = (w.lo + w.hi) / 2.0
    return min((w.lo, mid, w.hi), key=lambda off: abs(o - off))


# --- the L gesture against a curved host -----------------------------------------------------

def end_gesture(new_start, new_end, new_thickness, new_reference, host, hit_side, keep="longer",
                click=None):
    """T or L for a new STRAIGHT wall that ends on the face ``hit_side`` of a
    CURVED ``host`` (a ``junctions.Wall``).

    Same rule as ``drafting.end_gesture``: ending on the NEAR face makes a T
    (nothing to edit: the engine solves it); ending on the FAR face makes an
    L: the host is cut where the two AXES cross and keeps its longer part.
    Returns ``{"kind": "T"}`` or ``{"kind": "L", "new_end", "host_a",
    "host_b", "host_bulge", "cut_at", "kept"}``."""
    mid = (host.lo + host.hi) / 2.0
    _s0, o0 = host.local(new_start)
    near = "hi" if o0 > mid else "lo"
    if hit_side == near:
        return {"kind": "T"}
    nf = D.Frame(new_start, new_end, new_thickness, new_reference)
    axis0 = nf.axis_point(0.0)
    hits = CV.intersect(("line", axis0, nf.u), host.face(mid))
    x = CV.nearest(hits, click if click is not None else new_end)
    if x is None:
        raise ValueError("El eje del muro nuevo no corta el eje del muro curvo")
    sx = host.local(x)[0]
    if abs(D._cross(nf.u, host.tangent(sx))) < MIN_SIN:
        raise ValueError("El muro nuevo es tangente al muro curvo: no se puede hacer esquina")
    if not (EPS < sx < host.length - EPS):
        return {"kind": "T"}               # beyond the host's ends: the engine already makes a corner
    keep_start = sx >= host.length - sx if keep == "longer" else keep == "start"
    s0, s1 = (0.0, sx) if keep_start else (sx, host.length)
    a, b, bulge = sub_wall_of_spec(host, s0, s1)
    return {"kind": "L", "new_end": nf.reference_point_from_axis(x), "host_a": a, "host_b": b,
            "host_bulge": bulge, "cut_at": sx, "kept": "start" if keep_start else "end"}


# --- stretch to any face (straight or curved) ----------------------------------------------------

def _face_hits(first, specs, skip):
    """Crossings of the face ``first`` with every face of every wall in
    ``specs`` (not in ``skip``) that lie ON the other wall: [point]."""
    out = []
    for wid, o in specs.items():
        if wid in skip:
            continue
        for off in (o.lo, o.hi):
            for x in CV.intersect(first, o.face(off)):
                s, _ = o.local(x)
                if -EPS <= s <= o.length + EPS:
                    out.append(x)
    return out


def extend_line_to_faces(a, b, specs, max_gap, skip=()):
    """``drafting.extend_to_faces`` for any neighbour: both ends of the
    straight reference line a-b go to the nearest face crossed within
    ``max_gap`` beyond (or before) each end, straight or curved."""
    u = D._sub(b, a)
    length = math.hypot(*u)
    u = (u[0] / length, u[1] / length)
    out = [a, b]
    for end, (origin, direction) in enumerate(((a, D._mul(u, -1.0)), (b, u))):
        best = None
        for x in _face_hits(("line", origin, direction), specs, skip):
            along = D._dot(D._sub(x, origin), direction)
            if -max_gap <= along <= max_gap and (best is None or abs(along) < abs(best[0])):
                best = (along, x)
        if best is not None:
            out[end] = best[1]
    if math.dist(out[0], out[1]) < 1e-6:
        raise ValueError("El muro paralelo quedaría con longitud nula")
    return out[0], out[1]


def extend_arc_to_faces(a, b, bulge, specs, max_gap, skip=()):
    """The same for a curved reference line (a, b, bulge): each end moves
    ALONG ITS CIRCLE to the nearest face crossed within ``max_gap`` metres of
    arc. Returns (a, b, bulge)."""
    w = J.Wall("base", a, b, 0.01, "eje", bulge=bulge)
    s = [0.0, w.length]
    for end in (0, 1):
        best = None
        for x in _face_hits(w.face(0.0), specs, skip):
            along = w.local(x)[0] - s[end]
            if abs(along) <= max_gap and (best is None or abs(along) < abs(best[0])):
                best = (along, w.local(x)[0])
        if best is not None:
            s[end] = best[1]
    if s[1] - s[0] < 1e-6:
        raise ValueError("El muro paralelo quedaría con longitud nula")
    return sub_wall_of_spec(w, s[0], s[1])


# --- curved bases for MUROPARALELO -------------------------------------------------------------------

def base_from_wall(w, click):
    """The curved line a click picked on wall ``w`` (face or axis nearest to
    the click): ``{"c", "r", "a", "b", "bulge"}``."""
    off = nearest_face_offset(w, click)
    return {"c": w.c, "r": w.r - w.d * off, "a": w.point(0.0, off), "b": w.point(w.length, off),
            "bulge": w.bulge}


def base_from_arc(centre, radius, start_deg, end_deg):
    """The base of a DXF ARC (counter-clockwise from start to end)."""
    sweep = (float(end_deg) - float(start_deg)) % 360.0
    if sweep < 1e-9:
        sweep = 360.0
    t0 = math.radians(start_deg)
    a = (centre[0] + radius * math.cos(t0), centre[1] + radius * math.sin(t0))
    t1 = t0 + math.radians(sweep)
    b = (centre[0] + radius * math.cos(t1), centre[1] + radius * math.sin(t1))
    if sweep > math.degrees(CV.MAX_SWEEP) + 1e-9:          # more than a wall can be: two halves
        t2 = t0 + math.radians(sweep) / 2.0
        m = (centre[0] + radius * math.cos(t2), centre[1] + radius * math.sin(t2))
        h = math.tan(math.radians(sweep) / 8.0)
        return [{"c": tuple(centre), "r": radius, "a": a, "b": m, "bulge": h},
                {"c": tuple(centre), "r": radius, "a": m, "b": b, "bulge": h}]
    return [{"c": tuple(centre), "r": radius, "a": a, "b": b, "bulge": math.tan(math.radians(sweep) / 4.0)}]


def parallel_arcs(base, distance, side_point, body_point):
    """Walls parallel (concentric) to a curved base, ``distance`` away on the
    side of ``side_point`` (inside or outside the circle), with the body on
    the side of ``body_point``. ``base`` is one of the dicts above (or a list
    of them, for a full circle). Returns [(a, b, bulge, reference)]."""
    bases = base if isinstance(base, list) else [base]
    out = []
    for bs in bases:
        c, r = bs["c"], bs["r"]
        ps = math.dist(side_point, c)
        if abs(ps - r) < 1e-9:
            raise ValueError("Indique el lado con un punto fuera de la línea")
        r2 = r + (float(distance) if ps > r else -float(distance))
        if r2 <= 1e-6:
            raise ValueError("La paralela interior no cabe: el radio sería nulo o negativo")
        k = r2 / r
        a = (c[0] + (bs["a"][0] - c[0]) * k, c[1] + (bs["a"][1] - c[1]) * k)
        b = (c[0] + (bs["b"][0] - c[0]) * k, c[1] + (bs["b"][1] - c[1]) * k)
        pb = math.dist(body_point, c)
        if abs(pb - r2) < 1e-9:
            raise ValueError("Indique el lado del espesor con un punto fuera de la línea")
        ccw = bs["bulge"] > 0                      # travelling a→b counter-clockwise: left = inside
        reference = "izquierda" if (pb < r2) == ccw else "derecha"
        out.append((a, b, bs["bulge"], reference))
    return out


def far_face_base(w, click):
    """For the chain of MUROPARALELO: the far face of the wall just made,
    as a base (the face farther from ``click``'s opposite side)."""
    _s, o = w.local(click)
    off = w.hi if abs(o - w.hi) < abs(o - w.lo) else w.lo
    return {"c": w.c, "r": w.r - w.d * off, "a": w.point(0.0, off),
            "b": w.point(w.length, off), "bulge": w.bulge}


# --- facing face for DIVIDEMURO ------------------------------------------------------------------------

def first_face(origin, direction, specs, max_reach, skip=()):
    """Nearest face (straight or curved) crossed by the ray
    ``origin + t·direction`` with t between 1 mm and ``max_reach``."""
    best = None
    for x in _face_hits(("line", origin, direction), specs, skip):
        along = D._dot(D._sub(x, origin), direction)
        if 1e-3 < along <= max_reach and (best is None or along < best[0]):
            best = (along, x)
    return best[1] if best else None


def divide_walls(p1, p2, parts, thickness, length=None, specs=None, max_reach=50.0):
    """``drafting.divide_walls`` seeing every wall in ``specs``, curved too."""
    parts = int(parts)
    if parts < 2:
        raise ValueError("Indique al menos 2 partes")
    f = D.Frame(p1, p2, 1.0, "eje")
    clear = (f.length - (parts - 1) * thickness) / parts
    if clear <= 1e-6:
        raise ValueError("No caben los muros en ese tramo")
    out = []
    for i in range(1, parts):
        s = i * clear + (i - 1) * thickness + thickness / 2.0
        a = f.point(s)
        if length:
            b = D._add(a, D._mul(f.n, float(length)))
        else:
            b = first_face(a, f.n, specs or {}, max_reach)
            if b is None:
                raise ValueError("Sin longitud y sin muro enfrente: indique la Longitud")
        out.append((a, b, "eje"))
    return out


def divide_arc_walls(c, p1, p2, sweep_sign, parts, thickness, length=None, specs=None,
                     max_reach=50.0):
    """Walls that divide the ARC from p1 to p2 (both on the circle of centre
    ``c``; ``sweep_sign`` +1 counter-clockwise, −1 clockwise, the way the
    arc runs from p1 to p2) into ``parts`` equal clear spans.

    They are RADIAL, to the LEFT of the direction of travel (inside the
    circle when it runs counter-clockwise). The clear span is measured on the
    circle through p1, between the faces of the walls. Each wall is
    ``length`` long, or reaches the first face in front. Returns
    [(a, b, "eje")]."""
    parts = int(parts)
    if parts < 2:
        raise ValueError("Indique al menos 2 partes")
    r0 = math.dist(p1, c)
    if abs(math.dist(p2, c) - r0) > 1e-3 or r0 < 1e-6:
        raise ValueError("Los dos puntos deben estar sobre la misma circunferencia")
    if thickness >= 2 * r0:
        raise ValueError("El espesor no cabe en esa circunferencia")
    t1 = math.atan2(p1[1] - c[1], p1[0] - c[0])
    t2 = math.atan2(p2[1] - c[1], p2[0] - c[0])
    total = ((t2 - t1) * sweep_sign) % (2 * math.pi)
    if total < 1e-9 or total > CV.MAX_SWEEP + 1e-9:
        raise ValueError("El tramo de arco no es válido")
    beta = math.asin(thickness / (2.0 * r0))             # half the angle a wall covers on the circle
    clear = (total - (parts - 1) * 2 * beta) / parts
    if clear <= 1e-9:
        raise ValueError("No caben los muros en ese tramo")
    out = []
    for i in range(1, parts):
        phi = i * clear + (i - 1) * 2 * beta + beta
        th = t1 + sweep_sign * phi
        radial = (math.cos(th), math.sin(th))
        a = (c[0] + r0 * radial[0], c[1] + r0 * radial[1])
        left = (-radial[0] * sweep_sign, -radial[1] * sweep_sign)
        if length:
            b = (a[0] + left[0] * float(length), a[1] + left[1] * float(length))
        else:
            b = first_face(a, left, specs or {}, max_reach)
            if b is None:
                raise ValueError("Sin longitud y sin muro enfrente: indique la Longitud")
        out.append((a, b, "eje"))
    return out


# --- UNIRMURO: two arcs of the same circle -------------------------------------------------------------------

def joined_span(f1, f2):
    """(smin, smax), in the metres along ``f1``'s reference line, of the arc
    made by joining the curved walls ``f1`` and ``f2`` (same circle). Works
    for results larger than half a circle, where ``Wall.local`` would fold
    the far end of ``f2`` back to the other side."""
    circ = 2.0 * math.pi * f1.r
    mid = (f2.lo + f2.hi) / 2.0
    pa = f1.local(f2.point(0.0, mid))[0]
    # f2 runs from its start in its own direction: the same as f1's or the opposite
    same = (f1.d == f2.d)
    pb = pa + (f2.length * f1.r / f2.r if same else -f2.length * f1.r / f2.r)
    lo2, hi2 = min(pa, pb), max(pa, pb)
    best = None
    for k in (-1, 0, 1):
        l2, h2 = lo2 + k * circ, hi2 + k * circ
        gap = max(0.0, max(l2 - f1.length, 0.0 - h2))           # 0 when they touch or overlap
        if best is None or gap < best[0]:
            best = (gap, l2, h2)
    _gap, l2, h2 = best
    return min(0.0, l2), max(f1.length, h2)

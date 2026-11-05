# SPDX-License-Identifier: GPL-3.0-or-later
"""Wall drafting geometry: the decisions behind the drawing gestures.

Pure Python (no IngeCAD, no Qt): every rule here is tested against the
junction engine. A wall is described as in the BIM record: its reference
line ``a``-``b`` (the line the user draws), ``thickness`` and
``reference`` ("eje": axis; "izquierda": the wall body lies to the LEFT of
the drawn line; "derecha": to the right).

Gestures
--------
* **T / L at the end of a new wall.** Ending a wall on the NEAR face of an
  existing wall makes a T (the existing wall passes through). Ending it on
  the FAR face makes an L: the existing wall is cut at the corner and keeps
  its longer part. The T needs no edit (the engine solves it); the L is an
  explicit, undoable edit of both reference lines.
* **Extend/trim to a line.** The end of a wall nearest to the pick moves to
  where its reference line crosses a boundary line.
* **Move one end** (pivot about the other end).
* **Parallel wall** at a distance from a picked face, on a picked side.
"""
from __future__ import annotations

import math

from .junctions import offsets

EPS = 1e-9


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1])


def _mul(a, k):
    return (a[0] * k, a[1] * k)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def _cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


class Frame:
    """Local frame of a wall: s along the reference line, o across it
    (positive to the left). Faces are at o = lo and o = hi; the axis at
    o = mid."""

    def __init__(self, a, b, thickness, reference="eje"):
        self.a = (float(a[0]), float(a[1]))
        self.b = (float(b[0]), float(b[1]))
        d = _sub(self.b, self.a)
        self.length = math.hypot(*d)
        if self.length < 1e-6:
            raise ValueError("Extremos del muro coincidentes")
        self.u = (d[0] / self.length, d[1] / self.length)
        self.n = (-self.u[1], self.u[0])
        self.t = float(thickness)
        self.lo, self.hi = offsets(self.t, reference)
        self.mid = (self.lo + self.hi) / 2.0

    def point(self, s, o=0.0):
        return _add(_add(self.a, _mul(self.u, s)), _mul(self.n, o))

    def local(self, p):
        r = _sub(p, self.a)
        return _dot(r, self.u), _dot(r, self.n)

    def axis_point(self, s):
        return self.point(s, self.mid)

    def reference_point_from_axis(self, p_axis):
        """The point of the reference line that corresponds to an axis point."""
        return _sub(p_axis, _mul(self.n, self.mid))


def line_intersection(p, d, q, e):
    """Intersection of p + λd and q + μe, or None when parallel."""
    den = _cross(d, e)
    if abs(den) < 1e-12:
        return None
    lam = _cross(_sub(q, p), e) / den
    return _add(p, _mul(d, lam))


# --- picking a face ----------------------------------------------------------

def face_at(walls, point, tol=1e-3):
    """Which wall face the point lies on: [(wall_id, 'lo'|'hi', s)].

    ``walls`` is {id: (a, b, thickness, reference)}. A point on a face within
    ``tol`` (and between the wall's ends) is reported; usually one hit."""
    hits = []
    for wid, (a, b, t, ref) in walls.items():
        f = Frame(a, b, t, ref)
        s, o = f.local(point)
        if -tol <= s <= f.length + tol:
            for side, off in (("lo", f.lo), ("hi", f.hi)):
                if abs(o - off) <= tol:
                    hits.append((wid, side, s))
    return hits


# --- T / L gesture -----------------------------------------------------------

def end_gesture(new_start, new_end, new_thickness, new_reference, host, hit_side,
                keep="longer"):
    """Decide T or L for a new wall that ends on ``host``'s face ``hit_side``.

    ``host`` is (a, b, thickness, reference). Returns a dict:
    ``{"kind": "T"}`` or ``{"kind": "L", "new_end": p, "host_a": p, "host_b": p,
    "cut_at": s}`` with the reference-line points to write. Raises ValueError
    when the new wall is parallel to the host (no corner possible)."""
    hf = Frame(*host)
    s0, o0 = hf.local(new_start)
    near = "hi" if o0 > hf.mid else "lo"
    if hit_side == near:
        return {"kind": "T"}
    nf = Frame(new_start, new_end, new_thickness, new_reference)
    x = line_intersection(nf.axis_point(0.0), nf.u, hf.axis_point(0.0), hf.u)
    if x is None or abs(_cross(nf.u, hf.u)) < math.sin(math.radians(5)):
        raise ValueError("El muro nuevo es paralelo al existente: no se puede hacer esquina")
    sx, _ = hf.local(hf.reference_point_from_axis(x))
    if not (EPS < sx < hf.length - EPS):
        # Ending beyond the host's ends: the engine already makes a corner.
        return {"kind": "T"}
    host_a, host_b = hf.a, hf.b
    keep_start = sx >= hf.length - sx if keep == "longer" else keep == "start"
    corner_ref = hf.reference_point_from_axis(x)
    if keep_start:
        host_b = corner_ref
    else:
        host_a = corner_ref
    return {"kind": "L", "new_end": nf.reference_point_from_axis(x),
            "host_a": host_a, "host_b": host_b, "cut_at": sx,
            "kept": "start" if keep_start else "end"}


def shift_openings(openings, ds, new_length):
    """Opening offsets after the wall's start moved ``ds`` metres forward.
    Raises ValueError if an opening would fall outside the new wall."""
    out = []
    for o in openings:
        off = float(o["offset"]) - ds
        if off < -1e-9 or off + float(o["width"]) > new_length + 1e-9:
            raise ValueError("Una carpintería del muro quedaría fuera del tramo que se conserva")
        out.append({**o, "offset": max(0.0, off)})
    return out


# --- extend / trim / pivot ---------------------------------------------------

def nearest_end(a, b, point):
    return 0 if math.dist(a, point) <= math.dist(b, point) else 1


def extend_to_line(a, b, end, p, q):
    """New (a, b) after moving end ``end`` (0: a, 1: b) of the reference line
    to its intersection with the infinite line p-q."""
    d = _sub(b, a)
    x = line_intersection(a, d, p, _sub(q, p))
    if x is None:
        raise ValueError("La línea límite es paralela al muro")
    na, nb = (x, b) if end == 0 else (a, x)
    if math.dist(na, nb) < 1e-6:
        raise ValueError("El muro quedaría con longitud nula")
    # The kept end must stay on the same side: no flipping through it.
    if _dot(_sub(nb, na), d) <= 0:
        raise ValueError("El límite queda al otro lado del extremo que se conserva")
    return na, nb


def move_end(a, b, end, point):
    na, nb = (tuple(point), b) if end == 0 else (a, tuple(point))
    if math.dist(na, nb) < 1e-6:
        raise ValueError("El muro quedaría con longitud nula")
    return na, nb


# --- parallel wall -----------------------------------------------------------

def parallel_wall(p, q, distance, side_point, thickness):
    """A wall parallel to the face p-q, whose near face is ``distance`` away
    on the side of ``side_point``. Returns (a, b, reference): the reference
    line IS the near face, and the body extends away from p-q."""
    f = Frame(p, q, max(thickness, 1e-6), "eje")
    _s, o = f.local(side_point)
    if abs(o) < 1e-9:
        raise ValueError("Indique el lado con un punto fuera de la línea")
    sign = 1.0 if o > 0 else -1.0
    shift = _mul(f.n, sign * float(distance))
    a, b = _add(f.a, shift), _add(f.b, shift)
    # body on the far side: to the left of a->b when sign > 0
    return a, b, "izquierda" if sign > 0 else "derecha"


def extend_to_faces(a, b, walls, max_gap, skip=()):
    """Extend or trim both ends of a reference line to the nearest wall face
    crossed within ``max_gap`` beyond each end, so that the ends land on
    faces (T junctions) even when the neighbours are oblique."""
    u = _sub(b, a)
    length = math.hypot(*u)
    u = (u[0] / length, u[1] / length)
    out = [a, b]
    for end, (origin, direction) in enumerate(((a, _mul(u, -1.0)), (b, u))):
        best = None
        for wid, (wa, wb, t, ref) in walls.items():
            if wid in skip:
                continue
            f = Frame(wa, wb, t, ref)
            for off in (f.lo, f.hi):
                x = line_intersection(origin, direction, f.point(0.0, off), f.u)
                if x is None:
                    continue
                s, _o = f.local(x)
                if not (-1e-9 <= s <= f.length + 1e-9):
                    continue
                along = _dot(_sub(x, origin), direction)
                if -max_gap <= along <= max_gap and (best is None or abs(along) < abs(best[0])):
                    best = (along, x)
        if best is not None:
            out[end] = best[1]
    if math.dist(out[0], out[1]) < 1e-6:
        raise ValueError("El muro paralelo quedaría con longitud nula")
    return out[0], out[1]

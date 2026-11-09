# SPDX-License-Identifier: GPL-3.0-or-later
"""Accept IngeCAD's own editing orders on BIM elements (user, 9-11-2026:
«no deseo hacer un programa dentro de otro»).

IngeCAD transforms a whole entity -its XDATA world points and vectors
included (DXF group codes 1011 and 1012, a DXF convention ezdxf follows)-
when it moves, rotates, scales, mirrors or copies it, and undo puts them
back.  So every BIM element carries an invisible reference frame: the world
origin and the three unit vectors, written whenever its data is written.
After any generic edit the frame holds exactly the transformation IngeCAD
applied, and the plugin brings the BIM data into line with it: positions,
thicknesses and sizes scale, a mirror swaps the side of a wall and the face
a door opens to, a room's interior point moves with its outline.  Nothing
is rejected; what cannot be represented exactly is reported.

It needs no hook or patch in IngeCAD: it is read when the plan is
regenerated (any plugin order, UNIONESARQ) and when exporting.  Drawings
without the frame (made before v1.17) keep the previous reading.
"""
from __future__ import annotations

import copy
import math

FRAME_APPID = "ARQMARCO"
KINDS = ("wall", "column", "opening", "space")
TOL = 1e-9


MAX_WITNESS = 16


def _vertices(entity):
    try:
        if entity.dxftype() == "LWPOLYLINE":
            return [tuple(map(float, p)) for p in entity.get_points("xy")][:MAX_WITNESS]
    except Exception:
        pass
    return None


def set_frame(entity):
    """Write the identity frame (the element's data is now current), and
    the outline it had then, in plain numbers IngeCAD does not transform."""
    doc = entity.doc
    if doc is not None and FRAME_APPID not in doc.appids:
        doc.appids.new(FRAME_APPID)
    tags = [(1011, (0.0, 0.0, 0.0)), (1012, (1.0, 0.0, 0.0)),
            (1012, (0.0, 1.0, 0.0)), (1012, (0.0, 0.0, 1.0))]
    pts = _vertices(entity)
    if pts:
        tags.append((1070, len(pts)))
        tags += [(1040, c) for p in pts for c in p]
    entity.set_xdata(FRAME_APPID, tags)


def read_frame(entity):
    """(origin, ex, ey, ez) as 3-tuples, or None (no frame, or a frame that
    does not belong to the current geometry).

    IngeCAD 0.x undoes a MIRROR of a polyline by restoring its properties
    and vertices but not its XDATA, which the mirror did transform (every
    other order is undone with the inverse matrix, XDATA included).  After
    «mirror + undo» the frame would still say «mirrored» on a polyline that
    is back where it was: when the outline is exactly the one stored with
    the frame, the frame is stale and is ignored.  (A wall mirrored about
    its own axis looks the same; use the side option for that.)"""
    try:
        if not entity.has_xdata(FRAME_APPID):
            return None
        tags = list(entity.get_xdata(FRAME_APPID))
    except Exception:
        return None
    pts = [tuple(map(float, t.value)) for t in tags if t.code in (1011, 1012)]
    if len(pts) != 4 or not all(math.isfinite(c) for p in pts for c in p):
        return None
    nums = [float(t.value) for t in tags if t.code == 1040]
    count = next((int(t.value) for t in tags if t.code == 1070), 0)
    if count and len(nums) == 2 * count and moved(tuple(pts)):
        witness = [(nums[2 * i], nums[2 * i + 1]) for i in range(count)]
        now = _vertices(entity)
        if now is not None and len(now) == len(witness) and all(
                math.dist(a, b) <= 1e-9 for a, b in zip(now, witness)):
            return ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    return tuple(pts)


def moved(frame, tol=TOL):
    """True when the frame is not the identity: IngeCAD transformed it."""
    if frame is None:
        return False
    ident = ((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1))
    return any(abs(a - b) > tol for p, q in zip(frame, ident) for a, b in zip(p, q))


class Affine:
    """The transformation recorded in a frame."""

    def __init__(self, frame):
        self.o, self.ex, self.ey, self.ez = frame
        self.det = self.ex[0] * self.ey[1] - self.ex[1] * self.ey[0]
        self.kz = self.ez[2] if abs(self.ez[2]) > 1e-12 else 1.0

    def point(self, p):
        x, y = float(p[0]), float(p[1])
        return [self.o[0] + x * self.ex[0] + y * self.ey[0], self.o[1] + x * self.ex[1] + y * self.ey[1]]

    def vector(self, v):
        x, y = float(v[0]), float(v[1])
        return (x * self.ex[0] + y * self.ey[0], x * self.ex[1] + y * self.ey[1])

    @property
    def mirrored(self):
        return self.det < 0

    @property
    def uniform(self):
        sx, sy = math.hypot(*self.ex[:2]), math.hypot(*self.ey[:2])
        dot = self.ex[0] * self.ey[0] + self.ex[1] * self.ey[1]
        return abs(sx - sy) <= 1e-9 * max(sx, sy, 1.0) and abs(dot) <= 1e-9 * max(sx * sy, 1.0)

    @property
    def scale(self):
        """Plan scale factor (the mean one when it is not uniform)."""
        return math.sqrt(abs(self.det))

    def z(self, base):
        return self.o[2] + self.kz * float(base)


def _scaled(value, factor):
    return float(value) * factor


def transform_record(m, aff, entity=None, hosts=None):
    """(new metadata, [notes]) for the element ``m`` after the
    transformation ``aff``.  The CAD geometry stays the authority for what it
    holds (a wall's axis, a column's outline); the rest follows here."""
    new = copy.deepcopy(m)
    notes = []
    kind = m.get("kind")
    label = m.get("name") or {"wall": "Muro", "column": "Pilar", "opening": "Carpintería",
                              "space": "Recinto"}.get(kind, "Elemento")
    if "base" in m:
        new["base"] = aff.z(m.get("base", 0.0))
    if "height" in m and abs(aff.kz - 1.0) > 1e-12:
        new["height"] = _scaled(m["height"], abs(aff.kz))
    if kind == "wall":
        a, b = m.get("a"), m.get("b")
        if a and b:
            if entity is not None and entity.dxftype() == "LWPOLYLINE" and len(entity) == 2:
                pts = [tuple(map(float, p)) for p in entity.get_points("xy")]
                na, nb = list(pts[0]), list(pts[1])
            else:
                na, nb = aff.point(a), aff.point(b)
            new["a"], new["b"] = na, nb
            u = (b[0] - a[0], b[1] - a[1])
            lu = math.hypot(*u) or 1.0
            n = (-u[1] / lu, u[0] / lu)                    # left normal before
            u2 = (nb[0] - na[0], nb[1] - na[1])
            lu2 = math.hypot(*u2) or 1.0
            n2 = (-u2[1] / lu2, u2[0] / lu2)              # left normal now
            mn = aff.vector(n)
            factor = abs(mn[0] * n2[0] + mn[1] * n2[1])   # distance between the faces
            if abs(factor - 1.0) > 1e-9:
                new["thickness"] = _scaled(m["thickness"], factor)
                if m.get("layers"):
                    new["layers"] = [[_scaled(t, factor), mat] for t, mat in m["layers"]]
            if aff.mirrored:
                ref = m.get("reference", "eje")
                new["reference"] = {"izquierda": "derecha", "derecha": "izquierda"}.get(ref, ref)
            if not aff.uniform:
                notes.append(f"{label}: escalado desigual; el espesor se toma en la dirección "
                             "perpendicular al eje")
    elif kind == "column":
        if m.get("center"):
            new["center"] = aff.point(m["center"])
        r = math.radians(float(m.get("rotation") or 0.0))
        X = aff.vector((math.cos(r), math.sin(r)))
        Y = aff.vector((-math.sin(r), math.cos(r)))
        fx, fy = math.hypot(*X), math.hypot(*Y)
        new["rotation"] = math.degrees(math.atan2(X[1], X[0]))
        shape = m.get("shape", "rect")
        if aff.mirrored and shape == "steel":
            new["mirrored"] = not bool(m.get("mirrored"))
        if abs(fx - 1.0) > 1e-9 or abs(fy - 1.0) > 1e-9:
            if shape == "steel":
                w, d = float(m.get("width") or 0), float(m.get("depth") or 0)
                new.update(shape="rect", width=w * fx, depth=d * fy)
                for k in ("profile", "mirrored"):
                    new.pop(k, None)
                notes.append(f"{label}: perfil {m.get('profile') or 'metálico'} escalado; pasa a sección "
                             f"rectangular genérica de {w * fx:.3f} × {d * fy:.3f} m".replace(".", ","))
            elif shape == "rect":
                for k, f in (("width", fx), ("depth", fy)):
                    if k in m:
                        new[k] = _scaled(m[k], f)
            else:
                if "radius" in m:
                    new["radius"] = _scaled(m["radius"], math.sqrt(fx * fy))
                if abs(fx - fy) > 1e-9:
                    notes.append(f"{label}: sección circular o regular escalada de forma desigual; "
                                 "se toma la de igual área")
            if m.get("cover"):
                new["cover"] = _scaled(m["cover"], math.sqrt(fx * fy))
            dot = X[0] * Y[0] + X[1] * Y[1]
            if abs(dot) > 1e-9 * fx * fy:
                notes.append(f"{label}: la deformación no conserva los ángulos rectos; "
                             "se toma la sección rectangular equivalente")
        new.pop("polygon", None)
    elif kind == "opening":
        f = aff.scale
        if abs(f - 1.0) > 1e-9:
            for k in ("offset", "width", "leaf", "leaf2", "frame_width", "frame_depth",
                      "leaf_thickness", "chord"):
                if k in m and isinstance(m[k], (int, float)):
                    new[k] = _scaled(m[k], f)
        if abs(aff.kz - 1.0) > 1e-12:
            new["sill"] = _scaled(m.get("sill", 0.0), aff.kz)
        if aff.mirrored:
            new["side"] = -int(m.get("side") or 1)
    elif kind == "space":
        for k in ("seed", "ref_vertex"):
            if m.get(k):
                new[k] = aff.point(m[k])
        if m.get("islands"):
            new["islands"] = [[aff.point(q) for q in h] for h in m["islands"]]
    return new, notes


def reconcile(entity, m, notes=None):
    """``m`` brought into line with the transformation in ``entity``'s
    frame (unchanged when there is none or it is the identity)."""
    frame = read_frame(entity)
    if not moved(frame):
        return m
    new, more = transform_record(m, Affine(frame), entity)
    if notes is not None:
        notes.extend(more)
    return new

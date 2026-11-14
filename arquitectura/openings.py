# SPDX-License-Identifier: GPL-3.0-or-later
"""Carpentry (doors, windows, plain gaps) hosted by a wall: one definition
for the plan symbol, the plan cut of the wall, the 3D void and the filling
element exported to IngeTrazo.

Record (XDATA ``kind: 'opening'``, schema 3), in the host wall's frame
(``s`` along its reference line from ``a``; ``off`` across it, +n to the
left of a→b):

* ``offset``/``width``: the HOLE in the wall, s0 = offset, s1 = offset+width;
  ``sill``/``height``: its bottom above the wall base and its height.
* ``type``: ``door`` | ``window`` | ``gap`` (a plain opening, «vano»).
* ``leaves`` 1 | 2; ``leaf`` (main leaf) and ``leaf2`` (second leaf; for a
  door 2 × leaf when 0), ``frame_width`` (each jamb of the frame) and
  ``frame_depth`` (0 = automatic: 0,15 m for a door, 0,05 m for a window,
  never more than the wall thickness).
  Door: width = leaf (+ leaf2) + 2 · frame_width.
* ``side`` +1 | -1: the face the door swings to / the window opens to
  (the interior). ``hinge`` 0 | 1: the jamb carrying a single leaf (0 at s0).
  ``angle``: drawn opening angle (degrees).
* ``face``: where the frame sits in the thickness: ``interior`` (flush with
  the ``side`` face), ``centrada`` or ``exterior`` (flush with the other).
* ``sill_kind`` (windows): ``alfeizar`` | ``vierteaguas`` | ``ventanal``.

The DXF carrier of the record is a 2-point polyline along the middle of the
wall from s0 to s1 (on the hidden opening layer). The plan symbol and the
jambs are derived and redrawn by UNIONESARQ: the record is the authority.
"""
from __future__ import annotations

import math

TYPES = ("door", "window", "gap")
NAMES = {"door": "Puerta", "window": "Ventana", "gap": "Hueco"}
IFC = {"door": "IfcDoor", "window": "IfcWindow", "gap": "IfcOpeningElement"}
FACES = ("interior", "centrada", "exterior")
SILLS = ("alfeizar", "vierteaguas", "ventanal")
SYMBOL_LAYER = "ARQ-CARPINTERIA"
V3_KEYS = ("leaves", "leaf", "leaf2", "frame_width", "frame_depth", "side", "hinge",
           "angle", "face", "sill_kind", "operation", "leaf_thickness",
           "frame_material", "leaf_material", "glass_material", "sill_material")
# opening type (IFC names, as in the properties dialog)
OPERATIONS = {"door": ("SWINGING", "SLIDING"), "window": ("SIDEHUNG", "SLIDING", "FIXED"), "gap": ("",)}
OPERATION_NAMES = {"SWINGING": "abatible", "SLIDING": "corredera", "SIDEHUNG": "abatible",
                   "FIXED": "fija", "": ""}
# usual single-leaf doors (leaf width, m): UNE 56803 interior leaves 625, 725
# and 825 mm (entrance 825); 925 mm is a usual COMMERCIAL size, not in the
# standard's table (user's notes, 07/11/2026)
DOOR_LEAVES = {"62": 0.625, "72": 0.725, "82": 0.825, "92": 0.925}
COMMERCIAL_LEAVES = {"92"}
# DB-SUA, Anejo A, accessible route: clear width >= 0,80 m measured in the
# frame, given by one leaf; at its widest opening, reduced by the leaf's
# thickness, >= 0,78 m. Leaf thickness 35/40/45 mm (UNE 56803): 40 mm default.
SUA_FRAME_MIN = 0.80
SUA_OPEN_MIN = 0.78
LEAF_THICKNESS = 0.040

DEFAULTS = {
    "door": {"leaves": 1, "leaf": 0.825, "leaf2": 0.0, "frame_width": 0.03, "frame_depth": 0.0,
             "side": 1, "hinge": 0, "angle": 90.0, "face": "interior", "sill": 0.0,
             "height": 2.10, "sill_kind": ""},
    "window": {"leaves": 2, "leaf": 0.0, "leaf2": 0.0, "frame_width": 0.05, "frame_depth": 0.0,
               "side": 1, "hinge": 0, "angle": 90.0, "face": "interior", "sill": 0.90,
               "height": 1.20, "width": 1.20, "sill_kind": "alfeizar"},
    "gap": {"leaves": 0, "leaf": 0.0, "leaf2": 0.0, "frame_width": 0.0, "frame_depth": 0.0,
            "side": 1, "hinge": 0, "angle": 0.0, "face": "centrada", "sill": 0.0,
            "height": 2.10, "width": 0.90, "sill_kind": ""},
}
SILL_PROJECTION = {"alfeizar": 0.03, "vierteaguas": 0.05, "ventanal": 0.0}
SILL_OVERHANG = 0.03          # beyond each jamb


def kind_of(text):
    t = str(text or "").strip().lower()
    return {"puerta": "door", "door": "door", "p": "door", "ventana": "window",
            "window": "window", "v": "window", "hueco": "gap", "vano": "gap", "gap": "gap",
            "h": "gap"}.get(t)


def normalise(rec):
    """A copy of ``rec`` with every schema-3 field (older records: defaults
    that keep their hole: a schema-2 door keeps its width as the hole)."""
    out = dict(rec)
    typ = out.get("type") if out.get("type") in TYPES else "door"
    out["type"] = typ
    for k, v in DEFAULTS[typ].items():
        if k in ("sill", "height", "width"):
            continue
        out.setdefault(k, v)
    out["leaves"] = int(out.get("leaves") or 0)
    out["side"] = 1 if float(out.get("side") or 1) >= 0 else -1
    out["hinge"] = 1 if int(out.get("hinge") or 0) else 0
    if out["face"] not in FACES:
        out["face"] = "centrada"
    ops = OPERATIONS[typ]
    if out.get("operation") not in ops:
        out["operation"] = ops[0]
    if typ == "door":
        out["leaves"] = 2 if out["leaves"] >= 2 else 1
        # on a curved wall the carpentry is planar: its width is the chord
        # between the jambs (``chord``), the record's ``width`` runs along the wall
        real = float(out.get("chord") or out["width"])
        clear = real - 2 * float(out["frame_width"])
        if clear <= 0:
            out["frame_width"], clear = 0.0, real
        if out["leaves"] == 1:
            out["leaf"], out["leaf2"] = clear, 0.0
        else:
            main = float(out.get("leaf") or 0)
            if not 0 < main < clear:
                main = clear / 2
            out["leaf"], out["leaf2"] = main, clear - main
    elif typ == "window":
        out["leaves"] = 1 if out["operation"] == "FIXED" else max(1, out["leaves"])
        if out["sill_kind"] not in SILLS:
            out["sill_kind"] = "alfeizar"
    out["ifc_class"] = IFC[typ] if typ != "gap" else "IfcOpeningElement"
    out["schema"] = 3
    return out


def clear_width(rec):
    """(in the frame, at the widest opening) of a door, for DB-SUA: the
    widest single leaf between the frame's jambs, and that less the leaf's
    thickness when it swings (a sliding leaf leaves the frame free). The
    real figures depend on the frame (rebates): the manufacturer's data
    rule; ``frame_width`` and ``leaf_thickness`` let it be matched."""
    rec = normalise(rec)
    if rec["type"] != "door":
        return None
    frame = max(float(rec["leaf"]), float(rec.get("leaf2") or 0.0))
    t = float(rec.get("leaf_thickness") or LEAF_THICKNESS)
    opened = frame if rec.get("operation") == "SLIDING" else frame - t
    return frame, opened


def sua_text(rec):
    """What the clear width says about DB-SUA, and only that: a dimensional
    check of the door (Anejo A, accessible route), not a verdict on the
    route nor on the building (audit R10, H12)."""
    cw = clear_width(rec)
    if cw is None:
        return ""
    frame, opened = cw
    ok = sua_accessible(rec)

    def m(v, d=3):
        return f"{v:.{d}f}".replace(".", ",")
    return (f"Paso libre {m(frame)} m en el marco y {m(opened)} m abierta. "
            f"Ancho mínimo de puerta en itinerario accesible (DB-SUA, anejo A: "
            f"{m(SUA_FRAME_MIN, 2)} y {m(SUA_OPEN_MIN, 2)} m): {'cumple' if ok else 'no cumple'}. "
            "Es solo una comprobación dimensional de la puerta; no evalúa el itinerario.")


def sua_accessible(rec):
    cw = clear_width(rec)
    return cw is not None and cw[0] + 1e-9 >= SUA_FRAME_MIN and cw[1] + 1e-9 >= SUA_OPEN_MIN


def door_width(leaf, leaves=1, leaf2=0.0, frame_width=0.03):
    """Hole width of a door from its leaves (second leaf = main when 0)."""
    leaf = float(leaf)
    second = (float(leaf2) or leaf) if int(leaves) >= 2 else 0.0
    return leaf + second + 2 * float(frame_width)


def frame_band(spec, rec):
    """(f0, f1): the frame across the thickness (wall offsets)."""
    t = spec.hi - spec.lo
    depth = float(rec.get("frame_depth") or 0.0)
    if depth <= 0:
        depth = 0.15 if rec["type"] == "door" else 0.05
    depth = min(depth, t)
    face = rec.get("face", "centrada")
    toward_hi = (rec["side"] > 0) == (face == "interior")
    if face == "centrada":
        mid = (spec.lo + spec.hi) / 2
        return mid - depth / 2, mid + depth / 2
    return (spec.hi - depth, spec.hi) if toward_hi else (spec.lo, spec.lo + depth)


# --- curved walls: the carpentry is planar, on the chord between the jambs ---------

def span_of(spec, chord):
    """Length along the wall's reference line of a planar carpentry of
    width ``chord`` (the same on a straight wall)."""
    if not getattr(spec, "curved", False):
        return float(chord)
    r = spec.r
    if float(chord) >= 2 * r - 1e-9:
        raise ValueError("la carpintería es más ancha que el diámetro del muro curvo")
    return 2 * r * math.asin(float(chord) / (2 * r))


def chord_of(spec, width):
    """Planar width of a carpentry that takes ``width`` along the wall."""
    if not getattr(spec, "curved", False):
        return float(width)
    return 2 * spec.r * math.sin(float(width) / (2 * spec.r))


def proxy(spec, rec):
    """(straight wall, record) on which a carpentry of a curved wall is drawn
    and built: the chord between its jambs on the reference line, with the
    band across the thickness that is wall at both jambs AND at mid span (a
    planar frame must fit in the curved wall). A straight wall is returned
    as it is."""
    if not getattr(spec, "curved", False):
        return spec, rec
    from .geom.junctions import Wall
    s0 = float(rec["offset"])
    s1 = s0 + float(rec["width"])
    a, b = spec.point(s0, 0.0), spec.point(s1, 0.0)
    pw = Wall(spec.id, a, b, spec.thickness, spec.reference)
    shift = pw.local(spec.point((s0 + s1) / 2, 0.0))[1]      # rise of the arc at mid span
    lo, hi = pw.lo + max(0.0, shift), pw.hi + min(0.0, shift)
    if hi - lo < 0.02:
        raise ValueError("la carpintería es demasiado ancha para la curvatura del muro: "
                         "no cabe un cerco plano en su espesor")
    pw.lo, pw.hi = lo, hi
    return pw, {**rec, "offset": 0.0, "width": math.dist(a, b)}


def carrier_points(spec, rec):
    mid = (spec.lo + spec.hi) / 2
    s0 = float(rec["offset"])
    return [spec.point(s0, mid), spec.point(s0 + float(rec["width"]), mid)]


def cut_polygon(spec, rec, extra=1e-3):
    """The hole in plan: the strip s0..s1 across the whole thickness (on a
    curved wall the jambs are radial and the faces arcs)."""
    s0 = float(rec["offset"])
    s1 = s0 + float(rec["width"])
    lo, hi = spec.lo - extra, spec.hi + extra
    if getattr(spec, "curved", False):
        return (spec.run(lo, spec.point(s0, lo), spec.point(s1, lo))
                + spec.run(hi, spec.point(s1, hi), spec.point(s0, hi)))
    return [spec.point(s0, lo), spec.point(s1, lo), spec.point(s1, hi), spec.point(s0, hi)]


def opening_cuts(specs, openings):
    """{wall id: [hole polygon]} for plan_outline, from the opening records
    (``specs``: {wall id: junctions.Wall})."""
    cuts = {}
    for o in openings:
        spec = specs.get(o.get("wall_id"))
        if spec is not None:
            cuts.setdefault(spec.id, []).append(cut_polygon(spec, o))
    return cuts


def _world_dir(spec, lx, ly):
    return (spec.u[0] * lx + spec.n[0] * ly, spec.u[1] * lx + spec.n[1] * ly)


def _arc(spec, center, radius, d_closed, d_open):
    """('arc', centre, r, start°, end°) sweeping CCW between two local dirs."""
    a = _world_dir(spec, *d_closed)
    b = _world_dir(spec, *d_open)
    ang_a = math.degrees(math.atan2(a[1], a[0]))
    ang_b = math.degrees(math.atan2(b[1], b[0]))
    if a[0] * b[1] - a[1] * b[0] >= 0:
        return ("arc", center, radius, ang_a, ang_b)
    return ("arc", center, radius, ang_b, ang_a)


def plan_symbol(spec, rec):
    """Derived plan drawing of an opening, in world coordinates:
    [('line', p, q) | ('poly', [pts], closed) | ('arc', c, r, a0, a1)]."""
    rec = normalise(rec)
    if getattr(spec, "curved", False):
        return plan_symbol(*proxy(spec, rec))
    s0 = float(rec["offset"])
    s1 = s0 + float(rec["width"])
    pt = spec.point
    out = []
    if rec["type"] == "gap":
        return out
    f0, f1 = frame_band(spec, rec)
    fw = float(rec.get("frame_width") or 0.0)
    sg = rec["side"]
    lt = float(rec.get("leaf_thickness") or LEAF_THICKNESS)
    if rec["type"] == "door":
        h = f1 if sg > 0 else f0            # the face of the frame it opens to
        if fw > 0:
            out += _jambs(pt, s0, s1, fw, f0, f1, h, lt)
        c0, c1 = s0 + fw, s1 - fw
        if rec["operation"] == "SLIDING":
            # leaves in their closed position on the face it opens to, each
            # overlapping the next one by 5 cm, and the direction it runs
            lap = 0.05
            if rec["leaves"] == 1:
                runs = [(c0, c1 + lap, sg * 0.02, 1 if rec["hinge"] == 0 else -1)]
            else:
                mid = c0 + float(rec["leaf"])
                runs = [(c0, mid + lap / 2, sg * 0.02, 1), (mid - lap / 2, c1, sg * 0.05, -1)]
            for a, b, d, direction in runs:
                out.append(("poly", [pt(a, h + d), pt(b, h + d), pt(b, h + d + sg * 0.02),
                                     pt(a, h + d + sg * 0.02)], True))
                tip = b if direction > 0 else a
                out.append(("line", pt((a + b) / 2, h + d + sg * 0.01), pt(tip, h + d + sg * 0.01)))
            return out
        ang = math.radians(float(rec.get("angle") or 90.0))
        leaves = []
        if rec["leaves"] == 1:
            if rec["hinge"] == 0:
                leaves.append((c0, 1, float(rec["leaf"])))
            else:
                leaves.append((c1, -1, float(rec["leaf"])))
        else:
            leaves.append((c0, 1, float(rec["leaf"])))
            leaves.append((c1, -1, float(rec["leaf2"])))
        for sh, direction, length in leaves:
            # the leaf is a board ``lt`` thick: opened ``ang`` about its hinge,
            # its thickness on the side that faces the opening
            dx, dy = direction * math.cos(ang), sg * math.sin(ang)
            qx, qy = direction * math.sin(ang), -sg * math.cos(ang)

            def at(u, v, sh=sh, dx=dx, dy=dy, qx=qx, qy=qy):
                return pt(sh + dx * u + qx * v, h + dy * u + qy * v)
            out.append(("poly", [at(0, 0), at(length, 0), at(length, lt), at(0, lt)], True))
            out.append(_arc(spec, pt(sh, h), length, (direction, 0.0), (dx, dy)))
        return out
    # window: frame jambs, the leaves (profiles with their glass), the mark
    # where two leaves meet, the sill on the exterior face closing the hole
    if fw > 0:
        for a, b in ((s0, s0 + fw), (s1 - fw, s1)):
            out.append(("poly", [pt(a, f0), pt(b, f0), pt(b, f1), pt(a, f1)], True))
    c0, c1 = s0 + fw, s1 - fw
    mid = (f0 + f1) / 2
    band = f1 - f0
    n = max(1, int(rec["leaves"]))
    if rec["operation"] == "SLIDING" and n > 1:
        # leaves on two tracks, overlapping 5 cm
        lap, step = 0.05, (c1 - c0) / n
        d = band / 3
        for k in range(n):
            a = c0 + k * step - (lap / 2 if k else 0)
            b = c0 + (k + 1) * step + (lap / 2 if k < n - 1 else 0)
            o0 = f0 + (d * 0.25 if k % 2 == 0 else d * 1.75)
            out.append(("poly", [pt(a, o0), pt(b, o0), pt(b, o0 + d), pt(a, o0 + d)], True))
            out.append(("line", pt(a, o0 + d / 2), pt(b, o0 + d / 2)))
    else:
        dl = min(0.045, band * 0.8)
        lo, hi = mid - dl / 2, mid + dl / 2
        if rec["operation"] == "FIXED":
            n = 1
        step = (c1 - c0) / n
        for k in range(n):
            a, b = c0 + k * step, c0 + (k + 1) * step
            out.append(("poly", [pt(a, lo), pt(b, lo), pt(b, hi), pt(a, hi)], True))
            out.append(("line", pt(a, mid), pt(b, mid)))              # the glass
        for k in range(1, n):
            sk = c0 + k * step
            out.append(("line", pt(sk, f0 - 0.03), pt(sk, f1 + 0.03)))   # where two leaves meet
    proj = SILL_PROJECTION.get(rec.get("sill_kind"), 0.0)
    if proj > 0:
        ext, e = (spec.lo, -1) if sg > 0 else (spec.hi, 1)
        a, b = s0 - SILL_OVERHANG, s1 + SILL_OVERHANG
        out.append(("poly", [pt(a, ext), pt(a, ext + e * proj), pt(b, ext + e * proj),
                             pt(b, ext)], True))
    return out


def _jambs(pt, s0, s1, fw, f0, f1, h, lt, stop=0.01):
    """The two jambs of a door frame, in plan: ``fw`` wide where the leaf
    closes (its thickness ``lt``, on the face ``h`` it opens to) and a stop
    of ``stop`` more on the rest of the frame depth (the rebate the leaf
    closes against)."""
    far = f0 if h == f1 else f1
    sgn = 1 if h == f1 else -1
    out = []
    if abs(f1 - f0) <= lt + 0.005:
        for a, b in ((s0, s0 + fw), (s1 - fw, s1)):
            out.append(("poly", [pt(a, f0), pt(b, f0), pt(b, f1), pt(a, f1)], True))
        return out
    r = h - sgn * lt                     # the rebate line
    for edge, d in ((s0, 1), (s1, -1)):
        out.append(("poly", [pt(edge, far), pt(edge + d * (fw + stop), far), pt(edge + d * (fw + stop), r),
                             pt(edge + d * fw, r), pt(edge + d * fw, h), pt(edge, h)], True))
    return out


# --- the carpentry in 3D: frame, leaves, glass and sill -----------------------
#
# The pieces come from the same record (and the same rules) as the plan
# symbol above: the jambs and the head of the frame, each leaf where it
# closes, the sash profiles and the glass of a window, the sill outside.
# Boxes in the wall's own coordinates (s along it, o across it, z up), a
# hair apart so that every piece is a closed solid of its own (one mesh in
# IngeTrazo, one IfcDoor/IfcWindow in the IFC). User's request and audit R10
# (S1): a door or a window must not reach IngeTrazo as a plain block.

PART_GAP = 0.0005
GLASS_THICKNESS = 0.024          # double glazing 4/16/4
SASH_PROFILE = 0.06
DOOR_FLOOR_GAP = 0.005
SILL_THICKNESS = 0.03
PART_NAMES = {"frame": "Marco", "leaf": "Hoja", "glass": "Vidrio", "sill": "Alféizar"}
MATERIALS = {"door": {"frame": "Madera", "leaf": "Madera"},
             "window": {"frame": "Aluminio", "leaf": "Aluminio", "glass": "Vidrio", "sill": "Piedra"}}


def part_material(rec, role):
    """The material of a piece: the record's own (``frame_material``...) or
    the usual one for its kind."""
    key = {"frame": "frame_material", "leaf": "leaf_material", "glass": "glass_material",
           "sill": "sill_material"}[role]
    return str(rec.get(key) or MATERIALS.get(rec.get("type"), {}).get(role) or "")


def carpentry_parts(spec, rec, base):
    """[{'name', 'role', 'material', 'box': (s0, s1, o0, o1, z0, z1)} or
    {..., 'prism': (outline, holes, o0, o1)}] of a door or a window (none for
    a gap): outlines in (s, z), extruded across o0..o1. On a curved wall, on
    its ``proxy``."""
    rec = normalise(rec)
    if rec["type"] == "gap":
        return []
    spec, rec = proxy(spec, rec)
    g = PART_GAP
    f0, f1 = frame_band(spec, rec)
    s0 = float(rec["offset"])
    s1 = s0 + float(rec["width"])
    z0 = float(base) + float(rec["sill"])
    z1 = z0 + float(rec["height"])
    fw = max(0.0, float(rec.get("frame_width") or 0.0))
    sg = rec["side"]
    out = []

    def add(role, box, k=None):
        a, b, p, q, lo, hi = box
        if b - a > 1e-4 and q - p > 1e-4 and hi - lo > 1e-4:
            name = PART_NAMES[role] + (f" {k}" if k else "")
            out.append({"name": name, "role": role, "material": part_material(rec, role),
                        "box": (a, b, p, q, lo, hi)})

    door = rec["type"] == "door"
    if fw > 0 and 2 * fw < s1 - s0 and 2 * fw < z1 - z0:
        # the frame is ONE ring around the hole (jambs, head and, in a door,
        # a 5 mm threshold under the leaf): its face is the outline of the
        # whole door or window, what IngeTrazo measures their Width and
        # Height on (OverallWidth/OverallHeight in the IFC)
        bottom = z0 + (DOOR_FLOOR_GAP if door else fw)
        ring = ([(s0, z0), (s1, z0), (s1, z1), (s0, z1)],
                [[(s0 + fw, bottom), (s1 - fw, bottom), (s1 - fw, z1 - fw), (s0 + fw, z1 - fw)]])
        out.append({"name": PART_NAMES["frame"], "role": "frame",
                    "material": part_material(rec, "frame"), "prism": ring + (f0, f1)})
        c0, c1 = s0 + fw + g, s1 - fw - g
        zt = z1 - fw - g
        zb = bottom + g
    else:
        c0, c1, zt = s0, s1, z1
        zb = z0 + DOOR_FLOOR_GAP if door else z0
    if door:
        lt = min(float(rec.get("leaf_thickness") or LEAF_THICKNESS), f1 - f0)
        h = f1 if sg > 0 else f0
        if rec["operation"] == "SLIDING":
            lap = 0.05
            if rec["leaves"] == 1:
                runs = [(c0, c1 + lap, sg * 0.02)]
            else:
                mid = c0 + float(rec["leaf"])
                runs = [(c0, mid + lap / 2, sg * 0.02), (mid - lap / 2, c1, sg * 0.05)]
            for k, (a, b, d) in enumerate(runs, 1):
                p, q = sorted((h + d, h + d + sg * 0.02))
                add("leaf", (a, b, p, q, zb, zt), k if len(runs) > 1 else None)
            return out
        p, q = (h - lt, h) if sg > 0 else (h, h + lt)
        if rec["leaves"] == 1:
            add("leaf", (c0, c1, p, q, zb, zt))
        else:
            m = c0 + float(rec["leaf"])
            add("leaf", (c0, m - g / 2, p, q, zb, zt), 1)
            add("leaf", (m + g / 2, c1, p, q, zb, zt), 2)
        return out
    # window: sashes (stiles, rails) with their glass
    mid, band = (f0 + f1) / 2, f1 - f0
    n = max(1, int(rec["leaves"]))
    if rec["operation"] == "FIXED":
        n = 1
    leaves = []
    if rec["operation"] == "SLIDING" and n > 1:
        lap, step, d = 0.05, (c1 - c0) / n, band / 3
        for k in range(n):
            a = c0 + k * step - (lap / 2 if k else 0)
            b = c0 + (k + 1) * step + (lap / 2 if k < n - 1 else 0)
            o0 = f0 + (d * 0.25 if k % 2 == 0 else d * 1.75)
            leaves.append((a, b, o0, o0 + d))
    else:
        dl = min(0.045, band * 0.8)
        step = (c1 - c0) / n
        for k in range(n):
            a = c0 + k * step + (g / 2 if k else 0)
            b = c0 + (k + 1) * step - (g / 2 if k < n - 1 else 0)
            leaves.append((a, b, mid - dl / 2, mid + dl / 2))
    for k, (a, b, p, q) in enumerate(leaves, 1):
        tag = k if len(leaves) > 1 else None
        pr = min(SASH_PROFILE, (b - a) / 4, (zt - zb) / 4)
        add("leaf", (a, a + pr, p, q, zb, zt), tag)
        add("leaf", (b - pr, b, p, q, zb, zt), tag)
        add("leaf", (a + pr + g, b - pr - g, p, q, zb, zb + pr), tag)
        add("leaf", (a + pr + g, b - pr - g, p, q, zt - pr, zt), tag)
        gt = min(GLASS_THICKNESS, (q - p) * 0.6)
        gm = (p + q) / 2
        add("glass", (a + pr + g, b - pr - g, gm - gt / 2, gm + gt / 2, zb + pr + g, zt - pr - g), tag)
    proj = SILL_PROJECTION.get(rec.get("sill_kind"), 0.0)
    if proj > 0:
        ext, e = (spec.lo, -1) if sg > 0 else (spec.hi, 1)
        p, q = sorted((ext, ext + e * proj))
        add("sill", (s0 - SILL_OVERHANG, s1 + SILL_OVERHANG, p, q, z0 - SILL_THICKNESS, z0))
    return out


def carpentry_spec(spec, rec):
    """The spec the pieces of ``carpentry_parts`` are measured on (the chord
    of a curved wall)."""
    return proxy(spec, normalise(rec))[0]


def filling_box(spec, rec, base):
    """(s0, s1, f0, f1, z0, z1) of the door/window body (frame + leaves as
    one solid filling the hole across the frame depth). On a curved wall the
    values are on its ``proxy`` (the planar carpentry on the chord)."""
    rec = normalise(rec)
    spec, rec = proxy(spec, rec)
    f0, f1 = frame_band(spec, rec)
    s0 = float(rec["offset"])
    z0 = float(base) + float(rec["sill"])
    return s0, s0 + float(rec["width"]), f0, f1, z0, z0 + float(rec["height"])


# --- clear spans («paramentos») --------------------------------------------

def face_spans(spec, segments, tol=1e-6):
    """{'lo': [(s0, s1)], 'hi': [...]}: the visible stretches of each face of
    the wall in the solved plan (segments: plan_outline lines of THIS wall)."""
    out = {"lo": [], "hi": []}
    for a, b in segments:
        sa, oa = spec.local(a)
        sb, ob = spec.local(b)
        for key, off in (("lo", spec.lo), ("hi", spec.hi)):
            if abs(oa - off) < tol and abs(ob - off) < tol and abs(sb - sa) > tol:
                out[key].append((min(sa, sb), max(sa, sb)))
    for key in out:
        merged = []
        for s0, s1 in sorted(out[key]):
            if merged and s0 <= merged[-1][1] + tol:
                merged[-1] = (merged[-1][0], max(merged[-1][1], s1))
            else:
                merged.append((s0, s1))
        out[key] = merged
    return out


def span_at(spans, s):
    """The stretch containing s (or the nearest one)."""
    if not spans:
        return None
    return min(spans, key=lambda r: 0.0 if r[0] - 1e-9 <= s <= r[1] + 1e-9
               else min(abs(s - r[0]), abs(s - r[1])))


def free_span(spec, segments, s, side):
    """(clicked-face stretch, other-face stretch, usable = both) at s."""
    spans = face_spans(spec, segments)
    mine = span_at(spans["hi" if side > 0 else "lo"], s)
    if mine is None:
        return None, None, None
    others = spans["lo" if side > 0 else "hi"]
    # the stretch of the other face in front of the click; only if there is
    # none there, the one sharing most with the clicked stretch (a column or
    # a wall against the other face splits it, and the longest piece may be
    # elsewhere: the door was refused as «no cabe», prueba del 10-11)
    facing = [r for r in others if r[0] - 1e-9 <= s <= r[1] + 1e-9]
    other = facing[0] if facing else max(
        others, key=lambda r: min(r[1], mine[1]) - max(r[0], mine[0]), default=None)
    if other is None or min(other[1], mine[1]) <= max(other[0], mine[0]):
        return mine, None, mine
    return mine, other, (max(mine[0], other[0]), min(mine[1], other[1]))


def place(mode, width, s, span, usable, distance=0.0, other=None, anchor="lateral"):
    """(s0, hinge, width) for a placement mode («libre» is decided by the
    tool with its second click):
    * ``distancia``: the jamb nearest the clicked end of the stretch at
      ``distance`` from its corner (``anchor='medio'``: the centre of the
      hole at that distance);
    * ``centrada``: centred on the clicked face's stretch;
    * ``centrada_ext``: centred on the other face's stretch;
    * ``maxima``: the whole usable stretch."""
    u0, u1 = usable
    if mode == "distancia":
        if anchor == "medio":             # the distance is to the centre of the hole
            distance -= width / 2
        if s - u0 <= u1 - s:
            return u0 + distance, 0, width
        return u1 - distance - width, 1, width
    if mode in ("centrada", "centrada_ext"):
        ref = other if mode == "centrada_ext" and other else span
        mid = (ref[0] + ref[1]) / 2
        return mid - width / 2, (0 if s <= mid else 1), width
    if mode == "maxima":
        return u0, 0, u1 - u0
    raise ValueError("Modo de colocación desconocido: " + str(mode))

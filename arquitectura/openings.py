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
           "angle", "face", "sill_kind", "operation")
# opening type (IFC names, as in the properties dialog)
OPERATIONS = {"door": ("SWINGING", "SLIDING"), "window": ("SIDEHUNG", "SLIDING", "FIXED"), "gap": ("",)}
OPERATION_NAMES = {"SWINGING": "abatible", "SLIDING": "corredera", "SIDEHUNG": "abatible",
                   "FIXED": "fija", "": ""}
# usual single-leaf doors (leaf width, m): standard leaves 625/725/825/925 mm
DOOR_LEAVES = {"62": 0.625, "72": 0.725, "82": 0.825, "92": 0.925}

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
        clear = float(out["width"]) - 2 * float(out["frame_width"])
        if clear <= 0:
            out["frame_width"], clear = 0.0, float(out["width"])
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


def carrier_points(spec, rec):
    mid = (spec.lo + spec.hi) / 2
    s0 = float(rec["offset"])
    return [spec.point(s0, mid), spec.point(s0 + float(rec["width"]), mid)]


def cut_polygon(spec, rec, extra=1e-3):
    """The hole in plan: the strip s0..s1 across the whole thickness."""
    s0 = float(rec["offset"])
    s1 = s0 + float(rec["width"])
    lo, hi = spec.lo - extra, spec.hi + extra
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
    s0 = float(rec["offset"])
    s1 = s0 + float(rec["width"])
    pt = spec.point
    out = []
    if rec["type"] == "gap":
        return out
    f0, f1 = frame_band(spec, rec)
    fw = float(rec.get("frame_width") or 0.0)
    sg = rec["side"]
    if rec["type"] == "door":
        if fw > 0:
            for a, b in ((s0, s0 + fw), (s1 - fw, s1)):
                out.append(("poly", [pt(a, f0), pt(b, f0), pt(b, f1), pt(a, f1)], True))
        c0, c1 = s0 + fw, s1 - fw
        h = f1 if sg > 0 else f0            # hinge on the swing face of the frame
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
        for s, direction, length in leaves:
            hinge = pt(s, h)
            closed = (direction, 0.0)
            opened = (direction * math.cos(ang), sg * math.sin(ang))
            tip = _world_dir(spec, *opened)
            out.append(("line", hinge, (hinge[0] + tip[0] * length, hinge[1] + tip[1] * length)))
            out.append(_arc(spec, hinge, length, closed, opened))
        return out
    # window: frame, glazing, leaf divisions and the sill on the exterior face
    out.append(("poly", [pt(s0, f0), pt(s1, f0), pt(s1, f1), pt(s0, f1)], True))
    mid = (f0 + f1) / 2
    n = max(1, int(rec["leaves"]))
    if rec["operation"] == "SLIDING" and n > 1:
        # leaves on two tracks, overlapping 5 cm
        lap, step = 0.05, (s1 - s0 - 2 * fw) / n
        for k in range(n):
            a = s0 + fw + k * step - (lap / 2 if k else 0)
            b = s0 + fw + (k + 1) * step + (lap / 2 if k < n - 1 else 0)
            off = f0 + (f1 - f0) * (1 if k % 2 == 0 else 2) / 3
            out.append(("line", pt(a, off), pt(b, off)))
    else:
        out.append(("line", pt(s0 + fw, mid), pt(s1 - fw, mid)))
        for k in range(1, n):
            s = s0 + (s1 - s0) * k / n
            out.append(("line", pt(s, f0), pt(s, f1)))
    proj = SILL_PROJECTION.get(rec.get("sill_kind"), 0.0)
    if proj > 0:
        ext, e = (spec.lo, -1) if sg > 0 else (spec.hi, 1)
        a, b = s0 - SILL_OVERHANG, s1 + SILL_OVERHANG
        out.append(("poly", [pt(a, ext), pt(a, ext + e * proj), pt(b, ext + e * proj),
                             pt(b, ext)], False))
    return out


def filling_box(spec, rec, base):
    """(s0, s1, f0, f1, z0, z1) of the door/window body (frame + leaves as
    one solid filling the hole across the frame depth)."""
    rec = normalise(rec)
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
    other = max(others, key=lambda r: min(r[1], mine[1]) - max(r[0], mine[0]), default=None)
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

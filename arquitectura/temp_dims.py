# SPDX-License-Identifier: GPL-3.0-or-later
"""Temporary dimensions while drawing walls and placing carpentry.

The behaviour of the usual BIM programs, described functionally: while the
cursor moves, provisional dimensions show where the element will go — the
distance from each side of a door or window to the nearest reference on its
wall (a corner or another opening's jamb) and its width; the length and angle
of a wall being drawn and its distance to the nearest parallel walls. One of
them is *active*: typing a number places the element exactly at that
distance; another key (F6, or the option «cota») moves to the next one, and
«eje» switches between measuring to the jamb or to the centre.

Nothing here is drawn into the drawing. IngeCAD 0.8 renders the dimensions as
virtual entities through its own engine (``Tool.preview_entities``), with
real text, sized in screen pixels so they read the same at any zoom. On a
host without that hook only the lines are given (``segments``), through the
preview every IngeCAD has.
"""
from __future__ import annotations

import math

# sizes in screen pixels (converted with the host's px_to_space)
OFFSET_PX = 26        # dimension line from the measured face
STEP_PX = 22          # between two rows of dimensions
TEXT_PX = 11          # text height
TICK_PX = 5           # half-length of the 45° tick
GAP_PX = 3            # text above the dimension line
EXT_PX = 4            # extension line beyond the dimension line

ACTIVE_COLOR = 30     # orange: the dimension a typed number goes to
OTHER_COLOR = 140     # blue: informative
MIN_SHOWN = 1e-4


def world_per_px(ctx, fallback=0.01):
    """Drawing units per screen pixel at the current zoom (IngeCAD's
    px_to_space; a fixed value where the host has none, e.g. in tests)."""
    fn = getattr(getattr(ctx, "services", None), "px_to_space", None)
    try:
        v = float(fn(1.0)) if callable(fn) else 0.0
    except Exception:  # noqa: BLE001
        v = 0.0
    return v if v > 0 and math.isfinite(v) else fallback


def fmt(value):
    """2 decimals with the Spanish comma: 1,25."""
    return f"{float(value):.2f}".replace(".", ",")


def parse_length(text):
    """A typed distance in metres (comma or dot; «125cm» or «125 cm»).
    ValueError if it is not a non-negative number."""
    t = str(text).strip().lower().replace(" ", "")
    scale = 1.0
    if t.endswith("cm"):
        t, scale = t[:-2], 0.01
    elif t.endswith("m"):
        t = t[:-1]
    v = float(t.replace(",", ".")) * scale
    if not math.isfinite(v) or v < 0:
        raise ValueError("distancia no válida")
    return v


class Dim:
    """A dimension from ``a`` to ``b`` (points on the measured line), drawn
    ``offset`` drawing units away along the unit vector ``out``."""

    def __init__(self, a, b, out, offset, text, active=False, role=""):
        self.a, self.b = (float(a[0]), float(a[1])), (float(b[0]), float(b[1]))
        self.out = out
        self.offset = float(offset)
        self.text = text
        self.active = bool(active)
        self.role = role

    @property
    def length(self):
        return math.dist(self.a, self.b)

    def line(self):
        ox, oy = self.out[0] * self.offset, self.out[1] * self.offset
        return ((self.a[0] + ox, self.a[1] + oy), (self.b[0] + ox, self.b[1] + oy))

    def segments(self, px):
        """Extension lines, dimension line and 45° ticks (architectural
        style), in drawing units."""
        if self.length < MIN_SHOWN:
            return []
        d1, d2 = self.line()
        ex = (self.out[0] * EXT_PX * px, self.out[1] * EXT_PX * px)
        segs = [(self.a, (d1[0] + ex[0], d1[1] + ex[1])),
                (self.b, (d2[0] + ex[0], d2[1] + ex[1])),
                (d1, d2)]
        ux, uy = (d2[0] - d1[0]) / self.length, (d2[1] - d1[1]) / self.length
        tx, ty = (ux + self.out[0]) * TICK_PX * px / math.sqrt(2), (uy + self.out[1]) * TICK_PX * px / math.sqrt(2)
        for c in (d1, d2):
            segs.append(((c[0] - tx, c[1] - ty), (c[0] + tx, c[1] + ty)))
        return segs

    def text_place(self, px):
        """(insertion point, rotation in degrees, height): centred above
        the line, always readable (never upside down)."""
        d1, d2 = self.line()
        ang = math.degrees(math.atan2(d2[1] - d1[1], d2[0] - d1[0]))
        if ang > 90.0 + 1e-9 or ang <= -90.0:
            ang += 180.0
        ang = (ang + 180.0) % 360.0 - 180.0
        mid = ((d1[0] + d2[0]) / 2, (d1[1] + d2[1]) / 2)
        # «above» = the side of the text's own up direction
        up = (-math.sin(math.radians(ang)), math.cos(math.radians(ang)))
        g = GAP_PX * px
        return (mid[0] + up[0] * g, mid[1] + up[1] * g), ang, TEXT_PX * px


def segments(dims, px):
    out = []
    for d in dims:
        out += d.segments(px)
    return out


def entities(doc, dims, px):
    """Virtual LINE and TEXT entities for ``dims`` (never added to the
    drawing): what IngeCAD 0.8 renders through Tool.preview_entities."""
    from ezdxf.entities import Line, Text
    from ezdxf.enums import TextEntityAlignment
    out = []
    for d in dims:
        if d.length < MIN_SHOWN:
            continue
        color = ACTIVE_COLOR if d.active else OTHER_COLOR
        for a, b in d.segments(px):
            out.append(Line.new(dxfattribs={"start": (a[0], a[1], 0.0), "end": (b[0], b[1], 0.0),
                                            "color": color, "layer": "0"}, doc=doc))
        at, rot, h = d.text_place(px)
        t = Text.new(dxfattribs={"text": d.text, "height": h,
                                 "rotation": rot, "color": color, "layer": "0"}, doc=doc)
        t.set_placement((at[0], at[1], 0.0), align=TextEntityAlignment.BOTTOM_CENTER)
        out.append(t)
    return out


# --- carpentry: references on its wall -------------------------------------------------
def opening_jambs(openings, wall_id, exclude=None):
    """[(s0, s1)] of the other openings on the wall (exclude: an opening's id)."""
    out = []
    for m in openings or ():
        if m.get("wall_id") != wall_id or (exclude and m.get("id") == exclude):
            continue
        try:
            s0 = float(m["offset"])
            out.append((s0, s0 + float(m["width"])))
        except (KeyError, TypeError, ValueError):
            continue
    return out


def references(usable, jambs, s0, s1):
    """(left, right): the nearest reference before ``s0`` and after ``s1`` —
    the ends of the free stretch of wall and the jambs of other openings."""
    left, right = float(usable[0]), float(usable[1])
    for j0, j1 in jambs:
        if j1 <= s0 + 1e-6:
            left = max(left, j1)
        if j0 >= s1 - 1e-6:
            right = min(right, j0)
    return left, right


def carpentry_dims(spec, side, s0, width, left, right, px, active="left", to_axis=False):
    """The chain left reference | opening | right reference, on the face the
    opening is placed from, outside the wall on that side."""
    off_face = spec.hi if side > 0 else spec.lo
    sign = 1.0 if side > 0 else -1.0
    mid = s0 + width / 2.0
    t = spec.tangent(mid)
    n = (-t[1], t[0])
    out = (n[0] * sign, n[1] * sign)
    off = OFFSET_PX * px
    p = lambda s: spec.point(s, off_face)  # noqa: E731
    a0 = mid if to_axis else s0
    a1 = mid if to_axis else s0 + width
    other_face = spec.lo if side > 0 else spec.hi
    q = lambda s: spec.point(s, other_face)  # noqa: E731
    back = (-out[0], -out[1])
    # the width on the other side of the wall: on this side it would cross
    # the leaf's swing
    dims = [Dim(p(left), p(a0), out, off, fmt(a0 - left), active == "left", "left"),
            Dim(p(a1), p(right), out, off, fmt(right - a1), active == "right", "right"),
            Dim(q(s0), q(s0 + width), back, off, fmt(width), False, "width")]
    return dims


def placement_from_distance(which, distance, left, right, width, to_axis=False):
    """s0 of an opening at ``distance`` from the reference ``which``
    («left»/«right»), measured to its jamb or (to_axis) to its centre."""
    if which == "left":
        s0 = left + distance - (width / 2.0 if to_axis else 0.0)
    else:
        s0 = right - distance - (width / 2.0 if to_axis else width)
    if s0 < left - 1e-6 or s0 + width > right + 1e-6:
        raise ValueError(f"no cabe a {fmt(distance)} m: entre las referencias quedan "
                         f"{fmt(right - left)} m y el hueco mide {fmt(width)} m")
    return s0


# --- walls: length, angle and parallel walls ---------------------------------------------
def wall_dims(a, b, thickness, lo, hi, specs, px, max_dist=12.0):
    """Length of the wall being drawn (outside its left face), and the
    perpendicular distance from its end to the nearest parallel wall face on
    each side (axis to face), among ``specs`` (existing walls)."""
    L = math.dist(a, b)
    if L < 1e-6:
        return []
    u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
    n = (-u[1], u[0])
    dims = []
    ang = math.degrees(math.atan2(u[1], u[0])) % 360.0
    face = lambda p, off: (p[0] + n[0] * off, p[1] + n[1] * off)  # noqa: E731
    dims.append(Dim(face(a, hi), face(b, hi), n, OFFSET_PX * px,
                    f"{fmt(L)}  <{ang:.1f}°".replace(".", ","), True, "length"))
    best = {1: None, -1: None}
    for w in specs or ():
        if getattr(w, "curved", False):
            continue
        cross = u[0] * w.u[1] - u[1] * w.u[0]
        if abs(cross) > 0.02:
            continue
        sb, _ob = w.local(b)
        if not -1e-6 <= sb <= w.length + 1e-6:
            continue
        for off in (w.lo, w.hi):
            q = w.point(sb, off)
            d = (q[0] - b[0]) * n[0] + (q[1] - b[1]) * n[1]
            if abs(d) < 1e-6 or abs(d) > max_dist:
                continue
            k = 1 if d > 0 else -1
            if best[k] is None or abs(d) < abs(best[k][0]):
                best[k] = (d, q)
    for k, hit in best.items():
        if hit is None:
            continue
        d, q = hit
        dims.append(Dim(b, q, u, OFFSET_PX * px * 0.6, fmt(abs(d)), False, "parallel"))
    return dims

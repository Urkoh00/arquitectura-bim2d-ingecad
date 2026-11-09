# SPDX-License-Identifier: GPL-3.0-or-later
"""COTAMUROS: automatic chain dimensions across walls.

Two clicks draw a line through the plan; every wall face, column outline
and jamb it crosses is dimensioned (a line drawn outside, along a façade,
dimensions that façade's corners and openings instead), in one chain of IngeCAD aligned
dimensions (``core.actions.dim_aligned``) plus an optional overall
dimension.  The points come from the same derived outline the 3D model
uses (``junction_edge`` entities), so the dimensions are the real faces.

Dimensions are ordinary IngeCAD DIMENSION entities on ARQ-COTAS with the
``ARQ`` dimension style (metres, 2 decimals, comma, tick marks), so the
user edits them with IngeCAD's own tools.  They are not associative: after
moving a wall, run COTAMUROS again.
"""
from __future__ import annotations

import math

DIM_LAYER = "ARQ-COTAS"
DIM_STYLE = "ARQ"
MERGE = 0.005          # points closer than 5 mm are the same face


def _seg_seg(p, q, a, b):
    """Parameter t on p->q where it crosses segment a-b, or None."""
    rx, ry = q[0] - p[0], q[1] - p[1]
    sx, sy = b[0] - a[0], b[1] - a[1]
    den = rx * sy - ry * sx
    if abs(den) < 1e-12:
        return None
    qpx, qpy = a[0] - p[0], a[1] - p[1]
    t = (qpx * sy - qpy * sx) / den
    u = (qpx * ry - qpy * rx) / den
    if -1e-9 <= t <= 1 + 1e-9 and -1e-9 <= u <= 1 + 1e-9:
        return t
    return None


def _seg_arc(p, q, c, r, a0, a1):
    """Parameters t on p->q where it crosses the arc (degrees, CCW a0->a1)."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    fx, fy = p[0] - c[0], p[1] - c[1]
    A = dx * dx + dy * dy
    B = 2 * (fx * dx + fy * dy)
    C = fx * fx + fy * fy - r * r
    disc = B * B - 4 * A * C
    if A < 1e-18 or disc < 0:
        return []
    out = []
    span = (a1 - a0) % 360.0 or 360.0
    for s in (-1, 1):
        t = (-B + s * math.sqrt(disc)) / (2 * A)
        if -1e-9 <= t <= 1 + 1e-9:
            x, y = p[0] + t * dx, p[1] + t * dy
            ang = math.degrees(math.atan2(y - c[1], x - c[0]))
            if (ang - a0) % 360.0 <= span + 1e-7:
                out.append(t)
    return out


def crossings(edges, p, q):
    """Sorted, merged points where p->q crosses the outline ``edges``.

    ``edges``: ("line", a, b) or ("arc", centre, radius, start°, end°)."""
    ts = []
    for e in edges:
        if e[0] == "line":
            t = _seg_seg(p, q, e[1], e[2])
            if t is not None:
                ts.append(t)
        else:
            ts.extend(_seg_arc(p, q, e[1], e[2], e[3], e[4]))
    length = math.hypot(q[0] - p[0], q[1] - p[1])
    if length < 1e-9:
        return []
    ts.sort()
    pts, last = [], None
    for t in ts:
        if last is not None and (t - last) * length < MERGE:
            continue
        last = t
        pts.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return pts


def facade_points(edges, p, q, reach=3.0, tol_deg=1.0):
    """For a line drawn OUTSIDE the building, parallel to a façade: the
    corners and jambs of the nearest façade face (what is dimensioned on a
    façade: walls and openings), as (points on that face, offset of the
    drawn line from it along p->q's left normal).  ([], 0) if no straight
    face parallel to p->q lies within ``reach`` of it."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    L = math.hypot(dx, dy)
    if L < 1e-9:
        return []
    ux, uy = dx / L, dy / L
    cand = []
    for e in edges:
        if e[0] != "line":
            continue
        a, b = e[1], e[2]
        ex, ey = b[0] - a[0], b[1] - a[1]
        le = math.hypot(ex, ey)
        if le < 1e-6 or abs(ex * uy - ey * ux) / le > math.sin(math.radians(tol_deg)):
            continue
        d = (a[0] - p[0]) * -uy + (a[1] - p[1]) * ux          # signed offset
        if abs(d) > reach:
            continue
        ta = (a[0] - p[0]) * ux + (a[1] - p[1]) * uy
        tb = (b[0] - p[0]) * ux + (b[1] - p[1]) * uy
        if max(ta, tb) < 0 or min(ta, tb) > L:
            continue
        cand.append((abs(d), ta, tb, d))
    if not cand:
        return [], 0.0
    near = min(c[0] for c in cand)
    face = next(c[3] for c in cand if c[0] == near)
    ts = sorted(min(max(t, 0.0), L) for c in cand if c[0] <= near + 0.01 for t in c[1:3])
    pts, last = [], None
    for t in ts:
        if last is not None and t - last < MERGE:
            continue
        last = t
        pts.append((p[0] + ux * t - uy * face, p[1] + uy * t + ux * face))
    return pts, -face


def outline_edges(drawing):
    """The derived wall/column outline of the plan, as plain geometry."""
    from .architectural import metadata
    edges = []
    for e in drawing.modelspace():
        if e.dxftype() not in ("LINE", "ARC"):
            continue
        if (metadata(e) or {}).get("kind") != "junction_edge":
            continue
        if e.dxftype() == "LINE":
            edges.append(("line", (e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)))
        else:
            edges.append(("arc", (e.dxf.center.x, e.dxf.center.y), float(e.dxf.radius),
                          float(e.dxf.start_angle), float(e.dxf.end_angle)))
    return edges


def ensure_style(drawing, text_height=0.20):
    """Layer ARQ-COTAS and dimension style ARQ (metres at 1:100: 2 mm
    text, ticks, two decimals with a comma).  True when the style was
    created; for an existing style, the sizes it had (to undo the change)."""
    if DIM_LAYER not in drawing.layers:
        drawing.layers.add(DIM_LAYER, color=2)
    created = DIM_STYLE not in drawing.dimstyles
    st = drawing.dimstyles.new(DIM_STYLE) if created else drawing.dimstyles.get(DIM_STYLE)
    h = float(text_height)
    sizes = (("dimtxt", h), ("dimasz", 0.75 * h), ("dimtsz", 0.75 * h),
             ("dimexe", 0.5 * h), ("dimgap", 0.25 * h))
    if not created:
        old = {k: st.dxf.get(k) for k, _v in sizes}
        for key, value in sizes:
            st.dxf.set(key, value)
        return old
    for key, value in sizes + (("dimexo", 0.0),
                       ("dimtad", 1), ("dimtih", 0), ("dimtoh", 0), ("dimdec", 2),
                       ("dimdsep", ord(",")), ("dimzin", 0), ("dimlfac", 1.0),
                       ("dimscale", 1.0), ("dimtofl", 1)):
        try:
            st.dxf.set(key, value)
        except Exception:      # an older ezdxf without that variable
            pass
    return True


class _StyleCommand:
    """Create layer + dimension style once; undo removes what it created."""
    name = "ARQ ESTILO DE COTAS"

    def __init__(self, h):
        self.h, self.made_style, self.made_layer = h, False, False

    def do(self, document):
        d = document.doc
        self.made_layer = DIM_LAYER not in d.layers
        self.made_style = ensure_style(d, self.h)

    def undo(self, document):
        d = document.doc
        if isinstance(self.made_style, dict):          # sizes changed: put them back
            st = d.dimstyles.get(DIM_STYLE)
            for k, v in self.made_style.items():
                if v is not None:
                    st.dxf.set(k, v)
        elif self.made_style is True and DIM_STYLE in d.dimstyles:
            try:
                d.dimstyles.remove(DIM_STYLE)
            except Exception:
                pass
        if self.made_layer and DIM_LAYER in d.layers:
            try:
                d.layers.remove(DIM_LAYER)
            except Exception:
                pass


def chain(points, p, q, offset=0.0, total_offset=None):
    """[(a, b, location)] for the chain along p->q (offset to its left,
    0 = on the drawn line) and, with ``total_offset``, the overall one."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    L = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / L, dx / L
    out = []
    for a, b in zip(points, points[1:]):
        out.append((a, b, (a[0] + nx * offset, a[1] + ny * offset)))
    if total_offset is not None and len(points) > 2:
        a, b = points[0], points[-1]
        out.append((a, b, (a[0] + nx * total_offset, a[1] + ny * total_offset)))
    return out


def dimension_commands(spans):
    from core import actions
    cmds = []
    for a, b, loc in spans:
        c = actions.dim_aligned(a, b, loc, dimstyle=DIM_STYLE)
        c.layer = DIM_LAYER
        cmds.append(c)
    return cmds


def _tool_base():
    from tools.base import Tool
    return Tool


class CotaMurosTool(_tool_base()):
    """COTAMUROS: two points across the walls; each face is dimensioned."""
    name = "COTAMUROS"

    def start(self):
        from .compat import require_document
        self.doc = require_document(self.ctx)
        self.p1 = None
        self.h = 0.20
        self.total = True
        self.pending = None
        self._prompt()

    def _prompt(self):
        tot = "con total" if self.total else "sin total"
        if self.p1 is None:
            self.prompt(f"COTAMUROS (texto {self.h:g} m, {tot}): primer punto de la línea de cota, "
                        "fuera de los muros, o [altura de Texto/tOtal/Fin]:".replace(".", ",", 1))
        else:
            self.prompt("COTAMUROS: segundo punto (la línea debe atravesar los muros):")

    def preview_lines(self, cursor):
        if self.p1 is None:
            return []
        return [(self.p1, (float(cursor[0]), float(cursor[1])))]

    def on_point(self, p):
        p = (float(p[0]), float(p[1]))
        if self.p1 is None:
            self.p1 = p
            self._prompt()
            return
        self._make(self.p1, p)
        self.p1 = None
        self._prompt()

    def _make(self, p, q):
        from .transactions import SafeArchitecturalCommand
        edges = outline_edges(self.doc.doc)
        pts = crossings(edges, p, q)
        offset = 0.0
        if len(pts) < 2:                 # outside, parallel to a façade
            pts, offset = facade_points(edges, p, q)
        if len(pts) < 2:
            self.ctx.echo("COTAMUROS: la línea no atraviesa ningún muro ni corre paralela a una fachada "
                          "(a menos de 3 m); dibújela de lado a lado o junto a la fachada.")
            return
        away = 1.0 if offset >= 0 else -1.0
        spans = chain(pts, p, q, offset, offset + away * 3.0 * self.h if self.total else None)
        cmds = [_StyleCommand(self.h)] + dimension_commands(spans)
        self.ctx.execute(SafeArchitecturalCommand("ARQ COTAS DE MUROS", cmds))
        self.ctx.echo(f"COTAMUROS: {len(pts) - 1} cotas"
                      + (" y la total" if self.total and len(pts) > 2 else "")
                      + f" en la capa {DIM_LAYER}. Siga con otra línea o Intro para terminar.")

    def on_option(self, text):
        t = str(text).strip().lower()
        if self.pending == "h":
            self.pending = None
            try:
                v = float(t.replace(",", "."))
                if not v > 0:
                    raise ValueError
                self.h = v
            except ValueError:
                self.ctx.echo("COTAMUROS: altura de texto no válida.")
            self._prompt()
            return True
        if t in ("t", "texto"):
            self.pending = "h"
            self.prompt("Altura del texto de las cotas (m; 0,20 a escala 1:100):")
            return True
        if t in ("o", "total", "total"):
            self.total = not self.total
            self._prompt()
            return True
        if t in ("f", "fin"):
            self.ctx.finish()
            return True
        return False

    def on_enter(self):
        self.ctx.finish()

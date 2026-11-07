# SPDX-License-Identifier: GPL-3.0-or-later
"""LINEASAMURO: an old plan drawn with lines becomes BIM walls and openings.

Two clicks frame the part of the plan to convert. Inside the window, pairs
of parallel lines a wall thickness apart (between the minimum and maximum
thickness) are read as the two faces of a wall; a gap of an opening's size
is an opening, a door when a swing is drawn in it, a window when glazing is
drawn, a plain gap otherwise. The reading is done by ``vendor.walldetect``
(from cad2ingetrazo, GPL-3.0-or-later).

The walls are created on their axis with the thickness found, the openings
with their position, width, hinge and side, and everything regenerated in
ONE undo step. The original lines are moved to a switched-off layer
(«ARQ-PLANO-ORIGEN») so that they do not double the new contour; option B
erases them instead, C keeps them where they are.
"""
from __future__ import annotations

import math

from tools.base import Tool

from .architectural import metadata

ORIGIN_LAYER = "ARQ-PLANO-ORIGEN"
SAGITTA = 0.01          # m: arcs flattened this finely for the swing reading


def _num(text):
    v = float(str(text).strip().replace(",", "."))
    if not math.isfinite(v):
        raise ValueError("medida no finita")
    return v


def _flatten(c, r, a0, a1):
    step = 2 * math.acos(max(-1.0, 1 - SAGITTA / r)) if r > SAGITTA else (a1 - a0)
    n = max(2, int(math.ceil((a1 - a0) / max(step, 1e-3))))
    pts = [(c[0] + r * math.cos(a0 + (a1 - a0) * k / n), c[1] + r * math.sin(a0 + (a1 - a0) * k / n))
           for k in range(n + 1)]
    return [(p[0], p[1], q[0], q[1]) for p, q in zip(pts, pts[1:])]


def _pieces(entity):
    """([(x0, y0, x1, y1)] straight pieces, [(centre, r, a0, a1)] arcs, the
    angles in radians counter-clockwise, a0 < a1) of a LINE, ARC or
    LWPOLYLINE (whose bulged segments are arcs)."""
    t = entity.dxftype()
    if t == "LINE":
        a, b = entity.dxf.start, entity.dxf.end
        return [(a.x, a.y, b.x, b.y)], []
    if t == "ARC":
        c, r = entity.dxf.center, float(entity.dxf.radius)
        a0, a1 = math.radians(entity.dxf.start_angle), math.radians(entity.dxf.end_angle)
        if a1 <= a0:
            a1 += 2 * math.pi
        return [], [((c.x, c.y), r, a0, a1)]
    if t == "LWPOLYLINE":
        from .geom import curves as CV
        pts = [tuple(map(float, p)) for p in entity.get_points("xyb")]
        if entity.closed and len(pts) > 2:
            pts.append(pts[0])
        segs, arcs = [], []
        for p, q in zip(pts, pts[1:]):
            if abs(p[2]) < 1e-9 or math.dist(p[:2], q[:2]) < 1e-9:
                segs.append((p[0], p[1], q[0], q[1]))
                continue
            c, r, t0, sweep = CV.arc_of(p[:2], q[:2], p[2])
            a0, a1 = (t0, t0 + sweep) if sweep > 0 else (t0 + sweep, t0)
            arcs.append((c, r, a0, a1))
        return segs, arcs
    return [], []


def _segments(entity):
    """[(x0, y0, x1, y1)] of a LINE, LWPOLYLINE or ARC (arcs flattened)."""
    segs, arcs = _pieces(entity)
    for c, r, a0, a1 in arcs:
        segs = segs + _flatten(c, r, a0, a1)
    return segs


def collect(drawing, lo, hi):
    """(wall-face candidates, context, source entities) inside the window.
    The plugin's own entities (anything with ARQ XDATA or on an ARQ layer)
    are never read: only the user's drawing."""
    x0, x1 = sorted((lo[0], hi[0]))
    y0, y1 = sorted((lo[1], hi[1]))

    def inside(s):
        return all(x0 - 1e-9 <= x <= x1 + 1e-9 and y0 - 1e-9 <= y <= y1 + 1e-9
                   for x, y in ((s[0], s[1]), (s[2], s[3])))
    faces, context, sources, arcs = [], [], [], []
    for e in drawing.modelspace():
        if e.dxftype() not in ("LINE", "LWPOLYLINE", "ARC"):
            continue
        if metadata(e) or str(e.dxf.layer).upper().startswith("ARQ"):
            continue
        straight, curved = _pieces(e)
        segs = _segments(e)
        if not segs or not all(inside(s) for s in segs):
            continue
        sources.append(e)
        faces += [list(s) + [0] for s in straight]
        for c, r, a0, a1 in curved:
            arcs.append((c, r, a0, a1, [list(s) + [0] for s in _flatten(c, r, a0, a1)]))
    return faces, context, sources, arcs


def curved_walls(arcs, tmin, tmax, tol=1e-3):
    """Curved walls read from concentric arcs a wall thickness apart:
    ([(a, b, thickness, bulge)], indices of the arcs used). The axis runs
    counter-clockwise over the angles both faces cover; more than half a
    circle is split in two walls."""
    used, out = set(), []
    pairs = []
    for i, (ci, ri, a0i, a1i, _s) in enumerate(arcs):
        for j in range(i + 1, len(arcs)):
            cj, rj, a0j, a1j, _sj = arcs[j]
            t = abs(ri - rj)
            if math.dist(ci, cj) > tol or not (tmin - 1e-9 <= t <= tmax + 1e-9):
                continue
            # the angles both arcs cover (a1j shifted to the same turn)
            shift = 2 * math.pi * round((a0i - a0j) / (2 * math.pi))
            lo, hi = max(a0i, a0j + shift), min(a1i, a1j + shift)
            if hi - lo > 1e-3:
                pairs.append((t, i, j, lo, hi))
    for t, i, j, lo, hi in sorted(pairs):
        if i in used or j in used:
            continue
        used |= {i, j}
        c = arcs[i][0]
        r = (arcs[i][1] + arcs[j][1]) / 2
        n = 1 if hi - lo <= math.pi + 1e-9 else 2
        for k in range(n):
            t0 = lo + (hi - lo) * k / n
            t1 = lo + (hi - lo) * (k + 1) / n
            a = (c[0] + r * math.cos(t0), c[1] + r * math.sin(t0))
            b = (c[0] + r * math.cos(t1), c[1] + r * math.sin(t1))
            out.append((a, b, t, math.tan((t1 - t0) / 4)))
    return out, used


def detect(drawing, lo, hi, tmin=0.07, tmax=0.50):
    from .vendor import walldetect as WD
    faces, context, sources, arcs = collect(drawing, lo, hi)
    curved, used = curved_walls(arcs, tmin, tmax)
    # arcs that are not wall faces (a door's swing) are context for the openings
    context = faces + [s for k, arc in enumerate(arcs) if k not in used for s in arc[4]]
    walls, openings = WD.walls_from(faces, tmin, tmax, context=context)
    return walls, openings, sources, curved


class MoveToLayerCommand:
    name = "ARQ líneas de origen"

    def __init__(self, entities, layer):
        self.entities, self.layer = list(entities), layer
        self.old = [e.dxf.layer for e in self.entities]

    def do(self, document):
        for e in self.entities:
            e.dxf.layer = self.layer

    def undo(self, document):
        for e, layer in zip(self.entities, self.old):
            e.dxf.layer = layer


class LineasAMuroTool(Tool):
    name = "LINEASAMURO"

    def start(self):
        self.first = None
        self.tmin, self.tmax = 0.07, 0.50
        self.height = 2.70
        self.origin = "ocultar"          # ocultar | borrar | conservar
        self.pending = None
        self._prompt()

    def _prompt(self):
        if self.first is not None:
            self.prompt("LINEASAMURO: esquina opuesta de la ventana:")
            return
        fmt = (lambda v: f"{v:g}".replace(".", ","))  # noqa: E731
        self.prompt(f"LINEASAMURO (espesores {fmt(self.tmin)}–{fmt(self.tmax)} m, altura {fmt(self.height)} m, "
                    f"líneas de origen: {self.origin}): primera esquina de la ventana o "
                    "[Espesores/Altura/Origen]:")

    def on_option(self, text):
        t = str(text).strip().lower()
        if self.pending:
            key, self.pending = self.pending, None
            try:
                if key == "espesores":
                    vals = [_num(v) for v in t.replace(";", " ").split()]
                    if len(vals) != 2 or min(vals) <= 0:
                        raise ValueError("dos espesores positivos, p. ej. 0,05 0,50")
                    self.tmin, self.tmax = sorted(vals)
                elif key == "altura":
                    h = _num(t)
                    if h <= 0:
                        raise ValueError("altura positiva")
                    self.height = h
            except ValueError as exc:
                self.ctx.echo(f"LINEASAMURO: {exc}")
            self._prompt()
            return True
        if t in ("e", "espesores"):
            self.pending = "espesores"
            self.prompt("Espesor mínimo y máximo de muro (m):")
            return True
        if t in ("a", "altura"):
            self.pending = "altura"
            self.prompt("Altura de los muros (m):")
            return True
        if t in ("o", "origen"):
            order = ("ocultar", "borrar", "conservar")
            self.origin = order[(order.index(self.origin) + 1) % 3]
            self._prompt()
            return True
        return False

    def on_point(self, p):
        p = (float(p[0]), float(p[1]))
        if self.first is None:
            self.first = p
            self._prompt()
            return
        lo, self.first = self.first, None
        try:
            self._convert(lo, p)
        except Exception as exc:  # noqa: BLE001
            self.ctx.echo(f"LINEASAMURO: {type(exc).__name__}: {exc}")
        self._prompt()

    def _convert(self, lo, hi):
        from core.actions import EraseCommand
        from core.commands import CompositeCommand, DeferredCommand

        from .architectural_v10 import create_opening, create_wall
        from .compat import require_document
        from .transactions import apply_architectural_change
        doc = require_document(self.ctx)
        walls, openings, sources, curved = detect(doc.doc, lo, hi, self.tmin, self.tmax)
        if not walls and not curved:
            self.ctx.echo("LINEASAMURO: no se han encontrado pares de líneas paralelas con un espesor "
                          f"entre {self.tmin:g} y {self.tmax:g} m en la ventana.".replace(".", ","))
            return
        wall_cmds = [create_wall(a, b, float(t), self.height, 0.0, "eje", name="Muro")
                     for a, b, t in walls]
        door_h, win_sill, win_h = min(2.10, self.height), 0.90, 1.20
        if win_sill + win_h > self.height:
            win_sill = max(0.0, self.height - win_h)

        def openings_cmd(_document):
            cmds = []
            for k, pos, width, kind, hinge, face in openings:
                wall = wall_cmds[k].entity
                if wall is None:
                    continue
                extra = {"side": 1 if face >= 0 else -1, "hinge": 1 if hinge > 0 else 0}
                if kind == "door":
                    cmds.append(create_opening(wall, pos - width / 2, width, 0.0, door_h, kind="door", **extra))
                elif kind == "window":
                    cmds.append(create_opening(wall, pos - width / 2, width, win_sill,
                                               min(win_h, self.height - win_sill), kind="window", **extra))
                else:
                    cmds.append(create_opening(wall, pos - width / 2, width, 0.0, door_h, kind="gap", **extra))
            return CompositeCommand("ARQ huecos detectados", cmds) if cmds else None

        curved_cmds = [create_wall(a, b, float(t), self.height, 0.0, "eje", bulge=bulge, name="Muro")
                       for a, b, t, bulge in curved]
        steps = list(wall_cmds) + curved_cmds + [DeferredCommand("ARQ huecos detectados", openings_cmd)]
        if self.origin == "borrar":
            steps.append(EraseCommand(sources))
        elif self.origin == "ocultar":
            from core.layers import NewLayerCommand
            if ORIGIN_LAYER not in doc.doc.layers:
                steps.insert(0, NewLayerCommand(ORIGIN_LAYER, color=8))
            steps.append(MoveToLayerCommand(sources, ORIGIN_LAYER))
            steps.append(_LayerOff(ORIGIN_LAYER))
        apply_architectural_change(self.ctx, CompositeCommand("ARQ líneas a muros", steps), kind="opening")
        kinds = {"door": 0, "window": 0, "void": 0}
        for o in openings:
            kinds[o[3]] = kinds.get(o[3], 0) + 1
        self.ctx.echo(f"LINEASAMURO: {len(walls) + len(curved)} muros ({len(curved)} curvos), {kinds['door']} puertas, {kinds['window']} ventanas y "
                      f"{kinds['void']} vanos a partir de {len(sources)} entidades; líneas de origen: "
                      f"{self.origin}. Revise espesores y tipos con PROPIEDADESARQ.")


class _LayerOff:
    name = "ARQ capa apagada"

    def __init__(self, layer):
        self.layer, self.was = layer, None

    def do(self, document):
        lay = document.doc.layers.get(self.layer)
        self.was = lay.is_off()
        lay.off()

    def undo(self, document):
        if self.was is False:
            document.doc.layers.get(self.layer).on()

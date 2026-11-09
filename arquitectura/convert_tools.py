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


#: layer names that say what a plan's lines are (any language the plans
#: are drawn in; lower case, «contains»).  Used only when the operator has
#: not chosen the layers (option K/L/R): with none of them in the window,
#: every layer is read, as before.
WALL_HINTS = ("pared", "muro", "wall", "tabique", "cerramiento", "fachada", "medianer")
COLUMN_HINTS = ("pilar", "column", "soporte")
CARPENTRY_HINTS = ("carp", "puert", "ventan", "door", "window", "hueco")
#: lines INSIDE a wall (its cavity or insulation): never a wall face
CAVITY_HINTS = ("camara", "cámara", "aislam", "cavity", "insul")
MAX_DEPTH = 4             # blocks inside blocks


def _hint(name, hints):
    n = str(name).lower()
    return any(h in n for h in hints)


def _entities(drawing):
    """(entity, from_block) of the model space and of the blocks inserted in
    it (their entities as placed, read only: a block is never changed)."""
    def walk(insert, depth):
        try:
            parts = list(insert.virtual_entities())
        except Exception:  # noqa: BLE001  (an unreadable block is skipped)
            return
        for v in parts:
            if v.dxftype() == "INSERT":
                if depth < MAX_DEPTH:
                    yield from walk(v, depth + 1)
            elif v.dxftype() in ("LINE", "LWPOLYLINE", "ARC", "CIRCLE"):
                yield v, True
    for e in drawing.modelspace():
        if e.dxftype() == "INSERT":
            if not str(e.dxf.layer).upper().startswith("ARQ"):
                yield from walk(e, 1)
        else:
            yield e, False


def _closed_outline(e):
    """The vertices of a closed polyline or a circle (as a polygon), or None."""
    if e.dxftype() == "LWPOLYLINE" and e.closed:
        pts = [tuple(map(float, p)) for p in e.get_points("xy")]
        return pts if len(pts) >= 3 else None
    if e.dxftype() == "CIRCLE":
        c, r = e.dxf.center, float(e.dxf.radius)
        return [(c.x + r * math.cos(2 * math.pi * k / 24), c.y + r * math.sin(2 * math.pi * k / 24))
                for k in range(24)]
    return None


def layers_in(drawing, lo, hi):
    """{layer: number of entities} of the lines inside the window (blocks too)."""
    x0, x1 = sorted((lo[0], hi[0]))
    y0, y1 = sorted((lo[1], hi[1]))
    out = {}
    for e, _v in _entities(drawing):
        if e.dxftype() not in ("LINE", "LWPOLYLINE", "ARC", "CIRCLE") or metadata(e):
            continue
        segs = _segments(e) if e.dxftype() != "CIRCLE" else [(e.dxf.center.x, e.dxf.center.y) * 2]
        if segs and all(x0 - 1e-9 <= x <= x1 + 1e-9 and y0 - 1e-9 <= y <= y1 + 1e-9
                        for s in segs for x, y in ((s[0], s[1]), (s[2], s[3]))):
            out[e.dxf.layer] = out.get(e.dxf.layer, 0) + 1
    return out


def choose_layers(present, walls=None, columns=None, carpentry=None):
    """(wall, column, carpentry) layer sets for the window: the ones chosen
    by the operator, else the ones whose names say so, else (walls only)
    every layer -None-, as LINEASAMURO always did."""
    def pick(chosen, hints):
        if chosen:
            return {c for c in present if c.lower() in {x.lower() for x in chosen}}
        found = {c for c in present if _hint(c, hints)}
        return found
    w = pick(walls, WALL_HINTS) or None
    c = pick(columns, COLUMN_HINTS)
    k = pick(carpentry, CARPENTRY_HINTS)
    if w is not None:
        c -= w
        k -= w
    return w, c, k


def collect(drawing, lo, hi, wall_layers=None, column_layers=(), carpentry_layers=()):
    """(wall-face candidates, context, source entities, arcs, columns, block
    entities used) inside the window.  Wall faces come from ``wall_layers``
    (None: every layer); the rest is context for the openings (a door's
    swing, a window's glazing).  Closed outlines on ``column_layers`` are
    columns.  The plugin's own entities are never read; entities inside a
    block are read but never changed (not in ``sources``)."""
    x0, x1 = sorted((lo[0], hi[0]))
    y0, y1 = sorted((lo[1], hi[1]))

    def inside(s):
        return all(x0 - 1e-9 <= x <= x1 + 1e-9 and y0 - 1e-9 <= y <= y1 + 1e-9
                   for x, y in ((s[0], s[1]), (s[2], s[3])))
    faces, context, sources, arcs, columns = [], [], [], [], []
    others = []                           # lines of other layers (party walls' outer face)
    in_blocks = 0
    column_layers = set(column_layers or ())
    carpentry_layers = set(carpentry_layers or ())
    for e, virtual in _entities(drawing):
        if e.dxftype() not in ("LINE", "LWPOLYLINE", "ARC", "CIRCLE"):
            continue
        layer = e.dxf.layer
        if metadata(e) or str(layer).upper().startswith("ARQ"):
            continue
        if layer in column_layers:
            outline = _closed_outline(e)
            if outline and all(x0 <= x <= x1 and y0 <= y <= y1 for x, y in outline):
                columns.append(outline)
                if virtual:
                    in_blocks += 1
                else:
                    sources.append(e)
            continue
        if e.dxftype() == "CIRCLE":
            continue
        straight, curved = _pieces(e)
        segs = _segments(e)
        if not segs or not all(inside(s) for s in segs):
            continue
        if wall_layers is None or layer in wall_layers:
            faces += [list(s) + [0] for s in straight]
            for c, r, a0, a1 in curved:
                arcs.append((c, r, a0, a1, [list(s) + [0] for s in _flatten(c, r, a0, a1)]))
        else:
            context += [list(s) + [0] for s in segs]
            if layer not in carpentry_layers:
                if not _hint(layer, CAVITY_HINTS):
                    others += [list(s) for s in straight]
                continue                  # stays where it is (stairs, texts, furniture...)
        if virtual:
            in_blocks += 1
        else:
            sources.append(e)
    return faces, context, sources, arcs, columns, in_blocks, others


def party_walls(unpaired, others, tmin, tmax, min_len, ang_tol=1.5, overlap=0.6):
    """Walls whose second face is not on a wall layer: a party wall drawn
    with its inner face only, closed by the neighbour's boundary or a
    reference line.  Each long unpaired face takes the NEAREST parallel line
    of another layer a wall thickness away that runs along most of it.
    -> ([(a, b, thickness)], faces used)."""
    out, used = [], []
    for f in unpaired:
        p, q = f[:2], f[2:4]
        L = math.dist(p, q)
        if L < min_len:
            continue
        u = ((q[0] - p[0]) / L, (q[1] - p[1]) / L)
        n = (-u[1], u[0])
        best = None
        for g in others:
            a, b = g[:2], g[2:4]
            lg = math.dist(a, b)
            if lg < 1e-6:
                continue
            v = ((b[0] - a[0]) / lg, (b[1] - a[1]) / lg)
            if abs(u[0] * v[1] - u[1] * v[0]) > math.sin(math.radians(ang_tol)):
                continue
            da = (a[0] - p[0]) * n[0] + (a[1] - p[1]) * n[1]
            db = (b[0] - p[0]) * n[0] + (b[1] - p[1]) * n[1]
            d = (da + db) / 2
            if da * db <= 0 or not tmin - 1e-6 <= abs(d) <= tmax + 1e-6:
                continue
            ta = (a[0] - p[0]) * u[0] + (a[1] - p[1]) * u[1]
            tb = (b[0] - p[0]) * u[0] + (b[1] - p[1]) * u[1]
            cover = min(L, max(ta, tb)) - max(0.0, min(ta, tb))
            if cover < overlap * L:
                continue
            if best is None or abs(d) < abs(best):
                best = d
        if best is not None:
            off = (n[0] * best / 2, n[1] * best / 2)
            out.append(((p[0] + off[0], p[1] + off[1]), (q[0] + off[0], q[1] + off[1]), abs(best)))
            used.append(f)
    return out, used


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


def detect(drawing, lo, hi, tmin=0.07, tmax=0.50, wall_layers=None, column_layers=(),
           carpentry_layers=(), parallel=None):
    """(walls, openings, sources, curved) as before; with ``detail=True``
    callers use ``detect_all``.  ``parallel``: how far the two faces of a
    wall may stray from parallel over its length (m; old walls are rarely
    true), by default the reader's 5 mm."""
    return detect_all(drawing, lo, hi, tmin, tmax, wall_layers, column_layers,
                      carpentry_layers, parallel)[:4]


def detect_all(drawing, lo, hi, tmin=0.07, tmax=0.50, wall_layers=None, column_layers=(),
               carpentry_layers=(), parallel=None):
    """(walls, openings, sources, curved, columns, unpaired faces, entities in blocks)."""
    from .vendor import walldetect as WD
    faces, context, sources, arcs, columns, in_blocks, others = collect(
        drawing, lo, hi, wall_layers, column_layers, carpentry_layers)
    curved, used = curved_walls(arcs, tmin, tmax)
    # arcs that are not wall faces (a door's swing) are context for the openings
    context = faces + context + [s for k, arc in enumerate(arcs) if k not in used for s in arc[4]]
    saved = WD.PAR_TOL
    try:
        if parallel is not None:
            WD.PAR_TOL = max(saved, float(parallel))
        walls, openings = WD.walls_from(faces, tmin, tmax, context=context)
    finally:
        WD.PAR_TOL = saved
    unpaired = [f for f in faces if not _on_a_wall(f, walls)]
    if wall_layers is not None:
        # party walls: only with known wall layers (otherwise every line is
        # already a candidate face)
        extra, used_faces = party_walls(unpaired, others, tmin, tmax, max(tmax + 0.05, 1.5))
        walls = list(walls) + extra
        unpaired = [f for f in unpaired if f not in used_faces]
    return walls, openings, sources, curved, columns, unpaired, in_blocks


def _on_a_wall(face, walls, tol=0.02):
    """Does the face line lie on a face of one of the detected walls?"""
    x0, y0, x1, y1 = face[:4]
    m = ((x0 + x1) / 2, (y0 + y1) / 2)
    for a, b, t in walls:
        ux, uy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(ux, uy)
        if L < 1e-9:
            continue
        ux, uy = ux / L, uy / L
        along = (m[0] - a[0]) * ux + (m[1] - a[1]) * uy
        off = abs(-(m[0] - a[0]) * uy + (m[1] - a[1]) * ux)
        if -tol <= along <= L + tol and abs(off - t / 2) <= tol + 0.02 * t:
            return True
    return False


def column_values(outline, height):
    """PILAR values for a column drawn as a closed outline: a rectangle (its
    sides and turn), a circle, or any other shape by its bounding rectangle."""
    n = len(outline)
    c = (sum(p[0] for p in outline) / n, sum(p[1] for p in outline) / n)
    base = {"height": height, "base": 0.0, "name": "Pilar", "type_name": "Pilar (plano)",
            "material": "Sin definir"}
    if n >= 16:
        r = sum(math.dist(p, c) for p in outline) / n
        return c, dict(base, shape="circ", radius=r, width=2 * r, depth=2 * r, rotation=0.0)
    if n == 4:
        sides = [(outline[(i + 1) % 4][0] - outline[i][0], outline[(i + 1) % 4][1] - outline[i][1]) for i in range(4)]
        lens = [math.hypot(*v) for v in sides]
        if min(lens) > 1e-6 and all(abs(sides[i][0] * sides[(i + 1) % 4][0] + sides[i][1] * sides[(i + 1) % 4][1])
                                    <= 1e-3 * lens[i] * lens[(i + 1) % 4] for i in range(4)):
            rot = math.degrees(math.atan2(sides[0][1], sides[0][0]))
            return c, dict(base, shape="rect", width=lens[0], depth=lens[1], rotation=rot)
    xs, ys = [p[0] for p in outline], [p[1] for p in outline]
    c = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
    return c, dict(base, shape="rect", width=max(xs) - min(xs), depth=max(ys) - min(ys), rotation=0.0)


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
        from .compat import require_document
        from .parameters_arq import general_options
        self.lineas = dict(general_options(require_document(self.ctx))["lineas"])
        self._prompt()

    def _layers_text(self):
        def show(v):
            return ", ".join(v) if v else "por nombre"
        return (f"capas: muros {show(self.lineas['muros'])}; pilares {show(self.lineas['pilares'])}; "
                f"carpintería {show(self.lineas['carpinteria'])}")

    def _save_lineas(self):
        """The layer choice is kept in the drawing (general options), so the
        next plan of the same office is read the same way; one undo step."""
        from .compat import require_document
        from .parameters_arq import SetArchitecturalDefaults, load_defaults
        doc = require_document(self.ctx)
        values = load_defaults(doc)
        values["general"]["lineas"] = dict(self.lineas)
        self.ctx.execute(SetArchitecturalDefaults(values))

    def _prompt(self):
        if self.first is not None:
            self.prompt("LINEASAMURO: esquina opuesta de la ventana:")
            return
        fmt = (lambda v: f"{v:g}".replace(".", ","))  # noqa: E731
        self.prompt(f"LINEASAMURO (espesores {fmt(self.tmin)}–{fmt(self.tmax)} m, altura {fmt(self.height)} m, "
                    f"paralelismo {fmt(self.lineas['paralelismo'])} m, {self._layers_text()}, "
                    f"líneas de origen: {self.origin}): primera esquina de la ventana o "
                    "[Espesores/Altura/Origen/capas de muro K/capas de piLar/capas de caRpintería/Paralelismo]:")

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
                elif key == "paralelismo":
                    v = _num(t)
                    if not 0 <= v <= 0.5:
                        raise ValueError("entre 0 y 0,5 m")
                    self.lineas["paralelismo"] = v
                    self._save_lineas()
                elif key in ("muros", "pilares", "carpinteria"):
                    raw = str(text).strip()
                    names = [] if raw in ("", "*", "-") else [n.strip() for n in raw.replace(";", ",").split(",") if n.strip()]
                    self.lineas[key] = names
                    self._save_lineas()
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
        for keys, key, ask in ((("k", "muros"), "muros", "Capas de las caras de muro"),
                               (("l", "pilares"), "pilares", "Capas de los pilares"),
                               (("r", "carpinteria", "carpintería"), "carpinteria", "Capas de la carpintería")):
            if t in keys:
                self.pending = key
                self.prompt(f"{ask}, separadas por comas (- = reconocerlas por su nombre):")
                return True
        if t in ("p", "paralelismo"):
            self.pending = "paralelismo"
            self.prompt("Desviación admitida entre las dos caras de un muro antiguo (m; 0,005 dibujo nuevo, "
                        "0,03 levantamiento):")
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
        present = layers_in(doc.doc, lo, hi)
        wl, cl, kl = choose_layers(present, self.lineas["muros"], self.lineas["pilares"],
                                   self.lineas["carpinteria"])
        if wl is not None:
            self.ctx.echo("LINEASAMURO: caras de muro en " + ", ".join(sorted(wl))
                          + (("; pilares en " + ", ".join(sorted(cl))) if cl else "")
                          + (("; carpintería en " + ", ".join(sorted(kl))) if kl else "")
                          + " (opciones K, L y R para cambiarlo).")
        walls, openings, sources, curved, columns, unpaired, in_blocks = detect_all(
            doc.doc, lo, hi, self.tmin, self.tmax, wl, cl, kl, self.lineas["paralelismo"])
        # lines of a wall layer left without a partner (a party wall with one
        # face drawn, a wall too thin or too thick): kept visible and selected
        # (only with known wall layers, and longer than a wall is thick: the
        # short lines closing a wall's end or a jamb never have a partner)
        loose = {tuple(round(v, 6) for v in f[:4]) for f in unpaired
                 if math.dist(f[:2], f[2:4]) > self.tmax + 0.05}
        doubtful = [e for e in sources
                    if wl is not None and e.dxf.layer in wl and e.dxftype() != "CIRCLE"
                    and any(tuple(round(v, 6) for v in s) in loose for s in _pieces(e)[0])]
        sources = [e for e in sources if e not in doubtful]
        if not walls and not curved and not columns:
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
        from .columns import column_command
        column_cmds = [column_command(*column_values(outline, self.height)) for outline in columns]
        steps = (list(wall_cmds) + curved_cmds + [DeferredCommand("ARQ huecos detectados", openings_cmd)]
                 + column_cmds)
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
        self.ctx.echo(f"LINEASAMURO: {len(walls) + len(curved)} muros ({len(curved)} curvos), {len(columns)} pilares, "
                      f"{kinds['door']} puertas, {kinds['window']} ventanas y "
                      f"{kinds['void']} vanos a partir de {len(sources)} entidades; líneas de origen: "
                      f"{self.origin}. Revise espesores y tipos con PROPIEDADESARQ.")
        if in_blocks:
            self.ctx.echo(f"  Leídas {in_blocks} entidades dentro de bloques; los bloques no se modifican "
                          "(apague su capa o descompóngalos si estorban).")
        if doubtful:
            from .integrity import highlight
            highlight(self.ctx, [e.dxf.handle for e in doubtful])
            self.ctx.echo(f"  {len(doubtful)} líneas de muro sin pareja quedan visibles y seleccionadas: una "
                          "medianera con una sola cara, un muro fuera del espesor admitido o caras poco "
                          "paralelas (opción P). Revíselas o dibuje esos muros con MURO.")


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

# SPDX-License-Identifier: GPL-3.0-or-later
"""Phase 2 wall drawing tools (interaction only; geometry in geom/drafting.py).

* ``MURO`` (extends the v1.0 tool):
  - ``I`` / ``F5`` swaps the face being drawn (left/right) while drawing;
  - ``G`` (iGual) takes thickness, height, level, type and material from an
    existing wall picked on screen;
  - ending a wall on the NEAR face of another wall makes a T; on the FAR
    face, an L that cuts the other wall and keeps its longer part.
* ``MUROPARALELO``: wall parallel to a picked face at a typed distance, on
  the clicked side; repeatable.
* ``ESTIRAMURO``: extend or trim the picked end of a wall to a boundary line.
* ``PIVOTAMURO``: move one end of a wall, the other end stays.

Every edit is one undoable step with the regenerated plan (transactions.
apply_architectural_change); a wall keeps its BIM identity when edited.
"""
from __future__ import annotations

import copy
import math

from core.commands import CompositeCommand, DeferredCommand
from tools.base import Tool

from .architectural import metadata
from .architectural_v10 import EditArchitecturalCommand, create_wall, edit_opening, _find_openings
from .geom import drafting as D
from .tools_v10 import MuroTool as _MuroV10

FACE_TOL = 1e-3          # m: a click snapped on a face line


# --- shared helpers ------------------------------------------------------------

def walls_in(drawing):
    """({id: (a, b, thickness, reference)}, {id: entity}) of the drawing's walls."""
    geo, ents = {}, {}
    for e in drawing.modelspace():
        m = metadata(e) or {}
        if m.get("kind") != "wall" or e.dxftype() != "LWPOLYLINE" or e.closed or len(e) != 2:
            continue
        a, b = [tuple(map(float, p)) for p in e.get_points("xy")]
        geo[m["id"]] = (a, b, float(m["thickness"]), m.get("reference", "eje"))
        ents[m["id"]] = e
    return geo, ents


def wall_from_pick(ctx, point):
    """(wall entity, picked line (p, q) or None) for a click on a wall's
    contour line or on its axis; (None, None) otherwise."""
    from .arq_properties import resolve_arch_entity
    from .compat import require_document
    services = getattr(ctx, "services", None)
    picked = services.pick_entity(point) if services else None
    if picked is None:
        return None, None
    entity, _err = resolve_arch_entity(require_document(ctx), picked)
    if entity is None or (metadata(entity) or {}).get("kind") != "wall":
        return None, None
    return entity, line_of(picked, point)


def line_of(entity, point=None):
    """The straight segment of a picked LINE or LWPOLYLINE (nearest segment)."""
    if entity is None:
        return None
    t = entity.dxftype()
    if t == "LINE":
        return ((entity.dxf.start.x, entity.dxf.start.y), (entity.dxf.end.x, entity.dxf.end.y))
    if t == "LWPOLYLINE":
        pts = [tuple(map(float, p)) for p in entity.get_points("xy")]
        segs = list(zip(pts, pts[1:] + (pts[:1] if entity.closed else [])))
        if not segs:
            return None
        if point is None:
            return segs[0]
        return min(segs, key=lambda s: _dist_seg(point, *s))
    return None


def _dist_seg(p, a, b):
    ab = (b[0] - a[0], b[1] - a[1])
    L2 = ab[0] ** 2 + ab[1] ** 2
    if L2 == 0:
        return math.dist(p, a)
    t = max(0.0, min(1.0, ((p[0] - a[0]) * ab[0] + (p[1] - a[1]) * ab[1]) / L2))
    return math.dist(p, (a[0] + ab[0] * t, a[1] + ab[1] * t))


def reshape_wall(entity, a, b, end_moved):
    """Commands that set a wall's reference line to a-b keeping its identity,
    and move its openings so they keep their distance from the fixed end."""
    m = copy.deepcopy(metadata(entity))
    old_len = math.dist(m["a"], m["b"])
    new_len = math.dist(a, b)
    ops = _find_openings(entity.doc, m["id"])
    ds = (old_len - new_len) if end_moved == 0 else 0.0
    shifted = D.shift_openings(ops, ds, new_len)          # raises if one falls out
    m["a"], m["b"] = list(a), list(b)
    commands = [EditArchitecturalCommand(entity, m, points=[tuple(a), tuple(b)])]
    by_id = {o["id"]: o for o in shifted}
    for e in entity.doc.modelspace():
        rec = metadata(e) or {}
        if rec.get("kind") == "opening" and rec.get("wall_id") == m["id"] and rec["id"] in by_id:
            new_off = by_id[rec["id"]]["offset"]
            if abs(new_off - float(rec["offset"])) > 1e-12 or e.dxftype() == "LWPOLYLINE":
                commands.append(DeferredCommand(
                    "ARQ hueco", lambda _doc, e=e, off=new_off: edit_opening(e, offset=off)))
    return commands


def apply(ctx, name, commands, kind="wall"):
    from .transactions import apply_architectural_change
    return apply_architectural_change(ctx, CompositeCommand(name, commands), kind=kind)


def _document(ctx):
    from .compat import require_document
    return require_document(ctx)


# --- MURO ------------------------------------------------------------------------

class MuroCarasTool(_MuroV10):
    """MURO with face swap, property capture and the T/L end gesture."""
    name = "MURO"

    #: the single F5 shortcut of the main window while MURO is active
    _shortcut = None

    def start(self):
        self.capturing = False
        super().start()
        self._install_f5()

    # F5 swaps the face, as typed "I"/"F5" does. IngeCAD binds nothing to F5
    # (Ctrl+F5 is the sidebar, F8 is ORTHO) and offers plugin tools no key
    # hook yet, so a window shortcut lives only while MURO is the active
    # tool; any Qt problem leaves the typed option as the way to do it.
    def _install_f5(self):
        try:
            from PySide6.QtCore import Qt
            from PySide6.QtGui import QKeySequence, QShortcut
            from PySide6.QtWidgets import QWidget
            window = getattr(getattr(self.ctx, "services", None), "window", None)
            if not isinstance(window, QWidget):
                return
            MuroCarasTool._drop_f5()
            sc = QShortcut(QKeySequence(Qt.Key_F5), window)
            sc.setContext(Qt.WindowShortcut)
            sc.activated.connect(self._on_f5)
            MuroCarasTool._shortcut = sc
        except Exception:  # noqa: BLE001
            pass

    @classmethod
    def _drop_f5(cls):
        sc, cls._shortcut = cls._shortcut, None
        if sc is not None:
            try:
                sc.setEnabled(False)
                sc.deleteLater()
            except Exception:  # noqa: BLE001
                pass

    def _on_f5(self):
        services = getattr(self.ctx, "services", None)
        if getattr(services, "tool", None) is not self:
            MuroCarasTool._drop_f5()
            return
        self.on_option("F5")
        changed = getattr(services, "changed", None)
        if changed is not None:
            changed.emit()

    def on_cancel(self):
        MuroCarasTool._drop_f5()
        super().on_cancel()

    def _status(self):
        side = {"izquierda": "cara derecha (cuerpo a la izquierda)",
                "derecha": "cara izquierda (cuerpo a la derecha)", "eje": "eje"}[self.reference]
        self.ctx.echo(f"MURO: espesor {self.thickness:g} m, altura {self.height:g} m, "
                      f"se dibuja por: {side}")

    def on_option(self, text):
        txt = str(text).strip().lower()
        if not self.pending and txt in ("i", "invertir", "f5", "cara"):
            self.reference = {"izquierda": "derecha", "derecha": "izquierda"}.get(
                self.reference, "izquierda")
            self._status()
            return True
        if not self.pending and txt in ("g", "igual"):
            self.capturing = True
            self.prompt("MURO: designe el muro cuyas propiedades quiere usar:")
            return True
        return super().on_option(text)

    def on_point(self, p):
        if self.capturing:
            self.capturing = False
            entity, _line = wall_from_pick(self.ctx, p)
            if entity is None:
                self.ctx.echo("MURO: no se ha designado un muro.")
            else:
                m = metadata(entity)
                self.thickness, self.height = float(m["thickness"]), float(m["height"])
                self.base = float(m.get("base", 0.0))
                self.reference = m.get("reference", self.reference)
                self.bim = {k: m.get(k, self.bim.get(k, "")) for k in self.bim}
                self.ctx.echo("MURO: propiedades tomadas de " + (m.get("name") or "muro")
                              + f" ({m['id'][:8]}).")
                self._status()
            self.prompt("MURO: siguiente punto o [Espesor/Altura/Cota/Referencia/Invertir/iGual/Fin]:"
                        if self.startpoint is not None else
                        "MURO: primer punto o [Espesor/Altura/Cota/Referencia/Invertir/iGual/Fin]:")
            return
        if self.pending or self.startpoint is None or math.dist(self.startpoint, p) < 1e-6:
            return super().on_point(p)
        gesture = self._gesture(p)
        if gesture is None or gesture["kind"] == "T":
            return super().on_point(p)
        # L: cut the other wall and finish this one on the shared corner
        try:
            host_entity = gesture["host_entity"]
            end_moved = 1 if gesture["kept"] == "start" else 0
            commands = reshape_wall(host_entity, gesture["host_a"], gesture["host_b"], end_moved)
            new = create_wall(self.startpoint, gesture["new_end"], self.thickness, self.height,
                              self.base, self.reference, **self.bim)
            apply(self.ctx, "ARQ MURO en esquina", commands + [new])
        except Exception as exc:  # noqa: BLE001
            self.ctx.echo(f"MURO: no se pudo hacer la esquina ({type(exc).__name__}: {exc}).")
            return
        self.ctx.echo("MURO: esquina (L) con el muro existente, recortado por su parte más corta.")
        self.last_wall = new.entity
        self.startpoint = tuple(gesture["new_end"])
        self.last_point = self.startpoint
        self.prompt("MURO trazado. Siguiente punto o [E/A/C/R/I/G/Fin]:")

    def _gesture(self, p):
        """T/L decision for an end clicked on another wall's face."""
        geo, ents = walls_in(_document(self.ctx).doc)
        hits = D.face_at(geo, p, FACE_TOL)
        for wid, side, _s in hits:
            try:
                g = D.end_gesture(self.startpoint, p, self.thickness, self.reference,
                                  geo[wid], side)
            except ValueError as exc:
                self.ctx.echo(f"MURO: {exc}")
                continue
            g["host_entity"] = ents[wid]
            return g
        return None


# --- MUROPARALELO ----------------------------------------------------------------

class MuroParaleloTool(Tool):
    name = "MUROPARALELO"
    entity_picker = True

    def start(self):
        self.name = type(self).name
        from .parameters_arq import load_defaults
        d = load_defaults(_document(self.ctx))["wall"]
        self.thickness, self.height, self.base = d["thickness"], d["height"], d["base"]
        self.bim = {k: d[k] for k in ("name", "type_name", "material", "level")}
        self.distance = getattr(type(self), "_last_distance", None)
        self.face = None
        self._ask_distance()

    def _ask_distance(self):
        last = f" <{self.distance:g}>" if self.distance is not None else ""
        self.prompt(f"MUROPARALELO: distancia a la cara (m){last} o [Espesor]:")
        self.stage = "distance"

    def on_option(self, text):
        txt = str(text).strip().lower().replace(",", ".")
        if self.stage == "thickness":
            try:
                v = float(txt)
                if not (math.isfinite(v) and v > 0):
                    raise ValueError
            except ValueError:
                self.ctx.echo("Espesor no válido.")
                return True
            self.thickness = v
            self._ask_distance()
            return True
        if self.stage == "distance":
            if txt in ("e", "espesor"):
                self.stage = "thickness"
                self.prompt(f"Espesor del muro nuevo (m) <{self.thickness:g}>:")
                return True
            try:
                v = float(txt)
                if not (math.isfinite(v) and v >= 0):
                    raise ValueError
            except ValueError:
                self.ctx.echo("Indique una distancia en metros.")
                return True
            self.distance = type(self)._last_distance = v
            self.stage = "face"
            self.prompt("MUROPARALELO: designe la cara (línea) de referencia:")
            return True
        return False

    def on_enter(self):
        if self.stage == "distance" and self.distance is not None:
            self.stage = "face"
            self.prompt("MUROPARALELO: designe la cara (línea) de referencia:")
            return
        self.ctx.finish()

    def on_point(self, p):
        if self.stage == "face":
            services = getattr(self.ctx, "services", None)
            picked = services.pick_entity(p) if services else None
            line = line_of(picked, p)
            if line is None or math.dist(*line) < 1e-6:
                self.ctx.echo("Designe una línea recta (cara de muro, eje o línea).")
                return
            self.face = line
            self.stage = "side"
            self.prompt("MUROPARALELO: indique el lado:")
            return
        if self.stage == "side":
            try:
                a, b, ref = D.parallel_wall(self.face[0], self.face[1], self.distance, p,
                                            self.thickness)
                geo, _ents = walls_in(_document(self.ctx).doc)
                a, b = D.extend_to_faces(a, b, geo, max_gap=self.distance + self.thickness + 0.5)
                cmd = create_wall(a, b, self.thickness, self.height, self.base, ref, **self.bim)
                apply(self.ctx, "ARQ MURO PARALELO", [cmd])
                self.ctx.echo(f"MUROPARALELO: muro de {self.thickness:g} m a {self.distance:g} m "
                              f"de la cara ({math.dist(a, b):.3f} m de longitud).")
            except Exception as exc:  # noqa: BLE001
                self.ctx.echo(f"MUROPARALELO: {type(exc).__name__}: {exc}")
            self.stage = "face"
            self.prompt("MUROPARALELO: designe otra cara o Intro para terminar:")

    def preview_segments(self, cursor):
        if self.stage != "side" or self.face is None:
            return []
        try:
            a, b, ref = D.parallel_wall(self.face[0], self.face[1], self.distance, cursor,
                                        self.thickness)
            from .architectural_v10 import wall_corners
            c = wall_corners(a, b, self.thickness, ref)
            return list(zip(c, c[1:] + c[:1]))
        except ValueError:
            return []


# --- ESTIRAMURO / PIVOTAMURO -----------------------------------------------------

class _EndTool(Tool):
    entity_picker = True
    verb = ""

    def start(self):
        self.name = type(self).name
        self.wall = None
        self.end = None
        self.prompt(f"{self.name}: designe el muro cerca del extremo que quiere {self.verb}:")

    def _pick_wall(self, p):
        entity, _line = wall_from_pick(self.ctx, p)
        if entity is None:
            self.ctx.echo(f"{self.name}: designe un muro (su contorno).")
            return False
        m = metadata(entity)
        self.wall = entity
        self.end = D.nearest_end(m["a"], m["b"], p)
        self.last_point = tuple(m["b"] if self.end == 0 else m["a"])     # fixed end
        return True

    def _apply(self, a, b):
        try:
            apply(self.ctx, f"ARQ {self.name}", reshape_wall(self.wall, a, b, self.end))
            self.ctx.echo(f"{self.name}: muro modificado; conserva su identidad BIM.")
        except Exception as exc:  # noqa: BLE001
            self.ctx.echo(f"{self.name}: {type(exc).__name__}: {exc}")


class EstiraMuroTool(_EndTool):
    name = "ESTIRAMURO"
    verb = "alargar o acortar"

    def on_point(self, p):
        if self.wall is None:
            if self._pick_wall(p):
                self.prompt("ESTIRAMURO: designe la línea límite (cara de muro, eje o línea):")
            return
        services = getattr(self.ctx, "services", None)
        line = line_of(services.pick_entity(p) if services else None, p)
        if line is None:
            self.ctx.echo("ESTIRAMURO: designe una línea recta.")
            return
        m = metadata(self.wall)
        try:
            a, b = D.extend_to_line(tuple(m["a"]), tuple(m["b"]), self.end, *line)
        except ValueError as exc:
            self.ctx.echo(f"ESTIRAMURO: {exc}")
            return
        self._apply(a, b)
        self.wall = None
        self.prompt("ESTIRAMURO: designe otro muro o Intro para terminar:")


class PivotaMuroTool(_EndTool):
    name = "PIVOTAMURO"
    verb = "mover"

    def on_point(self, p):
        if self.wall is None:
            if self._pick_wall(p):
                self.prompt("PIVOTAMURO: nueva posición del extremo:")
            return
        m = metadata(self.wall)
        try:
            a, b = D.move_end(tuple(m["a"]), tuple(m["b"]), self.end, p)
        except ValueError as exc:
            self.ctx.echo(f"PIVOTAMURO: {exc}")
            return
        self._apply(a, b)
        self.wall = None
        self.last_point = None
        self.prompt("PIVOTAMURO: designe otro muro o Intro para terminar:")

    def preview_segments(self, cursor):
        if self.wall is None:
            return []
        m = metadata(self.wall)
        try:
            a, b = D.move_end(tuple(m["a"]), tuple(m["b"]), self.end, cursor)
            from .architectural_v10 import wall_corners
            c = wall_corners(a, b, float(m["thickness"]), m.get("reference", "eje"))
            return list(zip(c, c[1:] + c[:1]))
        except ValueError:
            return []


TOOLS = (MuroCarasTool, MuroParaleloTool, EstiraMuroTool, PivotaMuroTool)

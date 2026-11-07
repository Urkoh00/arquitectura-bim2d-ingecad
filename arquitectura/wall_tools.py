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
        if float(m.get("bulge") or 0.0):
            continue                      # curved: not a straight reference for the drawing aids
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


def refuse_curved(ctx, tool, entity):
    """True (and a message) when ``entity`` is a curved wall, which this
    tool does not handle yet."""
    if entity is not None and float((metadata(entity) or {}).get("bulge") or 0.0):
        ctx.echo(f"{tool}: aún no trabaja con muros curvos (use CURVAMURO con 0 para enderezarlo).")
        return True
    return False


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


# --- total thickness first, then the type -------------------------------------

class WallTypeChoice:
    """Shared by MURO, MUROPARALELO and DIVIDEMURO. The TOTAL thickness comes
    first: the types with that thickness are offered (one: applied; several:
    the user picks; none: a generic wall). ``T`` lists every type. The
    chosen type's layers travel with the wall (IfcMaterialLayerSet later)."""

    def _types(self):
        from .parameters_arq import load_defaults
        return load_defaults(_document(self.ctx))["wall_types"]

    def _apply_type(self, t):
        self.thickness = float(t["thickness"])
        self.bim["type_name"] = t["name"]
        self.bim["name"] = t["name"]
        if t.get("material"):
            self.bim["material"] = t["material"]
        self.bim["layers"] = [list(l) for l in t["layers"]]

    def _generic(self, thickness):
        from .parameters_arq import _num
        self.thickness = float(thickness)
        self.bim["type_name"] = f"Muro {_num(self.thickness)}"
        self.bim["name"] = "Muro"
        self.bim.pop("layers", None)

    def _set_thickness(self, value):
        """True when a choice among several types is pending."""
        from .parameters_arq import _num, types_with_thickness
        hits = types_with_thickness(self._types(), value)
        if len(hits) == 1:
            self._apply_type(hits[0])
            return False
        self._generic(value)
        if not hits:
            return False
        self.type_candidates = hits
        self.prompt(f"{self.name}: hay {len(hits)} tipos de {_num(float(value))} m: "
                    + "  ".join(f"{i}) {t['name']}" for i, t in enumerate(hits, 1))
                    + "  (Intro: genérico)")
        return True

    def _ask_type(self):
        from .parameters_arq import wall_types_text
        self.type_candidates = None
        self.choosing_type = True
        self.prompt(f"{self.name}: tipo (número o nombre; o un espesor): " + wall_types_text(self._types()))

    def _type_answer(self, text):
        """Handle the answer to a type question. Returns True when consumed."""
        from .parameters_arq import find_wall_type
        cands = getattr(self, "type_candidates", None)
        if cands is not None:
            self.type_candidates = None
            txt = str(text).strip()
            if txt.isdigit() and 1 <= int(txt) <= len(cands):
                self._apply_type(cands[int(txt) - 1])
            elif txt:
                t = find_wall_type(cands, txt)
                if t is not None:
                    self._apply_type(t)
            return True
        if getattr(self, "choosing_type", False):
            self.choosing_type = False
            txt = str(text).strip()
            if _is_thickness(txt):
                return self._set_thickness(float(txt.replace(",", "."))) or True
            t = find_wall_type(self._types(), txt)
            if t is None:
                self.ctx.echo(f"{self.name}: tipo no reconocido; se mantiene el actual.")
            else:
                self._apply_type(t)
            return True
        return False

    def _type_label(self):
        from .parameters_arq import _num
        return f"{self.bim.get('type_name') or 'Muro'} — {_num(self.thickness)} m"


def _is_thickness(txt):
    t = str(txt).strip().replace(",", ".")
    if not t or ("." not in t and not t.startswith("0")):
        return False          # «2» is a list number, «0,24» / «0.24» a thickness
    try:
        v = float(t)
        return math.isfinite(v) and 0 < v < 3
    except ValueError:
        return False


# --- MURO ------------------------------------------------------------------------

class MuroCarasTool(WallTypeChoice, _MuroV10):
    """MURO with face swap, property capture and the T/L end gesture."""
    name = "MURO"

    #: the single F5 shortcut of the main window while MURO is active
    _shortcut = None

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

    def on_enter(self):
        if getattr(self, "type_candidates", None) is not None or getattr(self, "choosing_type", False):
            self.type_candidates, self.choosing_type = None, False      # Intro: generic wall
            self._status()
            self._reprompt()
            return
        super().on_enter()

    def _reprompt(self):
        lab = self._type_label()
        self.prompt(f"MURO ({lab}): siguiente punto o longitud; [Tipo/Espesor/Altura/Cota/Referencia/Invertir/iGual/Fin]:"
                    if self.startpoint is not None else
                    f"MURO ({lab}): espesor total o primer punto; [Tipo/Altura/Cota/Referencia/Invertir/iGual/Fin]:")

    def _status(self):
        side = {"izquierda": "cara derecha (cuerpo a la izquierda)",
                "derecha": "cara izquierda (cuerpo a la derecha)", "eje": "eje"}[self.reference]
        self.ctx.echo(f"MURO: {self._type_label()}, altura {self.height:g} m, se dibuja por: {side}")

    def start(self):
        self.capturing = False
        super().start()
        if getattr(self, "bim", None) is not None and "layers" not in self.bim:
            # defaults: the type with the default thickness, if exactly one
            from .parameters_arq import types_with_thickness
            hits = types_with_thickness(self._types(), self.thickness)
            if len(hits) == 1 and self.bim.get("type_name") in ("", "Muro genérico", None):
                self._apply_type(hits[0])
        self._install_f5()
        if getattr(self, "startpoint", None) is None:
            self._reprompt()

    def on_option(self, text):
        txt = str(text).strip().lower()
        if self._type_answer(text):
            self._status()
            self._reprompt()
            return True
        if self.pending == "thickness":
            self.pending = None
            if not _is_thickness(txt) and not txt.replace(",", ".").replace(".", "", 1).isdigit():
                self.ctx.echo("Debe introducir un espesor en metros.")
                self._reprompt()
                return True
            if not self._set_thickness(float(txt.replace(",", "."))):
                self._status()
                self._reprompt()
            return True
        if not self.pending and txt in ("i", "invertir", "f5", "cara"):
            self.reference = {"izquierda": "derecha", "derecha": "izquierda"}.get(
                self.reference, "izquierda")
            self._status()
            return True
        if not self.pending and self.startpoint is None and _is_number_text(txt):
            # before the first point a number is the TOTAL thickness (after
            # it, IngeCAD takes a number as the length along the cursor)
            if not self._set_thickness(float(txt.replace(",", "."))):
                self._status()
                self._reprompt()
            return True
        if not self.pending and txt in ("t", "tipo"):
            self._ask_type()
            return True
        if not self.pending and txt in ("g", "igual"):
            self.capturing = True
            self.prompt("MURO: designe el muro cuyas propiedades quiere usar:")
            return True
        return super().on_option(text)

    # --- automatic face at the start ---------------------------------------
    # A wall started on another wall's face or in an inner corner may lie
    # on the wrong side (its body inside the existing wall). As with the
    # reference program's "cambio automático de cara en esquina", the face
    # is swapped when the other side overlaps less; F5 still overrides.
    auto_face = True

    def _auto_reference(self, end):
        if not (self.auto_face and getattr(self, "chain_first", False)
                and self.reference in ("izquierda", "derecha") and self.startpoint is not None):
            return self.reference
        try:
            geo, _ents = walls_in(_document(self.ctx).doc)
        except Exception:  # noqa: BLE001
            return self.reference
        if not D.face_at(geo, self.startpoint, FACE_TOL):
            return self.reference
        return D.best_side(self.startpoint, end, self.thickness, self.reference, geo)

    def preview_segments(self, cursor):
        if self.startpoint is None or self.pending is not None:
            return []
        try:
            from .architectural_v10 import wall_corners
            c = wall_corners(self.startpoint, cursor, self.thickness, self._auto_reference(cursor))
            return list(zip(c, c[1:] + c[:1]))
        except ValueError:
            return []

    def on_point(self, p):
        if self.startpoint is None and not self.capturing and not self.pending:
            self.chain_first = True
        elif (self.startpoint is not None and not self.capturing and not self.pending
              and math.dist(self.startpoint, p) > 1e-6):
            ref = self._auto_reference(p)
            if ref != self.reference:
                self.reference = ref
                self.ctx.echo("MURO: cara cambiada automáticamente para no invadir el muro existente (F5 la invierte).")
            self.chain_first = False
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
                self.bim = {k: m.get(k, self.bim.get(k, "")) for k in ("name", "type_name", "material", "level")}
                if m.get("layers"):
                    self.bim["layers"] = [list(l) for l in m["layers"]]
                self.ctx.echo("MURO: propiedades tomadas de " + (m.get("name") or "muro")
                              + f" ({m['id'][:8]}).")
                self._status()
            self._reprompt()
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

class MuroParaleloTool(WallTypeChoice, Tool):
    """Wall parallel to a line: distance, base line, side, thickness side.
    After a wall, a click on empty space (no line) is the side of the next
    parallel, measured from the far face of the wall just made."""
    name = "MUROPARALELO"
    entity_picker = True
    _last_distance = None

    def start(self):
        self.name = type(self).name
        from .parameters_arq import load_defaults
        d = load_defaults(_document(self.ctx))["wall"]
        self.thickness, self.height, self.base = d["thickness"], d["height"], d["base"]
        self.bim = {k: d[k] for k in ("name", "type_name", "material", "level")}
        self.distance = type(self)._last_distance if type(self)._last_distance is not None else 1.0
        self.face = None
        self.side = None
        self.last = None            # (a, b, ref) of the last wall made
        self.stage = "face"
        self._ask_face()

    def _ask_face(self):
        self.stage = "face"
        txt = "línea base o lado de paralela" if self.last else "línea base (cara, eje o línea)"
        self.prompt(f"MUROPARALELO ({self._type_label()}; distancia {self.distance:g} m): "
                    f"indique {txt}; o teclee [distancia/Espesor/Tipo]:")

    def on_option(self, text):
        raw = str(text).strip()
        txt = raw.lower().replace(",", ".")
        if self._type_answer(raw):
            self._ask_face()
            return True
        if self.stage == "thickness":
            self.stage = "face"
            try:
                v = float(txt)
                if not (math.isfinite(v) and v > 0):
                    raise ValueError
            except ValueError:
                self.ctx.echo("Espesor no válido.")
                self._ask_face()
                return True
            if not self._set_thickness(v):
                self._ask_face()
            return True
        if txt in ("e", "espesor"):
            self.stage = "thickness"
            self.prompt(f"Espesor total del muro nuevo (m) <{self.thickness:g}>:")
            return True
        if txt in ("t", "tipo"):
            self._ask_type()
            return True
        try:
            v = float(txt)
            if not (math.isfinite(v) and v >= 0):
                raise ValueError
        except ValueError:
            return False
        self.distance = type(self)._last_distance = v
        self.ctx.echo(f"MUROPARALELO: nueva distancia {v:g} m.")
        self._ask_face()
        return True

    def on_enter(self):
        if getattr(self, "type_candidates", None) is not None or getattr(self, "choosing_type", False):
            self.type_candidates, self.choosing_type = None, False
            self._ask_face()
            return
        if self.stage in ("side", "body", "thickness"):
            self._ask_face()
            return
        self.ctx.finish()

    def _picked_line(self, p):
        services = getattr(self.ctx, "services", None)
        picked = services.pick_entity(p) if services else None
        line = line_of(picked, p)
        if line is None or math.dist(*line) < 1e-6:
            return None
        return line

    def on_point(self, p):
        if self.stage == "face":
            line = self._picked_line(p)
            if line is not None:
                self.face = line
                self.stage = "side"
                self.prompt("MUROPARALELO: lado de la paralela:")
                return
            if self.last is None:
                self.ctx.echo("Designe una línea recta (cara de muro, eje o línea).")
                return
            # chained: base = far face of the last wall, side = this click
            a, b, ref = self.last
            f = D.Frame(a, b, self.last_thickness, ref)
            o_click = f.local(p)[1]
            off = f.hi if abs(o_click - f.hi) < abs(o_click - f.lo) else f.lo
            self.face = (f.point(0.0, off), f.point(f.length, off))
            self.side = p
            self.stage = "body"
            self.prompt("MUROPARALELO: lado del espesor:")
            return
        if self.stage == "side":
            self.side = p
            self.stage = "body"
            self.prompt("MUROPARALELO: lado del espesor:")
            return
        if self.stage == "body":
            try:
                a, b, ref = D.parallel_wall(self.face[0], self.face[1], self.distance, self.side,
                                            self.thickness, body_point=p)
                geo, _ents = walls_in(_document(self.ctx).doc)
                a, b = D.extend_to_faces(a, b, geo, max_gap=self.distance + self.thickness + 0.5)
                cmd = create_wall(a, b, self.thickness, self.height, self.base, ref, **self.bim)
                apply(self.ctx, "ARQ MURO PARALELO", [cmd])
                self.last, self.last_thickness = (a, b, ref), self.thickness
                self.ctx.echo(f"MUROPARALELO: muro de {self.thickness:g} m a {self.distance:g} m "
                              f"de la línea base ({math.dist(a, b):.3f} m de longitud).")
            except Exception as exc:  # noqa: BLE001
                self.ctx.echo(f"MUROPARALELO: {type(exc).__name__}: {exc}")
            self._ask_face()

    def preview_segments(self, cursor):
        from .architectural_v10 import wall_corners
        try:
            if self.stage == "side" and self.face is not None:
                return [D.parallel_line(self.face[0], self.face[1], self.distance, cursor)]
            if self.stage == "body" and self.face is not None:
                a, b, ref = D.parallel_wall(self.face[0], self.face[1], self.distance, self.side,
                                            self.thickness, body_point=cursor)
                c = wall_corners(a, b, self.thickness, ref)
                return list(zip(c, c[1:] + c[:1]))
        except ValueError:
            return []
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
        if refuse_curved(self.ctx, self.name, entity):
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
    """Extend or shorten a wall from its picked end: to a free point
    (projected on the wall's direction), to a picked line, or to another
    wall's face (near face: T; far face: L, which cuts that wall). A typed
    length goes along the cursor direction from the moving end."""
    name = "ESTIRAMURO"
    verb = "alargar o acortar"

    def _pick_wall(self, p):
        ok = super()._pick_wall(p)
        if ok:
            m = metadata(self.wall)
            self.last_point = tuple(m["a"] if self.end == 0 else m["b"])     # moving end
        return ok

    def _target(self, p):
        """(new reference line a, b, extra host commands, message)."""
        m = metadata(self.wall)
        a, b = tuple(m["a"]), tuple(m["b"])
        fixed = b if self.end == 0 else a
        services = getattr(self.ctx, "services", None)
        picked = services.pick_entity(p) if services else None
        own = picked is not None and (picked is self.wall or
                                      m["id"] in ((metadata(picked) or {}).get("wall_ids") or []))
        line = None if (picked is None or own) else line_of(picked, p)
        if line is None:
            # free point: projected on the wall's own direction
            f = D.Frame(a, b, float(m["thickness"]), m.get("reference", "eje"))
            s, _o = f.local(p)
            x = f.point(s)
            na, nb = (x, b) if self.end == 0 else (a, x)
            if math.dist(na, nb) < 1e-6 or (self.end == 1 and s <= 0) or (self.end == 0 and s >= f.length):
                raise ValueError("El punto queda al otro lado del extremo que se conserva")
            return na, nb, [], "hasta el punto indicado"
        na, nb = D.extend_to_line(a, b, self.end, *line)
        x = na if self.end == 0 else nb
        geo, ents = walls_in(_document(self.ctx).doc)
        geo.pop(m["id"], None)
        for wid, side, _s in D.face_at(geo, x, FACE_TOL):
            g = D.end_gesture(fixed, x, float(m["thickness"]), m.get("reference", "eje"),
                              geo[wid], side)
            if g["kind"] == "L":
                host_end = 1 if g["kept"] == "start" else 0
                extra = reshape_wall(ents[wid], g["host_a"], g["host_b"], host_end)
                ne = g["new_end"]
                na, nb = (ne, b) if self.end == 0 else (a, ne)
                return na, nb, extra, "en esquina (L) con el muro designado"
            return na, nb, [], "en T contra el muro designado"
        return na, nb, [], "hasta la línea designada"

    def on_point(self, p):
        if self.wall is None:
            if self._pick_wall(p):
                self.prompt("ESTIRAMURO: nuevo extremo (punto, línea o cara de otro muro) o longitud:")
            return
        try:
            a, b, extra, how = self._target(p)
            apply(self.ctx, "ARQ ESTIRAMURO", extra + reshape_wall(self.wall, a, b, self.end))
            self.ctx.echo(f"ESTIRAMURO: muro modificado {how}; conserva su identidad BIM.")
        except Exception as exc:  # noqa: BLE001
            self.ctx.echo(f"ESTIRAMURO: {exc}")
            return
        self.wall = None
        self.last_point = None
        self.prompt("ESTIRAMURO: designe otro muro cerca del extremo o Intro para terminar:")

    def preview_segments(self, cursor):
        if self.wall is None:
            return []
        m = metadata(self.wall)
        try:
            f = D.Frame(m["a"], m["b"], float(m["thickness"]), m.get("reference", "eje"))
            s, _o = f.local(cursor)
            x = f.point(s)
            a, b = (x, tuple(m["b"])) if self.end == 0 else (tuple(m["a"]), x)
            from .architectural_v10 import wall_corners
            c = wall_corners(a, b, float(m["thickness"]), m.get("reference", "eje"))
            return list(zip(c, c[1:] + c[:1]))
        except ValueError:
            return []


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


# --- split / delete a stretch / join ------------------------------------------------

_EPS = 1e-6


def _wall_frame(m):
    return D.Frame(m["a"], m["b"], float(m["thickness"]), m.get("reference", "eje"))


def _props(m):
    return {k: m.get(k) for k in ("name", "type_name", "material", "level") if m.get(k) is not None}


def _rehost(opening, new_wall_cmd, offset):
    """Deferred: the opening now belongs to the wall created by
    ``new_wall_cmd`` (known only after it runs), at ``offset`` from its start."""
    from .architectural_v10 import opening_record, opening_symbol
    from . import openings as OP

    def factory(_doc):
        d = metadata(opening)
        wall = new_wall_cmd.entity
        rec, pt = opening_record(wall, offset, d["width"], d["sill"], d["height"], d["type"],
                                 existing=d["id"], **{k: d.get(k, "") for k in
                                                      ("name", "type_name", "material", "operation")},
                                 **{k: d[k] for k in OP.V3_KEYS if k in d and k != "operation"})
        if opening.dxftype() == "LWPOLYLINE":
            return EditArchitecturalCommand(opening, rec, points=opening_symbol(wall, rec))
        return EditArchitecturalCommand(opening, rec, position=(pt[0], pt[1], 0.0))
    return DeferredCommand("ARQ hueco", factory)


def _openings_of(entity, wall_id):
    return [e for e in entity.doc.modelspace()
            if (metadata(e) or {}).get("kind") == "opening" and metadata(e).get("wall_id") == wall_id]


def split_wall(entity, s1, s2):
    """Commands removing the stretch [s1, s2] (metres along the reference
    line) of a wall. The part before keeps the identity; the part after, if
    any, is a new wall that takes the openings lying on it. An opening in
    the removed stretch stops the operation."""
    from core.actions import EraseCommand
    m = copy.deepcopy(metadata(entity))
    f = _wall_frame(m)
    L = f.length
    s1, s2 = max(0.0, min(s1, s2)), min(L, max(s1, s2))
    if s2 - s1 < _EPS:
        raise ValueError("El tramo indicado no tiene longitud")
    ops = _openings_of(entity, m["id"])
    for o in ops:
        d = metadata(o)
        lo, hi = float(d["offset"]), float(d["offset"]) + float(d["width"])
        if hi > s1 + 1e-9 and lo < s2 - 1e-9:
            raise ValueError("Hay una carpintería en el tramo que se quiere quitar")
    keep_before, keep_after = s1 > _EPS, s2 < L - _EPS
    if not keep_before and not keep_after:
        from .sync import DropGroupsCommand
        return [DropGroupsCommand([entity]), EraseCommand([entity, *ops])], "muro completo borrado"
    if not keep_after:
        return reshape_wall(entity, f.a, f.point(s1), 1), "tramo final quitado"
    if not keep_before:
        return reshape_wall(entity, f.point(s2), f.b, 0), "tramo inicial quitado"
    m["b"] = list(f.point(s1))
    cmds = [EditArchitecturalCommand(entity, m, points=[tuple(f.a), f.point(s1)])]
    new = create_wall(f.point(s2), f.b, float(m["thickness"]), float(m["height"]),
                      float(m.get("base", 0.0)), m.get("reference", "eje"), **_props(m))
    cmds.append(new)
    for o in ops:
        d = metadata(o)
        if float(d["offset"]) >= s2 - 1e-9:
            cmds.append(_rehost(o, new, float(d["offset"]) - s2))
    return cmds, "muro partido en dos"


def crossing_params(entity, drawing):
    """Positions (m along the wall) where other walls cross it or end on it."""
    m = metadata(entity)
    f = _wall_frame(m)
    geo, _ents = walls_in(drawing)
    out = []
    for wid, (a, b, t, ref) in geo.items():
        if wid == m["id"]:
            continue
        g = D.Frame(a, b, t, ref)
        x = D.line_intersection(f.axis_point(0.0), f.u, g.axis_point(0.0), g.u)
        if x is None:
            continue
        s, _o = f.local(f.reference_point_from_axis(x))
        sg, _og = g.local(g.reference_point_from_axis(x))
        reach = f.t / 2.0 + 1e-6
        if _EPS < s < f.length - _EPS and -reach <= sg <= g.length + reach:
            out.append(s)
    return sorted(out)


class BorraTramoTool(Tool):
    """Delete the stretch of a wall between the crossings (or crossing and
    end) around the picked point; the junctions are rebuilt."""
    name = "BORRATRAMO"
    entity_picker = True

    def start(self):
        self.name = type(self).name
        self.prompt("BORRATRAMO: designe el tramo de muro que quiere borrar:")

    def on_point(self, p):
        entity, _line = wall_from_pick(self.ctx, p)
        if entity is None:
            self.ctx.echo("BORRATRAMO: designe un muro por su contorno.")
            return
        if refuse_curved(self.ctx, "BORRATRAMO", entity):
            return
        f = _wall_frame(metadata(entity))
        sp, _o = f.local(p)
        cuts = crossing_params(entity, _document(self.ctx).doc)
        s1 = max([c for c in cuts if c < sp], default=0.0)
        s2 = min([c for c in cuts if c > sp], default=f.length)
        try:
            cmds, how = split_wall(entity, s1, s2)
            apply(self.ctx, "ARQ BORRATRAMO", cmds)
            self.ctx.echo(f"BORRATRAMO: {how} ({s2 - s1:.3f} m).")
        except Exception as exc:  # noqa: BLE001
            self.ctx.echo(f"BORRATRAMO: {exc}")
        self.prompt("BORRATRAMO: designe otro tramo o Intro para terminar:")


class ParteMuroTool(Tool):
    """Open a gap (a full-height void) in a wall between two points: the wall
    becomes two walls."""
    name = "PARTEMURO"
    entity_picker = True

    def start(self):
        self.name = type(self).name
        self.wall = None
        self.p1 = None
        self.prompt("PARTEMURO: designe el muro:")

    def on_point(self, p):
        if self.wall is None:
            entity, _line = wall_from_pick(self.ctx, p)
            if entity is None:
                self.ctx.echo("PARTEMURO: designe un muro por su contorno.")
                return
            if refuse_curved(self.ctx, "PARTEMURO", entity):
                return
            self.wall = entity
            self.prompt("PARTEMURO: primer punto del vano:")
            return
        if self.p1 is None:
            self.p1 = tuple(p)
            self.last_point = self.p1
            self.prompt("PARTEMURO: segundo punto del vano (o longitud):")
            return
        f = _wall_frame(metadata(self.wall))
        s1, s2 = f.local(self.p1)[0], f.local(p)[0]
        try:
            cmds, how = split_wall(self.wall, s1, s2)
            apply(self.ctx, "ARQ PARTEMURO", cmds)
            self.ctx.echo(f"PARTEMURO: vano de {abs(s2 - s1):.3f} m; {how}.")
        except Exception as exc:  # noqa: BLE001
            self.ctx.echo(f"PARTEMURO: {exc}")
        self.wall = self.p1 = self.last_point = None
        self.prompt("PARTEMURO: designe otro muro o Intro para terminar:")


class UnirMuroTool(Tool):
    """Join two walls lying on the same axis with the same thickness into
    one (closing the gap between them). The first keeps its identity and
    receives the openings of the second."""
    name = "UNIRMURO"
    entity_picker = True

    def start(self):
        self.name = type(self).name
        self.first = None
        self.prompt("UNIRMURO: designe el primer muro (conserva su identidad):")

    def on_point(self, p):
        from core.actions import EraseCommand
        entity, _line = wall_from_pick(self.ctx, p)
        if entity is None:
            self.ctx.echo("UNIRMURO: designe un muro por su contorno.")
            return
        if refuse_curved(self.ctx, "UNIRMURO", entity):
            return
        if self.first is None:
            self.first = entity
            self.prompt("UNIRMURO: designe el segundo muro:")
            return
        first, self.first = self.first, None
        try:
            m1, m2 = copy.deepcopy(metadata(first)), metadata(entity)
            if m1["id"] == m2["id"]:
                raise ValueError("Designe dos muros distintos")
            f1, f2 = _wall_frame(m1), _wall_frame(m2)
            if abs(f1.t - f2.t) > 1e-6:
                raise ValueError("Los muros tienen distinto espesor")
            if abs(D._cross(f1.u, f2.u)) > 1e-6:
                raise ValueError("Los muros no son paralelos")
            for q in (f2.axis_point(0.0), f2.axis_point(f2.length)):
                if abs(f1.local(q)[1] - f1.mid) > 1e-3:
                    raise ValueError("Los muros no están sobre el mismo eje")
            ss = [0.0, f1.length] + [f1.local(f1.reference_point_from_axis(q))[0]
                                     for q in (f2.axis_point(0.0), f2.axis_point(f2.length))]
            smin, smax = min(ss), max(ss)
            ops1 = _openings_of(first, m1["id"])
            m1["a"], m1["b"] = list(f1.point(smin)), list(f1.point(smax))
            cmds = [EditArchitecturalCommand(first, m1, points=[f1.point(smin), f1.point(smax)])]
            for o in ops1:
                if abs(smin) > 1e-12:
                    cmds.append(DeferredCommand("ARQ hueco", lambda _d, o=o, ds=smin: edit_opening(
                        o, offset=float(metadata(o)["offset"]) - ds)))
            class _Done:                       # the first wall plays "the new wall" for _rehost
                entity = first
            for o in _openings_of(entity, m2["id"]):
                d = metadata(o)
                ends = [f1.local(f2.point(float(d["offset"]) + k))[0] - smin
                        for k in (0.0, float(d["width"]))]
                cmds.append(_rehost(o, _Done, min(ends)))
            from .sync import DropGroupsCommand
            cmds += [DropGroupsCommand([entity]), EraseCommand([entity])]
            apply(self.ctx, "ARQ UNIRMURO", cmds)
            self.ctx.echo(f"UNIRMURO: un solo muro de {smax - smin:.3f} m.")
        except Exception as exc:  # noqa: BLE001
            self.ctx.echo(f"UNIRMURO: {exc}")
        self.prompt("UNIRMURO: designe el primer muro de otra pareja o Intro para terminar:")


# --- DIVIDEMURO ------------------------------------------------------------------

class DivideMuroTool(WallTypeChoice, Tool):
    """Divide the span between two points into N equal clear spans with
    walls perpendicular to it (to the left of the first->second direction).
    Length: typed with L; without it, each wall reaches the facing wall."""
    name = "DIVIDEMURO"

    def start(self):
        self.name = type(self).name
        from .parameters_arq import load_defaults
        d = load_defaults(_document(self.ctx))["wall"]
        self.thickness, self.height, self.base = d["thickness"], d["height"], d["base"]
        self.bim = {k: d[k] for k in ("name", "type_name", "material", "level")}
        self.parts = getattr(type(self), "_last_parts", 2)
        self.length = None
        self.p1 = None
        self.pending = None
        self._prompt()

    def _prompt(self):
        ln = f"{self.length:g} m" if self.length else "hasta el muro de enfrente"
        self.prompt(f"DIVIDEMURO ({self.parts} partes, {self._type_label()}, longitud {ln}): "
                    "primer punto o [número de partes/Longitud/Espesor/Tipo]:")

    def on_option(self, text):
        raw = str(text).strip()
        txt = raw.lower().replace(",", ".")
        if self._type_answer(raw):
            self._prompt()
            return True
        if self.pending:
            key, self.pending = self.pending, None
            try:
                v = float(txt)
                if not (math.isfinite(v) and v >= 0):
                    raise ValueError
            except ValueError:
                self.ctx.echo("Valor no válido.")
                self._prompt()
                return True
            if key == "length":
                self.length = v or None
            elif v > 0 and self._set_thickness(v):
                return True
            self._prompt()
            return True
        if txt in ("l", "longitud"):
            self.pending = "length"
            self.prompt("Longitud de los muros (m; 0 = hasta el muro de enfrente):")
            return True
        if txt in ("e", "espesor"):
            self.pending = "thickness"
            self.prompt(f"Espesor total (m) <{self.thickness:g}>:")
            return True
        if txt in ("t", "tipo"):
            self._ask_type()
            return True
        if txt.isdigit() and self.p1 is None:
            n = int(txt)
            if n < 2:
                self.ctx.echo("Indique al menos 2 partes.")
            else:
                self.parts = type(self)._last_parts = n
            self._prompt()
            return True
        return False

    def on_enter(self):
        if self.pending or getattr(self, "type_candidates", None) is not None \
                or getattr(self, "choosing_type", False):
            self.pending, self.type_candidates, self.choosing_type = None, None, False
            self._prompt()
            return
        self.ctx.finish()

    def on_point(self, p):
        if self.p1 is None:
            self.p1 = tuple(p)
            self.last_point = self.p1
            self.prompt("DIVIDEMURO: segundo punto (los muros se dibujan a la izquierda del sentido):")
            return
        p1, self.p1, self.last_point = self.p1, None, None
        try:
            geo, _ents = walls_in(_document(self.ctx).doc)
            lines = D.divide_walls(p1, p, self.parts, self.thickness, self.length, geo)
            cmds = [create_wall(a, b, self.thickness, self.height, self.base, ref, **self.bim)
                    for a, b, ref in lines]
            apply(self.ctx, "ARQ DIVIDEMURO", cmds)
            self.ctx.echo(f"DIVIDEMURO: {len(cmds)} muro(s); {self.parts} partes iguales.")
        except Exception as exc:  # noqa: BLE001
            self.ctx.echo(f"DIVIDEMURO: {exc}")
        self._prompt()

    def preview_segments(self, cursor):
        if self.p1 is None or math.dist(self.p1, cursor) < 1e-6:
            return []
        try:
            lines = D.divide_walls(self.p1, cursor, self.parts, self.thickness,
                                   self.length or 1.0)
        except ValueError:
            return [(self.p1, tuple(cursor))]
        from .architectural_v10 import wall_corners
        segs = [(self.p1, tuple(cursor))]
        for a, b, ref in lines:
            c = wall_corners(a, b, self.thickness, ref)
            segs += list(zip(c, c[1:] + c[:1]))
        return segs


# --- RECINTO -----------------------------------------------------------------------

SPACE_LAYER = "ARQ-RECINTOS"


def create_space(seed, room, *, name, number, height, base=0.0, level="Planta baja", use="",
                 ceiling=False, enclosure="interior"):
    """AddEntityCommand of a space: closed outline + its BIM record (seed)."""
    import uuid
    from core.actions import AddEntityCommand
    from .architectural import _xdata
    rec = {"kind": "space", "schema": 1, "id": uuid.uuid4().hex, "ifc_class": "IfcSpace",
           "seed": [float(seed[0]), float(seed[1])], "ref_vertex": list(room["outer"][0]),
           "name": name, "number": str(number), "use": use, "level": level,
           "base": float(base), "height": float(height), "ceiling": bool(ceiling), "enclosure": enclosure,
           "area": room["area"],
           "perimeter": room["perimeter"], "islands": [[list(q) for q in h] for h in room["holes"]]}

    def factory(msp):
        e = msp.add_lwpolyline([tuple(q) for q in room["outer"]], close=True)
        return _xdata(msp, e, rec)
    return AddEntityCommand("ARQ RECINTO", factory, layer=SPACE_LAYER), rec


class RecintoTool(Tool):
    """Space (room) by a click inside it; associative to the walls."""
    name = "RECINTO"

    def start(self):
        self.name = type(self).name
        from .parameters_arq import load_defaults
        d = load_defaults(_document(self.ctx))["wall"]
        self.slab_height = self.height = float(d["height"])
        self.ceiling = False
        self.enclosure = "interior"
        self.level = d.get("level") or "Planta baja"
        self.use = ""
        self.next_name = None
        self.pending = None
        self._prompt()

    def _prompt(self):
        top = (f"falso techo a {self.height:g} m" if self.ceiling
               else f"hasta el forjado, {self.height:g} m").replace(".", ",")
        kind = "" if self.enclosure == "interior" else "exterior cubierto, "
        self.prompt(f"RECINTO ({kind}{top}): haga clic dentro de la estancia o "
                    "[Nombre/Altura/Falso techo/Tipo/Uso]:")

    def _count(self):
        return sum(1 for e in _document(self.ctx).doc.modelspace()
                   if (metadata(e) or {}).get("kind") == "space")

    def on_option(self, text):
        raw = str(text).strip()
        txt = raw.lower()
        if self.pending:
            key, self.pending = self.pending, None
            if key == "name":
                self.next_name = raw
            elif key == "use":
                self.use = raw
            elif key == "enclosure":
                self.enclosure = "exterior_cubierto" if txt.startswith("e") else "interior"
            elif key == "ceiling":
                try:
                    v = float(txt.replace(",", ".")) if txt else 0.0
                    if not (math.isfinite(v) and v >= 0):
                        raise ValueError
                    if v > 0:
                        self.height, self.ceiling = v, True
                    else:
                        self.height, self.ceiling = self.slab_height, False
                except ValueError:
                    self.ctx.echo("Altura no válida.")
            else:
                try:
                    v = float(txt.replace(",", "."))
                    if not (math.isfinite(v) and v > 0):
                        raise ValueError
                    self.height = v
                except ValueError:
                    self.ctx.echo("Altura no válida.")
            self._prompt()
            return True
        if txt in ("n", "nombre"):
            self.pending = "name"
            self.prompt("Nombre del recinto:")
            return True
        if txt in ("a", "altura"):
            self.pending = "height"
            self.prompt(f"Altura libre del recinto (m) <{self.height:g}>:")
            return True
        if txt in ("t", "tipo"):
            self.pending = "enclosure"
            self.prompt("Tipo de recinto [Interior/Exterior cubierto (terraza, balcón, galería, porche)]:")
            return True
        if txt in ("f", "falso techo", "falsotecho", "techo"):
            self.pending = "ceiling"
            self.prompt("Altura libre bajo el falso techo (m; 0 = sin falso techo, hasta el forjado):")
            return True
        if txt in ("u", "uso"):
            self.pending = "use"
            self.prompt("Uso del recinto (p. ej. habitable, no habitable):")
            return True
        return False

    def on_enter(self):
        if self.pending:
            self.pending = None
            self._prompt()
            return
        self.ctx.finish()

    def on_point(self, p):
        from .exchange import read_model
        from .geom import junctions as J
        from .geom import spaces as SP
        doc = _document(self.ctx).doc
        records, columns, _ops, _issues = read_model(doc, strict=False)
        result = J.solve(J.walls_from_records(records), [(cid, m["polygon"]) for cid, m in columns])
        room, why = SP.space_at(result, p)
        if room is None:
            self.ctx.echo("RECINTO: " + ("el punto está dentro de un muro o pilar."
                                         if why == "muro" else
                                         "la estancia no está cerrada (falta un muro o una separación)."))
            return
        for e in doc.modelspace():
            m = metadata(e) or {}
            if m.get("kind") == "space" and m.get("seed"):
                other, _w = SP.space_at(result, m["seed"])
                if other is not None and other["outer"] == room["outer"]:
                    self.ctx.echo(f"RECINTO: esa estancia ya es el recinto {m.get('name')}.")
                    return
        n = self._count() + 1
        name = self.next_name or f"Recinto {n}"
        self.next_name = None
        cmd, rec = create_space(p, room, name=name, number=n, height=self.height,
                                level=self.level, use=self.use, ceiling=self.ceiling,
                                enclosure=self.enclosure)
        try:
            apply(self.ctx, "ARQ RECINTO", [cmd], kind="space")
        except Exception as exc:  # noqa: BLE001
            self.ctx.echo(f"RECINTO: {type(exc).__name__}: {exc}")
            return
        islas = f", {len(room['holes'])} isla(s) descontada(s)" if room["holes"] else ""
        num = lambda v: f"{v:.2f}".replace(".", ",")  # noqa: E731
        self.ctx.echo(f"RECINTO: {name}: {num(room['area'])} m², perímetro {num(room['perimeter'])} m"
                      f"{islas}; altura {num(self.height)} m"
                      f"{' hasta el falso techo' if self.ceiling else ''}.")
        self._prompt()


TOOLS = TOOLS + (RecintoTool, DivideMuroTool, BorraTramoTool, ParteMuroTool, UnirMuroTool)


def _is_number_text(txt):
    try:
        v = float(str(txt).replace(",", "."))
        return math.isfinite(v) and v > 0
    except ValueError:
        return False

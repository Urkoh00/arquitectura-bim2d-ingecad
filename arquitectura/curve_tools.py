# SPDX-License-Identifier: GPL-3.0-or-later
"""Curved walls: MUROCURVO draws them, CURVAMURO bends (or straightens) one.

A curved wall is the same BIM wall as a straight one, with a ``bulge`` in
its record and in its CAD axis (a polyline arc): its ends, and so its
junctions with the other walls, do not change when it is bent. The
junction engine (``geom.junctions``) makes its faces true concentric arcs.
"""
from __future__ import annotations

import copy
import math

from tools.base import Tool

from .architectural import metadata
from .geom import curves as CV


def _num(text):
    v = float(str(text).strip().replace(",", "."))
    if not math.isfinite(v):
        raise ValueError("número no válido")
    return v


def _fmt(v):
    return f"{v:g}".replace(".", ",")


def outline(a, b, bulge, thickness, reference):
    """Preview edges of a wall (straight or curved) from its reference line."""
    from .geom import junctions as J
    w = J.Wall("vista", a, b, thickness, reference, bulge=bulge)
    pts = w.strip()
    return list(zip(pts, pts[1:] + pts[:1]))


def _bulge_for(a, b, p):
    bulge = CV.bulge_through(a, b, p)
    if abs(bulge) > CV.MAX_BULGE + 1e-9:
        raise ValueError("más de media circunferencia: elija un punto de paso más cercano a la cuerda")
    return bulge


# --- MUROCURVO -------------------------------------------------------------------

class MuroCurvoTool(Tool):
    name = "MUROCURVO"

    def start(self):
        from .compat import require_document
        from .parameters_arq import load_defaults
        d = load_defaults(require_document(self.ctx))["wall"]
        self.thickness, self.height = float(d["thickness"]), float(d["height"])
        self.base, self.reference = float(d["base"]), d["reference"]
        self.bim = {k: d[k] for k in ("name", "type_name", "material", "level")}
        self.a = self.b = None
        self.circle = None              # None | "centre" | "radius"
        self.centre = None
        self.pending = None
        self.last_point = None
        self._prompt()

    def _label(self):
        return (f"espesor {_fmt(self.thickness)} m, altura {_fmt(self.height)} m, "
                f"referencia {self.reference}")

    def _prompt(self):
        if self.circle == "centre":
            self.prompt("MUROCURVO circular: centro:")
        elif self.circle == "radius":
            self.prompt("MUROCURVO circular: punto de la línea de referencia (o radio en m):")
        elif self.a is None:
            self.prompt(f"MUROCURVO ({self._label()}): punto inicial o "
                        "[Espesor/Altura/Cota/Referencia/circular (O)/Fin]:")
        elif self.b is None:
            self.prompt("MUROCURVO: punto final del muro:")
        else:
            self.prompt("MUROCURVO: punto de paso de la curva, o flecha en m (positiva a la izquierda "
                        "del sentido de dibujo):")

    def on_option(self, text):
        t = str(text).strip().lower()
        if self.pending:
            key, self.pending = self.pending, None
            try:
                if key == "reference":
                    refs = {"e": "eje", "eje": "eje", "i": "izquierda", "izquierda": "izquierda",
                            "d": "derecha", "derecha": "derecha"}
                    if t not in refs:
                        raise ValueError("referencia: eje / izquierda / derecha")
                    self.reference = refs[t]
                else:
                    v = _num(t)
                    if key != "base" and v <= 0:
                        raise ValueError("debe ser positivo")
                    setattr(self, key, v)
                self.ctx.echo(f"MUROCURVO: {self._label()}")
            except ValueError as exc:
                self.ctx.echo(f"MUROCURVO: {exc}")
            self._prompt()
            return True
        if self.circle == "radius":
            try:
                r = _num(t)
                if r <= 0:
                    raise ValueError("radio positivo")
                self._make_circle((self.centre[0] + r, self.centre[1]))
            except ValueError as exc:
                self.ctx.echo(f"MUROCURVO: {exc}")
            self._prompt()
            return True
        if t in ("o", "circular") and self.a is None and not self.circle:
            self.circle = "centre"
            self._prompt()
            return True
        if self.b is not None:
            try:
                sag = _num(t)
            except ValueError:
                sag = None
            if sag is not None:
                try:
                    self._make(CV.bulge_from_sagitta(self.a, self.b, sag))
                except ValueError as exc:
                    self.ctx.echo(f"MUROCURVO: {exc}")
                self._prompt()
                return True
        keys = {"e": "thickness", "espesor": "thickness", "a": "height", "altura": "height",
                "c": "base", "cota": "base", "r": "reference", "referencia": "reference"}
        if t in keys and self.b is None:
            self.pending = keys[t]
            self.prompt("Referencia [Eje/Izquierda/Derecha]:" if self.pending == "reference" else "Valor (m):")
            return True
        if t in ("f", "fin"):
            self.ctx.finish()
            return True
        return False

    def on_point(self, p):
        p = (float(p[0]), float(p[1]))
        if self.pending:
            self.ctx.echo("Termine primero la opción.")
            return
        if self.circle == "centre":
            self.centre = self.last_point = p
            self.circle = "radius"
        elif self.circle == "radius":
            try:
                self._make_circle(p)
            except ValueError as exc:
                self.ctx.echo(f"MUROCURVO: {exc}")
        elif self.a is None:
            self.a = self.last_point = p
        elif self.b is None:
            if math.dist(self.a, p) < 1e-6:
                self.ctx.echo("MUROCURVO: el punto final debe ser distinto del inicial.")
                return
            self.b = self.last_point = p
        else:
            try:
                self._make(_bulge_for(self.a, self.b, p))
            except ValueError as exc:
                self.ctx.echo(f"MUROCURVO: {exc}")
        self._prompt()

    def _make(self, bulge):
        from .architectural_v10 import create_wall
        from .transactions import apply_architectural_change
        cmd = create_wall(self.a, self.b, self.thickness, self.height, self.base, self.reference,
                          bulge=bulge, **self.bim)
        apply_architectural_change(self.ctx, cmd, kind="wall")
        if abs(bulge) > 1e-9:
            from .geom import junctions as J
            w = J.Wall("x", self.a, self.b, self.thickness, self.reference, bulge=bulge)
            self.ctx.echo(f"MUROCURVO: radio {_fmt(round(w.r, 3))} m, desarrollo {_fmt(round(w.length, 3))} m.")
        # chain: the next curved wall starts where this one ended
        self.a, self.b = self.b, None
        self.last_point = self.a

    def _make_circle(self, p):
        """A round wall: two half circles meeting end to end (each one is an
        ordinary curved wall, so every tool works on them)."""
        from core.commands import CompositeCommand
        from .architectural_v10 import create_wall
        from .transactions import apply_architectural_change
        c = self.centre
        if math.dist(c, p) < 1e-6:
            raise ValueError("el punto coincide con el centro")
        q = (2 * c[0] - p[0], 2 * c[1] - p[1])
        cmds = [create_wall(p, q, self.thickness, self.height, self.base, self.reference, bulge=1.0, **self.bim),
                create_wall(q, p, self.thickness, self.height, self.base, self.reference, bulge=1.0, **self.bim)]
        apply_architectural_change(self.ctx, CompositeCommand("ARQ MURO CIRCULAR", cmds), kind="wall")
        self.ctx.echo(f"MUROCURVO: muro circular de radio {_fmt(round(math.dist(c, p), 3))} m "
                      "(dos medias circunferencias).")
        self.circle = self.centre = self.last_point = None

    def on_enter(self):
        if self.circle:
            self.circle = self.centre = self.last_point = None
        elif self.pending:
            self.pending = None
        elif self.b is not None:
            self.b = None
        elif self.a is not None:
            self.a = self.last_point = None
        else:
            self.ctx.finish()
            return
        self._prompt()

    def preview_segments(self, cursor):
        if self.circle == "radius":
            try:
                c = self.centre
                q = (2 * c[0] - cursor[0], 2 * c[1] - cursor[1])
                return (outline(tuple(cursor), q, 1.0, self.thickness, self.reference)
                        + outline(q, tuple(cursor), 1.0, self.thickness, self.reference))
            except (ValueError, ZeroDivisionError):
                return []
        if self.a is None or self.pending:
            return []
        try:
            if self.b is None:
                if math.dist(self.a, cursor) < 1e-6:
                    return []
                return outline(self.a, cursor, 0.0, self.thickness, self.reference)
            return outline(self.a, self.b, _bulge_for(self.a, self.b, cursor), self.thickness, self.reference)
        except ValueError:
            return []


# --- CURVAMURO -------------------------------------------------------------------

def carried_openings(entity, old, new):
    """[(opening entity, new offset, new width)] keeping each carpentry (its
    real, planar width) at the same relative position along the wall when
    its curve changes. Raises ValueError when one no longer fits."""
    from . import openings as OP
    from .geom import junctions as J
    w0 = J.walls_from_records([(old["id"], old)])[0]
    w1 = J.walls_from_records([(new["id"], new)])[0]
    out, spans = [], []
    for e in entity.doc.modelspace():
        d = metadata(e) or {}
        if d.get("kind") != "opening" or d.get("wall_id") != old["id"]:
            continue
        chord = float(d.get("chord") or d["width"])
        centre = (float(d["offset"]) + float(d["width"]) / 2) * w1.length / w0.length
        width = OP.span_of(w1, chord)
        off = centre - width / 2
        label = d.get("name") or OP.NAMES.get(d.get("type"), "Carpintería")
        if off < -1e-9 or off + width > w1.length + 1e-9:
            raise ValueError(f"{label} no cabe en el muro con esa curvatura")
        OP.proxy(w1, {**OP.normalise(d), "offset": off, "width": width, "chord": chord})  # planar fit
        spans.append((off, off + width, label))
        out.append((e, max(0.0, off), width))
    spans.sort()
    for (a0, a1, la), (b0, _b1, lb) in zip(spans, spans[1:]):
        if a1 > b0 + 1e-9:
            raise ValueError(f"{la} y {lb} se solaparían con esa curvatura")
    return out


class CurvaMuroTool(Tool):
    name = "CURVAMURO"

    def start(self):
        self.wall = None
        self.prompt("CURVAMURO: designe el muro que quiere curvar (o enderezar):")

    def _pick(self, p):
        from .wall_tools import wall_from_pick
        entity, _line = wall_from_pick(self.ctx, p)
        if entity is None:
            self.ctx.echo("CURVAMURO: designe un muro por su contorno.")
            return
        m = metadata(entity)
        self.wall = entity
        self.last_point = tuple(m["a"])
        self.prompt("CURVAMURO: punto de paso del eje (o de la cara de referencia), o flecha en m "
                    "(positiva a la izquierda de a→b; 0 lo endereza):")

    def on_point(self, p):
        p = (float(p[0]), float(p[1]))
        if self.wall is None:
            self._pick(p)
            return
        m = metadata(self.wall)
        try:
            self._apply(_bulge_for(m["a"], m["b"], p))
        except ValueError as exc:
            self.ctx.echo(f"CURVAMURO: {exc}")

    def on_option(self, text):
        if self.wall is None:
            if str(text).strip().lower() in ("f", "fin"):
                self.ctx.finish()
                return True
            return False
        try:
            sag = _num(text)
        except ValueError:
            return False
        m = metadata(self.wall)
        try:
            self._apply(CV.bulge_from_sagitta(m["a"], m["b"], sag))
        except ValueError as exc:
            self.ctx.echo(f"CURVAMURO: {exc}")
        return True

    def _apply(self, bulge):
        from core.commands import CompositeCommand, DeferredCommand
        from .architectural_v10 import (EditArchitecturalCommand, _find_openings, axis_points,
                                        check_curve, edit_opening)
        from .transactions import apply_architectural_change
        old = metadata(self.wall)
        m = copy.deepcopy(old)
        if abs(bulge) > 1e-9:
            m["bulge"] = float(bulge)
        else:
            m.pop("bulge", None)
        check_curve(m)
        cmds = [EditArchitecturalCommand(self.wall, m, points=axis_points(m))]
        moves = carried_openings(self.wall, old, m)          # raises if one does not fit
        for e, off, width in moves:
            cmds.append(DeferredCommand("ARQ hueco", lambda _d, e=e, off=off, w=width:
                                        edit_opening(e, offset=off, width=w)))
        cmd = CompositeCommand("ARQ CURVAR MURO", cmds)
        apply_architectural_change(self.ctx, cmd, kind="opening" if moves else "wall")
        self.ctx.echo("CURVAMURO: muro enderezado." if "bulge" not in m else
                      f"CURVAMURO: muro curvado ({_fmt(round(math.degrees(4 * math.atan(abs(bulge))), 1))}°).")
        self.wall = None
        self.prompt("CURVAMURO: designe otro muro o [Fin]:")

    def on_enter(self):
        if self.wall is not None:
            self.wall = None
            self.prompt("CURVAMURO: designe el muro que quiere curvar (o enderezar):")
        else:
            self.ctx.finish()

    def preview_segments(self, cursor):
        if self.wall is None:
            return []
        m = metadata(self.wall)
        try:
            return outline(m["a"], m["b"], _bulge_for(m["a"], m["b"], cursor),
                           float(m["thickness"]), m.get("reference", "eje"))
        except (ValueError, ZeroDivisionError):
            return []

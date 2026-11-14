# SPDX-License-Identifier: GPL-3.0-or-later
"""PILAR: placing BIM columns the way architects place them.

* Free placement by one of 9 anchors (numeric keypad: 7 8 9 / 4 5 6 /
  1 2 3; 5 is the centre), with rotation by 90° (G), a typed angle (R) or
  automatic rotation from the wall or line under the cursor (A).
* «A distancia de paramentos» (P): two wall faces (or lines) and a click in
  the corner where the column goes: its sides lie at d1 and d2 from them.
  The usual façade case: two outer faces and d = 0,05 m.
* «A distancia de un paramento» (U): one face and a point along it.
* Sections typed with S: 0,30x0,30 · 30x40 (cm) · D0,35 · IPE 200 · IPN 160
  · HEA 200 · HEB 160 · UPN 120 · 2UPN 160 cajon · 2UPN 160 empresillado
  0,10. Covering (recubrimiento) with C.

Geometry in ``sections``; every insertion is one undoable step with the
plan regenerated (walls cut by the column, rooms go round it).
"""
from __future__ import annotations

import math

from tools.base import Tool

from . import sections as SEC
from .geom import drafting as D
from .wall_tools import _document, line_of


def _line_dir(line):
    (x0, y0), (x1, y1) = line
    L = math.hypot(x1 - x0, y1 - y0)
    return (x1 - x0) / L, (y1 - y0) / L


class PilarTool(Tool):
    name = "PILAR"

    @property
    def entity_picker(self):
        """IngeCAD gives a picking tool the raw cursor, without its object
        snaps. PILAR only picks while it asks for a wall face (P and U);
        the insertion point takes IngeCAD's snaps (end, middle, intersection,
        grid...) like any drawing command (prueba del usuario, 10-11)."""
        mode = getattr(self, "mode", "libre")
        picks = len(getattr(self, "picks", ()) or ())
        return (mode == "paramentos" and picks < 2) or (mode == "paramento" and picks < 1)

    def start(self):
        self.name = type(self).name
        from .parameters_arq import load_defaults
        self.values = dict(load_defaults(_document(self.ctx))["column"])
        self.values.setdefault("cover", 0.0)
        self.anchor = 5
        self.auto = False
        self.mode = "libre"
        self.d1 = self.d2 = 0.05
        self.picks = []
        self.pending = None
        from .double_click import preset
        taken = preset("PILAR")
        if taken:
            # a double-click on a column: its section, no sheet
            self.values.update({k: taken[k] for k in ("shape", "width", "depth", "radius", "rotation",
                                                      "profile", "cover", "height", "base", "name",
                                                      "type_name", "material", "level") if k in taken})
            self.ctx.echo("PILAR: con la sección de " + (taken.get("name") or "el pilar") + ".")
            self._prompt()
            return
        try:
            from . import bim_dialogs
            if bim_dialogs.available(self.ctx):
                values = bim_dialogs.column_properties(self.ctx, self.values, self.anchor)
                if values is None:
                    self.ctx.finish()
                    return
                self.anchor = int(values.pop("anchor", self.anchor) or 5)
                self.values.update(values)
        except Exception as exc:  # noqa: BLE001
            self.ctx.echo(f"PILAR: ficha no disponible ({type(exc).__name__}: {exc}).")
        self._prompt()

    # --- text ---------------------------------------------------------------
    def _section_text(self):
        v = self.values
        if v.get("shape") == "steel":
            s = v.get("profile", "")
        elif v.get("shape") == "rect":
            s = f"{float(v['width']):g}x{float(v['depth']):g}"
        else:
            s = f"D{2 * float(v['radius']):g}"
        cov = float(v.get("cover") or 0)
        return (s + (f" + recubrimiento {cov:g}" if cov else "")).replace(".", ",")

    def _prompt(self):
        mode = {"libre": f"enganche {self.anchor}" + (", autorrotación" if self.auto else ""),
                "paramentos": f"a {self.d1:g} y {self.d2:g} m de dos paramentos",
                "paramento": f"a {self.d1:g} m de un paramento"}[self.mode].replace(".", ",")
        steps = {"libre": ["punto de inserción"],
                 "paramentos": ["primer paramento", "segundo paramento",
                                "clic en la esquina donde va el pilar"],
                 "paramento": ["paramento", "punto a lo largo del paramento (en el lado del pilar)"]}[self.mode]
        step = steps[min(len(self.picks), len(steps) - 1)]
        self.prompt(f"PILAR ({self._section_text()}; {mode}): {step} o "
                    "[Sección/Enganche/Girar/Rotación/Autorrotación/Paramentos/Un paramento/Libre/reCubrimiento/Fin]:")

    def on_option(self, text):
        raw = str(text).strip()
        txt = raw.lower()
        if self.pending:
            key, self.pending = self.pending, None
            try:
                if key == "section":
                    self.values.update(SEC.parse_section(raw))
                    SEC.local_footprint(self.values)            # validate now
                elif key == "anchor":
                    k = int(txt)
                    if not 1 <= k <= 9:
                        raise ValueError("Enganche entre 1 y 9")
                    self.anchor = k
                elif key == "rotation":
                    self.values["rotation"] = float(txt.replace(",", "."))
                elif key == "cover":
                    v = float(txt.replace(",", "."))
                    if not (math.isfinite(v) and v >= 0):
                        raise ValueError("Recubrimiento no válido")
                    self.values["cover"] = v
                elif key in ("paramentos", "paramento"):
                    parts = [float(x.replace(",", ".")) for x in raw.replace(";", " ").split()] or [0.05]
                    self.d1 = parts[0]
                    self.d2 = parts[1] if len(parts) > 1 else parts[0]
                    self.mode, self.picks = key, []
            except (ValueError, TypeError) as exc:
                self.ctx.echo(f"PILAR: {exc}")
            self._prompt()
            return True
        options = {"s": ("section", "Sección (0,30x0,30 · D0,35 · IPE 200 · HEB 160 · UPN 120 · "
                                    "2UPN 160 cajon · 2UPN 160 empresillado 0,10):"),
                   "seccion": None, "e": ("anchor", "Enganche (teclado numérico: 7 8 9 / 4 5 6 / 1 2 3):"),
                   "r": ("rotation", "Ángulo del pilar (grados):"),
                   "c": ("cover", "Espesor del recubrimiento (m; 0 = sin recubrimiento):"),
                   "p": ("paramentos", f"Distancias a los paramentos (m) <{self.d1:g} {self.d2:g}>:"),
                   "u": ("paramento", f"Distancia al paramento (m) <{self.d1:g}>:")}
        options["seccion"] = options["s"]
        if txt in options:
            self.pending = options[txt][0]
            self.prompt("PILAR: " + options[txt][1])
            return True
        if txt in ("g", "girar"):
            self.values["rotation"] = (float(self.values.get("rotation") or 0) + 90.0) % 360.0
            self._prompt()
            return True
        if txt in ("a", "autorrotacion", "autorrotación"):
            self.auto = not self.auto
            self._prompt()
            return True
        if txt in ("l", "libre"):
            self.mode, self.picks = "libre", []
            self._prompt()
            return True
        if txt in ("f", "fin"):
            self.ctx.finish()
            return True
        return False

    def on_enter(self):
        if self.pending:
            key, self.pending = self.pending, None
            if key in ("paramentos", "paramento"):          # Intro keeps the distances
                self.mode, self.picks = key, []
            self._prompt()
            return
        if self.picks:
            self.picks = []
            self._prompt()
            return
        self.ctx.finish()

    # --- placement -------------------------------------------------------------
    def _picked_line(self, p):
        services = getattr(self.ctx, "services", None)
        return line_of(services.pick_entity(p) if services else None, p)

    def _auto_rotation(self, p):
        line = self._picked_line(p)
        if line is None or math.dist(*line) < 1e-9:
            return None
        ux, uy = _line_dir(line)
        return math.degrees(math.atan2(uy, ux))

    def _free_center(self, p):
        values = dict(self.values)
        if self.auto:
            rot = self._auto_rotation(p)
            if rot is not None:
                extra = round(float(self.values.get("rotation") or 0) / 90.0) * 90.0 % 180.0
                values["rotation"] = rot + extra
        return SEC.center_from_anchor(p, values, self.anchor), values

    def _corner_center(self, l1, l2, q):
        """Column in the corner of lines l1, l2 that contains q, its sides at
        d1 from l1 and d2 from l2, aligned with l1."""
        u1, u2 = _line_dir(l1), _line_dir(l2)
        x = D.line_intersection(l1[0], u1, l2[0], u2)
        if x is None:
            raise ValueError("Los dos paramentos son paralelos")
        n1 = (-u1[1], u1[0])
        if (q[0] - x[0]) * n1[0] + (q[1] - x[1]) * n1[1] < 0:
            n1 = (-n1[0], -n1[1])
        n2 = (-u2[1], u2[0])
        if (q[0] - x[0]) * n2[0] + (q[1] - x[1]) * n2[1] < 0:
            n2 = (-n2[0], -n2[1])
        # e1: along l1, away from l2 (toward q's side of l2)
        e1 = u1 if u1[0] * n2[0] + u1[1] * n2[1] > 0 else (-u1[0], -u1[1])
        # corner = intersection of l1 moved d1 toward q and l2 moved d2 toward q
        c = D.line_intersection((x[0] + n1[0] * self.d1, x[1] + n1[1] * self.d1), u1,
                                (x[0] + n2[0] * self.d2, x[1] + n2[1] * self.d2), u2)
        values = dict(self.values)
        values["rotation"] = (math.degrees(math.atan2(e1[1], e1[0]))
                              + round(float(self.values.get("rotation") or 0) / 90.0) * 90.0) % 360.0
        w, d = SEC.local_size(values)
        if abs(((values["rotation"] - math.degrees(math.atan2(e1[1], e1[0]))) % 180.0) - 90.0) < 1e-6:
            w, d = d, w                        # turned 90°: the depth runs along l1
        # oblique corner: move along e1 until the side clears l2 by d2
        s = abs(e1[0] * n2[0] + e1[1] * n2[1]) or 1.0
        center = (c[0] + e1[0] * (w / 2) + n1[0] * (d / 2),
                  c[1] + e1[1] * (w / 2) + n1[1] * (d / 2))
        if s < 0.999999:
            # for non-perpendicular faces keep the nearest corner at distance d2
            k = (d / 2) * abs(n1[0] * n2[0] + n1[1] * n2[1]) / s
            center = (center[0] + e1[0] * k, center[1] + e1[1] * k)
        return center, values

    def _face_center(self, line, q):
        u = _line_dir(line)
        n = (-u[1], u[0])
        if (q[0] - line[0][0]) * n[0] + (q[1] - line[0][1]) * n[1] < 0:
            n = (-n[0], -n[1])
        f = D.Frame(line[0], line[1], 1.0, "eje")
        s, _o = f.local(q)
        foot = f.point(s)
        values = dict(self.values)
        values["rotation"] = (math.degrees(math.atan2(u[1], u[0]))
                              + round(float(self.values.get("rotation") or 0) / 90.0) * 90.0) % 360.0
        w, d = SEC.local_size(values)
        if abs(((values["rotation"] - math.degrees(math.atan2(u[1], u[0]))) % 180.0) - 90.0) < 1e-6:
            w, d = d, w
        off = self.d1 + d / 2
        return (foot[0] + n[0] * off, foot[1] + n[1] * off), values

    def _place(self, center, values):
        from .columns import column_command
        from .transactions import apply_architectural_change
        try:
            from .grids import binding
            link=binding(_document(self.ctx).doc,center)
            if link:values={**values,'grid_link':link}
            apply_architectural_change(self.ctx, column_command(center, values), kind="column")
            self.ctx.echo(f"PILAR: {self._section_text()} colocado; muros y recintos actualizados.")
        except Exception as exc:  # noqa: BLE001
            self.ctx.echo(f"PILAR: {type(exc).__name__}: {exc}")

    def on_point(self, p):
        p = (float(p[0]), float(p[1]))
        if self.mode == "libre":
            center, values = self._free_center(p)
            self._place(center, values)
        elif self.mode == "paramentos":
            if len(self.picks) < 2:
                line = self._picked_line(p)
                if line is None:
                    self.ctx.echo("PILAR: designe una cara de muro o una línea.")
                    return
                self.picks.append(line)
            else:
                try:
                    center, values = self._corner_center(self.picks[0], self.picks[1], p)
                    self._place(center, values)
                except ValueError as exc:
                    self.ctx.echo(f"PILAR: {exc}")
                self.picks = []
        else:
            if not self.picks:
                line = self._picked_line(p)
                if line is None:
                    self.ctx.echo("PILAR: designe una cara de muro o una línea.")
                    return
                self.picks.append(line)
            else:
                center, values = self._face_center(self.picks[0], p)
                self._place(center, values)
                self.picks = []
        self._prompt()

    def preview_segments(self, cursor):
        try:
            if self.mode == "libre":
                center, values = self._free_center(cursor)
            elif self.mode == "paramentos" and len(self.picks) == 2:
                center, values = self._corner_center(self.picks[0], self.picks[1], cursor)
            elif self.mode == "paramento" and self.picks:
                center, values = self._face_center(self.picks[0], cursor)
            else:
                return []
            geo = SEC.column_geometry(center, values)
        except (ValueError, ZeroDivisionError):
            return []
        segs = []
        for poly in [geo["footprint"], *geo["sections"]]:
            segs += list(zip(poly, poly[1:] + poly[:1]))
        return segs

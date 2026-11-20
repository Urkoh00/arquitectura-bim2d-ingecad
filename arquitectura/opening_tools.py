# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: CARPINTERIA, PUERTAARQ, VENTANAARQ, HUECOARQ y MOVERCARP: colocar y mover puertas, ventanas
#   y huecos en los muros, con cotas temporales.
#   (Guía del código: docs/GUIA_DEL_CODIGO.md)
"""CARPINTERIA: doors, windows and plain gaps inserted in walls and partitions.

One click on the face of the wall toward which the door swings (the window
opens) places it; the wall is found from the clicked contour line, so any
wall or partition drawn with MURO works. Placement modes:

* ``libre``: the click marks the jamb at the hinge; a second click says to
  which side along the wall it extends and to which face it opens (Intro:
  toward the longer side, opening to the clicked face);
* ``distancia d``: the jamb nearest the clicked end of the clear stretch
  («paramento») at d from its corner;
* ``centrada``: centred on the clicked face's clear stretch;
* ``exterior``: centred on the other face's stretch;
* ``maxima``: as long as the clear stretch (windows and gaps).

The tool keeps going after each insertion (B swaps the hinge and S the
swing of the last one). A click on an existing door/window replaces its
model with the current one, keeping its identity, its centre and, unless
the width was given, its width («sustituir»).
"""
from __future__ import annotations

import copy
import math

from tools.base import Tool

from . import openings as OP
from . import temp_dims as TD
from .architectural import metadata


def _document(ctx):
    from .compat import require_document
    return require_document(ctx)


def _num(text):
    v = float(str(text).strip().replace(",", "."))
    if not math.isfinite(v):
        raise ValueError("medida no finita")
    return v


def analyse(drawing):
    """(walls {id: spec}, uncut plan segments {wall id: [(a, b)]}, records)."""
    from .exchange import read_model
    from .geom import junctions as J
    records, columns, _ops, _issues = read_model(drawing, strict=False)
    from .level_layers import target_available
    records=[(ident,m)for ident,m in records if target_available(drawing,m)]
    columns=[(ident,m)for ident,m in columns if target_available(drawing,m)]
    specs = J.walls_from_records(records)
    from .geom.bands import column_inputs
    result = J.solve(specs, column_inputs(columns))
    segs = {}
    for a, b, ids in J.plan_outline(result):
        for wid in ids:
            segs.setdefault(wid, []).append((a, b))
    return {w.id: w for w in specs}, segs, dict(records)


class CarpinteriaTool(Tool):
    name = "CARPINTERIA"
    entity_picker = True
    kind = "door"

    def start(self):
        self.name = type(self).name
        self.v = self._defaults(self.kind)
        self.mode = "libre"
        self.anchor = "lateral"
        self.distance = 0.10
        self.width_given = False
        self.pending = None
        self.first = None              # libre: (wall entity, spec, s, side, span info)
        self.last = None               # last inserted/modified opening entity
        self._cache = None
        self._ops_cache = None
        self.bim = {}                  # name, type_name, material from the sheet
        self.dim_active = "left"       # temporary dimension a typed number goes to
        self.dim_axis = False          # measure to the jamb (False) or to the centre
        self._hover = None             # last placement under the cursor (temp. dims)
        self.tab_locks = {}            # dimensions fixed with Tab: {"left"|"right"|"width": m}
        self.tab_order = []            # the order they were fixed in
        self._last_cursor = None
        from . import tabulador
        tabulador.install(self.ctx)
        from .double_click import preset
        taken = preset(self.name)
        if taken:
            # a double-click on a carpentry: its model, no sheet (D opens it)
            keys = ("type", "operation", "leaves", "leaf", "leaf2", "width", "height", "sill", "face",
                    "curve_mode", "facet_sagitta", "width_reference", "frame_width", "frame_depth", "setback", "setback_from", "sill_kind", "name", "type_name", "material")
            self.apply_sheet({k: taken[k] for k in keys if k in taken})
            self.ctx.echo(f"{self.name}: con el modelo de {taken.get('name') or 'la carpintería'}.")
        elif not self._sheet(first=True):
            return
        self._prompt()

    def _sheet(self, first=False):
        """The carpentry sheet (as MURO and PILAR have theirs). False when it
        was cancelled at the start: the command ends, as MURO does."""
        from . import bim_dialogs
        try:
            if not bim_dialogs.available(self.ctx):
                return True
            values = bim_dialogs.carpentry_properties(self.ctx, {**self.v, **self.bim})
        except Exception as exc:  # noqa: BLE001  (never lose the command for a Qt problem)
            self.ctx.echo(f"CARPINTERIA: ficha no disponible ({type(exc).__name__}: {exc}); "
                          "use las opciones de la línea de órdenes.")
            return True
        if values is None:
            if first:
                self.ctx.echo("CARPINTERIA: cancelado.")
                self.ctx.finish()
                return False
            return True
        self.apply_sheet(values)
        return True

    def apply_sheet(self, values):
        values = dict(values)
        kind = values.pop("type")
        if kind != self.v["type"]:
            self.v = self._defaults(kind)
            if kind == "door" and self.mode == "maxima":
                self.mode = "libre"
        for k in ("name", "type_name", "material"):
            text = values.pop(k, "")
            if text:
                self.bim[k] = text
            else:
                self.bim.pop(k, None)
        self.v.update({k: v for k, v in values.items() if k not in ("offset",)})
        self.width_given = True

    # --- settings ------------------------------------------------------------
    @staticmethod
    def _defaults(kind):
        v = {"type": kind, **copy.deepcopy(OP.DEFAULTS[kind]), "operation": OP.OPERATIONS[kind][0]}
        if kind == "door":
            v["width"] = OP.door_width(v["leaf"], 1, 0.0, v["frame_width"])
        return v

    def _width(self):
        v = self.v
        if v["type"] == "door" and v.get('curve_mode')!='curva':
            return OP.door_width(v["leaf"], v["leaves"], v.get("leaf2") or 0.0, v["frame_width"])
        return float(v["width"])

    def _summary(self):
        v = self.v
        f = lambda x: f"{float(x):.3f}".rstrip("0").rstrip(".").replace(".", ",")  # noqa: E731
        if v["type"] == "door":
            leaves = "1 hoja" if v["leaves"] == 1 else "2 hojas"
            txt = (f"Puerta {OP.OPERATION_NAMES[v['operation']]} {leaves} de {f(v['leaf'])}"
                   + (f"+{f(v['leaf2'] or v['leaf'])}" if v["leaves"] == 2 else ""))
            txt += f", hueco {f(self._width())} x {f(v['height'])}"
        elif v["type"] == "window":
            txt = (f"Ventana {OP.OPERATION_NAMES[v['operation']]} {v['leaves']} hoja(s) "
                   f"{f(v['width'])} x {f(v['height'])}, "
                   f"antepecho {f(v['sill'])}, {v['sill_kind']}")
        else:
            txt = f"Hueco {f(v['width'])} x {f(v['height'])}"
            if v["sill"]:
                txt += f", antepecho {f(v['sill'])}"
        mode = {"libre": "libre",
                "distancia": f"{'centro' if self.anchor == 'medio' else 'jamba'} a {f(self.distance)} m "
                             "de la esquina",
                "centrada": "centrada en la cara", "centrada_ext": "centrada en la otra cara",
                "maxima": "longitud máxima"}[self.mode]
        return f"{txt}; {mode}; ajuste {({'centrada': 'medio'}).get(v['face'], v['face'])}"

    def _prompt(self):
        if self.first is not None:
            self.prompt("CARPINTERIA: clic hacia donde se extiende y a la cara a la que abre "
                        "(Intro: hacia el lado más largo):")
            return
        ref = "centro" if self.dim_axis else "jamba"
        act = TD.FIELD_NAMES.get(self.dim_active, "izquierda")
        fixed = "".join(f"; {TD.FIELD_NAMES[k]} fijada {TD.fmt(v)}" for k, v in self.tab_locks.items())
        self.prompt(f"CARPINTERIA ({self._summary()}{fixed}): clic en la cara del muro hacia la que abre, "
                    f"o escriba la distancia de la cota activa ({act}, a la {ref}; Tab: siguiente) "
                    "[Puerta/Ventana/Hueco/aNcho/Hojas/Tipo de apertura/aLtura/Antepecho/Modo/"
                    "punto de Inserción/ajuste Cerco/cErco/Remate/Bisagra/Sentido/COta (F6)/EJe (F4)/"
                    "D ficha/Fin]:")

    def on_option(self, text):
        raw = str(text).strip()
        t = raw.lower()
        if self.pending:
            key, self.pending = self.pending, None
            try:
                self._set(key, raw)
            except (ValueError, TypeError) as exc:
                self.ctx.echo(f"CARPINTERIA: {exc}")
            self._prompt()
            return True
        kind = OP.kind_of(t)
        if kind is not None:
            self.v = self._defaults(kind)
            self.width_given = False
            if kind == "door" and self.mode == "maxima":
                self.mode = "libre"
            self._prompt()
            return True
        asks = {"n": ("ancho", "Ancho de hoja (puerta: 62/72/82/92 = hojas de 625/725/825/925 mm) "
                              "o del hueco (ventana, hueco); m o cm:"),
                "t": ("apertura", "Tipo de apertura [Abatible/Corredera/Fija (ventanas)]:"),
                "i": ("insercion", "Punto de inserción [Lateral (jamba)/Medio (centro)]:"),
                "ancho": None,
                "hojas": ("hojas", "Número de hojas (puerta: 1 o 2; 2 0,625 = hoja principal de 0,625):"),
                "l": ("altura", "Altura del hueco (m):"), "altura": None,
                "a": ("antepecho", "Antepecho (m sobre la base del muro):"), "antepecho": None,
                "m": ("modo", "Colocación [Libre/Distancia d/Centrada/Exterior (centrada en la otra cara)/"
                              "Máxima]:"), "modo": None,
                "c": ("cara", "Ajuste del cerco [Interior (plano hacia el que abre)/Medio/Exterior]:"),
                "cara": None,
                "e": ("cerco", "Cerco: ancho de cada jamba y profundidad (m; 0 = automática):"),
                "cerco": None,
                "r": ("remate", "Remate inferior de la ventana [Alféizar/Vierteaguas/venTanal]:"),
                "remate": None}
        for alias, target in (("ancho", "n"), ("altura", "l"), ("antepecho", "a"), ("modo", "m"),
                              ("cara", "c"), ("ajuste", "c"), ("cerco", "e"), ("remate", "r"),
                              ("apertura", "t"), ("insercion", "i")):
            asks[alias] = asks[target]
        if t in asks:
            self.pending = asks[t][0]
            self.prompt("CARPINTERIA: " + asks[t][1])
            return True
        if t in ("b", "bisagra", "s", "sentido"):
            self._flip("hinge" if t[0] == "b" else "side")
            return True
        if t in ("d", "ficha", "dialogo", "diálogo"):
            self._sheet()
            self._prompt()
            return True
        if t in ("f", "fin"):
            self.ctx.finish()
            return True
        if t in ("co", "cota"):
            self._next_dim()
            return True
        if t in ("ej", "eje", "borde", "jamba", "centro"):
            self._toggle_axis()
            return True
        if self._hover is not None:
            try:                                   # a typed distance: the active dimension
                d = TD.parse_length(raw)
            except ValueError:
                d = None
            if d is not None and d <= 30.0:     # larger: a width in cm (82 = hoja de 825)
                if self.tab_locks or self.dim_active == "width":
                    if self._tab_lock(raw):     # the active dimension, then place
                        self._tab_place()
                else:
                    self._place_at_distance(d)
                self._prompt()
                return True
        if self.first is None:
            try:                                   # a bare number: the width
                self._set("ancho", raw)
                self._prompt()
                return True
            except ValueError:
                return False
        return False

    def _set(self, key, raw):
        v = self.v
        t = raw.strip().lower()
        if key == "ancho":
            if v["type"] == "door" and t in OP.DOOR_LEAVES:
                w = OP.DOOR_LEAVES[t]
                if t in OP.COMMERCIAL_LEAVES:
                    self.ctx.echo("CARPINTERIA: hoja de 925 mm: medida comercial, no recogida en la UNE 56803.")
            else:
                w = _num(raw)
                if w > 10:                             # typed in cm
                    w /= 100.0
            if w <= 0:
                raise ValueError("el ancho debe ser positivo")
            if v["type"] == "door" and v.get('curve_mode')!='curva':
                v["leaf"] = w
            else:
                v["width"] = w
            self.width_given = True
        elif key == "hojas":
            parts = raw.replace(";", " ").split()
            n = int(parts[0])
            if v["type"] == "door":
                if n not in (1, 2):
                    raise ValueError("una puerta tiene 1 o 2 hojas")
                v["leaves"] = n
                v["leaf2"] = _num(parts[1]) if n == 2 and len(parts) > 1 else 0.0
                if v["leaf2"]:
                    v["leaf"], v["leaf2"] = v["leaf2"], v["leaf"]     # given = main leaf
            elif v["type"] == "window":
                if n < 1:
                    raise ValueError("al menos una hoja")
                v["leaves"] = n
        elif key == "altura":
            h = _num(raw)
            if h <= 0:
                raise ValueError("la altura debe ser positiva")
            v["height"] = h
        elif key == "antepecho":
            a = _num(raw)
            if a < 0:
                raise ValueError("antepecho negativo")
            v["sill"] = a
        elif key == "modo":
            word = t.split()[0] if t else "l"
            if word.startswith("d"):
                parts = t.split()
                if len(parts) > 1:
                    self.distance = _num(parts[1])
                self.mode = "distancia"
            elif word.startswith("c"):
                self.mode = "centrada"
            elif word.startswith("e"):
                self.mode = "centrada_ext"
            elif word.startswith("m"):
                if v["type"] == "door":
                    raise ValueError("longitud máxima: solo ventanas y huecos")
                self.mode = "maxima"
            else:
                self.mode = "libre"
        elif key == "cara" and t.startswith("distancia"):
            parts = t.split()
            if len(parts) != 3 or parts[1] not in ("interior", "exterior"):
                raise ValueError("Use: distancia interior|exterior retranqueo_en_metros")
            distance = _num(parts[2])
            if distance < 0:
                raise ValueError("Retranqueo negativo")
            v.update(face="distancia", setback_from=parts[1], setback=distance)
        elif key == "cara":
            v["face"] = {"i": "interior", "c": "centrada", "m": "centrada",
                         "e": "exterior"}.get(t[:1], v["face"])
        elif key == "apertura":
            op = {"a": "SWINGING" if v["type"] == "door" else "SIDEHUNG", "c": "SLIDING",
                  "f": "FIXED"}.get(t[:1])
            if op not in OP.OPERATIONS[v["type"]]:
                raise ValueError("tipo de apertura no disponible para " + OP.NAMES[v["type"]].lower())
            v["operation"] = op
            if op == "FIXED":
                v["leaves"] = 1
        elif key == "insercion":
            self.anchor = "medio" if t.startswith("m") else "lateral"
        elif key == "cerco":
            parts = [_num(x) for x in raw.replace(";", " ").split()]
            if parts:
                v["frame_width"] = max(0.0, parts[0])
            if len(parts) > 1:
                v["frame_depth"] = max(0.0, parts[1])
        elif key == "remate":
            v["sill_kind"] = ("ventanal" if t.startswith("vent") or t.startswith("t") else
                              "vierteaguas" if t.startswith("v") else "alfeizar")
            if v["sill_kind"] == "ventanal":
                v["sill"] = 0.0

    def _flip(self, key):
        e = self.last
        if e is None or not e.is_alive or (metadata(e) or {}).get("kind") != "opening":
            self.ctx.echo("CARPINTERIA: aún no hay una carpintería que girar.")
            return
        m = metadata(e)
        changes = {key: (1 - int(m.get("hinge") or 0)) if key == "hinge" else -int(m.get("side") or 1)}
        self._edit(e, changes, "bisagra cambiada" if key == "hinge" else "sentido de apertura cambiado")
        self._prompt()

    # --- geometry ---------------------------------------------------------------
    def _model(self):
        document=_document(self.ctx)
        revision=getattr(document,'revision',0)
        if self._cache is None or getattr(self,'_cache_revision',None)!=revision:
            self._cache = analyse(document.doc)
            self._cache_revision=revision
        return self._cache

    def _wall_at(self, p, tol=0.05):
        """The wall whose face was clicked. The pick may land on another
        entity drawn on that face (a room outline, a dimension): then the
        wall is found geometrically, the nearest face within ``tol``."""
        from .wall_tools import wall_from_pick
        specs, _segs, _recs = self._model()
        wall, _line = wall_from_pick(self.ctx, p)
        if wall is not None and metadata(wall)["id"] in specs:
            return wall, specs[metadata(wall)["id"]]
        best = None
        for w in specs.values():
            s, off = w.local(p)
            if not -tol <= s <= w.length + tol:
                continue
            d = 0.0 if w.lo <= off <= w.hi else min(abs(off - w.lo), abs(off - w.hi))
            if d <= tol and (best is None or d < best[0]):
                best = (d, w)
        if best is None:
            return None, None
        for e in _document(self.ctx).doc.modelspace():
            m = metadata(e) or {}
            if m.get("kind") == "wall" and m.get("id") == best[1].id and e.dxftype() == "LWPOLYLINE":
                return e, best[1]
        return None, None

    def _solve(self, spec, s, side, toward=None):
        """(s0, hinge, width) or raise ValueError."""
        specs, segs, _recs = self._model()
        span, other, usable = OP.free_span(spec, segs.get(spec.id, []), s, side)
        if usable is None:
            raise ValueError("no se encuentra la cara libre del muro")
        width = OP.span_of(spec, self._width(), self.v, side)       # along the wall (a curved one: its arc)
        if self.mode == "libre":
            if toward is None:
                toward = 1 if usable[1] - s >= s - usable[0] else -1
            s0, hinge = (s, 0) if toward > 0 else (s - width, 1)
        else:
            s0, hinge, width = OP.place(self.mode, width, s, span, usable, self.distance, other,
                                        self.anchor)
        if width <= 1e-6:
            raise ValueError("no queda paramento libre")
        if s0 < usable[0] - 1e-6 or s0 + width > usable[1] + 1e-6:
            raise ValueError(f"no cabe: el paramento libre mide {usable[1] - usable[0]:.3f} m "
                             f"y el hueco {width:.3f} m".replace(".", ","))
        return s0, hinge, width

    def _record(self, spec, s0, hinge, width, side):
        v = dict(self.v)
        v.update(offset=s0, width=width, hinge=hinge, side=side)
        if v["type"] == "door" and self.mode == "maxima":
            v["leaf"] = OP.chord_of(spec, width) - 2 * v["frame_width"]
        return v

    # --- actions -------------------------------------------------------------------
    def _create(self, wall, spec, s0, hinge, width, side):
        from .architectural_v10 import create_opening
        from .transactions import apply_architectural_change
        v = self._record(spec, s0, hinge, width, side)
        extra = {k: v[k] for k in OP.V3_KEYS if k in v}
        extra.update(getattr(self, "bim", {}))
        cmd = create_opening(wall, s0, width, v["sill"], v["height"], kind=v["type"], **extra)
        apply_architectural_change(self.ctx, cmd, kind="opening")
        self.last = getattr(cmd, "entity", None)
        self._cache = None
        self._ops_cache = None
        if v["type"] == "door" and self.last is not None and v.get("curve_mode")!="curva":
            rec = metadata(self.last) or {}
            frame, opened = OP.clear_width(rec)
            ok = OP.sua_accessible(rec)
            self.ctx.echo((f"CARPINTERIA: paso libre {frame:.3f} m en el marco y {opened:.3f} m abierta: "
                           + ("válida" if ok else "NO válida")
                           + " para itinerario accesible (DB-SUA: 0,80 y 0,78 m; depende del cerco real).")
                          .replace(".", ",", 2))
        what = {"door": "puerta insertada", "window": "ventana insertada", "gap": "hueco abierto"}[v["type"]]
        real = OP.chord_of(spec, width)
        self.ctx.echo(f"CARPINTERIA: {what} en el muro "
                      f"({real:.3f} m a {s0:.3f} m de su inicio".replace(".", ",", 2)
                      + (", curva sobre el arco)." if spec.curved and v.get("curve_mode")=="curva" else (", plana sobre la cuerda del muro curvo)." if spec.curved else ").")))

    def _edit(self, entity, changes, what):
        from .architectural_v10 import edit_opening
        from .transactions import apply_architectural_change
        try:
            cmd = edit_opening(entity, **changes)
            apply_architectural_change(self.ctx, cmd, kind="opening")
            self.last = entity
            self._cache = None
            self._ops_cache = None
            self.ctx.echo(f"CARPINTERIA: {what}.")
        except Exception as exc:  # noqa: BLE001
            self.ctx.echo(f"CARPINTERIA: {exc}")

    def _replace(self, entity):
        """Current model on an existing opening: same identity and centre."""
        m = metadata(entity)
        spec = self._model()[0].get(m.get("wall_id"))
        width = (OP.span_of(spec, self._width(), self.v, m.get("side",1)) if spec is not None else self._width()) \
            if (self.width_given or m.get("type") != self.v["type"]) else float(m["width"])
        centre = float(m["offset"]) + float(m["width"]) / 2
        changes = {k: self.v[k] for k in OP.V3_KEYS if k in self.v and k not in ("side", "hinge")}
        changes.update(type=self.v["type"], offset=centre - width / 2, width=width,
                       sill=self.v["sill"], height=self.v["height"])
        if self.v["type"] == "door" and not (self.width_given or m.get("type") != "door"):
            changes.pop("leaf", None)
        self._edit(entity, changes, "modelo sustituido (misma identidad)")

    def _picked_opening(self, p):
        from .arq_properties import resolve_arch_entity
        services = getattr(self.ctx, "services", None)
        picked = services.pick_entity(p) if services else None
        if picked is None:
            return None
        ent, _ = resolve_arch_entity(_document(self.ctx), picked)
        return ent if ent is not None and (metadata(ent) or {}).get("kind") == "opening" else None

    # --- temporary dimensions ---------------------------------------------------------
    def _openings(self):
        if self._ops_cache is None:
            from .exchange import read_model
            _w, _c, ops, _i = read_model(_document(self.ctx).doc, strict=False)
            self._ops_cache = ops
        return self._ops_cache

    def _placement(self, cursor):
        """(wall, spec, side, s0, hinge, width, left, right) under the cursor,
        or None: the same solution the click would give."""
        if self.first is not None:
            wall, spec, s, side = self.first
            sq, oq = spec.local(cursor)
            side = 1 if oq >= (spec.lo + spec.hi) / 2 else -1
            s0, hinge, width = self._solve(spec, s, side, 1 if sq >= s else -1)
        else:
            wall, spec = self._wall_at(cursor)
            if spec is None:
                return None
            s, off = spec.local(cursor)
            side = 1 if off >= (spec.lo + spec.hi) / 2 else -1
            s0, hinge, width = self._solve(spec, s, side)
        _specs, segs, _r = self._model()
        _span, _other, usable = OP.free_span(spec, segs.get(spec.id, []), s0 + width / 2, side)
        if usable is None:
            return None
        left, right = TD.references(usable, TD.opening_jambs(self._openings(), spec.id), s0, s0 + width)
        return wall, spec, side, s0, hinge, width, left, right

    def _hover_dims(self, cursor):
        try:
            hit = self._placement(cursor)
        except Exception:  # noqa: BLE001
            hit = None
        self._hover = hit
        if hit is None:
            return []
        _w, spec, side, s0, _h, width, left, right = hit
        if self.tab_locks:
            try:
                _w, spec, side, s0, _h, width = self._locked(hit)
            except ValueError:
                pass                       # shown where the cursor is; Enter reports why
        return TD.carpentry_dims(spec, side, s0, width, left, right, TD.world_per_px(self.ctx),
                                 self.dim_active, self.dim_axis, tuple(self.tab_locks))

    # --- Tab: fix the dimensions one by one ---------------------------------------------
    def tab_ready(self):
        return self.pending is None and self.first is None

    def _hole_width(self, width, spec, side):
        """Make the current model ``width`` wide along the wall (what the
        width dimension shows), as typing its aNcho would."""
        v = self.v
        target = float(width)
        if spec is not None and getattr(spec, "curved", False):
            lo, hi = 1e-6, 2 * target + 1.0
            for _ in range(60):                 # span_of grows with the chord
                mid = (lo + hi) / 2
                try:
                    over = OP.span_of(spec, mid, v, side) > target
                except ValueError:
                    over = True
                lo, hi = (lo, mid) if over else (mid, hi)
            chord = (lo + hi) / 2
        else:
            chord = target
        if v["type"] == "door" and v.get("curve_mode") != "curva":
            clear = chord - 2 * float(v["frame_width"])
            if int(v["leaves"]) >= 2:
                second = float(v.get("leaf2") or 0.0)
                leaf = clear - second if second else clear / 2
            else:
                leaf = clear
            if leaf <= 0.05:
                raise ValueError(f"un hueco de {TD.fmt(width)} m no deja sitio para la hoja")
            v["leaf"] = leaf
        else:
            v["width"] = chord
        self.width_given = True

    def _tab_lock(self, text):
        """Fix the active dimension to ``text``. False if not valid."""
        field = self.dim_active
        try:
            value = TD.parse_length(text)
            if field == "width":
                if value <= 1e-6:
                    raise ValueError("el ancho debe ser positivo")
                spec = side = None
                if self._hover is not None:
                    spec, side = self._hover[1], self._hover[2]
                self._hole_width(value, spec, side or 1)
        except ValueError as exc:
            self.ctx.echo(f"CARPINTERIA: {TD.FIELD_NAMES[field]}: {exc}")
            return False
        locks, order = self.tab_locks, self.tab_order
        if field in order:
            order.remove(field)
        order.append(field)
        locks[field] = value
        sides = [k for k in order if k in ("left", "right")]
        if self.dim_axis and len(sides) == 2:          # to the centre, one side is enough
            locks.pop(sides[0]); order.remove(sides[0])
        elif len(sides) == 2 and "width" in locks:      # left and right give the width
            older = next(k for k in order if k in locks)
            locks.pop(older); order.remove(older)
        return True

    def on_tab(self, text="", backwards=False):
        """Tab: fix the active dimension to the typed value (if any) and go
        to the next one: left, right, width (Shift+Tab: back)."""
        if str(text).strip():
            done = self.dim_active
            if not self._tab_lock(text):
                return
            self.dim_active = TD.next_field(TD.CARPENTRY_FIELDS, done, backwards)
            self.ctx.echo(f"CARPINTERIA: {TD.FIELD_NAMES[done]} fijada en {TD.fmt(self.tab_locks[done])} m; "
                          f"cota activa: {TD.FIELD_NAMES[self.dim_active]} (Intro coloca).")
        else:
            self.dim_active = TD.next_field(TD.CARPENTRY_FIELDS, self.dim_active, backwards)
            self.ctx.echo(f"CARPINTERIA: cota activa: {TD.FIELD_NAMES[self.dim_active]}.")
        self._prompt()

    def _locked(self, hit):
        """(wall, spec, side, s0, hinge, width) of the placement under the
        cursor with the fixed dimensions applied; ValueError if they do not fit."""
        wall, spec, side, s0, hinge, width, left, right = hit
        lk = self.tab_locks
        L, R = lk.get("left"), lk.get("right")
        if L is not None and R is not None and not self.dim_axis:
            s0, width, hinge = left + L, (right - R) - (left + L), 0
            if width <= 1e-6:
                raise ValueError(f"con {TD.fmt(L)} y {TD.fmt(R)} m a las referencias no queda hueco "
                                 f"(entre ellas hay {TD.fmt(right - left)} m)")
        elif L is not None:
            s0, hinge = TD.placement_from_distance("left", L, left, right, width, self.dim_axis), 0
        elif R is not None:
            s0, hinge = TD.placement_from_distance("right", R, left, right, width, self.dim_axis), 1
        elif s0 < left - 1e-6 or s0 + width > right + 1e-6:
            raise ValueError(f"no cabe: entre las referencias quedan {TD.fmt(right - left)} m")
        return wall, spec, side, s0, hinge, width

    def _tab_place(self, cursor=None):
        """Place the opening with the fixed dimensions on the wall under the
        cursor. True if something was placed."""
        cursor = cursor if cursor is not None else self._last_cursor
        hit = self._placement(cursor) if cursor is not None else self._hover
        if hit is None:
            self.ctx.echo("CARPINTERIA: lleve el cursor a la cara del muro donde va la carpintería.")
            return False
        try:
            wall, spec, side, s0, hinge, width = self._locked(hit)
            lk = self.tab_locks
            if "left" in lk and "right" in lk and not self.dim_axis:
                self._hole_width(width, spec, side)      # the width they give stays as the model's
                width = OP.span_of(spec, self._width(), self.v, side)
            self._create(wall, spec, s0, hinge, width, side)
        except ValueError as exc:
            self.ctx.echo(f"CARPINTERIA: {exc}")
            return False
        self.tab_locks, self.tab_order = {}, []
        self._hover = None
        self._ops_cache = None
        return True

    def preview_entities(self, cursor):
        """IngeCAD 0.8: the temporary dimensions, rendered with real text."""
        self._last_cursor = cursor
        try:
            dims = self._hover_dims(cursor)
            return TD.entities(_document(self.ctx).doc, dims, TD.world_per_px(self.ctx)) if dims else []
        except Exception:  # noqa: BLE001
            return []

    def _next_dim(self):
        self.dim_active = "right" if self.dim_active == "left" else "left"
        self._prompt()

    def _toggle_axis(self):
        self.dim_axis = not self.dim_axis
        self.ctx.echo("CARPINTERIA: las cotas miden a " + ("su centro." if self.dim_axis else "sus jambas."))
        self._prompt()

    def on_key(self, key):
        """F6: next temporary dimension; F4: jamb or centre (IngeCAD 0.8)."""
        if key == "F6":
            self._next_dim()
            return True
        if key == "F4":
            self._toggle_axis()
            return True
        return False

    def _place_at_distance(self, distance):
        """Typed number with the cursor on a wall: the opening at that
        distance from the active reference (as the temporary dimension shows)."""
        if self._hover is None:
            return
        wall, spec, side, s0, _h, width, left, right = self._hover
        try:
            s0 = TD.placement_from_distance(self.dim_active, distance, left, right, width, self.dim_axis)
        except ValueError as exc:
            self.ctx.echo(f"CARPINTERIA: {exc}")
            return
        self.first = None
        hinge = 0 if self.dim_active == "left" else 1
        try:
            self._create(wall, spec, s0, hinge, width, side)
        except ValueError as exc:
            # lo mismo que con un clic: se informa y la orden sigue (v1.29)
            self.ctx.echo(f"CARPINTERIA: {exc}")
            return
        self._hover = None
        self._ops_cache = None

    def on_point(self, p):
        p = (float(p[0]), float(p[1]))
        self._ops_cache = None
        if self.tab_locks and self.first is None and self.pending is None:
            try:
                self._tab_place(p)               # a click with fixed dimensions
            finally:
                self._prompt()
            return
        try:
            if self.first is not None:
                wall, spec, s, side = self.first
                self.first = None
                sq, oq = spec.local(p)
                toward = 1 if sq >= s else -1
                side = 1 if oq >= (spec.lo + spec.hi) / 2 else -1
                s0, hinge, width = self._solve(spec, s, side, toward)
                self._create(wall, spec, s0, hinge, width, side)
                return
            existing = self._picked_opening(p)
            if existing is not None:
                self._replace(existing)
                return
            wall, spec = self._wall_at(p)
            if wall is None or spec is None:
                self.ctx.echo("CARPINTERIA: designe la cara de un muro o tabique (o una carpintería "
                              "para sustituir su modelo).")
                return
            s, off = spec.local(p)
            side = 1 if off >= (spec.lo + spec.hi) / 2 else -1
            if self.mode == "libre":
                self._solve(spec, s, side)             # fits at least one way?
                self.first = (wall, spec, s, side)
                return
            s0, hinge, width = self._solve(spec, s, side)
            self._create(wall, spec, s0, hinge, width, side)
        except ValueError as exc:
            self.ctx.echo(f"CARPINTERIA: {exc}")
        except Exception as exc:  # noqa: BLE001
            self.ctx.echo(f"CARPINTERIA: {type(exc).__name__}: {exc}")
        finally:
            self._prompt()

    def on_enter(self):
        if self.pending:
            self.pending = None
            self._prompt()
            return
        if self.tab_locks and self.first is None:
            self._tab_place()
            self._prompt()
            return
        if self.first is not None:
            wall, spec, s, side = self.first
            self.first = None
            try:
                s0, hinge, width = self._solve(spec, s, side)
                self._create(wall, spec, s0, hinge, width, side)
            except ValueError as exc:
                self.ctx.echo(f"CARPINTERIA: {exc}")
            self._prompt()
            return
        self.ctx.finish()

    def on_cancel(self):
        self.first = None
        self.pending = None
        self.tab_locks, self.tab_order = {}, []

    def preview_segments(self, cursor):
        try:
            hit = self._placement(cursor) if (self.tab_locks and self.first is None) else None
            if hit is not None:
                wall, spec, side, s0, hinge, width = self._locked(hit)
            elif self.first is not None:
                wall, spec, s, side = self.first
                sq, oq = spec.local(cursor)
                side = 1 if oq >= (spec.lo + spec.hi) / 2 else -1
                s0, hinge, width = self._solve(spec, s, side, 1 if sq >= s else -1)
            else:
                wall, spec = self._wall_at(cursor)
                if spec is None:
                    return []
                s, off = spec.local(cursor)
                side = 1 if off >= (spec.lo + spec.hi) / 2 else -1
                s0, hinge, width = self._solve(spec, s, side)
        except Exception:  # noqa: BLE001
            return []
        rec = OP.normalise({"kind": "opening", "id": "", **self._record(spec, s0, hinge, width, side)})
        segs = []
        poly = OP.cut_polygon(spec, rec, 0.0)
        segs += list(zip(poly, poly[1:] + poly[:1]))
        for item in OP.plan_symbol(spec, rec):
            if item[0] == "line":
                segs.append((item[1], item[2]))
            elif item[0] == "poly":
                pts = item[1]
                segs += list(zip(pts, pts[1:] + (pts[:1] if item[2] else [])))
            else:
                c, r, a0, a1 = item[1:]
                if a1 < a0:
                    a1 += 360.0
                n = 12
                pts = [(c[0] + r * math.cos(math.radians(a0 + (a1 - a0) * k / n)),
                        c[1] + r * math.sin(math.radians(a0 + (a1 - a0) * k / n))) for k in range(n + 1)]
                segs += list(zip(pts, pts[1:]))
        if not _HOST_ENTITY_PREVIEW:
            segs += TD.segments(self._hover_dims(cursor), TD.world_per_px(self.ctx))
        return segs


#: IngeCAD 0.8 renders Tool.preview_entities (real text); older hosts only
#: draw the preview segments, so the dimension lines go there.
_HOST_ENTITY_PREVIEW = hasattr(Tool, "preview_entities")


class PuertaTool(CarpinteriaTool):
    name = "PUERTAARQ"
    kind = "door"


class VentanaTool(CarpinteriaTool):
    name = "VENTANAARQ"
    kind = "window"


class HuecoTool(CarpinteriaTool):
    name = "HUECOARQ"
    kind = "gap"


class MoverCarpinteriaTool(Tool):
    """MOVERCARP: move a placed door, window or gap with its temporary
    dimensions, as the usual BIM programs do when it is selected: designate
    it, read the distances to the nearest references on its wall, type the
    one wanted (F6 / «cota» switches the active one, F4 / «eje» measures to
    its centre) or click on its wall to bring its centre there. Same identity,
    host and model; one Undo per move."""
    name = "MOVERCARP"
    entity_picker = True

    def start(self):
        self.entity = None
        self.dim_active = "left"
        self.dim_axis = False
        from . import tabulador
        tabulador.install(self.ctx)
        self._prompt()

    def tab_ready(self):
        return self.entity is not None

    def on_tab(self, text="", backwards=False):
        """Tab: a typed distance moves it from the active reference; then
        the other reference becomes active."""
        if str(text).strip():
            try:
                d = TD.parse_length(text)
                _spec, _side, _s0, width, left, right = self._state()
                self._move_to(TD.placement_from_distance(self.dim_active, d, left, right, width,
                                                         self.dim_axis))
            except ValueError as exc:
                self.ctx.echo(f"MOVERCARP: {exc}")
                self._prompt()
                return
        self.dim_active = TD.next_field(TD.CARPENTRY_FIELDS[:2], self.dim_active, backwards)
        self._prompt()

    def _prompt(self):
        if self.entity is None:
            self.prompt("MOVERCARP: designe una puerta, ventana o hueco:")
            return
        ref = "centro" if self.dim_axis else "jamba"
        act = "izquierda" if self.dim_active == "left" else "derecha"
        self.prompt(f"MOVERCARP: distancia de la cota activa ({act}, a la {ref}; Tab: la otra) "
                    "o clic en el muro [COta (F6)/EJe (F4)/Otra/Fin]:")

    def _state(self):
        """(spec, side, s0, width, left, right) of the designated opening."""
        from .exchange import read_model
        m = metadata(self.entity) or {}
        specs, segs, _r = analyse(_document(self.ctx).doc)
        spec = specs.get(m.get("wall_id"))
        if spec is None:
            raise ValueError("su muro anfitrión no está en el dibujo")
        s0, width = float(m["offset"]), float(m["width"])
        side = 1 if int(m.get("side") or 1) > 0 else -1
        _span, _o, usable = OP.free_span(spec, segs.get(spec.id, []), s0 + width / 2, side)
        if usable is None:
            raise ValueError("no se encuentra el paramento libre del muro")
        _w, _c, ops, _i = read_model(_document(self.ctx).doc, strict=False)
        left, right = TD.references(usable, TD.opening_jambs(ops, spec.id, exclude=m.get("id")),
                                    s0, s0 + width)
        return spec, side, s0, width, left, right

    def _dims(self):
        if self.entity is None or not self.entity.is_alive:
            return []
        try:
            spec, side, s0, width, left, right = self._state()
        except Exception:  # noqa: BLE001
            return []
        return TD.carpentry_dims(spec, side, s0, width, left, right, TD.world_per_px(self.ctx),
                                 self.dim_active, self.dim_axis)

    def preview_entities(self, cursor):
        try:
            dims = self._dims()
            return TD.entities(_document(self.ctx).doc, dims, TD.world_per_px(self.ctx)) if dims else []
        except Exception:  # noqa: BLE001
            return []

    def preview_segments(self, cursor):
        if _HOST_ENTITY_PREVIEW:
            return []
        return TD.segments(self._dims(), TD.world_per_px(self.ctx))

    def _move_to(self, s0):
        from .architectural_v10 import edit_opening
        from .transactions import apply_architectural_change
        cmd = edit_opening(self.entity, offset=s0)
        apply_architectural_change(self.ctx, cmd, kind="opening")
        self.ctx.echo(f"MOVERCARP: desplazada; su jamba queda a {TD.fmt(s0)} m del inicio del muro.")

    def on_point(self, p):
        p = (float(p[0]), float(p[1]))
        try:
            if self.entity is None:
                from .arq_properties import resolve_arch_entity
                services = getattr(self.ctx, "services", None)
                picked = services.pick_entity(p) if services else None
                ent = resolve_arch_entity(_document(self.ctx), picked)[0] if picked is not None else None
                if ent is None or (metadata(ent) or {}).get("kind") != "opening":
                    self.ctx.echo("MOVERCARP: eso no es una puerta, ventana ni hueco.")
                    return
                self.entity = ent
                self._state()
                return
            spec, side, s0, width, left, right = self._state()
            s, _off = spec.local(p)
            new = s - width / 2.0
            if new < left - 1e-6 or new + width > right + 1e-6:
                raise ValueError(f"no cabe ahí: entre las referencias quedan {TD.fmt(right - left)} m "
                                 f"y el hueco mide {TD.fmt(width)} m")
            self._move_to(new)
        except ValueError as exc:
            self.ctx.echo(f"MOVERCARP: {exc}")
            if self.entity is not None and not self.entity.is_alive:
                self.entity = None
        finally:
            self._prompt()

    def on_option(self, text):
        raw = str(text).strip()
        t = raw.lower()
        if t in ("f", "fin"):
            self.ctx.finish()
            return True
        if t in ("o", "otra"):
            self.entity = None
            self._prompt()
            return True
        if t in ("co", "cota"):
            self.on_key("F6")
            return True
        if t in ("ej", "eje", "borde", "jamba", "centro"):
            self.on_key("F4")
            return True
        if self.entity is None:
            return False
        try:
            d = TD.parse_length(raw)
            spec, side, s0, width, left, right = self._state()
            self._move_to(TD.placement_from_distance(self.dim_active, d, left, right, width, self.dim_axis))
        except ValueError as exc:
            self.ctx.echo(f"MOVERCARP: {exc}")
        self._prompt()
        return True

    def on_key(self, key):
        if key == "F6":
            self.dim_active = "right" if self.dim_active == "left" else "left"
        elif key == "F4":
            self.dim_axis = not self.dim_axis
        else:
            return False
        self._prompt()
        return True

    def on_enter(self):
        if self.entity is not None:
            self.entity = None
            self._prompt()
            return
        self.ctx.finish()

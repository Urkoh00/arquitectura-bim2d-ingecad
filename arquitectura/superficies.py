# SPDX-License-Identifier: GPL-3.0-or-later
"""Useful floor area («superficie útil») of a room by a regulatory criterion.

The geometric room (``geom.spaces``) is the free floor between the faces of
walls and columns: it is what the 3D space and the IFC use, coplanar with
the elements around it. The USEFUL area applies a criterion on top of it.

Criterion ``extremadura_2019`` (Decreto 10/2019 de la Junta de Extremadura,
art. 2.3 y 2.4):

* useful area: closed by the inner face of the enclosures; deducted:
  partitions and other interior dividing elements, doors included (the room
  stops at the faces of its walls, so a door's threshold never counts);
  any vertical structural element, duct or conduit whose horizontal
  section exceeds 100 cm² (smaller ones are NOT deducted: they are given
  back to the room); floor with a free height under 1,50 m; the interior
  staircase (not modelled yet);
* half of the floor of covered private exterior spaces (terraces,
  galleries, balconies, drying areas, porches) at least 50 cm deep;
* useful habitable area: the useful area with the minimum free height the
  decree requires (``habitable_height``; the figure is in its annex and
  is a setting here, to be checked against the text in force).
"""
from __future__ import annotations

CRITERIA = {
    "extremadura_2019": {
        "label": "Decreto 10/2019 de Extremadura, art. 2.3",
        "max_section_kept": 0.0100,     # m²: up to 100 cm² is not deducted
        "min_free_height": 1.50,        # m: lower floor is not useful area
        "exterior_factor": 0.50,        # covered private exterior spaces
        "exterior_min_depth": 0.50,     # m
        # Anexo I, apartado 2, 2.1.B (DOE 18/02/2019, checked by the user on
        # 07/11/2026): 2,50 m; drops to 2,20 m on up to 40 % of each room
        # (not modelled: one height per room); 100 % at 2,20 m in baños,
        # aseos, vestíbulos y pasillos.
        "habitable_height": 2.50,
        "low_rooms_height": 2.20,
        "low_rooms": ("baño", "bano", "aseo", "vestíbulo", "vestibulo", "pasillo", "distribuidor"),
    },
}
DEFAULT = "extremadura_2019"
ENCLOSURES = ("interior", "exterior_cubierto")


def criterion(name=None):
    return CRITERIA.get(name or DEFAULT, CRITERIA[DEFAULT])


def small_columns(columns, crit=None):
    """Ids of columns whose plan section does not exceed the kept limit."""
    from .geom import polygon as P
    c = criterion(crit)
    out = set()
    for cid, m in columns:
        try:
            if abs(P.area([tuple(map(float, q[:2])) for q in m["polygon"]])) <= c["max_section_kept"] + 1e-12:
                out.add(cid)
        except Exception:  # noqa: BLE001
            pass
    return out


def useful_result(specs, columns, crit=None):
    """The junction solution without the columns that are not deducted
    (or None when there is none: then it is the ordinary solution)."""
    from .geom import junctions as J
    small = small_columns(columns, crit)
    if not small:
        return None
    return J.solve(specs, [(cid, m["polygon"]) for cid, m in columns if cid not in small])


def depth(room):
    """Shortest side of the minimum-area rectangle around the room (its
    outer outline; one side of that rectangle lies on a convex hull edge).
    Pure Python: IngeCAD does not ship shapely."""
    import math
    pts = _hull([tuple(map(float, q[:2])) for q in room["outer"]])
    if len(pts) < 3:
        return 0.0
    best = None
    for i in range(len(pts)):
        (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % len(pts)]
        ln = math.hypot(x1 - x0, y1 - y0)
        if ln < 1e-12:
            continue
        ux, uy = (x1 - x0) / ln, (y1 - y0) / ln
        us = [x * ux + y * uy for x, y in pts]
        ns = [-x * uy + y * ux for x, y in pts]
        a, b = max(us) - min(us), max(ns) - min(ns)
        if best is None or a * b < best[0] - 1e-15:
            best = (a * b, min(a, b))
    return best[1] if best else 0.0


def _hull(pts):
    """Convex hull, counter-clockwise (monotone chain)."""
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def evaluate(meta, room, room_useful=None, crit=None, by_use=None):
    """{'useful': m², 'factor': coefficient, 'computable': m², 'habitable': bool,
    'notes': [..]} for a room (``room_useful``: the same room solved without
    the columns that are not deducted)."""
    c = criterion(crit)
    useful = float((room_useful or room)["area"])
    height = float(meta.get("height") or 0.0)
    notes = []
    enclosure = meta.get("enclosure") or "interior"
    factor = 1.0
    if height < c["min_free_height"]:
        factor = 0.0
        notes.append(f"altura libre menor de {c['min_free_height']:.2f} m: no computa".replace(".", ","))
    elif enclosure == "exterior_cubierto":
        if depth(room) + 1e-9 >= c["exterior_min_depth"]:
            factor = c["exterior_factor"]
            notes.append("espacio exterior cubierto: computa el 50 %")
        else:
            factor = 0.0
            notes.append(f"espacio exterior de menos de {c['exterior_min_depth']:.2f} m de fondo: "
                         "no computa".replace(".", ",", 1))
    if room_useful is not None and abs(useful - float(room["area"])) > 1e-9:
        notes.append("pilares o conductos de hasta 100 cm² no descontados")
    # what kind of room it is (bathroom, corridor... need less height): by its
    # «Uso» when the drawing works with uses (general options), by its name
    # otherwise; the free name never changes a room that has a use
    use, name = (meta.get('use') or '').strip(), (meta.get('name') or '').strip()
    if by_use is None:
        words = f"{name} {use}"
    elif by_use:
        words = use or name
        if not use:
            notes.append("sin uso asignado: se clasifica por el nombre")
    else:
        words = name
    low_room = any(k in words.lower() for k in c.get("low_rooms", ()))
    needed = c["low_rooms_height"] if low_room else c["habitable_height"]
    if enclosure == "interior" and factor > 0 and height + 1e-9 < needed:
        notes.append(f"altura libre por debajo de {needed:.2f} m: no es superficie útil habitable".replace(".", ","))
    return {"useful": useful, "factor": factor, "computable": useful * factor,
            "habitable": enclosure == "interior" and factor > 0 and height + 1e-9 >= needed,
            "notes": notes, "criterion": c["label"]}


def table(drawing, crit=None):
    """Rows and totals of the drawing's rooms (for SUPERFICIES and the export)."""
    from .exchange import read_model, read_spaces
    from .geom import junctions as J
    from .geom import spaces as SP
    records, columns, _ops, _issues = read_model(drawing, strict=False)
    specs = J.walls_from_records(records)
    result = J.solve(specs, [(cid, m["polygon"]) for cid, m in columns])
    res_u = useful_result(specs, columns, crit)
    from .parameters_arq import general_options
    by_use = general_options(drawing)["usar_usos"]
    rows, totals = [], {"useful_interior": 0.0, "exterior_computable": 0.0, "computable": 0.0,
                        "habitable": 0.0}
    for _ident, m, _e in read_spaces(drawing):
        room, _why = SP.space_at(result, m["seed"])
        if room is None:
            rows.append({"name": m.get("name") or "Recinto", "error": "no está cerrado"})
            continue
        room_u = SP.space_at(res_u, m["seed"])[0] if res_u is not None else None
        ev = evaluate(m, room, room_u, crit, by_use=by_use)
        rows.append({"name": m.get("name") or "Recinto", "use": m.get("use") or "",
                     "enclosure": m.get("enclosure") or "interior", "height": float(m.get("height") or 0),
                     "net": room["area"], **ev})
        if (m.get("enclosure") or "interior") == "interior":
            totals["useful_interior"] += ev["computable"]
        else:
            totals["exterior_computable"] += ev["computable"]
        totals["computable"] += ev["computable"]
        if ev["habitable"]:
            totals["habitable"] += ev["computable"]
    return rows, totals


def _m2(v):
    return f"{v:.2f}".replace(".", ",")


def superficies(ctx, *args):
    """The schedule in the command line only (kept for scripts and tests)."""
    return report(ctx)


# --- the schedule drawn in the plan -------------------------------------------------

TABLE_LAYER = "ARQ-CUADROS"
TABLE_KIND = "area_table"
COLUMNS = (("Nº", 2), ("Recinto", 10), ("Uso", 6), ("Sup. útil (m²)", 8), ("Coef.", 4),
           ("Computable (m²)", 8), ("Altura (m)", 6), ("Habitable", 6))


def table_cells(rows, totals):
    """The schedule as text rows (header first) and its total rows."""
    body = []
    n = 0
    for r in rows:
        n += 1
        if "error" in r:
            body.append([str(n), r["name"], "", "no cerrado", "", "", "", ""])
            continue
        body.append([str(n), r["name"], r.get("use") or "", _m2(r["useful"]), f"{r['factor']:g}".replace(".", ","),
                     _m2(r["computable"]), _m2(r["height"]), "Sí" if r["habitable"] else "No"])
    foot = [["", "Superficie útil interior", "", "", "", _m2(totals["useful_interior"]), "", ""]]
    if totals["exterior_computable"]:
        foot.append(["", "Exteriores cubiertos (50 %)", "", "", "", _m2(totals["exterior_computable"]), "", ""])
    foot += [["", "Superficie útil computable", "", "", "", _m2(totals["computable"]), "", ""],
             ["", "Superficie útil habitable", "", "", "", _m2(totals["habitable"]), "", ""]]
    return [c for c, _w in COLUMNS], body, foot


def layout(rows, totals, origin, h=0.20):
    """Lines and texts of the schedule, its top-left corner at ``origin``:
    ([(a, b)], [(text, (x, y), height, align)]). ``h``: text height (m)."""
    header, body, foot = table_cells(rows, totals)
    unit = 0.55 * h                                   # a character's width (sans serif)
    widths = [max(w, len(header[i]), *(len(r[i]) for r in body + foot if i != 1 or r in body)) * unit + h
              for i, (_c, w) in enumerate(COLUMNS)]
    rh = 1.8 * h
    x0, y0 = float(origin[0]), float(origin[1])
    total_w = sum(widths)
    texts = [("CUADRO DE SUPERFICIES ÚTILES", (x0, y0 + 0.9 * h), 1.25 * h, "left")]
    lines = []
    all_rows = [header] + body + foot
    y = y0
    ys = [y]
    for k, r in enumerate(all_rows):
        cy = y - rh / 2
        x = x0
        for i, cell in enumerate(r):
            if cell:
                right = i >= 3
                texts.append((cell, (x + widths[i] - h / 2 if right else x + h / 2, cy), h,
                              "right" if right else "left"))
            x += widths[i]
        y -= rh
        ys.append(y)
    for k, yy in enumerate(ys):
        lines.append(((x0, yy), (x0 + total_w, yy)))
    bottom = ys[-1]
    foot_top = ys[1 + len(body)]
    x = x0
    for i, w in enumerate(widths + [0.0]):
        top = y0
        # in the total rows only the outer frame and the value column are drawn
        lines.append(((x, top), (x, foot_top)))
        if i in (0, 5, 6, len(widths)):
            lines.append(((x, foot_top), (x, bottom)))
        x += w
    texts.append((f"Criterio: {criterion()['label']}", (x0, bottom - 0.9 * h), 0.8 * h, "left"))
    return lines, texts


class AreaTableCommand:
    """Draw the schedule (and erase the previous one in the same step)."""
    name = "ARQ CUADRO DE SUPERFICIES"

    def __init__(self, lines, texts, old=()):
        self.lines, self.texts, self.old = lines, texts, list(old)
        self.made = []
        self.erase = None

    def do(self, document):
        import uuid

        from .architectural import _xdata
        msp = document.doc.modelspace()
        if TABLE_LAYER not in document.doc.layers:
            document.doc.layers.add(TABLE_LAYER, color=7)
        if self.old:
            from core.actions import EraseCommand
            self.erase = EraseCommand(self.old)
            self.erase.do(document)
        tag = {"kind": TABLE_KIND, "schema": 1, "table_id": uuid.uuid4().hex}
        self.made = []
        for a, b in self.lines:
            e = msp.add_line(a, b, dxfattribs={"layer": TABLE_LAYER})
            _xdata(msp, e, tag)
            self.made.append(e)
        from ezdxf.enums import TextEntityAlignment as A
        align = {"left": A.MIDDLE_LEFT, "right": A.MIDDLE_RIGHT}
        for text, p, h, al in self.texts:
            t = msp.add_text(text, dxfattribs={"layer": TABLE_LAYER, "height": h})
            t.set_placement(p, align=align[al])
            _xdata(msp, t, tag)
            self.made.append(t)

    def undo(self, document):
        msp = document.doc.modelspace()
        for e in self.made:
            if e.is_alive:
                msp.delete_entity(e)
        self.made = []
        if self.erase is not None:
            self.erase.undo(document)


def existing_tables(drawing):
    """The entities of the schedules already drawn, and the top-left corner
    of the first one (its title's insertion, raised back to the frame)."""
    from .architectural import metadata
    ents = [e for e in drawing.modelspace() if (metadata(e) or {}).get("kind") == TABLE_KIND]
    corner = None
    for e in ents:
        if e.dxftype() == "TEXT" and e.dxf.text.startswith("CUADRO DE SUPERFICIES"):
            p = e.get_placement()[1] if hasattr(e, "get_placement") else e.dxf.insert
            corner = (float(p[0]), float(p[1]) - 0.9 * float(e.dxf.height) / 1.25)
    return ents, corner


def report(ctx, drawing=None):
    """The schedule as text in the command line (SUPERFICIES prints it first)."""
    rows, totals = table(drawing if drawing is not None else ctx.document.doc)
    ctx.echo(f"SUPERFICIES — criterio: {criterion()['label']}")
    if not rows:
        ctx.echo("No hay recintos. Créelos con RECINTO.")
        return rows, totals
    for r in rows:
        if "error" in r:
            ctx.echo(f"  {r['name']}: {r['error']}")
            continue
        line = f"  {r['name']}: útil {_m2(r['useful'])} m²"
        if r["factor"] != 1.0:
            line += f" × {r['factor']:g} = {_m2(r['computable'])} m²".replace(".", ",")
        line += f"; altura {_m2(r['height'])} m" + ("; habitable" if r["habitable"] else "")
        if r["notes"]:
            line += " (" + "; ".join(r["notes"]) + ")"
        ctx.echo(line)
    ctx.echo(f"Superficie útil interior: {_m2(totals['useful_interior'])} m²")
    if totals["exterior_computable"]:
        ctx.echo(f"Espacios exteriores cubiertos (50 %): {_m2(totals['exterior_computable'])} m²")
    ctx.echo(f"Superficie útil computable: {_m2(totals['computable'])} m²")
    ctx.echo(f"Superficie útil habitable (altura ≥ {_m2(criterion()['habitable_height'])} m; "
             f"≥ {_m2(criterion()['low_rooms_height'])} m en baños, aseos, vestíbulos y pasillos): "
             f"{_m2(totals['habitable'])} m²")
    ctx.echo("Los descuelgues parciales hasta 2,20 m en el 40 % de una estancia no se modelan "
             "(cada recinto tiene una sola altura).")
    ctx.echo("Escaleras interiores: aún no se modelan; descuéntelas si las hay.")
    return rows, totals


def _tool_base():
    from tools.base import Tool
    return Tool


class SuperficiesTool(_tool_base()):
    """SUPERFICIES: the schedule in the command line and, at the point
    given, drawn in the plan (A: update the one already drawn, in place)."""
    name = "SUPERFICIES"

    def start(self):
        from .compat import require_document
        self.doc = require_document(self.ctx)
        self.h = 0.20
        self.pending = False
        self.rows, self.totals = report(self.ctx, self.doc.doc)
        if not self.rows:
            self.ctx.finish()
            return
        self._prompt()

    def _prompt(self):
        _ents, corner = existing_tables(self.doc.doc)
        extra = "/Actualizar el cuadro existente" if corner is not None else ""
        self.prompt(f"SUPERFICIES: esquina superior izquierda del cuadro (texto de {_m2(self.h)} m) o "
                    f"[altura de Texto{extra}/Fin]:")

    def _draw(self, origin):
        from .transactions import SafeArchitecturalCommand
        old, _c = existing_tables(self.doc.doc)
        lines, texts = layout(self.rows, self.totals, origin, self.h)
        self.ctx.execute(SafeArchitecturalCommand("ARQ CUADRO DE SUPERFICIES", [AreaTableCommand(lines, texts, old)]))
        self.ctx.echo(f"SUPERFICIES: cuadro de {len(self.rows)} recintos dibujado en la capa {TABLE_LAYER}"
                      + (" (sustituye al anterior)." if old else "."))
        self.ctx.finish()

    def on_point(self, p):
        self._draw((float(p[0]), float(p[1])))

    def on_option(self, text):
        t = str(text).strip().lower()
        if self.pending:
            self.pending = False
            try:
                v = float(t.replace(",", "."))
                if not (v > 0):
                    raise ValueError
                self.h = v
            except ValueError:
                self.ctx.echo("SUPERFICIES: altura de texto no válida.")
            self._prompt()
            return True
        if t in ("t", "texto"):
            self.pending = True
            self.prompt("Altura del texto del cuadro (m; 0,20 a escala 1:100 = 2 mm):")
            return True
        if t in ("a", "actualizar"):
            _ents, corner = existing_tables(self.doc.doc)
            if corner is None:
                self.ctx.echo("SUPERFICIES: no hay cuadro que actualizar; indique dónde dibujarlo.")
                return True
            self._draw(corner)
            return True
        if t in ("f", "fin"):
            self.ctx.finish()
            return True
        return False

    def on_enter(self):
        self.ctx.finish()

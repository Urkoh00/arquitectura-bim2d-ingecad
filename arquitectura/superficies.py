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
    from shapely.geometry import Polygon
    c = criterion(crit)
    out = set()
    for cid, m in columns:
        try:
            if Polygon(m["polygon"]).area <= c["max_section_kept"] + 1e-12:
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
    """Shortest side of the minimum rotated rectangle of the room."""
    from shapely.geometry import Polygon
    poly = Polygon(room["outer"], room.get("holes") or [])
    rect = poly.minimum_rotated_rectangle
    pts = list(rect.exterior.coords)[:4]
    if len(pts) < 4:
        return 0.0
    import math
    return min(math.dist(pts[0], pts[1]), math.dist(pts[1], pts[2]))


def evaluate(meta, room, room_useful=None, crit=None):
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
    words = f"{meta.get('name') or ''} {meta.get('use') or ''}".lower()
    low_room = any(k in words for k in c.get("low_rooms", ()))
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
    rows, totals = [], {"useful_interior": 0.0, "exterior_computable": 0.0, "computable": 0.0,
                        "habitable": 0.0}
    for _ident, m, _e in read_spaces(drawing):
        room, _why = SP.space_at(result, m["seed"])
        if room is None:
            rows.append({"name": m.get("name") or "Recinto", "error": "no está cerrado"})
            continue
        room_u = SP.space_at(res_u, m["seed"])[0] if res_u is not None else None
        ev = evaluate(m, room, room_u, crit)
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
    """SUPERFICIES: cuadro de superficies útiles de los recintos (sin modificar el dibujo)."""
    rows, totals = table(ctx.document.doc)
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

# SPDX-License-Identifier: GPL-3.0-or-later
"""IngeCAD -> IngeTrazo exchange contract ``arqbim`` v1 (JSON, metres).

The plugin computes the FINAL constructive geometry once (geom.junctions +
geom.solids) and writes it with its semantics. IngeTrazo only builds meshes
from the faces it is given (``ingetrazo_ext/arquitectura_bim.py``): no
geometry is recomputed on the other side, so plan, 3D and IFC come from the
same polygons.

Which geometry is authoritative: the CAD entity the user sees. A wall axis
is its open two-vertex LWPOLYLINE, a column its closed LWPOLYLINE; the
XDATA copies (a/b, center) are compared and any divergence is reported, so
a MOVE/ROTATE/MIRROR done with generic CAD commands is never exported
silently with stale data.
"""
from __future__ import annotations

import json
import math
import uuid

from .architectural import metadata
from .geom import junctions as J
from .geom import solids as S

FORMAT = "arqbim"
VERSION = 1
_GUID_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$"

PSET = {"IfcWall": "Pset_WallCommon", "IfcColumn": "Pset_ColumnCommon"}


def ifc_guid(hex_id):
    """Stable IFC GlobalId (22 chars) from the element's persistent UUID:
    the same wall keeps the same GlobalId in every export."""
    try:
        n = uuid.UUID(hex=str(hex_id)).int
    except ValueError:
        n = uuid.uuid5(uuid.NAMESPACE_OID, str(hex_id)).int
    return "".join(_GUID_CHARS[(n >> (6 * i)) & 63] for i in range(21, -1, -1))


def _pts(entity):
    return [tuple(map(float, p)) for p in entity.get_points("xy")]


def read_model(drawing, tol=1e-5, strict=True):
    """Tagged walls/columns/openings of the drawing, CAD geometry first.

    Returns (walls, columns, openings, issues). Raises on duplicated IDs:
    exporting two objects with one identity would corrupt the IFC. With
    ``strict=False`` (plan regeneration) a duplicate is kept under a
    provisional key and reported, so the drawing can still be displayed."""
    msp = drawing.modelspace()
    walls, columns, openings, issues, seen = [], [], [], [], {}
    for e in msp:
        m = metadata(e) or {}
        kind = m.get("kind")
        if kind not in ("wall", "column", "opening"):
            continue
        ident = m.get("id")
        if not ident:
            issues.append(f"{kind} sin identificador (entidad {e.dxf.handle})")
            continue
        if ident in seen and not strict:
            issues.append(f"Identificador BIM duplicado {ident} (entidad {e.dxf.handle}): "
                          "copia sin reidentificar")
            ident = f"{ident}#{e.dxf.handle}"
        elif ident in seen:
            raise ValueError(f"Identificador BIM duplicado {ident} (entidades {seen[ident]} y "
                             f"{e.dxf.handle}); probablemente una COPIA: ejecute UNIONESARQ, que le asigna identidad nueva")
        seen[ident] = e.dxf.handle
        m = dict(m)
        if kind == "wall":
            if e.dxftype() == "LWPOLYLINE" and not e.closed and len(e) == 2:
                a, b = _pts(e)
                if math.dist(a, m["a"]) > tol or math.dist(b, m["b"]) > tol:
                    issues.append(f"Muro {ident}: el eje CAD no coincide con XDATA; se exporta el eje CAD")
                m["a"], m["b"] = list(a), list(b)
            walls.append((ident, m))
        elif kind == "column":
            if e.dxftype() != "LWPOLYLINE":
                continue
            m["polygon"] = _pts(e)
            columns.append((ident, m))
        else:
            openings.append(m)
    return walls, columns, openings, issues


def build(drawing, project="Proyecto", generator="Arquitectura IngeCAD"):
    walls, columns, openings, issues = read_model(drawing)
    specs = J.walls_from_records(walls)
    result = J.solve(specs, [(cid, m["polygon"]) for cid, m in columns])
    issues += result.warnings
    by_wall = {}
    for o in openings:
        by_wall.setdefault(o.get("wall_id"), []).append(o)
    levels = {}
    elements = []
    for spec, (ident, m) in zip(specs, walls):
        level = m.get("level") or "Planta baja"
        levels.setdefault(level, float(m.get("base", 0.0)))
        ops = sorted(by_wall.get(ident, []), key=lambda o: float(o["offset"]))
        geo = result.walls[ident]
        faces, volume = S.wall_solid(geo["pieces"], spec.a, spec.u,
                                     float(m.get("base", 0.0)), float(m["height"]), ops)
        el = _element(ident, "IfcWall", m, faces, volume, geo["area"], level)
        el["footprint"] = [[list(map(list, o)), [list(map(list, h)) for h in hs]]
                           for o, hs in geo["loops"]]
        el["params"].update(a=list(spec.a), b=list(spec.b), thickness=spec.thickness,
                            reference=spec.reference)
        el["quantities"] = {"Length": spec.length, "Height": float(m["height"]),
                            "Width": spec.thickness, "GrossFootprintArea": geo["area"],
                            "GrossVolume": geo["area"] * float(m["height"]),
                            "NetVolume": volume}
        el["openings"] = []
        for o in ops:
            box = S.opening_box(spec.a, spec.u, spec.n, spec.lo - 0.01, spec.hi + 0.01,
                                o, float(m.get("base", 0.0)))
            el["openings"].append({"id": o["id"], "guid": ifc_guid(o["id"]),
                                   "name": o.get("name") or "Hueco",
                                   "kind": o.get("type", "opening"),
                                   "params": {k: o[k] for k in ("offset", "width", "sill", "height")},
                                   "faces": _faces_json(box)})
        elements.append(el)
    for ident, m in columns:
        level = m.get("level") or "Planta baja"
        levels.setdefault(level, float(m.get("base", 0.0)))
        faces, volume = S.prism_solid(m["polygon"], float(m.get("base", 0.0)), float(m["height"]))
        el = _element(ident, "IfcColumn", m, faces, volume, volume / float(m["height"]), level)
        el["params"].update({k: m.get(k) for k in ("shape", "width", "depth", "radius",
                                                   "rotation", "center")})
        el["footprint"] = [[[list(p) for p in result.columns[ident]], []]]
        el["quantities"] = {"Length": float(m["height"]), "CrossSectionArea": volume / float(m["height"]),
                            "GrossVolume": volume, "NetVolume": volume}
        elements.append(el)
    return {
        "format": FORMAT, "version": VERSION, "units": "m",
        "generator": generator, "project": {"name": project},
        "levels": [{"name": n, "elevation": z} for n, z in sorted(levels.items(), key=lambda kv: kv[1])],
        "elements": elements,
        "joins": {"nodes": [{"walls": n["walls"], "point": list(n["point"])} for n in result.nodes],
                  "tees": result.tees,
                  "clips": [{"loser": c["loser"], "winner": c["winner"], "area": c["area"]}
                            for c in result.clips]},
        "issues": issues,
    }


def _faces_json(faces):
    return [{"outer": [list(v) for v in o], "holes": [[list(v) for v in h] for h in hs]}
            for o, hs in faces]


def _element(ident, cls, m, faces, volume, plan_area, level):
    name = m.get("name") or ("Muro" if cls == "IfcWall" else "Pilar")
    material = m.get("material") or ""
    type_name = m.get("type_name") or ""
    psets = {PSET[cls]: {"Reference": type_name or None, "LoadBearing": None, "IsExternal": None}}
    psets["ARQ_IngeCAD"] = {"SourceId": ident, "Thickness": m.get("thickness"),
                            "Height": m.get("height"), "Base": m.get("base", 0.0),
                            "Reference": m.get("reference"), "Material": material or None}
    psets = {k: {p: v for p, v in d.items() if v is not None} for k, d in psets.items()}
    return {
        "id": ident, "guid": ifc_guid(ident), "ifc_class": cls, "name": name,
        "type_name": type_name, "material": material, "level": level,
        "params": {"height": float(m["height"]), "base": float(m.get("base", 0.0))},
        "psets": {k: v for k, v in psets.items() if v},
        "volume": volume, "plan_area": plan_area,
        "faces": _faces_json(faces),
    }


def write(drawing, path, **kw):
    data = build(drawing, **kw)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    return data

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
from . import openings as OP

FORMAT = "arqbim"
VERSION = 1
_GUID_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$"

PSET = {"IfcWall": "Pset_WallCommon", "IfcColumn": "Pset_ColumnCommon", "IfcSpace": "Pset_SpaceCommon",
        "IfcCovering": "Pset_CoveringCommon", "IfcDoor": "Pset_DoorCommon",
        "IfcWindow": "Pset_WindowCommon"}


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


def read_spaces(drawing):
    """[(id, metadata, entity)] of the drawing's spaces (rooms)."""
    out = []
    for e in drawing.modelspace():
        m = metadata(e) or {}
        if m.get("kind") == "space" and m.get("id") and m.get("seed"):
            out.append((m["id"], dict(m), e))
    return out


def build(drawing, project="Proyecto", generator="Arquitectura IngeCAD"):
    walls, columns, openings, issues = read_model(drawing)
    specs = J.walls_from_records(walls)
    result = J.solve(specs, [(cid, m["polygon"]) for cid, m in columns])
    issues += result.warnings
    from .geom import spaces as SP
    external = SP.external_walls(result)
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
        # envelope: a face on the outer boundary of the building (calculated)
        el["psets"].setdefault("Pset_WallCommon", {})["IsExternal"] = ident in external
        el["psets"]["ARQ_IngeCAD"]["IsExternalSource"] = "calculado"
        el["is_external"] = ident in external
        el["footprint"] = [[list(map(list, o)), [list(map(list, h)) for h in hs]]
                           for o, hs in geo["loops"]]
        el["params"].update(a=list(spec.a), b=list(spec.b), thickness=spec.thickness,
                            reference=spec.reference)
        layers = m.get("layers") or []
        if layers:
            # from the drawn face (reference line) toward the body; for an IFC
            # IfcMaterialLayerSet (pending in IngeTrazo) and readable as Pset
            total = sum(float(t) for t, _m in layers)
            if abs(total - spec.thickness) > 5e-4:
                issues.append(f"Muro {ident}: sus capas suman {total:.3f} m y el espesor es "
                              f"{spec.thickness:.3f} m")
            el["material_layers"] = [{"thickness": float(t), "material": mat} for t, mat in layers]
            el["psets"]["ARQ_Capas"] = {f"Capa {i}": f"{float(t):.3f} m {mat}".strip()
                                        for i, (t, mat) in enumerate(layers, 1)}
        el["quantities"] = {"Length": spec.length, "Height": float(m["height"]),
                            "Width": spec.thickness, "GrossFootprintArea": geo["area"],
                            "GrossVolume": geo["area"] * float(m["height"]),
                            "NetVolume": volume}
        el["openings"] = []
        fillings = []
        for o in ops:
            o = OP.normalise(o)
            box = S.opening_box(spec.a, spec.u, spec.n, spec.lo - 0.01, spec.hi + 0.01,
                                o, float(m.get("base", 0.0)))
            filled = o["type"] in ("door", "window")
            # the void is derived from the door/window: the door keeps the
            # record's identity, its hole gets a stable one of its own
            void_id = o["id"] + "-hueco" if filled else o["id"]
            el["openings"].append({"id": void_id, "guid": ifc_guid(void_id),
                                   "name": ("Hueco de " + (o.get("name") or OP.NAMES[o["type"]]))
                                   if filled else (o.get("name") or "Hueco"),
                                   "kind": o["type"],
                                   "params": {k: o[k] for k in ("offset", "width", "sill", "height")},
                                   "faces": _faces_json(box)})
            if filled:
                fillings.append(_filling(o, spec, {**m, "_external": ident in external}, level,
                                         ifc_guid(void_id), ident))
        elements.append(el)
        elements.extend(fillings)
    for ident, m in columns:
        level = m.get("level") or "Planta baja"
        base, height = float(m.get("base", 0.0)), float(m["height"])
        levels.setdefault(level, base)
        footprint = [tuple(p) for p in m["polygon"]]
        try:
            from .sections import column_geometry
            sections = column_geometry(m["center"], m)["sections"]
        except Exception:  # noqa: BLE001  (older records: the polygon is the section)
            sections = [footprint]
        from .geom import polygon as P
        sec_pieces = [pc for sec in sections for pc in P.convex_parts(sec)]
        faces, volume = S.wall_solid(sec_pieces, (0.0, 0.0), (1.0, 0.0), base, height, ())
        sec_area = sum(P.area(pc) for pc in sec_pieces)
        el = _element(ident, "IfcColumn", m, faces, volume, sec_area, level)
        el["params"].update({k: m.get(k) for k in ("shape", "width", "depth", "radius",
                                                   "rotation", "center", "profile", "cover")})
        el["footprint"] = [[[list(p) for p in result.columns[ident]], []]]
        el["quantities"] = {"Length": height, "CrossSectionArea": sec_area,
                            "GrossVolume": volume, "NetVolume": volume}
        if m.get("shape") == "steel":
            from . import profiles as PR
            prof = PR.parse(m.get("profile", ""))
            el["psets"]["ARQ_Perfil"] = {"Perfil": PR.designation(prof),
                                         "AreaNominal_cm2": round(PR.nominal_area(prof) * 1e4, 2),
                                         "Masa_kg_m": round(PR.mass_per_metre(prof), 1)}
            el["quantities"]["NetWeight"] = PR.mass_per_metre(prof) * height
        elements.append(el)
        # what the footprint has beyond the column itself: its covering
        rest = P.convex_parts(footprint)
        for sec in sections:
            rest = P.subtract(rest, sec)
        rest_area = sum(P.area(pc) for pc in rest)
        if rest_area > 1e-9:
            cf, cv = S.wall_solid(rest, (0.0, 0.0), (1.0, 0.0), base, height, ())
            cid = ident + "-rec"
            cover = float(m.get("cover") or 0.0)
            what = (f"Recubrimiento de {cover:.3f} m".replace(".", ",") if cover > 0
                    else "Interior del cajeado del perfil")
            cm = {"name": "Revestimiento de pilar", "type_name": what,
                  "material": m.get("cover_material") or "", "height": height, "base": base}
            ce = _element(cid, "IfcCovering", cm, cf, cv, rest_area, level)
            ce["psets"] = {"ARQ_Recubrimiento": {"Pilar": ident, "Descripcion": what,
                                                 "Espesor": cover}}
            ce["params"].update(host=ident)
            ce["footprint"] = []
            ce["quantities"] = {"Width": cover, "GrossArea": rest_area, "GrossVolume": cv,
                                "NetVolume": cv}
            elements.append(ce)
    comps = SP.components(result) if columns or specs else []
    for ident, m, ent in read_spaces(drawing):
        level = m.get("level") or "Planta baja"
        levels.setdefault(level, float(m.get("base", 0.0)))
        room, why = SP.space_at(result, m["seed"], comps)
        name = m.get("name") or "Recinto"
        if room is None:
            issues.append(f"Recinto {name}: " + ("su punto interior queda dentro de un muro o pilar"
                          if why == "muro" else "no está cerrado") + "; no se exporta")
            continue
        base, height = float(m.get("base", 0.0)), float(m["height"])
        faces, volume = S.wall_solid(room["pieces"], (0.0, 0.0), (1.0, 0.0), base, height, ())
        el = _element(ident, "IfcSpace", m, faces, volume, room["area"], level)
        el["psets"] = {"Pset_SpaceCommon": {k: v for k, v in (("Reference", m.get("number") or None),
                                                               ("IsExternal", False)) if v is not None},
                       "ARQ_Recinto": {k: v for k, v in (("Uso", m.get("use") or None),
                                                         ("Acondicionado", m.get("conditioned")),
                                                         ("SourceId", ident),
                                                         ("CriterioSuperficie", "libre entre caras de muros y pilares"),
                                                         ("Techo", "falso techo" if m.get("ceiling") else "forjado"))
                                       if v is not None}}
        el["params"].update(seed=list(map(float, m["seed"])))
        el["footprint"] = [[[list(q) for q in room["outer"]], [[list(q) for q in h] for h in room["holes"]]]]
        el["quantities"] = {"Height": height, "GrossFloorArea": room["area"], "NetFloorArea": room["area"],
                            "GrossPerimeter": room["perimeter"], "NetPerimeter": room["perimeter"],
                            "GrossVolume": volume, "NetVolume": volume}
        if m.get("ceiling"):
            # the room is the air below the false ceiling (Qto_SpaceBaseQuantities)
            el["quantities"]["FinishCeilingHeight"] = height
        elements.append(el)
        if m.get("ceiling"):
            elements.append(_ceiling(ident, m, room, base + height, level))
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


CEILING_THICKNESS = 0.015     # one plasterboard sheet


def _ceiling(space_id, m, room, z, level):
    """The false ceiling of a room as an IfcCovering .CEILING.: its outline,
    from the top of the room upwards, so the room's top face is coplanar
    with the ceiling's underside (what thermal analysis tools require)."""
    t = float(m.get("ceiling_thickness") or CEILING_THICKNESS)
    faces, volume = S.wall_solid(room["pieces"], (0.0, 0.0), (1.0, 0.0), z, t, ())
    cm = {"name": "Falso techo de " + (m.get("name") or "Recinto"), "height": t, "base": z,
          "type_name": m.get("ceiling_type") or "", "material": m.get("ceiling_material") or ""}
    el = _element(space_id + "-techo", "IfcCovering", cm, faces, volume, room["area"], level)
    el["enums"] = {"PredefinedType": "CEILING"}
    el["psets"]["ARQ_IngeCAD"].update({"Recinto": space_id, "Tipo": "falso techo"})
    for k in ("Thickness", "Reference"):
        el["psets"]["ARQ_IngeCAD"].pop(k, None)
    el["quantities"] = {"Width": t, "GrossArea": room["area"], "NetArea": room["area"]}
    el["footprint"] = []
    return el


def _door_enums(o):
    if o["type"] == "door":
        if o["leaves"] == 2:
            op = "DOUBLE_DOOR_SLIDING" if o["operation"] == "SLIDING" else "DOUBLE_DOOR_SINGLE_SWING"
        else:
            # IFC: hinge side seen in the direction the door opens
            left = (o["hinge"] == 0) == (o["side"] > 0)
            op = (("SLIDING_TO_LEFT" if not left else "SLIDING_TO_RIGHT") if o["operation"] == "SLIDING"
                  else ("SINGLE_SWING_LEFT" if left else "SINGLE_SWING_RIGHT"))
        return {"PredefinedType": "DOOR", "OperationType": op}
    part = {1: "SINGLE_PANEL", 2: "DOUBLE_PANEL_VERTICAL", 3: "TRIPLE_PANEL_VERTICAL"}
    return {"PredefinedType": "WINDOW", "PartitioningType": part.get(o["leaves"], "NOTDEFINED")}


def _filling(o, spec, wall_meta, level, void_guid, wall_id):
    """IfcDoor/IfcWindow filling a wall's hole (IfcRelFillsElement in the
    IFC): one closed body across the frame depth, so that wall + door have
    the volume of the uncut wall slice they replace."""
    from . import openings as OP
    base = float(wall_meta.get("base", 0.0))
    s0, s1, f0, f1, z0, z1 = OP.filling_box(spec, o, base)
    fake = {"offset": s0, "width": s1 - s0, "sill": z0 - base, "height": z1 - z0}
    faces = S.opening_box(spec.a, spec.u, spec.n, f0, f1, fake, base)
    cls = OP.IFC[o["type"]]
    m = {"name": o.get("name") or OP.NAMES[o["type"]], "type_name": o.get("type_name") or "",
         "material": o.get("material") or "", "height": z1 - z0, "base": z0}
    el = _element(o["id"], cls, m, faces, (s1 - s0) * (f1 - f0) * (z1 - z0), (s1 - s0) * (f1 - f0), level)
    el["fills"] = void_guid
    el["enums"] = _door_enums(o)
    el["host"] = wall_id
    el["params"].update({k: o.get(k) for k in ("offset", "width", "sill", "leaves", "leaf", "leaf2",
                                              "side", "hinge", "face", "frame_width", "frame_depth",
                                              "sill_kind")})
    common = el["psets"].setdefault(PSET[cls], {})
    common["IsExternal"] = bool(wall_meta.get("_external"))
    arq = el["psets"]["ARQ_IngeCAD"]
    for k in ("Thickness", "Reference"):
        arq.pop(k, None)
    arq["Host"] = wall_id
    arq["Apertura"] = OP.OPERATION_NAMES.get(o.get("operation"), "")
    arq["Ajuste"] = {"centrada": "medio"}.get(o.get("face"), o.get("face"))
    if o["type"] == "door":
        arq.update({"Hojas": o["leaves"], "Hoja": round(o["leaf"], 4),
                    "Cerco": round(float(o["frame_width"]), 4)})
        if o["leaves"] == 2:
            arq["Hoja2"] = round(o["leaf2"], 4)
    else:
        arq.update({"Hojas": o["leaves"], "Antepecho": float(o["sill"]),
                    "Remate": o.get("sill_kind") or ""})
    el["quantities"] = {"Height": z1 - z0, "Width": s1 - s0, "Area": (s1 - s0) * (z1 - z0)}
    el["footprint"] = []
    return el


def _element(ident, cls, m, faces, volume, plan_area, level):
    name = m.get("name") or {"IfcWall": "Muro", "IfcColumn": "Pilar", "IfcSpace": "Recinto",
                             "IfcCovering": "Revestimiento", "IfcDoor": "Puerta",
                             "IfcWindow": "Ventana"}.get(cls, cls)
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

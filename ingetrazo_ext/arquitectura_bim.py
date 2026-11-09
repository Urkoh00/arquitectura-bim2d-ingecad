# SPDX-License-Identifier: GPL-3.0-or-later
"""IngeTrazo extension: open ``.arqbim`` files written by the IngeCAD
Arquitectura plugin.

Install: copy this file to IngeTrazo's plugins folder (Extensions > Open
plugins folder). It runs inside IngeTrazo's own interpreter, so it works
with the installed or portable IngeTrazo: no Python, no source checkout and
no CONFIGIGZ on the user's side.

It computes NO geometry: every face comes from the contract, built once by
the IngeCAD plugin from the same footprints as the plan. Here we only build
IngeTrazo meshes with the official ``Mesh``/``Group`` classes, tag them with
``group.ifc`` (class, name, stable GlobalId, storey, material, type,
property sets, openings) and keep the full record in ``group.ext``.

The file is opened through IngeTrazo's own path (written as IGZ with
``formats.igz.save_scene`` and inserted with ``import_igz``), so the
insertion is one undo step and goes through the official reader.

Headless use (tests, batch):
    python arquitectura_bim.py model.arqbim model.igz [model.ifc]
run from an IngeTrazo source folder (or with it on PYTHONPATH).
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

SUFFIX = ".arqbim"
SUPPORTED = (1,)
#: key of this extension's data in the document (``scene.plugin_data``):
#: never the loader's file name, which the host would use by default
DATA_KEY = "arquitectura"


#: what each class may carry (possible finding 26 of the independent audit:
#: a space with wall layers made the IFC writer produce an invalid file)
ONLY_FOR = {"material_layers": {"IfcWall"}, "openings": {"IfcWall"},
            "fills": {"IfcDoor", "IfcWindow"}, "host": {"IfcDoor", "IfcWindow"}}


def validate_contract(data):
    """Check the whole contract before anything enters IngeTrazo: format,
    identities (unique ids and GUIDs), levels, classes and what each may
    carry, finite numbers, closed and well-oriented solids, holes inside
    their wall and coherent host/fills relations.  Raises ValueError with
    the first problem (independent audit of v1.15, ARQ-AUD-0012; adapted
    from the correction delivered with it)."""
    import math
    import re
    from collections import Counter
    if not isinstance(data, dict) or data.get("format") != "arqbim":
        raise ValueError("No es un archivo arqbim")
    if type(data.get("version")) is not int or data["version"] not in SUPPORTED:
        raise ValueError("No es un archivo arqbim compatible (versión %r)" % data.get("version"))
    if data.get("units") != "m":
        raise ValueError("Unidades no soportadas: %r" % data.get("units"))
    if not isinstance(data.get("elements"), list) or not isinstance(data.get("levels", []), list):
        raise ValueError("Faltan las listas de elementos o de plantas")
    if len(data["elements"]) > 200000:
        raise ValueError("Demasiados elementos")
    ids, guids, voids = set(), set(), {}
    vertices = [0]

    def finite_tree(value, depth=0):
        if depth > 60:
            raise ValueError("Contrato demasiado profundo")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Número no finito")
        if isinstance(value, dict):
            for v in value.values():
                finite_tree(v, depth + 1)
        elif isinstance(value, list):
            for v in value:
                finite_tree(v, depth + 1)
    finite_tree(data)

    def identity(obj):
        if not isinstance(obj, dict):
            raise ValueError("Elemento que no es un objeto")
        ident, guid = obj.get("id"), obj.get("guid")
        if not isinstance(ident, str) or not ident or ident in ids:
            raise ValueError("Identificador ausente o repetido: %r" % ident)
        if not isinstance(guid, str) or not re.fullmatch(r"[0-3][0-9A-Za-z_$]{21}", guid) or guid in guids:
            raise ValueError("GlobalId no válido o repetido: %r" % guid)
        ids.add(ident)
        guids.add(guid)

    def boundary(faces, who):
        if not isinstance(faces, list) or not faces:
            raise ValueError("%s sin caras" % who)
        edges, directions = Counter(), Counter()
        for face in faces:
            if not isinstance(face, dict):
                raise ValueError("%s: cara no válida" % who)
            for loop in [face.get("outer")] + list(face.get("holes") or []):
                if not isinstance(loop, list) or len(loop) < 3:
                    raise ValueError("%s: contorno de cara incompleto" % who)
                keys = []
                for pt in loop:
                    if (not isinstance(pt, (list, tuple)) or len(pt) != 3
                            or any(type(v) not in (int, float) or not math.isfinite(v) for v in pt)):
                        raise ValueError("%s: vértice no válido" % who)
                    keys.append(tuple(round(v, 7) for v in pt))
                    vertices[0] += 1
                    if vertices[0] > 2000000:
                        raise ValueError("Demasiados vértices")
                if len(set(keys)) != len(keys):
                    raise ValueError("%s: vértices repetidos en una cara" % who)
                for a, b in zip(keys, keys[1:] + keys[:1]):
                    key = tuple(sorted((a, b)))
                    edges[key] += 1
                    directions[key] += 1 if a < b else -1
        if any(n != 2 for n in edges.values()) or any(directions.values()):
            raise ValueError("%s: sólido abierto o caras mal orientadas" % who)

    levels = {}
    for lv in data.get("levels", []):
        if not isinstance(lv, dict) or not isinstance(lv.get("name"), str) or type(lv.get("elevation")) not in (int, float):
            raise ValueError("Planta no válida: %r" % lv)
        if lv["name"] in levels:
            raise ValueError("Planta repetida: %s" % lv["name"])
        levels[lv["name"]] = lv["elevation"]
    allowed = {"IfcWall", "IfcColumn", "IfcDoor", "IfcWindow", "IfcSpace", "IfcCovering"}
    by_id = {}
    for el in data["elements"]:
        identity(el)
        by_id[el["id"]] = el
        cls = el.get("ifc_class")
        who = "%s %s" % (cls, el.get("name") or el["id"])
        if cls not in allowed:
            raise ValueError("Clase no admitida: %r" % cls)
        if el.get("level") is not None and levels and el["level"] not in levels:
            raise ValueError("%s: planta %r inexistente" % (who, el["level"]))
        for key, classes in ONLY_FOR.items():
            if el.get(key) and cls not in classes:
                raise ValueError("%s: «%s» solo es válido en %s" % (who, key, ", ".join(sorted(classes))))
        if (el.get("enums") or {}).get("PredefinedType") == "CEILING" and cls != "IfcCovering":
            raise ValueError("%s: el tipo CEILING solo es válido en IfcCovering" % who)
        if type(el.get("volume")) not in (int, float) or el["volume"] <= 0:
            raise ValueError("%s: volumen no válido" % who)
        params = el.get("params")
        if not isinstance(params, dict):
            raise ValueError("%s: faltan sus parámetros" % who)
        boundary(el.get("faces"), who)
        for op in el.get("openings", []):
            identity(op)
            boundary(op.get("faces"), "Hueco de " + who)
            voids[op["guid"]] = el["id"]
            q = op.get("params", {})
            if any(type(q.get(k)) not in (int, float) for k in ("offset", "width", "sill", "height")):
                continue                     # a hole described only by its faces
            if q["offset"] < -1e-7 or q["sill"] < -1e-7 or min(q["width"], q["height"]) <= 0:
                raise ValueError("Hueco de %s con medidas no válidas" % who)
            height = params.get("height")
            if type(height) in (int, float) and q["sill"] + q["height"] > height + 1e-7:
                raise ValueError("Hueco de %s fuera de su altura" % who)
            if "a" in params and "b" in params:
                length = math.dist(params["a"][:2], params["b"][:2])
                bulge = float(params.get("bulge") or 0)
                if bulge:
                    sweep = 4 * math.atan(bulge)
                    length = length / (2 * math.sin(abs(sweep) / 2)) * abs(sweep)
                if q["offset"] + q["width"] > length + 1e-7:
                    raise ValueError("Hueco de %s fuera de su muro" % who)
    for el in data["elements"]:
        if el.get("host") and el["host"] not in by_id:
            raise ValueError("%s: su muro anfitrión no está en el modelo" % el["id"])
        if el.get("fills") and voids.get(el["fills"]) != el.get("host"):
            raise ValueError("%s: no rellena un hueco de su muro" % el["id"])
    return data


def read_contract(path):
    if Path(path).stat().st_size > 64 * 1024 * 1024:
        raise ValueError("El contrato supera 64 MiB")

    def reject(token):
        raise ValueError("Número no finito en el contrato: " + token)
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=reject)
    except (RecursionError, UnicodeError) as exc:
        raise ValueError("Contrato ilegible o demasiado profundo") from exc
    return validate_contract(data)


def survey_offset(data):
    """IngeTrazo's own rule for far coordinates (formats/recenter.py: beyond
    100 km, whole metres from the low corner), or None.  The same rule its
    importers apply, so an arqbim lands like any other file would."""
    import math
    lo, hi = [math.inf] * 3, [-math.inf] * 3
    for el in data["elements"]:
        for f in el["faces"]:
            for p in f["outer"]:
                for i in range(3):
                    lo[i] = min(lo[i], float(p[i]))
                    hi[i] = max(hi[i], float(p[i]))
    try:
        from formats.recenter import survey_offset as official
    except ImportError:                       # an IngeTrazo without it
        if not all(map(math.isfinite, lo + hi)) or max(abs(c) for c in lo + hi) <= 100_000.0:
            return None
        return tuple(float(int(c)) for c in lo)
    return official(lo, hi)


def definition(data, source=""):
    """The architectural definition kept in the IGZ (``plugin_data``): every
    element's identity, class, parameters, properties and relations, and the
    building's classifications — everything but the faces, which are the
    meshes themselves. JSON-safe, so IngeTrazo saves it with the document
    and another tool can read the model without rebuilding it."""
    keep = ("id", "guid", "ifc_class", "name", "level", "material_layers", "type_name", "material", "params",
            "psets", "quantities", "openings_ids", "fills", "host", "enums")
    elements = []
    for el in data.get("elements", []):
        rec = {k: el[k] for k in keep if k in el}
        if el.get("openings"):
            rec["openings"] = [{k: o[k] for k in ("id", "guid", "name", "kind", "params") if k in o}
                               for o in el["openings"]]
        elements.append(rec)
    return {"schema": 1, "format": data.get("format"), "version": data.get("version"),
            "generator": data.get("generator"), "project": data.get("project"),
            "levels": data.get("levels"), "source": str(source), "elements": elements}


def build_scene(data, offset=None):
    """A Scene with one tagged Group per element (IngeTrazo classes only).
    ``offset``: subtracted from every coordinate before it becomes single
    precision (``survey_offset``); kept in the document data."""
    from PySide6.QtGui import QVector3D as V

    validate_contract(data)
    ox, oy, oz = offset or (0.0, 0.0, 0.0)

    def local(p):
        return (float(p[0]) - ox, float(p[1]) - oy, float(p[2]) - oz)

    from core.group import Group
    from core.layers import Layer
    from core.mesh import Mesh
    from core.scene import Scene

    levels = {lv["name"]: float(lv["elevation"]) for lv in data.get("levels", [])}
    scene = Scene()
    layer_of = {"IfcWall": "ARQ-MUROS", "IfcColumn": "ARQ-PILARES", "IfcSpace": "ARQ-RECINTOS",
                "IfcCovering": "ARQ-PILARES", "IfcDoor": "ARQ-CARPINTERIA",
                "IfcWindow": "ARQ-CARPINTERIA"}
    for name in ("ARQ-MUROS", "ARQ-PILARES"):
        scene.layers.append(Layer(name, color=(0.72, 0.72, 0.70)))
    if any((el.get("enums") or {}).get("PredefinedType") == "CEILING" for el in data["elements"]):
        scene.layers.append(Layer("ARQ-TECHOS", color=(0.92, 0.92, 0.88)))
    if any(el["ifc_class"] in ("IfcDoor", "IfcWindow") for el in data["elements"]):
        scene.layers.append(Layer("ARQ-CARPINTERIA", color=(0.62, 0.45, 0.30)))
    if any(el["ifc_class"] == "IfcSpace" for el in data["elements"]):
        # rooms are volumes of air: off and translucent, so walls stay in view
        scene.layers.append(Layer("ARQ-RECINTOS", visible=False, color=(0.55, 0.75, 0.95),
                                  opacity=0.35))
    for el in data["elements"]:
        mesh = Mesh()
        for f in el["faces"]:
            outer = [V(*local(p)) for p in f["outer"]]
            holes = [[V(*local(p)) for p in h] for h in f.get("holes", [])] or None
            mesh.add_face(outer, holes)
        if not mesh.faces:
            raise ValueError("Elemento sin geometría: %s" % el["id"])
        g = Group(mesh, name=el.get("name") or el["ifc_class"])
        g.layer = ("ARQ-TECHOS" if (el.get("enums") or {}).get("PredefinedType") == "CEILING"
                   else layer_of.get(el["ifc_class"]))
        tag = {"class": el["ifc_class"], "name": g.name, "guid": el["guid"]}
        if el.get("level"):
            tag["storey"] = {"name": el["level"], "elevation": levels.get(el["level"], 0.0)}
        if el.get("material"):
            tag["material"] = el["material"]
        if el.get("type_name"):
            tag["type"] = el["type_name"]
        if el.get("psets"):
            tag["psets"] = el["psets"]
        if el.get("quantities"):
            tag["quantities"] = el["quantities"]
        if el.get("enums"):
            # enumerated attributes (IfcCovering .CEILING., door operation)
            tag["enums"] = el["enums"]
        if el.get("fills"):
            # IfcRelFillsElement: the hole (IfcOpeningElement) it fills
            tag["fills"] = el["fills"]
        if el.get("openings"):
            tag["openings"] = [{"guid": o["guid"], "name": o.get("name", "Hueco"),
                                "faces": [{"outer": [list(local(p)) for p in f["outer"]],
                                           "holes": [[list(local(p)) for p in h] for h in f.get("holes", [])]}
                                          for f in o["faces"]]} for o in el["openings"]]
        g.ifc = tag
        record = {k: v for k, v in el.items() if k not in ("faces",)}
        g.ext = {"arquitectura": {"schema": 3, "source_id": el["id"], **record}}
        scene.groups.append(g)
    stored = {"models": {data.get("project", {}).get("name") or "modelo": definition(data)}}
    if offset:
        stored["survey_offset"] = list(offset)
    scene.plugin_data = {DATA_KEY: stored}
    return scene


def check_scene(scene, data):
    """Identity and quantity checks after the official reader."""
    from core.bim import collect_objects
    want = {el["id"]: el for el in data["elements"]}
    got = {}
    for g in scene.groups:
        info = (getattr(g, "ext", None) or {}).get("arquitectura") or {}
        uid = info.get("source_id")
        if uid in got:
            raise RuntimeError("Identificador BIM duplicado al releer: %s" % uid)
        got[uid] = g
    if set(got) != set(want):
        raise RuntimeError("El IGZ no conserva los elementos: faltan %s" % sorted(set(want) - set(got)))
    report = []
    for obj in collect_objects(scene):
        g = obj["group"]
        el = want[g.ext["arquitectura"]["source_id"]]
        if obj["volume"] is None:
            raise RuntimeError("Sólido no estanco en IngeTrazo: %s" % el["id"])
        # IngeTrazo keeps positions in single precision (QVector3D): allow
        # their float32 rounding, never a geometric difference. The volume
        # is measured here in double precision about the solid's own first
        # vertex: IngeTrazo's takeoff sums the triple products in float32
        # with world coordinates, which loses ~1e-4 m3 on a door 35 m from
        # the origin (REGISTRO_UPSTREAM T-09); that is not the model's error.
        vol = _volume64(obj["group"])
        offset = ((getattr(scene, "plugin_data", None) or {}).get(DATA_KEY) or {}).get("survey_offset")
        if abs(vol - el["volume"]) > _float32_volume_tolerance(el, offset):
            raise RuntimeError("Volumen distinto en %s: %.6f != %.6f" % (el["id"], vol, el["volume"]))
        report.append((el["ifc_class"], el["id"], vol, el["volume"]))
    return report


def _volume64(group):
    """Enclosed volume of a top-level group's mesh, in double precision,
    with the coordinates taken from its first vertex (no cancellation)."""
    total, ref = 0.0, None
    for f in group.mesh.faces:
        for tri in f.triangulate():
            pts = [(float(p.x()), float(p.y()), float(p.z())) for p in tri]
            if ref is None:
                ref = pts[0]
            (ax, ay, az), (bx, by, bz), (cx, cy, cz) = [(x - ref[0], y - ref[1], z - ref[2]) for x, y, z in pts]
            total += (ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx)) / 6.0
    return abs(total)


def _float32_volume_tolerance(el, offset=None):
    """Bound of the volume change caused by rounding every vertex to
    float32: surface area x largest coordinate x 2^-23 (x2 for safety),
    with the coordinates IngeTrazo holds (after ``offset``)."""
    import math
    big, area = 1.0, 0.0
    ox, oy, oz = offset or (0.0, 0.0, 0.0)
    for f in el["faces"]:
        pts = [(p[0] - ox, p[1] - oy, p[2] - oz) for p in f["outer"]]
        big = max(big, *(abs(c) for p in pts for c in p))
        n = [0.0, 0.0, 0.0]
        for i in range(len(pts)):
            x0, y0, z0 = pts[i]
            x1, y1, z1 = pts[(i + 1) % len(pts)]
            n[0] += (y0 - y1) * (z0 + z1)
            n[1] += (z0 - z1) * (x0 + x1)
            n[2] += (x0 - x1) * (y0 + y1)
        area += 0.5 * math.sqrt(sum(c * c for c in n))
    return 2.0 * area * big * 2.0 ** -23


def to_igz(contract_path, igz_path, offset="auto"):
    """``offset``: "auto" (IngeTrazo's rule), None or an (x, y, z) to reuse
    (a second model in a document that was already moved)."""
    from core.scene import Scene
    from formats.igz import load_into, save_scene
    data = read_contract(contract_path)
    if offset == "auto":
        offset = survey_offset(data)
    scene = build_scene(data, offset)
    save_scene(scene, Path(igz_path))
    loaded = Scene()
    load_into(loaded, Path(igz_path))
    return data, loaded, check_scene(loaded, data)


# -- inside IngeTrazo ----------------------------------------------------------------------

def setup(app):
    app.key = DATA_KEY              # our data under our own key, whatever file loaded us

    def open_arqbim(path):
        stored = app.document_data({}) or {}
        # a second model goes where the first one went (same offset)
        previous = stored.get("survey_offset")
        with tempfile.TemporaryDirectory(prefix="arqbim_") as directory:
            tmp = Path(directory) / (Path(path).stem + ".igz")
            data, scene, _report = to_igz(path, tmp, offset=tuple(previous) if previous else "auto")
            offset = ((scene.plugin_data or {}).get(DATA_KEY) or {}).get("survey_offset")
            models = dict(stored.get("models") or {})
            key, n = Path(path).stem, 2
            while key in models:                      # never overwrite another model
                key, n = "%s (%d)" % (Path(path).stem, n), n + 1
            models[key] = definition(data, Path(path).name)
            value = {**stored, "models": models}
            if offset:
                value["survey_offset"] = list(offset)
            if hasattr(app, "import_igz_with_data"):
                # an IngeTrazo that inserts geometry and data in one undo step
                app.import_igz_with_data(tmp, value)
            else:
                # the official IngeTrazo: the component, then the document
                # data (an inserted component does not bring it along)
                app.import_igz(tmp, at=(0.0, 0.0, 0.0))
                app.set_document_data(value)
        if offset:
            note = ("Modelo desplazado cerca del origen (coordenadas lejanas, regla de IngeTrazo): "
                    "desplazamiento %.0f, %.0f, %.0f m" % tuple(offset))
            try:
                app.window.statusBar().showMessage(note, 10000)
            except Exception:
                pass
            print(note)
        return True

    def ask_and_open():
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(app.window, "Importar arquitectura IngeCAD",
                                              "", "Arquitectura BIM (*.arqbim)")
        if path:
            try:
                open_arqbim(path)
            except Exception as exc:  # noqa: BLE001  (tell the user, do not fail silently)
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(app.window, "Importar arquitectura IngeCAD",
                                    "No se pudo importar %s:\n\n%s: %s" % (Path(path).name,
                                                                           type(exc).__name__, exc))
                raise

    app.add_file_opener(SUFFIX, open_arqbim)
    app.add_menu_action("Importar arquitectura IngeCAD (.arqbim)…", ask_and_open)


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if len(args) not in (2, 3):
        raise SystemExit(__doc__)
    sys.path.insert(0, str(Path.cwd()))
    data, scene, report = to_igz(args[0], args[1])
    print("IGZ releído con el lector oficial: %d elementos, todos estancos" % len(report))
    if len(args) == 3:
        from formats.ifc import save_ifc
        n = save_ifc(scene, args[2], project_name=data["project"]["name"])
        print("IFC escrito con formats.ifc: %d elementos" % n)

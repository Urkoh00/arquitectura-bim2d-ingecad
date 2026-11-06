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


def read_contract(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("format") != "arqbim" or data.get("version") not in SUPPORTED:
        raise ValueError("No es un archivo arqbim compatible (versión %r)" % data.get("version"))
    if data.get("units") != "m":
        raise ValueError("Unidades no soportadas: %r" % data.get("units"))
    return data


def build_scene(data):
    """A Scene with one tagged Group per element (IngeTrazo classes only)."""
    from PySide6.QtGui import QVector3D as V

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
            outer = [V(*p) for p in f["outer"]]
            holes = [[V(*p) for p in h] for h in f.get("holes", [])] or None
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
                                "faces": o["faces"]} for o in el["openings"]]
        g.ifc = tag
        record = {k: v for k, v in el.items() if k not in ("faces",)}
        g.ext = {"arquitectura": {"schema": 3, "source_id": el["id"], **record}}
        scene.groups.append(g)
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
        vol = obj["volume"]
        if vol is None:
            raise RuntimeError("Sólido no estanco en IngeTrazo: %s" % el["id"])
        # IngeTrazo keeps positions in single precision (QVector3D): allow
        # float32 rounding, never a geometric difference.
        if abs(vol - el["volume"]) > _float32_volume_tolerance(el):
            raise RuntimeError("Volumen distinto en %s: %.6f != %.6f" % (el["id"], vol, el["volume"]))
        report.append((el["ifc_class"], el["id"], vol, el["volume"]))
    return report


def _float32_volume_tolerance(el):
    """Bound of the volume change caused by rounding every vertex to
    float32: surface area x largest coordinate x 2^-23 (x2 for safety)."""
    import math
    big, area = 1.0, 0.0
    for f in el["faces"]:
        pts = f["outer"]
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


def to_igz(contract_path, igz_path):
    from core.scene import Scene
    from formats.igz import load_into, save_scene
    data = read_contract(contract_path)
    scene = build_scene(data)
    save_scene(scene, Path(igz_path))
    loaded = Scene()
    load_into(loaded, Path(igz_path))
    return data, loaded, check_scene(loaded, data)


# -- inside IngeTrazo ----------------------------------------------------------------------

def setup(app):
    def open_arqbim(path):
        tmp = Path(tempfile.mkdtemp(prefix="arqbim_")) / (Path(path).stem + ".igz")
        to_igz(path, tmp)
        app.import_igz(tmp, at=(0.0, 0.0, 0.0))
        return True

    def ask_and_open():
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(app.window, "Importar arquitectura IngeCAD",
                                              "", "Arquitectura BIM (*.arqbim)")
        if path:
            open_arqbim(path)

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

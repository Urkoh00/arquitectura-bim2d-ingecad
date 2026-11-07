# SPDX-License-Identifier: GPL-3.0-or-later
"""The plugin runs with what IngeCAD ships, nothing more.

Found by the user on 7-11-2026 (v1.14.0): MURO failed in IngeCAD with
«No module named 'shapely'». The test environment has shapely (the tests
use it to check the geometry), so nothing caught it. Here the plugin's
code is read for imports outside IngeCAD's own requirements, and a whole
session is run with shapely made impossible to import."""
import ast
import sys
from pathlib import Path

import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401  (fixture)
from tests.test_recintos import _cmd_ctx
from tests.test_wall_tools import Session, draw

ROOT = Path(__file__).resolve().parents[1]
STDLIB = set(sys.stdlib_module_names)
# IngeCAD's own packages and its requirements.txt (PySide6, ezdxf, numpy, Pillow, pyproj)
ALLOWED = {"core", "tools", "formats", "views", "PySide6", "ezdxf", "numpy", "PIL", "pyproj"}


@pytest.mark.parametrize("folder", ["arquitectura", "ingetrazo_ext"])
def test_solo_importa_lo_que_trae_el_programa(folder):
    bad = []
    for f in (ROOT / folder).rglob("*.py"):
        siblings = {g.stem for g in f.parent.glob("*.py")}   # a script run on its own imports its siblings
        for node in ast.walk(ast.parse(f.read_text("utf-8"))):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            for n in names:
                top = n.split(".")[0]
                if top not in STDLIB and top not in ALLOWED and top not in siblings:
                    bad.append(f"{f.relative_to(ROOT)}: {n}")
    assert not bad, "dependencias que IngeCAD/IngeTrazo no instalan: " + ", ".join(bad)


def test_sesion_completa_sin_shapely(plugin, monkeypatch):
    for mod in [m for m in list(sys.modules) if m == "shapely" or m.startswith("shapely.")]:
        monkeypatch.delitem(sys.modules, mod)
    for mod in ("shapely", "shapely.geometry", "shapely.ops"):
        monkeypatch.setitem(sys.modules, mod, None)          # import → ImportError
    s = Session(plugin)
    m = s.tool("MURO")
    draw(m, (0, 0), (5, 0), (5, 4), (0, 4), (0, 0))
    assert len(s.walls()) == 4, s.out[-3:]
    p = s.tool("PILAR")
    p.on_point((2.5, 2))
    c = s.tool("MUROCURVO")
    c.on_point((5, 0))
    c.on_point((5, 4))
    c.on_option("1")
    v = s.tool("VENTANAARQ")
    v.on_point((2.5, 4.15))
    v.on_point((3, 4.15))
    r = s.tool("RECINTO")
    r.on_point((1, 1))
    bad = [o for o in s.out if "No module" in o or "ImportError" in o or "ModuleNotFound" in o]
    assert not bad, bad
    s.plugin.commands["SUPERFICIES"](_ctx(s))
    data = s.export(None)
    assert {e["ifc_class"] for e in data["elements"]} >= {"IfcWall", "IfcColumn", "IfcWindow", "IfcSpace"}


def _ctx(s):
    return _cmd_ctx(s)

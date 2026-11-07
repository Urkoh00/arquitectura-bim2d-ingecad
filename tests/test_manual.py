# SPDX-License-Identifier: GPL-3.0-or-later
"""The user manual is kept up to date with every version."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_manual_de_la_version_actual():
    version = re.search(r'_VERSION = "([^"]+)"', (ROOT / "arquitectura" / "__init__.py").read_text("utf-8")).group(1)
    manual = (ROOT / "docs" / "MANUAL.md").read_text("utf-8")
    assert f"versión **{version}**" in manual, "docs/MANUAL.md no corresponde a la versión del plugin"
    assert f"| {version} |" in manual, "falta la versión en «Novedades por versión» del manual"


def test_manual_cubre_las_ordenes_bim():
    src = (ROOT / "arquitectura" / "__init__.py").read_text("utf-8")
    manual = (ROOT / "docs" / "MANUAL.md").read_text("utf-8")
    toolbar = set(re.findall(r'ToolbarItem\("[^"]+", "([A-Z]+)"', src))
    missing = sorted(c for c in toolbar if f"`{c}`" not in manual)
    assert not missing, f"órdenes de la barra sin documentar en el manual: {missing}"

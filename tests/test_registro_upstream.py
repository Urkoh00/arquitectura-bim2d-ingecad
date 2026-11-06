# SPDX-License-Identifier: GPL-3.0-or-later
"""El registro de incidencias de IngeCAD/IngeTrazo recoge todos los parches propuestos."""
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"


def test_todos_los_parches_figuran_en_el_registro():
    registro = (DOCS / "REGISTRO_UPSTREAM.md").read_text(encoding="utf-8")
    parches = sorted((DOCS / "propuestas_upstream").glob("*/*.patch"))
    assert parches
    faltan = [f"{p.parent.name}/{p.name[:5]}" for p in parches
              if f"{p.parent.name}/{p.name[:5]}" not in registro]
    assert not faltan, f"Parches sin registrar en docs/REGISTRO_UPSTREAM.md: {faltan}"

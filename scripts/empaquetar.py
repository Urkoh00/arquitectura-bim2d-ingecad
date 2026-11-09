# SPDX-License-Identifier: GPL-3.0-or-later
"""Crea dist/Arquitectura_IngeCAD_<version>.zip listo para instalar en IngeCAD.

Uso:  python scripts/empaquetar.py
"""
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
version = re.search(r'_VERSION\s*=\s*"([^"]+)"', (ROOT / "arquitectura" / "__init__.py").read_text(encoding="utf-8")).group(1)
out = ROOT / "dist" / f"Arquitectura_IngeCAD_v{version}.zip"
out.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    # the plugin, the IngeTrazo extension and, so whoever installs from the
    # ZIP can reproduce the checks, the tests, this script and the docs
    for base in ("arquitectura", "ingetrazo_ext", "tests", "scripts", "docs"):
        for f in sorted((ROOT / base).rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts:
                z.write(f, f.relative_to(ROOT))
    for f in ("LICENSE", "README.md", "CHANGELOG.md", "pytest.ini", "requirements-dev.txt"):
        if (ROOT / f).is_file():
            z.write(ROOT / f, f)
    z.write(ROOT / "docs" / "MANUAL.md", "MANUAL.md")        # the user manual of this version
print(out)

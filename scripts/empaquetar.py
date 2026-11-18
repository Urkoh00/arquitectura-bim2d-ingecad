# SPDX-License-Identifier: GPL-3.0-or-later
"""Crea dist/Arquitectura_IngeCAD_<version>.zip listo para instalar en IngeCAD.

Uso:  python scripts/empaquetar.py
"""
import re
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
version = re.search(r'_VERSION\s*=\s*"([^"]+)"', (ROOT / "arquitectura" / "__init__.py").read_text(encoding="utf-8")).group(1)
out = ROOT / "dist" / f"Arquitectura_IngeCAD_v{version}.zip"
out.parent.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT / "scripts"))
from bundle_roundtrip import bundle  # noqa: E402

GUIDE = ROOT / "docs" / "GUIA_DEL_CODIGO.md"


def guide_text():
    """La guía del código con la versión de este paquete."""
    text = GUIDE.read_text(encoding="utf-8")
    text, n = re.subn(r"Versión de referencia: \*\*[^*]+\*\*", f"Versión de referencia: **{version}**", text, count=1)
    if not n:
        raise SystemExit("La guía del código no tiene la línea «Versión de referencia»")
    return text


with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z, tempfile.TemporaryDirectory() as tmp:
    # the plugin, the IngeTrazo extension and, so whoever installs from the
    # ZIP can reproduce the checks, the tests, this script and the docs
    for base in ("arquitectura", "ingetrazo_ext", "tests", "scripts", "docs"):
        for f in sorted((ROOT / base).rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts and "arq_shared" not in f.parts \
                    and f != GUIDE:
                z.write(f, f.relative_to(ROOT))
    # el código compartido con la extensión, copiado ahora de su fuente
    shared = Path(tmp) / "arq_shared"
    bundle(shared)
    for f in sorted(shared.rglob("*")):
        if f.is_file():
            z.write(f, Path("ingetrazo_ext") / "arq_shared" / f.relative_to(shared))
    # la guía del código, con la versión de este paquete, en docs/ y en la raíz
    z.writestr("docs/GUIA_DEL_CODIGO.md", guide_text())
    z.writestr(f"GUIA_DEL_CODIGO_v{version}.md", guide_text())
    for f in ("LICENSE", "README.md", "CHANGELOG.md", "pytest.ini", "requirements-dev.txt"):
        if (ROOT / f).is_file():
            z.write(ROOT / f, f)
    z.write(ROOT / "docs" / "MANUAL.md", "MANUAL.md")        # the user manual of this version
print(out)

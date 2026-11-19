# SPDX-License-Identifier: GPL-3.0-or-later
"""El ZIP de cada versión lleva la guía del código con su versión y el código
compartido con IngeTrazo recién copiado de su fuente (v1.29)."""
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_zip_lleva_la_guia_con_su_version_y_el_codigo_compartido(tmp_path):
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "empaquetar.py")],
                         capture_output=True, text=True, check=True).stdout.strip().splitlines()[-1]
    version = re.search(r'_VERSION\s*=\s*"([^"]+)"',
                        (ROOT / "arquitectura" / "__init__.py").read_text(encoding="utf-8")).group(1)
    with zipfile.ZipFile(out) as z:
        names = set(z.namelist())
        assert f"MANUAL_v{version}.md" in names       # el manual, con la versión en el nombre
        for name in (f"GUIA_DEL_CODIGO_v{version}.md", "docs/GUIA_DEL_CODIGO.md"):
            assert f"Versión de referencia: **{version}**" in z.read(name).decode("utf-8")
        manifest = json.loads(z.read("ingetrazo_ext/arq_shared/MANIFEST.json"))
        assert "defensas.py" in manifest and "particiones_virtuales.py" in manifest
        for name, sha in manifest.items():
            data = z.read(f"ingetrazo_ext/arq_shared/{name}")
            assert data == (ROOT / "arquitectura" / name).read_bytes()
            assert hashlib.sha256(data).hexdigest() == sha
        assert "MANUAL.md" in names

# SPDX-License-Identifier: GPL-3.0-or-later
"""Rutas de las pruebas.

- La raíz de este repositorio (paquetes ``arquitectura``, ``ingetrazo_ext``, ``tests``).
- Las fuentes de IngeCAD: variable de entorno ``INGECAD_SRC`` o, si no existe,
  una carpeta ``ingecad`` junto a este repositorio (``../ingecad``).
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# La batería prueba todas las funciones: perfil Modelo Térmico, que lo incluye
# todo. Las pruebas de los perfiles fijan el suyo (tests/test_perfiles.py).
os.environ.setdefault("ARQ_PERFIL", "termico")
INGECAD = Path(os.environ.get("INGECAD_SRC", ROOT.parent / "ingecad")).resolve()

for p in (str(ROOT), str(INGECAD)):
    if p not in sys.path:
        sys.path.insert(0, p)

if not (INGECAD / "core").is_dir():
    raise SystemExit(
        f"No encuentro las fuentes de IngeCAD en {INGECAD}. Clone "
        "https://github.com/ingelibre/ingecad junto a este repositorio o defina INGECAD_SRC.")

# El código compartido con la extensión de IngeTrazo (ingetrazo_ext/arq_shared)
# no se guarda en el repositorio: se copia de su fuente antes de las pruebas,
# como al construir el ZIP (scripts/bundle_roundtrip.py).
if (ROOT / "scripts" / "bundle_roundtrip.py").is_file():
    sys.path.insert(0, str(ROOT / "scripts"))
    from bundle_roundtrip import bundle  # noqa: E402
    bundle()

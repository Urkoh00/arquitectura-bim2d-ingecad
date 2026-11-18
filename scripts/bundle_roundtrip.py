# SPDX-License-Identifier: GPL-3.0-or-later
"""Copia literal del código del plugin que necesita la extensión de IngeTrazo.

La extensión (ingetrazo_ext/_arq_edit.py) regenera en IngeTrazo los elementos
cambiados con EL MISMO código que los generó en IngeCAD: nunca una segunda
implementación. Ese código se copia a ``ingetrazo_ext/arq_shared/``:

- al construir el ZIP de cada versión (scripts/empaquetar.py);
- al ejecutar las pruebas (tests/conftest.py).

La carpeta NO se guarda en el repositorio (.gitignore): así no puede quedar
desfasada respecto de su fuente. MANIFEST.json lleva el SHA-256 de cada copia.

Uso:  python scripts/bundle_roundtrip.py   (escribe ingetrazo_ext/arq_shared)
"""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "arquitectura"
# módulos sin dependencias del anfitrión que usa la extensión (directa o
# indirectamente, desde exchange.py y roundtrip_model.py)
FILES = ["roundtrip_model.py", "architectural.py", "exchange.py", "openings.py", "cabinets.py",
         "curved_carpentry.py", "wall_categories.py", "defensas.py", "particiones_virtuales.py"]


def bundle(target=ROOT / "ingetrazo_ext" / "arq_shared"):
    """Escribe la copia en ``target`` y devuelve su manifiesto {fichero: sha256}."""
    target = Path(target)
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / "__init__.py").write_text("# SPDX-License-Identifier: GPL-3.0-or-later\n")
    files = FILES + [str(p.relative_to(SOURCE)) for p in sorted((SOURCE / "geom").glob("*.py"))]
    manifest = {}
    for name in files:
        p = target / name
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SOURCE / name, p)
        manifest[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    (target / "MANIFEST.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    print(f"{len(bundle())} ficheros copiados en ingetrazo_ext/arq_shared")

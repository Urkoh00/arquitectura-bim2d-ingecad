# SPDX-License-Identifier: GPL-3.0-or-later
"""F5 cambia la cara de MURO en la ventana real de IngeCAD (proceso aparte)."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import INGECAD


def test_f5_en_ventana_real():
    pytest.importorskip("PySide6.QtTest")
    env = {**os.environ, "INGECAD_SRC": str(INGECAD),
           "QT_QPA_PLATFORM": os.environ.get("QT_QPA_PLATFORM", "offscreen")}
    script = Path(__file__).with_name("ventana_f5.py")
    proc = subprocess.run([sys.executable, "-I", str(script)], env=env, capture_output=True,
                          text=True, timeout=120)
    line = next((l for l in proc.stdout.splitlines() if l.startswith("RESULTADO ")), None)
    assert line, proc.stdout[-2000:] + proc.stderr[-3000:]
    r = json.loads(line[len("RESULTADO "):])
    assert r == {"lienzo": "derecha", "linea_ordenes": "izquierda",
                 "tras_cancelar": "izquierda", "atajo_retirado": True}

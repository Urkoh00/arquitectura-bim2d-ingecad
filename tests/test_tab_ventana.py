# SPDX-License-Identifier: GPL-3.0-or-later
"""Tab fija las cotas de MURO en la ventana real de IngeCAD (proceso aparte)."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import INGECAD


def test_tab_en_ventana_real():
    pytest.importorskip("PySide6.QtTest")
    env = {**os.environ, "INGECAD_SRC": str(INGECAD),
           "QT_QPA_PLATFORM": os.environ.get("QT_QPA_PLATFORM", "offscreen")}
    script = Path(__file__).with_name("ventana_tab.py")
    proc = subprocess.run([sys.executable, "-I", str(script)], env=env, capture_output=True,
                          text=True, timeout=120)
    line = next((l for l in proc.stdout.splitlines() if l.startswith("RESULTADO ")), None)
    assert line, proc.stdout[-2000:] + proc.stderr[-3000:]
    r = json.loads(line[len("RESULTADO "):])
    assert r == {"inicio": [0.0, 0.0], "fijadas": {"length": 5.0}, "activa": "angle",
                 "linea_vacia": True, "foco_en_linea": True, "muros": 1,
                 "extremo": [0.0, 5.0], "sin_orden": "ok"}

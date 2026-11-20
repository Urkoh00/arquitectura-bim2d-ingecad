# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: aísla los abortos de Qt para probar órdenes sin crear QApplication.
import os
from pathlib import Path
import subprocess
import sys


def invocar_orden_sin_qt(orden, preparacion=""):
    programa = (
        """
import sys
from types import SimpleNamespace
sys.path[:0] = [sys.argv[1], sys.argv[2]]
from arquitectura import plugin_spec
from tests.test_wall_tools import Session
spec = plugin_spec()
sesion = Session(spec)
contexto = SimpleNamespace(document=sesion.document, execute=sesion.history.execute, echo=sesion.out.append, prompt=sesion.out.append, finish=lambda: None, services=sesion.services)
argumentos = []
"""
        + preparacion
        + """
profundidad = sesion.history.depth
spec.commands[sys.argv[3]](contexto, *argumentos)
assert sesion.history.depth == profundidad
print('SIN_ABORTAR', sesion.out)
"""
    )
    resultado = subprocess.run(
        [
            sys.executable,
            "-c",
            programa,
            os.environ["INGECAD_SRC"],
            str(Path(__file__).resolve().parents[1]),
            orden,
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert "SIN_ABORTAR" in resultado.stdout
    return resultado.stdout

# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: las fichas de niveles informan sin abortar cuando no existe QApplication.
import os
from pathlib import Path
import subprocess
import sys
import pytest


@pytest.mark.parametrize("orden", ["NIVELES", "NIVELASIGNAR"])
def test_orden_de_niveles_sin_aplicacion_qt_no_aborta(orden):
    raiz = Path(__file__).resolve().parents[1]
    programa = """
import sys
sys.path[:0] = [sys.argv[1], sys.argv[2]]
from arquitectura import plugin_spec
from tests.test_wall_tools import Session
from tools.base import ToolContext
spec = plugin_spec()
sesion = Session(spec)
contexto = ToolContext(execute=sesion.history.execute, echo=sesion.out.append, prompt=sesion.out.append, finish=lambda: None, services=sesion.services)
spec.commands[sys.argv[3]](contexto)
assert sesion.history.depth == 0
assert any('ventana' in str(texto).lower() for texto in sesion.out), sesion.out
print('SIN_ABORTAR', sesion.out)
"""
    resultado = subprocess.run(
        [sys.executable, "-c", programa, os.environ["INGECAD_SRC"], str(raiz), orden],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert "SIN_ABORTAR" in resultado.stdout

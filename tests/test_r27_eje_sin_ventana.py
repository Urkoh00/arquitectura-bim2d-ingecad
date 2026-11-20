# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: las fichas de ejes no abortan el proceso cuando falta una ventana Qt.
import os
from pathlib import Path
import subprocess
import sys
import pytest


@pytest.mark.parametrize('opcion', ['ficha', 'separaciones', 'tabla'])
def test_eje_sin_aplicacion_qt_informa_sin_abortar(opcion):
    script = Path(__file__).with_name('probar_eje_sin_ventana.py')
    resultado = subprocess.run([sys.executable, '-I', str(script), opcion], env=os.environ.copy(),
                               capture_output=True, text=True, timeout=20)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert 'SIN CIERRE' in resultado.stdout

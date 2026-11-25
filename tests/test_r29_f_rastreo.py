# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: el controlador de IngeCAD entrega a las órdenes el punto alineado por OTRACK.
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tests.conftest import INGECAD


@pytest.mark.parametrize('orden', ['MUROPARALELO', 'ESTIRAMURO', 'CARPINTERIA', 'ARMARIOBIM', 'MOVERCARP', 'MURO', 'MUROCURVO', 'PILAR', 'RECINTO', 'FORJADO'])
def test_otrack_entrega_el_punto_alineado(orden, tmp_path):
    pytest.importorskip('PySide6.QtTest')
    entorno = dict(os.environ)
    entorno.update({'INGECAD_SRC': str(INGECAD), 'ARQ_PERFIL': 'planos',
                    'XDG_CONFIG_HOME': str(tmp_path / 'config'),
                    'QT_QPA_PLATFORM': os.environ.get('QT_QPA_PLATFORM', 'offscreen')})
    guion = Path(__file__).with_name('ventana_otrack_r29.py')
    proceso = subprocess.run([sys.executable, '-I', str(guion), orden, str(tmp_path)],
                             env=entorno, capture_output=True, text=True, timeout=120)
    linea = next((linea for linea in proceso.stdout.splitlines() if linea.startswith('RESULTADO ')), None)
    assert proceso.returncode == 0 and linea, proceso.stdout[-2000:] + proceso.stderr[-3000:]
    datos = json.loads(linea.removeprefix('RESULTADO '))
    assert not datos['excepciones']
    assert datos['adquiridos'], datos
    assert datos['guia'], datos
    assert len(datos['entregados']) == 1
    punto = datos['entregados'][0]
    assert punto == pytest.approx(datos['resuelto'])
    assert punto[1] == pytest.approx(datos['origen'][1])
    assert abs(punto[1] - datos['cursor'][1]) > 0.005
    if orden in ('MUROPARALELO', 'ESTIRAMURO', 'MOVERCARP'):
        assert datos['seleccion_inicial']

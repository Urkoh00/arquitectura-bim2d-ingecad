# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: las teclas llegan a las órdenes escritas, con fichas reales y con variantes por texto.
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.escenarios_r27 import preparar


@pytest.mark.parametrize("orden", ["MURO", "-MURO", "CARPINTERIA", "-CARPINTERIA", "MOVERCARP"])
def test_teclas_y_tab_se_entregan_a_la_orden_activa(plugin, tmp_path, orden):
    semilla = tmp_path / "semilla"
    semilla.mkdir()
    preparar(plugin).document.save_as(semilla / "modelo.dxf")
    destino = tmp_path / "resultado"
    if orden.endswith("MURO"):
        respuestas = [
            {"tecla": "F5"},
            "70,20",
            {"texto": "5", "tecla": "Tab"},
            {"texto": "90", "tecla": "Return"},
            "",
        ]
    elif orden == "MOVERCARP":
        respuestas = [
            "2.03,0.6",
            {"tecla": "F4"},
            {"tecla": "F6"},
            {"texto": "1", "tecla": "Tab"},
            {"tecla": "Tab", "atras": True},
            "",
        ]
    else:
        respuestas = [
            {"tecla": "F4"},
            {"tecla": "F6"},
            {"tecla": "Tab"},
            {"tecla": "Tab", "atras": True},
            "5,0.15",
            "7,0.15",
            "",
        ]
    entorno = {
        **os.environ,
        "R27_SEMILLA": str(semilla),
        "R27_RESPUESTAS": json.dumps(respuestas),
        "R27_VERIFICAR": "0",
    }
    proceso = subprocess.run(
        [
            sys.executable,
            "-I",
            str(Path(__file__).with_name("ventana_r27.py")),
            orden,
            str(destino),
        ],
        env=entorno,
        capture_output=True,
        text=True,
        timeout=40,
    )
    assert proceso.returncode == 0, proceso.stdout + proceso.stderr
    datos = json.loads((destino / "resultado.json").read_text())
    if orden.startswith("-"):
        assert datos["cuadros"] == []
    teclas = [r for r in datos["respuestas"] if isinstance(r, dict)]
    if orden.endswith("MURO"):
        assert teclas[0]["antes"]["reference"] != teclas[0]["despues"]["reference"]
        assert teclas[1]["despues"]["tab_locks"]["length"] == 5.0
        assert any(
            r.get("kind") == "wall" and r.get("a") == [70.0, 20.0] and r.get("b") == [70.0, 25.0]
            for r in datos["registros"]
        )
    else:
        assert teclas[0]["antes"]["dim_axis"] != teclas[0]["despues"]["dim_axis"]
        assert teclas[1]["antes"]["dim_active"] != teclas[1]["despues"]["dim_active"]
        assert teclas[2]["antes"]["dim_active"] != teclas[2]["despues"]["dim_active"]
        assert teclas[3]["antes"]["dim_active"] != teclas[3]["despues"]["dim_active"]

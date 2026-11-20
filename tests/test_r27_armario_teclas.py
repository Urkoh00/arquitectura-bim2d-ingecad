# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: ARMARIOBIM no recibe los estados de cotas que solo inicializa CARPINTERIA.
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session
from tests.test_r27_creacion_texto import responder
from tests.escenarios_r27 import preparar


@pytest.mark.parametrize("orden", ["ARMARIOBIM", "-ARMARIOBIM"])
@pytest.mark.parametrize("tecla", ["F4", "F6", "Tab"])
def test_teclas_no_aplicables_no_acceden_a_cotas_sin_inicializar(plugin, orden, tecla):
    sesion = Session(plugin)
    herramienta = sesion.tool(orden)
    if orden.startswith("-"):
        responder(herramienta)
    if tecla == "Tab":
        assert herramienta.tab_ready() is False
        assert herramienta.on_tab() is False
    else:
        assert herramienta.on_key(tecla) is False
    assert sesion.history.depth == 0


@pytest.mark.parametrize("orden", ["ARMARIOBIM", "-ARMARIOBIM"])
def test_armario_se_coloca_tras_pulsar_teclas_en_mainwindow(plugin, tmp_path, orden):
    semilla = tmp_path / "semilla"
    semilla.mkdir()
    preparar(plugin).document.save_as(semilla / "modelo.dxf")
    destino = tmp_path / "resultado"
    respuestas = [{"tecla": tecla} for tecla in ("F4", "F6", "Tab")] + ["6,0.15", ""]
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
    assert not datos["excepciones"]
    assert "AttributeError" not in datos["historial"]
    assert any(r.get("cabinet") for r in datos["registros"] if r.get("kind") == "opening")
    if orden.startswith("-"):
        assert datos["cuadros"] == []

# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: un espacio escrito pertenece al nombre o al perfil, sin ejecutar una respuesta incompleta.
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.escenarios_r27 import preparar


@pytest.mark.parametrize(
    "orden,respuestas,clase,campo,esperado",
    [
        ("RECINTO", ["nombre", "Centro norte", "5,4", ""], "space", "name", "Centro norte"),
        ("PILAR", ["seccion", "IPE 200", "70,20", ""], "column", "profile", "IPE 200"),
    ],
)
def test_texto_con_espacios_por_teclado_en_mainwindow(
    plugin, tmp_path, orden, respuestas, clase, campo, esperado
):
    semilla = tmp_path / "semilla"
    semilla.mkdir()
    preparar(plugin).document.save_as(semilla / "modelo.dxf")
    destino = tmp_path / "resultado"
    entorno = {
        **os.environ,
        "R27_SEMILLA": str(semilla),
        "R27_RESPUESTAS": json.dumps(respuestas),
        "R27_VERIFICAR": "0",
    }
    script = Path(__file__).with_name("ventana_r27.py")
    proceso = subprocess.run(
        [sys.executable, "-I", str(script), orden, str(destino)],
        env=entorno,
        capture_output=True,
        text=True,
        timeout=40,
    )
    assert proceso.returncode == 0, proceso.stdout + proceso.stderr
    datos = json.loads((destino / "resultado.json").read_text())
    assert not datos["excepciones"]
    assert any(
        r.get("kind") == clase and r.get(campo) == esperado for r in datos["registros"]
    ), datos["historial"]


@pytest.mark.parametrize(
    "orden,respuestas",
    [
        ("EJES", ["x 1x3", "y 1x4", "70,20"]),
        ("EDITAREJE", ["50,2", "renumerar 4"]),
    ],
)
def test_opciones_con_argumento_en_la_misma_respuesta(plugin, tmp_path, orden, respuestas):
    semilla = tmp_path / "semilla"
    semilla.mkdir()
    preparar(plugin).document.save_as(semilla / "modelo.dxf")
    destino = tmp_path / "resultado"
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
    ejes = [r for r in datos["registros"] if r.get("kind") == "grid_axis"]
    if orden == "EJES":
        assert len(ejes) == 8, datos["historial"]
    else:
        assert any(r.get("label") == "4" for r in ejes), datos["historial"]

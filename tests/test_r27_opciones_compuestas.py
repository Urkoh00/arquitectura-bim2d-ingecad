# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: las opciones anunciadas con varias palabras llegan completas a su herramienta.
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.escenarios_r27 import preparar


@pytest.mark.parametrize(
    "orden,respuestas,comprobacion",
    [
        ("RECINTO", ["falso techo", "2,5", "5,4", ""], "techo"),
        ("PILAR", ["un paramento", "0,05", "8,0.15", "8,1", ""], "pilar"),
        ("CARPINTERIA", ["tipo de apertura", "corredera", "5,0.15", "7,0.15", ""], "apertura"),
        ("CARPINTERIA", ["ajuste cerco", "exterior", "5,0.15", "7,0.15", ""], "cara"),
        (
            "CARPINTERIA",
            ["punto de insercion", "medio", "modo", "distancia 1", "5,0.15", ""],
            "insercion",
        ),
    ],
)
def test_opcion_compuesta_por_teclado(plugin, tmp_path, orden, respuestas, comprobacion):
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
    assert "Point or option keyword required" not in datos["historial"], datos["historial"]
    registros = datos["registros"]
    if comprobacion == "techo":
        assert any(
            r.get("kind") == "space" and r.get("ceiling") is True and r.get("height") == 2.5
            for r in registros
        )
    elif comprobacion == "pilar":
        assert sum(r.get("kind") == "column" for r in registros) == 2
    elif comprobacion == "apertura":
        assert any(
            r.get("kind") == "opening" and r.get("operation") == "SLIDING" for r in registros
        )
    elif comprobacion == "cara":
        assert any(r.get("kind") == "opening" and r.get("face") == "exterior" for r in registros)
    else:
        assert sum(r.get("kind") == "opening" for r in registros) == 2

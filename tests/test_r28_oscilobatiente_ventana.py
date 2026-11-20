# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: inserta ambas manos por la ficha real y por texto, sin cuadros en la variante con guion.
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session


@pytest.mark.parametrize("orden", ["VENTANAARQ", "-VENTANAARQ"])
@pytest.mark.parametrize("bisagra", [0, 1])
def test_oscilobatiente_por_teclado_en_mainwindow(plugin, tmp_path, orden, bisagra):
    sesion = Session(plugin)
    muro = sesion.tool("MURO")
    muro.on_point((0.0, 0.0))
    muro.on_point((8.0, 0.0))
    muro.on_enter()
    identidades = set(sesion.walls())
    semilla = tmp_path / "semilla"
    semilla.mkdir()
    sesion.document.save_as(semilla / "modelo.dxf")
    destino = tmp_path / "resultado"
    entorno = {
        **os.environ,
        "R27_SEMILLA": str(semilla),
        "R27_RESPUESTAS": json.dumps(["2,0.15", "4,0.15", ""]),
        "R27_VALORES": json.dumps(
            {
                "operation": "TILTANDTURN",
                "hinge": "Inicial" if bisagra == 0 else "Final",
            }
        ),
        "R27_VALORES_CUADRO": json.dumps({"operation": "TILTANDTURN", "hinge": bisagra}),
        "R27_VERIFICAR": os.environ.get("R28_COMPROBAR_DWG", "0"),
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
        timeout=55,
    )
    (tmp_path / "proceso.log").write_text(proceso.stdout + proceso.stderr)
    assert proceso.returncode == 0, proceso.stdout + proceso.stderr
    datos = json.loads((destino / "resultado.json").read_text())
    assert not datos["excepciones"]
    assert len(datos["cuadros"]) == (0 if orden.startswith("-") else 1)
    assert {r["id"] for r in datos["registros"] if r["kind"] == "wall"} == identidades
    aberturas = [r for r in datos["registros"] if r["kind"] == "opening"]
    assert len(aberturas) == 1
    assert aberturas[0]["operation"] == "TILTANDTURN"
    assert aberturas[0]["hinge"] == bisagra
    if not orden.startswith("-"):
        assert (destino / "ficha_editada.png").exists()
    if entorno["R27_VERIFICAR"] == "1":
        pruebas = datos["verificaciones"]
        assert pruebas["deshacer_exacto"] and pruebas["rehacer_exacto"]
        assert pruebas["uniones_idempotente"]
        assert pruebas["incidencias_antes"] == pruebas["incidencias_despues"] == []
        assert all(p["datos_bim_iguales"] and p["contrato_valido"] for p in pruebas["persistencia"])

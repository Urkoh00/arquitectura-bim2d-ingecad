# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: crea una oscilobatiente doble con manilla mediante teclado en MainWindow real.
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session


@pytest.mark.parametrize("orden", ["VENTANAARQ", "-VENTANAARQ"])
@pytest.mark.parametrize("principal", ["left", "right"])
def test_la_principal_y_manilla_por_ficha_y_texto_en_ventana(plugin, tmp_path, orden, principal):
    sesion = Session(plugin)
    muro = sesion.tool("MURO")
    muro.on_point((0.0, 0.0))
    muro.on_point((8.0, 0.0))
    muro.on_enter()
    semilla = tmp_path / "semilla"
    semilla.mkdir()
    sesion.document.save_as(semilla / "modelo.dxf")
    destino = tmp_path / "resultado"
    entorno = {
        **os.environ,
        "R27_SEMILLA": str(semilla),
        "R27_TAMANO": "2400,1500",
        "R27_RESPUESTAS": json.dumps(["2,0.15", "4,0.15", ""]),
        "R27_VALORES": json.dumps(
            {
                "operation": "TILTANDTURN",
                "leaves": "2",
                "main_leaf": "Izquierda" if principal == "left" else "Derecha",
                "handle_height": "1,35",
                "handle_material": "Acero",
            }
        ),
        "R27_VALORES_CUADRO": json.dumps(
            {
                "operation": "TILTANDTURN",
                "leaves": 2,
                "main_leaf": principal,
                "handle_height": 1.35,
                "handle_material": "Acero",
            }
        ),
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
        timeout=70,
    )
    (tmp_path / "proceso.log").write_text(proceso.stdout + proceso.stderr)
    assert proceso.returncode == 0, proceso.stdout + proceso.stderr
    datos = json.loads((destino / "resultado.json").read_text())
    assert not datos["excepciones"]
    if os.environ.get("QT_QPA_PLATFORM") == "xcb":
        assert datos["plataforma"] == "xcb"
    assert len(datos["cuadros"]) == (0 if orden.startswith("-") else 1)
    ventanas = [r for r in datos["registros"] if r["kind"] == "opening"]
    assert len(ventanas) == 1
    assert ventanas[0]["leaves"] == 2 and ventanas[0]["main_leaf"] == principal
    assert ventanas[0]["handle_height"] == 1.35 and ventanas[0]["handle_material"] == "Acero"
    if entorno["R27_VERIFICAR"] == "1":
        pruebas = datos["verificaciones"]
        assert pruebas["deshacer_exacto"] and pruebas["rehacer_exacto"]
        assert pruebas["uniones_idempotente"]
        assert pruebas["incidencias_antes"] == pruebas["incidencias_despues"] == []
        assert all(p["datos_bim_iguales"] and p["contrato_valido"] for p in pruebas["persistencia"])

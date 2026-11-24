# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: configura las nuevas manillas por teclado en fichas y variantes de órdenes.
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session


@pytest.mark.parametrize("orden", ["PUERTAARQ", "-PUERTAARQ", "VENTANAARQ", "-VENTANAARQ"])
def test_manillas_por_ficha_y_por_texto_en_mainwindow(plugin, tmp_path, orden):
    sesion = Session(plugin)
    muro = sesion.tool("MURO")
    muro.on_point((0, 0))
    muro.on_point((8, 0))
    muro.on_enter()
    semilla = tmp_path / "semilla"
    semilla.mkdir()
    sesion.document.save_as(semilla / "modelo.dxf")
    puerta = "PUERTA" in orden
    valores = {"operation": "SWINGING" if puerta else "TILTANDTURN", "leaves": 2}
    if puerta:
        valores.update(leaf=0.825, leaf2=0.725, handles_mode="ambas")
    else:
        valores.update(handles=2)
    texto = {clave: str(valor) for clave, valor in valores.items()}
    texto["handles_mode"] = "Ambas"
    destino = tmp_path / "resultado"
    entorno = {
        **os.environ, "R27_SEMILLA": str(semilla), "R27_TAMANO": "2400,1500",
        "R27_RESPUESTAS": json.dumps(["2,0.15", "4,0.15", ""]),
        "R27_VALORES": json.dumps(texto), "R27_VALORES_CUADRO": json.dumps(valores),
        "R27_VERIFICAR": os.environ.get("R28_COMPROBAR_DWG", "0"),
    }
    proceso = subprocess.run(
        [sys.executable, "-I", str(Path(__file__).with_name("ventana_r27.py")), orden, str(destino)],
        env=entorno, capture_output=True, text=True, timeout=90,
    )
    (tmp_path / "proceso.log").write_text(proceso.stdout + proceso.stderr)
    assert proceso.returncode == 0, proceso.stdout + proceso.stderr
    datos = json.loads((destino / "resultado.json").read_text())
    assert not datos["excepciones"]
    assert len(datos["cuadros"]) == (0 if orden.startswith("-") else 1)
    if entorno["QT_QPA_PLATFORM"] == "xcb":
        assert datos["plataforma"] == "xcb"
    registros = [registro for registro in datos["registros"] if registro["kind"] == "opening"]
    assert len(registros) == 1
    assert registros[0]["handles_mode" if puerta else "handles"] == ("ambas" if puerta else 2)
    if entorno["R27_VERIFICAR"] == "1":
        pruebas = datos["verificaciones"]
        assert pruebas["deshacer_exacto"] and pruebas["rehacer_exacto"]
        assert pruebas["uniones_idempotente"]
        assert pruebas["incidencias_antes"] == pruebas["incidencias_despues"] == []
        assert all(paso["datos_bim_iguales"] and paso["contrato_valido"]
                   for paso in pruebas["persistencia"])

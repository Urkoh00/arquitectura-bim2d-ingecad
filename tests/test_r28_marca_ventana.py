# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: la marca se edita por teclado en la ficha real y en -PROPIEDADESARQ, con igual resultado.
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_r28_marcas_dibujo import modelo


@pytest.mark.parametrize("orden", ["PROPIEDADESARQ", "-PROPIEDADESARQ"])
def test_edicion_real_de_marca_conserva_la_identidad(plugin, tmp_path, orden):
    sesion, memoria, _ = modelo(plugin)
    _, cambio = memoria.preparar(sesion.document.doc)
    sesion.history.execute(cambio)
    identidades = {
        sesion.meta(e)["id"]
        for e in sesion.document.doc.modelspace()
        if (sesion.meta(e) or {}).get("kind") == "opening"
    }
    semilla = tmp_path / "semilla"
    semilla.mkdir()
    sesion.document.save_as(semilla / "modelo.dxf")
    destino = tmp_path / "resultado"
    entorno = {
        **os.environ,
        "R27_SEMILLA": str(semilla),
        "R27_RESPUESTAS": json.dumps(["1.03,0.6"]),
        "R27_VALORES": json.dumps({"mark": "P8"}),
        "R27_VALORES_CUADRO": json.dumps({"mark": "P8"}),
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
    assert any(
        r.get("mark") == "P8" and r.get("mark_manual")
        for r in datos["registros"]
        if r.get("kind") == "opening"
    )
    assert {r["id"] for r in datos["registros"] if r.get("kind") == "opening"} == identidades
    assert not datos["excepciones"]
    assert len(datos["cuadros"]) == (0 if orden.startswith("-") else 1)

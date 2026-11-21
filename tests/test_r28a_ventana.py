# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: genera y actualiza el plano por teclado en MainWindow y conserva pruebas DXF/DWG.
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.escenario_r28 import modelo_carpinterias
from tests.escenarios_r27 import modulo
from tests.test_r28a_plano import generar


@pytest.mark.parametrize("orden", ["MEMORIACARP", "-MEMORIACARP"])
@pytest.mark.parametrize("actualizar", [False, True])
def test_generacion_y_actualizacion_en_ventana_real(plugin, tmp_path, orden, actualizar):
    sesion = modelo_carpinterias(plugin)
    plano = modulo(plugin, "memoria_plano")
    identidad = None
    if actualizar:
        generar(sesion, plugin)
        identidad = plano.planos(sesion.document.doc)[0][1]["id"]
        puerta = next(
            e
            for e in sesion.document.doc.modelspace()
            if (sesion.meta(e) or {}).get("kind") == "opening"
            and sesion.meta(e)["type"] == "door"
            and not sesion.meta(e).get("cabinet")
        )
        cambio = modulo(plugin, "architectural_v10").edit_opening(puerta, height=2.2)
        modulo(plugin, "transactions").apply_architectural_change(
            sesion.tool("MURO").ctx, cambio, kind="opening"
        )
        assert plano.avisos(sesion.document.doc)
    identidades = {
        sesion.meta(e)["id"]
        for e in sesion.document.doc.modelspace()
        if (sesion.meta(e) or {}).get("kind") in ("wall", "opening", "space")
    }
    semilla = tmp_path / "semilla"
    semilla.mkdir()
    sesion.document.save_as(semilla / "modelo.dxf")
    destino = tmp_path / "resultado"
    entorno = {
        **os.environ,
        "R27_SEMILLA": str(semilla),
        "R27_TITULO": "Ensayo sintético R28-A",
        "R27_TAMANO": "2400,1500",
        "R27_ORDEN_INICIAL": orden + (" Actualizar" if actualizar else ""),
        "R27_RESPUESTAS": json.dumps(
            [] if actualizar else (["30,30"] if orden.startswith("-") else ["", "30,30"])
        ),
        "R27_VALORES": "{}",
        "R27_VALORES_CUADRO": "{}",
        "R27_VERIFICAR": os.environ.get("R28_COMPROBAR_DWG", "0"),
        "R28_CAPTURAS_MEMORIA": "1",
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
        timeout=100,
    )
    (tmp_path / "proceso.log").write_text(proceso.stdout + proceso.stderr)
    assert proceso.returncode == 0, proceso.stdout + proceso.stderr
    datos = json.loads((destino / "resultado.json").read_text())
    assert not datos["excepciones"]
    if os.environ.get("QT_QPA_PLATFORM") == "xcb":
        assert datos["plataforma"] == "xcb"
    assert len(datos["cuadros"]) == (0 if actualizar or orden.startswith("-") else 1)
    assert {
        r["id"] for r in datos["registros"] if r.get("kind") in ("wall", "opening", "space")
    } == identidades
    memorias = [r for r in datos["registros"] if r.get("kind") == "carpentry_schedule"]
    assert len(memorias) == 1 and memorias[0]["rows"]
    armario = next(fila for fila in memorias[0]["rows"] if fila["marca"].startswith("A"))
    assert armario["unidades"] == 3 and armario["manos"] == {"izquierda": 2, "derecha": 1}
    if actualizar:
        assert memorias[0]["id"] == identidad
    assert all(
        (destino / nombre).is_file()
        for nombre in ("plano_general.png", "fichas_acotadas.png", "tabla_resumen.png")
    )
    if entorno["R27_VERIFICAR"] == "1":
        verificaciones = datos["verificaciones"]
        assert verificaciones["deshacer_exacto"] and verificaciones["rehacer_exacto"]
        assert verificaciones["uniones_idempotente"]
        assert not verificaciones["incidencias_despues"]
        assert all(
            p["datos_bim_iguales"]
            and p["contrato_valido"]
            and p["memoria_textos_iguales"]
            and p["memoria_cotas_iguales"]
            for p in verificaciones["persistencia"]
        )

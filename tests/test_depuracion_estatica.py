# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: impide nuevos avisos estáticos sin borrar los ya revisados por motivos de estilo.
from collections import Counter
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

import pytest


RAIZ = Path(__file__).resolve().parents[1]
REGLAS = "F,B023,B006,B008,E722"


def avisos(carpeta, raiz):
    proceso = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--isolated", "--select", REGLAS,
         "--output-format", "json", str(carpeta)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proceso.returncode in (0, 1), proceso.stdout + proceso.stderr
    return Counter(
        (aviso["code"], Path(aviso["filename"]).relative_to(raiz).as_posix(), aviso["message"])
        for aviso in json.loads(proceso.stdout)
    )


def test_no_aparecen_avisos_nuevos_sin_revision():
    pytest.importorskip("ruff", reason="Instale requirements-dev.txt para ejecutar la depuración")
    registro = json.loads(Path(__file__).with_name("ruff_admitido.json").read_text())
    assert importlib.metadata.version("ruff") == registro["ruff"], "Revisar avisos al cambiar Ruff"
    permitidos = Counter((aviso["code"], aviso["file"], aviso["message"])
                         for aviso in registro["warnings"])
    nuevos = avisos(RAIZ / "arquitectura", RAIZ) - permitidos
    assert not nuevos, "Avisos nuevos que requieren prueba y triaje: " + repr(nuevos)


def test_un_nombre_inexistente_produce_un_aviso_nuevo(tmp_path):
    pytest.importorskip("ruff")
    archivo = tmp_path / "ejemplo.py"
    archivo.write_text("print(nombre_inexistente)\n")
    resultado = avisos(archivo, tmp_path)
    assert any(codigo == "F821" for codigo, _, _ in resultado)

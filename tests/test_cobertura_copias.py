# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: la cobertura incorpora el código que el cargador real importa desde sus copias.
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


def test_la_copia_del_plugin_cuenta_como_su_fuente(tmp_path):
    pytest.importorskip("coverage")
    raiz = Path(__file__).resolve().parents[1]
    copia = tmp_path / "plugin" / "arquitectura" / "geom" / "soldadura.py"
    copia.parent.mkdir(parents=True)
    shutil.copyfile(raiz / "arquitectura" / "geom" / "soldadura.py", copia)
    programa = """
import coverage
import importlib.util
import sys
from pathlib import Path

carpeta, ruta, configuracion = map(Path, sys.argv[1:])
medicion = coverage.Coverage(config_file=str(configuracion),
                            data_file=str(carpeta / '.coverage'), data_suffix=True)
medicion.start()
especificacion = importlib.util.spec_from_file_location('soldadura_de_ensayo', ruta)
modulo = importlib.util.module_from_spec(especificacion)
especificacion.loader.exec_module(modulo)
soldador = modulo.Soldador(1e-7)
assert soldador.indice((0, 0, 0)) == soldador.indice((1e-9, 0, 0))
medicion.stop()
medicion.save()
union = coverage.Coverage(config_file=str(configuracion), data_file=str(carpeta / '.coverage'))
union.combine(data_paths=[str(carpeta)])
union.save()
union.json_report(outfile=str(carpeta / 'resultado.json'))
"""
    proceso = subprocess.run(
        [sys.executable, "-c", programa, str(tmp_path), str(copia), str(raiz / ".coveragerc")],
        cwd=raiz, capture_output=True, text=True,
    )
    assert proceso.returncode == 0, proceso.stdout + proceso.stderr
    datos = json.loads((tmp_path / "resultado.json").read_text())
    assert list(datos["files"]) == ["arquitectura/geom/soldadura.py"]
    assert datos["totals"]["covered_lines"] > 0

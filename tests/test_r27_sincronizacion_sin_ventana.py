# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: las rutas ausentes, errores y conflictos de sincronización no abren widgets sin Qt.
import pytest
from tests.ejecucion_sin_qt_r27 import invocar_orden_sin_qt


@pytest.mark.parametrize("caso", ["sin_ruta", "archivo_invalido", "conflicto"])
def test_sincronizacion_sin_qt_informa_y_no_aplica_cambios(caso):
    preparacion = """
from pathlib import Path
import json
import tempfile
carpeta = tempfile.TemporaryDirectory()
ruta = Path(carpeta.name) / 'cambios.arqcambios'
"""
    if caso == "archivo_invalido":
        preparacion += "ruta.write_text('{}')\nargumentos = [str(ruta)]\n"
    elif caso == "conflicto":
        preparacion += """
from arquitectura import roundtrip, roundtrip_model, architectural_v10
from arquitectura.transactions import apply_architectural_change
muro = sesion.tool('MURO')
muro.on_point((0., 0.))
muro.on_point((5., 0.))
muro.on_enter()
entidad = next(iter(sesion.walls().values()))
identidad = sesion.meta(entidad)['id']
origen = roundtrip.snapshot(sesion.document.doc)
nuevo, _ = roundtrip_model.propose(origen, identidad, {'height': 3.5})
ruta.write_text(json.dumps(roundtrip_model.changes(origen, nuevo)))
apply_architectural_change(muro.ctx, architectural_v10.edit_wall(entidad, height=3.2), kind='wall')
argumentos = [str(ruta)]
"""
    salida = invocar_orden_sin_qt("SINCRONIZARARQ", preparacion)
    assert "SINCRONIZARARQ" in salida
    if caso != "archivo_invalido":
        assert "-SINCRONIZARARQ" in salida

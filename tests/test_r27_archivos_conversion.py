# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: exportación, conflictos y clasificación se completan por texto con modelos sintéticos.
from copy import deepcopy
import json
import pytest
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session
from tests.test_r27_creacion_texto import responder
from tests.test_r27_configuracion_texto import modulo


def muro(sesion):
    herramienta = sesion.tool("MURO")
    herramienta.on_point((0.0, 0.0))
    herramienta.on_point((5.0, 0.0))
    herramienta.on_enter()
    return next(iter(sesion.walls().values()))


def test_exportacion_texto_es_el_mismo_contrato(plugin, tmp_path):
    sesion = Session(plugin)
    muro(sesion)
    herramienta = sesion.tool("-EXPORTARBIM")
    ruta = tmp_path / "Prueba térmica.arqbim"
    responder(herramienta, {"ruta": str(ruta)})
    contrato = json.loads(ruta.read_text())
    esperado = sesion.export(tmp_path)
    assert contrato["elements"] == esperado["elements"]
    assert sesion.history.depth == 1


@pytest.mark.parametrize(
    "conflicto,decision,altura", [(False, "keep", 3.5), (True, "keep", 3.2), (True, "apply", 3.5)]
)
def test_sincronizar_texto_con_y_sin_conflicto(plugin, tmp_path, conflicto, decision, altura):
    sesion = Session(plugin)
    entidad = muro(sesion)
    sincronizacion = modulo(plugin, "roundtrip")
    modelo = modulo(plugin, "roundtrip_model")
    origen = sincronizacion.snapshot(sesion.document.doc)
    identidad = sesion.meta(entidad)["id"]
    nuevo, _ = modelo.propose(origen, identidad, {"height": 3.5})
    ruta = tmp_path / "Cambios térmicos.arqcambios"
    ruta.write_text(json.dumps(modelo.changes(origen, nuevo)), encoding="utf-8")
    if conflicto:
        cambio = modulo(plugin, "architectural_v10").edit_wall(entidad, height=3.2)
        modulo(plugin, "transactions").apply_architectural_change(
            sesion.tool("MURO").ctx, cambio, kind="wall"
        )
    antes = deepcopy(sesion.meta(entidad))
    profundidad = sesion.history.depth
    herramienta = sesion.tool("-SINCRONIZARARQ")
    responder(herramienta, {"ruta": str(ruta), identidad: decision})
    assert sesion.meta(entidad)["height"] == altura
    assert sesion.meta(entidad)["id"] == identidad
    if not conflicto or decision == "apply":
        despues = deepcopy(sesion.meta(entidad))
        assert sesion.history.depth == profundidad + 1
        sesion.history.undo()
        assert sesion.meta(entidad) == antes
        sesion.history.redo()
        assert sesion.meta(entidad) == despues
    else:
        assert sesion.history.depth == profundidad


def test_sincronizar_archivo_invalido_permite_reintentar(plugin, tmp_path):
    sesion = Session(plugin)
    ruta = tmp_path / "invalido.arqcambios"
    ruta.write_text("{}")
    herramienta = sesion.tool("-SINCRONIZARARQ")
    herramienta.on_option(str(ruta))
    assert herramienta._campos_texto is not None
    assert sesion.history.depth == 0
    herramienta.on_cancel()


def test_clasificacion_texto_previsualiza_confirma_y_deshace(plugin):
    sesion = Session(plugin)
    dibujo = sesion.document.doc
    dibujo.layers.new("Muros origen")
    for y in (0.0, 0.2):
        dibujo.modelspace().add_line((0.0, y), (5.0, y), dxfattribs={"layer": "Muros origen"})
    antes = [(e.dxf.handle, e.dxf.layer) for e in dibujo.modelspace()]
    herramienta = sesion.tool("-LINEASAMURO")
    responder(herramienta, {"capa.Muros origen": "Muros"})
    herramienta.on_point((-1.0, -1.0))
    herramienta.on_point((6.0, 1.0))
    assert herramienta.conversion_preview is not None
    assert not sesion.walls()
    herramienta.on_option("confirmar")
    assert len(sesion.walls()) == 1
    despues = [sesion.meta(e) for e in dibujo.modelspace()]
    assert sesion.history.depth == 1
    sesion.history.undo()
    assert [(e.dxf.handle, e.dxf.layer) for e in dibujo.modelspace()] == antes
    sesion.history.redo()
    assert [sesion.meta(e) for e in dibujo.modelspace()] == despues

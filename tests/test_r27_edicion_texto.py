# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: editar por texto conserva identificadores y permite deshacer los datos BIM completos.
from copy import deepcopy
import pytest
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session
from tests.test_r27_creacion_texto import responder


@pytest.mark.parametrize("orden", ["-PROPIEDADESARQ", "-EDITARARQ"])
def test_edicion_muro_por_texto_conserva_identidad(plugin, orden):
    sesion = Session(plugin)
    muro = sesion.tool("MURO")
    muro.on_point((0.0, 0.0))
    muro.on_point((5.0, 0.0))
    muro.on_enter()
    entidad = next(iter(sesion.walls().values()))
    antes = deepcopy(sesion.meta(entidad))
    herramienta = sesion.tool(orden)
    herramienta.on_point((2.0, 0.1))
    responder(herramienta, {"height": "350cm", "name": "Muro de baño"})
    despues = deepcopy(sesion.meta(entidad))
    assert despues["height"] == 3.5
    assert despues["name"] == "Muro de baño"
    assert despues["id"] == antes["id"]
    sesion.history.undo()
    assert sesion.meta(entidad) == antes
    sesion.history.redo()
    assert sesion.meta(entidad) == despues


def test_editar_eje_por_texto_conserva_referencias(plugin):
    sesion = Session(plugin)
    rejilla = sesion.tool("EJES")
    rejilla.on_point((0.0, 0.0))
    ejes = [
        e
        for e in sesion.document.doc.modelspace()
        if (sesion.meta(e) or {}).get("kind") == "grid_axis"
    ]
    entidad = ejes[0]
    antes = deepcopy(sesion.meta(entidad))
    punto = tuple(entidad.get_points("xy")[0])
    herramienta = sesion.tool("-EDITAREJE")
    herramienta.on_point(punto)
    assert herramienta.entity is not None
    herramienta.on_option("ficha")
    responder(herramienta, {"label": "Eje técnico"})
    despues = deepcopy(sesion.meta(entidad))
    assert despues["id"] == antes["id"]
    assert despues["label"] == "Eje técnico"
    sesion.history.undo()
    assert sesion.meta(entidad) == antes
    sesion.history.redo()
    assert sesion.meta(entidad) == despues

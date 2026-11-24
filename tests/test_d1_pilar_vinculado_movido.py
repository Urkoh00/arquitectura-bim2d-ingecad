# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: actualizar los ejes conserva las transformaciones nativas de un pilar vinculado.
from copy import deepcopy

import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session
from tests.escenarios_r27 import modulo


@pytest.mark.parametrize("angulo_rejilla", [0.0, 30.0])
@pytest.mark.parametrize("transformacion", ["desplazar", "girar", "escalar", "reflejar"])
def test_actualizar_rejilla_conserva_el_pilar_movido_y_su_vinculo(
    plugin, angulo_rejilla, transformacion
):
    from core import actions, commands

    sesion = Session(plugin)
    rejilla = modulo(plugin, "grids")
    transacciones = modulo(plugin, "transactions")
    contexto = sesion.tool("MURO").ctx
    transacciones.apply_architectural_change(contexto, rejilla.create_grid((0, 0), {
        "x": "1x4", "y": "1x3", "angle": angulo_rejilla, "dimensions": False,
    }), kind="column")
    assert rejilla.place_columns(contexto, {
        "shape": "rect", "width": 0.3, "depth": 0.4, "height": 3.0, "base": 0.0,
    }, selected={3})
    pilar = next(entidad for entidad in sesion.document.doc.modelspace()
                 if (sesion.meta(entidad) or {}).get("kind") == "column")
    original = deepcopy(sesion.meta(pilar))
    if transformacion == "desplazar":
        cambio = actions.move_entities([pilar], 1.2, -0.4)
    elif transformacion == "girar":
        cambio = actions.rotate_entities([pilar], (0, 0), 37)
    elif transformacion == "escalar":
        cambio = actions.scale_entities([pilar], (0, 0), 1.2)
    else:
        cambio = actions.mirror_entities([pilar], (0, 0), (1, 0), keep_source=False)
    propietario = "ensayo-d1-pilar-vinculado"
    commands.register_reactor(modulo(plugin, "reactor").ArquitecturaReactor(), propietario)
    commands.register_reactor(rejilla.GridReactor(), propietario)
    try:
        sesion.history.execute(cambio)
        movido = deepcopy(sesion.meta(pilar))
        vertices = list(pilar.get_points("xy"))
        centro_geometrico = [sum(punto[eje] for punto in vertices) / len(vertices) for eje in (0, 1)]
        assert movido["center"] == pytest.approx(centro_geometrico)
        rejilla.update(contexto)
        actualizado = deepcopy(sesion.meta(pilar))
        assert actualizado["center"] == pytest.approx(centro_geometrico)
        assert actualizado["id"] == original["id"]
        for clave in ("u", "v", "grid_id"):
            assert actualizado["grid_link"][clave] == original["grid_link"][clave]
        sesion.history.undo()
        assert sesion.meta(pilar) == movido
        sesion.history.undo()
        assert sesion.meta(pilar) == original
        sesion.history.redo()
        assert sesion.meta(pilar) == movido
        sesion.history.redo()
        assert sesion.meta(pilar) == actualizado

        eje = next(entidad for entidad, registro in rejilla.axes(sesion.document.doc)
                   if registro["id"] == actualizado["grid_link"]["u"])
        ejes = {registro["id"]: entidad for entidad, registro in rejilla.axes(sesion.document.doc)}
        cruzado = ejes[actualizado["grid_link"]["v"]]
        cruce_inicial = rejilla.intersect(eje, cruzado)
        sesion.history.execute(actions.move_entities([eje], 1.0, 0.0))
        cruce_final = rejilla.intersect(eje, cruzado)
        esperado = [centro_geometrico[i] + cruce_final[i] - cruce_inicial[i] for i in (0, 1)]
        assert sesion.meta(pilar)["center"] == pytest.approx(esperado)
        assert sesion.meta(pilar)["id"] == original["id"]
        sesion.history.undo()
        assert sesion.meta(pilar) == actualizado
    finally:
        commands.unregister_reactors(propietario)

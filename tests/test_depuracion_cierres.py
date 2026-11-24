# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: reproduce los cierres señalados por el análisis sin aplicar correcciones de estilo.
import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session
from tests.escenarios_r27 import modulo


def test_los_carriles_se_consumen_antes_de_cambiar_la_iteracion(plugin, monkeypatch):
    aberturas = modulo(plugin, "openings")
    armarios = modulo(plugin, "cabinets")
    muro = modulo(plugin, "geom.junctions").Wall("muro", (0, 0), (5, 0), 0.3)
    datos = aberturas.normalise({
        "type": "door", "operation": "SLIDING", "offset": 1, "width": 1.2,
        "height": 2.1, "sill": 0, "leaves": 3, "frame_width": 0,
        "cabinet": True, "cabinet_mode": "nicho", "niche_depth": 0.2, "side": 1,
    })
    monkeypatch.setattr(aberturas, "plan_symbol", lambda forma, frente: [
        ("line", (frente["offset"], 0), (frente["offset"] + frente["width"], 0))
    ])
    simbolos = armarios._niche_symbols(muro, datos)
    assert [simbolo[1][1] for simbolo in simbolos] == pytest.approx([0, 0.03, 0])


def test_los_rangos_conservan_cada_categoria_en_su_iteracion(plugin):
    sesion = Session(plugin)
    dibujo = sesion.document.doc
    capas = {"caras": "muros", "divisiones": "particiones", "linderos": "medianeras"}
    espesores = {"muros": 0.3, "particiones": 0.1, "medianeras": 0.2}
    for indice, (capa, papel) in enumerate(capas.items()):
        dibujo.layers.new(capa)
        eje = indice * 3
        for separacion in (-espesores[papel] / 2, espesores[papel] / 2):
            dibujo.modelspace().add_line((0, eje + separacion), (4, eje + separacion),
                                        dxfattribs={"layer": capa})
    planes = modulo(plugin, "conversion_plan")
    clasificacion = planes.Classification(capas, thickness_ranges={
        "muros": (0.25, 0.35), "particiones": (0.08, 0.12), "medianeras": (0.18, 0.22),
    })
    plan = planes.analyse(dibujo, (-1, -1), (5, 8), clasificacion)
    assert len(plan.result[0]) == 3
    assert set(plan.wall_roles) == set(espesores)
    for (_, _, espesor), papel in zip(plan.result[0], plan.wall_roles):
        assert espesor == pytest.approx(espesores[papel])


def test_emit_no_difiere_el_papel_de_las_entidades_de_otras_capas(plugin):
    sesion = Session(plugin)
    dibujo = sesion.document.doc
    for capa in ("caras", "soportes"):
        dibujo.layers.new(capa)
    for y in (-0.15, 0.15):
        dibujo.modelspace().add_line((0, y), (4, y), dxfattribs={"layer": "caras"})
    dibujo.modelspace().add_lwpolyline(
        [(9, 9), (9.3, 9), (9.3, 9.3), (9, 9.3)], close=True,
        dxfattribs={"layer": "soportes"},
    )
    planes = modulo(plugin, "conversion_plan")
    plan = planes.analyse(dibujo, (-1, -1), (11, 11),
                          planes.Classification({"caras": "muros", "soportes": "pilares"}))
    assert len(plan.result[0]) == 1
    assert len(plan.result[4]) == 1


def test_el_contorno_descartado_sigue_validando_la_entrada_del_muro(plugin):
    crear = modulo(plugin, "architectural_v10").create_wall
    with pytest.raises(ValueError):
        crear((0, 0), (0, 0), 0.3)
    with pytest.raises(ValueError):
        crear((0, 0), (3, 0), 0)

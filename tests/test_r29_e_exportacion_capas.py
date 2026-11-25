# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: el contrato conserva la posición física de las capas y la auditoría no altera tipos antiguos.
from copy import deepcopy

import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session
from tests.escenarios_r27 import modulo


def vivienda(sesion, plugin, *, orden="exterior-interior", repetir_tipo=True):
    arquitectura = modulo(plugin, "architectural_v10")
    transacciones = modulo(plugin, "transactions")
    puntos = [(0, 0), (6, 0), (6, 4), (0, 4)]
    muros = []
    for i, (inicio, fin) in enumerate(zip(puntos, puntos[1:] + puntos[:1])):
        datos = {"layers": [[0.05, "Acabado"], [0.25, "Hoja"]],
                 "type_name": "Tipo de ensayo" if repetir_tipo else str(i), "wall_category": "fachada"}
        if orden is not None:
            datos["orden_capas"] = orden
        cambio = arquitectura.create_wall(inicio, fin, 0.3, **datos)
        transacciones.apply_architectural_change(sesion.tool("MURO").ctx, cambio)
        muros.append(cambio.entity)
    return muros


def test_el_contrato_coloca_el_tipo_desde_el_exterior_geometrico(plugin):
    sesion = Session(plugin)
    muros = vivienda(sesion, plugin)
    antes = [deepcopy(sesion.meta(muro)) for muro in muros]
    contrato = sesion.export(None)
    elementos = [e for e in contrato["elements"] if e["ifc_class"] == "IfcWall"]
    for elemento in elementos:
        assert elemento["params"]["cara_exterior_resuelta"] == "derecha"
        capa = elemento["params"]["capas_colocadas"][0]
        assert capa["material"] == "Acabado"
        assert capa["min"] == pytest.approx(-0.15)
        assert capa["max"] == pytest.approx(-0.10)
    assert [sesion.meta(muro) for muro in muros] == antes


def test_un_tipo_anterior_avisa_una_vez_sin_cambiar_sus_datos(plugin):
    sesion = Session(plugin)
    muros = vivienda(sesion, plugin, orden=None)
    antes = [deepcopy(sesion.meta(muro)) for muro in muros]
    informe = modulo(plugin, "quality").audit_architecture(sesion.document)
    avisos = [aviso for aviso in informe["incidencias"] if "orden de capas" in aviso]
    assert len(avisos) == 1
    assert "Tipo de ensayo" in avisos[0]
    assert [sesion.meta(muro) for muro in muros] == antes


def test_medianera_auto_no_adivina_y_la_anulacion_manual_se_exporta(plugin):
    sesion = Session(plugin)
    arquitectura = modulo(plugin, "architectural_v10")
    transacciones = modulo(plugin, "transactions")
    muro = arquitectura.create_wall((0, 0), (5, 0), 0.3, wall_category="medianera",
                                    layers=[[0.05, "A"], [0.25, "F"]], orden_capas="exterior-interior")
    transacciones.apply_architectural_change(sesion.tool("MURO").ctx, muro)
    informe = modulo(plugin, "quality").audit_architecture(sesion.document)
    assert any("exterior indeterminada" in aviso for aviso in informe["incidencias"])
    cambio = arquitectura.edit_wall(muro.entity, cara_exterior="izquierda")
    transacciones.apply_architectural_change(sesion.tool("MURO").ctx, cambio)
    elemento = next(e for e in sesion.export(None)["elements"] if e["id"] == sesion.meta(muro.entity)["id"])
    assert elemento["params"]["cara_exterior_resuelta"] == "izquierda"
    assert elemento["params"]["capas_colocadas"][0]["max"] == pytest.approx(0.15)
    sesion.history.undo()
    assert sesion.meta(muro.entity).get("cara_exterior", "auto") == "auto"


@pytest.mark.parametrize("situacion", ["exterior_cubierto", "exterior_descubierto"])
def test_los_muros_de_patio_y_porche_se_orientan_hacia_el_recinto_exterior(plugin, situacion):
    sesion = Session(plugin)
    arquitectura = modulo(plugin, "architectural_v10")
    transacciones = modulo(plugin, "transactions")
    muros_patio = []
    for interior, puntos in ((False, [(0, 0), (12, 0), (12, 12), (0, 12)]),
                             (True, [(4, 4), (8, 4), (8, 8), (4, 8)])):
        for inicio, fin in zip(puntos, puntos[1:] + puntos[:1]):
            cambio = arquitectura.create_wall(inicio, fin, 0.3,
                layers=[[0.05, "Acabado"], [0.25, "Hoja"]], orden_capas="exterior-interior")
            transacciones.apply_architectural_change(sesion.tool("MURO").ctx, cambio)
            if interior:
                muros_patio.append(sesion.meta(cambio.entity)["id"])
    recinto = sesion.tool("RECINTO")
    recinto.enclosure = situacion
    recinto.on_point((6, 6))
    contrato = sesion.export(None)
    for elemento in contrato["elements"]:
        if elemento["id"] in muros_patio:
            assert elemento["params"]["cara_exterior_resuelta"] == "izquierda"
    espacio = next(e for e in contrato["elements"] if e["ifc_class"] == "IfcSpace")
    assert espacio["psets"]["Pset_SpaceCommon"]["IsExternal"] is True
    if situacion == "exterior_descubierto":
        evaluacion = modulo(plugin, "superficies").evaluate(
            {"enclosure": situacion, "height": 3}, {"area": 16, "outer": [(0, 0), (4, 0), (4, 4), (0, 4)]})
        assert evaluacion["factor"] == 0

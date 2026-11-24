# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: las cotas usan la orden nativa mediante su constructor público, sin tocar su fábrica.
import math

import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_r29_precision import configurar
from tests.test_wall_tools import Session
from tests.escenarios_r27 import modulo


@pytest.mark.parametrize("precision,decimales", [("Centímetros", 2), ("Milímetros", 3)])
@pytest.mark.parametrize("direccion", [(1.0, 0.0), (0.6, 0.8)])
def test_cota_sin_acceso_a_la_fabrica_interna_con_deshacer_y_rehacer(
    plugin, monkeypatch, precision, decimales, direccion
):
    from core import actions

    sesion = Session(plugin)
    configurar(sesion, precision)
    cotas = modulo(plugin, "cotas")
    orden_nativa = actions.AddDimensionCommand
    renderizadas = []

    class OrdenPublica:
        """Solo expone el contrato de la orden; oculta sus detalles de implementación."""
        def __init__(self, fabrica):
            def crear(espacio, documento):
                resultado = fabrica(espacio, documento)
                renderizadas.append(resultado.dimension)
                return resultado

            self.orden = orden_nativa(crear)
            self.layer = None

        def do(self, documento):
            self.orden.layer = self.layer
            self.orden.do(documento)

        def undo(self, documento):
            self.orden.undo(documento)

    monkeypatch.setattr(actions, "AddDimensionCommand", OrdenPublica)
    sesion.history.execute(cotas._StyleCommand(0.20))
    dibujo = sesion.document.doc
    estilo_inicial = dict(dibujo.dimstyles.get(cotas.DIM_STYLE).dxf.all_existing_dxf_attribs())
    bloques_iniciales = {bloque.name for bloque in dibujo.blocks}
    inicio = (10.0, 20.0)
    fin = (inicio[0] + 2.347 * direccion[0], inicio[1] + 2.347 * direccion[1])
    ubicacion = (inicio[0] + 0.4 * direccion[1], inicio[1] - 0.4 * direccion[0])
    orden, = cotas.dimension_commands([(inicio, fin, ubicacion)], sesion.document)
    sesion.history.execute(orden)
    dimension, = list(dibujo.modelspace().query("DIMENSION"))
    assert dimension.get_measurement() == pytest.approx(2.347)
    assert dimension.override().get("dimdec") == decimales
    assert dimension.dxf.layer == cotas.DIM_LAYER
    assert len(renderizadas) == 1
    assert math.dist(tuple(dimension.dxf.defpoint2)[:2], tuple(dimension.dxf.defpoint3)[:2]) == pytest.approx(2.347)
    bloques_creados = {bloque.name for bloque in dibujo.blocks} - bloques_iniciales
    assert len([nombre for nombre in bloques_creados if nombre.startswith("*D")]) == 1
    sesion.history.undo()
    assert not list(dibujo.modelspace().query("DIMENSION"))
    assert not any(nombre in dibujo.blocks for nombre in bloques_creados if nombre.startswith("*D"))
    sesion.history.redo()
    dimension, = list(dibujo.modelspace().query("DIMENSION"))
    assert dimension.get_measurement() == pytest.approx(2.347)
    assert dimension.override().get("dimdec") == decimales
    assert len(renderizadas) == 2
    assert dict(dibujo.dimstyles.get(cotas.DIM_STYLE).dxf.all_existing_dxf_attribs()) == estilo_inicial

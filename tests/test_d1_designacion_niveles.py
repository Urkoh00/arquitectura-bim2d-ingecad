# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: reproducciones de la designación entre niveles y de la referencia de carpintería.
from copy import deepcopy

import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session
from tests.escenarios_r27 import modulo


def niveles(sesion, plugin, prefijo):
    catalogo = modulo(plugin, "levels")
    capas = modulo(plugin, "level_layers")
    datos = deepcopy(catalogo.load(sesion.document))
    inferior = datos["active"]
    superior = "planta-superior-de-ensayo"
    datos["levels"].append({"id": superior, "name": "Planta superior", "elevation": 3.0})
    datos.update(active=superior, layer_managed=True)
    sesion.history.execute(catalogo.StoreCatalog(datos))
    dibujo = sesion.document.doc
    dibujo.layers.new("ARQ-MUROS" + capas.suffix(superior))
    dibujo.layers.new(prefijo + capas.suffix(inferior))
    return capas, inferior, superior


@pytest.mark.parametrize("tipo,prefijo", [("column", "ARQ-PILARES"), ("wall", "ARQ-PARTICIONES")])
def test_elemento_inferior_que_alcanza_la_activa_no_exige_crear_su_capa_de_categoria(
    plugin, tipo, prefijo
):
    sesion = Session(plugin)
    capas, inferior, superior = niveles(sesion, plugin, prefijo)
    registro = {"id": "elemento", "kind": tipo, "wall_category": "particion",
                "level_id": inferior, "base": 0.0, "height": 6.0}
    dibujo = sesion.document.doc
    destino = prefijo + capas.suffix(superior)
    anteriores = [(c.dxf.name, c.dxf.color, c.dxf.flags) for c in dibujo.layers]
    assert destino not in dibujo.layers
    assert capas.target_available(dibujo, registro)
    assert destino not in dibujo.layers
    assert [(c.dxf.name, c.dxf.color, c.dxf.flags) for c in dibujo.layers] == anteriores


@pytest.mark.parametrize("estado", ["off", "freeze", "lock"])
def test_categoria_ausente_no_ignora_el_estado_nativo_del_nivel_activo(plugin, estado):
    sesion = Session(plugin)
    capas, inferior, superior = niveles(sesion, plugin, "ARQ-PILARES")
    capa = sesion.document.doc.layers.get("ARQ-MUROS" + capas.suffix(superior))
    getattr(capa, estado)()
    assert not capas.target_available(sesion.document.doc, {
        "kind": "column", "level_id": inferior, "base": 0.0, "height": 6.0,
    })



@pytest.mark.parametrize("estado", ["off", "freeze", "lock"])
def test_categoria_existente_conserva_su_propio_estado(plugin, estado):
    sesion = Session(plugin)
    capas, inferior, superior = niveles(sesion, plugin, "ARQ-PILARES")
    destino = sesion.document.doc.layers.new("ARQ-PILARES" + capas.suffix(superior))
    getattr(destino, estado)()
    assert not capas.target_available(sesion.document.doc, {
        "kind": "column", "level_id": inferior, "base": 0.0, "height": 6.0,
    })


@pytest.mark.parametrize("base,altura", [(0.0, 3.0), (4.0, 2.0), (0.0, 0.0)])
def test_un_elemento_fuera_de_la_planta_activa_no_se_designa(plugin, base, altura):
    sesion = Session(plugin)
    capas, inferior, superior = niveles(sesion, plugin, "ARQ-PILARES")
    assert not capas.target_available(sesion.document.doc, {
        "kind": "column", "level_id": inferior, "base": base, "height": altura,
    })


@pytest.mark.parametrize("estado,disponible", [(None, True), ("off", False), ("freeze", False), ("lock", False)])
def test_sin_capas_del_nivel_se_hereda_la_categoria_base(plugin, estado, disponible):
    sesion = Session(plugin)
    capas, inferior, superior = niveles(sesion, plugin, "ARQ-PILARES")
    dibujo = sesion.document.doc
    dibujo.layers.remove("ARQ-MUROS" + capas.suffix(superior))
    if "ARQ-PILARES" not in dibujo.layers:
        dibujo.layers.new("ARQ-PILARES")
    if estado is not None:
        getattr(dibujo.layers.get("ARQ-PILARES"), estado)()
    assert capas.target_available(dibujo, {
        "kind": "column", "level_id": inferior, "base": 0.0, "height": 6.0,
    }) is disponible


def test_una_categoria_existente_no_hereda_el_estado_de_otra(plugin):
    sesion = Session(plugin)
    capas, inferior, superior = niveles(sesion, plugin, "ARQ-PILARES")
    dibujo = sesion.document.doc
    dibujo.layers.new("ARQ-PILARES" + capas.suffix(superior))
    dibujo.layers.get("ARQ-MUROS" + capas.suffix(superior)).lock()
    assert capas.target_available(dibujo, {
        "kind": "column", "level_id": inferior, "base": 0.0, "height": 6.0,
    })

# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: una orden antigua completa ocupa un solo paso de Deshacer y Rehacer.
import pytest
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session


def estado(dibujo):
    elementos = []
    for entidad in dibujo.modelspace():
        atributos = entidad.dxf.all_existing_dxf_attribs()
        datos = tuple(sorted((clave, str(valor)) for clave, valor in atributos.items()
                             if clave not in ('handle', 'owner')))
        puntos = tuple(str(vertice.dxf.location) for vertice in entidad.vertices) \
            if entidad.dxftype() == 'POLYLINE' else ()
        elementos.append((entidad.dxftype(), datos, puntos))
    return sorted(elementos)


@pytest.mark.parametrize('orden', ['ESCALERA', 'BLOQUE', 'CAPASARQ', 'CAPASAUTO', 'CURVAS3D'])
def test_deshacer_una_orden_antigua_completa(plugin, orden):
    sesion = Session(plugin)
    antes = estado(sesion.document.doc)
    capas_antes = sorted(capa.dxf.name for capa in sesion.document.doc.layers)
    herramienta = sesion.tool(orden)
    if orden == 'BLOQUE':
        herramienta.on_option('1')
    if orden == 'CURVAS3D':
        herramienta.on_enter()
        herramienta.on_enter()
        herramienta.on_point((0., 0.))
        herramienta.on_point((2., 1.))
        herramienta.on_option('fin')
    elif orden not in ('CAPASARQ', 'CAPASAUTO'):
        herramienta.on_point((2., 3.))
    despues = estado(sesion.document.doc)
    capas_despues = sorted(capa.dxf.name for capa in sesion.document.doc.layers)
    assert sesion.history.depth == 1
    sesion.history.undo()
    assert estado(sesion.document.doc) == antes
    assert sorted(capa.dxf.name for capa in sesion.document.doc.layers) == capas_antes
    sesion.history.redo()
    assert estado(sesion.document.doc) == despues
    assert sorted(capa.dxf.name for capa in sesion.document.doc.layers) == capas_despues

# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: P3 conserva las capas del contrato y comprueba el desplazamiento
# respecto a la geometría real, con referencias en eje, izquierda y derecha.
import copy
import math

import pytest
from core.commands import History
from core.document import Document
from arquitectura import architectural_v10, exchange
from arquitectura.geom.junctions import Wall
from ingetrazo_ext import arquitectura_bim as extension


def crear_muro(referencia, angulo, con_capas=True):
    documento = Document.new()
    for nombre in ["ARQ-MUROS", "ARQ-MUROS3D", "ARQ-HUECOS3D"]:
        documento.doc.layers.add(nombre)
    extremo = (4 * math.cos(math.radians(angulo)), 4 * math.sin(math.radians(angulo)))
    datos = {"type_name": "Muro de prueba", "material": "Ladrillo"}
    if con_capas:
        datos["layers"] = [[.1, "Ladrillo"], [.2, "Aislante"]]
    orden = architectural_v10.create_wall((0, 0), extremo, .3, 2.7,
                                          reference=referencia, **datos)
    History(documento).execute(orden)
    return exchange.build(documento.doc)["elements"][0]


@pytest.mark.parametrize("referencia,desplazamiento", [
    ("eje", -.15), ("izquierda", 0.), ("derecha", -.3),
])
@pytest.mark.parametrize("angulo", [0, 27, 90, 180])
def test_capas_y_desplazamiento_cuadran_con_las_caras(referencia, desplazamiento, angulo):
    elemento = crear_muro(referencia, angulo)
    original = copy.deepcopy(elemento)
    etiqueta = {}
    extension._etiqueta_material_muro(etiqueta, elemento)
    assert etiqueta["material_layers"] == elemento["material_layers"]
    assert etiqueta["material_layers"] is not elemento["material_layers"]
    assert etiqueta["layer_offset"] == pytest.approx(desplazamiento)
    parametros = elemento["params"]
    muro = Wall("ensayo", parametros["a"], parametros["b"], .3, referencia)
    cotas = [muro.local(punto[:2])[1] for cara in elemento["faces"] for punto in cara["outer"]]
    assert min(cotas) == pytest.approx(etiqueta["layer_offset"])
    assert max(cotas) == pytest.approx(etiqueta["layer_offset"] + .3)
    assert elemento == original


def test_muro_sin_capas_conserva_desplazamiento_para_la_capa_generica():
    elemento = crear_muro("derecha", 0, con_capas=False)
    etiqueta = {}
    extension._etiqueta_material_muro(etiqueta, elemento)
    assert "material_layers" not in etiqueta
    assert etiqueta["layer_offset"] == -.3


@pytest.mark.parametrize("clase", ["IfcColumn", "IfcSlab", "IfcDoor", "IfcWindow", "IfcSpace"])
def test_solo_los_muros_reciben_capas(clase):
    etiqueta = {"type": "Tipo", "material": "Material"}
    elemento = {"ifc_class": clase, "material_layers": [{"thickness": .2, "material": "Otro"}]}
    extension._etiqueta_material_muro(etiqueta, elemento)
    assert etiqueta == {"type": "Tipo", "material": "Material"}

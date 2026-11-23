# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: el bloque «delivery» que el escritor IFC de IngeTrazo 0.6.3 lee de cada objeto.
"""Desde IngeTrazo 0.6.3 el escritor IFC oficial lee de cada objeto un bloque
``delivery`` (tipo predefinido, ObjectType, Tag, material y propiedades
comunes) y rechaza la exportación entera si una clase o un valor no está en
su lista. La extensión lo rellena con lo que el plugin ya exporta y lo
filtra con esa misma lista, leída del IngeTrazo instalado."""
import os
import sys

import pytest

from ingetrazo_ext import arquitectura_bim as X

#: Extracto con la misma forma que resources/bim/turkiye_delivery.json de 0.6.3.
REGLAS = {
    "IfcWall": {
        "psets": {"Pset_WallCommon": {"IsExternal": "IfcBoolean", "FireRating": "IfcLabel"}},
        "predefined_types": {
            "IFC4": ["PARTITIONING", "STANDARD", "USERDEFINED", "NOTDEFINED"],
            "IFC4X3_ADD2": ["PARTITIONING", "STANDARD", "USERDEFINED", "NOTDEFINED"]},
    },
    "IfcSpace": {
        "psets": {"Pset_SpaceCoveringRequirements": {"FloorCovering": "IfcLabel"}},
        "predefined_types": {"IFC4": ["INTERNAL", "EXTERNAL"],
                             "IFC4X3_ADD2": ["INTERNAL", "EXTERNAL"]},
    },
    "IfcSlab": {
        "psets": {"Pset_SlabCommon": {"IsExternal": "IfcBoolean"}},
        "predefined_types": {"IFC4": ["BASESLAB", "ROOF", "FLOOR"],
                             "IFC4X3_ADD2": ["BASESLAB", "ROOF", "FLOOR"]},
    },
}


def muro(**cambios):
    el = {"ifc_class": "IfcWall", "material": "Ladrillo",
          "enums": {"PredefinedType": "USERDEFINED"},
          "attributes": {"ObjectType": "PARTYWALL"},
          "params": {"mark": ""},
          "psets": {"Pset_WallCommon": {"IsExternal": True, "Reference": "Fachada 300"}}}
    el.update(cambios)
    return el


def test_un_muro_lleva_tipo_material_y_propiedad_comun():
    entrega = X._entrega_ifc(muro(), {}, REGLAS)
    assert entrega == {"predefined_type": "USERDEFINED", "object_type": "PARTYWALL",
                       "material": "Ladrillo",
                       "psets": {"Pset_WallCommon": {"IsExternal": True}}}


def test_solo_las_propiedades_que_ingetrazo_admite():
    entrega = X._entrega_ifc(muro(), {}, REGLAS)
    assert "Reference" not in entrega["psets"]["Pset_WallCommon"]


def test_userdefined_sin_objecttype_no_se_envia():
    entrega = X._entrega_ifc(muro(attributes={}), {}, REGLAS)
    assert "predefined_type" not in entrega


def test_un_tipo_que_ingetrazo_no_admite_no_se_envia():
    entrega = X._entrega_ifc(muro(enums={"PredefinedType": "EXTERNALWALL"}, attributes={}),
                             {}, REGLAS)
    assert "predefined_type" not in entrega


def test_una_clase_que_ingetrazo_no_admite_no_lleva_bloque():
    """IfcBuildingElementProxy (armario): con bloque, IngeTrazo rechazaría
    la exportación de todo el modelo."""
    assert X._entrega_ifc(muro(ifc_class="IfcBuildingElementProxy"), {}, REGLAS) == {}


def test_un_recinto_no_lleva_material_ni_marca():
    recinto = {"ifc_class": "IfcSpace", "material": "", "enums": {"PredefinedType": "INTERNAL"},
               "params": {"mark": "R1"}, "psets": {"Pset_SpaceCommon": {"IsExternal": False}}}
    assert X._entrega_ifc(recinto, {}, REGLAS) == {"predefined_type": "INTERNAL"}


def test_la_marca_de_carpinteria_es_el_tag():
    assert X._entrega_ifc(muro(params={"mark": "P2"}), {}, REGLAS)["tag"] == "P2"


def test_sin_reglas_no_hay_bloque():
    """IngeTrazo anterior a 0.6.3: el escritor no lee el bloque."""
    assert X._entrega_ifc(muro(), {}, None) == {}


def test_un_muro_no_lleva_capas_mientras_ingetrazo_las_rechace():
    entrega = X._entrega_ifc(muro(), {"material_layers": [{"material": "A", "thickness": .1}],
                                      "layer_offset": -.05}, REGLAS)
    assert "layer" not in entrega and "layers" not in entrega


CADENA = """
import sys, json
from pathlib import Path
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[2])
import arquitectura_bim as X
from core.scene import Scene
from formats.igz import load_into, save_scene
from formats.ifc import save_ifc
import ifcopenshell, ifcopenshell.validate, ifcopenshell.util.element as U
datos = X.read_contract(sys.argv[3])
escena = X.build_scene(datos); X.check_scene(escena, datos)
save_scene(escena, Path(sys.argv[3] + ".igz"))
leida = Scene(); load_into(leida, Path(sys.argv[3] + ".igz"))
save_ifc(leida, sys.argv[3] + ".ifc")
f = ifcopenshell.open(sys.argv[3] + ".ifc")
log = ifcopenshell.validate.json_logger()
ifcopenshell.validate.validate(f, log, express_rules=True)
muros = f.by_type("IfcWall")
print(json.dumps({"errores": len(log.statements),
                  "tipos": [str(m.PredefinedType) for m in muros],
                  "exterior": [U.get_psets(m).get("Pset_WallCommon", {}).get("IsExternal")
                               for m in muros]}))
"""


@pytest.mark.skipif(not os.environ.get("INGETRAZO_SRC"),
                    reason="cadena completa: requiere INGETRAZO_SRC con IngeTrazo 0.6.3 o posterior")
def test_cadena_completa_con_ingetrazo(tmp_path):
    """Contrato → escena → IGZ → IFC con el escritor oficial, en un proceso
    aparte (IngeCAD e IngeTrazo tienen los dos un paquete «core»): 0 errores
    EXPRESS, tipo predefinido e IsExternal en todos los muros."""
    import json
    import subprocess

    pytest.importorskip("ifcopenshell")
    from core.commands import History
    from core.document import Document

    from arquitectura import exchange as E
    from arquitectura.architectural_v10 import create_wall

    d = Document.new()
    for name in ['ARQ-MUROS', 'ARQ-MUROS3D', 'ARQ-HUECOS3D', 'ARQ-RECINTOS']:
        d.doc.layers.add(name)
    h = History(d)
    for a, b in [((0, 0), (5, 0)), ((5, 0), (5, 4)), ((5, 4), (0, 4)), ((0, 4), (0, 0))]:
        h.execute(create_wall(a, b, .3, 3))
    contrato = tmp_path / "m.arqbim"
    E.write(d.doc, str(contrato))
    ext = os.path.join(os.path.dirname(X.__file__))
    r = subprocess.run([sys.executable, "-I", "-c", CADENA, os.environ["INGETRAZO_SRC"], ext,
                        str(contrato)], capture_output=True, text=True, timeout=240,
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    assert r.returncode == 0, r.stderr[-2000:]
    medida = json.loads(r.stdout.strip().splitlines()[-1])
    assert medida["errores"] == 0
    assert medida["tipos"] and "None" not in medida["tipos"]
    assert all(v is not None for v in medida["exterior"])

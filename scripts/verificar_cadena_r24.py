# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: verifica el ejemplo público de P3 con los lectores oficiales.
"""Ejecutar con IngeTrazo P3 en PYTHONPATH; IfcOpenShell solo para el ensayo."""
import importlib.util
import json
from pathlib import Path
import sys

import ifcopenshell
import ifcopenshell.util.element as utilidades
import ifcopenshell.validate


def verificar(destino):
    ruta = Path(__file__).resolve().parents[1] / "ingetrazo_ext" / "arquitectura_bim.py"
    especificacion = importlib.util.spec_from_file_location("extension_arq", ruta)
    extension = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(extension)
    contrato, escena, solidos = extension.to_igz(
        destino / "modelo_sintetico.arqbim", destino / "modelo_sintetico.igz")
    from formats.ifc import save_ifc
    ruta_ifc = destino / "modelo_sintetico.ifc"
    assert save_ifc(escena, ruta_ifc) == 10
    por_nombre = {elemento["name"]: elemento for elemento in contrato["elements"]}
    for grupo in escena.groups:
        elemento = por_nombre[grupo.ifc["name"]]
        for origen, etiqueta in (("type_name", "type"), ("material", "material")):
            if elemento.get(origen):
                assert grupo.ifc[etiqueta] == elemento[origen]
        if elemento["ifc_class"] == "IfcWall":
            if "material_layers" in elemento:
                assert grupo.ifc["material_layers"] == elemento["material_layers"]
            assert grupo.ifc["layer_offset"] == -elemento["params"]["thickness"] / 2
        else:
            assert "material_layers" not in grupo.ifc
    modelo = ifcopenshell.open(str(ruta_ifc))
    muros = []
    for muro in modelo.by_type("IfcWall"):
        elemento = por_nombre[muro.Name]
        uso = utilidades.get_material(muro)
        assert uso.is_a("IfcMaterialLayerSetUsage")
        assert uso.LayerSetDirection == "AXIS2"
        assert uso.DirectionSense == "POSITIVE"
        assert uso.OffsetFromReferenceLine == -elemento["params"]["thickness"] / 2
        capas = [{"material": capa.Material.Name, "thickness": capa.LayerThickness}
                 for capa in uso.ForLayerSet.MaterialLayers]
        esperadas = elemento.get("material_layers") or [
            {"material": elemento.get("material") or "Undefined",
             "thickness": elemento["params"]["thickness"]}]
        assert capas == esperadas
        tipo = utilidades.get_type(muro)
        assert tipo.Name == elemento["type_name"]
        assert utilidades.get_material(tipo) == uso.ForLayerSet
        muros.append({"nombre": muro.Name, "tipo": tipo.Name, "capas": capas,
                      "desplazamiento": uso.OffsetFromReferenceLine})
    tipos = modelo.by_type("IfcTypeObject")
    relaciones = modelo.by_type("IfcRelDefinesByType")
    assert len(tipos) == len(relaciones) == 7
    assert len(modelo.by_type("IfcMaterialLayerSetUsage")) == 5
    registro = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate(str(ruta_ifc), registro, express_rules=True)
    errores = [{"regla": entrada.get("attribute"),
                "clase": entrada.get("instance").is_a(),
                "mensaje": entrada["message"]} for entrada in registro.statements]
    assert len(errores) == 3, errores
    assert sorted(error["regla"] for error in errores) == [
        "IfcRelContainedInSpatialStructure.WR31",
        "IfcSpatialStructureElement.WR41", "IfcSpatialStructureElement.WR41"]
    resumen = {"elementos": len(solidos), "solidos": solidos,
               "tipos": len(tipos), "relaciones_de_tipo": len(relaciones),
               "muros": muros, "errores_express": errores,
               "norte_igz": escena.north_deg,
               "norte_ifc": str(modelo.by_type("IfcGeometricRepresentationContext")[0].TrueNorth)}
    (destino / "verificacion.json").write_text(
        json.dumps(resumen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(resumen, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    verificar(Path(sys.argv[1]).resolve())

# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: genera desde cero el modelo público de R24-P3 con las órdenes
# de IngeCAD; no lee ni adapta el modelo de referencia privado.
"""Ejecutar con IngeCAD 0.8.0 en PYTHONPATH."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from core.commands import History
from core.document import Document
from arquitectura import architectural, architectural_v10, exchange, levels, slabs
from arquitectura import parameters_arq, transactions, wall_tools
from arquitectura.geom import bands, spaces


def generar(destino):
    destino.mkdir(parents=True, exist_ok=True)
    documento = Document.new()
    historial = History(documento)
    contexto = SimpleNamespace(document=documento, execute=historial.execute)
    historial.execute(levels.StoreCatalog(levels.load(documento)))
    valores = parameters_arq.load_defaults(documento)
    valores["general"]["norte"] = 30.
    historial.execute(parameters_arq.SetArchitecturalDefaults(valores))
    catalogo = {tipo["name"]: tipo for tipo in valores["wall_types"]}
    fachada = catalogo["Fachada caravista + aislamiento + LHD (ejemplo)"]
    tabique = catalogo["PYL 78/48"]
    muros = []
    definiciones = [
        ((0, 0), (8, 0), fachada["thickness"], "fachada", fachada["name"],
         fachada["material"], fachada["layers"]),
        ((8, 0), (8, 6), .3, "fachada", "Fachada genérica 300", "Ladrillo", None),
        ((8, 6), (0, 6), .3, "fachada", "Fachada genérica 300", "Ladrillo", None),
        ((0, 6), (0, 0), .3, "medianera", "Medianera genérica 300", "Bloque", None),
        ((4, fachada["thickness"] / 2), (4, 5.85), tabique["thickness"],
         "tabique", tabique["name"], tabique["material"], tabique["layers"]),
    ]
    for numero, (inicio, fin, espesor, categoria, tipo, material, capas) in enumerate(definiciones):
        datos = {"wall_category": categoria, "type_name": tipo,
                 "material": material, "name": f"Muro sintético {numero + 1}"}
        if capas:
            datos["layers"] = capas
        orden = architectural_v10.create_wall(inicio, fin, espesor, 3., reference="eje", **datos)
        transactions.apply_architectural_change(contexto, orden)
        muros.append(orden.entity)
    puerta = architectural_v10.create_opening(
        muros[0], 1., .9, 0., 2.1, kind="door", type_name="Puerta 900",
        material="Madera", operation="SWINGING")
    transactions.apply_architectural_change(contexto, puerta, kind="opening")
    ventana = architectural_v10.create_opening(
        muros[1], 2., 1.2, 1.2, 1.2, kind="window", type_name="Ventana 1200",
        material="Aluminio", operation="SLIDING")
    transactions.apply_architectural_change(contexto, ventana, kind="opening")
    if slabs.LAYER not in documento.doc.layers:
        documento.doc.layers.add(slabs.LAYER)
    solera = slabs.create([(-.15, -.13), (8.15, -.13), (8.15, 6.15), (-.15, 6.15)],
                         thickness=.2, top=0., slab_kind="solera",
                         material="Hormigón", name="Solera sintética")
    transactions.apply_architectural_change(contexto, solera, kind="slab")
    for numero, semilla in enumerate([(2, 3), (6, 3)], 1):
        registros, pilares, _huecos, _avisos = exchange.read_model(documento.doc)
        red = bands.solve_records(registros, pilares)
        recinto, motivo = spaces.space_at(red, semilla)
        assert recinto is not None, motivo
        orden, _registro = wall_tools.create_space(
            semilla, recinto, name=f"Recinto sintético {numero}", number=numero, height=3.)
        transactions.apply_architectural_change(contexto, orden, kind="space")
        # El tipo se fija en el registro mediante la orden de edición existente,
        # no se escribe XDATA ni se cambia a mano el contrato exportado.
        registro = architectural.metadata(orden.entity)
        edicion = architectural_v10.EditArchitecturalCommand(
            orden.entity, {**registro, "type_name": "Espacio interior sintético"})
        transactions.apply_architectural_change(contexto, edicion, kind="space")
    contrato = exchange.write(documento.doc, destino / "modelo_sintetico.arqbim",
                              project="Ensayo público R24-P3")
    documento.save_as(destino / "modelo_sintetico.dxf")
    clases = {}
    for elemento in contrato["elements"]:
        clases[elemento["ifc_class"]] = clases.get(elemento["ifc_class"], 0) + 1
    assert clases == {"IfcWall": 5, "IfcDoor": 1, "IfcWindow": 1, "IfcSpace": 2, "IfcSlab": 1}
    resumen = {"clases": clases, "incidencias": contrato["issues"],
               "tipos_de_origen": [elemento.get("type_name", "") for elemento in contrato["elements"]]}
    (destino / "generacion.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2))
    print(json.dumps(resumen, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    generar(Path(sys.argv[1]).resolve())

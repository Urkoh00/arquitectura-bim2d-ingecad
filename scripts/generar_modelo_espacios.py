# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: genera desde cero una vivienda sintética de cinco recintos para
#   comprobar los espacios del modelo analítico (prueba de aceptación 4).
"""Ejecutar con IngeCAD 0.8.0 en PYTHONPATH:

    python scripts/generar_modelo_espacios.py <carpeta>

Vivienda de 10 × 8 m, muros de 2,70 m bajo una cubierta plana de 0,30 m
(2,70–3,00), solera, norte a 30°. Cinco recintos de 2,70 m: cocina,
dormitorio 1, estar, baño y dormitorio 2; tres tabiques con encuentros en T;
puerta de entrada, siete ventanas y cuatro puertas de paso. Cada recinto
toca la envolvente por al menos un lado; el baño tiene dos fachadas
(medianera y norte) y una ventana alta."""
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

ALTURA = 2.7
RECINTOS = [  # nombre, semilla, uso
    ("Cocina", (2.5, 2.0)),
    ("Dormitorio 1", (7.5, 2.0)),
    ("Estar-comedor", (7.5, 6.0)),
    ("Baño", (1.25, 6.0)),
    ("Dormitorio 2", (3.75, 6.0)),
]


def generar(destino):
    destino.mkdir(parents=True, exist_ok=True)
    documento = Document.new()
    historial = History(documento)
    contexto = SimpleNamespace(document=documento, execute=historial.execute)
    historial.execute(levels.StoreCatalog(levels.load(documento)))
    valores = parameters_arq.load_defaults(documento)
    valores["general"]["norte"] = 30.
    historial.execute(parameters_arq.SetArchitecturalDefaults(valores))
    tabique = {t["name"]: t for t in valores["wall_types"]}["PYL 78/48"]
    e = tabique["thickness"]

    def muro(a, b, espesor, categoria, tipo, material, nombre, capas=None):
        datos = {"wall_category": categoria, "type_name": tipo, "material": material,
                 "name": nombre}
        if capas:
            datos["layers"] = capas
        orden = architectural_v10.create_wall(a, b, espesor, ALTURA, reference="eje", **datos)
        transactions.apply_architectural_change(contexto, orden)
        return orden.entity

    fachada = ("Fachada genérica 300", "Ladrillo")
    sur = muro((0, 0), (10, 0), .3, "fachada", *fachada, "Fachada sur")
    este = muro((10, 0), (10, 8), .3, "fachada", *fachada, "Fachada este")
    norte = muro((10, 8), (0, 8), .3, "fachada", *fachada, "Fachada norte")
    muro((0, 8), (0, 0), .3, "medianera", "Medianera genérica 300", "Bloque", "Medianera oeste")
    # tabiques: uno vertical de fachada a fachada, dos horizontales en T con él
    # y uno vertical que separa el baño
    t_v = muro((5, .15), (5, 7.85), e, "tabique", tabique["name"], tabique["material"],
               "Tabique central", tabique["layers"])
    t_o = muro((.15, 4), (5, 4), e, "tabique", tabique["name"], tabique["material"],
               "Tabique oeste", tabique["layers"])
    t_e = muro((5, 4), (9.85, 4), e, "tabique", tabique["name"], tabique["material"],
               "Tabique este", tabique["layers"])
    t_b = muro((2.5, 4), (2.5, 7.85), e, "tabique", tabique["name"], tabique["material"],
               "Tabique del baño", tabique["layers"])

    def hueco(anfitrion, desde, ancho, antepecho, alto, clase, tipo, material, **extra):
        orden = architectural_v10.create_opening(
            anfitrion, desde, ancho, antepecho, alto, kind=clase, type_name=tipo,
            material=material, **extra)
        transactions.apply_architectural_change(contexto, orden, kind="opening")

    # Puerta de entrada (este, al estar) y ventanas.
    hueco(este, 5.0, 1.0, 0., 2.1, "door", "Puerta de entrada 1000", "Madera",
          operation="SWINGING")
    hueco(sur, 1.5, 1.2, 1.0, 1.2, "window", "Ventana 1200", "Aluminio", operation="SLIDING")
    hueco(sur, 6.9, 1.2, 1.0, 1.2, "window", "Ventana 1200", "Aluminio", operation="SLIDING")
    hueco(este, 1.4, 1.2, 1.0, 1.2, "window", "Ventana 1200", "Aluminio", operation="SLIDING")
    hueco(norte, 1.5, 2.0, .9, 1.3, "window", "Ventana 2000", "Aluminio", operation="SLIDING")
    hueco(norte, 6.0, 1.2, 1.0, 1.2, "window", "Ventana 1200", "Aluminio", operation="SLIDING")
    hueco(norte, 8.6, .6, 1.6, .6, "window", "Ventana baño 600", "Aluminio",
          operation="SINGLE_PANEL")
    hueco(este, 6.6, .8, 1.0, 1.2, "window", "Ventana 800", "Aluminio", operation="SLIDING")
    # Puertas de paso: cocina–dormitorio 1, dormitorio 1–estar, dormitorio 2–estar, baño–dormitorio 2.
    for anfitrion, desde in ((t_v, 2.0), (t_e, 1.0), (t_v, 5.5), (t_b, 1.5)):
        hueco(anfitrion, desde, .8, 0., 2.1, "door", "Puerta de paso 800", "Madera",
              operation="SWINGING")

    if slabs.LAYER not in documento.doc.layers:
        documento.doc.layers.add(slabs.LAYER)
    contorno = [(-.15, -.15), (10.15, -.15), (10.15, 8.15), (-.15, 8.15)]
    for nombre, clase, espesor, cara in (("Solera", "solera", .2, 0.),
                                         ("Cubierta", "cubierta", .3, 3.)):
        orden = slabs.create(contorno, thickness=espesor, top=cara, slab_kind=clase,
                             material="Hormigón", name=f"{nombre} sintética")
        transactions.apply_architectural_change(contexto, orden, kind="slab")

    for numero, (nombre, semilla) in enumerate(RECINTOS, 1):
        registros, pilares, _huecos, _avisos = exchange.read_model(documento.doc)
        red = bands.solve_records(registros, pilares)
        recinto, motivo = spaces.space_at(red, semilla)
        assert recinto is not None, (nombre, motivo)
        orden, _registro = wall_tools.create_space(
            semilla, recinto, name=nombre, number=numero, height=ALTURA)
        transactions.apply_architectural_change(contexto, orden, kind="space")
        registro = architectural.metadata(orden.entity)
        edicion = architectural_v10.EditArchitecturalCommand(
            orden.entity, {**registro, "type_name": "Espacio habitable"})
        transactions.apply_architectural_change(contexto, edicion, kind="space")

    contrato = exchange.write(documento.doc, destino / "vivienda_espacios.arqbim",
                              project="Prueba de aceptación 4: espacios")
    documento.save_as(destino / "vivienda_espacios.dxf")
    clases = {}
    for elemento in contrato["elements"]:
        clases[elemento["ifc_class"]] = clases.get(elemento["ifc_class"], 0) + 1
    recintos = {el["name"]: round(el["quantities"].get("NetFloorArea", 0), 3)
                for el in contrato["elements"] if el["ifc_class"] == "IfcSpace"}
    resumen = {"clases": clases, "incidencias": contrato["issues"], "recintos_m2": recintos}
    (destino / "generacion.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2))
    print(json.dumps(resumen, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    generar(Path(sys.argv[1]).resolve())

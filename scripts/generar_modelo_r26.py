# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: genera desde cero el modelo público de R26-P4 con las órdenes
# de IngeCAD; no lee ni adapta el modelo de referencia privado.
"""Ejecutar con IngeCAD 0.8.0 en PYTHONPATH."""
import json
import math
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


def generar(destino, angulo=0., lejano=False, caso="normal"):
    radianes = math.radians(angulo)
    coseno = math.cos(radianes)
    seno = math.sin(radianes)
    origen = (700000., 4600000.) if lejano else (0., 0.)

    def transformar(punto):
        x, y = punto
        return (origen[0] + x * coseno - y * seno,
                origen[1] + x * seno + y * coseno)

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
        if caso == "curvo" and numero == 1:
            datos["bulge"] = .15
        orden = architectural_v10.create_wall(transformar(inicio), transformar(fin), espesor, 3., reference="eje", **datos)
        transactions.apply_architectural_change(contexto, orden)
        muros.append(orden.entity)
    puerta = architectural_v10.create_opening(
        muros[0], 1., .9, 0., 2.1, kind="door", type_name="Puerta 900",
        material="Madera", operation="SWINGING")
    transactions.apply_architectural_change(contexto, puerta, kind="opening")
    datos_ventana = {"curve_mode": "curva"} if caso == "curvo" else {}
    ventana = architectural_v10.create_opening(
        muros[1], 2., 1.2, 1.2, 1.2, kind="window", type_name="Ventana 1200",
        material="Aluminio", operation="SLIDING", **datos_ventana)
    transactions.apply_architectural_change(contexto, ventana, kind="opening")
    if caso == "nicho":
        hueco = architectural_v10.create_opening(
            muros[2], 1.5, .8, 1., 1., kind="gap", name="Hueco sin carpintería")
        transactions.apply_architectural_change(contexto, hueco, kind="opening")
        # La orden nativa de armario en nicho crea su frente como IfcDoor.
        # Se conserva esa clasificación y la geometría real de la cavidad.
        nicho = architectural_v10.create_opening(
            muros[4], 1.5, .9, 0., 1.8, kind="door", cabinet=True,
            cabinet_mode="nicho", niche_depth=.04, leaves=2, angle=0.,
            name="Nicho sintético", material="Madera", type_name="Armario sintético")
        transactions.apply_architectural_change(contexto, nicho, kind="opening")
    if slabs.LAYER not in documento.doc.layers:
        documento.doc.layers.add(slabs.LAYER)
    limite_derecho = 8.8 if caso == "curvo" else 8.15
    solera = slabs.create([transformar(punto) for punto in
                          [(-.15, -.13), (limite_derecho, -.13),
                           (limite_derecho, 6.15), (-.15, 6.15)]],
                         thickness=.2, top=0., slab_kind="solera",
                         material="Hormigón", name="Solera sintética")
    transactions.apply_architectural_change(contexto, solera, kind="slab")
    for numero, semilla in enumerate([(2, 3), (6, 3)], 1):
        semilla = transformar(semilla)
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
                              project="Ensayo público R26-P4")
    documento.save_as(destino / "modelo_sintetico.dxf")
    clases = {}
    for elemento in contrato["elements"]:
        clases[elemento["ifc_class"]] = clases.get(elemento["ifc_class"], 0) + 1
    esperadas = {"IfcWall": 5, "IfcDoor": 1, "IfcWindow": 1, "IfcSpace": 2, "IfcSlab": 1}
    if caso == "nicho":
        esperadas["IfcDoor"] = 2
    assert clases == esperadas
    resumen = {"clases": clases, "incidencias": contrato["issues"],
               "tipos_de_origen": [elemento.get("type_name", "") for elemento in contrato["elements"]]}
    (destino / "generacion.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2))
    print(json.dumps(resumen, ensure_ascii=False, indent=2))


def generar_forjados(destino):
    """Cuatro contornos reales permiten comprobar medidas sin envolventes."""
    destino.mkdir(parents=True, exist_ok=True)
    documento = Document.new()
    historial = History(documento)
    contexto = SimpleNamespace(document=documento, execute=historial.execute)
    historial.execute(levels.StoreCatalog(levels.load(documento)))
    documento.doc.layers.add(slabs.LAYER)
    coseno = math.cos(math.pi / 6)
    seno = math.sin(math.pi / 6)
    girado = [(5 + x * coseno - y * seno, 1.5 + x * seno + y * coseno)
              for x, y in [(-1, -.5), (1, -.5), (1, .5), (-1, .5)]]
    circular = [(2 + .6 * math.cos(i * math.tau / 32),
                 5 + .6 * math.sin(i * math.tau / 32)) for i in range(32)]
    huecos = [[(1, 1), (3, 1), (3, 2), (1, 2)], girado, circular,
              [(5, 4), (7, 4), (7, 4.5), (5.5, 4.5), (5.5, 6), (5, 6)]]
    orden = slabs.create([(0, 0), (8, 0), (8, 8), (0, 8)], huecos,
                         thickness=.2, top=0., name="Forjado con cuatro huecos",
                         material="Hormigón")
    transactions.apply_architectural_change(contexto, orden, kind="slab")
    exchange.write(documento.doc, destino / "modelo_sintetico.arqbim",
                   project="Ensayo de contornos de huecos R26")
    documento.save_as(destino / "modelo_sintetico.dxf")


if __name__ == "__main__":
    if "forjados" in sys.argv[3:]:
        generar_forjados(Path(sys.argv[1]).resolve())
    else:
        generar(Path(sys.argv[1]).resolve(), float(sys.argv[2]),
                "lejano" in sys.argv[3:],
                "nicho" if "nicho" in sys.argv[3:] else "curvo" if "curvo" in sys.argv[3:] else "normal")

# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: comprueba la propuesta B0 y sus paños analíticos sin modificar dibujos ni importar IngeCAD.
"""Herramienta de desarrollo; no es un solucionador ni un exportador de cubiertas."""

from copy import deepcopy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

from jsonschema import Draft202012Validator
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

RAIZ = Path(__file__).resolve().parents[1]
# Leer esta fuente pura conserva la tolerancia del plugin sin cargar su registro.
especificacion = importlib.util.spec_from_file_location(
    "soldadura_cubiertas_b0", RAIZ / "arquitectura/geom/soldadura.py"
)
soldadura = importlib.util.module_from_spec(especificacion)
especificacion.loader.exec_module(soldadura)
TOLERANCIA = soldadura.TOLERANCIA
ESQUEMA = json.loads((RAIZ / "docs/esquemas/cubierta-v1.schema.json").read_text())
Draft202012Validator.check_schema(ESQUEMA)
VALIDADOR = Draft202012Validator(ESQUEMA)


def huella_entrada(modelo):
    fuente = {clave: valor for clave, valor in modelo.items() if clave != "solution"}
    texto = json.dumps(
        fuente, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _finitos(valor):
    if isinstance(valor, float) and not math.isfinite(valor):
        raise ValueError("Las medidas de cubierta deben ser finitas")
    if isinstance(valor, dict):
        for contenido in valor.values():
            _finitos(contenido)
    if isinstance(valor, list):
        for contenido in valor:
            _finitos(contenido)


def _poligono(exterior, patios):
    for anillo in [exterior, *patios]:
        if any(math.dist(a, b) <= TOLERANCIA for a, b in zip(anillo, anillo[1:] + anillo[:1])):
            raise ValueError("Lado nulo o menor que la tolerancia de soldadura")
    poligono = Polygon(exterior, patios)
    if not poligono.is_valid or poligono.area <= TOLERANCIA**2:
        raise ValueError("Contorno cruzado, patio fuera del dominio o superficie nula")
    if not poligono.exterior.is_ccw or any(anillo.is_ccw for anillo in poligono.interiors):
        raise ValueError("El exterior debe ser antihorario y los patios horarios")
    return poligono


def _normal(inicio, final):
    largo = math.dist(inicio, final)
    return (-(final[1] - inicio[1]) / largo, (final[0] - inicio[0]) / largo)


def cota(plano, punto):
    origen = plano["point"]
    pendiente = plano["gradient"]
    return origen[2] + math.fsum(pendiente[i] * (punto[i] - origen[i]) for i in range(2))


def _anillo_desplazado(puntos, lados):
    # Solo desplaza las rectas del contorno; no calcula el esqueleto ni sus eventos.
    lineas = []
    for indice, lado in enumerate(lados):
        inicio = puntos[indice]
        final = puntos[(indice + 1) % len(puntos)]
        normal = _normal(inicio, final)
        largo = math.dist(inicio, final)
        direccion = tuple((final[i] - inicio[i]) / largo for i in range(2))
        apoyo = tuple(inicio[i] - normal[i] * lado["overhang"] for i in range(2))
        lineas.append((apoyo, direccion, normal))
    resultado = []
    for indice, (actual, direccion, normal) in enumerate(lineas):
        anterior, rumbo, normal_anterior = lineas[indice - 1]
        determinante = rumbo[0] * direccion[1] - rumbo[1] * direccion[0]
        diferencia = tuple(actual[i] - anterior[i] for i in range(2))
        if abs(determinante) <= 1e-14:
            separacion = abs(sum(diferencia[i] * normal[i] for i in range(2)))
            if sum(normal[i] * normal_anterior[i] for i in range(2)) < 0 or separacion > TOLERANCIA:
                raise ValueError("Lados paralelos con vuelos incompatibles")
            resultado.append(actual)
        else:
            parametro = (diferencia[0] * direccion[1] - diferencia[1] * direccion[0]) / determinante
            resultado.append(tuple(anterior[i] + parametro * rumbo[i] for i in range(2)))
    return resultado


def validar(modelo):
    """Valida datos y, si existe, la partición manual; devuelve mediciones de referencia."""
    _finitos(modelo)
    errores = sorted(VALIDADOR.iter_errors(modelo), key=lambda error: str(list(error.path)))
    if errores:
        raise ValueError("Esquema de cubierta no válido: " + errores[0].message)
    identificadores = set()

    def registrar(identificador):
        if identificador in identificadores:
            raise ValueError("Identificador de cubierta repetido: " + identificador)
        identificadores.add(identificador)

    registrar(modelo["id"])
    anillos = [modelo["outer"], *modelo["holes"]]
    coordenadas = []
    lados_por_id = {}
    anillos_desplazados = []
    for anillo in anillos:
        registrar(anillo["id"])
        vertices = anillo["vertices"]
        for vertice in vertices:
            registrar(vertice["id"])
        puntos = [vertice["xy"] for vertice in vertices]
        coordenadas.append(puntos)
        # Verificar longitudes antes de obtener las normales o dividir por el largo.
        if any(math.dist(a, b) <= TOLERANCIA for a, b in zip(puntos, puntos[1:] + puntos[:1])):
            raise ValueError("Lado nulo o menor que la tolerancia de soldadura")
        lados = []
        for indice, vertice in enumerate(vertices):
            siguiente = vertices[(indice + 1) % len(vertices)]
            candidatos = [
                lado
                for lado in modelo["edges"]
                if lado["ring_id"] == anillo["id"]
                and lado["start_vertex_id"] == vertice["id"]
                and lado["end_vertex_id"] == siguiente["id"]
            ]
            if len(candidatos) != 1:
                raise ValueError("Cada tramo del anillo requiere exactamente un lado identificado")
            lado = candidatos[0]
            registrar(lado["id"])
            lados_por_id[lado["id"]] = (lado, vertice["xy"], siguiente["xy"])
            lados.append(lado)
            pendiente = lado["slope"]
            if lado["role"] != "eave" and pendiente is not None:
                raise ValueError("Un piñón o borde manual no tiene pendiente de faldón")
            if lado["role"] == "eave":
                if pendiente is None or (modelo["mode"] != "flat" and pendiente <= 0):
                    raise ValueError("El alero inclinado necesita una pendiente positiva")
                if modelo["mode"] == "flat" and pendiente != 0:
                    raise ValueError("La cubierta plana requiere pendiente cero")
        anillos_desplazados.append(_anillo_desplazado(puntos, lados))
    dominio_soporte = _poligono(coordenadas[0], coordenadas[1:])
    dominio = _poligono(anillos_desplazados[0], anillos_desplazados[1:])
    if len(lados_por_id) != len(modelo["edges"]):
        raise ValueError("Hay lados que no pertenecen a un tramo de los anillos")
    if modelo["layers"]:
        total = math.fsum(capa["thickness"] for capa in modelo["layers"])
        if abs(total - modelo["thickness"]["value"]) > TOLERANCIA:
            raise ValueError("Los estratos no suman el espesor declarado")
        for capa in modelo["layers"]:
            registrar(capa["id"])
    aleros = [lado for lado in modelo["edges"] if lado["role"] == "eave"]
    if modelo["mode"] == "automatic" and aleros:
        arranque = aleros[0]["start_offset"]
        if any(abs(lado["start_offset"] - arranque) > TOLERANCIA for lado in aleros):
            raise ValueError(
                "El automático no admite todavía arranques a distinta cota; use paños manuales"
            )
    solucion = modelo["solution"]
    if solucion is None:
        return {
            "estado": "sin resolver",
            "area_soporte": dominio_soporte.area,
            "area_planta": dominio.area,
        }
    if solucion["input_fingerprint"] != huella_entrada(modelo):
        raise ValueError("La solución está desactualizada respecto de su entrada")
    dibujado = _poligono(solucion["outer"], solucion["holes"])
    error_area = TOLERANCIA * max(1.0, dominio.length)
    if dibujado.symmetric_difference(dominio).area > error_area:
        raise ValueError("El contorno resuelto no coincide con los vuelos y patios")
    piezas = []
    area_real = []
    volumenes_bajo = []
    planos = []
    referencias = set()
    for faldon in solucion["facets"]:
        registrar(faldon["id"])
        poligono = _poligono(faldon["outer"], faldon["holes"])
        if poligono.difference(dominio).area > error_area:
            raise ValueError("Un faldón sale del dominio de la cubierta")
        plano = faldon["plane"]
        for identificador in faldon["source_edge_ids"]:
            if identificador not in lados_por_id:
                raise ValueError("Un faldón referencia un lado inexistente")
            lado, inicio, final = lados_por_id[identificador]
            if lado["role"] == "gable":
                raise ValueError("Un piñón no puede generar un faldón")
            referencias.add(identificador)
            if lado["role"] == "eave":
                normal = _normal(inicio, final)
                esperado = [lado["slope"] * componente for componente in normal]
                # Comparar cotas sobre una distancia local evita una tolerancia angular en metros.
                largo = max(1.0, math.dist(inicio, final))
                if math.dist(esperado, plano["gradient"]) * largo > TOLERANCIA:
                    raise ValueError("La pendiente del paño no corresponde a su lado")
                apoyo = [inicio[i] - normal[i] * lado["overhang"] for i in range(2)]
                if abs(cota(plano, apoyo) - lado["start_offset"]) > TOLERANCIA:
                    raise ValueError("La cota de arranque del paño no coincide con el alero")
        # La integral de una función afín sobre un polígono es área por su valor en el centroide.
        centro = poligono.centroid
        volumenes_bajo.append(poligono.area * cota(plano, (centro.x, centro.y)))
        area_real.append(poligono.area * math.sqrt(1.0 + sum(v * v for v in plano["gradient"])))
        piezas.append(poligono)
        planos.append(plano)
    if any(lado["id"] not in referencias for lado in aleros):
        raise ValueError("Hay un alero sin paño asociado")
    union = unary_union(piezas)
    if union.symmetric_difference(dominio).area > error_area:
        raise ValueError("Faltan paños para cubrir el dominio")
    if abs(math.fsum(p.area for p in piezas) - union.area) > error_area:
        raise ValueError("Los paños se solapan")
    for indice, pieza in enumerate(piezas):
        for otro in range(indice):
            encuentro = pieza.boundary.intersection(piezas[otro].boundary)
            if encuentro.is_empty:
                continue
            for parte in getattr(encuentro, "geoms", [encuentro]):
                if not hasattr(parte, "coords"):
                    continue
                for punto in parte.coords:
                    if abs(cota(planos[indice], punto) - cota(planos[otro], punto)) > TOLERANCIA:
                        raise ValueError("Dos paños contiguos no coinciden en cota")
    mediciones = {
        "estado": "referencia manual comprobada",
        "area_soporte": dominio_soporte.area,
        "area_planta": dominio.area,
        "area_faldones": math.fsum(area_real),
        "volumen_bajo_cota_cero_local": math.fsum(volumenes_bajo),
    }
    if modelo["thickness"]["direction"] == "vertical":
        mediciones["volumen_material_vertical"] = dominio.area * modelo["thickness"]["value"]
    return mediciones


def main(rutas):
    resultados = []
    for ruta in rutas:
        caso = json.loads(Path(ruta).read_text())
        modelo = deepcopy(caso["model"])
        try:
            medidas = validar(modelo)
        except ValueError as error:
            if caso["expected"]["decision"] != "reject":
                raise
            motivo = caso["expected"].get("reason", "")
            if motivo.casefold() not in str(error).casefold():
                raise ValueError("El rechazo no corresponde al motivo previsto") from error
            resultados.append({"caso": caso["case_id"], "rechazado": str(error)})
        else:
            if caso["expected"]["decision"] == "reject":
                raise ValueError("Se aceptó el caso que debía rechazarse: " + caso["case_id"])
            volumen = caso["expected"]["volume_below_local_zero"]
            if not math.isclose(
                medidas["volumen_bajo_cota_cero_local"], volumen, rel_tol=0.0, abs_tol=TOLERANCIA
            ):
                raise ValueError("El volumen no coincide con la referencia analítica")
            for evento in caso["expected"]["events"]:
                incidentes = [
                    f
                    for f in modelo["solution"]["facets"]
                    if Polygon(f["outer"], f["holes"]).distance(Point(evento[:2])) <= TOLERANCIA
                ]
                if len(incidentes) < 2 or any(
                    abs(cota(f["plane"], evento) - evento[2]) > TOLERANCIA for f in incidentes
                ):
                    raise ValueError("La cota del encuentro no coincide con los paños incidentes")
            resultados.append({"caso": caso["case_id"], **medidas})
    print(json.dumps(resultados, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main(sys.argv[1:])

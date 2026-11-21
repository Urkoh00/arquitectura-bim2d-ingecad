# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: lee las carpinterías y conserva sus marcas y catálogo mediante órdenes deshacibles.
from copy import deepcopy
import hashlib
import json

from .architectural import metadata
from . import memoria_carpinteria as memoria

CAPA_CATALOGO = "ARQ-CARPINTERIA-DATOS"
TIPO_CATALOGO = "carpentry_catalog"


def catalogo(dibujo):
    for entidad in dibujo.modelspace():
        datos = metadata(entidad) or {}
        if datos.get("kind") == TIPO_CATALOGO:
            return entidad, deepcopy(datos["catalogo"])
    return None, None


def leer(dibujo):
    from .exchange import read_model
    from .geom.junctions import walls_from_records
    from .levels import load
    from .level_layers import opening_level

    muros, _, huecos, _ = read_model(dibujo, strict=True)
    registros = dict(muros)
    geometria = {muro.id: muro for muro in walls_from_records(muros)}
    niveles = {nivel["id"]: nivel["name"] for nivel in load(dibujo)["levels"]}
    piezas = []
    for hueco in huecos:
        muro = geometria[hueco["wall_id"]]
        anfitrion = registros[hueco["wall_id"]]
        for pieza in memoria.unidades(muro, hueco):
            pieza["nivel_id"] = opening_level(dibujo, hueco, anfitrion)["id"] or next(iter(niveles))
            pieza["nivel"] = niveles.get(
                pieza["nivel_id"], hueco.get("level") or anfitrion.get("level") or "Sin nivel"
            )
            pieza["espesor_muro"] = muro.thickness
            pieza["mano"] = (
                "izquierda"
                if (hueco.get("hinge", 0) == 0) == (hueco.get("side", 1) > 0)
                else "derecha"
            )
            pieza["recintos"] = recintos_vecinos(dibujo, muro, pieza["registro"], pieza["nivel_id"])
            pieza["posicion"] = muro.point(hueco["offset"] + hueco["width"] / 2, 0.0)
            pieza["muro_id"] = muro.id
            piezas.append(pieza)
    return piezas


def estado_fuentes(dibujo):
    """Incluye datos y ubicación; una auditoría nunca reescribe las marcas."""
    datos = []
    for entidad in dibujo.modelspace():
        registro = metadata(entidad) or {}
        if registro.get("kind") in ("wall", "opening", "space"):
            datos.append(registro)
    texto = json.dumps(
        sorted(datos, key=lambda r: (r["kind"], r["id"])), sort_keys=True, ensure_ascii=True
    )
    return hashlib.sha256(texto.encode()).hexdigest()


def preparar(dibujo):
    from core.actions import AddEntityCommand
    from core.layers import NewLayerCommand
    from .architectural import _xdata
    from .architectural_v10 import EditArchitecturalCommand
    from .transactions import SafeArchitecturalCommand

    entidad_catalogo, anterior = catalogo(dibujo)
    grupos, nuevo = memoria.asignar_marcas(leer(dibujo), anterior)
    marcas = {}
    for grupo in grupos:
        for pieza in grupo["piezas"]:
            origen = pieza["origen"]
            if origen in marcas and marcas[origen] != grupo["marca"]:
                raise ValueError(
                    "Los frentes de un armario requieren marcas distintas; no se puede guardar una marca única"
                )
            marcas[origen] = grupo["marca"]
    ordenes = []
    for entidad in dibujo.modelspace():
        registro = metadata(entidad) or {}
        if registro.get("kind") == "opening" and registro.get("id") in marcas:
            nuevo_registro = {**registro, "mark": marcas[registro["id"]], "mark_manual": False}
            if registro != nuevo_registro:
                ordenes.append(EditArchitecturalCommand(entidad, nuevo_registro))
    registro_catalogo = {"kind": TIPO_CATALOGO, "schema": 1, "catalogo": nuevo}
    if entidad_catalogo is None:
        if CAPA_CATALOGO not in dibujo.layers:
            ordenes.append(NewLayerCommand(CAPA_CATALOGO))

        def crear_catalogo(espacio):
            entidad = espacio.add_point((0.0, 0.0), dxfattribs={"invisible": 1})
            return _xdata(espacio, entidad, registro_catalogo)

        ordenes.append(
            AddEntityCommand("ARQ catálogo de marcas", crear_catalogo, layer=CAPA_CATALOGO)
        )
    elif metadata(entidad_catalogo) != registro_catalogo:
        ordenes.append(EditArchitecturalCommand(entidad_catalogo, registro_catalogo))
    return grupos, SafeArchitecturalCommand("ARQ marcas de carpintería", ordenes)


def recintos_vecinos(dibujo, muro, registro, nivel_id):
    """Muestrea ambas caras del vano; un hueco largo puede dar a varios recintos."""
    from .geom import polygon as poligonos
    from .geom.soldadura import TOLERANCIA
    from .levels import load

    cotas = {nivel["id"]: nivel["elevation"] for nivel in load(dibujo)["levels"]}
    muestras = []
    for fraccion in (0.25, 0.5, 0.75):
        estacion = registro["offset"] + registro["width"] * fraccion
        for cara in (muro.lo - 0.01, muro.hi + 0.01):
            muestras.append(muro.point(estacion, cara))
    vecinos = []
    for entidad in dibujo.modelspace():
        datos = metadata(entidad) or {}
        if datos.get("kind") != "space" or entidad.dxftype() != "LWPOLYLINE":
            continue
        if datos.get("level_id"):
            if datos["level_id"] != nivel_id:
                continue
        elif abs(float(datos.get("base", 0)) - cotas.get(nivel_id, 0)) > TOLERANCIA:
            continue
        exterior = [tuple(punto) for punto in entidad.get_points("xy")]
        patios = datos.get("islands", [])
        if any(
            poligonos.point_in_polygon(punto, exterior)
            and not any(poligonos.point_in_polygon(punto, patio) for patio in patios)
            for punto in muestras
        ):
            vecinos.append(datos.get("name") or datos.get("number") or "Recinto sin nombre")
    return sorted(set(vecinos))


def transmitancia(pieza, biblioteca):
    """Estimación por áreas proyectadas, sin inventar el puente lineal del fabricante."""
    if not biblioteca or pieza["registro"]["type"] != "window":
        return None
    from . import biblioteca_termica as termica
    from .geom import polygon as poligonos
    import math

    materiales = pieza["definicion"]["materiales"]
    valores = []
    for apartado, papel in (("vidrios", "glass"), ("marcos", "frame")):
        coincidencias = [
            dato
            for nombre, dato in biblioteca.get(apartado, {}).items()
            if termica._plano(nombre) == termica._plano(materiales[papel])
        ]
        if len(coincidencias) != 1:
            return None
        valor = coincidencias[0].get("u")
        if not isinstance(valor, (int, float)) or not math.isfinite(valor) or valor <= 0:
            return None
        valores.append(valor)
    area_vidrio = 0.0
    for parte in pieza["medidas"]["plantillas"]:
        if parte["role"] != "glass":
            continue
        if "box" in parte:
            inicio, final, _, _, inferior, superior = parte["box"]
            area_vidrio += (final - inicio) * (superior - inferior)
        else:
            exterior, patios, _, _ = parte["prism"]
            area_vidrio += abs(poligonos.area(exterior)) - sum(
                abs(poligonos.area(patio)) for patio in patios
            )
    medidas = pieza["medidas"]
    area_total = medidas["ancho"] * medidas["alto"]
    if not 0 < area_vidrio < area_total:
        return None
    vidrio, marco = valores
    return (vidrio * area_vidrio + marco * (area_total - area_vidrio)) / area_total


def filas(grupos, configuracion, biblioteca=None):
    """Filtra unidades, conserva la marca global y agrega su localización y sus manos."""
    from collections import Counter

    resultado = []
    for grupo in grupos:
        seleccionadas = [
            pieza
            for pieza in grupo["piezas"]
            if (configuracion["planta"] == "all" or pieza["nivel_id"] == configuracion["planta"])
            and (configuracion["huecos"] or pieza["prefijo"] != "H")
        ]
        niveles = sorted({pieza["nivel_id"] for pieza in seleccionadas}, key=str)
        lotes = (
            [seleccionadas]
            if configuracion["agrupar"] == "marca"
            else [
                [pieza for pieza in seleccionadas if pieza["nivel_id"] == nivel]
                for nivel in niveles
            ]
        )
        for piezas in lotes:
            if not piezas:
                continue
            representante = piezas[0]
            espesores = []
            for pieza in piezas:
                grupo_espesor = next(
                    (
                        grupo
                        for grupo in espesores
                        if memoria.iguales(grupo[0], pieza["espesor_muro"])
                    ),
                    None,
                )
                if grupo_espesor is None:
                    espesores.append([pieza["espesor_muro"], 1])
                else:
                    grupo_espesor[1] += 1
            espesor = min(espesores, key=lambda grupo: (-grupo[1], grupo[0]))[0]
            medidas = representante["medidas"]
            area = medidas["ancho"] * medidas["alto"]
            resultado.append(
                {
                    "marca": grupo["marca"],
                    "piezas": piezas,
                    "unidades": len(piezas),
                    "medidas": medidas,
                    "definicion": grupo["definicion"],
                    "manos": dict(Counter(pieza["mano"] for pieza in piezas)),
                    "plantas": sorted({pieza["nivel"] for pieza in piezas}),
                    "recintos": sorted(
                        {nombre for pieza in piezas for nombre in pieza["recintos"]}
                    ),
                    "espesor_muro": espesor,
                    "area_unitaria": area,
                    "area_total": area * len(piezas),
                    "u": transmitancia(representante, biblioteca),
                }
            )
    return sorted(
        resultado, key=lambda fila: (fila["marca"][0], int(fila["marca"][1:]), fila["plantas"])
    )

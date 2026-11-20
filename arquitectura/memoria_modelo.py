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

    muros, _, huecos, _ = read_model(dibujo, strict=True)
    registros = dict(muros)
    geometria = {muro.id: muro for muro in walls_from_records(muros)}
    niveles = {nivel["id"]: nivel["name"] for nivel in load(dibujo)["levels"]}
    piezas = []
    for hueco in huecos:
        muro = geometria[hueco["wall_id"]]
        anfitrion = registros[hueco["wall_id"]]
        for pieza in memoria.unidades(muro, hueco):
            pieza["nivel_id"] = hueco.get("level_id", anfitrion.get("level_id"))
            pieza["nivel"] = niveles.get(
                pieza["nivel_id"], hueco.get("level") or anfitrion.get("level") or "Sin nivel"
            )
            pieza["espesor_muro"] = muro.thickness
            pieza["mano"] = (
                "izquierda"
                if (hueco.get("hinge", 0) == 0) == (hueco.get("side", 1) > 0)
                else "derecha"
            )
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

# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: coloca capas desde el exterior físico y clasifica el aislamiento por el catálogo.
"""Reglas constructivas puras, compartibles con la extensión de IngeTrazo."""
import math

from .geom.soldadura import TOLERANCIA
from .wall_categories import category


ORDENES = ("cara-dibujada", "exterior-interior")
CARAS = ("auto", "izquierda", "derecha")
CLASES_MATERIAL = ("aislante", "fabrica", "hoja", "revestimiento", "trasdosado", "camara")
ENVOLVENTES = ("fachada", "medianera", "sotano")


def validar_orden_y_cara(registro):
    """Validación común de las fichas, la creación y el intercambio editable."""
    if registro.get('cara_exterior', 'auto') not in CARAS:
        raise ValueError('Cara exterior: auto, izquierda o derecha')
    if 'orden_capas' in registro and registro['orden_capas'] not in ORDENES:
        raise ValueError('Orden de capas no válido')


def lado_exterior(registro, lados):
    """La anulación explícita prevalece; auto conserva lo indeterminado."""
    cara = registro.get("cara_exterior", "auto")
    if cara not in CARAS:
        raise ValueError("Cara exterior: auto, izquierda o derecha")
    if cara != "auto":
        return cara
    return lados.get(registro["id"])


def colocar(registro, muro, lados):
    """Bandas físicas de material o None si no deben reinterpretarse sus capas."""
    capas = registro.get("layers") or []
    if not capas:
        return None, []
    orden = registro.get("orden_capas")
    if orden is None:
        if category(registro) in ENVOLVENTES:
            tipo = registro.get("type_name") or "Sin nombre"
            return None, [f"Tipo «{tipo}»: revise el orden de capas; conserva el significado anterior"]
        return None, []
    if orden not in ORDENES:
        raise ValueError("Orden de capas no válido")
    if orden == "cara-dibujada":
        return None, []
    lado = lado_exterior(registro, lados)
    if lado not in ("izquierda", "derecha"):
        return None, [f"Muro {registro['id']}: cara exterior indeterminada; indique izquierda o derecha"]
    total = math.fsum(float(espesor) for espesor, _material in capas)
    if abs(total - muro.thickness) > TOLERANCIA:
        return None, [f"Muro {registro['id']}: las capas no suman su espesor"]
    posicion = muro.hi if lado == "izquierda" else muro.lo
    sentido = -1 if lado == "izquierda" else 1
    resultado = []
    for espesor, material in capas:
        siguiente = posicion + sentido * float(espesor)
        resultado.append({"min": min(posicion, siguiente), "max": max(posicion, siguiente),
                          "material": material, "espesor": float(espesor)})
        posicion = siguiente
    return resultado, []


def aislamiento(capas, catalogo):
    """Posición, material y espesor según clases explícitas, nunca según nombres."""
    if not capas:
        return None, ["muro en contacto sin capas: no se deduce aislamiento automático"]
    materiales = {nombre.strip().casefold(): datos for nombre, datos
                  in catalogo.get("materiales", {}).items()}
    clases = []
    avisos = []
    for espesor, material in capas:
        if isinstance(espesor, bool) or not math.isfinite(float(espesor)) or float(espesor) <= 0:
            return None, ["espesor de capa no válido"]
        clase = materiales.get(str(material).strip().casefold(), {}).get("clase_constructiva")
        if clase not in CLASES_MATERIAL:
            avisos.append(f"Material «{material}» sin clasificación constructiva: no se resuelve")
        clases.append(clase)
    if avisos:
        return None, avisos
    aislantes = [indice for indice, clase in enumerate(clases) if clase == "aislante"]
    if not aislantes:
        return None, []
    if len(aislantes) != 1:
        return None, ["varias capas aislantes: seleccione el aislamiento del pilar"]
    indice = aislantes[0]
    fuera = clases[:indice]
    dentro = clases[indice + 1:]
    hoja_fuera = any(clase in ("fabrica", "hoja") for clase in fuera)
    hoja_dentro = any(clase in ("fabrica", "hoja") for clase in dentro)
    if hoja_fuera and hoja_dentro:
        posicion = "camara"
    elif not hoja_fuera and hoja_dentro and all(clase == "revestimiento" for clase in fuera):
        posicion = "exterior"
    elif hoja_fuera and not hoja_dentro and all(clase in ("revestimiento", "trasdosado") for clase in dentro):
        posicion = "interior"
    else:
        return None, ["posición del aislamiento indeterminada entre las hojas y los acabados"]
    espesor, material = capas[indice]
    return {"posicion": posicion, "espesor": float(espesor), "material": str(material)}, []

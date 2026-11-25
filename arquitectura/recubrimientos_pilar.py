# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: resuelve la partición y el aislamiento del pilar a partir de sus muros de contacto.
"""Reglas del recubrimiento sin dependencias de los anfitriones CAD."""
from copy import deepcopy
import math
import unicodedata

from .geom import junctions as encuentros, polygon as poligonos
from .geom.soldadura import TOLERANCIA
from .sections import column_geometry


MODOS_AISLAMIENTO = (("Automático", "auto"), ("Con aislamiento", "con"), ("Sin aislamiento", "sin"))
CAMPOS = (
    "cover_type", "cover_material", "insulation_mode", "insulation_thickness",
    "insulation_material", "insulation_resolved_thickness", "insulation_resolved_material",
)


def normalizar(datos):
    """Conserva cover como espesor de la partición; separa el aislamiento añadido."""
    salida = deepcopy(datos)
    salida.setdefault("cover", 0.0)
    salida.setdefault("cover_type", "")
    salida.setdefault("cover_material", "Partición de recubrimiento")
    salida.setdefault("insulation_mode", "auto")
    salida.setdefault("insulation_thickness", 0.05)
    salida.setdefault("insulation_material", "Aislamiento")
    for campo in ("cover", "insulation_thickness", "insulation_resolved_thickness"):
        valor = salida.get(campo, 0.0)
        if isinstance(valor, bool):
            raise ValueError("Espesor de recubrimiento no válido")
        valor = float(valor)
        if not math.isfinite(valor) or valor < 0:
            raise ValueError("Los espesores de recubrimiento deben ser finitos y no negativos")
        salida[campo] = valor
    if salida["insulation_mode"] not in {valor for _, valor in MODOS_AISLAMIENTO}:
        raise ValueError("Modo de aislamiento de pilar no válido")
    if salida["insulation_mode"] == "con" and salida["insulation_thickness"] <= 0:
        raise ValueError("Indique un espesor positivo para el aislamiento del pilar")
    return salida


def espesor_total(datos):
    """Espesor geométrico: partición más aislamiento resuelto, en metros."""
    return float(datos.get("cover") or 0) + float(datos.get("insulation_resolved_thickness") or 0)


def _texto(texto):
    return "".join(
        letra for letra in unicodedata.normalize("NFD", str(texto).casefold())
        if not unicodedata.combining(letra)
    )


def _aislamiento_muro(muro, catalogo, lados):
    from . import capas_envolvente as capas

    if not muro.get("layers"):
        return None, ["muro en contacto sin capas: no se deduce aislamiento automático"]
    if muro.get("orden_capas") != "exterior-interior":
        tipo = muro.get("type_name") or "Sin nombre"
        return None, [f"Tipo «{tipo}»: revise el orden de capas; conserva el significado anterior"]
    if capas.lado_exterior(muro, lados) is None:
        return None, ["cara exterior indeterminada: no se deduce aislamiento automático"]
    candidato, avisos = capas.aislamiento(muro['layers'], catalogo)
    if candidato is None or candidato['posicion'] == 'exterior':
        return None, avisos
    return (candidato['espesor'], candidato['material']), avisos


def _coinciden_en_altura(pilar, muro):
    base_pilar, base_muro = float(pilar.get("base", 0)), float(muro.get("base", 0))
    return min(base_pilar + float(pilar["height"]), base_muro + float(muro["height"])) > (
        max(base_pilar, base_muro) + TOLERANCIA
    )


def resolver(pilar, muros, catalogo=None, lados=None):
    """Devuelve datos nuevos y avisos; nunca modifica el pilar ni sus muros."""
    catalogo = catalogo or {}
    lados = lados or {}
    salida = normalizar(pilar)
    salida["insulation_resolved_thickness"] = 0.0
    salida["insulation_resolved_material"] = ""
    if salida["cover"] <= 0 or salida["insulation_mode"] == "sin":
        return salida, []
    if salida["insulation_mode"] == "con":
        salida["insulation_resolved_thickness"] = salida["insulation_thickness"]
        salida["insulation_resolved_material"] = salida["insulation_material"]
        return salida, []
    nucleo = column_geometry(salida["center"], {
        **salida, "cover": 0, "insulation_resolved_thickness": 0,
    })["footprint"]
    piezas_nucleo = poligonos.convex_parts(nucleo)
    candidatos, avisos = [], []
    for identificador, muro in muros:
        if muro.get("wall_category") not in ("fachada", "medianera", "sotano"):
            continue
        if not _coinciden_en_altura(salida, muro):
            continue
        forma = encuentros.walls_from_records([(identificador, muro)])[0]
        area = poligonos.overlap_area(piezas_nucleo, poligonos.convex_parts(forma.strip()))
        if area <= TOLERANCIA * TOLERANCIA:
            continue
        candidato, avisos_muro = _aislamiento_muro(muro, catalogo, lados)
        for aviso in avisos_muro:
            avisos.append(f"Pilar {salida['id']}, muro {identificador}: {aviso}")
        if candidato:
            candidatos.append(candidato)
    if candidatos:
        espesor, material = candidatos[0]
        if any(abs(otro - espesor) > TOLERANCIA or _texto(nombre) != _texto(material)
               for otro, nombre in candidatos[1:]):
            avisos.append(f"Pilar {salida['id']}: muros con aislamientos distintos; elija Con o Sin")
        else:
            salida["insulation_resolved_thickness"] = espesor
            salida["insulation_resolved_material"] = material
    return salida, avisos

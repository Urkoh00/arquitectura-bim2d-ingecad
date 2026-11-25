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


def aplicar_tipo(datos, tipos=None):
    """El tipo elegido fija su espesor; un nombre desconocido no se interpreta."""
    salida = normalizar(datos)
    nombre = salida['cover_type']
    if nombre and tipos is not None:
        tipo = next((tipo for tipo in tipos if tipo['name'] == nombre), None)
        if tipo is None or tipo.get('wall_category') != 'particion':
            raise ValueError('Elija un tipo de partición para el recubrimiento')
        salida['cover'] = math.fsum(float(espesor) for espesor, _material in tipo['layers'])
        salida['cover_material'] = ' / '.join(str(material) for _espesor, material in tipo['layers'])
    return salida


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
        return (None if avisos else (0.0, '')), avisos
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
    if candidatos and not avisos:
        espesor, material = candidatos[0]
        if any(abs(otro - espesor) > TOLERANCIA or _texto(nombre) != _texto(material)
               for otro, nombre in candidatos[1:]):
            avisos.append(f"Pilar {salida['id']}: muros con aislamientos distintos; elija Con o Sin")
        else:
            salida["insulation_resolved_thickness"] = espesor
            salida["insulation_resolved_material"] = material
    return salida, avisos


def en_altura(datos, elevacion):
    """Una sección de pilar; las franjas se consultan sin alterar el registro."""
    salida = dict(datos)
    for franja in datos.get('insulation_bands', []):
        if franja['base'] <= elevacion < franja['base'] + franja['height']:
            salida.update({campo: franja[campo] for campo in (
                'insulation_resolved_thickness', 'insulation_resolved_material')})
            break
    return salida


def resolver_franjas(pilar, muros, catalogo=None, lados=None):
    """Un pilar que cruza plantas conserva el aislamiento de cada tramo real."""
    base = float(pilar.get('base', 0))
    cima = base + float(pilar['height'])
    if not math.isfinite(base) or not math.isfinite(cima) or cima <= base:
        raise ValueError('El pilar necesita una cota finita y una altura positiva')
    cotas = {base, cima}
    for _identificador, muro in muros:
        inferior = float(muro.get('base', 0))
        superior = inferior + float(muro['height'])
        cotas.update(cota for cota in (inferior, superior) if base < cota < cima)
    cotas = sorted(cotas)
    salida = normalizar(pilar)
    franjas = []
    avisos = []
    for inferior, superior in zip(cotas, cotas[1:]):
        if superior - inferior <= TOLERANCIA:
            continue
        tramo, notas = resolver({**pilar, 'base': inferior, 'height': superior - inferior},
                                 muros, catalogo, lados)
        franjas.append({campo: tramo[campo] for campo in (
            'base', 'height', 'insulation_resolved_thickness', 'insulation_resolved_material')})
        avisos.extend(nota for nota in notas if nota not in avisos)
    salida['insulation_bands'] = franjas
    mayor = max(franjas, key=lambda franja: franja['insulation_resolved_thickness'])
    salida['insulation_resolved_thickness'] = mayor['insulation_resolved_thickness']
    salida['insulation_resolved_material'] = mayor['insulation_resolved_material']
    return salida, avisos


def resolver_modelo(muros, pilares, catalogo, recintos=()):
    """Lectura derivada pura: no escribe entidades, catálogos ni archivos."""
    from .geom.bands import solve_records
    from .capas_envolvente import lados_del_modelo

    if not pilares:
        return pilares, []
    lados = {}
    necesita_exterior = any(float(pilar.get('cover') or 0) > 0 and
                           pilar.get('insulation_mode', 'auto') == 'auto' for _identificador, pilar in pilares)
    tipos_orientados = any(muro.get('layers') and muro.get('orden_capas') == 'exterior-interior'
                          for _identificador, muro in muros)
    if necesita_exterior and tipos_orientados:
        sin_aislamiento = []
        for identificador, pilar in pilares:
            copia = {**pilar, 'insulation_resolved_thickness': 0}
            copia.pop('insulation_bands', None)
            copia['polygon'] = column_geometry(copia['center'], copia)['footprint']
            sin_aislamiento.append((identificador, copia))
        # El exterior se obtiene antes de añadir el aislamiento que depende de él.
        lados = lados_del_modelo(solve_records(muros, sin_aislamiento), recintos)
    resultado = []
    avisos = []
    for identificador, pilar in pilares:
        resuelto, notas = resolver_franjas(pilar, muros, catalogo, lados)
        seccion_base = en_altura(resuelto, float(resuelto.get('base', 0)) + TOLERANCIA)
        resuelto['polygon'] = column_geometry(resuelto['center'], seccion_base)['footprint']
        resultado.append((identificador, resuelto))
        avisos.extend(nota for nota in notas if nota not in avisos)
    return resultado, avisos


def capas_geometricas(pilar, resultado):
    """Piezas convexas de cada capa, recortadas con los mismos encuentros."""
    identificador = pilar['id']
    capas = {'CLADDING': [], 'INSULATION': []}
    franjas = getattr(resultado, 'column_bands', {}).get(identificador, [])
    for inferior, superior, contorno in franjas:
        datos = en_altura(pilar, (inferior + superior) / 2)
        aislante = float(datos.get('insulation_resolved_thickness') or 0)
        nucleo = column_geometry(datos['center'], {**datos, 'cover': 0,
                                 'insulation_resolved_thickness': 0})['sections']
        interfaz = column_geometry(datos['center'], {**datos, 'cover': 0})['footprint']
        libre = poligonos.convex_parts(contorno)
        for seccion in nucleo:
            libre = poligonos.subtract(libre, seccion)
        particion = poligonos.subtract(libre, interfaz) if aislante > 0 else libre
        aislamiento = []
        if aislante > 0:
            for pieza in libre:
                recorte = poligonos.convex_intersection(pieza, interfaz)
                if recorte and poligonos.area(recorte) > TOLERANCIA ** 2:
                    aislamiento.append(recorte)
        for tipo, piezas, espesor, material in (
            ('CLADDING', particion, float(datos.get('cover') or 0), datos.get('cover_material', '')),
            ('INSULATION', aislamiento, aislante, datos.get('insulation_resolved_material', '')),
        ):
            if piezas:
                capas[tipo].append({'base': inferior, 'height': superior - inferior,
                                     'pieces': piezas, 'thickness': espesor, 'material': material})
    return capas

# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: valida el fichero de procedencia de una entrada revisada y autoriza
# solo las caras, puertas y ventanas confirmadas, sin importar datos BIM externos.
"""Contrato arq.entrada-revisada/v1; no contiene lógica del laboratorio."""
from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from datetime import date
import hashlib
import json
from pathlib import Path
import re

ESQUEMA = "arq.entrada-revisada/v1"
ESTADOS = {"confirmado", "pendiente", "rechazado", "candidato"}
PAPELES = {"muro-cara", "muro-eje", "puerta", "ventana", "hueco"}
CATEGORIAS_CONFIRMADAS = {"muro-cara": "muros", "puerta": "puertas", "ventana": "ventanas"}
TIPOS_GEOMETRICOS = {"LINE", "LWPOLYLINE", "ARC", "HATCH", "SOLID", "TRACE"}


def es_capa_revisada(nombre):
    """El prefijo reservado nunca basta para autorizar una conversión."""
    return str(nombre).strip().casefold().startswith("rev-")


def hash_archivo(ruta):
    """Calcula el hash sin cargar un DXF grande entero en memoria."""
    resumen = hashlib.sha256()
    with Path(ruta).open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
            resumen.update(bloque)
    return resumen.hexdigest()


def _objeto_sin_duplicados(pares):
    resultado = {}
    for clave, valor in pares:
        if clave in resultado:
            raise ValueError("La procedencia contiene una clave repetida: " + clave)
        resultado[clave] = valor
    return resultado


def _comprobar_claves(objeto, obligatorias, opcionales=()):
    if not isinstance(objeto, dict):
        raise ValueError("La procedencia contiene un objeto no válido")
    if not set(obligatorias).issubset(objeto) or set(objeto) - set(obligatorias) - set(opcionales):
        raise ValueError("La procedencia contiene campos ausentes o desconocidos")


def _comprobar_hash(resumen):
    if not isinstance(resumen, str) or re.fullmatch(r"[0-9a-f]{64}", resumen) is None:
        raise ValueError("El hash SHA-256 no es válido")


@dataclass(frozen=True)
class ProcedenciaRevisada:
    ruta: Path
    ruta_fuente: Path
    hash_procedencia: str
    hash_fuente: str
    huella_dibujo: str
    asignaciones: tuple

    def categoria(self, entidad):
        """Consulta inmutable; las asignaciones manuales no elevan una revisión."""
        identificador = entidad.dxf.handle or ""
        posicion = bisect_left(self.asignaciones, (identificador, ""))
        if posicion < len(self.asignaciones):
            encontrado, categoria = self.asignaciones[posicion]
            if encontrado == identificador:
                return categoria
        return None

    def comprobar(self, dibujo):
        from .conversion_plan import fingerprint

        if not dibujo.filename or Path(dibujo.filename).resolve() != self.ruta_fuente.resolve():
            raise ValueError("La procedencia no corresponde al fichero DXF activo")
        try:
            if hash_archivo(self.ruta) != self.hash_procedencia:
                raise ValueError("La procedencia cambió; vuelva a cargarla y analizar")
            if hash_archivo(self.ruta_fuente) != self.hash_fuente:
                raise ValueError("El DXF fuente cambió; vuelva a revisar y analizar")
        except OSError as error:
            raise ValueError("No se puede comprobar la procedencia o el DXF") from error
        if fingerprint(dibujo) != self.huella_dibujo:
            raise ValueError("El dibujo cambió respecto al DXF revisado")

    def resumen_capa(self, dibujo, nombre):
        categorias = set()
        confirmadas = 0
        for entidad in dibujo.modelspace():
            if entidad.dxf.layer != nombre:
                continue
            categoria = self.categoria(entidad)
            if categoria is not None:
                confirmadas += 1
                categorias.add(categoria)
        if not confirmadas:
            return "No convertir"
        nombres = {"muros": "caras de muro", "puertas": "puertas", "ventanas": "ventanas"}
        clases = ", ".join(nombres[categoria] for categoria in sorted(categorias))
        return f"Solo {confirmadas} entidades confirmadas: {clases}"


def cargar_procedencia(ruta, dibujo):
    """Valida el contrato y el DXF local; nunca abre la fuente original."""
    from .conversion_plan import fingerprint
    import ezdxf

    ruta = Path(ruta).expanduser().resolve()
    try:
        if ruta.stat().st_size > 4 * 1024 * 1024:
            raise ValueError("El fichero de procedencia supera 4 MiB")
        contenido = ruta.read_bytes()
        datos = json.loads(contenido, object_pairs_hook=_objeto_sin_duplicados)
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError("No se puede leer el JSON de procedencia") from error
    _comprobar_claves(datos, ("schema", "dxf", "source", "units", "scale_checked", "review", "layers"), ("entities",))
    if datos["schema"] != ESQUEMA:
        raise ValueError("Esquema de procedencia desconocido")
    if datos["units"] != "m" or datos["scale_checked"] is not True:
        raise ValueError("La entrada necesita metros y escala comprobada")
    revision = datos["review"]
    _comprobar_claves(revision, ("state", "date"), ("reviewer",))
    if revision["state"] != "revisado":
        raise ValueError("La entrada no declara el estado global revisado")
    fecha = revision["date"]
    if not isinstance(fecha, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha) is None:
        raise ValueError("La fecha de revisión debe tener formato AAAA-MM-DD")
    try:
        date.fromisoformat(fecha)
    except ValueError as error:
        raise ValueError("La fecha de revisión no existe") from error
    if "reviewer" in revision and (not isinstance(revision["reviewer"], str) or not revision["reviewer"].strip()):
        raise ValueError("El nombre del revisor no es válido")
    original = datos["source"]
    _comprobar_claves(original, ("name", "sha256"))
    if not isinstance(original["name"], str) or not original["name"].strip():
        raise ValueError("Falta el nombre de la fuente original")
    _comprobar_hash(original["sha256"])
    # source es informativo: la aplicación no tiene por qué disponer del
    # croquis, foto o PDF y no debe buscarlo ni leerlo para activar este modo.
    fuente = datos["dxf"]
    _comprobar_claves(fuente, ("name", "sha256"))
    nombre = fuente["name"]
    if not isinstance(nombre, str) or not nombre or any(caracter in nombre for caracter in "/\\:"):
        raise ValueError("El DXF debe ser un nombre de fichero sin ruta")
    if Path(nombre).suffix.casefold() != ".dxf":
        raise ValueError("El fichero declarado no es un DXF")
    if ruta.name != nombre + ".procedencia.json":
        raise ValueError("La procedencia debe llamarse <dxf>.procedencia.json")
    resumen = fuente["sha256"]
    _comprobar_hash(resumen)
    ruta_fuente = ruta.parent / nombre
    if not dibujo.filename or Path(dibujo.filename).resolve() != ruta_fuente.resolve():
        raise ValueError("La procedencia debe estar junto al fichero DXF activo")
    try:
        if hash_archivo(ruta_fuente) != resumen:
            raise ValueError("El hash del DXF no coincide")
        dibujo_fuente = ezdxf.readfile(ruta_fuente)
    except (OSError, ezdxf.DXFError) as error:
        raise ValueError("No se puede leer el DXF de procedencia") from error
    if int(dibujo_fuente.header.get("$INSUNITS", 0)) not in (0, 6):
        raise ValueError("Las unidades del DXF no son metros")
    huella = fingerprint(dibujo_fuente)
    if fingerprint(dibujo) != huella:
        raise ValueError("El dibujo activo no coincide con el DXF revisado")
    capas = datos["layers"]
    if not isinstance(capas, dict):
        raise ValueError("Las capas revisadas deben ser un objeto")
    nombres_dxf = {capa.dxf.name.strip().casefold() for capa in dibujo.layers if es_capa_revisada(capa.dxf.name)}
    capas_revisadas = {}
    for nombre_capa, fila in capas.items():
        nombre_normalizado = nombre_capa.strip().casefold()
        if not es_capa_revisada(nombre_capa) or nombre_normalizado in capas_revisadas:
            raise ValueError("Capa de revisión no válida o repetida")
        _comprobar_claves(fila, ("role", "state"))
        if not isinstance(fila["role"], str) or not isinstance(fila["state"], str) or fila["role"] not in PAPELES or fila["state"] not in ESTADOS:
            raise ValueError("Papel o estado de capa no válido")
        capas_revisadas[nombre_normalizado] = fila
    if set(capas_revisadas) != nombres_dxf:
        raise ValueError("La procedencia no describe exactamente las capas REV-* del DXF")
    entidades = {entidad.dxf.handle: entidad for entidad in dibujo.modelspace()}
    excepciones = datos.get("entities", {})
    if not isinstance(excepciones, dict) or len(excepciones) > 200000:
        raise ValueError("Las excepciones por entidad no son válidas")
    for identificador, fila in excepciones.items():
        _comprobar_claves(fila, ("state",))
        entidad = entidades.get(identificador)
        if entidad is None or not es_capa_revisada(entidad.dxf.layer):
            raise ValueError("La excepción no identifica una entidad REV-* del espacio modelo")
        if not isinstance(fila["state"], str) or fila["state"] not in ESTADOS:
            raise ValueError("Estado de entidad no válido")
    asignaciones = []
    for identificador, entidad in entidades.items():
        fila = capas_revisadas.get(entidad.dxf.layer.strip().casefold())
        if fila is None:
            continue
        estado = excepciones.get(identificador, fila)["state"]
        categoria = CATEGORIAS_CONFIRMADAS.get(fila["role"])
        if estado == "confirmado" and categoria is not None and entidad.dxftype() in TIPOS_GEOMETRICOS:
            asignaciones.append((identificador, categoria))
    procedencia = ProcedenciaRevisada(
        ruta=ruta,
        ruta_fuente=ruta_fuente,
        hash_procedencia=hashlib.sha256(contenido).hexdigest(),
        hash_fuente=resumen,
        huella_dibujo=huella,
        asignaciones=tuple(sorted(asignaciones)),
    )
    # Otra aplicación podría haber escrito el DXF mientras se analizaba.
    procedencia.comprobar(dibujo)
    return procedencia


def ruta_contigua(documento):
    """El contrato de plano.dxf se llama plano.dxf.procedencia.json."""
    nombre = documento.path
    if not nombre:
        return None
    ruta = Path(str(nombre) + ".procedencia.json")
    return ruta if ruta.is_file() else None

def filtrar_huecos(muros, huecos, curvas, huecos_curvos, detalles, entidades):
    """Una interrupción sin revisión no autoriza a cerrar un muro ni a cortarlo.

    El lector normal puede deducir vanos a partir de huecos entre líneas. En
    esta entrada se conserva el muro completo para revisión si alguno de sus
    vanos no está respaldado por una puerta o ventana confirmada. No se inventa
    otra geometría para rellenar la interrupción.
    """
    from .convert_tools import _segments
    from .geom.junctions import Wall

    categorias = {"door": "puertas", "window": "ventanas"}
    pendientes = set()
    for indice, posicion, ancho, clase, bisagra, lado in huecos:
        categoria = categorias.get(clase)
        apoyado = False
        inicio, fin, espesor = muros[indice]
        muro = Wall("revision", inicio, fin, espesor, "eje")
        margen = max(.08, min(.2, .15 * ancho))
        for entidad, papel in entidades:
            if papel != categoria:
                continue
            trazos = _segments(entidad)
            if not trazos:
                continue
            estaciones = [muro.local(punto)[0] for trazo in trazos for punto in (trazo[:2], trazo[2:4])]
            if min(estaciones) < posicion - ancho / 2 - margen:
                continue
            if max(estaciones) > posicion + ancho / 2 + margen:
                continue
            # Una confirmación distante en otra planta de dibujo no justifica
            # este vano. El margen transversal admite el giro de su hoja.
            distancias = [abs(muro.local(punto)[1]) for trazo in trazos for punto in (trazo[:2], trazo[2:4])]
            if min(distancias) > espesor / 2 + .2:
                continue
            apoyado = True
            break
        if not apoyado:
            pendientes.add(indice)
    curvas_pendientes = {operacion[0] for operacion in huecos_curvos if operacion[3] not in categorias}
    indices_validos = [indice for indice in range(len(muros)) if indice not in pendientes]
    indices_curvos_validos = [indice for indice in range(len(curvas)) if indice not in curvas_pendientes]
    indices = {anterior: nuevo for nuevo, anterior in enumerate(indices_validos)}
    indices_curvos = {anterior: nuevo for nuevo, anterior in enumerate(indices_curvos_validos)}
    nuevos_huecos = []
    nuevos_detalles = []
    for operacion, detalle in zip(huecos, detalles):
        if operacion[0] in indices:
            nuevos_huecos.append((indices[operacion[0]], *operacion[1:]))
            nuevos_detalles.append(detalle)
    nuevas_curvas = [curva for indice, curva in enumerate(curvas) if indice not in curvas_pendientes]
    nuevos_huecos_curvos = [
        (indices_curvos[operacion[0]], *operacion[1:])
        for operacion in huecos_curvos if operacion[0] in indices_curvos
    ]
    nuevos_muros = [muro for indice, muro in enumerate(muros) if indice not in pendientes]
    return nuevos_muros, nuevos_huecos, nuevas_curvas, nuevos_huecos_curvos, nuevos_detalles, len(pendientes) + len(curvas_pendientes)

# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: BIBLIOTECAHE: importa el catálogo de materiales, composiciones,
#   vidrios, marcos y huecos de la Herramienta Unificada (fichero .bdc) a una
#   biblioteca térmica del usuario y calcula la U de una composición.
#   (Guía del código: docs/GUIA_DEL_CODIGO.md)
"""Biblioteca térmica del usuario, importada del catálogo oficial.

El plugin **no distribuye** el catálogo de la Herramienta Unificada
LIDER-CALENER (``BDCatalogo.bdc``): es un dato del Ministerio. Cada usuario lo
importa desde su propia instalación, o desde el fichero que indique, como
hacen otros programas de cálculo. Se aceptan:

- el ``.bdc`` de la instalación (texto BDL en ISO-8859-1 o UTF-8);
- el ``.bdc.utf8.gz`` que publica el IETcc-CSIC;
- un ``.zip`` que contenga uno de los anteriores.

La biblioteca se guarda en un JSON en la carpeta de configuración del
usuario, nunca en el repositorio ni en el dibujo, y se reutiliza en todos los
proyectos. Su estructura sigue la del modelo de envolvente del IETcc
(materiales, composiciones de opacos, vidrios, marcos y huecos), para que el
futuro exportador de envolvente la use sin traducciones.

Bloques BDL que se leen: ``MATERIAL`` (PROPERTIES o RESISTANCE), ``LAYERS``,
``GLASS-TYPE``, ``NAME-FRAME`` y ``GAP``. El factor solar del vidrio es
``SHADING-COEF × 0,86``, el mismo criterio que el intérprete del IETcc.

``u_opaco`` calcula la transmitancia de una composición por capas con las
resistencias superficiales del DA DB-HE/1 (tabla 1). No sustituye a los
programas reconocidos: sirve para tantear tipos de muro durante el dibujo.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import re
import unicodedata
import zipfile
from pathlib import Path

FORMATO = "arquitectura-biblioteca-termica"
VERSION = 1
#: factor del IETcc para pasar de SHADING-COEF a g⊥ (vidrio de referencia)
FACTOR_G = 0.86
#: resistencias superficiales (Rsi, Rse) en m²K/W, DA DB-HE/1, tabla 1
RESISTENCIAS_SUPERFICIALES = {
    "vertical": (0.13, 0.04),
    "ascendente": (0.10, 0.04),    # cubiertas y techos (flujo hacia arriba)
    "descendente": (0.17, 0.04),   # suelos sobre el exterior (flujo hacia abajo)
}
#: carpetas donde suele instalarse la Herramienta Unificada en Windows
CARPETAS_INSTALACION = (
    r"C:\ProgramasCTEyCEE\CTEHE2019",
    r"C:\ProgramasCTEyCEE",
)

_CABECERA = re.compile(r'^\s*"(.+?)"\s*=\s*([A-Z][A-Z-]*)\s*$')
_CAMPO = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_-]*)\s*=\s*(.*?)\s*$')
_TIPOS = ("MATERIAL", "LAYERS", "GLASS-TYPE", "NAME-FRAME", "GAP")


# ---------------------------------------------------------------- lectura

def _texto(datos: bytes) -> str:
    """Decodifica el BDL: UTF-8 si lo es; si no, ISO-8859-1 (el de la instalación)."""
    try:
        texto = datos.decode("utf-8")
    except UnicodeDecodeError:
        texto = datos.decode("iso-8859-1")
    return texto.replace("\r\n", "\n").replace("\r", "\n")


def leer_bytes(ruta) -> tuple[bytes, str]:
    """Contenido del catálogo y nombre del fichero que lo contenía."""
    ruta = Path(ruta)
    datos = ruta.read_bytes()
    if datos[:2] == b"\x1f\x8b":
        return gzip.decompress(datos), ruta.name
    if datos[:4] == b"PK\x03\x04":
        with zipfile.ZipFile(io.BytesIO(datos)) as z:
            nombres = [n for n in z.namelist()
                       if n.lower().endswith((".bdc", ".bdc.utf8", ".bdc.utf8.gz"))]
            if not nombres:
                raise ValueError(f"{ruta.name}: el ZIP no contiene ningún catálogo .bdc")
            interior = z.read(nombres[0])
            if interior[:2] == b"\x1f\x8b":
                interior = gzip.decompress(interior)
            return interior, f"{ruta.name}/{nombres[0]}"
    return datos, ruta.name


def _bloques(texto: str):
    """Bloques BDL ``"nombre" = TIPO`` con sus campos, hasta ``..``.

    Cada bloque se entrega completo: al cerrarse con ``..``, al empezar el
    siguiente o al acabar el texto."""
    actual = None
    for linea in texto.split("\n"):
        if linea.lstrip().startswith("$"):
            continue
        m = _CABECERA.match(linea)
        if m:
            if actual is not None:
                yield actual
            actual = {"nombre": _nombre(m.group(1)), "tipo": m.group(2), "campos": {}}
            continue
        if linea.strip() == "..":
            if actual is not None:
                yield actual
            actual = None
            continue
        m = _CAMPO.match(linea)
        if m and actual is not None:
            actual["campos"][m.group(1).upper()] = m.group(2)
    if actual is not None:
        yield actual


def _nombre(texto) -> str:
    """Nombre sin espacios repetidos: algunas versiones del catálogo escriben
    «Hormigón convencional  d 2400» (dos espacios) en un sitio y no en otro."""
    return " ".join(str(texto).split())


def _valor(texto: str):
    texto = texto.strip()
    if texto.startswith("("):
        return [_valor(x) for x in re.findall(r'"[^"]*"|[^,()\s]+', texto)]
    if texto.startswith('"'):
        return texto.strip('"').strip()
    try:
        return float(texto)
    except ValueError:
        return texto


def _num(campos, clave):
    v = _valor(campos.get(clave, ""))
    return v if isinstance(v, float) else None


def _lista(v):
    return v if isinstance(v, list) else [v]


def importar(ruta) -> dict:
    """Lee el catálogo y devuelve la biblioteca (sin guardarla)."""
    datos, origen = leer_bytes(ruta)
    texto = _texto(datos)
    bib = {"formato": FORMATO, "version": VERSION,
           "origen": {"fichero": origen, "sha256": hashlib.sha256(datos).hexdigest()},
           "materiales": {}, "composiciones": {}, "vidrios": {}, "marcos": {}, "huecos": {},
           "avisos": []}
    for b in _bloques(texto):
        if b["tipo"] not in _TIPOS:
            continue
        c, nombre = b["campos"], b["nombre"]
        grupo = _valor(c.get("GROUP", "")) or ""
        if b["tipo"] == "MATERIAL":
            tipo = str(_valor(c.get("TYPE", "PROPERTIES")))
            m = {"grupo": grupo, "tipo": tipo}
            if tipo == "RESISTANCE":
                m["resistencia"] = _num(c, "RESISTANCE")
            else:
                m.update(conductividad=_num(c, "CONDUCTIVITY"), densidad=_num(c, "DENSITY"),
                         calor_especifico=_num(c, "SPECIFIC-HEAT"),
                         difusion_vapor=_num(c, "VAPOUR-DIFFUSIVITY-FACTOR"))
            bib["materiales"][nombre] = m
        elif b["tipo"] == "LAYERS":
            materiales = _lista(_valor(c.get("MATERIAL", "()")))
            espesores = _lista(_valor(c.get("THICKNESS", "()")))
            if len(materiales) != len(espesores):
                bib["avisos"].append(f"Composición «{nombre}»: capas y espesores no coinciden")
                continue
            bib["composiciones"][nombre] = {
                "grupo": grupo,
                "capas": [[_nombre(m), float(e)] for m, e in zip(materiales, espesores)]}
        elif b["tipo"] == "GLASS-TYPE":
            sc = _num(c, "SHADING-COEF")
            bib["vidrios"][nombre] = {"grupo": grupo, "u": _num(c, "GLASS-CONDUCTANCE"),
                                      "g": None if sc is None else round(sc * FACTOR_G, 6)}
        elif b["tipo"] == "NAME-FRAME":
            bib["marcos"][nombre] = {"grupo": grupo, "u": _num(c, "FRAME-CONDUCT"),
                                     "absortividad": _num(c, "FRAME-ABS"),
                                     "ancho": _num(c, "FRAME-WIDTH")}
        elif b["tipo"] == "GAP":
            porcentaje = _num(c, "PORCENTAGE")
            bib["huecos"][nombre] = {
                "grupo": grupo, "vidrio": _nombre(_valor(c.get("GLASS-TYPE", "")) or ""),
                "marco": _nombre(_valor(c.get("NAME-FRAME", "")) or ""),
                "fraccion_marco": None if porcentaje is None else porcentaje / 100.0,
                "permeabilidad_100pa": _num(c, "INF-COEF")}
    # referencias rotas: se avisan, no se descartan
    for nombre, comp in bib["composiciones"].items():
        for material, _e in comp["capas"]:
            if material not in bib["materiales"]:
                bib["avisos"].append(f"Composición «{nombre}»: falta el material «{material}»")
    for nombre, hueco in bib["huecos"].items():
        for clave, apartado in (("vidrio", "vidrios"), ("marco", "marcos")):
            if hueco[clave] and hueco[clave] not in bib[apartado]:
                bib["avisos"].append(f"Hueco «{nombre}»: falta el {clave} «{hueco[clave]}»")
    if not bib["materiales"]:
        raise ValueError(f"{origen}: no contiene ningún bloque MATERIAL; ¿es un catálogo .bdc?")
    return bib


# -------------------------------------------------------------- persistencia

def ruta_usuario() -> Path:
    """JSON de la biblioteca: ``ARQ_BIBLIOTECA_TERMICA`` o la carpeta de configuración."""
    propia = os.environ.get("ARQ_BIBLIOTECA_TERMICA")
    if propia:
        return Path(propia).expanduser()
    base = os.environ.get("APPDATA") if os.name == "nt" else None
    base = Path(base) if base else Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "IngeCAD" / "arquitectura" / "biblioteca_termica.json"


def guardar(bib: dict, ruta=None) -> Path:
    destino = Path(ruta) if ruta else ruta_usuario()
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(".tmp")
    temporal.write_text(json.dumps(bib, ensure_ascii=False, indent=1), encoding="utf-8")
    temporal.replace(destino)       # escritura atómica: nunca queda una biblioteca a medias
    return destino


def cargar(ruta=None) -> dict | None:
    origen = Path(ruta) if ruta else ruta_usuario()
    if not origen.is_file():
        return None
    bib = json.loads(origen.read_text(encoding="utf-8"))
    if bib.get("formato") != FORMATO:
        raise ValueError(f"{origen}: no es una biblioteca térmica del plugin")
    return bib


def catalogos_instalados() -> list[Path]:
    """Catálogos encontrados en las carpetas habituales de la instalación."""
    vistos = []
    for carpeta in CARPETAS_INSTALACION:
        raiz = Path(carpeta)
        if raiz.is_dir():
            for p in sorted(raiz.rglob("BDCatalogo.bdc")):
                if p not in vistos:
                    vistos.append(p)
    return vistos


# ------------------------------------------------------------------ consulta

def _plano(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto)
    return "".join(ch for ch in sin_tildes if not unicodedata.combining(ch)).casefold()


def buscar(bib: dict, texto: str, apartado: str = "materiales") -> list[str]:
    """Nombres que contienen todas las palabras de ``texto`` (sin tildes ni mayúsculas)."""
    palabras = _plano(texto).split()
    return [n for n in bib.get(apartado, {}) if all(p in _plano(n) for p in palabras)]


def resistencia_capa(bib: dict, material: str, espesor: float) -> float:
    m = bib["materiales"].get(material)
    if m is None:
        raise KeyError(f"El material «{material}» no está en la biblioteca")
    if m.get("tipo") == "RESISTANCE":
        if m.get("resistencia") is None:
            raise ValueError(f"El material «{material}» no tiene resistencia")
        return m["resistencia"]
    lam = m.get("conductividad")
    if not lam or lam <= 0:
        raise ValueError(f"El material «{material}» no tiene conductividad")
    return espesor / lam


def u_opaco(bib: dict, capas, posicion: str = "vertical") -> float:
    """U (W/m²K) de una lista de capas ``[(material, espesor m), …]``."""
    rsi, rse = RESISTENCIAS_SUPERFICIALES[posicion]
    r = rsi + rse + sum(resistencia_capa(bib, m, float(e)) for m, e in capas)
    return 1.0 / r


# ------------------------------------------------------------------- orden

def _elegir_fichero(ctx):
    try:
        from PySide6.QtWidgets import QFileDialog
        from .compat import dialog_parent
        inicio = next((str(p.parent) for p in catalogos_instalados()), "")
        nombre, _f = QFileDialog.getOpenFileName(
            dialog_parent(ctx), "Importar el catálogo de la Herramienta Unificada", inicio,
            "Catálogo (*.bdc *.gz *.zip);;Todos (*)")
        return Path(nombre) if nombre else None
    except (ImportError, RuntimeError, TypeError):
        return None


def _resumen(bib) -> str:
    return (f"{len(bib['materiales'])} materiales, {len(bib['composiciones'])} composiciones, "
            f"{len(bib['vidrios'])} vidrios, {len(bib['marcos'])} marcos, "
            f"{len(bib['huecos'])} huecos")


def biblioteca_he(ctx, *args):
    """BIBLIOTECAHE, biblioteca térmica del usuario (fuera del dibujo):
      BIBLIOTECAHE                          estado: fichero, origen y recuentos
      BIBLIOTECAHE importar [ruta]          importa el catálogo .bdc (sin ruta: el de la
                                            instalación o el que se elija)
      BIBLIOTECAHE buscar texto             materiales que contienen el texto
      BIBLIOTECAHE u Nombre                 U de una composición del catálogo (vertical)
      BIBLIOTECAHE u Nombre / techo|suelo   … como cubierta o como suelo sobre el exterior"""
    palabras = " ".join(str(a) for a in args).strip()
    orden, _, resto = palabras.partition(" ")
    orden, resto = orden.casefold(), resto.strip()
    try:
        if orden == "importar":
            ruta = Path(resto).expanduser() if resto else None
            if ruta is None:
                instalados = catalogos_instalados()
                ruta = instalados[0] if len(instalados) == 1 else _elegir_fichero(ctx)
            if ruta is None:
                ctx.echo("BIBLIOTECAHE: indique el fichero, p. ej. BIBLIOTECAHE importar "
                         r"C:\ProgramasCTEyCEE\CTEHE2019\BDCatalogo.bdc")
                return None
            bib = importar(ruta)
            destino = guardar(bib)
            ctx.echo(f"BIBLIOTECAHE: importado {bib['origen']['fichero']}: {_resumen(bib)}.")
            ctx.echo(f"  Guardada en {destino} (para todos los proyectos; no se copia al dibujo).")
            for aviso in bib["avisos"][:5]:
                ctx.echo("  Aviso: " + aviso)
            if len(bib["avisos"]) > 5:
                ctx.echo(f"  … y {len(bib['avisos']) - 5} avisos más.")
            return bib
        bib = cargar()
        if bib is None:
            ctx.echo("BIBLIOTECAHE: no hay biblioteca térmica. Use «BIBLIOTECAHE importar» con el "
                     "BDCatalogo.bdc de la Herramienta Unificada (el plugin no lo distribuye).")
            return None
        if orden == "buscar":
            nombres = buscar(bib, resto)
            ctx.echo(f"BIBLIOTECAHE: {len(nombres)} materiales con «{resto}».")
            for n in nombres[:30]:
                m = bib["materiales"][n]
                dato = (f"R = {m['resistencia']} m²K/W" if m.get("tipo") == "RESISTANCE"
                        else f"λ = {m['conductividad']} W/mK")
                ctx.echo(f"  {n}  ({dato})")
            return nombres
        if orden == "u":
            nombre, _, pos = resto.partition("/")
            nombre, pos = nombre.strip(), pos.strip().casefold()
            posicion = {"techo": "ascendente", "cubierta": "ascendente",
                        "suelo": "descendente"}.get(pos, "vertical")
            comp = bib["composiciones"].get(nombre)
            if comp is None:
                parecidos = buscar(bib, nombre, "composiciones")[:5]
                ctx.echo(f"BIBLIOTECAHE: no existe la composición «{nombre}»."
                         + (" Parecidas: " + "; ".join(parecidos) if parecidos else ""))
                return None
            u = u_opaco(bib, comp["capas"], posicion)
            ctx.echo(f"BIBLIOTECAHE: U = {u:.2f} W/m²K ({nombre}, {posicion}).")
            return u
        o = bib["origen"]
        ctx.echo(f"BIBLIOTECAHE: {ruta_usuario()}")
        ctx.echo(f"  Origen: {o['fichero']} (SHA-256 {o['sha256'][:12]}…): {_resumen(bib)}.")
        return bib
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        ctx.echo(f"BIBLIOTECAHE: {exc}")
        return None

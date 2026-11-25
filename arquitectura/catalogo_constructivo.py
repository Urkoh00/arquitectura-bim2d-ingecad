# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: CATALOGOEC: importa a una biblioteca del usuario las soluciones del
#   catálogo autonómico de elementos constructivos (IFC exportados desde su
#   aplicación web), las contrasta con la biblioteca térmica del Ministerio y
#   crea con ellas tipos de muro (fachadas y particiones).
#   (Guía del código: docs/GUIA_DEL_CODIGO.md)
"""Catálogo de elementos constructivos del usuario.

**Qué se lee.** La aplicación web del catálogo de elementos constructivos del
Instituto Valenciano de la Edificación (v04.00) exporta las soluciones elegidas
en IFC4: un ``IfcWallType``, ``IfcSlabType`` o ``IfcRoofType`` por solución,
con su conjunto de capas (``IfcMaterialLayerSet``), las propiedades de cada
material (``IfcMaterialProperties``) y los conjuntos ``IVE_Prestaciones``,
``IVE_Documentacion`` y ``Pset_*Common`` del tipo.

**Qué no se hace.** El plugin **no distribuye** el catálogo ni ningún dato
suyo: cada usuario importa los IFC que exportó, y la biblioteca se guarda en un
JSON de su carpeta de configuración, nunca en el repositorio ni en el dibujo,
igual que la biblioteca térmica (``biblioteca_termica.py``). No hace falta
IfcOpenShell: un lector STEP mínimo basta para estas entidades.

**Correcciones al importar** (defectos comprobados en los IFC del catálogo):

- los GlobalId se repiten entre ficheros: se ignoran; la clave es el código;
- ``OffsetFromReferenceLine`` = −140 m: se ignora (no es un dato constructivo);
- números escritos como texto con coma (``'207,00'``) y reales con la coma
  como separador dentro del valor (``IFCREAL(15,00)``): se leen como número;
- un 0 en magnitudes que no pueden ser nulas (densidad, calor específico,
  masa, conductividad, transmitancia…) significa «sin dato»: se guarda vacío;
- los comentarios ``/* … */`` del fichero se descartan.

**Rango de las fuentes.** El catálogo del Ministerio (Herramienta Unificada,
``biblioteca_termica``) tiene rango superior: **no puede haber
contradicciones**. Por eso:

- los tipos de muro creados desde el catálogo guardan solo **nombres de
  material y espesores**; las propiedades térmicas de cada capa se toman
  siempre de la biblioteca térmica del Ministerio por nombre;
- ``contrastar`` compara cada material con el del Ministerio **solo por
  nombre idéntico** (sin tildes, mayúsculas ni espacios repetidos): no se
  presuponen equivalencias que no estén escritas. Si los valores difieren,
  prevalece el del Ministerio y se avisa;
- la U declarada por el catálogo autonómico se muestra como dato informativo
  junto a la que resulta de la biblioteca del Ministerio, cuando se puede
  calcular; si difieren, prevalece la del Ministerio.

**Referencias al catálogo estatal.** Solo se anotan las que el propio fichero
declara (el código ``P5.1`` en el nombre de la solución o «CEC P5.1» en el
nombre de un material), marcadas como «declarada»; nunca se deducen.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
import re
import unicodedata
import zipfile
from pathlib import Path

FORMATO = "arquitectura-catalogo-constructivo"
VERSION = 1
FUENTE = "Catálogo de elementos constructivos (IVE)"

#: familia del código → (denominación, categoría de muro o None)
FAMILIAS = {
    "FC": ("Fachada", "fachada"),
    "PT": ("Partición", "particion"),
    "FJ": ("Forjado", None),
    "QB": ("Cubierta", None),
}
#: clase del tipo IFC → clase del elemento
TIPOS_IFC = {"IFCWALLTYPE": "IfcWall", "IFCSLABTYPE": "IfcSlab", "IFCROOFTYPE": "IfcRoof"}
#: magnitudes en las que un 0 del catálogo significa «sin dato»
SIN_CERO = {
    "MassDensity", "SpecificHeatCapacity", "ThermalConductivity", "Masa", "Espesor",
    "MasaSuperficial", "ThermalTransmitance", "IndiceGlobalReduccionAcustica",
}
#: tolerancia relativa al contrastar con la biblioteca del Ministerio
TOLERANCIA = 1e-3


# ----------------------------------------------------------------- lector STEP

class Ref(int):
    """Referencia ``#n`` a otra entidad."""


class Enum(str):
    """Valor enumerado ``.X.``."""


class Tipado:
    """Valor con tipo, p. ej. ``IFCREAL(0.5)``."""
    __slots__ = ("tipo", "valor")

    def __init__(self, tipo, valor):
        self.tipo, self.valor = tipo, valor


_NUMERO = re.compile(r"[+-]?(\d+\.?\d*([eE][+-]?\d+)?|\.\d+([eE][+-]?\d+)?)")
_ENTIDAD = re.compile(r"#(\d+)\s*=\s*([A-Za-z0-9_]+)\s*\(", re.S)


def _decodificar(texto: str) -> str:
    """Cadena STEP (ISO 10303-21) a texto: ``''``, ``\\S\\``, ``\\X\\``, ``\\X2\\``."""
    salida, i = [], 0
    while i < len(texto):
        if texto.startswith("\\S\\", i) and i + 3 < len(texto):
            salida.append(chr(ord(texto[i + 3]) + 128))
            i += 4
        elif texto.startswith("\\X2\\", i):
            fin = texto.find("\\X0\\", i + 4)
            if fin < 0:
                salida.append(texto[i:])
                break
            hexa = texto[i + 4:fin]
            salida.append("".join(chr(int(hexa[j:j + 4], 16)) for j in range(0, len(hexa), 4)))
            i = fin + 4
        elif texto.startswith("\\X\\", i) and i + 5 <= len(texto):
            salida.append(chr(int(texto[i + 3:i + 5], 16)))
            i += 5
        elif texto.startswith("\\\\", i):
            salida.append("\\")
            i += 2
        else:
            salida.append(texto[i])
            i += 1
    return "".join(salida)


def _sin_comentarios(texto: str) -> str:
    """Quita los comentarios ``/* … */`` que no están dentro de una cadena."""
    salida, i, n = [], 0, len(texto)
    while i < n:
        c = texto[i]
        if c == "'":
            fin = i + 1
            while fin < n:
                if texto[fin] == "'":
                    if fin + 1 < n and texto[fin + 1] == "'":
                        fin += 2
                        continue
                    break
                fin += 1
            salida.append(texto[i:fin + 1])
            i = fin + 1
        elif texto.startswith("/*", i):
            fin = texto.find("*/", i + 2)
            i = n if fin < 0 else fin + 2
        else:
            salida.append(c)
            i += 1
    return "".join(salida)


class _Lector:
    """Analizador de los argumentos de una entidad STEP."""

    def __init__(self, texto, avisos):
        self.t, self.i, self.avisos = texto, 0, avisos

    def _blancos(self):
        while self.i < len(self.t) and self.t[self.i] in " \t\r\n":
            self.i += 1

    def lista(self):
        """Lee ``( … )`` a partir de la posición actual (que es ``(``)."""
        assert self.t[self.i] == "("
        self.i += 1
        valores, crudos = [], []
        while True:
            self._blancos()
            if self.i >= len(self.t):
                raise ValueError("entidad STEP sin cerrar")
            if self.t[self.i] == ")":
                self.i += 1
                return valores, crudos
            inicio = self.i
            valores.append(self.valor())
            crudos.append(self.t[inicio:self.i].strip())
            self._blancos()
            if self.i < len(self.t) and self.t[self.i] == ",":
                self.i += 1

    def valor(self):
        self._blancos()
        c = self.t[self.i]
        if c == "'":
            fin, partes = self.i + 1, []
            while True:
                j = self.t.index("'", fin)
                partes.append(self.t[fin:j])
                if j + 1 < len(self.t) and self.t[j + 1] == "'":
                    partes.append("'")
                    fin = j + 2
                    continue
                self.i = j + 1
                return _decodificar("".join(partes))
        if c == "#":
            m = re.compile(r"#(\d+)").match(self.t, self.i)
            self.i = m.end()
            return Ref(int(m.group(1)))
        if c == "$":
            self.i += 1
            return None
        if c == "*":
            self.i += 1
            return "*"
        if c == ".":
            m = re.compile(r"\.([A-Za-z0-9_]+)\.").match(self.t, self.i)
            if m:
                self.i = m.end()
                v = m.group(1).upper()
                return True if v == "T" else False if v == "F" else Enum(v)
        if c == "(":
            return self.lista()[0]
        m = _NUMERO.match(self.t, self.i)
        if m:
            self.i = m.end()
            v = m.group(0)
            return float(v) if any(x in v for x in ".eE") else int(v)
        m = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(").match(self.t, self.i)
        if m:
            self.i = m.end() - 1
            valores, crudos = self.lista()
            return Tipado(m.group(1).upper(), self._reparar(m.group(1), valores, crudos))
        raise ValueError(f"valor STEP no reconocido cerca de «{self.t[self.i:self.i + 20]}»")

    def _reparar(self, tipo, valores, crudos):
        """``IFCREAL(15,00)``: la coma decimal partió el número en dos."""
        if len(valores) == 2 and all(re.fullmatch(r"[+-]?\d+", c or "") for c in crudos):
            self.avisos["coma_decimal"] = self.avisos.get("coma_decimal", 0) + 1
            return float(f"{crudos[0]}.{crudos[1].lstrip('+-')}")
        return valores[0] if len(valores) == 1 else valores


def leer_step(texto: str):
    """(entidades, cabecera, avisos) de un fichero IFC en STEP.

    ``entidades`` = {n: (TIPO, [argumentos])}; ``cabecera`` = textos de
    FILE_NAME y FILE_SCHEMA; ``avisos`` = recuento de reparaciones."""
    texto = _sin_comentarios(texto)
    avisos: dict = {}
    cabecera = {}
    m = re.search(r"FILE_NAME\s*\((.*?)\)\s*;", texto, re.S)
    if m:
        try:
            datos = _Lector("(" + m.group(1) + ")", avisos).lista()[0]
            cabecera["fichero"] = datos
        except (ValueError, IndexError):
            pass
    m = re.search(r"FILE_SCHEMA\s*\(\s*\(\s*'([^']*)'", texto)
    cabecera["esquema"] = m.group(1) if m else ""
    inicio = texto.find("DATA;")
    if inicio < 0:
        raise ValueError("no es un fichero IFC en STEP (falta DATA;)")
    cuerpo = texto[inicio + 5:]
    entidades = {}
    for m in _ENTIDAD.finditer(cuerpo):
        lector = _Lector(cuerpo, avisos)
        lector.i = m.end() - 1
        try:
            args, _crudos = lector.lista()
        except (ValueError, IndexError):
            avisos["entidades_ilegibles"] = avisos.get("entidades_ilegibles", 0) + 1
            continue
        entidades[int(m.group(1))] = (m.group(2).upper(), args)
    return entidades, cabecera, avisos


# ------------------------------------------------------------ interpretación

def _numero(valor):
    """Número de un valor IFC; acepta el texto con coma decimal («207,00»)."""
    if isinstance(valor, Tipado):
        valor = valor.valor
    if isinstance(valor, bool) or valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor) if math.isfinite(float(valor)) else None
    texto = str(valor).strip().replace(" ", "")
    if re.fullmatch(r"[+-]?\d+(,\d+)?", texto):
        return float(texto.replace(",", "."))
    if re.fullmatch(r"[+-]?\d+(\.\d+)?", texto):
        return float(texto)
    return None


def _valor_propiedad(nombre, valor):
    """Valor limpio de una propiedad: número, booleano, texto o None."""
    if isinstance(valor, Tipado):
        valor = valor.valor
    if isinstance(valor, bool):
        return valor
    n = _numero(valor)
    if n is not None:
        return None if (n == 0 and nombre in SIN_CERO) else n
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto or None


def _propiedades(ent, ids):
    out = {}
    for i in ids or ():
        tipo, a = ent.get(i, ("", []))
        if tipo == "IFCPROPERTYSINGLEVALUE" and a:
            out[str(a[0])] = _valor_propiedad(str(a[0]), a[2] if len(a) > 2 else None)
    return out


def _psets(ent, ids):
    out = {}
    for i in ids or ():
        tipo, a = ent.get(i, ("", []))
        if tipo == "IFCPROPERTYSET" and len(a) > 4:
            out[str(a[2])] = _propiedades(ent, a[4])
    return out


def _codigo(nombre: str):
    """(familia, código, denominación) de «Fachada FC07b04M32050»."""
    palabras = nombre.split()
    codigo = palabras[-1] if palabras else ""
    familia = codigo[:2].upper()
    if familia not in FAMILIAS:
        familia = ""
    return familia, codigo, " ".join(palabras[:-1])


_REF_CTE = re.compile(r"(?:^|[_\s])P(\d+(?:\.\d+)?)(?:[_\s]|$)")
_REF_CTE_MATERIAL = re.compile(r"\bCEC\s+([A-Z]{1,2}\d+(?:\.\d+)*)")


def _referencias_cte(codigo, capas):
    refs = []
    m = _REF_CTE.search(codigo)
    if m:
        refs.append({"codigo": "P" + m.group(1), "origen": "declarada en el código de la solución"})
    for c in capas:
        for r in _REF_CTE_MATERIAL.findall(c["material"]):
            if all(x["codigo"] != r for x in refs):
                refs.append({"codigo": r, "origen": f"declarada en el material «{c['material']}»"})
    return refs


def _materiales(ent):
    """{id de IfcMaterial: {nombre de pset: propiedades}}."""
    out = {}
    for tipo, a in ent.values():
        if tipo == "IFCMATERIALPROPERTIES" and len(a) > 3 and isinstance(a[3], Ref):
            out.setdefault(int(a[3]), {})[str(a[0])] = _propiedades(ent, a[2])
    return out


def _conjunto_capas(ent, ref):
    tipo, a = ent.get(ref, ("", []))
    if tipo == "IFCMATERIALLAYERSETUSAGE" and a:
        tipo, a = ent.get(a[0], ("", []))
    return a if tipo == "IFCMATERIALLAYERSET" else None


def soluciones_de(entidades, origen, avisos):
    """Soluciones (por código) de las entidades de un fichero."""
    props_material = _materiales(entidades)
    material_de = {}
    for tipo, a in entidades.values():
        if tipo == "IFCRELASSOCIATESMATERIAL" and len(a) > 5:
            for obj in a[4] or ():
                material_de[int(obj)] = a[5]
    psets_rel = {}
    for tipo, a in entidades.values():
        if tipo == "IFCRELDEFINESBYPROPERTIES" and len(a) > 5:
            for obj in a[4] or ():
                psets_rel.setdefault(int(obj), []).append(a[5])
    out = {}
    for ident, (tipo, a) in entidades.items():
        if tipo not in TIPOS_IFC or len(a) < 3 or not a[2]:
            continue
        nombre = " ".join(str(a[2]).split())
        familia, codigo, denominacion = _codigo(nombre)
        if not codigo:
            continue
        ids_psets = list(a[5] or []) + [p for p in psets_rel.get(ident, []) if p not in (a[5] or [])]
        psets = _psets(entidades, ids_psets)
        capas = []
        conjunto = _conjunto_capas(entidades, material_de.get(ident))
        for capa_id in (conjunto[0] if conjunto else []) or []:
            t, c = entidades.get(capa_id, ("", []))
            if t != "IFCMATERIALLAYER" or len(c) < 2:
                continue
            _tm, mat = entidades.get(c[0], ("", []))
            nombre_mat = " ".join(str(mat[0]).split()) if mat else ""
            espesor = _numero(c[1])
            if espesor is None or espesor <= 0:
                avisos.append(f"{codigo}: capa «{nombre_mat}» sin espesor válido")
                continue
            propiedades = {}
            for valores in props_material.get(int(c[0]), {}).values():
                propiedades.update(valores)
            declarado = propiedades.get("Espesor")
            if declarado is not None and abs(declarado / 1000.0 - espesor) > 5e-4:
                avisos.append(f"{codigo}: «{nombre_mat}» declara {declarado:g} mm y la capa mide "
                              f"{espesor * 1000:g} mm; vale la capa")
            capas.append({
                "material": nombre_mat,
                "categoria": " ".join(str(mat[2]).split()) if len(mat) > 2 and mat[2] else "",
                "espesor": espesor,
                "hoja": str(c[4]) if len(c) > 4 and c[4] else "",
                "propiedades": propiedades,
            })
        if not capas:
            avisos.append(f"{codigo}: sin capas; no se importa")
            continue
        comunes = {k: v for n, p in psets.items() if n.startswith("Pset_") for k, v in p.items()}
        out[codigo] = {
            "codigo": codigo,
            "familia": familia,
            "denominacion": denominacion or (FAMILIAS.get(familia, ("",))[0]),
            "nombre": nombre,
            "clase_ifc": TIPOS_IFC[tipo],
            "tipo_predefinido": str(a[-1]) if isinstance(a[-1], Enum) else None,
            "capas": capas,
            "espesor": sum(c["espesor"] for c in capas),
            "prestaciones": psets.get("IVE_Prestaciones", {}),
            "documentacion": psets.get("IVE_Documentacion", {}),
            "comunes": comunes,
            "referencias_cte": _referencias_cte(codigo, capas),
            "origen": origen,
        }
    return out


# ---------------------------------------------------------------- importación

def _ficheros(ruta: Path):
    """(nombre, bytes) de cada IFC de un fichero, ZIP o carpeta."""
    if ruta.is_dir():
        for p in sorted(ruta.rglob("*")):
            if p.is_file() and p.suffix.lower() in (".ifc", ".zip"):
                yield from _ficheros(p)
        return
    datos = ruta.read_bytes()
    if datos[:4] == b"PK\x03\x04":
        with zipfile.ZipFile(io.BytesIO(datos)) as z:
            for n in sorted(z.namelist()):
                if n.lower().endswith(".ifc"):
                    yield f"{ruta.name}/{n}", z.read(n)
        return
    yield ruta.name, datos


def _texto(datos: bytes) -> str:
    try:
        return datos.decode("utf-8")
    except UnicodeDecodeError:
        return datos.decode("iso-8859-1")


def vacia() -> dict:
    return {"formato": FORMATO, "version": VERSION, "fuente": FUENTE,
            "origenes": [], "soluciones": {}, "avisos": []}


def _comparable(sol):
    return {k: v for k, v in sol.items() if k != "origen"}


def importar(rutas, biblioteca=None) -> dict:
    """Añade a ``biblioteca`` (o a una vacía) las soluciones de los IFC dados.

    Una solución que ya estaba se sustituye si llega con datos distintos, y se
    avisa; si llega igual, solo se anota el nuevo origen."""
    bib = json.loads(json.dumps(biblioteca)) if biblioteca else vacia()
    if isinstance(rutas, (str, Path)):
        rutas = [rutas]
    leidos = 0
    for ruta in rutas:
        for nombre, datos in _ficheros(Path(ruta).expanduser()):
            avisos: list = []
            entidades, cabecera, recuento = leer_step(_texto(datos))
            fichero = cabecera.get("fichero") or []
            aplicacion = str(fichero[4]) if len(fichero) > 4 and fichero[4] else ""
            sha = hashlib.sha256(datos).hexdigest()
            nuevas = soluciones_de(entidades, nombre, avisos)
            if recuento.get("coma_decimal"):
                avisos.append(f"{nombre}: {recuento['coma_decimal']} valores con coma decimal "
                              "corregidos")
            if recuento.get("entidades_ilegibles"):
                avisos.append(f"{nombre}: {recuento['entidades_ilegibles']} entidades ilegibles")
            for codigo, sol in nuevas.items():
                previa = bib["soluciones"].get(codigo)
                if previa is not None and _comparable(previa) != _comparable(sol):
                    avisos.append(f"{codigo}: {nombre} trae datos distintos de {previa['origen']}; "
                                  "se conservan los nuevos")
                bib["soluciones"][codigo] = sol
            bib["origenes"] = [o for o in bib["origenes"] if o["sha256"] != sha]
            bib["origenes"].append({"fichero": nombre, "sha256": sha, "aplicacion": aplicacion,
                                    "esquema": cabecera.get("esquema", ""),
                                    "soluciones": sorted(nuevas)})
            bib["avisos"].extend(avisos)
            leidos += 1
    if not leidos:
        raise ValueError("no se ha encontrado ningún fichero IFC")
    if not bib["soluciones"]:
        raise ValueError("los ficheros no contienen soluciones del catálogo (tipos de muro, "
                         "forjado o cubierta con capas)")
    return bib


# -------------------------------------------------------------- persistencia

def ruta_usuario() -> Path:
    """JSON del catálogo: ``ARQ_CATALOGO_CONSTRUCTIVO`` o la carpeta de configuración."""
    propia = os.environ.get("ARQ_CATALOGO_CONSTRUCTIVO")
    if propia:
        return Path(propia).expanduser()
    return _carpeta_config() / "catalogo_constructivo.json"


def _carpeta_config() -> Path:
    base = os.environ.get("APPDATA") if os.name == "nt" else None
    base = Path(base) if base else Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "IngeCAD" / "arquitectura"


def guardar(bib: dict, ruta=None) -> Path:
    destino = Path(ruta) if ruta else ruta_usuario()
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(".tmp")
    temporal.write_text(json.dumps(bib, ensure_ascii=False, indent=1), encoding="utf-8")
    temporal.replace(destino)
    return destino


def cargar(ruta=None) -> dict | None:
    origen = Path(ruta) if ruta else ruta_usuario()
    if not origen.is_file():
        return None
    bib = json.loads(origen.read_text(encoding="utf-8"))
    if bib.get("formato") != FORMATO:
        raise ValueError(f"{origen}: no es un catálogo de elementos constructivos del plugin")
    return bib


# ------------------------------------------------------------------- consulta

def _plano(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", str(texto))
    return " ".join("".join(ch for ch in sin_tildes if not unicodedata.combining(ch)).casefold().split())


def buscar(bib: dict, texto: str) -> list[str]:
    """Códigos cuyo código, nombre o materiales contienen todas las palabras."""
    palabras = _plano(texto).split()
    out = []
    for codigo, sol in bib.get("soluciones", {}).items():
        todo = _plano(" ".join([codigo, sol["nombre"], *(c["material"] for c in sol["capas"])]))
        if all(p in todo for p in palabras):
            out.append(codigo)
    return sorted(out)


def solucion(bib: dict, texto: str):
    """La solución de código ``texto`` (sin distinguir mayúsculas), o None."""
    sols = bib.get("soluciones", {})
    if texto in sols:
        return sols[texto]
    hits = [s for c, s in sols.items() if c.casefold() == str(texto).casefold()]
    return hits[0] if len(hits) == 1 else None


def _difiere(a, b):
    return abs(a - b) > TOLERANCIA * max(abs(a), abs(b), 1e-12)


#: propiedad del catálogo autonómico → dato de la biblioteca del Ministerio
_CONTRASTE = (("ThermalConductivity", "conductividad", "λ"),
              ("MassDensity", "densidad", "ρ"),
              ("SpecificHeatCapacity", "calor_especifico", "c"),
              ("FactorResistenciaDifusionVaporAgua", "difusion_vapor", "μ"))


def contrastar(sol: dict, termica: dict | None) -> dict:
    """Contraste de una solución con la biblioteca térmica del Ministerio.

    Devuelve ``{"capas": [...], "u_catalogo", "u_ministerio", "avisos"}``.
    Cada capa indica el material del Ministerio con el mismo nombre (o None)
    y las diferencias encontradas; prevalece siempre el del Ministerio."""
    out = {"capas": [], "u_catalogo": sol.get("comunes", {}).get("ThermalTransmitance"),
           "u_ministerio": None, "avisos": []}
    if not termica:
        out["avisos"].append("Sin biblioteca térmica del Ministerio (BIBLIOTECAHE importar): "
                             "no se puede contrastar")
        return out
    por_nombre = {}
    for nombre in termica.get("materiales", {}):
        por_nombre.setdefault(_plano(nombre), []).append(nombre)
    completas = True
    for capa in sol["capas"]:
        candidatos = por_nombre.get(_plano(capa["material"]), [])
        fila = {"material": capa["material"], "espesor": capa["espesor"],
                "ministerio": candidatos[0] if len(candidatos) == 1 else None,
                "diferencias": []}
        if len(candidatos) > 1:
            out["avisos"].append(f"«{capa['material']}»: varios materiales del Ministerio con ese "
                                 "nombre; no se elige ninguno")
        if fila["ministerio"] is None:
            completas = False
        else:
            m = termica["materiales"][fila["ministerio"]]
            for clave_ive, clave_he, simbolo in _CONTRASTE:
                a, b = capa["propiedades"].get(clave_ive), m.get(clave_he)
                if isinstance(a, (int, float)) and isinstance(b, (int, float)) and _difiere(a, b):
                    fila["diferencias"].append(f"{simbolo} {a:g} (catálogo) ≠ {b:g} (Ministerio)")
            if fila["diferencias"]:
                out["avisos"].append(f"«{capa['material']}»: " + "; ".join(fila["diferencias"])
                                     + "; prevalece el Ministerio")
        out["capas"].append(fila)
    if completas and sol.get("familia") in ("FC", "PT"):
        from .biblioteca_termica import u_opaco
        try:
            out["u_ministerio"] = u_opaco(termica, [(f["ministerio"], f["espesor"])
                                                    for f in out["capas"]])
        except (KeyError, ValueError) as exc:
            out["avisos"].append(f"U con el Ministerio no calculable: {exc}")
    uc, um = out["u_catalogo"], out["u_ministerio"]
    if isinstance(uc, (int, float)) and isinstance(um, (int, float)) and abs(uc - um) > 0.005:
        out["avisos"].append(f"U = {um:.2f} W/m²K con el Ministerio y {uc:.2f} declarada por el "
                             "catálogo; prevalece la del Ministerio")
    return out


def tipo_de_muro(sol: dict, nombre: str | None = None) -> dict:
    """Tipo de muro del plugin (``parameters_arq``) desde una solución FC o PT.

    Solo lleva nombres de material y espesores: las propiedades térmicas se
    toman siempre de la biblioteca del Ministerio. Las capas van en el orden
    del catálogo (de la cara exterior a la interior en las fachadas); MURO
    puede invertirlas al dibujar."""
    familia = sol.get("familia")
    categoria = FAMILIAS.get(familia, (None, None))[1]
    if categoria is None:
        raise ValueError(f"{sol['codigo']}: solo las fachadas (FC) y particiones (PT) son tipos "
                         "de muro")
    from .parameters_arq import normalise_type
    return normalise_type({
        "name": nombre or sol["codigo"],
        "layers": [[c["espesor"], c["material"]] for c in sol["capas"]],
        "wall_category": categoria,
        "catalogo": {"codigo": sol["codigo"], "fuente": FUENTE},
        "orden_capas": "cara-dibujada" if categoria == "particion" else "exterior-interior",
    })


# ------------------------------------------------------------------- orden

def _resumen(bib) -> str:
    cuenta = {}
    for s in bib["soluciones"].values():
        cuenta[s["familia"] or "otras"] = cuenta.get(s["familia"] or "otras", 0) + 1
    return ", ".join(f"{v} {k}" for k, v in sorted(cuenta.items())) or "ninguna solución"


def _num(v, d=2):
    return "—" if not isinstance(v, (int, float)) else f"{v:.{d}f}".replace(".", ",")


def _cargar_termica():
    try:
        from .biblioteca_termica import cargar as cargar_termica
        return cargar_termica()
    except (OSError, ValueError):
        return None


def _elegir_ficheros(ctx):
    try:
        from PySide6.QtWidgets import QApplication, QFileDialog
        if QApplication.instance() is None:
            return None
        from .compat import dialog_parent
        nombres, _f = QFileDialog.getOpenFileNames(
            dialog_parent(ctx), "Importar soluciones del catálogo de elementos constructivos", "",
            "IFC del catálogo (*.ifc *.zip);;Todos (*)")
        return [Path(n) for n in nombres] or None
    except (ImportError, RuntimeError, TypeError):
        return None


def catalogo_ec(ctx, *args):
    """CATALOGOEC, catálogo de elementos constructivos del usuario (fuera del dibujo):
      CATALOGOEC                        estado: fichero, orígenes y recuentos
      CATALOGOEC importar ruta [ruta…]  añade los IFC exportados (ficheros, ZIP o carpeta)
      CATALOGOEC buscar texto           soluciones por código, nombre o material
      CATALOGOEC ver CÓDIGO             capas, prestaciones y contraste con el Ministerio
      CATALOGOEC tipo CÓDIGO [nombre]   crea o actualiza un tipo de muro (FC o PT)
      CATALOGOEC vaciar                 borra el catálogo del usuario"""
    palabras = " ".join(str(a) for a in args).strip()
    orden, _, resto = palabras.partition(" ")
    orden, resto = orden.casefold(), resto.strip()
    try:
        if orden == "importar":
            rutas = [Path(p) for p in _partes(resto)] if resto else _elegir_ficheros(ctx)
            if not rutas:
                ctx.echo("CATALOGOEC: indique los IFC exportados del catálogo, p. ej. "
                         "CATALOGOEC importar Fachadas.ifc Particiones.ifc")
                return None
            bib = importar(rutas, cargar())
            destino = guardar(bib)
            ctx.echo(f"CATALOGOEC: {_resumen(bib)} en {destino} (para todos los proyectos; "
                     "no se copia al dibujo).")
            for aviso in bib["avisos"][-5:]:
                ctx.echo("  Aviso: " + aviso)
            return bib
        if orden == "vaciar":
            ruta = ruta_usuario()
            if ruta.is_file():
                ruta.unlink()
            ctx.echo("CATALOGOEC: catálogo del usuario borrado.")
            return None
        bib = cargar()
        if bib is None:
            ctx.echo("CATALOGOEC: no hay catálogo. Exporte las soluciones en IFC desde la "
                     "aplicación del catálogo y use «CATALOGOEC importar» (el plugin no lo "
                     "distribuye).")
            return None
        if orden == "buscar":
            codigos = buscar(bib, resto)
            ctx.echo(f"CATALOGOEC: {len(codigos)} soluciones con «{resto}».")
            for c in codigos[:30]:
                s = bib["soluciones"][c]
                ctx.echo(f"  {c}  {s['denominacion']}, {_num(s['espesor'], 3)} m")
            return codigos
        if orden in ("ver", "tipo"):
            codigo, _, nombre = resto.partition(" ")
            sol = solucion(bib, codigo)
            if sol is None:
                parecidas = buscar(bib, codigo)[:5]
                ctx.echo(f"CATALOGOEC: no existe la solución «{codigo}»."
                         + (" Parecidas: " + ", ".join(parecidas) if parecidas else ""))
                return None
            if orden == "ver":
                return _ver(ctx, sol)
            return _crear_tipo(ctx, sol, nombre.strip() or None)
        ctx.echo(f"CATALOGOEC: {ruta_usuario()}")
        ctx.echo(f"  {_resumen(bib)}; orígenes: "
                 + "; ".join(o["fichero"] for o in bib["origenes"]))
        return bib
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        ctx.echo(f"CATALOGOEC: {exc}")
        return None


def _partes(texto):
    import shlex
    try:
        return shlex.split(texto, posix=os.name != "nt")
    except ValueError:
        return texto.split()


def _ver(ctx, sol):
    ctx.echo(f"CATALOGOEC: {sol['nombre']} ({sol['clase_ifc']}), {_num(sol['espesor'], 3)} m")
    for c in sol["capas"]:
        ctx.echo(f"  {_num(c['espesor'], 3)} m  {c['material']}"
                 + (f"  [{c['hoja']}]" if c["hoja"] else ""))
    p, k = sol["prestaciones"], sol["comunes"]
    datos = [("U declarada", _num(k.get("ThermalTransmitance")) + " W/m²K"),
             ("Masa", _num(p.get("MasaSuperficial"), 0) + " kg/m²"),
             ("RA", _num(p.get("IndiceGlobalReduccionAcustica"), 1) + " dBA"),
             ("Fuego", k.get("FireRating") or "—")]
    ctx.echo("  Catálogo (informativo): " + " · ".join(f"{a} {b}" for a, b in datos))
    for r in sol["referencias_cte"]:
        ctx.echo(f"  Catálogo estatal: {r['codigo']} ({r['origen']})")
    contraste = contrastar(sol, _cargar_termica())
    sin = [f["material"] for f in contraste["capas"] if f["ministerio"] is None]
    if contraste["u_ministerio"] is not None:
        ctx.echo(f"  U con la biblioteca del Ministerio: {_num(contraste['u_ministerio'])} W/m²K "
                 "(prevalece)")
    if sin and contraste["capas"]:
        ctx.echo("  Sin material del mismo nombre en la biblioteca del Ministerio: " + "; ".join(sin))
    for aviso in contraste["avisos"]:
        ctx.echo("  Aviso: " + aviso)
    return {"solucion": sol, "contraste": contraste}


def _crear_tipo(ctx, sol, nombre):
    from .parameters_arq import SetArchitecturalDefaults, load_defaults, sort_types, layers_text
    tipo = tipo_de_muro(sol, nombre)
    actual = load_defaults(ctx.document)
    tipos = [t for t in actual["wall_types"] if t["name"].casefold() != tipo["name"].casefold()]
    actual["wall_types"] = sort_types(tipos + [tipo])
    ctx.execute(SetArchitecturalDefaults(actual))
    ctx.echo(f"CATALOGOEC: tipo «{tipo['name']}» ({tipo['wall_category']}): {layers_text(tipo)}. "
             "Las propiedades térmicas se toman de la biblioteca del Ministerio.")
    contraste = contrastar(sol, _cargar_termica())
    for aviso in contraste["avisos"]:
        ctx.echo("  Aviso: " + aviso)
    return tipo

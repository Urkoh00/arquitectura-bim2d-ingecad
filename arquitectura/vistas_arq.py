# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: SECCIONARQ y ALZADOARQ: dibujan en el dibujo una sección o un alzado
#   derivados del modelo BIM (los mismos sólidos que van a IngeTrazo), con su
#   marca en planta; «Actualizar» los regenera en un solo Deshacer.
#   (Guía del código: docs/GUIA_DEL_CODIGO.md)
"""Secciones y alzados derivados.

La geometría la calcula ``geom/vistas.py`` a partir de ``exchange.build``.
Aquí solo se dibuja y se guarda:

- un **ancla** (un punto invisible) con los datos de la vista: tipo, nombre,
  línea, lado, profundidad e inserción. Si el usuario mueve el ancla junto con
  la vista, «Actualizar» respeta la nueva posición;
- los **detalles**: relleno y contorno de lo cortado, líneas vistas, niveles,
  título y la marca de la sección en planta. Cada uno lleva el identificador
  de su vista y todos forman un grupo, para moverlos juntos.

Regenerar sustituye todos los detalles de la vista en un solo Deshacer. La
vista no es asociativa: lo que el usuario dibuje encima no se conserva al
actualizar (las cotas de nivel se generan con la vista).

Aspecto (PARAMETROSARQ > General, v1.48.3): lo cortado se rellena con un gris
de la gama (por defecto, claro) o se raya en diagonal o cruzado; tres grosores
distinguen lo cortado (0,50 mm), la línea de tierra (0,70 mm) y lo visto
(0,18 mm). Cada vista aplica esas opciones a sus capas al generarse, y el
Deshacer devuelve las capas como estaban.

Capas: ``ARQ-VISTA-CORTE``, ``ARQ-VISTA-RELLENO``, ``ARQ-VISTA-VISTO``,
``ARQ-VISTA-TIERRA`` (la cota ±0,00), ``ARQ-VISTA-NIVELES`` (0,13 mm),
``ARQ-VISTA-TEXTOS`` y ``ARQ-VISTA-MARCAS`` (la línea de corte en planta).
"""
from __future__ import annotations

import math
import uuid
from copy import deepcopy

from core.commands import Command

from .architectural import _xdata, metadata, reenlazar

KIND = "arq_view"
DETALLE = "arq_view_detail"
VERSION = 1
CAPAS = {
    "ARQ-VISTA-CORTE": (7, 50),
    "ARQ-VISTA-RELLENO": (9, 13),
    "ARQ-VISTA-VISTO": (7, 18),
    "ARQ-VISTA-TIERRA": (7, 70),
    "ARQ-VISTA-NIVELES": (3, 13),
    "ARQ-VISTA-TEXTOS": (7, 18),
    "ARQ-VISTA-MARCAS": (1, 50),
}
#: relleno de lo cortado (opción general «vista_relleno»)
RELLENOS = {"color": "Color completo", "diagonal": "Rayado diagonal",
            "cruzado": "Rayado cruzado"}
PATRONES = {"diagonal": "ANSI31", "cruzado": "ANSI37"}
#: gama de grises del relleno: (nombre, color ACI)
GAMA = (("Gris muy claro", 254), ("Gris claro", 9), ("Gris medio", 8),
        ("Gris oscuro", 251), ("Casi negro", 250))
#: grosores normalizados de línea, en mm
GROSORES = (0.13, 0.18, 0.25, 0.35, 0.50, 0.70, 1.00)
#: separación de los trazos del rayado en el papel, en mm
RAYADO_MM = 2.0
#: altura de los textos de la vista, en metros de dibujo (≈ 2,5 mm a 1:50)
TEXTO = 0.125
TIPOS = {"seccion": "SECCIÓN", "alzado": "ALZADO"}


def centesimas(mm):
    """Grosor DXF (centésimas de mm) de un grosor en mm de la tabla."""
    return int(next(x for x in GROSORES if abs(x - mm) < 1e-9) * 100 + 0.5)


def vistas(dibujo):
    """[(ancla, datos)] de las vistas del dibujo."""
    return [(e, m) for e in dibujo.modelspace()
            if (m := metadata(e) or {}).get("kind") == KIND]


def nombre_libre(dibujo, tipo):
    usados = {m.get("nombre") for _e, m in vistas(dibujo)}
    if tipo == "seccion":
        for letra in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            if letra not in usados:
                return letra
    n = 1
    while f"{n}" in usados:
        n += 1
    return f"{n}"


def _num(v):
    texto = f"{v:+.2f}".replace(".", ",")
    return texto if v else "±0,00"


def _insercion(ancla, datos):
    try:
        punto = ancla.dxf.location
        return (float(punto.x), float(punto.y))
    except AttributeError:
        return tuple(map(float, datos["insert"][:2]))


class VistaArq(Command):
    """Crea o regenera una vista (sección o alzado) como una transacción."""
    name = "ARQ VISTA"
    needs_regen = True

    def __init__(self, datos, ancla=None):
        self.datos = deepcopy(datos)
        self.ancla = ancla
        self.datos.setdefault("id", uuid.uuid4().hex)
        self.grupo = "ARQVISTA_" + self.datos["id"]
        self.nuevos = None
        self.aplicado = False
        self.resumen = {}

    # ------------------------------------------------------------ dibujo
    def _capas(self, dibujo, opciones):
        """Crea las capas que faltan y les aplica las opciones generales;
        guarda cómo estaban las existentes para el Deshacer."""
        deseado = dict(CAPAS)
        deseado["ARQ-VISTA-CORTE"] = (7, centesimas(opciones["grosor_corte"]))
        deseado["ARQ-VISTA-TIERRA"] = (7, centesimas(opciones["grosor_tierra"]))
        deseado["ARQ-VISTA-VISTO"] = (7, centesimas(opciones["grosor_visto"]))
        deseado["ARQ-VISTA-RELLENO"] = (int(opciones["vista_color"]), 13)
        for nombre, (color, grosor) in deseado.items():
            if nombre not in dibujo.layers:
                capa = dibujo.layers.new(nombre, dxfattribs={"color": color})
                capa.dxf.lineweight = grosor
                self.capas_creadas.append(nombre)
                continue
            capa = dibujo.layers.get(nombre)
            antes = (capa.dxf.color, capa.dxf.get("lineweight", -3))
            if nombre in ("ARQ-VISTA-CORTE", "ARQ-VISTA-TIERRA", "ARQ-VISTA-VISTO",
                          "ARQ-VISTA-RELLENO") and antes != (color, grosor):
                self.capas_cambiadas.setdefault(nombre, antes)
                capa.dxf.color = color
                capa.dxf.lineweight = grosor

    def _detalle(self, espacio, entidad, papel):
        _xdata(espacio, entidad, {"kind": DETALLE, "schema": 1,
                                  "view_id": self.datos["id"], "role": papel})
        return entidad

    def _dibujar(self, documento):
        from .exchange import build
        from .geom import vistas as G
        from .levels import load as niveles

        dibujo = documento.doc
        espacio = dibujo.modelspace()
        d = self.datos
        opciones = self.opciones
        modelo = build(dibujo)
        cam = G.Camara(d["p"], d["q"], d["lado"], seccion=d["tipo"] == "seccion",
                       profundidad=d.get("profundidad"))
        resultado = G.vista(modelo["elements"], cam)
        x0, y0 = d["insert"]

        def xy(s, z):
            return (x0 + s, y0 + z)

        for corte in resultado["cortes"]:
            relleno = espacio.add_hatch(color=256, dxfattribs={"layer": "ARQ-VISTA-RELLENO"})
            if opciones["vista_relleno"] == "color":
                relleno.set_solid_fill(color=256)
            else:
                # ANSI31/37 separan sus trazos 3,175 unidades: se escalan
                # para que en el papel queden a RAYADO_MM a la escala elegida
                escala = RAYADO_MM / 1000.0 * opciones["escala"] / 3.175
                relleno.set_pattern_fill(PATRONES[opciones["vista_relleno"]],
                                         color=256, scale=escala)
            for anillo in corte["anillos"]:
                relleno.paths.add_polyline_path([xy(*v) for v in anillo], is_closed=True)
            self._detalle(espacio, relleno, "relleno")
            for anillo in corte["anillos"]:
                self._detalle(espacio, espacio.add_lwpolyline(
                    [xy(*v) for v in anillo], close=True,
                    dxfattribs={"layer": "ARQ-VISTA-CORTE"}), "corte")
        for a, b, _ident in resultado["vistos"]:
            self._detalle(espacio, espacio.add_line(
                xy(*a), xy(*b), dxfattribs={"layer": "ARQ-VISTA-VISTO"}), "visto")
        zmin, zmax = resultado["cotas"]
        catalogo = niveles(dibujo)
        n_niveles = 0
        # línea de tierra: la cota ±0,00, más ancha que la vista
        self._detalle(espacio, espacio.add_line(
            xy(-1.0, 0.0), xy(cam.largo + 1.0, 0.0),
            dxfattribs={"layer": "ARQ-VISTA-TIERRA"}), "tierra")
        for nivel in catalogo.get("levels", []):
            z = float(nivel.get("elevation", 0.0))
            if resultado["vistos"] or resultado["cortes"]:
                if not (zmin - 1e-6 <= z <= zmax + 1e-6):
                    continue
            if abs(z) > 1e-9:
                self._detalle(espacio, espacio.add_line(
                    xy(-0.5, z), xy(cam.largo + 0.5, z),
                    dxfattribs={"layer": "ARQ-VISTA-NIVELES"}), "nivel")
            self._detalle(espacio, espacio.add_text(
                f"{_num(z)} {nivel.get('name', '')}".strip(),
                dxfattribs={"layer": "ARQ-VISTA-TEXTOS", "height": TEXTO,
                            "insert": xy(cam.largo + 0.6, z + 0.03)}), "nivel")
            n_niveles += 1
        titulo = f"{TIPOS[d['tipo']]} {d['nombre']}"
        if d["tipo"] == "seccion":
            titulo = f"{TIPOS['seccion']} {d['nombre']}-{d['nombre']}'"
        self._detalle(espacio, espacio.add_text(
            titulo, dxfattribs={"layer": "ARQ-VISTA-TEXTOS", "height": 2 * TEXTO,
                                "insert": xy(0.0, min(zmin, 0.0) - 6 * TEXTO)}), "titulo")
        if d["tipo"] == "seccion":
            self._marca(espacio, cam)
        self.resumen = {"cortados": len(resultado["cortes"]),
                        "lineas": len(resultado["vistos"]), "niveles": n_niveles}

    def _marca(self, espacio, cam):
        """Línea de corte en planta: tramos gruesos en los extremos, flechas
        hacia donde se mira y la letra de la sección."""
        p, u, d = cam.p, cam.u, cam.d
        largo = min(0.6, cam.largo / 3)
        flecha = 0.35
        for extremo, signo in ((p, 1), ((p[0] + u[0] * cam.largo, p[1] + u[1] * cam.largo), -1)):
            interior = (extremo[0] + u[0] * largo * signo, extremo[1] + u[1] * largo * signo)
            self._detalle(espacio, espacio.add_line(
                extremo, interior, dxfattribs={"layer": "ARQ-VISTA-MARCAS"}), "marca")
            punta = (extremo[0] + d[0] * flecha, extremo[1] + d[1] * flecha)
            self._detalle(espacio, espacio.add_line(
                extremo, punta, dxfattribs={"layer": "ARQ-VISTA-MARCAS"}), "marca")
            for lado in (1, -1):
                ala = (punta[0] - d[0] * 0.1 + u[0] * 0.06 * lado,
                       punta[1] - d[1] * 0.1 + u[1] * 0.06 * lado)
                self._detalle(espacio, espacio.add_line(
                    punta, ala, dxfattribs={"layer": "ARQ-VISTA-MARCAS"}), "marca")
            letra = (extremo[0] + d[0] * (flecha + 0.1) - u[0] * 0.25 * signo,
                     extremo[1] + d[1] * (flecha + 0.1) - u[1] * 0.25 * signo)
            nombre = self.datos["nombre"] + ("" if signo == 1 else "'")
            self._detalle(espacio, espacio.add_text(
                nombre, dxfattribs={"layer": "ARQ-VISTA-MARCAS", "height": 2 * TEXTO,
                                    "insert": letra}), "marca")

    def _grupo(self, dibujo, entidades):
        if self.grupo not in dibujo.groups:
            dibujo.groups.new(self.grupo)
        dibujo.groups.get(self.grupo).set_data(entidades)

    # --------------------------------------------------------- transacción
    def do(self, documento):
        dibujo = documento.doc
        espacio = dibujo.modelspace()
        self.capas_creadas = []
        self.capas_cambiadas = {}
        inicial = self.nuevos is None
        if inicial:
            from .parameters_arq import general_options
            self.opciones = general_options(documento)
        if inicial:
            self.anteriores = [e for e in espacio
                               if (metadata(e) or {}).get("view_id") == self.datos["id"]]
            self.datos_anteriores = deepcopy(metadata(self.ancla)) if self.ancla is not None else None
            self.grupo_anterior = self.grupo in dibujo.groups
            self.nuevos = []
        originales = {e.dxf.handle for e in espacio}
        try:
            self._capas(dibujo, self.opciones)
            if self.grupo in dibujo.groups:
                dibujo.groups.get(self.grupo).clear()
            for e in self.anteriores:
                if e.is_alive and e.dxf.owner is not None:
                    espacio.unlink_entity(e)
            if inicial:
                self._dibujar(documento)
                self.nuevos = [e for e in espacio if e.dxf.handle not in originales]
                self.datos_nuevos = {"kind": KIND, "schema": 1, "version": VERSION,
                                     **{k: self.datos[k] for k in (
                                         "id", "tipo", "nombre", "p", "q", "lado",
                                         "profundidad", "insert")},
                                     "resumen": self.resumen}
                if self.ancla is None:
                    self.ancla = espacio.add_point(
                        (*self.datos["insert"], 0.0),
                        dxfattribs={"layer": "ARQ-VISTA-TEXTOS", "invisible": 1})
            else:
                for e in self.nuevos:
                    reenlazar(espacio, e)
                if self.datos_anteriores is None:
                    reenlazar(espacio, self.ancla)
            _xdata(espacio, self.ancla, self.datos_nuevos)
            self._grupo(dibujo, [self.ancla, *self.nuevos])
            self.aplicado = True
            documento.dirty = True
        except Exception:
            self.nuevos = [e for e in espacio
                           if e.dxf.handle not in originales and e is not self.ancla]
            self.aplicado = True
            self.undo(documento)
            self.nuevos = None
            raise

    def undo(self, documento):
        if not self.aplicado:
            return
        dibujo = documento.doc
        espacio = dibujo.modelspace()
        if self.grupo in dibujo.groups:
            dibujo.groups.get(self.grupo).clear()
            if not self.grupo_anterior:
                dibujo.groups.delete(self.grupo)
        for e in self.nuevos or []:
            if e.is_alive and e.dxf.owner is not None:
                espacio.unlink_entity(e)
        if self.datos_anteriores is None:
            if self.ancla is not None and self.ancla.dxf.owner is not None:
                espacio.unlink_entity(self.ancla)
        else:
            _xdata(espacio, self.ancla, self.datos_anteriores)
        for e in self.anteriores:
            reenlazar(espacio, e)
        if self.grupo_anterior:
            self._grupo(dibujo, [self.ancla, *self.anteriores])
        for nombre in reversed(self.capas_creadas):
            if nombre in dibujo.layers:
                dibujo.layers.remove(nombre)
        for nombre, (color, grosor) in self.capas_cambiadas.items():
            if nombre in dibujo.layers:
                capa = dibujo.layers.get(nombre)
                capa.dxf.color = color
                capa.dxf.lineweight = grosor
        self.aplicado = False
        documento.dirty = True


def generar(ctx, datos):
    """Crea una vista nueva. ``datos``: tipo, nombre, p, q, lado,
    profundidad (o None) e insert."""
    from .compat import require_document
    from .transactions import SafeArchitecturalCommand
    require_document(ctx)
    vista = VistaArq(datos)
    ctx.execute(SafeArchitecturalCommand("ARQ " + TIPOS[datos["tipo"]].capitalize(), [vista]))
    return vista


def actualizar(ctx):
    """Regenera todas las vistas del dibujo en un solo Deshacer."""
    from .compat import require_document
    from .transactions import SafeArchitecturalCommand
    documento = require_document(ctx)
    existentes = vistas(documento.doc)
    if not existentes:
        ctx.echo("No hay secciones ni alzados que actualizar")
        return []
    cambios = []
    for ancla, datos in existentes:
        nuevos = dict(datos, insert=list(_insercion(ancla, datos)))
        cambios.append(VistaArq(nuevos, ancla))
    ctx.execute(SafeArchitecturalCommand("ARQ Actualizar vistas", cambios))
    return cambios


# ------------------------------------------------------------------- órdenes

def _texto_numero(texto):
    try:
        v = float(str(texto).strip().replace(",", "."))
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def crear_herramientas(Tool):
    """Las herramientas se crean con la clase Tool del núcleo (inyectada para
    poder probar el módulo sin ventana)."""

    class VistaTool(Tool):
        name = "SECCIONARQ"
        tipo = "seccion"

        def start(self):
            self.name = type(self).name
            from .compat import require_document
            self.dibujo = require_document(self.ctx).doc
            self.puntos = []
            self.profundidad = None
            self.nombre = nombre_libre(self.dibujo, self.tipo)
            self.esperando = None
            self._pedir()

        def _pedir(self):
            n = len(self.puntos)
            linea = "la línea de corte" if self.tipo == "seccion" else "la línea del alzado"
            if n == 0:
                self.prompt(f"{self.name} {self.nombre}: primer punto de {linea} "
                            "[Nombre/Profundidad/Actualizar]:")
            elif n == 1:
                self.prompt(f"{self.name}: segundo punto de {linea}:")
            elif n == 2:
                self.prompt(f"{self.name}: punto del lado hacia el que se mira:")
            else:
                self.prompt(f"{self.name}: punto de inserción de la vista:")

        def on_option(self, texto):
            palabra = str(texto).strip()
            clave = palabra.casefold()
            if self.esperando == "nombre":
                self.esperando = None
                if palabra:
                    self.nombre = palabra
                self._pedir()
                return True
            if self.esperando == "profundidad":
                self.esperando = None
                v = _texto_numero(palabra)
                if clave in ("", "todo", "toda"):
                    self.profundidad = None
                elif v is None or v <= 0:
                    self.ctx.echo("La profundidad debe ser un número positivo o «Todo»")
                    self.esperando = "profundidad"
                    return True
                else:
                    self.profundidad = v
                self._pedir()
                return True
            if clave in ("n", "nombre"):
                self.esperando = "nombre"
                self.prompt(f"{self.name}: nombre de la vista <{self.nombre}>:")
                return True
            if clave in ("p", "profundidad"):
                self.esperando = "profundidad"
                actual = "Todo" if self.profundidad is None else f"{self.profundidad:g}"
                self.prompt(f"{self.name}: profundidad visible detrás de la línea, en m, "
                            f"o Todo <{actual}>:")
                return True
            if clave in ("a", "actualizar"):
                try:
                    cambios = actualizar(self.ctx)
                    if cambios:
                        self.ctx.echo(f"{len(cambios)} vistas actualizadas desde el modelo.")
                except (ValueError, RuntimeError) as error:
                    self.ctx.echo(f"{self.name}: {error}")
                self.ctx.finish()
                return True
            return False

        def on_point(self, punto):
            if self.esperando:
                self.ctx.echo("Responda antes a la pregunta")
                return
            self.puntos.append(tuple(map(float, punto[:2])))
            if len(self.puntos) == 2 and math.dist(*self.puntos) < 1e-6:
                self.puntos.pop()
                self.ctx.echo("El segundo punto coincide con el primero")
            if len(self.puntos) < 4:
                self._pedir()
                return
            p, q, lado, insercion = self.puntos
            datos = {"tipo": self.tipo, "nombre": self.nombre, "p": list(p), "q": list(q),
                     "lado": list(lado), "profundidad": self.profundidad,
                     "insert": list(insercion)}
            try:
                vista = generar(self.ctx, datos)
            except (ValueError, RuntimeError) as error:
                self.ctx.echo(f"{self.name}: {error}")
                # el lado (3.er punto) suele ser la causa: se piden de nuevo
                # el lado y la inserción (revisión del 24-11)
                del self.puntos[2:]
                self._pedir()
                return
            r = vista.resumen
            self.ctx.echo(f"{self.name}: {r.get('cortados', 0)} elementos cortados, "
                          f"{r.get('lineas', 0)} líneas vistas. «Actualizar» la regenera "
                          "desde el modelo.")
            self.ctx.finish()

        def on_enter(self):
            self.ctx.finish()

    class AlzadoTool(VistaTool):
        name = "ALZADOARQ"
        tipo = "alzado"

    return VistaTool, AlzadoTool

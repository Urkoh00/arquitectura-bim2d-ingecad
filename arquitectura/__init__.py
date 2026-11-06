# -*- coding: utf-8 -*-
"""
Arquitectura — plugin de dibujo arquitectónico para IngeCAD
Origen: versión 0.9 (ampliada desde la 1.0 con identidad BIM)

Comandos:
  CAPASARQ / CAPASAUTO  — crear capas y distribuir elementos
  MURO                  — muro de doble línea (flujo continuo + puerta)
  PILAR                 — pilares rectangulares o circulares
  PUERTA / VENTANA / ARMARIO — carpinterías
  SUPERFICIE            — cálculo y etiquetado de áreas
  CAMARA                — cámara / eje de muro
  ESCALERA              — escalera en alzado
  ELEMENTOS             — activar / desactivar tipos
  BLOQUE                — insertar bloque de mobiliario
  MEMORIACARP           — memoria de carpintería
  SELATRIB              — selección por atributos (árbol de elementos)
  TRAMA                 — tramas / hatch
  HIPERVINCULO / URL    — hipervínculo a fichero externo
  CURVAS3D              — elevar curvas de nivel a 3D
  VERTPOLY / VERTICES   — vértices de polilínea + coordenadas (parcelas)
  LISTATEXTOS           — listado de textos / áreas listo para portapapeles
  AYUDAARQ              — lista de comandos

Licencia: GPL-3.0-or-later
"""

from __future__ import annotations

import math
import os
from collections import defaultdict
from pathlib import Path

from core.plugins import SEPARATOR, MenuItem, PluginSpec, Submenu, ToolbarItem
from tools.base import Tool
from .compat import require_document, document_of


# ---------------------------------------------------------------------------
# Capas estándar
# ---------------------------------------------------------------------------

LAYERS = {
    "ARQ-MUROS":         {"color": 8,  "linetype": "Continuous"},
    "ARQ-TABIQUES":      {"color": 8,  "linetype": "Continuous"},
    "ARQ-PILAres":       {"color": 4,  "linetype": "Continuous"},
    "ARQ-PUERTAS":       {"color": 3,  "linetype": "Continuous"},
    "ARQ-VENTANAS":      {"color": 5,  "linetype": "Continuous"},
    "ARQ-ARMARIOS":      {"color": 6,  "linetype": "Continuous"},
    "ARQ-ESCALERAS":     {"color": 1,  "linetype": "Continuous"},
    "ARQ-CAMARAS":       {"color": 2,  "linetype": "DASHED"},
    "ARQ-AREAS":         {"color": 1,  "linetype": "Continuous"},
    "ARQ-COTAS":         {"color": 2,  "linetype": "Continuous"},
    "ARQ-TEXTOS":        {"color": 7,  "linetype": "Continuous"},
    "ARQ-MOBILIARIO":    {"color": 6,  "linetype": "Continuous"},
    "ARQ-TRAMAS":        {"color": 8,  "linetype": "Continuous"},
    "ARQ-MEMORIA":       {"color": 7,  "linetype": "Continuous"},
    "ARQ-HIPERVINCULOS": {"color": 6,  "linetype": "Continuous"},
    "ARQ-CURVAS3D":      {"color": 2,  "linetype": "Continuous"},
    "ARQ-COORD":         {"color": 3,  "linetype": "Continuous"},  # vértices / coordenadas
}

LAYER_ALIASES = {
    "ARQ-PILARES": "ARQ-PILAres",
}


def _layer_name(name: str) -> str:
    return LAYER_ALIASES.get(name.upper(), name)


def _ensure_layers(ctx):
    """Crear capas mediante comandos deshacibles del núcleo vigente."""
    from core.layers import NewLayerCommand
    doc = require_document(ctx)
    for name, props in LAYERS.items():
        if name not in doc.doc.layers:
            ctx.execute(NewLayerCommand(name, color=props["color"]))


def _set_layer(ctx, name: str):
    """Asegurar la capa sin modificar la capa de trabajo del usuario."""
    name = _layer_name(name)
    _ensure_layers(ctx)
    return name


def _execute_entity(ctx, command, layer):
    # AddEntityCommand del núcleo permite una capa de destino explícita.
    if layer:
        command.layer = _set_layer(ctx, layer)
    ctx.execute(command)


# ---------------------------------------------------------------------------
# Helpers geométricos
# ---------------------------------------------------------------------------

def _dist(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _mid(a, b):
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


def _unit(a, b):
    d = _dist(a, b)
    if d < 1e-12:
        return (1.0, 0.0)
    return ((b[0] - a[0]) / d, (b[1] - a[1]) / d)


def _perp(u):
    return (-u[1], u[0])


def _offset_point(p, u, dist):
    return (p[0] + u[0] * dist, p[1] + u[1] * dist)


def _angle(a, b):
    return math.atan2(b[1] - a[1], b[0] - a[0])


def _rotate(p, origin, ang):
    cos_a, sin_a = math.cos(ang), math.sin(ang)
    dx, dy = p[0] - origin[0], p[1] - origin[1]
    return (origin[0] + dx * cos_a - dy * sin_a,
            origin[1] + dx * sin_a + dy * cos_a)


def _poly_area(pts):
    n = len(pts)
    if n < 3:
        return 0.0
    a = 0.0
    for i in range(n):
        j = (i + 1) % n
        a += pts[i][0] * pts[j][1]
        a -= pts[j][0] * pts[i][1]
    return abs(a) / 2.0


def _centroid(pts):
    if not pts:
        return (0.0, 0.0)
    sx = sum(p[0] for p in pts)
    sy = sum(p[1] for p in pts)
    n = len(pts)
    return (sx / n, sy / n)


def _add_line(ctx, p1, p2, layer=None):
    from core import actions
    _execute_entity(ctx, actions.add_line(p1, p2), layer)


def _add_circle(ctx, center, radius, layer=None):
    from core import actions
    _execute_entity(ctx, actions.add_circle(center, radius), layer)


def _add_text(ctx, pos, text, height=0.25, layer=None):
    from core import actions
    _execute_entity(ctx, actions.add_text(pos, str(text), height), layer)


def _add_rect(ctx, p1, p2, layer=None):
    x1, y1 = p1
    x2, y2 = p2
    _add_line(ctx, (x1, y1), (x2, y1), layer)
    _add_line(ctx, (x2, y1), (x2, y2), layer)
    _add_line(ctx, (x2, y2), (x1, y2), layer)
    _add_line(ctx, (x1, y2), (x1, y1), layer)


def _add_arc_approx(ctx, center, radius, start_ang, end_ang, layer=None, segments=12):
    da = (end_ang - start_ang) / segments
    pts = []
    for i in range(segments + 1):
        a = start_ang + i * da
        pts.append((center[0] + radius * math.cos(a),
                    center[1] + radius * math.sin(a)))
    for a, b in zip(pts[:-1], pts[1:]):
        _add_line(ctx, a, b, layer)


# ---------------------------------------------------------------------------
# Puente para la API Tool de IngeCAD vigente (start/on_option/on_point).
# No modifica ni sustituye las herramientas nativas del programa.
# ---------------------------------------------------------------------------

class ArchitectureTool(Tool):
    """Adaptador de las herramientas v0.7 al contrato de Tool vigente.

    El núcleo invoca start() y entrega todo texto por on_option(); no expone
    add_keyword/request_point/request_number/request_keyword ni on_number.
    Se conservan los estados y handlers originales del plugin.
    """

    def start(self):
        self.name = type(self).name
        self._arq_mode = "point"
        self._arq_keywords = set()
        self.on_start()

    def add_keyword(self, value):
        self._arq_keywords.add(str(value).casefold())

    def request_point(self):
        self._arq_mode = "point"

    def request_number(self):
        self._arq_mode = "number"

    def request_keyword(self):
        self._arq_mode = "keyword"

    def on_option(self, text: str) -> bool:
        raw = str(text).strip()
        if not raw:
            self.on_enter()
            return True
        # La fase de captura numérica prevalece sobre las palabras clave;
        # en otras fases se admiten números como opciones de menú.
        if self._arq_mode == "number":
            try:
                number = float(raw.replace(",", "."))
            except ValueError:
                if hasattr(self, "on_keyword"):
                    self.on_keyword(raw)
                    return True
                return False
            if not math.isfinite(number):
                self.ctx.echo("Indique un número finito válido.")
                return True
            handler = getattr(self, "on_number", None)
            if handler is None:
                return False
            handler(number)
            return True
        if hasattr(self, "on_keyword"):
            self.on_keyword(raw)
            return True
        return False

# ---------------------------------------------------------------------------
# Herramientas
# ---------------------------------------------------------------------------

class CapasArqTool(ArchitectureTool):
    name = "CAPASARQ"

    def on_start(self):
        _ensure_layers(self.ctx)
        self.ctx.echo("Capas ARQ-* creadas / verificadas.")
        for name in sorted(LAYERS.keys()):
            self.ctx.echo(f"  · {name}")
        self.ctx.finish()


class CapasAutoTool(ArchitectureTool):
    name = "CAPASAUTO"

    def on_start(self):
        _ensure_layers(self.ctx)
        self.ctx.echo("Distribución recomendada:")
        self.ctx.echo("  Muros/particiones → ARQ-MUROS / ARQ-TABIQUES")
        self.ctx.echo("  Pilares           → ARQ-PILAres")
        self.ctx.echo("  Puertas/Ventanas  → ARQ-PUERTAS / ARQ-VENTANAS")
        self.ctx.echo("  Áreas / textos    → ARQ-AREAS / ARQ-TEXTOS")
        self.ctx.echo("  Tramas            → ARQ-TRAMAS")
        self.ctx.finish()


class MuroTool(ArchitectureTool):
    """Muro de doble línea — flujo continuo con menú contextual.
    Palabras clave: espesor | puerta / p  (inserta carpintería y sigue).
    """
    name = "MURO"

    def on_start(self):
        self.thickness = 0.15
        self.pts = []
        self.last_segment = None
        self._door_mode = False
        self.add_keyword("espesor")
        self.add_keyword("puerta")
        self.add_keyword("p")
        self.add_keyword("fin")
        self.ctx.echo(f"MURO — espesor = {self.thickness:.3f} m  |  'espesor' cambia  |  'P' inserta puerta")
        self.ctx.echo("Indique primer punto del muro:")
        self.request_point()

    def on_keyword(self, key: str):
        key = key.lower()
        if key == "espesor":
            self.ctx.echo("Nuevo espesor (m):")
            self._waiting_thickness = True
            self.request_number()
            return
        if key in ("puerta", "p"):
            if self.last_segment is None:
                self.ctx.echo("No hay un tramo de muro completo. Marque el segundo punto antes de insertar la puerta.")
                self.ctx.echo("Indique el punto final del muro:" if self.pts else "Indique primer punto del muro:")
                self.request_point()
                return
            self._door_mode = True
            self.ctx.echo("PUERTA en muro — indique punto de inserción sobre el tramo (o Enter = centro del último):")
            self.request_point()
            return
        if key == "fin":
            self.ctx.echo("Comando MURO finalizado.")
            self.ctx.finish()
            return
        self.request_point()

    def on_number(self, value: float):
        if getattr(self, "_waiting_thickness", False):
            if value > 0.01:
                self.thickness = value
                self.ctx.echo(f"Espesor = {self.thickness:.3f} m")
            self._waiting_thickness = False
            self.ctx.echo("Continúe indicando puntos:")
            self.request_point()
            return
        self.request_point()

    def on_point(self, pt):
        if self._door_mode:
            self._insert_door_at(pt)
            self._door_mode = False
            self.ctx.echo("Puerta insertada. Continúe el muro (siguiente punto) o Enter / 'fin':")
            self.request_point()
            return
        if not self.pts:
            self.pts.append(pt)
            self.ctx.echo("Marque el SEGUNDO punto con el ratón para dibujar el muro (Intro no dibuja el tramo):")
            self.request_point()
            return
        p0 = self.pts[-1]
        p1 = pt
        if _dist(p0, p1) < 1e-8:
            self.ctx.echo("El segundo punto coincide con el anterior; indique otro punto para definir la longitud del muro.")
            self.request_point()
            return
        self._draw_wall_segment(p0, p1)
        self.last_segment = (p0, p1)
        self.pts.append(p1)
        self.ctx.echo("Siguiente punto (Enter termina / 'P' puerta / 'espesor'):")
        self.request_point()

    def on_enter(self):
        if self._door_mode and self.last_segment:
            mid = _mid(self.last_segment[0], self.last_segment[1])
            self._insert_door_at(mid)
            self._door_mode = False
            self.ctx.echo("Puerta en centro del tramo. Continúe el muro:")
            self.request_point()
            return
        if len(self.pts) == 1:
            self.ctx.echo("No se ha dibujado el muro: falta el segundo punto. Haga clic en el extremo del tramo; 'fin' o ESC cancela.")
            self.request_point()
            return
        if len(self.pts) >= 2:
            self.ctx.echo(f"Tramo de muro cerrado ({len(self.pts)-1} segmentos).")
        else:
            self.ctx.echo("Todavía no hay puntos definidos.")
        self.pts = []
        self.last_segment = None
        self.ctx.echo("Nuevo tramo de muro — indique primer punto (o 'fin' / ESC):")
        self.request_point()

    def _draw_wall_segment(self, p0, p1):
        u = _unit(p0, p1)
        n = _perp(u)
        half = self.thickness / 2.0
        a1 = _offset_point(p0, n, half)
        a2 = _offset_point(p1, n, half)
        b1 = _offset_point(p0, n, -half)
        b2 = _offset_point(p1, n, -half)
        _add_line(self.ctx, a1, a2, "ARQ-MUROS")
        _add_line(self.ctx, b1, b2, "ARQ-MUROS")
        _add_line(self.ctx, a1, b1, "ARQ-MUROS")
        _add_line(self.ctx, a2, b2, "ARQ-MUROS")

    def _insert_door_at(self, pt):
        """Símbolo simplificado de puerta 1 hoja (0.80 m) sobre el muro."""
        width = 0.80
        if self.last_segment:
            u = _unit(self.last_segment[0], self.last_segment[1])
        else:
            u = (1.0, 0.0)
        n = _perp(u)
        half_w = width / 2.0
        p_a = _offset_point(pt, u, -half_w)
        p_b = _offset_point(pt, u, half_w)
        _add_line(self.ctx, p_a, _offset_point(p_a, n, self.thickness * 0.6), "ARQ-PUERTAS")
        _add_line(self.ctx, p_b, _offset_point(p_b, n, self.thickness * 0.6), "ARQ-PUERTAS")
        _add_arc_approx(self.ctx, p_a, width, 0.0, math.pi / 2, "ARQ-PUERTAS", segments=8)
        _add_text(self.ctx, (pt[0], pt[1] + 0.25), "P", 0.18, "ARQ-PUERTAS")
        self.ctx.echo(f"Puerta 1 hoja ({width:.2f} m) insertada.")


class PilarTool(ArchitectureTool):
    name = "PILAR"

    def on_start(self):
        self.shape = "rect"
        self.w = 0.30
        self.h = 0.30
        self.r = 0.15
        self.add_keyword("rect")
        self.add_keyword("circ")
        self.add_keyword("r")
        self.add_keyword("c")
        self.ctx.echo("PILAR — 'rect' (default) o 'circ'. Indique centro:")
        self.request_point()

    def on_keyword(self, key: str):
        key = key.lower()
        if key in ("rect", "r"):
            self.shape = "rect"
            self.ctx.echo("Rectangular. Ancho (m) o punto de centro:")
            self.request_number()
            self._waiting = "w"
            return
        if key in ("circ", "c"):
            self.shape = "circ"
            self.ctx.echo("Circular. Radio (m) o punto de centro:")
            self.request_number()
            self._waiting = "r"
            return
        self.request_point()

    def on_number(self, value: float):
        w = getattr(self, "_waiting", None)
        if w == "w":
            self.w = max(0.05, value)
            self.ctx.echo(f"Ancho = {self.w:.3f}. Alto (m):")
            self._waiting = "h"
            self.request_number()
            return
        if w == "h":
            self.h = max(0.05, value)
            self.ctx.echo(f"Alto = {self.h:.3f}. Indique centro:")
            self._waiting = None
            self.request_point()
            return
        if w == "r":
            self.r = max(0.05, value)
            self.ctx.echo(f"Radio = {self.r:.3f}. Indique centro:")
            self._waiting = None
            self.request_point()
            return
        self.request_point()

    def on_point(self, pt):
        if self.shape == "rect":
            hw, hh = self.w / 2, self.h / 2
            _add_rect(self.ctx, (pt[0] - hw, pt[1] - hh), (pt[0] + hw, pt[1] + hh), "ARQ-PILAres")
            self.ctx.echo(f"Pilar rect {self.w:.2f}×{self.h:.2f}")
        else:
            _add_circle(self.ctx, pt, self.r, "ARQ-PILAres")
            self.ctx.echo(f"Pilar circ r={self.r:.2f}")
        self.ctx.echo("Siguiente centro o ESC:")
        self.request_point()


class PuertaTool(ArchitectureTool):
    name = "PUERTA"

    def on_start(self):
        self.width = 0.80
        self.hojas = 1
        self.add_keyword("1")
        self.add_keyword("2")
        self.add_keyword("ancho")
        self.ctx.echo("PUERTA — 1 hoja (default) o 2. 'ancho' cambia. Indique punto de inserción:")
        self.request_point()

    def on_keyword(self, key: str):
        key = key.lower()
        if key == "1":
            self.hojas = 1
            self.ctx.echo("1 hoja. Indique punto:")
        elif key == "2":
            self.hojas = 2
            self.ctx.echo("2 hojas. Indique punto:")
        elif key == "ancho":
            self.ctx.echo("Ancho (m):")
            self.request_number()
            return
        self.request_point()

    def on_number(self, value: float):
        if value > 0.1:
            self.width = value
            self.ctx.echo(f"Ancho = {self.width:.3f}")
        self.request_point()

    def on_point(self, pt):
        w = self.width
        u = (1.0, 0.0)
        n = (0.0, 1.0)
        half = w / 2
        pa = _offset_point(pt, u, -half)
        pb = _offset_point(pt, u, half)
        _add_line(self.ctx, pa, _offset_point(pa, n, 0.12), "ARQ-PUERTAS")
        _add_line(self.ctx, pb, _offset_point(pb, n, 0.12), "ARQ-PUERTAS")
        if self.hojas == 1:
            _add_arc_approx(self.ctx, pa, w, 0, math.pi / 2, "ARQ-PUERTAS", 8)
        else:
            _add_arc_approx(self.ctx, pa, w / 2, 0, math.pi / 2, "ARQ-PUERTAS", 6)
            _add_arc_approx(self.ctx, pb, w / 2, math.pi / 2, math.pi, "ARQ-PUERTAS", 6)
        _add_text(self.ctx, (pt[0], pt[1] + 0.3), f"P{self.hojas}", 0.18, "ARQ-PUERTAS")
        self.ctx.echo(f"Puerta {self.hojas} hoja(s) {w:.2f} m")
        self.ctx.echo("Siguiente punto o ESC:")
        self.request_point()


class VentanaTool(ArchitectureTool):
    name = "VENTANA"

    def on_start(self):
        self.width = 1.20
        self.add_keyword("ancho")
        self.ctx.echo("VENTANA — indique punto de inserción ('ancho' para cambiar):")
        self.request_point()

    def on_keyword(self, key: str):
        if key.lower() == "ancho":
            self.ctx.echo("Ancho (m):")
            self.request_number()
            return
        self.request_point()

    def on_number(self, value: float):
        if value > 0.1:
            self.width = value
            self.ctx.echo(f"Ancho = {self.width:.3f}")
        self.request_point()

    def on_point(self, pt):
        w = self.width
        half = w / 2
        _add_line(self.ctx, (pt[0] - half, pt[1]), (pt[0] + half, pt[1]), "ARQ-VENTANAS")
        _add_line(self.ctx, (pt[0] - half, pt[1] + 0.04), (pt[0] + half, pt[1] + 0.04), "ARQ-VENTANAS")
        _add_line(self.ctx, (pt[0] - half, pt[1] - 0.04), (pt[0] + half, pt[1] - 0.04), "ARQ-VENTANAS")
        _add_text(self.ctx, (pt[0], pt[1] + 0.25), "V", 0.18, "ARQ-VENTANAS")
        self.ctx.echo(f"Ventana {w:.2f} m")
        self.request_point()


class ArmarioTool(ArchitectureTool):
    name = "ARMARIO"

    def on_start(self):
        self.ctx.echo("ARMARIO — indique esquina 1:")
        self.request_point()
        self.pts = []

    def on_point(self, pt):
        self.pts.append(pt)
        if len(self.pts) == 1:
            self.ctx.echo("Esquina 2 (diagonal):")
            self.request_point()
            return
        p1, p2 = self.pts[0], self.pts[1]
        _add_rect(self.ctx, p1, p2, "ARQ-ARMARIOS")
        # línea diagonal de armario
        _add_line(self.ctx, p1, p2, "ARQ-ARMARIOS")
        c = _mid(p1, p2)
        _add_text(self.ctx, c, "A", 0.20, "ARQ-ARMARIOS")
        self.ctx.echo("Armario creado.")
        self.pts = []
        self.ctx.echo("Siguiente esquina 1 o ESC:")
        self.request_point()


class SuperficieTool(ArchitectureTool):
    name = "SUPERFICIE"

    def on_start(self):
        self.pts = []
        self.ctx.echo("SUPERFICIE — indique vértices del contorno (Enter cierra):")
        self.request_point()

    def on_point(self, pt):
        self.pts.append(pt)
        self.ctx.echo(f"Vértice {len(self.pts)}. Siguiente o Enter:")
        self.request_point()

    def on_enter(self):
        if len(self.pts) < 3:
            self.ctx.echo("Se necesitan al menos 3 puntos.")
            self.ctx.finish()
            return
        area = _poly_area(self.pts)
        c = _centroid(self.pts)
        _add_text(self.ctx, c, f"{area:.2f} m²", 0.30, "ARQ-AREAS")
        self.ctx.echo(f"Área = {area:.2f} m²")
        self.ctx.finish()


class CamaraTool(ArchitectureTool):
    name = "CAMARA"

    def on_start(self):
        self.offset = 0.05
        self.add_keyword("offset")
        self.pts = []
        self.ctx.echo("CAMARA — indique puntos del eje (Enter termina). 'offset' cambia separación:")
        self.request_point()

    def on_keyword(self, key: str):
        if key.lower() == "offset":
            self.ctx.echo("Offset (m):")
            self.request_number()
            return
        self.request_point()

    def on_number(self, value: float):
        self.offset = max(0.01, value)
        self.ctx.echo(f"Offset = {self.offset:.3f}")
        self.request_point()

    def on_point(self, pt):
        self.pts.append(pt)
        if len(self.pts) >= 2:
            p0, p1 = self.pts[-2], self.pts[-1]
            u = _unit(p0, p1)
            n = _perp(u)
            a1 = _offset_point(p0, n, self.offset)
            a2 = _offset_point(p1, n, self.offset)
            _add_line(self.ctx, a1, a2, "ARQ-CAMARAS")
        self.ctx.echo("Siguiente punto o Enter:")
        self.request_point()

    def on_enter(self):
        self.ctx.echo("Cámara / eje terminado.")
        self.ctx.finish()


class EscaleraTool(ArchitectureTool):
    name = "ESCALERA"

    def on_start(self):
        self.n_steps = 12
        self.step_h = 0.175
        self.step_w = 0.28
        self.add_keyword("peldaños")
        self.add_keyword("huella")
        self.add_keyword("contrahuella")
        self.ctx.echo("ESCALERA — indique origen (esquina inferior). Keywords: peldaños / huella / contrahuella")
        self.request_point()

    def on_keyword(self, key: str):
        key = key.lower()
        if key == "peldaños":
            self.ctx.echo("Nº peldaños:")
            self._waiting = "n"
            self.request_number()
            return
        if key == "huella":
            self.ctx.echo("Huella (m):")
            self._waiting = "w"
            self.request_number()
            return
        if key == "contrahuella":
            self.ctx.echo("Contrahuella (m):")
            self._waiting = "h"
            self.request_number()
            return
        self.request_point()

    def on_number(self, value: float):
        w = getattr(self, "_waiting", None)
        if w == "n":
            self.n_steps = max(2, int(value))
        elif w == "w":
            self.step_w = max(0.15, value)
        elif w == "h":
            self.step_h = max(0.10, value)
        self._waiting = None
        self.ctx.echo(f"Peldaños={self.n_steps}  huella={self.step_w:.3f}  contrahuella={self.step_h:.3f}")
        self.request_point()

    def on_point(self, pt):
        x0, y0 = pt
        for i in range(self.n_steps + 1):
            x = x0 + i * self.step_w
            y = y0 + i * self.step_h
            _add_line(self.ctx, (x, y0), (x, y), "ARQ-ESCALERAS")
            if i < self.n_steps:
                _add_line(self.ctx, (x, y), (x + self.step_w, y), "ARQ-ESCALERAS")
        self.ctx.echo(f"Escalera {self.n_steps} peldaños generada.")
        self.ctx.finish()


class ElementosTool(ArchitectureTool):
    name = "ELEMENTOS"

    GROUPS = {
        "1": ("Muros", "ARQ-MUROS"),
        "2": ("Tabiques", "ARQ-TABIQUES"),
        "3": ("Pilares", "ARQ-PILAres"),
        "4": ("Puertas", "ARQ-PUERTAS"),
        "5": ("Ventanas", "ARQ-VENTANAS"),
        "6": ("Armarios", "ARQ-ARMARIOS"),
        "7": ("Escaleras", "ARQ-ESCALERAS"),
        "8": ("Cámaras", "ARQ-CAMARAS"),
        "9": ("Áreas", "ARQ-AREAS"),
        "0": ("Tramas", "ARQ-TRAMAS"),
    }

    def on_start(self):
        self.ctx.echo("ELEMENTOS — active/desactive grupos (número):")
        for k, (label, layer) in self.GROUPS.items():
            self.ctx.echo(f"  {k} = {label} ({layer})")
        self.request_keyword()

    def on_keyword(self, key: str):
        if key in self.GROUPS:
            label, layer = self.GROUPS[key]
            self.ctx.echo(f"Grupo «{label}» → capa {layer}. Use el administrador de capas para on/off.")
        else:
            self.ctx.echo("Número no válido.")
        self.ctx.finish()


class BloqueTool(ArchitectureTool):
    name = "BLOQUE"

    ITEMS = {
        "1": "Sofá",
        "2": "Mesa",
        "3": "Silla",
        "4": "Cama",
        "5": "Lavabo",
        "6": "WC",
    }

    def on_start(self):
        self.ctx.echo("BLOQUE — elija tipo:")
        for k, name in self.ITEMS.items():
            self.ctx.echo(f"  {k} = {name}")
        self.request_keyword()

    def on_keyword(self, key: str):
        if key in self.ITEMS:
            self.item = self.ITEMS[key]
            self.ctx.echo(f"{self.item}. Indique punto de inserción:")
            self.request_point()
            return
        self.ctx.echo("Opción no válida.")
        self.ctx.finish()

    def on_point(self, pt):
        # Símbolo genérico de bloque
        _add_rect(self.ctx, (pt[0] - 0.4, pt[1] - 0.3), (pt[0] + 0.4, pt[1] + 0.3), "ARQ-MOBILIARIO")
        _add_text(self.ctx, pt, self.item[:4], 0.15, "ARQ-MOBILIARIO")
        self.ctx.echo(f"Bloque «{self.item}» insertado.")
        self.ctx.finish()


class MemoriaCarpTool(ArchitectureTool):
    name = "MEMORIACARP"

    def on_start(self):
        self.add_keyword("tabla")
        self.add_keyword("fichas")
        self.ctx.echo("MEMORIACARP — 'tabla' o 'fichas':")
        self.request_keyword()

    def on_keyword(self, key: str):
        key = key.lower()
        if key == "tabla":
            self._list_console()
            self.ctx.finish()
            return
        if key == "fichas":
            self.ctx.echo("Indique punto de inserción de las fichas:")
            self.request_point()
            return
        self.ctx.echo("Use 'tabla' o 'fichas'.")
        self.ctx.finish()

    def _list_console(self):
        self.ctx.echo("=== Memoria de Carpintería (resumen) ===")
        self.ctx.echo("Capas ARQ-PUERTAS / ARQ-VENTANAS / ARQ-ARMARIOS")
        self.ctx.echo("Revise el número de entidades en cada capa.")
        self.ctx.echo("Modelos sugeridos: P01 (puerta 0.80), V01 (ventana 1.20), A01 (armario).")

    def on_point(self, pt):
        x, y = pt
        fichas = [
            ("P01", "Puerta 1 hoja", "0.80 × 2.10", "Madera"),
            ("V01", "Ventana corredera", "1.20 × 1.20", "Aluminio"),
            ("A01", "Armario empotrado", "1.00 × 0.60", "Melamina"),
        ]
        for i, (mod, desc, dims, mat) in enumerate(fichas):
            ox = x + i * 3.5
            _add_rect(self.ctx, (ox, y), (ox + 3.0, y + 2.0), "ARQ-MEMORIA")
            _add_text(self.ctx, (ox + 0.15, y + 1.6), f"Modelo: {mod}", 0.22, "ARQ-MEMORIA")
            _add_text(self.ctx, (ox + 0.15, y + 1.2), desc, 0.18, "ARQ-MEMORIA")
            _add_text(self.ctx, (ox + 0.15, y + 0.8), f"Dim: {dims}", 0.18, "ARQ-MEMORIA")
            _add_text(self.ctx, (ox + 0.15, y + 0.4), f"Mat: {mat}", 0.18, "ARQ-MEMORIA")
        self.ctx.echo("Fichas de memoria generadas en ARQ-MEMORIA.")
        self.ctx.finish()


class SelAtribTool(ArchitectureTool):
    """Selección por Atributos/Elementos mediante un árbol jerárquico de tipos.
    """
    name = "SELATRIB"

    ELEMENTOS = {
        "1":  ("Arcos", None),
        "2":  ("Bloques", ["ARQ-MOBILIARIO"]),
        "3":  ("Carpinterías", ["ARQ-PUERTAS", "ARQ-VENTANAS", "ARQ-ARMARIOS"]),
        "4":  ("Círculos", None),
        "5":  ("Cotas", ["ARQ-COTAS"]),
        "6":  ("Curvas por puntos", None),
        "7":  ("Elipses", None),
        "8":  ("Particiones curvas", ["ARQ-MUROS"]),
        "9":  ("Particiones rectas", ["ARQ-MUROS", "ARQ-TABIQUES"]),
        "10": ("Pilares", ["ARQ-PILAres"]),
        "11": ("Polígonos", None),
        "12": ("Polilíneas", None),
        "13": ("Puntos", None),
        "14": ("Rectángulos", None),
        "15": ("Rectas", None),
        "16": ("Señales", None),
        "17": ("Textos", ["ARQ-TEXTOS", "ARQ-AREAS"]),
        "18": ("Tramas", ["ARQ-TRAMAS"]),
    }

    COLORES = {
        "1": "Rojo", "2": "Amarillo", "3": "Verde", "4": "Cian",
        "5": "Azul", "6": "Magenta", "7": "Blanco", "8": "Color 8 (gris)",
        "71": "Color 71", "251": "Color 251", "252": "Color 252",
    }

    def on_start(self):
        self.ctx.echo("=== Selección por Atributos/Elementos ===")
        self.ctx.echo("  E = Elementos     C = Capas")
        self.ctx.echo("  O = Colores       T = Tipos de línea")
        self.ctx.echo("  G = Grueso de línea")
        self.add_keyword("e")
        self.add_keyword("elementos")
        self.add_keyword("c")
        self.add_keyword("capas")
        self.add_keyword("o")
        self.add_keyword("colores")
        self.add_keyword("t")
        self.add_keyword("tipos")
        self.add_keyword("g")
        self.add_keyword("grueso")
        self.request_keyword()

    def on_keyword(self, key: str):
        key = key.lower()
        if key in ("e", "elementos"):
            self.ctx.echo("Elementos:")
            for k, (label, _) in self.ELEMENTOS.items():
                self.ctx.echo(f"  {k:>2}  {label}")
            self.ctx.echo("Indique el número del tipo a seleccionar (ej. 3 = Carpinterías):")
            self._mode = "elem"
            self.request_number()
            return
        if key in ("c", "capas"):
            self.ctx.echo("Capas (ejemplo del proyecto + ARQ-*):")
            self.ctx.echo("  0, 1, 01a-Baja, 01b-Baja Muebles y Superficies, Hatch")
            for name in sorted(LAYERS.keys()):
                self.ctx.echo(f"  · {name}")
            self.ctx.echo("Escriba el nombre (o parte) de la capa a filtrar:")
            self._mode = "capa"
            self.request_keyword()
            return
        if key in ("o", "colores"):
            self.ctx.echo("Colores:")
            for k, name in self.COLORES.items():
                self.ctx.echo(f"  {k:>3}  {name}")
            self.ctx.echo("Indique número ACI del color:")
            self._mode = "color"
            self.request_number()
            return
        if key in ("t", "tipos"):
            self.ctx.echo("Tipos de línea habituales: Continuous, DASHED, CENTER, HIDDEN, PHANTOM…")
            self.ctx.echo("Filtro informativo. Use el administrador de tipos de línea de IngeCAD.")
            self.ctx.finish()
            return
        if key in ("g", "grueso"):
            self.ctx.echo("Gruesos de línea: 0.00  0.13  0.18  0.25  0.35  0.50  0.70  1.00")
            self.ctx.echo("Filtro informativo. Ajuste el grueso en propiedades de entidad.")
            self.ctx.finish()
            return
        if getattr(self, "_mode", None) == "capa":
            layer = key.strip()
            self.ctx.echo(f"Filtro por capa «{layer}».")
            self.ctx.echo("En IngeCAD: use el filtro de capas o selección por atributo nativo.")
            self.ctx.echo("Si es una capa ARQ-*, las entidades de esa capa quedan resaltadas conceptualmente.")
            self.ctx.finish()
            return
        self.ctx.echo("Opción no reconocida. Use E / C / O / T / G.")
        self.ctx.finish()

    def on_number(self, value: float):
        mode = getattr(self, "_mode", None)
        if mode == "elem":
            key = str(int(value))
            if key in self.ELEMENTOS:
                label, layers = self.ELEMENTOS[key]
                self.ctx.echo(f"→ Seleccionado: {label}")
                if layers:
                    self.ctx.echo(f"  Capas asociadas: {', '.join(layers)}")
                    self.ctx.echo("  Las entidades de esas capas se consideran seleccionadas.")
                    self.ctx.echo("  Aplique el filtro nativo de IngeCAD si es necesario.")
                else:
                    self.ctx.echo("  Tipo geométrico — filtre por tipo de entidad en el selector de IngeCAD.")
            else:
                self.ctx.echo("Número de elemento no válido (1-18).")
            self.ctx.finish()
            return
        if mode == "color":
            aci = int(value)
            name = self.COLORES.get(str(aci), f"ACI {aci}")
            self.ctx.echo(f"→ Color {name}. Aplique este color a la selección actual o filtre por él.")
            self.ctx.finish()
            return
        self.ctx.finish()


class TramaTool(ArchitectureTool):
    name = "TRAMA"

    PATTERNS = {
        "1": "ANGLE",
        "2": "ANSI31",
        "3": "U10_45_135",
        "4": "SOLID",
        "5": "HORIZONTAL",
        "6": "VERTICAL",
        "7": "DIAGONAL",
    }

    def on_start(self):
        self.ctx.echo("TRAMA — elija patrón:")
        for k, name in self.PATTERNS.items():
            self.ctx.echo(f"  {k} = {name}")
        for k in self.PATTERNS:
            self.add_keyword(k)
        self.request_keyword()
        self.pts = []
        self.pattern = "ANSI31"
        self.scale = 1.0

    def on_keyword(self, key: str):
        if key in self.PATTERNS:
            self.pattern = self.PATTERNS[key]
            self.ctx.echo(f"Patrón = {self.pattern}. Indique escala (número) o puntos del contorno:")
            self.request_number()
            self._waiting_scale = True
            return
        self.ctx.echo("Patrón no válido.")
        self.ctx.finish()

    def on_number(self, value: float):
        if getattr(self, "_waiting_scale", False):
            self.scale = max(0.01, value)
            self._waiting_scale = False
            self.ctx.echo(f"Escala = {self.scale}. Indique vértices del contorno (Enter cierra):")
            self.request_point()
            return
        self.request_point()

    def on_point(self, pt):
        self.pts.append(pt)
        self.ctx.echo(f"Vértice {len(self.pts)}. Siguiente o Enter:")
        self.request_point()

    def on_enter(self):
        if len(self.pts) < 3:
            self.ctx.echo("Contorno insuficiente.")
            self.ctx.finish()
            return
        try:
            from core import actions
            self.ctx.execute(actions.add_hatch(self.pts, pattern=self.pattern, scale=self.scale))
            self.ctx.echo(f"Hatch '{self.pattern}' aplicado.")
        except Exception:
            self.ctx.echo("API hatch no disponible — generando relleno aproximado.")
            self._approx_fill()
        self.ctx.finish()

    def _approx_fill(self):
        xs = [p[0] for p in self.pts]
        ys = [p[1] for p in self.pts]
        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
        step = max((xmax - xmin), (ymax - ymin)) / 12.0 * self.scale
        if step < 1e-6:
            return
        y = ymin
        while y <= ymax:
            _add_line(self.ctx, (xmin, y), (xmax, y), "ARQ-TRAMAS")
            y += step


class HiperVinculoTool(ArchitectureTool):
    """Hipervínculo / URL — inserción de enlace a fichero externo (PDF, etc.)
    """
    name = "HIPERVINCULO"

    def on_start(self):
        self.path = ""
        self.add_keyword("ejemplo")
        self.add_keyword("archivo")
        self.add_keyword("descartar")
        self.ctx.echo("=== Inserción Hiperenlace ===")
        self.ctx.echo("Introduzca la ruta completa del fichero, o:")
        self.ctx.echo("  ejemplo  → ficha de producto de ejemplo (Sikasil WT-40)")
        self.ctx.echo("  archivo  → (simula diálogo Abrir archivo)")
        self.request_keyword()

    def on_keyword(self, key: str):
        k = key.lower().strip()
        if k == "ejemplo":
            self.path = r"C:\Product_Data_Sheets\window_data_sheet.pdf"
        elif k == "archivo":
            self.path = r"C:\Product_Data_Sheets\Sikasil_WT-40.pdf"
            self.ctx.echo("(Simulación de diálogo Archivo…)")
        elif k == "descartar":
            self.path = ""
            self.ctx.echo("Camino descartado. Introduzca otra ruta o 'ejemplo':")
            self.request_keyword()
            return
        else:
            self.path = key
        self.ctx.echo(f"Hiperenlace: {self.path}")
        self.ctx.echo("Indique el punto de inserción del marcador en el dibujo:")
        self.request_point()

    def on_point(self, pt):
        _add_circle(self.ctx, pt, 0.18, "ARQ-HIPERVINCULOS")
        _add_circle(self.ctx, pt, 0.10, "ARQ-HIPERVINCULOS")
        _add_circle(self.ctx, pt, 0.04, "ARQ-HIPERVINCULOS")
        label = "URL"
        try:
            base = os.path.basename(self.path.replace("\\", "/"))
            if base:
                label = base[:22]
        except Exception:
            pass
        _add_text(self.ctx, (pt[0] + 0.25, pt[1] + 0.12), label, 0.16, "ARQ-HIPERVINCULOS")
        short = self.path
        if len(short) > 55:
            short = "…" + short[-52:]
        _add_text(self.ctx, (pt[0] + 0.25, pt[1] - 0.18), short, 0.11, "ARQ-HIPERVINCULOS")
        self.ctx.echo(f"Hipervínculo creado → {self.path}")
        self.ctx.echo("Al hacer clic sobre el marcador (si IngeCAD lo soporta) se abrirá el documento.")
        self.ctx.echo("En el vídeo se abre Acrobat Reader con la ficha de producto.")
        self.ctx.finish()


class UrlTool(HiperVinculoTool):
    name = "URL"


class Curvas3DTool(ArchitectureTool):
    """Curvas de nivel → 3D.
    Flujo: indicar altura base → incremento de altura → dibujar curvas
    en orden; se elevan con Z = base + i * paso.
    """
    name = "CURVAS3D"

    def on_start(self):
        self.base = 0.0
        self.step = 1.0
        self.curves = []
        self.current = []
        self._phase = "base"
        self.add_keyword("base")
        self.add_keyword("paso")
        self.add_keyword("fin")
        self.add_keyword("aceptar")
        self.ctx.echo("=== Altura curvas de nivel (CURVAS3D) ===")
        self.ctx.echo("Indicar altura base [0.00]:")
        self.request_number()

    def on_keyword(self, key: str):
        key = key.lower()
        if key == "base":
            self.ctx.echo("Indicar altura base:")
            self._phase = "base"
            self.request_number()
            return
        if key == "paso":
            self.ctx.echo("Indicar incremento de altura:")
            self._phase = "paso"
            self.request_number()
            return
        if key in ("fin", "aceptar"):
            self._finalize()
            return
        self.ctx.echo("Indique puntos de la curva o 'fin':")
        self.request_point()

    def on_number(self, value: float):
        if self._phase == "base":
            self.base = value
            self.ctx.echo(f"Altura base = {self.base:.2f}")
            self.ctx.echo("Indicar incremento de altura [1.00]:")
            self._phase = "paso"
            self.request_number()
            return
        if self._phase == "paso":
            self.step = value if abs(value) > 1e-9 else 1.0
            self.ctx.echo(f"Incremento = {self.step:.2f}")
            self.ctx.echo("Indique los puntos de cada curva de nivel (orden de menor a mayor cota).")
            self.ctx.echo("Enter cierra una curva. Escriba 'fin' cuando termine.")
            self._phase = "curvas"
            self.request_point()
            return
        self.request_point()

    def on_point(self, pt):
        if self._phase != "curvas":
            self.ctx.echo("Primero confirme altura base e incremento.")
            self.request_number()
            return
        self.current.append(pt)
        self.ctx.echo(f"  punto {len(self.current)} — siguiente o Enter (cierra curva):")
        self.request_point()

    def on_enter(self):
        if self._phase != "curvas":
            if self._phase == "base":
                self.base = 0.0
                self.ctx.echo("Base = 0.00 (por defecto)")
                self.ctx.echo("Indicar incremento de altura [1.00]:")
                self._phase = "paso"
                self.request_number()
                return
            if self._phase == "paso":
                self.step = 1.0
                self.ctx.echo("Incremento = 1.00 (por defecto)")
                self.ctx.echo("Indique puntos de las curvas (Enter cierra / 'fin' genera 3D):")
                self._phase = "curvas"
                self.request_point()
                return
        if len(self.current) >= 2:
            self.curves.append(list(self.current))
            z_est = self.base + (len(self.curves) - 1) * self.step
            self.ctx.echo(f"Curva {len(self.curves)} registrada ({len(self.current)} pts) → Z≈{z_est:.2f}")
        self.current = []
        self.ctx.echo("Nueva curva o escriba 'fin' para elevar a 3D:")
        self.request_point()

    def _finalize(self):
        if self.current and len(self.current) >= 2:
            self.curves.append(list(self.current))
        if not self.curves:
            self.ctx.echo("No se han definido curvas. Comando cancelado.")
            self.ctx.finish()
            return
        self.ctx.echo(f"Elevando {len(self.curves)} curvas  (base={self.base:.2f}  paso={self.step:.2f})…")
        for i, pts in enumerate(self.curves):
            z = self.base + i * self.step
            for a, b in zip(pts[:-1], pts[1:]):
                _add_line(self.ctx, a, b, "ARQ-CURVAS3D")
            c = _centroid(pts)
            _add_text(self.ctx, (c[0], c[1]), f"Z={z:.2f}", height=0.30, layer="ARQ-CURVAS3D")
            try:
                from core import actions
                pts3d = [(p[0], p[1], z) for p in pts]
                self.ctx.execute(actions.AddEntityCommand("ARQ-CURVAS3D",
                    lambda msp, vertices=pts3d: msp.add_polyline3d(vertices),
                    layer="ARQ-CURVAS3D"))
            except Exception as exc:
                self.ctx.echo(f"No se pudo crear la polilínea 3D: {exc}")
                step = max(1, len(pts) // 10)
                for p in pts[::step]:
                    _add_circle(self.ctx, p, 0.06, "ARQ-CURVAS3D")
        self.ctx.echo("Curvas procesadas; compruebe la geometría 3D en ARQ-CURVAS3D.")
        self.ctx.echo("Active la vista 3D / órbita de IngeCAD para ver el relieve (como en el vídeo).")
        self.ctx.finish()


class VertPolyTool(ArchitectureTool):
    """Vértices de polilínea + listado de coordenadas.

    Flujo:
      1. Indicar los vértices de la parcela (polilínea).
      2. Enter cierra la polilínea.
      3. Indicar punto de inserción del listado de coordenadas.
      4. Se numeran los vértices (1,2,3…) y se genera la tabla X/Y/Z.
    """
    name = "VERTPOLY"

    def on_start(self):
        self.pts = []
        self._mode = "collect"   # collect | insert
        self.ctx.echo("VERTPOLY — vértices de polilínea / coordenadas de parcela")
        self.ctx.echo("Indique los vértices de la polilínea (Enter cierra):")
        self.add_keyword("c")
        self.add_keyword("cerrar")
        self.request_point()

    def on_keyword(self, key: str):
        if key.lower() in ("c", "cerrar", "close") and self._mode == "collect":
            self.on_enter()
        else:
            self.request_point()

    def on_point(self, pt):
        if self._mode == "insert":
            self._generate(pt)
            return
        # modo collect
        self.pts.append(pt)
        n = len(self.pts)
        self.ctx.echo(f"  Vértice {n}  ({pt[0]:.3f}, {pt[1]:.3f})")
        self.ctx.echo("Siguiente vértice o Enter / 'c' para cerrar:")
        self.request_point()

    def on_enter(self):
        if self._mode != "collect":
            return
        if len(self.pts) < 2:
            self.ctx.echo("Se necesitan al menos 2 puntos.")
            self.ctx.finish()
            return
        self.ctx.echo(f"Polilínea con {len(self.pts)} vértices. Indique punto de inserción del listado:")
        self._mode = "insert"
        self.request_point()

    def _generate(self, insert_pt):
        # Deduplicar puntos consecutivos
        verts = []
        for p in self.pts:
            if not verts or _dist(verts[-1], p) > 1e-6:
                verts.append(p)
        if len(verts) > 1 and _dist(verts[0], verts[-1]) < 1e-6:
            verts = verts[:-1]

        if len(verts) < 2:
            self.ctx.echo("Polilínea inválida.")
            self.ctx.finish()
            return

        # Dibujar contorno
        for a, b in zip(verts, verts[1:] + [verts[0]]):
            _add_line(self.ctx, a, b, "ARQ-COORD")

        # Números en vértices (offset radial desde el centroide)
        cx, cy = _centroid(verts)
        for i, p in enumerate(verts, start=1):
            dx, dy = p[0] - cx, p[1] - cy
            L = math.hypot(dx, dy) or 1.0
            ox = p[0] + 0.28 * dx / L
            oy = p[1] + 0.28 * dy / L
            _add_text(self.ctx, (ox, oy), str(i), height=0.28, layer="ARQ-COORD")
            _add_circle(self.ctx, p, 0.06, "ARQ-COORD")

        # Listado de coordenadas (formato del vídeo)
        lines = []
        for i, p in enumerate(verts, start=1):
            x, y = p[0], p[1]
            z = p[2] if len(p) > 2 else 0.0
            lines.append(f"{i:>2}  {x:8.2f}  {y:8.2f}  {z:6.2f}")

        x0, y0 = insert_pt
        line_h = 0.32
        _add_text(self.ctx, (x0, y0 + line_h), "Nº     X         Y         Z", height=0.22, layer="ARQ-COORD")
        for i, txt in enumerate(lines):
            _add_text(self.ctx, (x0, y0 - i * line_h), txt, height=0.22, layer="ARQ-COORD")

        self.ctx.echo(f"Generados {len(verts)} vértices numerados + listado de coordenadas.")
        self.ctx.echo("Capa ARQ-COORD. Puede copiar el listado al portapapeles (nativo) o a Calc/Writer.")
        self.ctx.finish()


class VerticesTool(VertPolyTool):
    name = "VERTICES"


class ListaTextosTool(ArchitectureTool):
    """Genera un listado limpio de textos/áreas listo para portapapeles o tabla.

    Flujo:
      - El usuario indica un punto de inserción.
      - Se genera un bloque de texto multilínea con etiquetas de recinto + superficie
        (ejemplo realista) o se invita a usar textos ya existentes.
      - El contenido está formateado para pegar en Writer/Calc y convertir a tabla.
    """
    name = "LISTATEXTOS"

    def on_start(self):
        self.ctx.echo("LISTATEXTOS — listado de textos / superficies")
        self.ctx.echo("Opciones:")
        self.ctx.echo("  E = Ejemplo de recintos (COCINA, SALON…)")
        self.ctx.echo("  C = Solo cabecera de coordenadas (para VERTPOLY)")
        self.ctx.echo("  M = Mensaje de ayuda para copiar textos nativos")
        self.add_keyword("e")
        self.add_keyword("ejemplo")
        self.add_keyword("c")
        self.add_keyword("coord")
        self.add_keyword("m")
        self.add_keyword("manual")
        self.request_keyword()

    def on_keyword(self, key: str):
        key = key.lower()
        if key in ("e", "ejemplo"):
            self._mode = "ejemplo"
            self.ctx.echo("Indique punto de inserción del listado de recintos:")
            self.request_point()
        elif key in ("c", "coord"):
            self._mode = "coord"
            self.ctx.echo("Indique punto de inserción de la plantilla de coordenadas:")
            self.request_point()
        else:
            self.ctx.echo("=== Cómo copiar textos al portapapeles ===")
            self.ctx.echo("1. Seleccione los textos del dibujo (nombres de recintos + áreas).")
            self.ctx.echo("2. Edición → Copiar texto al portapapeles (si está disponible).")
            self.ctx.echo("3. Pegue (Ctrl+V) en un procesador de textos o en Texto multilínea.")
            self.ctx.echo("4. En Writer: Tabla → Convertir → Texto a tabla (separador espacio o ;).")
            self.ctx.echo("5. Puede llevar la tabla a Calc / Excel.")
            self.ctx.echo("Use LISTATEXTOS E para generar un ejemplo listo.")
            self.ctx.finish()

    def on_point(self, pt):
        mode = getattr(self, "_mode", "ejemplo")
        x0, y0 = pt
        line_h = 0.35
        if mode == "ejemplo":
            # Datos de ejemplo del vídeo (planta de vivienda)
            items = [
                ("COCINA", "10.80 m²"),
                ("PASILLO", "17.08 m²"),
                ("ASEO", "2.00 m²"),
                ("SALON", "35.75 m²"),
                ("DORMITORIO 1", "12.90 m²"),
                ("DORMITORIO 2", "12.87 m²"),
                ("SUP. TOTAL CONSTRUIDA", "117.64 m²"),
            ]
            _add_text(self.ctx, (x0, y0 + line_h), "RECINTO                  SUPERFICIE", height=0.22, layer="ARQ-TEXTOS")
            for i, (name, area) in enumerate(items):
                txt = f"{name:<22} {area}"
                _add_text(self.ctx, (x0, y0 - i * line_h), txt, height=0.22, layer="ARQ-TEXTOS")
            self.ctx.echo("Listado de ejemplo generado (capa ARQ-TEXTOS).")
            self.ctx.echo("Seleccione los textos y use 'Copiar texto al portapapeles' si está disponible,")
            self.ctx.echo("o transcriba / exporte para formar la tabla en Writer/Calc.")
        else:
            header = "Nº     X         Y         Z"
            _add_text(self.ctx, (x0, y0), header, height=0.22, layer="ARQ-COORD")
            self.ctx.echo("Plantilla de coordenadas colocada. Use VERTPOLY para rellenarla.")
        self.ctx.finish()


class AyudaArqTool(ArchitectureTool):
    name = "AYUDAARQ"

    def on_start(self):
        self.ctx.echo("=== Plugin Arquitectura v0.8 — comandos ===")
        self.ctx.echo("CAPASARQ / CAPASAUTO  — capas ARQ-*")
        self.ctx.echo("MURO                  — muro BIM encadenado; I o F5 cambia la cara, G toma las propiedades de otro muro,")
        self.ctx.echo("                        antes del primer punto, un número es el ESPESOR TOTAL (ofrece los tipos que lo tienen);")
        self.ctx.echo("                        T elige un tipo del catálogo (Termoarcilla, PYL, multicapa...; ver TIPOSMURO)")
        self.ctx.echo("                        terminar en la cara próxima de otro muro = T; en la alejada = L (lo recorta)")
        self.ctx.echo("MUROPARALELO          — distancia, línea base, lado y lado del espesor; un clic en vacío encadena otro")
        self.ctx.echo("ESTIRAMURO            — alarga o acorta un muro hasta un punto, una línea o la cara de otro muro (T/L)")
        self.ctx.echo("PIVOTAMURO            — mueve un extremo de un muro")
        self.ctx.echo("DIVIDEMURO            — divide un tramo en N partes iguales con muros perpendiculares")
        self.ctx.echo("BORRATRAMO            — borra el tramo de muro entre cruces (o hasta su extremo)")
        self.ctx.echo("PARTEMURO / UNIRMURO  — abre un vano en un muro / une dos muros alineados")
        self.ctx.echo("RECINTO               — espacio BIM (IfcSpace) con un clic dentro de la estancia; sigue a los muros")
        self.ctx.echo("PILAR                 — S sección (0,30x0,30 · D0,35 · IPE/IPN/HEA/HEB/UPN · 2UPN cajon/empresillado),")
        self.ctx.echo("                        E enganche 1-9, G girar 90°, A autorrotación, P a distancia de dos paramentos,")
        self.ctx.echo("                        U de un paramento, C recubrimiento")
        self.ctx.echo("PILAR                 — pilar rect/circ")
        self.ctx.echo("CARPINTERIA           — puertas, ventanas y huecos en muros y tabiques: clic en la cara hacia la que abre;")
        self.ctx.echo("                        P/V/H tipo, un número o N = ancho de hoja (puerta) o de hueco, Hojas 1/2 (2 0,625),")
        self.ctx.echo("                        M colocación: Libre (2.º clic: sentido) / Distancia d a la esquina / Centrada /")
        self.ctx.echo("                        Exterior (centrada en la otra cara) / Máxima; C cerco interior/centrado/exterior,")
        self.ctx.echo("                        E cerco (ancho y profundidad), R alféizar/vierteaguas/ventanal, B bisagra y S sentido")
        self.ctx.echo("                        de la última; pinchar una carpintería sustituye su modelo (misma identidad)")
        self.ctx.echo("PUERTAARQ / VENTANAARQ / HUECOARQ — CARPINTERIA con ese tipo de partida")
        self.ctx.echo("ARMARIO               — armarios (pendiente)")
        self.ctx.echo("SUPERFICIE            — área m² + etiqueta")
        self.ctx.echo("CAMARA                — eje / cámara de muro")
        self.ctx.echo("ESCALERA              — escalera en alzado")
        self.ctx.echo("ELEMENTOS             — activar/desactivar grupos")
        self.ctx.echo("BLOQUE                — mobiliario")
        self.ctx.echo("MEMORIACARP           — memoria de carpintería")
        self.ctx.echo("SELATRIB              — selección por atributos (árbol de elementos)")
        self.ctx.echo("TRAMA                 — hatch / tramas")
        self.ctx.echo("HIPERVINCULO / URL    — hipervínculo a fichero externo")
        self.ctx.echo("CURVAS3D              — elevar curvas de nivel a 3D")
        self.ctx.echo("VERTPOLY / VERTICES   — vértices + coordenadas de parcela (2017)")
        self.ctx.echo("LISTATEXTOS           — listado de textos/áreas para portapapeles")
        self.ctx.echo("AYUDAARQ              — esta ayuda")
        self.ctx.finish()


TOOL_CLASSES = (
    CapasArqTool, CapasAutoTool, MuroTool, PilarTool, PuertaTool,
    VentanaTool, ArmarioTool, SuperficieTool, CamaraTool, EscaleraTool,
    ElementosTool, BloqueTool, MemoriaCarpTool, SelAtribTool, TramaTool,
    HiperVinculoTool, UrlTool, Curvas3DTool, VertPolyTool, VerticesTool,
    ListaTextosTool, AyudaArqTool,
)


from .tools3d import Muro3DTool, Hueco3DTool, exportar_igz, configurar_igz
from .tools_v10 import MuroTool as MuroV10Tool, CarpinteriaTool, VentanaArqTool, EditarArqTool
from .columns import PilarBimTool
from .arq_properties import ArqPropiedadesTool

def diagnostico_arq(ctx, *args):
    from .architectural import collect
    from .architectural_v10 import junction_report
    try:
        model=collect(ctx.document)
        joints=junction_report(model['walls'])
        ctx.echo(f"ARQ: {len(model['walls'])} muros y {sum(len(w['openings']) for w in model['walls'])} huecos; encuentros detectados: {len(joints)}")
        for j in joints:
            ctx.echo(f"  {j['type']} entre {j['a'][:8]} y {j['b'][:8]} en ({j['point'][0]:.3f}, {j['point'][1]:.3f})")
        if joints: ctx.echo('Encuentros en planta: la capa ARQ-MUROS contiene la unión 2D. La unión 3D/IFC sigue pendiente.')
    except (ValueError,KeyError,TypeError) as err:
        ctx.echo('DIAGNOSTICOARQ: '+str(err))

from .wall_tools import MuroCarasTool, MuroParaleloTool, EstiraMuroTool, PivotaMuroTool, RecintoTool, DivideMuroTool, BorraTramoTool, ParteMuroTool, UnirMuroTool
from .column_tools import PilarTool as PilarPerfilesTool
from .opening_tools import (CarpinteriaTool as CarpinteriaArqTool, PuertaTool as PuertaArqTool,
                            VentanaTool as VentanaArqTool2, HuecoTool as HuecoArqTool)
TOOL_CLASSES = tuple(MuroCarasTool if t.name == "MURO" else PilarPerfilesTool if t.name == "PILAR" else t for t in TOOL_CLASSES) + (CarpinteriaArqTool, PuertaArqTool, VentanaArqTool2, HuecoArqTool, EditarArqTool, ArqPropiedadesTool, MuroParaleloTool, EstiraMuroTool, PivotaMuroTool, RecintoTool, DivideMuroTool, BorraTramoTool, ParteMuroTool, UnirMuroTool)

def arqdiag(ctx, *args):
    """Diagnóstico sin mutar el dibujo y sin depender de PySide6."""
    ctx.echo('ARQDIAG — Arquitectura 1.10.0-dev (motor de nodos, huella única 2D/3D, exportación .arqbim)')
    try:
        from .wall_tools import MuroCarasTool as MuroTool
        ctx.echo(f'Herramienta MURO: {MuroTool.__module__}.{MuroTool.__name__}')
        ctx.echo(f'Documento activo: {document_of(ctx) is not None}')
        from . import bim_dialogs
        ctx.echo(f'Ficha BIM disponible: {bim_dialogs.available(ctx)}')
    except Exception as exc:
        ctx.echo(f'ARQDIAG: {type(exc).__name__}: {exc}')
    ctx.echo('Prueba: MURO, haga dos clics separados; después PILAR, marque un centro.')

def unionesarq(ctx,*args):
    try:
        from .wall_network import RegenerateContoursCommand, sync_report
        from .compat import require_document
        from core.layers import NewLayerCommand
        doc = require_document(ctx)
        if 'ARQ-MUROS' not in doc.doc.layers:
            ctx.execute(NewLayerCommand('ARQ-MUROS', color=8))
        cmd = RegenerateContoursCommand()
        ctx.execute(cmd)
        copies, moved, groups = sync_report(cmd)
        if copies:
            ctx.echo(f'UNIONESARQ: {copies} copia(s) con identidad BIM nueva (el original conserva la suya).')
        if moved:
            ctx.echo(f'UNIONESARQ: {moved} elemento(s) con datos BIM actualizados desde la geometría CAD.')
        ctx.echo(f'UNIONESARQ: {cmd.new_count} segmentos de contorno regenerados; {groups} muro(s) seleccionables como objeto completo.')
        for issue in cmd.issues:
            if 'duplicado' not in issue:
                ctx.echo('  Aviso: ' + issue)
    except Exception as exc:
        ctx.echo(f'UNIONESARQ: {type(exc).__name__}: {exc}')

def plugin_spec() -> PluginSpec:
    from .migration import migrar_arq
    from .parameters_arq import parametros_arq, tipos_muro
    from pathlib import Path
    glyph = Path(__file__).parent / "icons"
    from .quality import validar_arq
    from .bim_export import exportar_bim
    import dataclasses
    extra = {}
    # Follow-up reactor: only on an IngeCAD that offers the hook (proposal
    # sent upstream); on older hosts the plugin works as before.
    if "reactors" in {f.name for f in dataclasses.fields(PluginSpec)}:
        from .reactor import ArquitecturaReactor
        extra["reactors"] = (ArquitecturaReactor(),)
    return PluginSpec(
        **extra,
        id="arquitectura",
        name="Arquitectura",
        version="1.10.0-dev",
        description="Dibujo arquitectónico 2D con objetos BIM (muros, pilares, carpinterías) y exportación a IngeTrazo/IFC",
        tools={tool.name: tool for tool in (*TOOL_CLASSES, Muro3DTool, Hueco3DTool)},
        commands={"EXPORTARBIM": exportar_bim, "EXPORTARIGZ": exportar_igz, "CONFIGIGZ": configurar_igz, "DIAGNOSTICOARQ": diagnostico_arq, "ARQDIAG": arqdiag, "UNIONESARQ": unionesarq, "ARQVALIDAR": validar_arq, "ARQMIGRAR": migrar_arq, "PARAMETROSARQ": parametros_arq, "TIPOSMURO": tipos_muro},
        menu=(
            MenuItem("Parámetros iniciales de Arquitectura...", "PARAMETROSARQ"),
            MenuItem("Tipos de muro (espesor total y capas)...", "TIPOSMURO"),
            MenuItem("Crear capas ARQ", "CAPASARQ"),
            MenuItem("Distribuir en capas", "CAPASAUTO"),
            SEPARATOR,
            Submenu("Construcción", (
                MenuItem("Muro 2D arquitectónico", "MURO", icon=glyph / "muro.svg"),
                MenuItem("Muro paralelo a una cara", "MUROPARALELO"),
                MenuItem("Alargar o acortar muro hasta una línea", "ESTIRAMURO"),
                MenuItem("Mover un extremo de muro", "PIVOTAMURO"),
                MenuItem("Dividir un tramo en partes iguales con muros", "DIVIDEMURO"),
                MenuItem("Borrar un tramo de muro (entre cruces)", "BORRATRAMO"),
                MenuItem("Abrir un vano en un muro (partirlo)", "PARTEMURO"),
                MenuItem("Unir dos muros alineados", "UNIRMURO"),
                MenuItem("Recinto (espacio BIM) por clic", "RECINTO"),
                MenuItem("Puerta vinculada", "PUERTAARQ", icon=glyph / "puerta.svg"),
                MenuItem("Ventana vinculada", "VENTANAARQ", icon=glyph / "ventana.svg"),
                MenuItem("Hueco (vano)", "HUECOARQ"),
                MenuItem("Carpintería (puertas, ventanas, huecos)", "CARPINTERIA"),
                MenuItem("Editar entidad arquitectónica", "EDITARARQ", icon=glyph / "editar.svg"),
                MenuItem("Propiedades BIM del elemento", "PROPIEDADESARQ", icon=glyph / "editar.svg"),
                MenuItem("Regenerar uniones de muros y pilares", "UNIONESARQ"),
                MenuItem("Diagnosticar encuentros", "DIAGNOSTICOARQ"),
                MenuItem("Validar integridad CAD y BIM", "ARQVALIDAR"),
                MenuItem("Convertir muros de versiones anteriores", "ARQMIGRAR"),
                MenuItem("Muro arquitectónico 3D", "MURO3D"),
                MenuItem("Hueco en muro 3D", "HUECO3D"),
                MenuItem("Pilar BIM", "PILAR", icon=glyph / "pilar.svg"),
                MenuItem("Puerta", "PUERTA"),
                MenuItem("Ventana", "VENTANA"),
                MenuItem("Armario", "ARMARIO"),
                MenuItem("Cámara / Eje de muro", "CAMARA"),
                MenuItem("Escalera", "ESCALERA"),
            )),
            Submenu("Dibujo y documentación", (
                MenuItem("Superficie / Área", "SUPERFICIE"),
                MenuItem("Bloque mobiliario", "BLOQUE"),
                MenuItem("Trama / Hatch", "TRAMA"),
                MenuItem("Memoria de Carpintería", "MEMORIACARP"),
                MenuItem("Vértices y coordenadas", "VERTPOLY"),
                MenuItem("Listado de textos", "LISTATEXTOS"),
            )),
            Submenu("Intercambio 3D", (
                MenuItem("Exportar modelo BIM para IngeTrazo (.arqbim)", "EXPORTARBIM", icon=glyph / "igz.svg"),
                SEPARATOR,
                MenuItem("Configurar IngeTrazo (puente antiguo)...", "CONFIGIGZ"),
                MenuItem("Exportar IGZ (puente antiguo, requiere fuentes)", "EXPORTARIGZ"),
            )),
            Submenu("Utilidades", (
                MenuItem("Selección por atributos", "SELATRIB"),
                MenuItem("Activar / Desactivar elementos", "ELEMENTOS"),
                MenuItem("Hipervínculo", "HIPERVINCULO"),
                MenuItem("Curvas de nivel a 3D", "CURVAS3D"),
            )),
            SEPARATOR,
            MenuItem("Diagnóstico del plugin", "ARQDIAG"),
            MenuItem("Ayuda Arquitectura", "AYUDAARQ"),
        ),
        toolbar=(
            ToolbarItem("Muro", "MURO", icon=glyph / "muro.svg"),
            ToolbarItem("Puerta ARQ", "PUERTAARQ", icon=glyph / "puerta.svg"),
            ToolbarItem("Ventana ARQ", "VENTANAARQ", icon=glyph / "ventana.svg"),
            ToolbarItem("Pilar", "PILAR", icon=glyph / "pilar.svg"),
            ToolbarItem("Superficie", "SUPERFICIE"),
            ToolbarItem("Selección por atributos", "SELATRIB"),
            ToolbarItem("Hipervínculo", "HIPERVINCULO"),
            ToolbarItem("Curvas 3D", "CURVAS3D"),
            ToolbarItem("Editar ARQ", "EDITARARQ", icon=glyph / "editar.svg"),
            ToolbarItem("Propiedades BIM", "PROPIEDADESARQ", icon=glyph / "editar.svg"),
            ToolbarItem("Exportar BIM", "EXPORTARBIM", icon=glyph / "igz.svg"),
            ToolbarItem("Vértices", "VERTPOLY"),
        ),
    )


PLUGIN = plugin_spec()

# SPDX-License-Identifier: GPL-3.0-or-later
"""Particiones virtuales: límites de recinto sin muro.

QUÉ ES
    Una línea sin espesor que separa dos recintos que en el edificio real no
    tienen nada físico entre ellos: la cocina abierta y el salón, el
    vestíbulo y el pasillo. No es un elemento constructivo: no tiene volumen,
    no forma encuentros con los muros y no aparece en el 3D. Solo cuenta
    para RECINTO, que la usa como borde igual que un muro.

CÓMO ESTÁ HECHA
    - En el dibujo es una polilínea abierta, en la capa ARQ-PARTICIONES-
      VIRTUALES, con línea de trazos, y lleva sus datos BIM (identidad,
      nivel) en XDATA como el resto de elementos. Su geometría es la de la
      propia polilínea: se edita con las órdenes de IngeCAD (pinzamientos,
      DESPLAZA, GIRA…) y los recintos se rehacen solos (reactor.py).
    - El reparto de un recinto se hace en geom/spaces.py
      (``split_by_partitions``): el hueco que dejan los muros se corta por
      las particiones y el recinto es la parte que contiene el punto
      designado. El área es exacta: suma de trozos, sin bandas finas.
    - Una partición que no llega de un lado a otro de la estancia no separa
      nada (como en el edificio real), y el recinto sigue siendo uno solo.

NIVELES
    La partición pertenece al nivel activo cuando se dibuja (su cota). Solo
    separa los recintos cuya cota está en su nivel: entre ``base`` y
    ``base + height``.

EXPORTACIÓN
    IFC tiene una clase para esto, IfcVirtualElement, pero el exportador de
    IngeTrazo no la admite (véase T-15 en el registro de errores). Por eso la
    partición NO viaja como elemento con geometría: va en la lista
    ``virtual_partitions`` del contrato, y cada recinto que limita la cita en
    ``params.virtual_boundaries``. Cuando IngeTrazo admita IfcVirtualElement,
    bastará con exportarla desde esa lista.

QUIÉN LO USA
    PARTICIONVIRTUAL (la orden, al final de este fichero), geom/bands
    (solve_records la cuelga del resultado de los muros), geom/spaces
    (reparto del recinto), exchange (contrato) y reactor (edición nativa).
"""
from __future__ import annotations

import math
import uuid

from tools.base import Tool

KIND = "virtual_partition"
LAYER = "ARQ-PARTICIONES-VIRTUALES"
LAYER_COLOR = 8
LINETYPE = "DASHED"
IFC_CLASS = "IfcVirtualElement"
DEFAULT_HEIGHT = 3.0            # m, si no hay niveles: separa los recintos de su cota


# --- Lectura -------------------------------------------------------------------------
def read(drawing):
    """Las particiones del dibujo: [{id, points, base, height, level, handle}].

    Los puntos se leen de la polilínea (la geometría del dibujo manda), no de
    una copia en XDATA: así una edición nativa de IngeCAD ya cuenta."""
    from .architectural import metadata
    out, seen = [], set()
    for e in drawing.modelspace():
        m = metadata(e) or {}
        if m.get("kind") != KIND or e.dxftype() != "LWPOLYLINE":
            continue
        pts = [(float(p[0]), float(p[1])) for p in e.get_points("xy")]
        pts = [p for i, p in enumerate(pts) if i == 0 or math.dist(p, pts[i - 1]) > 1e-9]
        if len(pts) < 2:
            continue
        ident = m.get("id") or e.dxf.handle
        if ident in seen:                 # una COPIA de IngeCAD: identidad provisional
            ident = f"{ident}#{e.dxf.handle}"
        seen.add(ident)
        out.append({"id": ident, "points": pts, "base": float(m.get("base", 0.0)),
                    "height": float(m.get("height", DEFAULT_HEIGHT)),
                    "level": m.get("level") or "", "handle": e.dxf.handle})
    return out


def segments_at(partitions, base):
    """Los tramos [(a, b, id)] de las particiones que separan recintos de cota ``base``."""
    out = []
    for p in partitions or ():
        if p["base"] - 1e-6 <= float(base) < p["base"] + p["height"] - 1e-6:
            out += [(a, b, p["id"]) for a, b in zip(p["points"], p["points"][1:])]
    return out


# --- Creación -------------------------------------------------------------------------
def _level_of(drawing):
    """(nombre, cota, id) del nivel activo, o el nivel por defecto."""
    from .levels import KEY, load
    if KEY not in drawing.rootdict:
        return "Planta baja", 0.0, None, DEFAULT_HEIGHT
    data = load(drawing)
    lv = next(v for v in data["levels"] if v["id"] == data["active"])
    return lv["name"], float(lv["elevation"]), lv["id"], float(lv.get("height") or DEFAULT_HEIGHT)


def _ensure_linetype(drawing):
    """La línea de trazos de IngeCAD, cargándola de su biblioteca si falta."""
    if LINETYPE in drawing.linetypes:
        return LINETYPE
    try:
        from core.linetypes import ezdxf_pattern, library
        description, dashes = library()[LINETYPE]
        drawing.linetypes.add(LINETYPE, pattern=ezdxf_pattern(dashes), description=description)
        return LINETYPE
    except Exception:  # noqa: BLE001  (otra versión de IngeCAD: línea continua)
        return "Continuous"


def create(points, name=""):
    """Orden deshacible que añade una partición virtual por ``points``."""
    from core.actions import AddEntityCommand
    from .architectural import _xdata
    from .level_layers import tagged
    pts = [(float(p[0]), float(p[1])) for p in points]
    if len(pts) < 2:
        raise ValueError("Una partición virtual necesita al menos dos puntos")
    for a, b in zip(pts, pts[1:]):
        if math.dist(a, b) < 1e-6:
            raise ValueError("Dos puntos seguidos coinciden")
    rec = {"kind": KIND, "schema": 1, "id": uuid.uuid4().hex, "ifc_class": IFC_CLASS,
           "name": name or "Partición virtual"}

    def factory(msp):
        level, base, level_id, height = _level_of(msp.doc)
        rec.update(level=level, base=base, height=height)
        if level_id:
            rec["level_id"] = level_id
        e = msp.add_lwpolyline(pts, format="xy",
                               dxfattribs={"linetype": _ensure_linetype(msp.doc)})
        return _xdata(msp, e, rec)
    return tagged(AddEntityCommand("ARQ PARTICIÓN VIRTUAL", factory, layer=LAYER), rec)


# --- Orden PARTICIONVIRTUAL ---------------------------------------------------------
class ParticionVirtualTool(Tool):
    """PARTICIONVIRTUAL: una línea sin espesor que separa dos recintos.

    Se dibuja por puntos, como una polilínea: cada clic añade un vértice e
    Intro la termina. Conviene que empiece y acabe en una cara o en el eje de
    un muro (o más allá): si queda corta, no separa nada. Al terminar, los
    recintos de los dos lados se rehacen y cada uno toma su parte."""
    name = "PARTICIONVIRTUAL"

    def start(self):
        self.name = type(self).name
        self.points = []
        self.last_point = None            # ancla de ORTO/POLAR de IngeCAD
        self.prompt("PARTICIONVIRTUAL: primer punto (en un muro o más allá):")

    def on_point(self, p):
        p = (float(p[0]), float(p[1]))
        if self.points and math.dist(p, self.points[-1]) < 1e-6:
            self.ctx.echo("Seleccione un punto distinto del anterior.")
            return
        self.points.append(p)
        self.last_point = p
        self.prompt("PARTICIONVIRTUAL: siguiente punto (Intro: terminar; Deshacer: quitar el último):"
                    if len(self.points) > 1 else "PARTICIONVIRTUAL: siguiente punto:")

    def preview_segments(self, cursor):
        pts = self.points + [tuple(cursor[:2])]
        return list(zip(pts, pts[1:])) if self.points else []

    def on_option(self, text):
        txt = str(text).strip().lower()
        if txt in ("d", "deshacer", "u") and self.points:
            self.points.pop()
            self.last_point = self.points[-1] if self.points else None
            return True
        if txt in ("f", "fin"):
            self.on_enter()
            return True
        return False

    def on_enter(self):
        if len(self.points) < 2:
            self.ctx.finish()
            return
        try:
            from .transactions import apply_architectural_change
            apply_architectural_change(self.ctx, create(self.points), kind=KIND)
        except Exception as exc:  # noqa: BLE001  (se informa y se puede repetir)
            self.ctx.echo(f"PARTICIONVIRTUAL: no se pudo crear ({type(exc).__name__}: {exc}).")
            return
        self.ctx.echo("PARTICIONVIRTUAL: creada; los recintos se han actualizado.")
        self.points, self.last_point = [], None
        self.prompt("PARTICIONVIRTUAL: primer punto de otra partición (Intro: terminar):")

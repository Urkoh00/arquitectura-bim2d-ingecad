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

SIN DEPENDENCIAS DEL ANFITRIÓN
    Este módulo no importa IngeCAD al cargarse: viaja también a la extensión
    de IngeTrazo (arq_shared), donde exchange.py lo necesita. Por eso la orden
    de usuario está en wall_tools.py.

QUIÉN LO USA
    PARTICIONVIRTUAL (la orden, en wall_tools.py), geom/bands
    (solve_records la cuelga del resultado de los muros), geom/spaces
    (reparto del recinto), exchange (contrato) y reactor (edición nativa).
"""
from __future__ import annotations

import math
import uuid


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
    z = float(lv["elevation"])
    # los niveles guardan cotas, no alturas: la del nivel es la distancia al
    # siguiente; el último toma la altura por defecto (revisión del 24-11)
    encima = [float(v["elevation"]) for v in data["levels"] if float(v["elevation"]) > z + 1e-9]
    return lv["name"], z, lv["id"], (min(encima) - z) if encima else DEFAULT_HEIGHT


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

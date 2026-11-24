# SPDX-License-Identifier: GPL-3.0-or-later
"""Defensas: barandillas, balaustradas y antepechos (petos).

QUÉ ES
    Una defensa es un elemento vertical de protección colocado a lo largo de
    una línea: el borde de una terraza, de un balcón o de un hueco de
    escalera. No es un muro de cerramiento, pero se dibuja y se comporta como
    uno: tiene espesor, altura y nivel, forma encuentros con los muros y
    cierra recintos (una terraza queda limitada por su barandilla).

CÓMO ESTÁ HECHA
    No hay un elemento nuevo en el dibujo: una defensa es un MURO con la
    categoría «defensa» (véase wall_categories.py). Así reutiliza sin copiar
    nada el motor de encuentros, la edición, los niveles, el Deshacer y la
    exportación de los muros. Este módulo solo añade lo que la distingue:

    - su tipo (barandilla, balaustrada o antepecho) y sus valores por defecto;
    - la comprobación de sus datos (no admite huecos; porcentaje de huecos);
    - su clase IFC (IfcRailing, o IfcWall PARAPET si es un antepecho macizo);
    - su volumen en 3D: un antepecho es macizo; una barandilla se construye
      con pasamanos y montantes DENTRO de la misma huella que se ve en planta,
      de modo que la planta y el 3D proceden de la misma definición;
    - el aviso del DB-SUA 1 (altura mínima de las barreras de protección).

DATOS DEL REGISTRO (además de los de un muro)
    wall_category = 'defensa'
    defense_type  = 'barandilla' | 'balaustrada' | 'antepecho'
    void_ratio    = proporción de huecos del alzado, de 0 (macizo) a 0,95

QUIÉN LO USA
    wall_tools.DefensaTool (orden DEFENSA), architectural_v10 (crear y editar),
    architectural.validate_wall (comprobación) y exchange.build (exportación).
"""
from __future__ import annotations

import math

# --- Vocabulario --------------------------------------------------------------------
# tipo -> (nombre visible, clase IFC, PredefinedType, espesor, proporción de huecos)
TYPES = {
    "barandilla":  ("Barandilla",            "IfcRailing", "GUARDRAIL",  0.05, 0.85),
    "balaustrada": ("Balaustrada",           "IfcRailing", "BALUSTRADE", 0.15, 0.50),
    "antepecho":   ("Antepecho (peto macizo)", "IfcWall",  "PARAPET",    0.15, 0.00),
}
DEFAULT_TYPE = "barandilla"
DEFAULT_HEIGHT = 1.10          # m: la altura que exige el DB-SUA 1 con desniveles > 6 m
MAX_VOID = 0.95

# Dimensiones de la barandilla en 3D (m). Son una representación: lo que se
# mide y se exporta es la huella, la altura y la proporción de huecos.
RAIL_HEIGHT = 0.05             # canto del pasamanos
POST_MIN_GAP = 0.01            # luz mínima entre montantes
FIT_TOL = 1e-6                 # m: holgura al comprobar que un montante cabe en la huella


def defense_type(record):
    """El tipo de una defensa ('barandilla' si el registro no lo dice)."""
    value = record.get("defense_type") or DEFAULT_TYPE
    if value not in TYPES:
        raise ValueError(f"Tipo de defensa no válido: {value!r}")
    return value


def void_ratio(record):
    """Proporción de huecos (0 = macizo). Un antepecho es siempre macizo."""
    kind = defense_type(record)
    if kind == "antepecho":
        return 0.0
    value = record.get("void_ratio")
    if value is None:
        value = TYPES[kind][4]
    else:
        try:
            value = float(value)
        except (TypeError, ValueError):
            # un dato que no es un número (texto o lista) llega como
            # ValueError, el error que esperan las órdenes que lo validan
            raise ValueError(f"Proporción de huecos de la defensa no numérica: {value!r}") from None
    if not (math.isfinite(value) and 0.0 <= value <= MAX_VOID):
        raise ValueError(f"Proporción de huecos de la defensa fuera de 0–{MAX_VOID:g}: {value}")
    return value


def defaults(kind=DEFAULT_TYPE):
    """Espesor, altura y proporción de huecos con que empieza la orden DEFENSA."""
    _name, _cls, _pre, thickness, voids = TYPES[kind]
    return {"thickness": thickness, "height": DEFAULT_HEIGHT, "void_ratio": voids}


def is_defense(record):
    return record.get("wall_category") == "defensa"


# --- Comprobación ----------------------------------------------------------------------
def validate(record):
    """Lo que un muro normal admite y una defensa no. Lanza ValueError."""
    if not is_defense(record):
        return
    defense_type(record)
    void_ratio(record)
    if record.get("openings"):
        raise ValueError("Una defensa no admite puertas, ventanas ni huecos")


def sua_warning(height):
    """Aviso del DB-SUA 1, apartado 3.2.1, o '' si la altura lo cumple siempre.

    Las barreras de protección miden al menos 0,90 m si la diferencia de cota
    que protegen no supera 6 m, y 1,10 m en los demás casos. El plugin no
    conoce el desnivel que hay detrás de la defensa, así que solo avisa."""
    h = float(height)
    if h < 0.90 - 1e-9:
        return (f"DB-SUA 1: una barrera de protección mide al menos 0,90 m "
                f"(1,10 m si el desnivel supera 6 m); esta mide {h:.2f} m".replace(".", ","))
    if h < 1.10 - 1e-9:
        return "DB-SUA 1: 0,90 m basta solo si el desnivel no supera 6 m; si lo supera, 1,10 m"
    return ""


# --- Exportación (IFC) ---------------------------------------------------------------
def ifc(record):
    """(clase IFC, PredefinedType) de la defensa."""
    _name, cls, predefined, _t, _v = TYPES[defense_type(record)]
    return cls, predefined


def psets(record, is_external):
    """Juegos de propiedades propios de la defensa."""
    kind = defense_type(record)
    cls, _pre = ifc(record)
    common = "Pset_RailingCommon" if cls == "IfcRailing" else "Pset_WallCommon"
    return {
        common: {"Height": float(record["height"]), "IsExternal": bool(is_external)},
        "ARQ_Defensa": {"Tipo": TYPES[kind][0], "PorcentajeHuecos": round(void_ratio(record) * 100, 1)},
    }


# --- Volumen en 3D -----------------------------------------------------------------
def _inside_convex(pt, poly, tol=1e-9):
    """``pt`` dentro (o sobre el borde) del polígono convexo antihorario ``poly``."""
    x, y = pt
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        if (b[0] - a[0]) * (y - a[1]) - (b[1] - a[1]) * (x - a[0]) < -tol:
            return False
    return True


def railing_solid(geometry, spec, base, height, voids):
    """Caras y volumen de una barandilla o balaustrada recta.

    ``geometry`` es la huella del muro ya resuelta por el motor de encuentros
    (sus ``pieces``), así que los extremos ya están recortados por los muros
    a los que llega. Dentro de esa huella se levantan:
      - el pasamanos: la huella entera en la franja superior (RAIL_HEIGHT);
      - los montantes: secciones cuadradas del espesor de la defensa, a una
        separación tal que la proporción de huecos del alzado sea ``voids``.
    Un montante solo se coloca si su sección cae entera dentro de la huella;
    el primero y el último, si no caben por un recorte, se deslizan hacia dentro.

    Devuelve (caras, volumen) como geom.solids.prism_solid. Una defensa curva
    o sin montantes que quepan se construye maciza (lo dice el aviso)."""
    from .geom import polygon as P
    from .geom import solids as S

    t = spec.thickness
    rail = min(RAIL_HEIGHT, height / 4.0)
    post_h = height - rail
    # Todo se reúne en celdas (polígono convexo, (z0, z1)) y geom.solids
    # calcula el contorno cerrado de su unión: el pasamanos y un montante que
    # se tocan forman un único sólido, sin caras ni aristas repetidas.
    # El pasamanos sigue la huella exacta, con sus encuentros:
    cells = [(P.ccw(list(pc)), (base + post_h, base + height)) for pc in geometry["pieces"]]
    # montantes: separación entre ejes s con  t / s = 1 - voids  (alzado)
    solid_share = max(1.0 - voids, 1e-6)
    spacing = max(t / solid_share, t + POST_MIN_GAP)
    mid = (spec.lo + spec.hi) / 2.0
    count = max(int(math.floor(spec.length / spacing)) + 1, 2)
    step = spec.length / (count - 1)
    pieces = [P.ccw(list(pc)) for pc in geometry["pieces"]]

    def square(s):
        return [spec.point(s - t / 2, mid - t / 2), spec.point(s + t / 2, mid - t / 2),
                spec.point(s + t / 2, mid + t / 2), spec.point(s - t / 2, mid + t / 2)]

    def fits(s):
        # la sección entera, no solo su centro: cada esquina (retranqueada
        # FIT_TOL, porque el montante ocupa todo el espesor y sus esquinas
        # caen sobre las caras) dentro de alguna pieza de la huella
        e = t / 2 - FIT_TOL
        corners = [spec.point(s + a * e, mid + b * e) for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        return all(any(_inside_convex(c, pc) for pc in pieces) for c in corners)

    for k in range(count):
        s = min(max(k * step, t / 2.0), spec.length - t / 2.0)
        if not fits(s):
            # un extremo recortado por un muro (recto o a inglete): el primer
            # y el último montante se deslizan hacia dentro hasta caber, sin
            # pasar de medio paso; los demás que no quepan no se colocan
            if k not in (0, count - 1):
                continue
            hacia = 1.0 if k == 0 else -1.0
            paso = t / 8.0
            s = next((s + hacia * paso * i for i in range(1, int(step / 2 / paso) + 1)
                      if fits(s + hacia * paso * i)), None)
            if s is None:
                continue
        cells.append((P.ccw(square(s)), (base, base + post_h)))
    cells = S._snap(cells)
    faces = S.boundary(cells)
    volume = math.fsum(P.area(poly) * (z1 - z0) for poly, (z0, z1) in cells)
    return faces, volume

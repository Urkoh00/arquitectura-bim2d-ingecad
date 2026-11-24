# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: secciones y alzados (Python puro): corta y proyecta los sólidos del
#   contrato con una cámara ortográfica horizontal y elimina las líneas ocultas.
#   (Guía del código: docs/GUIA_DEL_CODIGO.md)
"""Vistas ortográficas de los sólidos del contrato.

**Una sola geometría.** La entrada son las caras de los elementos de
``exchange.build``: las mismas que van a IngeTrazo y al IFC. Una sección o un
alzado no recalculan nada del edificio; solo proyectan esas caras, de modo que
la planta, el 3D y las vistas no pueden contradecirse.

**Cámara.** Una línea en planta de ``p`` a ``q`` y el lado hacia el que se
mira. En coordenadas de la vista, ``s`` es la distancia a lo largo de la línea
(de 0 a su longitud), ``z`` la cota y ``t`` la profundidad, positiva hacia
donde se mira. Una **sección** corta por ``t = 0`` y solo ve lo que queda
detrás; un **alzado** no corta y ve todo lo que hay en la franja de la línea.
``profundidad`` limita lo que se ve detrás.

**Líneas ocultas.** Los sólidos son cerrados, así que solo se dibujan las
aristas de las caras que miran a la cámara, y solo los tramos que no tapa
ninguna cara más cercana (ni la superficie cortada). Las caras son planas: la
diferencia de profundidad entre una arista y una cara que la tapa varía
linealmente a lo largo de la arista, así que el tramo oculto se calcula
exactamente, sin muestrear. Las aristas que separan dos caras coplanarias
contiguas (una costura, no un canto) no se dibujan.

Los puntos se identifican con la soldadura por tolerancia (``soldadura``),
nunca redondeando coordenadas.
"""
from __future__ import annotations

import math

from .soldadura import Soldador

#: clases que se ven en las vistas (los recintos y los huecos no son materia)
CLASES = frozenset({
    "IfcWall", "IfcColumn", "IfcSlab", "IfcDoor", "IfcWindow", "IfcRailing",
    "IfcBuildingElementProxy", "IfcCovering", "IfcRoof", "IfcStair", "IfcBeam",
    "IfcMember", "IfcPlate", "IfcFooting",
})
#: masas de construcción: entre dos de ellas, una junta coplanaria no se dibuja
#: (dos muros que forman un mismo paramento); entre piezas de una carpintería, sí
MASIVOS = frozenset({"IfcWall", "IfcColumn", "IfcSlab", "IfcCovering", "IfcRoof"})
EPS = 1e-7          # m: tolerancia geométrica
EPS_PROF = 1e-6     # m: una cara tapa a una arista si está más cerca que esto
CELDA = 1.0         # m: rejilla para buscar las caras que pueden tapar una arista


class Camara:
    """Cámara ortográfica horizontal (ver el resumen del módulo)."""

    def __init__(self, p, q, lado, seccion=True, profundidad=None):
        p, q, lado = (tuple(map(float, v[:2])) for v in (p, q, lado))
        largo = math.dist(p, q)
        if not largo > EPS:
            raise ValueError("La línea de la vista necesita dos puntos distintos")
        u = ((q[0] - p[0]) / largo, (q[1] - p[1]) / largo)
        d = (-u[1], u[0])
        lado_t = (lado[0] - p[0]) * d[0] + (lado[1] - p[1]) * d[1]
        if abs(lado_t) <= EPS:
            raise ValueError("Indique hacia qué lado de la línea se mira")
        if lado_t < 0:
            d = (-d[0], -d[1])
        if profundidad is not None and not (math.isfinite(profundidad) and profundidad > 0):
            raise ValueError("La profundidad debe ser positiva")
        self.p, self.u, self.d, self.largo = p, u, d, largo
        self.seccion = bool(seccion)
        self.profundidad = None if profundidad is None else float(profundidad)

    def local(self, v):
        x, y, z = float(v[0]) - self.p[0], float(v[1]) - self.p[1], float(v[2])
        return (x * self.u[0] + y * self.u[1], z, x * self.d[0] + y * self.d[1])

    def normal_local(self, anillo):
        """Normal exterior de una cara en (s, z, t). Se calcula en el sistema
        del dibujo y se proyecta: (s, z, t) no es un triedro directo, así que
        la regla de Newell aplicada en él daría la normal invertida."""
        n = _normal([tuple(map(float, v)) for v in anillo])
        if n is None:
            return None
        return (n[0] * self.u[0] + n[1] * self.u[1], n[2], n[0] * self.d[0] + n[1] * self.d[1])

    def planos(self):
        """Semiespacios ``(eje, valor, signo)`` que acotan lo visible:
        ``signo * (coord[eje] - valor) >= 0``."""
        out = [(0, 0.0, 1), (0, self.largo, -1)]
        if self.seccion:
            out.append((2, 0.0, 1))
        if self.profundidad is not None:
            out.append((2, self.profundidad, -1))
        return out


def _recortar(loop, eje, valor, signo):
    """Sutherland-Hodgman de un anillo 3D contra un semiespacio."""
    out = []
    n = len(loop)
    for i in range(n):
        a, b = loop[i], loop[(i + 1) % n]
        da, db = signo * (a[eje] - valor), signo * (b[eje] - valor)
        if da >= -EPS:
            out.append(a)
        if (da >= -EPS) != (db >= -EPS) and abs(da - db) > 1e-15:
            k = da / (da - db)
            out.append(tuple(a[j] + (b[j] - a[j]) * k for j in range(3)))
    return out


def _normal(loop):
    nx = ny = nz = 0.0
    for i in range(len(loop)):
        x0, y0, z0 = loop[i]
        x1, y1, z1 = loop[(i + 1) % len(loop)]
        nx += (y0 - y1) * (z0 + z1)
        ny += (z0 - z1) * (x0 + x1)
        nz += (x0 - x1) * (y0 + y1)
    ln = math.sqrt(nx * nx + ny * ny + nz * nz)
    return None if ln < 1e-14 else (nx / ln, ny / ln, nz / ln)


def _area2(loop):
    return 0.5 * sum(loop[i][0] * loop[(i + 1) % len(loop)][1]
                     - loop[(i + 1) % len(loop)][0] * loop[i][1] for i in range(len(loop)))


def _dentro(pt, anillos):
    """Par-impar sobre todos los anillos (el exterior y sus huecos)."""
    x, y = pt
    dentro = False
    for poly in anillos:
        n = len(poly)
        for i in range(n):
            a, b = poly[i], poly[(i + 1) % n]
            if (a[1] > y) != (b[1] > y):
                xx = a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
                if xx > x:
                    dentro = not dentro
    return dentro


class _Cara:
    """Cara que mira a la cámara, ya recortada: anillos en (s, z) y su plano."""
    __slots__ = ("elemento", "parte", "masivo", "anillos", "plano", "caja", "aristas")

    def __init__(self, elemento, anillos3, normal, parte=None, masivo=False):
        self.elemento = elemento
        self.parte = (elemento, parte)
        self.masivo = masivo
        self.anillos = [[(v[0], v[1]) for v in r] for r in anillos3]
        p0 = anillos3[0][0]
        # n·(s, z, t) = c  ->  t = (c - ns*s - nz*z) / nt
        self.plano = (normal[0], normal[1], normal[2],
                      normal[0] * p0[0] + normal[1] * p0[1] + normal[2] * p0[2])
        xs = [v[0] for r in self.anillos for v in r]
        zs = [v[1] for r in self.anillos for v in r]
        self.caja = (min(xs), min(zs), max(xs), max(zs))
        self.aristas = [(r[i], r[(i + 1) % len(r)]) for r in anillos3 for i in range(len(r))]

    def profundidad(self, s, z):
        ns, nz, nt, c = self.plano
        return (c - ns * s - nz * z) / nt


def _caras_visibles(elementos, cam):
    caras = []
    for el in elementos:
        for cara in el["faces"]:
            exterior = cara["outer"] if isinstance(cara, dict) else cara[0]
            huecos = cara.get("holes", []) if isinstance(cara, dict) else cara[1]
            anillos = [[cam.local(v) for v in r] for r in [exterior, *huecos]]
            normal = cam.normal_local(exterior)
            if normal is None or normal[2] > -1e-9:
                continue                    # de espaldas o de canto: no se ve
            recortados = []
            for indice, r in enumerate(anillos):
                for eje, valor, signo in cam.planos():
                    r = _recortar(r, eje, valor, signo)
                    if len(r) < 3:
                        break
                if len(r) >= 3 and abs(_area2([(v[0], v[1]) for v in r])) > 1e-12:
                    recortados.append(r)
                elif indice == 0:
                    break                   # sin su exterior, los huecos no forman cara
            if recortados:
                parte = cara.get("part") if isinstance(cara, dict) else None
                caras.append(_Cara(el["id"], recortados, normal, parte,
                                   el.get("ifc_class") in MASIVOS))
    return caras


# ----------------------------------------------------------------------- corte

def _corte_elemento(el, cam):
    """Segmentos (s, z) de la intersección del sólido con el plano t = 0."""
    segmentos = []
    for cara in el["faces"]:
        exterior = cara["outer"] if isinstance(cara, dict) else cara[0]
        huecos = cara.get("holes", []) if isinstance(cara, dict) else cara[1]
        anillos = [[cam.local(v) for v in r] for r in [exterior, *huecos]]
        normal = _normal(anillos[0])
        if normal is None:
            continue
        # dirección de la recta cara ∩ plano: n × (0, 0, 1)
        direc = (normal[1], -normal[0])
        if math.hypot(*direc) < 1e-9:
            continue                        # la cara está en el plano de corte
        cortes = []
        for r in anillos:
            for i in range(len(r)):
                a, b = r[i], r[(i + 1) % len(r)]
                # semiabierto: un vértice en t = 0 cuenta del lado positivo
                if (a[2] >= 0) != (b[2] >= 0):
                    k = a[2] / (a[2] - b[2])
                    cortes.append((a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k))
        if len(cortes) < 2:
            continue
        cortes.sort(key=lambda v: v[0] * direc[0] + v[1] * direc[1])
        for i in range(0, len(cortes) - 1, 2):
            a, b = cortes[i], cortes[i + 1]
            if math.dist(a, b) > EPS:
                segmentos.append((a, b))
    return segmentos


def _anillos(segmentos):
    """Encadena segmentos no orientados en anillos cerrados."""
    sold = Soldador(1e-6)
    vecinos = {}
    puntos = {}
    for a, b in segmentos:
        ia, ib = sold.indice((a[0], a[1], 0.0)), sold.indice((b[0], b[1], 0.0))
        if ia == ib:
            continue
        puntos[ia], puntos[ib] = a, b
        vecinos.setdefault(ia, []).append(ib)
        vecinos.setdefault(ib, []).append(ia)
    usados = set()
    anillos = []
    for inicio in list(vecinos):
        for siguiente in list(vecinos[inicio]):
            arista = frozenset((inicio, siguiente))
            if arista in usados:
                continue
            usados.add(arista)
            anillo, previo, actual = [inicio], inicio, siguiente
            while actual != inicio and len(anillo) < 100000:
                anillo.append(actual)
                opciones = [v for v in vecinos[actual] if frozenset((actual, v)) not in usados]
                if not opciones:
                    break
                nuevo = opciones[0]
                usados.add(frozenset((actual, nuevo)))
                previo, actual = actual, nuevo
            if actual == inicio and len(anillo) >= 3:
                poly = [puntos[i] for i in anillo]
                if abs(_area2(poly)) > 1e-12:
                    anillos.append(poly)
    return anillos


def _recortar_2d(poly, minimo, maximo):
    """Recorta un anillo (s, z) a la franja minimo <= s <= maximo."""
    r = [(v[0], v[1], 0.0) for v in poly]
    for valor, signo in ((minimo, 1), (maximo, -1)):
        r = _recortar(r, 0, valor, signo)
        if len(r) < 3:
            return []
    return [(v[0], v[1]) for v in r]


def cortes(elementos, cam):
    """[{id, clase, anillos}] de lo cortado por la sección (vacío en un alzado)."""
    if not cam.seccion:
        return []
    out = []
    for el in elementos:
        anillos = []
        for poly in _anillos(_corte_elemento(el, cam)):
            poly = _recortar_2d(poly, 0.0, cam.largo)
            if len(poly) >= 3 and abs(_area2(poly)) > 1e-10:
                anillos.append(poly)
        if anillos:
            out.append({"id": el["id"], "clase": el["ifc_class"], "anillos": anillos})
    return out


# -------------------------------------------------------------- líneas ocultas

def _rejilla(caras):
    celdas = {}
    for i, c in enumerate(caras):
        x0, z0, x1, z1 = c.caja
        for gx in range(math.floor(x0 / CELDA), math.floor(x1 / CELDA) + 1):
            for gz in range(math.floor(z0 / CELDA), math.floor(z1 / CELDA) + 1):
                celdas.setdefault((gx, gz), []).append(i)
    return celdas


def _candidatas(celdas, a, b):
    x0, x1 = sorted((a[0], b[0]))
    z0, z1 = sorted((a[1], b[1]))
    vistas = set()
    for gx in range(math.floor(x0 / CELDA), math.floor(x1 / CELDA) + 1):
        for gz in range(math.floor(z0 / CELDA), math.floor(z1 / CELDA) + 1):
            vistas.update(celdas.get((gx, gz), ()))
    return vistas


def _tramos_ocultos(a, b, tapa):
    """Intervalos de [0, 1] de la arista a→b (3D local) que tapa la cara ``tapa``."""
    x0, z0, x1, z1 = tapa.caja
    if max(a[0], b[0]) < x0 - EPS or min(a[0], b[0]) > x1 + EPS or \
            max(a[1], b[1]) < z0 - EPS or min(a[1], b[1]) > z1 + EPS:
        return []
    ds, dz = b[0] - a[0], b[1] - a[1]
    lambdas = {0.0, 1.0}
    for anillo in tapa.anillos:
        n = len(anillo)
        for i in range(n):
            p, q = anillo[i], anillo[(i + 1) % n]
            es, ez = q[0] - p[0], q[1] - p[1]
            den = ds * ez - dz * es
            if abs(den) < 1e-15:
                continue
            lam = ((p[0] - a[0]) * ez - (p[1] - a[1]) * es) / den
            mu = ((p[0] - a[0]) * dz - (p[1] - a[1]) * ds) / den
            if 0.0 < lam < 1.0 and -1e-12 <= mu <= 1.0 + 1e-12:
                lambdas.add(lam)
    # donde la arista cruza el plano de la cara cambia quién está delante
    def dif(lam):
        s, z, t = (a[j] + (b[j] - a[j]) * lam for j in range(3))
        return tapa.profundidad(s, z) - t
    d0, d1 = dif(0.0), dif(1.0)
    if (d0 < 0) != (d1 < 0) and abs(d0 - d1) > 1e-15:
        cruce = d0 / (d0 - d1)
        if 0.0 < cruce < 1.0:
            lambdas.add(cruce)
    orden = sorted(lambdas)
    ocultos = []
    for l0, l1 in zip(orden, orden[1:]):
        if l1 - l0 < 1e-12:
            continue
        m = 0.5 * (l0 + l1)
        punto = (a[0] + ds * m, a[1] + dz * m)
        if dif(m) < -EPS_PROF and _dentro(punto, tapa.anillos):
            ocultos.append((l0, l1))
    return ocultos


def _union(intervalos):
    out = []
    for i0, i1 in sorted(intervalos):
        if out and i0 <= out[-1][1] + 1e-12:
            out[-1] = (out[-1][0], max(out[-1][1], i1))
        else:
            out.append((i0, i1))
    return out


def _mismo_plano(p, q):
    return all(abs(p[i] - q[i]) <= 1e-6 for i in range(4))


def _costura(a, b, cara, otra):
    """Intervalos de la arista a→b de ``cara`` que son junta con ``otra``:
    caras coplanarias, a ambos lados de la arista, con una arista colineal
    que la solapa. Una junta no es un canto y no se dibuja."""
    if not _mismo_plano(cara.plano, otra.plano):
        return []
    if not (cara.parte == otra.parte or (cara.masivo and otra.masivo)):
        return []
    ds, dz = b[0] - a[0], b[1] - a[1]
    largo2 = ds * ds + dz * dz
    if largo2 <= EPS * EPS:
        return []
    out = []
    for p, q in otra.aristas:
        # colineal: los dos extremos de la otra arista sobre la recta a→b
        if abs((p[0] - a[0]) * dz - (p[1] - a[1]) * ds) > 1e-6 * math.sqrt(largo2) or \
                abs((q[0] - a[0]) * dz - (q[1] - a[1]) * ds) > 1e-6 * math.sqrt(largo2):
            continue
        l0 = ((p[0] - a[0]) * ds + (p[1] - a[1]) * dz) / largo2
        l1 = ((q[0] - a[0]) * ds + (q[1] - a[1]) * dz) / largo2
        l0, l1 = max(0.0, min(l0, l1)), min(1.0, max(l0, l1))
        if l1 - l0 <= 1e-9:
            continue
        # a lados opuestos: la sonda del lado que no es de «cara» cae en «otra»
        m = 0.5 * (l0 + l1)
        punto = (a[0] + ds * m, a[1] + dz * m)
        normal = (-dz / math.sqrt(largo2), ds / math.sqrt(largo2))
        sonda = 1e-5
        izquierda = (punto[0] + normal[0] * sonda, punto[1] + normal[1] * sonda)
        derecha = (punto[0] - normal[0] * sonda, punto[1] - normal[1] * sonda)
        fuera = derecha if _dentro(izquierda, cara.anillos) else izquierda
        if _dentro(fuera, otra.anillos):
            out.append((l0, l1))
    return out


def vistos(elementos, cam, cortados=()):
    """Segmentos visibles ``[((s0, z0), (s1, z1), id)]`` tras eliminar las
    líneas ocultas. ``cortados`` (de ``cortes``) tapan lo que queda detrás."""
    caras = _caras_visibles(elementos, cam)
    for c in cortados:
        # la superficie cortada es una cara en t = 0 que mira a la cámara
        anillos = [[(v[0], v[1], 0.0) for v in r] for r in c["anillos"]]
        caras.append(_Cara(c["id"], anillos, (0.0, 0.0, -1.0)))
    n_reales = len(caras) - len(cortados)
    celdas = _rejilla(caras)
    out = []
    for i in range(n_reales):
        cara = caras[i]
        for a, b in cara.aristas:
            if math.dist(a, b) <= EPS:
                continue
            if cam.seccion and abs(a[2]) <= EPS and abs(b[2]) <= EPS:
                continue                    # en el plano de corte: es contorno cortado
            if all(abs(v[0]) <= EPS for v in (a, b)) or \
                    all(abs(v[0] - cam.largo) <= EPS for v in (a, b)):
                continue                    # borde artificial del recorte lateral
            ocultos = []
            for j in _candidatas(celdas, a, b):
                if j == i:
                    continue
                ocultos.extend(_tramos_ocultos(a, b, caras[j]))
                if j < n_reales:
                    ocultos.extend(_costura(a, b, cara, caras[j]))
            libre = 0.0
            for l0, l1 in _union(ocultos) + [(1.0, 1.0)]:
                if l0 - libre > 1e-9:
                    p0 = (a[0] + (b[0] - a[0]) * libre, a[1] + (b[1] - a[1]) * libre)
                    p1 = (a[0] + (b[0] - a[0]) * l0, a[1] + (b[1] - a[1]) * l0)
                    if math.dist(p0, p1) > 1e-6:
                        out.append((p0, p1, cara.elemento))
                libre = max(libre, l1)
    return _sin_duplicados(out)


def _sin_duplicados(segmentos):
    """Une los segmentos colineales que se solapan: una arista vista desde
    dos caras, o un canto que otro elemento prolonga, se dibuja una sola vez.
    Las rectas se agrupan con la soldadura por tolerancia (ángulo y distancia
    al origen), nunca redondeando."""
    sold = Soldador(1e-7)
    rectas = {}
    for a, b, ident in segmentos:
        ds, dz = b[0] - a[0], b[1] - a[1]
        ang = math.atan2(dz, ds)
        if ang < 0:
            ang += math.pi
        if ang >= math.pi - 1e-9:
            ang -= math.pi
        u = (math.cos(ang), math.sin(ang))
        dist = a[1] * u[0] - a[0] * u[1]          # distancia firmada al origen
        k = sold.indice((ang, dist, 0.0))
        t0 = a[0] * u[0] + a[1] * u[1]
        t1 = b[0] * u[0] + b[1] * u[1]
        rectas.setdefault(k, (u, dist, []))[2].append((min(t0, t1), max(t0, t1), ident))
    return _puntos(rectas)


def _puntos(rectas):
    out = []
    for u, dist, tramos in rectas.values():
        n = (-u[1], u[0])
        tramos.sort()
        actual = None
        unidos = []
        for t0, t1, ident in tramos:
            if actual and t0 <= actual[1] + 1e-9:
                actual[1] = max(actual[1], t1)
            else:
                if actual:
                    unidos.append(actual)
                actual = [t0, t1, ident]
        if actual:
            unidos.append(actual)
        for t0, t1, ident in unidos:
            if t1 - t0 <= 1e-6:
                continue
            base = (n[0] * dist, n[1] * dist)
            out.append(((base[0] + u[0] * t0, base[1] + u[1] * t0),
                        (base[0] + u[0] * t1, base[1] + u[1] * t1), ident))
    return out


def vista(elementos, cam):
    """{'cortes': [...], 'vistos': [...], 'largo', 'cotas'}: la vista completa."""
    elementos = [e for e in elementos if e.get("ifc_class") in CLASES and e.get("faces")]
    cortados = cortes(elementos, cam)
    segs = vistos(elementos, cam, cortados)
    zs = [v[1] for c in cortados for r in c["anillos"] for v in r] + \
         [v[1] for a, b, _ in segs for v in (a, b)]
    return {"cortes": cortados, "vistos": segs, "largo": cam.largo,
            "cotas": (min(zs), max(zs)) if zs else (0.0, 0.0)}

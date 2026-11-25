# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: Recintos: el hueco que dejan los muros alrededor de un punto, su reparto por particiones
#   virtuales y los muros exteriores del edificio.
#   (Guía del código: docs/GUIA_DEL_CODIGO.md)
"""Spaces (rooms) from the junction engine's footprints.

The footprints of walls and columns tile without overlaps (junctions.solve).
Their union is one or more components; each HOLE of a component is a room,
closed by the very faces of the walls around it (doors do not open a room:
openings cut the 3D wall, not its footprint). Islands (a free-standing
column, an inner core) are the other components lying inside a hole.

A space is identified by a SEED point the user clicked inside the room, so
it is associative: when walls move, the space is recomputed from its seed.
Pure Python, no dependencies; the same polygons feed the plan and the IFC.
"""
from __future__ import annotations

import math

from . import polygon as P


def _all_pieces(result):
    pieces = [pc for g in result.walls.values() for pc in g["pieces"]]
    for poly in result.columns.values():
        pieces.extend(P.convex_parts(poly))
    return pieces


def network_at(result, base):
    networks=getattr(result,'vertical_networks',None)
    if networks is None:return result
    for (lo,hi),part in networks:
        if lo-1e-9<=float(base)<hi-1e-9:return part
    from .junctions import Result
    return Result()


def components(result):
    """[(outer_ccw, [holes_cw])] of the union of every footprint.

    Kept on the result: a result is final once solved, and every room of a
    plan asks for the same union (with a hundred rooms the union was
    recomputed a hundred times per change, two to three seconds a wall).
    Callers only read it."""
    cached = getattr(result, "_components", None)
    if cached is not None:
        return cached
    comps = P.merge(_all_pieces(result))
    try:
        result._components = comps
    except AttributeError:
        pass
    return comps


def _inside(pt, poly):
    return P.point_in_polygon(pt, poly)


def _perimeter(loop):
    return sum(math.dist(a, b) for a, b in zip(loop, loop[1:] + loop[:1]))


def space_at(result, seed, comps=None, partitions=()):
    """The room containing ``seed``: a dict with ``outer`` (ccw), ``holes``
    (islands, cw), ``pieces`` (convex, for solids), ``area`` and
    ``perimeter``; or ``(None, reason)`` with reason "muro" (the seed lies
    inside a wall or column) or "abierto" (it is not enclosed).

    ``partitions``: tramos [(a, b, id)] de particiones virtuales (v1.29). El
    hueco que dejan los muros se reparte por ellas y el recinto es la parte
    que contiene ``seed`` (split_by_partitions). Sin particiones, el
    resultado es exactamente el de siempre."""
    room, why = _space_at(result, seed, comps)
    if room is None or not partitions:
        return room, why
    return split_by_partitions(room, seed, partitions), ""


def _space_at(result, seed, comps=None):
    comps = comps if comps is not None else components(result)
    seed = (float(seed[0]), float(seed[1]))
    for outer, holes in comps:
        if _inside(seed, outer) and not any(_inside(seed, h) for h in holes):
            return None, "muro"
    best = None
    for outer, holes in comps:
        for h in holes:
            if _inside(seed, h):
                a = abs(P.area(h))
                if best is None or a < best[0]:          # the innermost hole
                    best = (a, h)
    if best is None:
        return None, "abierto"
    room = P.ccw(list(best[1]))
    islands = [o for o, _hs in comps if o is not room and _inside(P._interior_probe(o), room)
               and abs(P.area(o)) < abs(P.area(room))]
    pieces = P.convex_parts(room)
    for isl in islands:
        pieces = P.subtract(pieces, isl)
    area = sum(P.area(x) for x in pieces)
    holes = [list(reversed(P.ccw(list(i)))) for i in islands]
    return {"outer": room, "holes": holes, "pieces": pieces, "area": area,
            "perimeter": _perimeter(room) + sum(_perimeter(h) for h in holes)}, ""


def external_walls(result, outline=None, tol=1e-7, *, exteriores=(), con_lados=False):
    """Muros expuestos; con_lados devuelve su lado, o None si ambos lo están.

    El contorno exterior del edificio incluye sus recintos interiores para
    no confundir una partición aislada con una fachada. Los patios y porches
    declarados se reciben como regiones exteriores, con sus posibles islas.
    Un muro abierto puede tener dos caras expuestas: no se elige una al azar.
    """
    from .junctions import plan_outline
    from .soldadura import TOLERANCIA

    contornos = components(result)
    envolventes = []
    for anillo, _huecos in contornos:
        contenido = any(
            abs(P.area(otro)) > abs(P.area(anillo))
            and all(_inside(punto, otro) for punto in anillo)
            for otro, _islas in contornos
        )
        if not contenido:
            envolventes.append(anillo)
    piezas = _all_pieces(result)
    paso = max(tol, TOLERANCIA) * 4

    def expuesto(punto):
        # La sonda debe estar en aire, no dentro del material de otro muro.
        if any(_inside(punto, pieza) for pieza in piezas):
            return False
        if not any(_inside(punto, anillo) for anillo in envolventes):
            return True
        return any(
            _inside(punto, region['outer'])
            and not any(_inside(punto, isla) for isla in region.get('holes', ()))
            for region in exteriores
        )

    lados = {}
    especificaciones = getattr(result, 'specs', {})
    segmentos = outline if outline is not None else plan_outline(result)
    for inicio, fin, propietarios in segmentos:
        medio = ((inicio[0] + fin[0]) / 2, (inicio[1] + fin[1]) / 2)
        for identificador in propietarios:
            muro = especificaciones.get(identificador)
            if muro is None:
                continue
            estacion, desplazamiento = muro.local(medio)
            estacion_inicial = muro.local(inicio)[0]
            estacion_final = muro.local(fin)[0]
            if abs(estacion_final - estacion_inicial) <= tol:
                continue
            lado = 'izquierda' if desplazamiento > (muro.lo + muro.hi) / 2 else 'derecha'
            signo = 1 if lado == 'izquierda' else -1
            tangente = muro.tangent(estacion)
            sonda = (medio[0] - signo * tangente[1] * paso,
                     medio[1] + signo * tangente[0] * paso)
            if expuesto(sonda):
                lados.setdefault(identificador, set()).add(lado)
    if con_lados:
        return {identificador: next(iter(opciones)) if len(opciones) == 1 else None
                for identificador, opciones in lados.items()}
    return set(lados)


def _on_segment(m, p, q, tol):
    d = P.sub(q, p)
    L2 = P.dot(d, d)
    if L2 == 0:
        return math.dist(m, p) <= tol
    t = P.dot(P.sub(m, p), d) / L2
    if t < -1e-9 or t > 1 + 1e-9:
        return False
    return abs(P.cross(d, P.sub(m, p))) / math.sqrt(L2) <= tol


# --- Particiones virtuales (v1.29) -----------------------------------------------------
# El recinto que dejan los muros se reparte por las particiones virtuales:
#   1. cada trozo convexo del recinto se corta por la recta de cada partición
#      que pasa por él (un corte de más no importa: el paso 2 lo deshace);
#   2. dos celdas vecinas siguen unidas salvo que una partición cubra ENTERO
#      el lado que comparten;
#   3. el recinto son las celdas a las que se llega desde el punto designado.
# El área es la suma exacta de las celdas: no hay bandas finas ni tolerancias
# de área. Una partición que no cruza la estancia de lado a lado deja todas
# las celdas unidas, y el recinto sale igual que sin ella.

_ON_LINE = 1e-7          # m: un punto a esta distancia está sobre la línea


def _clip_segment(a, b, poly):
    """Parte del segmento a–b dentro del polígono convexo ``poly`` (ccw), o None."""
    t0, t1 = 0.0, 1.0
    d = P.sub(b, a)
    n = len(poly)
    for i in range(n):
        q, r = poly[i], poly[(i + 1) % n]
        e = P.sub(r, q)
        num = P.cross(e, P.sub(a, q))        # > 0: a a la izquierda (dentro)
        den = P.cross(e, d)
        if abs(den) < 1e-15:
            if num < 0:
                return None
            continue
        t = -num / den
        if den > 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return None
    if (t1 - t0) * math.hypot(*d) <= _ON_LINE:
        return None
    return t0, t1


def _cut_cells(cells, segments):
    """Corta las celdas convexas por la recta de cada tramo que las atraviesa."""
    for a, b, _ident in segments:
        d = P.sub(b, a)
        if math.hypot(*d) < 1e-9:
            continue
        nxt = []
        for c in cells:
            side = [P.cross(d, P.sub(q, a)) for q in c]
            scale = math.hypot(*d) * _ON_LINE
            straddles = max(side) > scale and min(side) < -scale
            if straddles and _clip_segment(a, b, c) is not None:
                left = P.clip_halfplane(c, a, d)
                right = P.clip_halfplane(c, a, (-d[0], -d[1]))
                nxt += [x for x in (left, right) if x]
            else:
                nxt.append(c)
        cells = nxt
    return cells


def _shared(ci, cj):
    """Lados comunes de dos celdas: [(p, q)] donde coinciden (en sentidos opuestos)."""
    out = []
    for i in range(len(ci)):
        a, b = ci[i], ci[(i + 1) % len(ci)]
        d = P.sub(b, a)
        L = math.hypot(*d)
        if L < 1e-12:
            continue
        u = (d[0] / L, d[1] / L)
        for j in range(len(cj)):
            c, e = cj[j], cj[(j + 1) % len(cj)]
            if abs(P.cross(u, P.sub(c, a))) > _ON_LINE or abs(P.cross(u, P.sub(e, a))) > _ON_LINE:
                continue
            s0, s1 = sorted((P.dot(P.sub(c, a), u), P.dot(P.sub(e, a), u)))
            lo, hi = max(0.0, s0), min(L, s1)
            if hi - lo > _ON_LINE:
                out.append(((a[0] + u[0] * lo, a[1] + u[1] * lo), (a[0] + u[0] * hi, a[1] + u[1] * hi)))
    return out


def _covered(p, q, segments):
    """(cubierto, ids): si los tramos de partición tapan entero el lado p–q."""
    d = P.sub(q, p)
    L = math.hypot(*d)
    u = (d[0] / L, d[1] / L)
    spans, ids = [], set()
    for a, b, ident in segments:
        if abs(P.cross(u, P.sub(a, p))) > _ON_LINE or abs(P.cross(u, P.sub(b, p))) > _ON_LINE:
            continue
        s0, s1 = sorted((P.dot(P.sub(a, p), u), P.dot(P.sub(b, p), u)))
        if s1 > _ON_LINE and s0 < L - _ON_LINE:
            spans.append((max(0.0, s0), min(L, s1)))
            ids.add(ident)
    reach = 0.0
    for s0, s1 in sorted(spans):
        if s0 > reach + _ON_LINE:
            return False, ids
        reach = max(reach, s1)
    return reach >= L - _ON_LINE, ids


def split_by_partitions(room, seed, segments):
    """El recinto ``room`` (de space_at) recortado por las particiones virtuales.

    Devuelve ``room`` tal cual si ninguna partición lo divide; si no, un
    recinto nuevo con las mismas claves y ``virtual_boundaries`` (los ids de
    las particiones que lo limitan)."""
    box = P.bbox(room["pieces"])
    near = [s for s in segments
            if not (max(s[0][0], s[1][0]) < box[0] - _ON_LINE or min(s[0][0], s[1][0]) > box[2] + _ON_LINE
                    or max(s[0][1], s[1][1]) < box[1] - _ON_LINE or min(s[0][1], s[1][1]) > box[3] + _ON_LINE)]
    if not near:
        return room
    cells = _cut_cells([P.ccw(list(c)) for c in room["pieces"]], near)
    if len(cells) <= len(room["pieces"]):
        return room
    seed = (float(seed[0]), float(seed[1]))
    start = next((k for k, c in enumerate(cells) if _inside(seed, c)), None)
    if start is None:                     # el punto cae sobre una partición
        start = min(range(len(cells)),
                    key=lambda k: math.dist(seed, P.mul(P.add(cells[k][0], cells[k][len(cells[k]) // 2]), 0.5)))
    reached, frontier, bounds = {start}, [start], set()
    boxes = [P.bbox([c]) for c in cells]
    while frontier:
        i = frontier.pop()
        for j in range(len(cells)):
            if j in reached or P.boxes_apart(boxes[i], boxes[j], 1e-6):
                continue
            if any(not _covered(p, q, near)[0] for p, q in _shared(cells[i], cells[j])):
                reached.add(j)
                frontier.append(j)
    if len(reached) == len(cells):
        return room                          # ninguna partición cierra: un solo recinto
    # las particiones que separan lo alcanzado de lo demás son sus límites
    for i in reached:
        for j in range(len(cells)):
            if j not in reached and not P.boxes_apart(boxes[i], boxes[j], 1e-6):
                for p, q in _shared(cells[i], cells[j]):
                    bounds |= _covered(p, q, near)[1]
    pieces = [cells[k] for k in sorted(reached)]
    comps = P.merge(pieces)
    outer, holes = max(comps, key=lambda c: P.area(c[0]))
    area = math.fsum(P.area(c) for c in pieces)
    return {"outer": outer, "holes": holes, "pieces": pieces, "area": area,
            "perimeter": _perimeter(outer) + sum(_perimeter(h) for h in holes),
            "virtual_boundaries": sorted(x for x in bounds if x)}

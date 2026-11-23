# SPDX-License-Identifier: GPL-3.0-or-later
"""Muros curvos, segunda parte: más de media circunferencia, esquina en L contra un
muro curvo, paralela a un arco, DIVIDEMURO sobre un arco y alargar hasta caras curvas.

Solo usa el motor geométrico (Python puro): no necesita shapely, IngeCAD ni pantalla.
"""
import math
import random
from contextlib import contextmanager

from arquitectura.geom import curved_drafting as CD
from arquitectura.geom import curves as CV
from arquitectura.geom import drafting as D
from arquitectura.geom import junctions as J
from arquitectura.geom import solids as S
from arquitectura.geom import spaces as SP


# --- utilidades ----------------------------------------------------------------------------------

@contextmanager
def raises(exc):
    try:
        yield
    except exc:
        return
    raise AssertionError(f"debía lanzar {exc.__name__}")


def close(a, b, rel=1e-6, abs_=1e-9):
    return abs(a - b) <= max(abs_, rel * max(abs(a), abs(b)))


def deg(d):
    return math.tan(math.radians(d) / 4.0)


def pt(c, r, d):
    return (c[0] + r * math.cos(math.radians(d)), c[1] + r * math.sin(math.radians(d)))


def inside(p, poly):
    x, y = p
    c, n = False, len(poly)
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


def overlap_and_area(result, bbox, step=0.02):
    """(área cubierta por más de una pieza, área cubierta) muestreando una rejilla."""
    polys = [pc for g in result.walls.values() for pc in g["pieces"]]
    x0, y0, x1, y1 = bbox
    multi = tot = 0
    y = y0
    while y < y1:
        x = x0
        while x < x1:
            k = sum(1 for pc in polys if inside((x, y), pc))
            multi += k > 1
            tot += k >= 1
            x += step
        y += step
    return multi * step * step, tot * step * step


def edge_counts(faces):
    c = {}
    k = lambda v: tuple(round(x, 9) for x in v)  # noqa: E731
    for o, hs in faces:
        for ring in (o, *hs):
            for i in range(len(ring)):
                a, b = k(ring[i]), k(ring[(i + 1) % len(ring)])
                c[(a, b)] = c.get((a, b), 0) + 1
    return c


def watertight(faces):
    c = edge_counts(faces)
    return all(n == 1 and c.get((b, a)) == 1 for (a, b), n in c.items())


def check_solids(result, walls, height=2.7):
    for w in walls:
        faces, vol = S.wall_solid(result.walls[w.id]["pieces"], w.a, w.u, 0.0, height)
        assert watertight(faces), w.id
        assert close(vol, result.walls[w.id]["area"] * height, 1e-9), w.id


# --- 1. más de media circunferencia ---------------------------------------------------------------

def test_el_limite_es_350_grados_y_no_180():
    assert close(math.degrees(CV.MAX_SWEEP), 350.0)
    J.Wall("x", pt((0, 0), 2, 0), pt((0, 0), 2, 270), 0.3, bulge=deg(270))
    J.Wall("x", pt((0, 0), 2, 0), pt((0, 0), 2, 350), 0.3, bulge=deg(349.9))
    with raises(ValueError):
        J.Wall("x", pt((0, 0), 2, 0), pt((0, 0), 2, 355), 0.3, bulge=deg(355))


def test_punto_de_paso_da_el_arco_mayor():
    a, b = pt((0, 0), 2, 45), pt((0, 0), 2, 315)       # el arco de 270° pasa por (-2, 0)
    assert close(CV.bulge_through(a, b, (-2, 0)), deg(270), 1e-9)
    assert close(CV.bulge_through(a, b, (2, 0)), -deg(90), 1e-9)        # el otro lado: 90° al revés
    c, r, _t0, sweep = CV.arc_of(a, b, deg(270))
    assert math.dist(c, (0, 0)) < 1e-9 and close(r, 2.0) and close(math.degrees(sweep), 270.0)


def test_arco_de_270_huella_area_y_3d():
    w = J.Wall("c", (0, 0), (2, 2), 0.2, bulge=deg(270))
    r = J.solve([w])
    assert not r.warnings
    anillo = 270 / 360 * math.pi * ((w.r + 0.1) ** 2 - (w.r - 0.1) ** 2)
    assert close(r.walls["c"]["area"], anillo, 3e-3)                    # cuerdas de ≤ 1 mm
    check_solids(r, [w])


def test_circulo_con_dos_muros_300_y_60():
    c = (0, 0)
    w1 = J.Wall("a", pt(c, 2, 0), pt(c, 2, 300), 0.3, bulge=deg(300))
    w2 = J.Wall("b", pt(c, 2, 300), pt(c, 2, 360), 0.3, bulge=deg(60))
    r = J.solve([w1, w2])
    assert not r.warnings and [n["degree"] for n in r.nodes] == [2, 2]
    multi, tot = overlap_and_area(r, (-2.4, -2.4, 2.4, 2.4))
    anillo = math.pi * (2.15 ** 2 - 1.85 ** 2)
    assert multi == 0.0 and close(tot, anillo, 2e-3)
    check_solids(r, [w1, w2])


def test_recinto_cerrado_por_arco_de_340():
    c = (0, 0)
    arco = J.Wall("w", pt(c, 2, 10), pt(c, 2, 350), 0.3, bulge=deg(340))
    cierre = J.Wall("c", pt(c, 2, 350), pt(c, 2, 10), 0.3)
    r = J.solve([arco, cierre])
    assert not r.warnings
    room, why = SP.space_at(r, (0, 0))
    assert not why and 10.0 < room["area"] < math.pi * 1.85 ** 2
    check_solids(r, [arco, cierre])


def test_T_contra_la_parte_mayor_de_un_arco():
    c = (0, 0)
    arco = J.Wall("arc", pt(c, 2, 45), pt(c, 2, 315), 0.3, bulge=deg(270))
    t = J.Wall("t", pt(c, 3.5, 180), pt(c, 2.1, 180), 0.2)
    r = J.solve([arco, t])
    assert not r.warnings and len(r.tees) == 1
    multi, _tot = overlap_and_area(r, (-4.0, -2.4, 2.4, 2.4))
    assert multi == 0.0
    check_solids(r, [arco, t])


def test_los_arcos_del_plano_de_mas_de_180_grados():
    w = J.Wall("c", (0, 0), (2, 2), 0.2, bulge=deg(270))
    items = [it for it in J.plan_items(J.solve([w])) if it[0] == "arc"]
    assert sorted(round(it[2], 6) for it in items) == [round(w.r - 0.1, 6), round(w.r + 0.1, 6)]
    for it in items:
        ang = (it[4] - it[3]) % 360.0
        assert abs(ang - 270.0) < 1.0, ang            # un solo arco de 270°, no dos medios


def test_sub_wall_hasta_350():
    w = J.Wall("c", pt((0, 0), 2, 0), pt((0, 0), 2, 180), 0.3, bulge=deg(180))
    a, b, bulge = CD.sub_wall_of_spec(w, -w.r * math.radians(60), w.length)      # alargado a 240°
    assert close(4 * math.degrees(math.atan(bulge)), 240.0, 1e-9)
    with raises(ValueError):
        CD.sub_wall_of_spec(w, -w.r * math.radians(200), w.length)               # 380°


# --- 2. esquina en L contra un muro curvo -----------------------------------------------------------

def _cuarto():
    """Cuarto de círculo de radio 3 (de 0° a 90°), grosor 0,3, eje."""
    return J.Wall("h", pt((0, 0), 3, 0), pt((0, 0), 3, 90), 0.3, bulge=deg(90))


def test_cara_cercana_de_un_muro_curvo_es_T():
    h = _cuarto()
    start, end = (4.5, 1.5), (2.0, 1.5)
    hits = CD.face_at({"h": h}, pt((0, 0), 3.15, math.degrees(math.asin(1.5 / 3.15))), 1e-3)
    assert len(hits) == 1 and hits[0][0] == "h"
    near = "hi" if h.local(start)[1] > 0 else "lo"
    assert CD.end_gesture(start, end, 0.2, "eje", h, near) == {"kind": "T"}


def test_L_recorta_el_arco_y_las_huellas_encajan():
    h = _cuarto()
    start, end = (4.5, 1.5), (2.0, 1.5)
    far = "lo" if h.local(start)[1] > 0 else "hi"               # la cara por la que NO se entra
    g = CD.end_gesture(start, end, 0.2, "eje", h, far)
    assert g["kind"] == "L"
    corner = g["new_end"]
    # el eje del muro nuevo corta el eje del arco (radio 3 por ser el eje)
    assert close(math.dist(corner, (0, 0)), 3.0, 1e-9)
    nuevo = J.Wall("n", start, g["new_end"], 0.2, "eje")
    recortado = J.Wall("h", g["host_a"], g["host_b"], 0.3, "eje", bulge=g["host_bulge"])
    assert recortado.length < h.length and g["kept"] in ("start", "end")
    r = J.solve([recortado, nuevo])
    assert not r.warnings and [n["degree"] for n in r.nodes] == [2]
    multi, _tot = overlap_and_area(r, (-0.5, -0.5, 5.0, 3.5))
    assert multi == 0.0
    check_solids(r, [recortado, nuevo])


def test_L_conserva_la_parte_mas_larga():
    h = _cuarto()
    start = (4.5, 0.6)                                    # corta cerca del extremo de 0°: lo largo queda hacia 90°
    far = "lo" if h.local(start)[1] > 0 else "hi"
    g = CD.end_gesture(start, (2.0, 0.6), 0.2, "eje", h, far)
    assert g["kind"] == "L" and g["kept"] == "end"
    assert math.dist(g["host_b"], pt((0, 0), 3, 90)) < 1e-9


def test_L_fuera_de_los_extremos_o_paralelo_no_hace_L():
    h = _cuarto()
    start = (4.5, -1.0)                                   # el eje cruza la circunferencia FUERA del arco (y<0)
    far = "lo" if h.local(start)[1] > 0 else "hi"
    g = CD.end_gesture(start, (2.0, -1.0), 0.2, "eje", h, far)
    assert g["kind"] == "T"
    # tangente: muro que roza el arco
    with raises(ValueError):
        CD.end_gesture((3.0, -1.0), (3.0, 2.0), 0.2, "eje", h, "lo" if h.local((3.0, -1.0))[1] > 0 else "hi")


def test_L_contra_arco_de_mas_de_180():
    arco = J.Wall("big", pt((0, 0), 3, 20), pt((0, 0), 3, 340), 0.3, bulge=deg(320))
    start = (-5.0, 0.0)                                    # viene de fuera hacia el centro por el lado de 180°
    far = "lo" if arco.local(start)[1] > 0 else "hi"
    g = CD.end_gesture(start, (-1.0, 0.0), 0.2, "eje", arco, far)
    assert g["kind"] == "L" and abs(g["cut_at"] - arco.length / 2) < 1e-6
    # al cortar por la mitad queda cada mitad de 160°: se conserva una
    rec = J.Wall("big", g["host_a"], g["host_b"], 0.3, "eje", bulge=g["host_bulge"])
    assert close(rec.length, arco.length / 2, 1e-6)


# --- 3. alargar hasta cualquier cara; equivalencia con el caso recto --------------------------------

def test_alargar_a_caras_rectas_da_lo_mismo_que_el_motor_antiguo():
    rnd = random.Random(7)
    for _ in range(200):
        walls = {}
        specs = {}
        for i in range(rnd.randint(1, 4)):
            a = (rnd.uniform(-5, 5), rnd.uniform(-5, 5))
            b = (a[0] + rnd.uniform(-4, 4), a[1] + rnd.uniform(-4, 4))
            if math.dist(a, b) < 0.5:
                continue
            t = rnd.choice([0.1, 0.2, 0.3])
            ref = rnd.choice(["eje", "izquierda", "derecha"])
            walls[str(i)] = (a, b, t, ref)
            specs[str(i)] = J.Wall(str(i), a, b, t, ref)
        a = (rnd.uniform(-5, 5), rnd.uniform(-5, 5))
        b = (a[0] + rnd.uniform(-3, 3), a[1] + rnd.uniform(-3, 3))
        if math.dist(a, b) < 0.5:
            continue
        try:
            old = D.extend_to_faces(a, b, walls, 1.5)
        except ValueError:
            old = None
        try:
            new = CD.extend_line_to_faces(a, b, specs, 1.5)
        except ValueError:
            new = None
        assert (old is None) == (new is None)
        if old:
            assert math.dist(old[0], new[0]) < 1e-7 and math.dist(old[1], new[1]) < 1e-7


def test_alargar_una_recta_hasta_la_cara_de_un_muro_curvo():
    h = _cuarto()
    a, b = (4.5, 1.0), (3.4, 1.0)                         # le falta llegar a la cara exterior (r = 3,15)
    na, nb = CD.extend_line_to_faces(a, b, {"h": h}, 1.0)
    assert na == a and close(math.dist(nb, (0, 0)), 3.15, 1e-9) and close(nb[1], 1.0, 1e-12)


# --- 4. MUROPARALELO sobre un arco ----------------------------------------------------------------------

def test_paralela_desde_un_muro_curvo_fuera_y_dentro():
    h = _cuarto()
    base = CD.base_from_wall(h, pt((0, 0), 3.14, 45))            # cara exterior (r = 3.15)
    assert close(base["r"], 3.15, 1e-9)
    (a, b, bulge, ref), = CD.parallel_arcs(base, 1.0, pt((0, 0), 5, 45), pt((0, 0), 5, 45))
    w = J.Wall("p", a, b, 0.2, ref, bulge=bulge)
    assert close(w.r, 4.15, 1e-9) and close(w.sweep, h.sweep, 1e-12)
    assert ref == "derecha"                      # CCW y cuerpo hacia fuera = a la derecha
    # el cuerpo está de verdad hacia fuera de la línea de referencia (4,15 → 4,35)
    assert w.lo == -0.2 and w.hi == 0.0
    pm = w.point(w.length / 2, (w.lo + w.hi) / 2)
    assert close(math.dist(pm, (0, 0)), 4.25, 1e-9)
    (a, b, bulge, ref), = CD.parallel_arcs(base, 1.0, pt((0, 0), 1, 45), pt((0, 0), 1, 45))
    w = J.Wall("p", a, b, 0.2, ref, bulge=bulge)
    assert close(w.r, 2.15, 1e-9) and ref == "izquierda"
    pm = w.point(w.length / 2, (w.lo + w.hi) / 2)
    assert close(math.dist(pm, (0, 0)), 2.05, 1e-9)


def test_paralela_de_un_muro_en_sentido_horario():
    cw = J.Wall("cw", pt((0, 0), 3, 90), pt((0, 0), 3, 0), 0.3, bulge=-deg(90))
    base = CD.base_from_wall(cw, pt((0, 0), 3, 45))
    (a, b, bulge, ref), = CD.parallel_arcs(base, 1.0, pt((0, 0), 6, 45), pt((0, 0), 6, 45))
    w = J.Wall("p", a, b, 0.2, ref, bulge=bulge)
    assert bulge < 0 and ref == "izquierda"      # CW: la izquierda es el lado de fuera
    assert close(math.dist(w.point(w.length / 2, (w.lo + w.hi) / 2), (0, 0)), 4.1, 1e-9)


def test_paralela_de_un_circulo_entero_son_dos_muros():
    bases = CD.base_from_arc((0, 0), 2.0, 0.0, 360.0)
    assert len(bases) == 2
    walls = CD.parallel_arcs(bases, 0.5, (5, 0), (5, 0))
    assert len(walls) == 2
    specs = [J.Wall(str(i), a, b, 0.2, ref, bulge=bl) for i, (a, b, bl, ref) in enumerate(walls)]
    r = J.solve(specs)
    assert not r.warnings and [n["degree"] for n in r.nodes] == [2, 2]
    multi, tot = overlap_and_area(r, (-3, -3, 3, 3))
    assert multi == 0.0 and close(tot, math.pi * (2.7 ** 2 - 2.5 ** 2), 3e-3)


def test_paralela_de_un_arco_dxf_de_mas_de_350_se_parte():
    bases = CD.base_from_arc((1, 1), 3.0, 10.0, 5.0)      # 355°
    assert len(bases) == 2
    for bs in bases:
        assert abs(math.degrees(4 * math.atan(bs["bulge"])) - 177.5) < 1e-9


def test_paralela_interior_que_no_cabe_y_puntos_sobre_la_linea():
    h = _cuarto()
    base = CD.base_from_wall(h, pt((0, 0), 3.0, 45))
    with raises(ValueError):
        CD.parallel_arcs(base, 3.5, (0, 0.5), (0, 0.5))
    with raises(ValueError):
        CD.parallel_arcs(base, 1.0, pt((0, 0), 3.0, 30), (5, 5))


def test_alargar_una_paralela_curva_hasta_los_muros_vecinos():
    h = _cuarto()
    r1 = J.Wall("r1", (2.0, -0.5), (2.0, 1.0), 0.3)           # vertical, caras x = 1,85 y 2,15
    r2 = J.Wall("r2", (0.2, 2.0), (2.0, 2.0), 0.3)            # horizontal, caras y = 1,85 y 2,15
    base = CD.base_from_wall(h, pt((0, 0), 2.9, 45))          # cara interior r = 2,85
    (a, b, bulge, ref), = CD.parallel_arcs(base, 0.5, pt((0, 0), 1, 45), pt((0, 0), 1, 45))   # r = 2,35
    a2, b2, bulge2 = CD.extend_arc_to_faces(a, b, bulge, {"h": h, "r1": r1, "r2": r2}, 1.2, skip=("h",))
    y = math.sqrt(2.35 ** 2 - 2.15 ** 2)                       # donde la circunferencia corta x = 2,15
    assert math.dist(a2, (2.15, y)) < 1e-9 and math.dist(b2, (y, 2.15)) < 1e-9
    w = J.Wall("n", a2, b2, 0.2, ref, bulge=bulge2)
    assert close(w.r, 2.35, 1e-9) and w.length < 0.5 * math.pi * 2.35   # recortada por los dos lados
    # con un margen más corto no llega y se queda como estaba
    a3, b3, _ = CD.extend_arc_to_faces(a, b, bulge, {"r1": r1, "r2": r2}, 0.5)
    assert math.dist(a3, a) < 1e-9 and math.dist(b3, b) < 1e-9


# --- 5. DIVIDEMURO sobre un arco -----------------------------------------------------------------------

def test_dividir_un_arco_en_partes_iguales_medidas_sobre_la_circunferencia():
    c = (0, 0)
    p1, p2 = pt(c, 3.0, 10), pt(c, 3.0, 130)
    lineas = CD.divide_arc_walls(c, p1, p2, +1, 4, 0.2, length=1.5)
    assert len(lineas) == 3
    r0, beta = 3.0, math.asin(0.2 / 6.0)
    ang = lambda p: math.atan2(p[1], p[0])      # noqa: E731
    centros = [ang(a) for a, _b, _r in lineas]
    # espacios libres (cara a cara) iguales
    bordes = [math.radians(10)] + sum(([t - beta, t + beta] for t in centros), []) + [math.radians(130)]
    libres = [bordes[2 * i + 1] - bordes[2 * i] for i in range(4)]
    assert all(close(x, libres[0], 1e-9) for x in libres)
    assert close(sum(libres) + 3 * 2 * beta, math.radians(120), 1e-9)
    for a, b, ref in lineas:                    # radiales, hacia dentro (CCW → izquierda = dentro), de 1,5 m
        assert ref == "eje" and close(math.dist(a, b), 1.5, 1e-9) and close(math.hypot(*b), 1.5, 1e-9)


def test_dividir_un_arco_en_sentido_horario_va_hacia_fuera():
    c = (0, 0)
    lineas = CD.divide_arc_walls(c, pt(c, 3.0, 130), pt(c, 3.0, 10), -1, 3, 0.2, length=1.0)
    for a, b, _ref in lineas:
        assert close(math.hypot(*b), 4.0, 1e-9)


def test_dividir_un_arco_llega_hasta_el_muro_de_enfrente_curvo_o_recto():
    c = (0, 0)
    anillo = J.Wall("r", pt(c, 1.0, 0), pt(c, 1.0, 180), 0.2, bulge=deg(180))    # centro interior de radio 1
    lineas = CD.divide_arc_walls(c, pt(c, 3.0, 20), pt(c, 3.0, 160), +1, 3, 0.2, specs={"r": anillo})
    for a, b, _ref in lineas:
        assert close(math.hypot(*b), 1.1, 1e-6)      # llega a la cara exterior (r = 1,1) del muro de enfrente
    with raises(ValueError):
        CD.divide_arc_walls(c, pt(c, 3.0, 20), pt(c, 3.0, 160), +1, 3, 0.2)       # sin longitud y sin muro


def test_dividir_en_recta_ve_los_muros_curvos_de_enfrente():
    h = _cuarto()                                         # en el cuarto de círculo de radio 3
    lineas = CD.divide_walls((0.0, 0.5), (2.0, 0.5), 2, 0.2, specs={"h": h})
    a, b, ref = lineas[0]
    assert close(a[0], 1.0, 1e-9) and close(math.hypot(*b), 2.85, 1e-9)


def test_dividir_un_arco_valida_los_puntos():
    c = (0, 0)
    with raises(ValueError):
        CD.divide_arc_walls(c, pt(c, 3.0, 10), pt(c, 4.0, 130), +1, 3, 0.2, length=1.0)
    with raises(ValueError):
        CD.divide_arc_walls(c, pt(c, 3.0, 10), pt(c, 3.0, 20), +1, 5, 0.5, length=1.0)


# --- 6. UNIRMURO: arcos de la misma circunferencia ------------------------------------------------------------

def test_unir_dos_arcos_da_mas_de_media_circunferencia():
    c = (0, 0)
    f1 = J.Wall("a", pt(c, 2, 0), pt(c, 2, 200), 0.3, bulge=deg(200))
    f2 = J.Wall("b", pt(c, 2, 200), pt(c, 2, 300), 0.3, bulge=deg(100))
    smin, smax = CD.joined_span(f1, f2)
    assert close(smin, 0.0, 1e-9) and close(smax, 2 * math.radians(300), 1e-9)
    a, b, bulge = CD.sub_wall_of_spec(f1, smin, smax)
    assert close(4 * math.degrees(math.atan(bulge)), 300.0, 1e-9)


def test_unir_sentidos_opuestos_y_hacia_atras():
    c = (0, 0)
    f1 = J.Wall("a", pt(c, 2, 100), pt(c, 2, 280), 0.3, bulge=deg(180))
    f2 = J.Wall("b", pt(c, 2, 20), pt(c, 2, 100), 0.3, bulge=deg(80))        # 20°→100°: va hacia atrás, mismo sentido
    smin, smax = CD.joined_span(f1, f2)
    assert close(smin, -2 * math.radians(80), 1e-9) and close(smax, f1.length, 1e-9)
    f3 = J.Wall("c", pt(c, 2, 300), pt(c, 2, 280), 0.3, bulge=-deg(20))        # sentido opuesto, 280°→300°
    smin, smax = CD.joined_span(f1, f3)
    assert close(smin, 0.0, 1e-9) and close(smax, 2 * math.radians(200), 1e-9)

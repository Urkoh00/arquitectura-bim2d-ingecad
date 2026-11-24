# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: secciones y alzados de sólidos sintéticos: corte, líneas ocultas,
#   costuras, profundidad y recorte lateral, con resultados calculados a mano.
import math

import pytest

from arquitectura.geom import vistas as V


def caja(ident, x0, y0, z0, x1, y1, z1, clase="IfcWall"):
    """Prisma cerrado con las normales hacia fuera."""
    a, b, c, d = (x0, y0), (x1, y0), (x1, y1), (x0, y1)

    def q(*pts):
        return {"outer": [list(p) for p in pts], "holes": []}
    caras = [
        q((*a, z0), (*d, z0), (*c, z0), (*b, z0)),          # suelo (normal -z)
        q((*a, z1), (*b, z1), (*c, z1), (*d, z1)),          # techo (+z)
        q((*a, z0), (*b, z0), (*b, z1), (*a, z1)),          # y = y0 (normal -y)
        q((*b, z0), (*c, z0), (*c, z1), (*b, z1)),          # x = x1
        q((*c, z0), (*d, z0), (*d, z1), (*c, z1)),          # y = y1
        q((*d, z0), (*a, z0), (*a, z1), (*d, z1)),          # x = x0
    ]
    return {"id": ident, "ifc_class": clase, "faces": caras}


def muro_con_ventana(ident, x0, x1, y0, y1, h, w0, w1, a0, a1):
    """Muro de x0 a x1 (espesor de y0 a y1, altura h) con un hueco pasante
    entre w0 y w1 y entre las cotas a0 y a1: las caras de los paramentos
    llevan el hueco y las jambas, el dintel y el alféizar lo cierran."""
    base = caja(ident, x0, y0, 0, x1, y1, h)
    caras = base["faces"]
    for i in (2, 4):                         # paramentos y = y0 e y = y1
        y = y0 if i == 2 else y1
        hueco = [[w0, y, a0], [w0, y, a1], [w1, y, a1], [w1, y, a0]]
        if i == 4:
            hueco = hueco[::-1]
        caras[i]["holes"] = [hueco[::-1] if i == 2 else hueco]
    def q(*pts):
        return {"outer": [list(p) for p in pts], "holes": []}
    caras += [
        q((w0, y0, a0), (w0, y0, a1), (w0, y1, a1), (w0, y1, a0)),   # jamba izquierda (+x)
        q((w1, y0, a0), (w1, y1, a0), (w1, y1, a1), (w1, y0, a1)),   # jamba derecha (-x)
        q((w0, y0, a0), (w0, y1, a0), (w1, y1, a0), (w1, y0, a0)),   # alféizar (+z)
        q((w0, y0, a1), (w1, y0, a1), (w1, y1, a1), (w0, y1, a1)),   # dintel (-z)
    ]
    return base


def _longitud(segs):
    return math.fsum(math.dist(a, b) for a, b, _ in segs)


def _alzado_sur(largo=10.0, profundidad=None):
    # mirando hacia +y desde y = -5: línea de (−1, −5) a (largo−1, −5)
    return V.Camara((-1, -5), (largo - 1, -5), (0, 0), seccion=False, profundidad=profundidad)


def test_el_alzado_de_una_caja_es_su_contorno():
    vista = V.vista([caja("A", 0, 0, 0, 4, 0.3, 3)], _alzado_sur())
    assert vista["cortes"] == []
    assert len(vista["vistos"]) == 4
    assert _longitud(vista["vistos"]) == pytest.approx(2 * (4 + 3))
    xs = [v[0] for a, b, _ in vista["vistos"] for v in (a, b)]
    assert min(xs) == pytest.approx(1.0) and max(xs) == pytest.approx(5.0)   # s = x + 1


def test_lo_que_esta_detras_queda_oculto_en_la_parte_tapada():
    delante = caja("A", 0, 0, 0, 4, 0.3, 3)
    detras = caja("B", 2, 2, 0, 8, 2.3, 5)   # más alta y más ancha, detrás
    vista = V.vista([delante, detras], _alzado_sur())
    # de B se ve: el borde superior entero (6), el lateral derecho (5), la
    # parte del lateral izquierdo por encima de A (5 − 3 = 2) y el suelo
    # desde x = 4 hasta 8 (4, que prolonga el de A); lo demás lo tapa A, cuyo
    # contorno se ve entero (14)
    assert _longitud(vista["vistos"]) == pytest.approx(14 + 6 + 5 + 2 + 4)
    izquierdo_b = [s for s in vista["vistos"]
                   if abs(s[0][0] - 3) < 1e-9 and abs(s[1][0] - 3) < 1e-9]
    assert [(min(a[1], b[1]), max(a[1], b[1])) for a, b, _ in izquierdo_b] == [
        pytest.approx((3.0, 5.0))]


def test_dos_cajas_contiguas_y_coplanarias_no_dibujan_la_costura():
    a = caja("A", 0, 0, 0, 4, 0.3, 3)
    b = caja("B", 4, 0, 0, 7, 0.3, 3)
    vista = V.vista([a, b], _alzado_sur())
    verticales_en_la_junta = [s for s in vista["vistos"]
                              if abs(s[0][0] - 5) < 1e-9 and abs(s[1][0] - 5) < 1e-9]
    assert verticales_en_la_junta == []
    assert _longitud(vista["vistos"]) == pytest.approx(2 * 7 + 2 * 3)


def test_la_seccion_corta_y_rellena_lo_cortado():
    muro = caja("M", 0, 0, 0, 6, 0.3, 3)
    pilar = caja("P", 2, 3, 0, 2.3, 3.3, 3, clase="IfcColumn")      # detrás del corte
    # corte transversal por x = 1, mirando hacia +x
    cam = V.Camara((1, -1), (1, 5), (2, 0), seccion=True)
    vista = V.vista([muro, pilar], cam)
    assert [c["id"] for c in vista["cortes"]] == ["M"]
    anillo = vista["cortes"][0]["anillos"][0]
    assert abs(V._area2(anillo)) == pytest.approx(0.3 * 3)
    # lo que queda detrás: el pilar entero (contorno 0,3 x 3) y, del muro,
    # nada más que su corte (su cara de canto x = 6 está tapada por el corte)
    assert _longitud([s for s in vista["vistos"] if s[2] == "P"]) == pytest.approx(2 * (0.3 + 3))
    assert [s for s in vista["vistos"] if s[2] == "M"] == []


def test_la_seccion_por_una_ventana_corta_el_muro_en_dos():
    muro = muro_con_ventana("M", 0, 6, 0, 0.3, 3, 2, 3.2, 0.9, 2.1)
    cam = V.Camara((2.5, -1), (2.5, 2), (4, 0), seccion=True)       # por el hueco
    vista = V.vista([muro], cam)
    anillos = vista["cortes"][0]["anillos"]
    assert sorted(abs(V._area2(r)) for r in anillos) == pytest.approx(
        sorted([0.3 * 0.9, 0.3 * (3 - 2.1)]))


def test_el_alzado_dibuja_el_hueco_de_la_ventana():
    muro = muro_con_ventana("M", 0, 6, 0, 0.3, 3, 2, 3.2, 0.9, 2.1)
    vista = V.vista([muro], _alzado_sur())
    # contorno del muro (2·6 + 2·3) y del hueco (2·1,2 + 2·1,2); las jambas,
    # el alféizar y el dintel son de canto y no añaden nada
    assert _longitud(vista["vistos"]) == pytest.approx(18 + 4.8)


def test_la_profundidad_limita_lo_que_se_ve_detras():
    cerca = caja("A", 0, 0, 0, 1, 0.3, 1)
    lejos = caja("B", 3, 20, 0, 4, 20.3, 1)
    vista = V.vista([cerca, lejos], _alzado_sur(profundidad=10))
    assert {s[2] for s in vista["vistos"]} == {"A"}


def test_lo_que_sale_de_la_franja_de_la_linea_se_recorta():
    largo = caja("A", -5, 0, 0, 20, 0.3, 3)
    vista = V.vista([largo], _alzado_sur(largo=10))       # s de 0 a 10
    # solo los bordes superior e inferior, de 10 m cada uno; los cortes
    # laterales del recorte no son aristas del muro
    assert _longitud(vista["vistos"]) == pytest.approx(20)


def test_una_cara_que_cruza_por_delante_tapa_solo_desde_el_cruce():
    # una losa inclinada que pasa de estar detrás a estar delante de una caja
    caja_ = caja("A", 0, 1, 0, 4, 1.3, 1)
    rampa = {"id": "R", "ifc_class": "IfcSlab", "faces": [
        {"outer": [[0, 0, 0.5], [4, 2, 0.5], [4, 2, 0.6], [0, 0, 0.6]], "holes": []},
    ]}
    # la cara de la rampa mira hacia −y + x: se ve desde el sur
    vista = V.vista([caja_, rampa], _alzado_sur())
    inferior = [s for s in vista["vistos"] if s[2] == "A" and abs(s[0][1]) < 1e-9 and abs(s[1][1]) < 1e-9]
    assert _longitud(inferior) == pytest.approx(4)          # el suelo de A no lo tapa la rampa


def test_la_camara_rechaza_datos_invalidos():
    with pytest.raises(ValueError):
        V.Camara((0, 0), (0, 0), (1, 1))
    with pytest.raises(ValueError):
        V.Camara((0, 0), (1, 0), (2, 0))       # el lado está sobre la línea
    with pytest.raises(ValueError):
        V.Camara((0, 0), (1, 0), (0, 1), profundidad=-1)


def test_solo_se_toman_las_caras_que_miran_a_la_camara():
    # (s, z, t) no es un triedro directo: la normal se toma del sistema del
    # dibujo. Mirando hacia +y, la cara visible de la caja es la de y = 0,
    # a 5 m de la línea, no la de y = 0,3 (que mira hacia +y)
    caras = V._caras_visibles([caja("A", 0, 0, 0, 4, 0.3, 3)], _alzado_sur())
    assert len(caras) == 1
    ns, nz, nt, c = caras[0].plano
    assert caras[0].profundidad(2.0, 1.0) == pytest.approx(5.0)


def test_una_cara_interior_entre_dos_muros_queda_oculta():
    # dos muros en esquina a inglete: las caras del inglete están dentro del
    # conjunto y tapadas por el paramento; no aparecen en el alzado
    def prisma(ident, pts, h):
        n = len(pts)
        caras = [{"outer": [[*p, 0] for p in reversed(pts)], "holes": []},
                 {"outer": [[*p, h] for p in pts], "holes": []}]
        for i in range(n):
            a, b = pts[i], pts[(i + 1) % n]
            caras.append({"outer": [[*a, 0], [*b, 0], [*b, h], [*a, h]], "holes": []})
        return {"id": ident, "ifc_class": "IfcWall", "faces": caras}
    sur = prisma("S", [(-0.15, -0.15), (6.15, -0.15), (5.85, 0.15), (0.15, 0.15)], 3)
    oeste = prisma("O", [(-0.15, -0.15), (0.15, 0.15), (0.15, 3.85), (-0.15, 4.15)], 3)
    vista = V.vista([sur, oeste], _alzado_sur())
    # solo el contorno del paramento sur: 2 × 6,3 + 2 × 3
    assert _longitud(vista["vistos"]) == pytest.approx(2 * 6.3 + 2 * 3)

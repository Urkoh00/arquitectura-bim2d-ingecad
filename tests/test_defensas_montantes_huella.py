# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: un montante de barandilla solo se coloca si su sección entera cabe en
#   la huella recortada por los muros; si un extremo no cabe, se desliza hacia
#   dentro en vez de sobresalir (revisión del 24-11).
import math

import pytest

from arquitectura import defensas as DF
from arquitectura.geom import polygon as P


class Recta:
    """Defensa recta a lo largo de x, de 0 a ``largo``, con el espesor
    centrado en el eje (lo = −t/2, hi = t/2)."""

    def __init__(self, largo, t):
        self.length, self.thickness = largo, t
        self.lo, self.hi = -t / 2, t / 2

    def point(self, s, o):
        return (s, o)


def _montantes(faces, base, post_h):
    """Puntos de la base (z = base) de las caras: contorno de los montantes."""
    return [tuple(v[:2]) for f in faces for v in (f["outer"] if isinstance(f, dict) else f[0])
            if abs(v[2] - base) < 1e-9]


def _dentro(punto, piezas, tol=1e-7):
    x, y = punto
    for pc in piezas:
        n = len(pc)
        ok = True
        orient = P.area(pc) > 0
        for i in range(n):
            a, b = pc[i], pc[(i + 1) % n]
            c = (b[0] - a[0]) * (y - a[1]) - (b[1] - a[1]) * (x - a[0])
            if (c < -tol) if orient else (c > tol):
                ok = False
                break
        if ok:
            return True
    return False


@pytest.mark.parametrize("corte", ["recto", "inglete"])
def test_ningun_montante_sobresale_de_la_huella_recortada(corte):
    t, largo = 0.05, 2.0
    spec = Recta(largo, t)
    if corte == "recto":
        # el muro al que llega recorta el arranque 1 cm: el primer montante
        # (centrado en s = t/2) tendría el centro dentro y la sección fuera
        pieza = [(0.01, -t / 2), (largo, -t / 2), (largo, t / 2), (0.01, t / 2)]
    else:
        # esquina a inglete: la cara inferior arranca en 0 y la superior en 0,05
        pieza = [(0.0, -t / 2), (largo, -t / 2), (largo, t / 2), (0.05, t / 2)]
    faces, volumen = DF.railing_solid({"pieces": [pieza]}, spec, 0.0, 1.0, 0.8)
    base = _montantes(faces, 0.0, 1.0 - DF.RAIL_HEIGHT)
    assert base, "debe haber montantes"
    fuera = [p for p in base if not _dentro(p, [pieza])]
    assert fuera == []
    # el arranque sigue teniendo montante: se ha deslizado, no quitado
    assert min(p[0] for p in base) < 0.2


def test_sin_recorte_los_montantes_no_cambian():
    t, largo = 0.05, 2.0
    spec = Recta(largo, t)
    pieza = [(0.0, -t / 2), (largo, -t / 2), (largo, t / 2), (0.0, t / 2)]
    faces, volumen = DF.railing_solid({"pieces": [pieza]}, spec, 0.0, 1.0, 0.8)
    base = _montantes(faces, 0.0, 1.0 - DF.RAIL_HEIGHT)
    assert min(p[0] for p in base) == pytest.approx(0.0)
    assert max(p[0] for p in base) == pytest.approx(largo)
    # volumen: pasamanos + 9 montantes enteros (80 % de huecos: separación
    # 0,05 / 0,20 = 0,25 m, 2 / 0,25 = 8 tramos, 9 montantes, calculado a mano)
    esperado = largo * t * DF.RAIL_HEIGHT + 9 * t * t * (1.0 - DF.RAIL_HEIGHT)
    assert volumen == pytest.approx(esperado)


@pytest.mark.parametrize("dato", ["abc", [1], {"a": 1}])
def test_una_proporcion_de_huecos_no_numerica_es_un_valueerror_claro(dato):
    # antes, una lista daba TypeError, que las órdenes no esperan
    with pytest.raises(ValueError, match="no numérica"):
        DF.void_ratio({"defense_type": "barandilla", "void_ratio": dato})

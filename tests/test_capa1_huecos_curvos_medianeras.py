# SPDX-License-Identifier: GPL-3.0-or-later
"""Capa 1 de limitaciones: huecos en muros curvos de LINEASAMURO y espesor de medianeras.

Son pruebas de geometría pura: no necesitan abrir IngeCAD. Si IngeCAD no está instalado
se simulan solo sus módulos de interfaz (tests/_sin_ingecad.py).
"""
import math
from types import SimpleNamespace as NS
import pytest

try:
    import core  # noqa: F401  (IngeCAD real)
except ImportError:
    import importlib.util
    import os
    _ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_sin_ingecad.py')
    _spec = importlib.util.spec_from_file_location('_sin_ingecad', _ruta)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    _mod.install()

from arquitectura import convert_tools as C, conversion_curves as K
from arquitectura.geom.junctions import Wall


# ---------------------------------------------------------------- dibujo sintético
def _p(x, y):
    return NS(x=x, y=y)


def _linea(a, b):
    return NS(dxftype=lambda: 'LINE', dxf=NS(start=_p(*a), end=_p(*b)))


def _arco(c, r, a0, a1):
    return NS(dxftype=lambda: 'ARC', dxf=NS(center=_p(*c), radius=r,
              start_angle=math.degrees(a0) % 360, end_angle=math.degrees(a1) % 360))


def _pt(r, a):
    return (r*math.cos(a), r*math.sin(a))


def _anillo(r=3.0, t=.3, huecos=((90, 1.0, 'puerta'),), recorrido=None):
    """Muro circular de eje r con huecos (grados del centro, ancho de arco, tipo).
    Si `recorrido` (grados) se da, solo ese arco a cada lado de cada hueco."""
    gs = sorted(((math.radians(c)-w/r/2) % math.tau, (math.radians(c)+w/r/2) % math.tau, w, k)
                for c, w, k in huecos)
    leaves, arcs, runs = [], [], []
    for i, (g0, g1, w, k) in enumerate(gs):
        siguiente = gs[(i+1) % len(gs)][0]
        fin = siguiente if siguiente > g1 else siguiente+math.tau
        if recorrido:
            fin = min(fin, g1+math.radians(recorrido))
        runs.append((g1, fin))
    if recorrido and len(gs) == 1:
        # un solo hueco con tramos de `recorrido` grados a cada lado (el resto del círculo, abierto)
        g0, g1 = gs[0][0], gs[0][1]
        runs = [(g1, g1+math.radians(recorrido)), (g0-math.radians(recorrido), g0)]
    for a0, a1 in runs:
        for rad in (r-t/2, r+t/2):
            leaves.append((_arco((0, 0), rad, a0, a1), 'muros'))
            arcs.append(((0, 0), rad, a0 % math.tau, a0 % math.tau+(a1-a0), []))
    curved, _ = C.curved_walls(arcs, .07, .5)
    for g0, g1, w, k in gs:
        c = (g0+g1)/2
        A, B = _pt(r, g0), _pt(r, g1)
        ch = math.dist(A, B)
        u = ((B[0]-A[0])/ch, (B[1]-A[1])/ch)
        n = (-u[1], u[0])
        if n[0]*-math.cos(c)+n[1]*-math.sin(c) < 0:
            n = (-n[0], -n[1])
        if k == 'ventana':
            for rad in (r-t/2+.05, r, r+t/2-.05):
                leaves.append((_arco((0, 0), rad, g0, g1), 'ventanas'))
            continue
        if k == 'vano':
            continue
        hojas = ((A, B),) if k == 'puerta' else ((A, B), (B, A))
        rad = ch if k == 'puerta' else ch/2
        for H, otro in hojas:
            leaves.append((_linea(H, (H[0]+n[0]*rad, H[1]+n[1]*rad)), 'puertas'))
            ao = math.atan2(n[1], n[0])
            ac = math.atan2(otro[1]-H[1], otro[0]-H[0])
            d = (ac-ao+math.pi) % math.tau-math.pi
            lo, hi = (ao, ao+d) if d > 0 else (ao+d, ao)
            leaves.append((_arco(H, rad, lo, hi), 'puertas'))
    return curved, leaves


def _muros(res):
    return [Wall('w', a, b, t, 'eje', bulge=bu) for a, b, t, bu in res]


def _verifica(res, ops, esperados, ancho):
    muros = _muros(res)
    assert all(abs(m.sweep) <= math.pi+1e-6 for m in muros), 'un muro supera 180°'
    assert [o[3] for o in ops] == esperados
    for k, pos, w, *_ in ops:
        assert w == pytest.approx(ancho, abs=1e-6)
        # el hueco queda dentro de su muro, con muro macizo a cada lado
        assert w/2 + .29 <= pos <= muros[k].length - w/2 - .29


# ---------------------------------------------------------------- huecos curvos
@pytest.mark.parametrize('radio', [1.5, 3.0, 6.0])
@pytest.mark.parametrize('centro', [0, 90, 200, 359])
@pytest.mark.parametrize('tipo,esperado', [('puerta', 'door'), ('puerta doble', 'door'), ('ventana', 'window')])
def test_anillo_con_un_hueco_conserva_el_hueco(radio, centro, tipo, esperado):
    """Antes: el hueco de un anillo cae en la costura y se perdía sin aviso."""
    curved, leaves = _anillo(radio, huecos=[(centro, .9, tipo)])
    res, ops, avisos = K.recover(curved, leaves)
    _verifica(res, ops, [esperado], .9)
    assert len(res) == 3, 'un anillo de 360° necesita tres muros de 180° como máximo'


def test_anillo_con_dos_huecos():
    curved, leaves = _anillo(3.0, huecos=[(30, .9, 'puerta'), (210, 1.2, 'ventana')])
    res, ops, _ = K.recover(curved, leaves)
    assert sorted(o[3] for o in ops) == ['door', 'window']
    assert all(abs(m.sweep) <= math.pi+1e-6 for m in _muros(res))


@pytest.mark.parametrize('radio', [1.5, 3.0, 6.0])
def test_conjunto_de_mas_de_180_grados_se_reparte_sin_perder_el_hueco(radio):
    """Dos tramos de 100° unidos por una puerta: el muro único no cabe (máximo 180°)."""
    curved, leaves = _anillo(radio, huecos=[(90, .9, 'puerta doble')], recorrido=100)
    res, ops, _ = K.recover(curved, leaves)
    assert [o[3] for o in ops] == ['door']
    assert all(abs(m.sweep) <= math.pi+1e-6 for m in _muros(res))


def test_hueco_sin_evidencia_no_se_une():
    curved, leaves = _anillo(3.0, huecos=[(90, 1.0, 'vano')])
    res, ops, avisos = K.recover(curved, leaves)
    assert ops == []
    assert any('sin carpintería inequívoca' in a for a in avisos)


def test_sin_huecos_la_salida_no_cambia():
    """Un anillo cerrado sin huecos conserva los muros de la lectura original."""
    arcs = [((0, 0), 2.85, 0.0, math.tau, []), ((0, 0), 3.15, 0.0, math.tau, [])]
    curved, _ = C.curved_walls(arcs, .07, .5)
    leaves = [(_arco((0, 0), r, 0, math.tau-1e-9), 'muros') for r in (2.85, 3.15)]
    res, ops, avisos = K.recover(curved, leaves)
    assert len(res) == len(curved) and ops == []


# ---------------------------------------------------------------- reparto en muros de 180°
def test_plan_cuts_no_corta_si_cabe():
    assert K.plan_cuts(0, math.pi, [(1.0, 1.3)], 3.0) == []


def test_plan_cuts_no_corta_dentro_de_un_hueco():
    cortes = K.plan_cuts(0, math.tau, [(math.pi-.15, math.pi+.15)], 3.0)
    assert cortes and len(cortes) == 2
    for c in cortes:
        assert not (math.pi-.15-.1 <= c <= math.pi+.15+.1)
    limites = [0, *cortes, math.tau]
    assert all(b-a <= math.pi+1e-9 for a, b in zip(limites, limites[1:]))


def test_plan_cuts_sin_solucion_devuelve_none():
    # cuatro huecos casi contiguos: no queda muro macizo donde cortar
    huecos = [(i*1.5, i*1.5+1.45) for i in range(4)]
    assert K.plan_cuts(0, 6.0, huecos, 1.0) is None


# ---------------------------------------------------------------- medianeras
CARA = [[0, 0, 6, 0]]


def _medianera(otras):
    avisos = []
    out, _ = C.party_walls(CARA, otras, .07, .5, 1.5, notes=avisos)
    return [round(o[2], 3) for o in out], avisos


def test_medianera_prefiere_el_limite_vecino_completo_al_mobiliario():
    espesor, _ = _medianera([[0, .10, 4, .10], [0, .25, 6, .25]])
    assert espesor == [.25]


def test_medianera_suma_tramos_del_limite_vecino():
    espesor, _ = _medianera([[0, .25, 2, .25], [2, .25, 4, .25], [4, .25, 6, .25]])
    assert espesor == [.25]


def test_medianera_empate_toma_la_mas_cercana_y_avisa():
    espesor, avisos = _medianera([[0, .20, 6, .20], [0, .30, 6, .30]])
    assert espesor == [.20]
    assert avisos and '0.200' in avisos[0] and '0.300' in avisos[0]


def test_medianera_una_candidata_como_antes():
    assert _medianera([[0, .25, 6, .25]]) == ([.25], [])


def test_medianera_sin_cobertura_suficiente_no_se_crea():
    assert _medianera([[0, .25, 1.8, .25]])[0] == []

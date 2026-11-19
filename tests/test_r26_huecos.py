# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: medidas reales de huecos, sin cajas envolventes que falseen cantidades.
import copy
import math

import pytest
from ingetrazo_ext import arquitectura_bim as extension
from arquitectura.geom.soldadura import TOLERANCIA


def transformar(contorno, angulo, origen):
    coseno = math.cos(math.radians(angulo))
    seno = math.sin(math.radians(angulo))
    return [(origen[0] + x * coseno - y * seno, origen[1] + x * seno + y * coseno)
            for x, y in contorno]


@pytest.mark.parametrize('angulo', [0, 30])
@pytest.mark.parametrize('origen', [(0., 0.), (700000., 4600000.)])
def test_rectangulo_mide_lados_y_no_envolvente(angulo, origen):
    contorno = transformar([(0, 0), (4, 0), (4, 2), (0, 2)], angulo, origen)
    medidas = extension._medidas_contorno_hueco(contorno)
    assert medidas == pytest.approx({'Width': 4., 'Height': 2.}, abs=TOLERANCIA)
    assert 'Area' not in medidas


@pytest.mark.parametrize('tipo', ['circulo', 'L'])
def test_area_poligono_real_sin_anchos_inventados(tipo):
    if tipo == 'circulo':
        contorno = [(math.cos(i * math.tau / 32), math.sin(i * math.tau / 32))
                    for i in range(32)]
        esperada = 16 * math.sin(math.tau / 32)
    else:
        contorno = [(0, 0), (3, 0), (3, 1), (1, 1), (1, 3), (0, 3)]
        esperada = 5.
    medidas = extension._medidas_contorno_hueco(contorno)
    assert medidas == pytest.approx({'Area': esperada})
    assert 'Width' not in medidas and 'Height' not in medidas


def test_rectangulo_con_copias_a_lados_de_frontera_decimal():
    contorno = [(0.00000004999, 0), (4, 0), (4, 2), (0.00000004999, 2),
                (0.00000005001, 0)]
    medidas = extension._medidas_contorno_hueco(contorno)
    assert medidas['Width'] == pytest.approx(4., abs=TOLERANCIA)
    assert medidas['Height'] == 2.


@pytest.mark.parametrize('profundidad,previsto,fondo', [(None, 'OPENING', .3),
    (0, 'OPENING', .3), (.1, 'RECESS', .1), (.3, 'OPENING', .3)])
@pytest.mark.parametrize('nombre', ['Puerta', 'Ventana', 'Hueco'])
def test_medidas_de_muro_y_nicho(profundidad, previsto, fondo, nombre):
    elemento = {'ifc_class': 'IfcWall', 'params': {'thickness': .3}}
    hueco = {'guid': '0' * 22, 'name': nombre,
             'params': {'width': .9, 'height': 2.1, 'niche_depth': profundidad},
             'faces': [{'outer': [[1, 2, 0], [2, 2, 0], [2, 2, 2.1]]}]}
    original = copy.deepcopy(hueco)
    etiqueta = extension._etiqueta_hueco(elemento, hueco, lambda punto: punto)
    assert etiqueta['predefined'] == previsto
    assert etiqueta['quantities'] == {'Width': .9, 'Height': 2.1, 'Depth': fondo}
    assert hueco == original


@pytest.mark.parametrize('angulo', [0, 30])
def test_hueco_forjado_desde_footprint(angulo):
    contorno = transformar([(0, 0), (4, 0), (4, 2), (0, 2)], angulo, (0., 0.))
    hueco = {'guid': '0' * 22, 'params': {'base': -.2, 'height': .2}, 'faces': []}
    elemento = {'ifc_class': 'IfcSlab', 'params': {'thickness': .2},
                'openings': [hueco], 'footprint': [[[], [contorno]]]}
    etiqueta = extension._etiqueta_hueco(elemento, hueco, lambda punto: punto)
    assert etiqueta['quantities'] == pytest.approx({'Width': 4., 'Height': 2., 'Depth': .2})
    assert etiqueta['predefined'] == 'OPENING'


def test_hueco_forjado_no_rectangular_desde_caras():
    contorno = [(0, 0), (3, 0), (3, 1), (1, 1), (1, 3), (0, 3)]
    hueco = {'guid': '0' * 22, 'params': {'base': -.2, 'height': .2},
             'faces': [{'outer': [[x, y, z] for x, y in contorno]} for z in [-.2, 0.]]}
    elemento = {'ifc_class': 'IfcSlab', 'params': {'thickness': .2}, 'openings': [hueco]}
    etiqueta = extension._etiqueta_hueco(elemento, hueco, lambda punto: punto)
    assert etiqueta['quantities'] == {'Depth': .2, 'Area': 5.}


@pytest.mark.parametrize('tipo', ['circulo', 'L'])
def test_etiqueta_forjado_irregular_con_area_y_depth(tipo):
    if tipo == 'circulo':
        contorno = [(math.cos(i * math.tau / 32), math.sin(i * math.tau / 32))
                    for i in range(32)]
        area = 16 * math.sin(math.tau / 32)
    else:
        contorno = [(0, 0), (3, 0), (3, 1), (1, 1), (1, 3), (0, 3)]
        area = 5.
    hueco = {'guid': '0' * 22, 'params': {'base': -.2, 'height': .2}, 'faces': []}
    elemento = {'ifc_class': 'IfcSlab', 'params': {'thickness': .2},
                'openings': [hueco], 'footprint': [[[], [contorno]]]}
    etiqueta = extension._etiqueta_hueco(elemento, hueco, lambda punto: punto)
    assert etiqueta['quantities'] == pytest.approx({'Depth': .2, 'Area': area})
    assert 'Width' not in etiqueta['quantities'] and 'Height' not in etiqueta['quantities']


def test_depth_forjado_siempre_es_el_espesor():
    hueco = {'guid': '0' * 22, 'params': {'height': .2, 'niche_depth': .05}, 'faces': []}
    contorno = [(0, 0), (2, 0), (2, 1), (0, 1)]
    elemento = {'ifc_class': 'IfcSlab', 'params': {'thickness': .2},
                'openings': [hueco], 'footprint': [[[], [contorno]]]}
    etiqueta = extension._etiqueta_hueco(elemento, hueco, lambda punto: punto)
    assert etiqueta['quantities'] == {'Width': 2., 'Height': 1., 'Depth': .2}
    assert etiqueta['predefined'] == 'OPENING'

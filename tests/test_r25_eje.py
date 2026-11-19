# Resumen: el eje usa la línea de referencia y el mismo origen que la malla.
import math
import pytest
from ingetrazo_ext import arquitectura_bim as extension
from tests.test_r24_materiales import crear_muro


@pytest.mark.parametrize('referencia', ['eje', 'izquierda', 'derecha'])
@pytest.mark.parametrize('angulo', [0, 27, 90, 180, 233])
def test_eje_coincide_con_referencia(referencia, angulo):
    elemento = crear_muro(referencia, angulo)
    desplazamiento = (700000., 4600000., 25.)
    elemento['params']['base'] = 32.5
    for nombre in ['a', 'b']:
        elemento['params'][nombre][0] += desplazamiento[0]
        elemento['params'][nombre][1] += desplazamiento[1]
    etiqueta = {}
    extension._etiqueta_eje_muro(etiqueta, elemento, desplazamiento)
    assert etiqueta['axis']['start'] == pytest.approx([0., 0., 7.5])
    assert etiqueta['axis']['end'] == pytest.approx([
        4 * math.cos(math.radians(angulo)), 4 * math.sin(math.radians(angulo)), 7.5])


def test_muro_curvo_sin_eje_recto():
    elemento = crear_muro('eje', 0)
    elemento['params']['bulge'] = .2
    etiqueta = {}
    extension._etiqueta_eje_muro(etiqueta, elemento, (0., 0., 0.))
    assert 'axis' not in etiqueta

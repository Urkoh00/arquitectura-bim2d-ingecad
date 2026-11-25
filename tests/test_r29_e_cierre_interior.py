# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: la partición del pilar se coloca hacia el interior, con referencias y sentidos distintos.
from copy import deepcopy
import math

import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session
from tests.escenarios_r27 import modulo
from tests.test_r29_e_pilar_geometria import insertar


def anillo(sesion, plugin, puntos, referencia='eje'):
    entidades = []
    for inicio, final in zip(puntos, puntos[1:] + puntos[:1]):
        orden = modulo(plugin, 'architectural_v10').create_wall(
            inicio, final, 0.3, reference=referencia, wall_category='fachada')
        modulo(plugin, 'transactions').apply_architectural_change(sesion.tool('MURO').ctx, orden)
        entidades.append(orden.entity)
    return entidades


def elementos(sesion, plugin):
    return modulo(plugin, 'exchange').build(sesion.document.doc)['elements']


def particion(sesion, plugin):
    return next(e for e in elementos(sesion, plugin) if e['ifc_class'] == 'IfcCovering'
                and e['enums']['PredefinedType'] == 'CLADDING')


@pytest.mark.parametrize('referencia', ['eje', 'izquierda', 'derecha'])
@pytest.mark.parametrize('invertir', [False, True])
def test_fachada_solo_recubre_hacia_el_recinto(plugin, monkeypatch, referencia, invertir):
    monkeypatch.setenv('ARQ_PERFIL', 'planos')
    sesion = Session(plugin)
    puntos = [(0, 0), (6, 0), (6, 4), (0, 4)]
    if invertir:
        puntos.reverse()
    muros = anillo(sesion, plugin, puntos, referencia)
    sur = next(sesion.meta(e) for e in muros if sesion.meta(e)['a'][1] == sesion.meta(e)['b'][1] == 0)
    geometria = modulo(plugin, 'geom.junctions').walls_from_records([(sur['id'], sur)])[0]
    centro = geometria.point(geometria.length / 2, (geometria.lo + geometria.hi) / 2)
    interior = max(geometria.point(geometria.length / 2, lado)[1] for lado in (geometria.lo, geometria.hi))
    insertar(sesion, plugin, centro=centro, insulation_mode='sin')
    capa = particion(sesion, plugin)
    assert capa['quantities']['NetVolume'] == pytest.approx(0.44 * 0.07 * 3)
    assert capa['quantities']['NetArea'] == pytest.approx((0.44 + 2 * 0.07) * 3)
    assert all(punto[1] >= interior - 1e-7 for cara in capa['faces'] for punto in cara['outer'])
    detalles = [(e, sesion.meta(e) or {}) for e in sesion.document.doc.modelspace()]
    assert all(punto[1] >= interior - 1e-7 for e, datos in detalles
               if datos.get('cover_role') == 'CLADDING' for punto in e.get_points('xy'))


def test_cambiar_particion_recalcula_recinto_en_un_deshacer(plugin):
    sesion = Session(plugin)
    anillo(sesion, plugin, [(0, 0), (6, 0), (6, 4), (0, 4)])
    pilar = insertar(sesion, plugin, centro=(3, 0), insulation_mode='sin')
    sesion.tool('RECINTO').on_point((3, 2))
    recinto = next(e for e in sesion.document.doc.modelspace() if (sesion.meta(e) or {}).get('kind') == 'space')
    assert sesion.meta(recinto)['net_volume'] == pytest.approx((5.7 * 3.7 - 0.44 * 0.07) * 3)
    antes = deepcopy((sesion.meta(pilar), sesion.meta(recinto)))
    profundidad = sesion.history.depth
    orden = modulo(plugin, 'columns').EditColumnCommand(pilar, {'cover': 0.1})
    modulo(plugin, 'transactions').apply_architectural_change(sesion.tool('PILAR').ctx, orden, kind='column')
    despues = deepcopy((sesion.meta(pilar), sesion.meta(recinto)))
    assert sesion.history.depth == profundidad + 1
    assert sesion.meta(recinto)['net_volume'] == pytest.approx((5.7 * 3.7 - 0.5 * 0.1) * 3)
    assert sesion.meta(pilar)['id'] == antes[0]['id']
    sesion.history.undo()
    assert (sesion.meta(pilar), sesion.meta(recinto)) == antes
    sesion.history.redo()
    assert (sesion.meta(pilar), sesion.meta(recinto)) == despues


def test_el_patio_declarado_es_exterior_y_el_forro_queda_hacia_el_edificio(plugin):
    sesion = Session(plugin)
    anillo(sesion, plugin, [(0, 0), (12, 0), (12, 12), (0, 12)])
    anillo(sesion, plugin, [(4, 4), (8, 4), (8, 8), (4, 8)])
    patio = sesion.tool('RECINTO')
    patio.enclosure = 'exterior_descubierto'
    patio.on_point((6, 6))
    insertar(sesion, plugin, centro=(6, 4), insulation_mode='sin')
    capa = particion(sesion, plugin)
    assert all(punto[1] <= 3.85 + 1e-7 for cara in capa['faces'] for punto in cara['outer'])
    assert capa['quantities']['NetVolume'] == pytest.approx(0.44 * 0.07 * 3)


def test_fachada_curva_no_deja_particion_fuera_del_circulo(plugin):
    sesion = Session(plugin)
    for inicio, final in [((-4, 0), (4, 0)), ((4, 0), (-4, 0))]:
        orden = modulo(plugin, 'architectural_v10').create_wall(inicio, final, 0.3, bulge=1)
        modulo(plugin, 'transactions').apply_architectural_change(sesion.tool('MURO').ctx, orden)
    # Sobresale 5 cm hacia el recinto: tiene una cara realmente libre.
    insertar(sesion, plugin, centro=(3.95, 0), insulation_mode='sin')
    capa = particion(sesion, plugin)
    assert capa['quantities']['NetVolume'] > 0
    assert all(math.hypot(*punto[:2]) <= 3.8501 for cara in capa['faces'] for punto in cara['outer'])


def test_una_fachada_abierta_indeterminada_avisa_y_no_adivina_el_interior(plugin, monkeypatch):
    monkeypatch.setenv('ARQ_PERFIL', 'planos')
    sesion = Session(plugin)
    orden = modulo(plugin, 'architectural_v10').create_wall((0, 0), (6, 0), 0.3)
    modulo(plugin, 'transactions').apply_architectural_change(sesion.tool('MURO').ctx, orden)
    insertar(sesion, plugin, centro=(3, 0), insulation_mode='sin')
    assert not any(e['ifc_class'] == 'IfcCovering' for e in elementos(sesion, plugin))
    informe = modulo(plugin, 'quality').audit_architecture(sesion.document)
    assert any('interior indeterminado' in aviso for aviso in informe['incidencias'])


def test_la_cara_forzada_resuelve_una_fachada_abierta(plugin):
    sesion = Session(plugin)
    orden = modulo(plugin, 'architectural_v10').create_wall((0, 0), (6, 0), 0.3,
                                                          cara_exterior='izquierda')
    modulo(plugin, 'transactions').apply_architectural_change(sesion.tool('MURO').ctx, orden)
    insertar(sesion, plugin, centro=(3, 0), insulation_mode='sin')
    capa = particion(sesion, plugin)
    assert all(punto[1] <= -0.15 + 1e-7 for cara in capa['faces'] for punto in cara['outer'])
    assert capa['quantities']['NetVolume'] == pytest.approx(0.44 * 0.07 * 3)


def test_una_particion_interior_conserva_el_recubrimiento_de_ambas_caras(plugin):
    sesion = Session(plugin)
    orden = modulo(plugin, 'architectural_v10').create_wall((0, 0), (6, 0), 0.1,
                                                          wall_category='particion')
    modulo(plugin, 'transactions').apply_architectural_change(sesion.tool('MURO').ctx, orden)
    insertar(sesion, plugin, centro=(3, 0), insulation_mode='sin')
    capa = particion(sesion, plugin)
    assert capa['quantities']['NetVolume'] == pytest.approx((0.44 ** 2 - 0.3 ** 2 - 0.14 * 0.1) * 3)
    cotas = [punto[1] for cara in capa['faces'] for punto in cara['outer']]
    assert min(cotas) < -0.15 and max(cotas) > 0.15

# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: aislamiento y partición reales por franjas, con volúmenes analíticos y Deshacer.
from copy import deepcopy

import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session
from tests.escenarios_r27 import modulo


def insertar(sesion, plugin, centro=(2, 2), **cambios):
    valores = {**modulo(plugin, 'parameters_arq').load_defaults(sesion.document)['column'], **cambios}
    modulo(plugin, 'transactions').apply_architectural_change(
        sesion.tool('PILAR').ctx, modulo(plugin, 'columns').column_command(centro, valores), kind='column')
    return next(e for e in sesion.document.doc.modelspace() if (sesion.meta(e) or {}).get('kind') == 'column')


def configurar(sesion, plugin):
    parametros = modulo(plugin, 'parameters_arq')
    datos = parametros.load_defaults(sesion.document)
    datos['general']['materiales_constructivos'] = {'F': 'fabrica', 'A': 'aislante'}
    sesion.history.execute(parametros.SetArchitecturalDefaults(datos))


def pared(sesion, plugin, base=0, altura=3, aislamiento=0.05):
    orden = modulo(plugin, 'architectural_v10').create_wall(
        (-3, 0), (3, 0), 0.3, height=altura, base=base,
        layers=[[0.1, 'F'], [aislamiento, 'A'], [0.2 - aislamiento, 'F']],
        orden_capas='exterior-interior', cara_exterior='derecha', wall_category='fachada')
    modulo(plugin, 'transactions').apply_architectural_change(sesion.tool('MURO').ctx, orden)
    return orden.entity


def recubrimientos(sesion):
    return {e['enums']['PredefinedType']: e for e in sesion.export(None)['elements']
            if e['ifc_class'] == 'IfcCovering'}


def test_pilar_aislado_dos_anillos_con_volumen_y_superficie_analiticos(plugin):
    sesion = Session(plugin)
    entidad = insertar(sesion, plugin, insulation_mode='con', insulation_thickness=0.05)
    capas = recubrimientos(sesion)
    assert set(capas) == {'CLADDING', 'INSULATION'}
    assert capas['INSULATION']['quantities']['NetVolume'] == pytest.approx((0.4 ** 2 - 0.3 ** 2) * 3)
    assert capas['CLADDING']['quantities']['NetVolume'] == pytest.approx((0.54 ** 2 - 0.4 ** 2) * 3)
    assert capas['CLADDING']['quantities']['NetArea'] == pytest.approx(4 * 0.54 * 3)
    assert capas['INSULATION']['quantities']['NetArea'] == pytest.approx(4 * 0.4 * 3)
    assert capas['CLADDING']['host'] == sesion.meta(entidad)['id']
    assert capas['INSULATION']['host'] == sesion.meta(entidad)['id']


def test_en_fachada_no_se_solapan_aislamiento_particion_y_muro(plugin):
    sesion = Session(plugin)
    configurar(sesion, plugin)
    pared(sesion, plugin)
    insertar(sesion, plugin, centro=(0, 0))
    capas = recubrimientos(sesion)
    # En fachada se reviste solo hacia el interior, no por ambas caras libres.
    assert capas['INSULATION']['quantities']['NetVolume'] == pytest.approx(0.4 * 0.05 * 3)
    assert capas['CLADDING']['quantities']['NetVolume'] == pytest.approx((0.54 * 0.12 - 0.4 * 0.05) * 3)
    geometria = modulo(plugin, 'exchange')
    muros, columnas, _huecos, avisos = geometria.read_model(sesion.document.doc)
    resultado = modulo(plugin, 'geom.bands').solve_records(muros, columnas)
    poligonos = modulo(plugin, 'geom.polygon')
    for capa in capas.values():
        for exterior, huecos in capa['footprint']:
            trozos = poligonos.convex_parts(exterior)
            for hueco in huecos:
                trozos = poligonos.subtract(trozos, hueco)
            assert all(poligonos.overlap_area(trozos, muro['pieces']) < 1e-9
                       for muro in resultado.walls.values())
    assert not avisos


def test_pilar_entre_plantas_toma_el_aislamiento_de_cada_franja(plugin):
    sesion = Session(plugin)
    configurar(sesion, plugin)
    pared(sesion, plugin, base=0, aislamiento=0.05)
    pared(sesion, plugin, base=3, aislamiento=0.08)
    insertar(sesion, plugin, centro=(0, 0), height=6)
    aislamiento = recubrimientos(sesion)['INSULATION']
    esperado = (0.3 + 2 * 0.05) * 0.05 * 3 + (0.3 + 2 * 0.08) * 0.08 * 3
    assert aislamiento['quantities']['NetVolume'] == pytest.approx(esperado)
    bandas = aislamiento['params']['franjas']
    assert [(b['base'], b['height'], b['thickness']) for b in bandas] == [(0, 3, 0.05), (3, 3, 0.08)]


def test_cambiar_tipo_recalcula_el_pilar_y_se_deshace_en_un_paso(plugin):
    sesion = Session(plugin)
    configurar(sesion, plugin)
    muro = pared(sesion, plugin)
    pilar = insertar(sesion, plugin, centro=(0, 0))
    antes = deepcopy(sesion.meta(pilar))
    volumen_antes = recubrimientos(sesion)['INSULATION']['quantities']['NetVolume']
    profundidad = sesion.history.depth
    cambio = modulo(plugin, 'architectural_v10').edit_wall(
        muro, layers=[[0.1, 'F'], [0.08, 'A'], [0.12, 'F']])
    modulo(plugin, 'transactions').apply_architectural_change(sesion.tool('MURO').ctx, cambio)
    despues = deepcopy(sesion.meta(pilar))
    assert despues['insulation_resolved_thickness'] == pytest.approx(0.08)
    assert sesion.history.depth == profundidad + 1
    assert despues['id'] == antes['id']
    sesion.history.undo()
    assert sesion.meta(pilar) == antes
    assert recubrimientos(sesion)['INSULATION']['quantities']['NetVolume'] == pytest.approx(volumen_antes)
    sesion.history.redo()
    assert sesion.meta(pilar) == despues


def test_exportar_y_auditar_no_escriben_el_pilar(plugin):
    sesion = Session(plugin)
    configurar(sesion, plugin)
    pared(sesion, plugin)
    pilar = insertar(sesion, plugin, centro=(0, 0))
    antes = deepcopy(sesion.meta(pilar))
    puntos = list(pilar.get_points())
    recubrimientos(sesion)
    modulo(plugin, 'quality').audit_architecture(sesion.document)
    assert sesion.meta(pilar) == antes
    assert list(pilar.get_points()) == puntos


def test_recinto_sigue_la_particion_y_no_el_nucleo_del_pilar(plugin):
    sesion = Session(plugin)
    arquitectura = modulo(plugin, 'architectural_v10')
    transacciones = modulo(plugin, 'transactions')
    puntos = [(0, 0), (6, 0), (6, 4), (0, 4)]
    for inicio, final in zip(puntos, puntos[1:] + puntos[:1]):
        transacciones.apply_architectural_change(sesion.tool('MURO').ctx,
                                                  arquitectura.create_wall(inicio, final, 0.3))
    pilar = insertar(sesion, plugin, insulation_mode='con', insulation_thickness=0.05)
    recinto = sesion.tool('RECINTO')
    recinto.on_point((4, 2))
    espacio = next(e for e in sesion.document.doc.modelspace()
                   if (sesion.meta(e) or {}).get('kind') == 'space')
    volumen = (5.7 * 3.7 - 0.54 ** 2) * 3
    assert sesion.meta(espacio)['net_volume'] == pytest.approx(volumen)
    antes = deepcopy(sesion.meta(espacio))
    cambio = modulo(plugin, 'columns').EditColumnCommand(pilar, {**sesion.meta(pilar), 'insulation_mode': 'sin'})
    transacciones.apply_architectural_change(sesion.tool('PILAR').ctx, cambio, kind='column')
    assert sesion.meta(espacio)['net_volume'] == pytest.approx((5.7 * 3.7 - 0.44 ** 2) * 3)
    sesion.history.undo()
    assert sesion.meta(espacio) == antes
    sesion.history.redo()
    assert sesion.meta(espacio)['net_volume'] == pytest.approx((5.7 * 3.7 - 0.44 ** 2) * 3)


def test_planta_distingue_las_capas_y_oculta_el_portador_que_invade_el_muro(plugin):
    sesion = Session(plugin)
    configurar(sesion, plugin)
    pared(sesion, plugin)
    pilar = insertar(sesion, plugin, centro=(0, 0))
    assert pilar.dxf.invisible == 1
    detalles = [(e, sesion.meta(e) or {}) for e in sesion.document.doc.modelspace()]
    capas = {(registro.get('cover_role'), e.dxf.layer) for e, registro in detalles
             if registro.get('column_id') == sesion.meta(pilar)['id'] and registro.get('cover_role')}
    assert capas == {('CLADDING', 'ARQ-PARTICIONES'), ('INSULATION', 'ARQ-AISLAMIENTOS')}


def test_falta_clasificacion_avisa_sin_deducir_aislamiento(plugin):
    sesion = Session(plugin)
    pared(sesion, plugin)
    insertar(sesion, plugin, centro=(0, 0))
    assert set(recubrimientos(sesion)) == {'CLADDING'}
    informe = modulo(plugin, 'quality').audit_architecture(sesion.document)
    assert any('clasifica' in aviso for aviso in informe['incidencias'])


def test_cambiar_clasificacion_recalcula_en_el_mismo_deshacer(plugin):
    sesion = Session(plugin)
    pared(sesion, plugin)
    pilar = insertar(sesion, plugin, centro=(0, 0))
    antes = deepcopy(sesion.meta(pilar))
    parametros = modulo(plugin, 'parameters_arq')
    datos = parametros.load_defaults(sesion.document)
    datos['general']['materiales_constructivos'] = {'F': 'fabrica', 'A': 'aislante'}
    profundidad = sesion.history.depth
    parametros.guardar_parametros(sesion.tool('PILAR').ctx, datos)
    despues = deepcopy(sesion.meta(pilar))
    assert despues['insulation_resolved_thickness'] == pytest.approx(0.05)
    assert sesion.history.depth == profundidad + 1
    sesion.history.undo()
    assert sesion.meta(pilar) == antes
    sesion.history.redo()
    assert sesion.meta(pilar) == despues


def test_escala_nativa_conserva_los_dos_espesores_y_las_identidades(plugin):
    from core import actions

    sesion = Session(plugin)
    pilar = insertar(sesion, plugin, insulation_mode='con', insulation_thickness=0.05)
    antes = deepcopy(sesion.meta(pilar))
    cambio = actions.scale_entities([pilar], (0, 0), 2)
    modulo(plugin, 'transactions').apply_architectural_change(sesion.tool('PILAR').ctx, cambio, kind='column')
    despues = deepcopy(sesion.meta(pilar))
    assert despues['cover'] == pytest.approx(0.14)
    assert despues['insulation_resolved_thickness'] == pytest.approx(0.1)
    assert despues['id'] == antes['id']
    sesion.history.undo()
    assert sesion.meta(pilar) == antes
    sesion.history.redo()
    assert sesion.meta(pilar) == despues

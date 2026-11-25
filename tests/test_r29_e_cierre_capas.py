# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: la capa de aislamiento se crea por geometría real y comparte el Deshacer del modelo.
import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session
from tests.escenarios_r27 import modulo
from tests.test_r29_e_pilar_geometria import insertar, pared


@pytest.mark.parametrize('modo', ['auto', 'sin'])
def test_planos_no_crea_capa_sin_aislamiento(plugin, monkeypatch, modo):
    monkeypatch.setenv('ARQ_PERFIL', 'planos')
    sesion = Session(plugin)
    insertar(sesion, plugin, insulation_mode=modo)
    assert 'ARQ-AISLAMIENTOS' not in sesion.document.doc.layers
    assert 'ARQ-PARTICIONES' in sesion.document.doc.layers
    modulo(plugin, 'transactions').apply_architectural_change(sesion.tool('MURO').ctx,
        modulo(plugin, 'architectural_v10').create_wall((10, 0), (16, 0), 0.3))
    assert 'ARQ-AISLAMIENTOS' not in sesion.document.doc.layers


def test_planos_con_datos_termicos_previos_no_borra_su_aislamiento(plugin, monkeypatch):
    monkeypatch.setenv('ARQ_PERFIL', 'planos')
    sesion = Session(plugin)
    insertar(sesion, plugin, insulation_mode='con', insulation_thickness=0.05)
    assert 'ARQ-AISLAMIENTOS' in sesion.document.doc.layers
    assert sesion.document.doc.layers.get('ARQ-AISLAMIENTOS').color == 3
    sesion.history.undo()
    assert 'ARQ-AISLAMIENTOS' not in sesion.document.doc.layers
    sesion.history.redo()
    assert 'ARQ-AISLAMIENTOS' in sesion.document.doc.layers
    assert any((sesion.meta(e) or {}).get('cover_role') == 'INSULATION'
               for e in sesion.document.doc.modelspace())


def test_conserva_la_capa_preexistente_aunque_este_vacia(plugin, monkeypatch):
    monkeypatch.setenv('ARQ_PERFIL', 'planos')
    sesion = Session(plugin)
    capa = sesion.document.doc.layers.add('ARQ-AISLAMIENTOS', color=1)
    capa.description = 'Capa propia del dibujo'
    insertar(sesion, plugin, insulation_mode='sin')
    sesion.history.undo()
    assert sesion.document.doc.layers.get('ARQ-AISLAMIENTOS') is capa
    assert capa.color == 1 and capa.description == 'Capa propia del dibujo'


def test_cambiar_clasificacion_crea_y_deshace_la_capa_necesaria(plugin):
    sesion = Session(plugin)
    pared(sesion, plugin)
    insertar(sesion, plugin, centro=(0, 0))
    assert 'ARQ-AISLAMIENTOS' not in sesion.document.doc.layers
    parametros = modulo(plugin, 'parameters_arq')
    datos = parametros.load_defaults(sesion.document)
    datos['general']['materiales_constructivos'] = {'F': 'fabrica', 'A': 'aislante'}
    profundidad = sesion.history.depth
    parametros.guardar_parametros(sesion.tool('PILAR').ctx, datos)
    assert sesion.history.depth == profundidad + 1
    assert 'ARQ-AISLAMIENTOS' in sesion.document.doc.layers
    sesion.history.undo()
    assert 'ARQ-AISLAMIENTOS' not in sesion.document.doc.layers
    sesion.history.redo()
    assert 'ARQ-AISLAMIENTOS' in sesion.document.doc.layers


def test_un_fallo_de_regeneracion_restaura_tambien_la_capa(plugin, monkeypatch):
    sesion = Session(plugin)
    regeneracion = modulo(plugin, 'wall_network').RegenerateContoursCommand

    def fallar(_self, _documento):
        raise RuntimeError('Fallo de dibujo de prueba')

    monkeypatch.setattr(regeneracion, '_new_details', fallar)
    datos = {**modulo(plugin, 'parameters_arq').load_defaults(sesion.document)['column'],
             'insulation_mode': 'con'}
    orden = modulo(plugin, 'columns').column_command((0, 0), datos)
    with pytest.raises(RuntimeError, match='Fallo de dibujo de prueba'):
        modulo(plugin, 'transactions').apply_architectural_change(sesion.tool('PILAR').ctx, orden, kind='column')
    assert 'ARQ-AISLAMIENTOS' not in sesion.document.doc.layers
    assert not any((sesion.meta(e) or {}).get('kind') == 'column' for e in sesion.document.doc.modelspace())

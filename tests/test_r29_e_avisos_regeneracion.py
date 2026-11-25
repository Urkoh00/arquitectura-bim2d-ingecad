# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: UNIONESARQ filtra los avisos térmicos sin ocultar problemas del plano ni cambiar datos.
from copy import deepcopy

import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session
from tests.escenarios_r27 import modulo
from tests.test_r29_e_cierre_interior import anillo
from tests.test_r29_e_pilar_geometria import insertar


@pytest.mark.parametrize('perfil', ['planos', 'bim', 'termico'])
def test_uniones_solo_muestra_el_aviso_aislante_en_termico(plugin, monkeypatch, perfil):
    monkeypatch.setenv('ARQ_PERFIL', perfil)
    sesion = Session(plugin)
    anillo(sesion, plugin, [(0, 0), (6, 0), (6, 4), (0, 4)])
    insertar(sesion, plugin, centro=(3, 0))
    antes = deepcopy(modulo(plugin, 'exchange').build(sesion.document.doc))
    contexto = sesion.tool('PILAR').ctx
    sesion.out.clear()
    plugin.commands['UNIONESARQ'](contexto)
    assert any('segmentos de contorno regenerados' in linea for linea in sesion.out)
    mensajes = [linea for linea in sesion.out if 'no se deduce aislamiento automático' in linea]
    assert bool(mensajes) == (perfil == 'termico')
    assert modulo(plugin, 'exchange').build(sesion.document.doc) == antes


def test_uniones_planos_conserva_el_aviso_de_cara_interior_indeterminada(plugin, monkeypatch):
    monkeypatch.setenv('ARQ_PERFIL', 'planos')
    sesion = Session(plugin)
    orden = modulo(plugin, 'architectural_v10').create_wall((-3, 0), (3, 0), 0.3)
    contexto = sesion.tool('PILAR').ctx
    modulo(plugin, 'transactions').apply_architectural_change(contexto, orden)
    insertar(sesion, plugin, centro=(0, 0))
    sesion.out.clear()
    plugin.commands['UNIONESARQ'](contexto)
    assert any('interior indeterminado' in linea for linea in sesion.out)
    assert not any('aislamiento automático' in linea for linea in sesion.out)

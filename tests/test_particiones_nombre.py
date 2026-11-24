# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: v1.48.1: «Tabique» pasa a llamarse «Partición» (categoría, capa,
#   conversión y órdenes) sin romper los dibujos anteriores.
from importlib import import_module

import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401  (fixture)
from tests.test_recintos import _cmd_ctx
from tests.test_wall_tools import Session


def _m(plugin, nombre):  # noqa: F811
    return import_module(plugin.tools['PILAR'].__module__.rsplit('.', 1)[0] + '.' + nombre)


def test_la_categoria_y_la_capa_se_llaman_particion(plugin):  # noqa: F811
    wc = _m(plugin, 'wall_categories')
    assert ('Partición', 'particion') in wc.CATEGORIES
    assert wc.LAYERS['particion'] == 'ARQ-PARTICIONES'
    assert wc.ifc_type('particion') == ('PARTITIONING', None)
    assert not any('abique' in nombre for nombre, _ in wc.CATEGORIES)


def test_los_datos_anteriores_se_leen_como_particion(plugin):  # noqa: F811
    wc = _m(plugin, 'wall_categories')
    assert wc.category({'wall_category': 'tabique'}) == 'particion'
    assert wc.category({'wall_role': 'tabiques'}) == 'particion'
    assert wc.ifc_type('tabique') == ('PARTITIONING', None)
    assert wc.category_of_layer('ARQ-TABIQUES@N1') == 'particion'
    pa = _m(plugin, 'parameters_arq')
    tipo = pa.normalise_type({'name': 'Viejo', 'layers': [[.1, 'LHD']], 'wall_category': 'tabique'})
    assert tipo['wall_category'] == 'particion'
    cp = _m(plugin, 'conversion_plan')
    c = cp.Classification({'CAPA': 'tabiques'}, thickness_ranges={'tabiques': (.05, .15)})
    assert c.layers == {'CAPA': 'particiones'} and c.thickness_ranges == {'particiones': (.05, .15)}
    c.assign(['1A'], 'tabiques')
    assert c.handles == {'1A': 'particiones'}


def test_un_dibujo_sin_migrar_conserva_su_capa_anterior(plugin):  # noqa: F811
    wc = _m(plugin, 'wall_categories')
    s = Session(plugin)
    capas = s.document.doc.layers
    assert wc.layer_name('particion', capas) == 'ARQ-PARTICIONES'
    capas.new('ARQ-TABIQUES')
    assert wc.layer_name('particion', capas) == 'ARQ-TABIQUES'
    # las capas estándar no le crean ARQ-PARTICIONES
    s.tool('CAPASAUTO')
    assert 'ARQ-PARTICIONES' not in capas and 'ARQ-MUROS' in capas
    capas.new('ARQ-PARTICIONES')
    assert wc.layer_name('particion', capas) == 'ARQ-PARTICIONES'


def test_arqmigrar_renombra_las_capas_de_tabiques_y_se_deshace(plugin):  # noqa: F811
    s = Session(plugin)
    capas = s.document.doc.layers
    capas.new('ARQ-TABIQUES')
    capas.new('ARQ-TABIQUES@N2')
    msp = s.document.doc.modelspace()
    linea = msp.add_line((0, 0), (1, 0), dxfattribs={'layer': 'ARQ-TABIQUES@N2'})
    plugin.commands['ARQMIGRAR'](_cmd_ctx(s))
    assert 'ARQ-TABIQUES' not in capas and 'ARQ-TABIQUES@N2' not in capas
    assert 'ARQ-PARTICIONES@N2' in capas and linea.dxf.layer == 'ARQ-PARTICIONES@N2'
    assert any('2 capas ARQ-TABIQUES renombradas' in x for x in s.out)
    s.history.undo()
    assert 'ARQ-TABIQUES@N2' in capas and linea.dxf.layer == 'ARQ-TABIQUES@N2'
    assert 'ARQ-PARTICIONES' not in capas


@pytest.mark.parametrize('palabra', ['partición', 'tabique'])
def test_muro_acepta_particion_y_la_palabra_anterior(plugin, palabra):  # noqa: F811
    s = Session(plugin)
    t = s.tool('MURO')
    t.on_option(palabra)
    assert t.bim['wall_category'] == 'particion'

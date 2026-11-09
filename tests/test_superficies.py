# SPDX-License-Identifier: GPL-3.0-or-later
"""Superficie útil por criterio normativo (Decreto 10/2019 de Extremadura), sobre IngeCAD real."""
from importlib import import_module

import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401  (fixture)
from tests.test_recintos import _cmd_ctx, _labels, _spaces, _vivienda
from tests.test_wall_tools import Session


def _mod_sup(s):
    from importlib import import_module
    return import_module(s.plugin.tools["PILAR"].__module__.rsplit(".", 1)[0] + ".superficies")


def _column(s, center, side):
    cols = import_module(s.plugin.tools['PILAR'].__module__.rsplit('.', 1)[0] + '.columns')
    s.history.execute(cols.column_command(center, {'shape': 'rect', 'width': side, 'depth': side,
                                                   'rotation': 0.0, 'height': 2.7, 'base': 0.0}))


def _superficies(s):
    out = []
    ctx = _cmd_ctx(s)
    ctx.echo = out.append
    rows, totals = _mod_sup(s).superficies(ctx)
    return rows, totals, out


def test_pilares_de_hasta_100_cm2_no_se_descuentan(plugin):
    s = Session(plugin)
    _vivienda(s)
    _column(s, (1.5, 2.0), 0.08)        # 64 cm²: no se descuenta
    _column(s, (2.5, 2.0), 0.30)        # 900 cm²: se descuenta
    s.plugin.commands['UNIONESARQ'](_cmd_ctx(s))
    r = s.tool('RECINTO')
    r.on_point((1, 1))
    m = s.meta(_spaces(s)[0])
    assert m['area'] == pytest.approx(17.86 - 0.0064 - 0.09)          # geometría (3D, IFC)
    assert m['useful_area'] == pytest.approx(17.86 - 0.09)            # superficie útil
    assert '17,77 m²' in _labels(s)[0].dxf.text
    data = s.export(None)
    sp = next(e for e in data['elements'] if e['ifc_class'] == 'IfcSpace')
    arq = sp['psets']['ARQ_Recinto']
    assert arq['SuperficieUtil'] == pytest.approx(17.77)
    assert arq['CriterioSuperficie'].startswith('Decreto 10/2019 de Extremadura')
    assert sp['quantities']['NetFloorArea'] == pytest.approx(17.86 - 0.0064 - 0.09)


def test_terraza_computa_la_mitad_y_altura_baja_no_computa(plugin):
    s = Session(plugin)
    _vivienda(s)
    r = s.tool('RECINTO')
    r.on_option('f')
    r.on_option('2,40')                 # útil, pero no habitable (< 2,50)
    r.on_point((2, 2))
    r.on_option('f')
    r.on_option('0')
    r.on_option('t')
    r.on_option('exterior')
    r.on_point((6, 2))
    rows, totals, out = _superficies(s)
    by = {row['name']: row for row in rows}
    assert by['Recinto 1']['computable'] == pytest.approx(17.86) and not by['Recinto 1']['habitable']
    assert by['Recinto 2']['factor'] == 0.5
    assert by['Recinto 2']['computable'] == pytest.approx(17.86 / 2)
    assert totals['useful_interior'] == pytest.approx(17.86)
    assert totals['computable'] == pytest.approx(17.86 * 1.5)
    assert totals['habitable'] == pytest.approx(0.0)
    assert any('Superficie útil computable: 26,79 m²' in o for o in out)
    assert '(computa 8,93)' in ' '.join(e.dxf.text for e in _labels(s))
    sp = {e['name']: e for e in s.export(None)['elements'] if e['ifc_class'] == 'IfcSpace'}
    assert sp['Recinto 2']['psets']['Pset_SpaceCommon']['IsExternal'] is True
    # un recinto de menos de 1,50 m de altura libre no computa
    sm = import_module(s.plugin.tools['PILAR'].__module__.rsplit('.', 1)[0] + '.superficies')
    ev = sm.evaluate({'height': 1.40}, {'area': 5.0, 'outer': [(0, 0), (2, 0), (2, 2.5), (0, 2.5)]})
    assert ev['computable'] == 0.0 and ev['notes']


def test_la_puerta_del_tabique_no_suma_superficie(plugin):
    s = Session(plugin)
    _vivienda(s)
    t = s.tool('CARPINTERIA')
    t.on_option('m')
    t.on_option('c')
    t.on_point((3.95, 2.0))
    r = s.tool('RECINTO')
    r.on_point((2, 2))
    r.on_point((6, 2))
    rows, totals, _out = _superficies(s)
    assert totals['useful_interior'] == pytest.approx(2 * 17.86)      # el paso de la puerta no computa


def test_cuadro_de_superficies_en_el_dibujo(plugin):
    from tests.test_recintos import _vivienda
    from tests.test_wall_tools import Session
    s = Session(plugin)
    _vivienda(s)
    r = s.tool('RECINTO')
    r.on_point((2, 2))
    r.on_point((6, 2))
    sup = _mod_sup(s)
    t = s.tool('SUPERFICIES')
    t.on_point((10, 5))
    ents = [e for e in s.document.doc.modelspace() if (s.meta(e) or {}).get('kind') == 'area_table']
    texts = [e.dxf.text for e in ents if e.dxftype() == 'TEXT']
    assert 'CUADRO DE SUPERFICIES ÚTILES' in texts and 'Recinto 1' in texts and 'Recinto 2' in texts
    assert 'Superficie útil computable' in texts
    total = sup.table(s.document.doc)[1]['computable']
    assert f"{total:.2f}".replace('.', ',') in texts
    assert all(e.dxf.layer == sup.TABLE_LAYER for e in ents)
    n = len(ents)
    # change the model, update the schedule in place: one schedule, new figures
    r = s.tool('RECINTO')
    r.on_option('n')
    r.on_option('Salón')
    s.tool('SUPERFICIES').on_option('a')
    ents2 = [e for e in s.document.doc.modelspace() if (s.meta(e) or {}).get('kind') == 'area_table']
    assert len(ents2) == n and any(e.dxftype() == 'TEXT' and e.dxf.text == 'Recinto 1' for e in ents2)
    s.history.undo()
    assert len([e for e in s.document.doc.modelspace() if (s.meta(e) or {}).get('kind') == 'area_table']) == n
    s.history.undo()
    assert not [e for e in s.document.doc.modelspace() if (s.meta(e) or {}).get('kind') == 'area_table']

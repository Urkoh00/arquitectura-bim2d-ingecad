# SPDX-License-Identifier: GPL-3.0-or-later
"""Analytical volumes and native history, without private drawings."""
import copy

import pytest

from arquitectura import space_envelope as SE
from arquitectura.geom import solids as S, polygon as P
from arquitectura.slabs import region
from tests.test_solids import watertight
from tests.test_ingecad_integration import plugin
from tests.test_wall_tools import Session
from tests.test_r12_conversion import module
from tests.test_fichas import qt

OUTER = [(0, 0), (6, 0), (6, 4), (0, 4)]
HALF = [(0, 0), (3, 0), (3, 4), (0, 4)]
HOLE = [(1, 1), (2, 1), (2, 2), (1, 2)]


def limit(ident, top, thickness=.2, outer=OUTER, holes=()):
    return dict(id=ident, base=top-thickness, thickness=thickness,
                pieces=region(outer, holes)['pieces'], limit_type='forjado')


def record(**kw):
    return dict(height=2.7, base=0, height_mode='auto', **kw)


def check(envelope, volume):
    assert envelope['volume'] == pytest.approx(volume)
    assert S.face_volume(envelope['faces']) == pytest.approx(volume)
    assert watertight(envelope['faces'])


@pytest.mark.parametrize('base,top,thickness', [(0, 3.2, .25), (3.2, 6.4, .3), (-3, 0, .2)])
def test_analytical_between_visible_slab_faces(base, top, thickness):
    m = record(); m['base'] = base
    env = SE.resolve(m, region(OUTER), [limit('floor', base), limit('upper', top, thickness)])
    check(env, 24*(top-thickness-base))
    assert env['base'] == base
    assert env['upper_limit'] == 'forjado'
    assert env['upper_limit_ids'] == ['upper']
    assert env['lower_limit_ids'] == ['floor']


def test_case_a_horizontal_slab_precedes_higher_roof_support():
    env = SE.resolve(record(), region(OUTER), [limit('floor', 0), limit('upper', 3.2), limit('higher', 5)])
    check(env, 72)
    assert env['upper_limit_ids'] == ['upper']


@pytest.mark.parametrize('ceiling,expected,kind', [(2.5, 60, 'falso techo'), (3.5, 72, 'forjado')])
def test_case_c_nearest_upper_limit_wins(ceiling, expected, kind):
    m = record(ceiling=True); m['height'] = ceiling
    env = SE.resolve(m, region(OUTER), [limit('floor', 0), limit('upper', 3.2)])
    check(env, expected)
    assert env['upper_limit'] == kind


def test_manual_override_and_legacy_keep_height():
    for mode in [None, 'manual']:
        m = dict(height=2.4, base=0)
        if mode: m['height_mode'] = mode
        env = SE.resolve(m, region(OUTER), [limit('upper', 3.2)])
        check(env, 57.6)
        assert env['upper_limit'] == 'manual'


def test_no_limit_uses_manual_fallback():
    env = SE.resolve(record(), region(OUTER))
    check(env, 64.8)
    assert env['upper_limit'] == 'manual'


def test_partial_slab_and_hole_do_not_cap_uncovered_area():
    env = SE.resolve(record(), region(OUTER), [limit('upper', 3.2, outer=HALF, holes=[HOLE])])
    check(env, 11*3+13*2.7)
    assert env['height'] == pytest.approx(3)
    assert env['volume'] != pytest.approx(24*env['height'])
    assert env['upper_limit'] == 'forjado, manual'


def test_different_floor_tops_and_ceiling_remain_watertight():
    env = SE.resolve(record(ceiling=True), region(OUTER), [limit('low', 0), limit('raised', .15, outer=HALF)])
    check(env, 64.8)
    assert env['base'] == 0
    assert watertight(S.boundary(env['ceiling_cells']))


@pytest.mark.parametrize('height', [0, -1, float('nan'), float('inf')])
def test_invalid_height_rejected(height):
    m = record(); m['height'] = height
    with pytest.raises(ValueError): SE.resolve(m, region(OUTER))


def poly(s, points=OUTER):
    t = s.tool('RECINTO'); t.on_option('polilinea')
    for p in points: t.on_point(p)
    t.on_enter()
    found = [e for e in s.document.doc.modelspace() if (s.meta(e) or {}).get('kind') == 'space']
    assert found, s.out[-3:]
    return found[0]


def spaces(s, path):
    return [e for e in s.export(path)['elements'] if e['ifc_class'] == 'IfcSpace']


def test_polyline_analytic_export_and_one_undo(plugin, tmp_path):
    s = Session(plugin); E = module(s, 'conversion_plan'); before = E.fingerprint(s.document.doc)
    ent = poly(s); ident = s.meta(ent)['id']
    el = spaces(s, tmp_path)[0]
    assert el['quantities']['NetVolume'] == pytest.approx(72.0)        # 24 m² × 3,00 m
    assert S.face_volume([(f['outer'], f['holes']) for f in el['faces']]) == pytest.approx(72.0)
    assert el['psets']['ARQ_Recinto']['Techo'] == 'manual'
    s.history.undo()
    assert E.fingerprint(s.document.doc) == before
    s.history.redo()
    assert s.meta(ent)['id'] == ident


def test_polyline_concave_native_move_save_and_reload(plugin, tmp_path):
    from core import actions
    import ezdxf
    s = Session(plugin)
    ent = poly(s, [(0,0),(6,0),(6,2),(3,2),(3,4),(0,4)])
    s.history.execute(actions.move_entities([ent], 10, 5))
    s.plugin.commands['UNIONESARQ'](__import__('tests.test_recintos', fromlist=['_cmd_ctx'])._cmd_ctx(s))
    el = spaces(s, tmp_path)[0]
    assert el['plan_area'] == pytest.approx(18)
    assert min(p[0] for p in el['footprint'][0][0]) == pytest.approx(10)
    path = tmp_path/'room.dxf'; s.document.doc.saveas(path)
    out = module(s, 'exchange').build(ezdxf.readfile(path))
    assert next(e for e in out['elements'] if e['ifc_class']=='IfcSpace')['volume'] == pytest.approx(54.0)
    assert not [i for i in s.issues() if 'Recinto' in i or 'Contorno' in i]


def test_automatic_room_reacts_to_slab_edit_and_undo(plugin, tmp_path):
    s = Session(plugin); slabs = module(s, 'slabs')
    slabs.apply_new(s.tool('MURO').ctx, OUTER, thickness=.25)
    upper = slabs.apply_new(s.tool('MURO').ctx, OUTER, thickness=.25, top_offset=3.2)
    ent = poly(s)
    el = spaces(s, tmp_path)[0]
    assert el['volume'] == pytest.approx(24*2.95)
    assert s.meta(ent)['upper_limit_ids'] == [slabs.read(upper.entity)['id']]
    m = slabs.read(upper.entity); m['thickness'] = .4
    module(s, 'transactions').apply_architectural_change(s.tool('MURO').ctx, slabs.EditSlab(upper.entity,m))
    # Changing thickness through EditSlab with fixed base keeps underside unchanged.
    assert spaces(s, tmp_path)[0]['volume'] == pytest.approx(24*2.95)
    m = slabs.read(upper.entity); m['base'] -= .3
    module(s, 'transactions').apply_architectural_change(s.tool('MURO').ctx, slabs.EditSlab(upper.entity,m))
    assert spaces(s, tmp_path)[0]['volume'] == pytest.approx(24*2.65)
    s.history.undo()
    assert spaces(s, tmp_path)[0]['volume'] == pytest.approx(24*2.95)


def test_manual_switch_preserves_requested_height(plugin, tmp_path):
    s = Session(plugin); slabs = module(s, 'slabs')
    slabs.apply_new(s.tool('MURO').ctx, OUTER, thickness=.2, top_offset=3.2)
    ent = poly(s)
    assert spaces(s, tmp_path)[0]['volume'] == pytest.approx(72)
    edit = module(s, 'arq_properties').space_change(ent, {'height_mode':'manual','height':2.4})
    module(s, 'transactions').apply_architectural_change(s.tool('MURO').ctx, edit)
    assert spaces(s, tmp_path)[0]['volume'] == pytest.approx(57.6)
    s.history.undo()
    assert spaces(s, tmp_path)[0]['volume'] == pytest.approx(72)


def test_invalid_polygon_and_cancel_make_no_changes(plugin):
    s = Session(plugin); E = module(s,'conversion_plan'); before = E.fingerprint(s.document.doc)
    t = s.tool('RECINTO'); t.on_option('p')
    for p in [(0,0),(4,4),(0,4),(4,0)]: t.on_point(p)
    t.on_enter()
    assert E.fingerprint(s.document.doc) == before
    t.on_cancel()
    assert E.fingerprint(s.document.doc) == before


def test_polyline_preview_measurement_does_not_write_drawing(plugin):
    s = Session(plugin); t = s.tool('RECINTO'); t.on_option('p'); t.on_point((0,0))
    E = module(s,'conversion_plan'); before = E.fingerprint(s.document.doc)
    assert t.preview_entities((3,4))[0].dxf.text == '5.000 m'
    assert t.preview_segments((3,4))
    assert E.fingerprint(s.document.doc) == before


def test_click_rooms_on_superposed_levels(plugin, tmp_path):
    from tests.test_r16_levels_slabs import catalog
    from tests.test_wall_tools import draw
    s = Session(plugin); slabs = module(s, 'slabs')
    for top in (0, 3.2, 6.4):
        slabs.apply_new(s.tool('MURO').ctx, OUTER, thickness=.2, top_offset=top)
    draw(s.tool('MURO'), (0,0),(6,0),(6,4),(0,4),(0,0))
    s.tool('RECINTO').on_point((2,2))
    L, data, pa = catalog(s); pa['elevation'] = 3.2; data['active'] = pa['id']; L.apply(s.tool('MURO').ctx, data)
    draw(s.tool('MURO'), (0,0),(6,0),(6,4),(0,4),(0,0))
    s.tool('RECINTO').on_point((2,2))
    result = spaces(s, tmp_path)
    assert len(result) == 2
    assert sorted(e['params']['base'] for e in result) == pytest.approx([0,3.2])
    assert max(e['params']['base'] for e in result) == pytest.approx(3.2)
    assert all(e['quantities']['Height'] == pytest.approx(3) for e in result)
    assert not [i for i in s.issues() if 'misma estancia' in i]


def test_legacy_false_ceiling_export_is_preserved(plugin, tmp_path):
    s = Session(plugin)
    t = s.tool('RECINTO'); t.on_option('f'); t.on_option('2.5'); t.on_option('p')
    for p in OUTER: t.on_point(p)
    t.on_enter()
    data = s.export(tmp_path)
    space = next(e for e in data['elements'] if e['ifc_class']=='IfcSpace')
    ceiling = next(e for e in data['elements'] if e['ifc_class']=='IfcCovering')
    assert space['volume'] == pytest.approx(60)
    assert space['psets']['ARQ_Recinto']['Techo'] == 'falso techo'
    assert ceiling['params']['base'] == pytest.approx(2.5)


@pytest.mark.parametrize('units', [1, 4])
def test_polyline_non_metre_units_are_rejected_without_changes(plugin, units):
    s = Session(plugin); s.document.doc.header['$INSUNITS'] = units
    E = module(s,'conversion_plan'); before = E.fingerprint(s.document.doc)
    t = s.tool('RECINTO'); t.on_option('p')
    for p in OUTER: t.on_point(p)
    t.on_enter()
    assert E.fingerprint(s.document.doc) == before
    assert any('exige metros' in msg for msg in s.out)


def test_sheet_shows_limit_and_preserves_manual_reserve(plugin, qt):
    from tests.test_fichas import _Ctx
    from PySide6.QtWidgets import QLabel
    s = Session(plugin); bd = module(s, 'bim_dialogs')
    dlg, read = bd.space_form(_Ctx(), {'height':2.7,'height_mode':'auto',
        'upper_limit':'forjado','free_height':2.95,'net_volume':70.8}, by_use=False)
    texts = [w.text() for w in dlg.findChildren(QLabel)]
    assert 'forjado' in texts and '2.950' in texts and '70.800' in texts
    mode = dlg._arq['height_mode']
    mode.setCurrentIndex(mode.findData('manual'))
    assert read()['height_mode']=='manual' and read()['height']==pytest.approx(2.7)
    dlg.close()

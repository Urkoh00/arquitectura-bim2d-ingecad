# SPDX-License-Identifier: GPL-3.0-or-later
"""Sheets (Qt dialogs) for carpentry and spaces, as walls and columns have.

Asked by the user on 7-11-2026: «los tipos de carpintería y huecos deben
tener su cuadro de diálogo, al igual que los recintos» and PROPIEDADESARQ
must recognise carpentry, holes and spaces as BIM elements."""
from importlib import import_module

import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401  (fixture)
from tests.test_recintos import _labels, _spaces, _vivienda
from tests.test_wall_tools import Session


def _mod(s, name):
    return import_module(s.plugin.tools['PILAR'].__module__.rsplit('.', 1)[0] + '.' + name)


class _Ctx:
    services = None


@pytest.fixture
def qt():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_ficha_de_carpinteria(plugin, qt):
    bd = _mod(Session(plugin), 'bim_dialogs')
    dlg, read = bd.carpentry_form(_Ctx(), {'type': 'door', 'leaf': 0.825, 'frame_width': 0.03,
                                           'width': 0.885, 'height': 2.1, 'sill': 0.0})
    w = dlg._arq
    assert w['ifc'].text() == 'IfcDoor' and 'válida' in w['clear'].text()
    w['preset'].setCurrentIndex(w['preset'].findData(0.725))        # hoja de 725
    v = read()
    assert v['leaf'] == pytest.approx(0.725) and v['width'] == pytest.approx(0.785)
    assert 'NO válida' in w['clear'].text()                          # 0,725 < 0,80 (DB-SUA)
    w['typ'].setCurrentIndex(w['typ'].findData('window'))
    w['width'].setValue(1.5)
    v = read()
    assert v['type'] == 'window' and v['width'] == pytest.approx(1.5) and w['ifc'].text() == 'IfcWindow'
    assert v['operation'] in ('SIDEHUNG', 'SLIDING', 'FIXED')
    w['typ'].setCurrentIndex(w['typ'].findData('gap'))
    assert read()['frame_width'] == 0.0 and w['ifc'].text() == 'IfcOpeningElement'


def test_ficha_de_recinto(plugin, qt):
    bd = _mod(Session(plugin), 'bim_dialogs')
    dlg, read = bd.space_form(_Ctx(), {'name': 'Salón', 'height': 2.6})
    w = dlg._arq
    w['use'].setText('Estar')
    w['ceiling'].setChecked(True)
    w['enclosure'].setCurrentIndex(1)
    v = read()
    assert v['name'] == 'Salón' and v['use'] == 'Estar' and v['ceiling'] is True
    assert v['enclosure'] == 'exterior_cubierto' and v['height'] == pytest.approx(2.6)


def _sheets_on(s, monkeypatch, carpentry=None, space=None):
    bd = _mod(s, 'bim_dialogs')
    monkeypatch.setattr(bd, 'available', lambda ctx: True)
    if carpentry is not None:
        monkeypatch.setattr(bd, 'carpentry_properties', lambda ctx, rec, editing=False: carpentry(rec))
    if space is not None:
        monkeypatch.setattr(bd, 'space_properties', lambda ctx, rec: space(rec))


def test_propiedadesarq_reconoce_carpinterias_y_recintos(plugin, monkeypatch):
    s = Session(plugin)
    _vivienda(s)
    p = s.tool('PUERTAARQ')
    p.on_point((2, 0.15))
    p.on_point((3, 0.15))
    r = s.tool('RECINTO')
    r.on_point((2, 2))
    door = next(e for e in s.document.doc.modelspace() if (s.meta(e) or {}).get('kind') == 'opening')
    ident = s.meta(door)['id']
    symbol = next(e for e in s.document.doc.modelspace() if (s.meta(e) or {}).get('kind') == 'opening_symbol')
    label = _labels(s)[0]

    def new_door(rec):
        return {**{k: rec[k] for k in ('type', 'operation', 'height', 'sill', 'face', 'frame_width',
                                      'frame_depth', 'leaves', 'side', 'hinge')},
                'leaf': 0.725, 'leaf2': 0.0, 'width': 0.785, 'offset': 1.0,
                'name': 'P1', 'type_name': 'Puerta de paso', 'material': 'Madera'}
    _sheets_on(s, monkeypatch, carpentry=new_door,
               space=lambda rec: {'name': 'Dormitorio', 'number': '7', 'use': 'Dormir',
                                  'enclosure': 'interior', 'height': 2.5, 'ceiling': True,
                                  'level': 'Planta baja'})
    picks = iter([symbol, label])
    monkeypatch.setattr(s.services, 'pick_entity', lambda point, radius=0.05: next(picks))
    t = s.tool('PROPIEDADESARQ')
    t.on_point((0, 0))
    m = s.meta(door)
    assert m['id'] == ident and m['name'] == 'P1' and m['material'] == 'Madera'
    assert m['leaf'] == pytest.approx(0.725) and m['width'] == pytest.approx(0.785)
    assert m['offset'] == pytest.approx(1.0)
    t = s.tool('PROPIEDADESARQ')
    t.on_point((0, 0))
    sp = s.meta(_spaces(s)[0])
    assert sp['name'] == 'Dormitorio' and sp['use'] == 'Dormir' and sp['ceiling'] is True
    assert any('Dormitorio' in (l.dxf.text if l.dxftype() == 'TEXT' else l.text) for l in _labels(s))
    data = s.export(None)
    sp_el = next(e for e in data['elements'] if e['ifc_class'] == 'IfcSpace')
    assert sp_el['name'] == 'Dormitorio'
    s.history.undo()
    assert s.meta(_spaces(s)[0])['name'] != 'Dormitorio'


def test_carpinteria_y_recinto_abren_su_ficha(plugin, monkeypatch):
    s = Session(plugin)
    _vivienda(s)
    _sheets_on(s, monkeypatch,
               carpentry=lambda rec: {'type': 'window', 'operation': 'SLIDING', 'leaves': 2, 'width': 1.5,
                                      'height': 1.1, 'sill': 1.0, 'face': 'exterior', 'frame_width': 0.05,
                                      'frame_depth': 0.0, 'sill_kind': 'vierteaguas', 'name': 'V1',
                                      'type_name': 'Corredera 2 hojas', 'material': 'Aluminio'},
               space=lambda rec: {'name': 'Cocina', 'number': '3', 'use': 'Cocina', 'enclosure': 'interior',
                                  'height': 2.5, 'ceiling': False, 'level': 'Planta baja'})
    v = s.tool('CARPINTERIA')
    v.on_point((2, 4.85))
    v.on_point((3, 4.85))
    w = next(s.meta(e) for e in s.document.doc.modelspace() if (s.meta(e) or {}).get('kind') == 'opening')
    assert (w['type'], w['operation'], w['name'], w['material']) == ('window', 'SLIDING', 'V1', 'Aluminio')
    assert w['width'] == pytest.approx(1.5) and w['sill_kind'] == 'vierteaguas'
    r = s.tool('RECINTO')
    r.on_point((6, 2))
    sp = s.meta(_spaces(s)[0])
    assert (sp['name'], sp['number'], sp['use']) == ('Cocina', '3', 'Cocina')
    out = []
    ctx = type('C', (), {'document': s.document, 'echo': out.append})()
    import tempfile, os
    path = os.path.join(tempfile.mkdtemp(), 'x.arqbim')
    _mod(s, 'bim_export').exportar_bim(ctx, path)
    assert any('1 ventanas' in o for o in out), out

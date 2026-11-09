# SPDX-License-Identifier: GPL-3.0-or-later
"""Integrity before exporting (independent audit of v1.15, ARQ-AUD-0001,
0005, 0013 and 0024), with the user's decision of 9-11-2026: never block
and never stay silent.  Every problem is reported with the entities it
concerns (highlighted in the drawing); the operator decides to export
without them or to cancel.  Nothing tagged disappears without a word."""
import os
import tempfile
from importlib import import_module

import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401  (fixture)
from tests.test_recintos import _spaces, _vivienda
from tests.test_wall_tools import Session


def _mod(s, name):
    return import_module(s.plugin.tools['PILAR'].__module__.rsplit('.', 1)[0] + '.' + name)


def _tagged(s, kind):
    return [e for e in s.document.doc.modelspace() if (s.meta(e) or {}).get('kind') == kind]


def _export(s, monkeypatch=None, answer=None):
    out = []
    ctx = type('C', (), {'document': s.document, 'echo': out.append, 'services': None})()
    if answer is not None:
        bd = _mod(s, 'bim_dialogs')
        monkeypatch.setattr(bd, 'available', lambda ctx: True)
        monkeypatch.setattr(bd, 'problems_dialog', lambda ctx, problems: answer)
    path = os.path.join(tempfile.mkdtemp(), 'x.arqbim')
    return _mod(s, 'bim_export').exportar_bim(ctx, path), out


def _door(s):
    p = s.tool('PUERTAARQ')
    p.on_point((2, 0.15))
    p.on_point((3, 0.15))
    return _tagged(s, 'opening')[0]


def test_carpinteria_huerfana_se_avisa_y_no_desaparece_en_silencio(plugin):   # 0001
    s = Session(plugin)
    _vivienda(s)
    door = _door(s)
    arch = _mod(s, 'architectural')
    m = s.meta(door)
    m['wall_id'] = 'muro-inexistente'
    arch._xdata(s.document.doc.modelspace(), door, m)
    problems = _mod(s, 'integrity').audit(s.document.doc)
    assert [p['code'] for p in problems] == ['huerfano']
    assert problems[0]['handles'] == [door.dxf.handle]
    data, out = _export(s)
    assert data is not None and not any(e['ifc_class'] == 'IfcDoor' for e in data['elements'])
    assert any('sin muro anfitrión' in o for o in out)
    assert any('sin muro anfitrión' in i for i in data['issues'])
    assert door.is_alive                        # the drawing is not touched


def test_hueco_que_no_cabe_se_avisa(plugin):                                   # 0005
    s = Session(plugin)
    _vivienda(s)
    door = _door(s)
    arch = _mod(s, 'architectural')
    m = s.meta(door)
    m['offset'] = 7.9                            # the wall is 8 m long
    arch._xdata(s.document.doc.modelspace(), door, m)
    problems = _mod(s, 'integrity').audit(s.document.doc)
    assert [p['code'] for p in problems] == ['hueco'] and 'longitud' in problems[0]['text']
    assert len(problems[0]['handles']) == 2      # the door and its wall, to highlight
    m['offset'], m['height'] = 1.0, 9.0
    arch._xdata(s.document.doc.modelspace(), door, m)
    assert 'altura' in _mod(s, 'integrity').audit(s.document.doc)[0]['text']
    data, _out = _export(s)
    assert sum(e['ifc_class'] == 'IfcWall' for e in data['elements']) == 5   # the host stays


def test_recinto_copiado_no_repite_identidad(plugin):                          # 0013
    s = Session(plugin)
    _vivienda(s)
    s.tool('RECINTO').on_point((2, 2))
    space = _spaces(s)[0]
    copy = space.copy()
    s.document.doc.modelspace().add_entity(copy)
    problems = _mod(s, 'integrity').audit(s.document.doc)
    assert [p['code'] for p in problems] == ['duplicado'] and problems[0]['handles'] == [copy.dxf.handle]
    data, _out = _export(s)
    guids = [e['guid'] for e in data['elements']]
    assert len(guids) == len(set(guids))
    assert sum(e['ifc_class'] == 'IfcSpace' for e in data['elements']) == 1


def test_datos_ilegibles_se_avisan(plugin):                                    # 0024
    s = Session(plugin)
    _vivienda(s)
    walls = _tagged(s, 'wall')
    broken = walls[0]
    arch = _mod(s, 'architectural')
    broken.set_xdata(arch.APPID, [(1000, '{"kind":')])
    problems = _mod(s, 'integrity').audit(s.document.doc)
    assert [p['code'] for p in problems] == ['ilegible'] and problems[0]['handles'] == [broken.dxf.handle]
    data, out = _export(s)
    assert any('ilegibles' in o for o in out)
    assert sum(e['ifc_class'] == 'IfcWall' for e in data['elements']) == len(walls) - 1
    assert broken.is_alive
    report = _mod(s, 'quality').audit_architecture(s.document)
    assert any('ilegibles' in i for i in report['incidencias'])


def test_el_operador_decide(plugin, monkeypatch):
    s = Session(plugin)
    _vivienda(s)
    door = _door(s)
    arch = _mod(s, 'architectural')
    m = s.meta(door)
    m['wall_id'] = 'nada'
    arch._xdata(s.document.doc.modelspace(), door, m)
    data, out = _export(s, monkeypatch, answer=False)
    assert data is None and any('cancelado' in o for o in out)
    data, out = _export(s, monkeypatch, answer=True)
    assert data is not None and any('Omitidos 1' in o for o in out)


def test_sin_problemas_no_hay_dialogo(plugin, monkeypatch):
    s = Session(plugin)
    _vivienda(s)
    _door(s)
    bd = _mod(s, 'bim_dialogs')
    monkeypatch.setattr(bd, 'available', lambda ctx: True)
    monkeypatch.setattr(bd, 'problems_dialog', lambda ctx, p: pytest.fail('no debe abrirse'))
    data, _out = _export(s)
    assert data is not None and any(e['ifc_class'] == 'IfcDoor' for e in data['elements'])


def test_ventana_de_problemas_resalta(plugin):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    s = Session(plugin)
    _vivienda(s)
    door = _door(s)
    arch = _mod(s, 'architectural')
    m = s.meta(door)
    m['wall_id'] = 'nada'
    arch._xdata(s.document.doc.modelspace(), door, m)
    problems = _mod(s, 'integrity').audit(s.document.doc)

    class Services:
        selection = set()
        window = None
    ctx = type('C', (), {'document': s.document, 'services': Services()})()
    dlg, lst = _mod(s, 'bim_dialogs').problems_form(ctx, problems)
    assert lst.count() == 1
    lst.setCurrentRow(0)
    assert ctx.services.selection == {door.dxf.handle}

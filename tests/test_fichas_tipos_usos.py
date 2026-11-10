# SPDX-License-Identifier: GPL-3.0-or-later
"""Fichas pedidas en la prueba del usuario del 10-11: tipos de muro con todos
sus parámetros (TIPOSMURO y la ficha de MURO) y los usos del CTE (USOSARQ)."""
from importlib import import_module

import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401  (fixture)
from tests.test_wall_tools import Session


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _mod(s, name):
    return import_module(s.plugin.tools['PILAR'].__module__.rsplit('.', 1)[0] + '.' + name)


CTX = type('C', (), {'host': None, 'services': None})()


def test_ficha_de_muro_elige_tipo_con_sus_capas(plugin, qapp):
    s = Session(plugin)
    bd = _mod(s, 'bim_dialogs')
    types = _mod(s, 'parameters_arq').load_defaults(s.document)['wall_types']
    dlg, read = bd.wall_form(CTX, {'thickness': 0.3, 'name': 'Muro'}, types)
    w = dlg._arq
    assert w['type'].currentData() is None                     # generic
    i = w['type'].findData('Tabique LHD 7 guarnecido')
    w['type'].setCurrentIndex(i)
    assert w['layers'].rowCount() == 3 and not w['thickness'].isEnabled()
    v = read()
    assert v['thickness'] == pytest.approx(0.10) and v['type_name'] == 'Tabique LHD 7 guarnecido'
    assert [round(l[0], 3) for l in v['layers']] == [0.015, 0.07, 0.015]
    w['type'].setCurrentIndex(0)                                # back to generic
    w['thickness'].setValue(0.25)
    v = read()
    assert v['layers'] == [] and v['type_name'] == 'Muro 0,25' and w['thickness'].isEnabled()


def test_muro_con_tipo_de_la_ficha_guarda_las_capas(plugin, qapp, monkeypatch):
    s = Session(plugin)
    bd = _mod(s, 'bim_dialogs')
    types = _mod(s, 'parameters_arq').load_defaults(s.document)['wall_types']
    pyl = next(t for t in types if t['name'] == 'PYL 98/48')
    monkeypatch.setattr(bd, 'available', lambda ctx: True)
    monkeypatch.setattr(bd, 'wall_properties', lambda ctx, d, types=None: {
        **d, 'thickness': pyl['thickness'], 'type_name': pyl['name'], 'name': pyl['name'],
        'material': pyl['material'], 'layers': pyl['layers'], 'ifc_class': 'IfcWall'})
    t = s.tool('MURO')
    t.on_point((0, 0))
    t.on_point((4, 0))
    m = next(iter(s.meta(e) for e in s.walls().values()))
    assert m['type_name'] == 'PYL 98/48' and len(m['layers']) == 3
    assert m['thickness'] == pytest.approx(0.098)


def test_editar_muro_cambia_o_quita_las_capas(plugin):
    s = Session(plugin)
    t = s.tool('MURO')
    t.thickness = 0.10
    t.on_point((0, 0))
    t.on_point((4, 0))
    av = _mod(s, 'architectural_v10')
    e = next(iter(s.walls().values()))
    s.history.execute(av.edit_wall(e, thickness=0.10, type_name='Tabique',
                                   layers=[[0.015, 'Yeso'], [0.07, 'LHD'], [0.015, 'Yeso']]))
    assert len(s.meta(e)['layers']) == 3
    s.history.execute(av.edit_wall(e, thickness=0.12))       # thickness by hand: layers dropped
    assert 'layers' not in s.meta(e)


def test_tiposmuro_ficha_edita_el_catalogo(plugin, qapp):
    s = Session(plugin)
    bd = _mod(s, 'bim_dialogs')
    types = _mod(s, 'parameters_arq').load_defaults(s.document)['wall_types']
    dlg, read = bd.wall_types_form(CTX, types)
    w = dlg._arq
    assert w['list'].count() == len(types)
    w['new']()
    w['name'].setText('Muro de prueba')
    w['add_layer']()
    out = read()
    mine = next(t for t in out if t['name'] == 'Muro de prueba')
    assert len(mine['layers']) == 2 and mine['thickness'] == pytest.approx(0.11)
    assert len(out) == len(types) + 1
    w['list'].setCurrentRow(0)                               # moving away keeps the edit
    first = w['name'].text()
    w['name'].setText(first + ' bis')
    w['list'].setCurrentRow(1)
    assert any(t['name'] == first + ' bis' for t in read())
    w['delete']()
    assert len(read()) == len(types)
    w['name'].setText('Termoarcilla 14')                      # a name already in use
    with pytest.raises(ValueError):
        read()


def test_tiposmuro_y_usosarq_guardan_lo_de_la_ficha(plugin, monkeypatch):
    s = Session(plugin)
    bd = _mod(s, 'bim_dialogs')
    pa = _mod(s, 'parameters_arq')
    out = []
    ctx = type('C', (), {'document': s.document, 'echo': out.append, 'execute': s.history.execute})()
    monkeypatch.setattr(bd, 'available', lambda ctx: True)
    monkeypatch.setattr(bd, 'wall_types_dialog',
                        lambda ctx, types: [{'name': 'Único', 'layers': [[0.2, 'Hormigón']]}])
    pa.tipos_muro(ctx)
    assert [t['name'] for t in pa.load_defaults(s.document)['wall_types']] == ['Único']
    monkeypatch.setattr(bd, 'usos_dialog', lambda ctx, u: {
        'tipo_edificio_cee': 'EdificioUsoTerciario', 'uso_dbhe': 'otros usos',
        'carga_dbhe': 'alta', 'horario_dbhe': '16', 'uso_dbsi': 'Docente'})
    pa.usos_arq(ctx)
    u = pa.load_defaults(s.document)['usos']
    assert u['uso_dbsi'] == 'Docente' and u['carga_dbhe'] == 'alta'
    s.history.undo()
    assert pa.load_defaults(s.document)['usos']['uso_dbsi'] == 'Residencial Vivienda'


def test_ficha_de_usos(plugin, qapp):
    s = Session(plugin)
    bd = _mod(s, 'bim_dialogs')
    u = _mod(s, 'parameters_arq').load_defaults(s.document)['usos']
    dlg, read = bd.usos_form(CTX, u)
    w = dlg._arq
    assert not w['carga'].isEnabled()
    w['dbhe'].setCurrentIndex(w['dbhe'].findData('otros usos'))
    assert w['carga'].isEnabled()
    w['dbsi'].setCurrentText('Hospitalario')
    v = read()
    assert v['uso_dbhe'] == 'otros usos' and v['carga_dbhe'] == 'media' and v['horario_dbhe'] == '12'
    assert v['uso_dbsi'] == 'Hospitalario'
    _mod(s, 'parameters_arq').validate_defaults({**_mod(s, 'parameters_arq').load_defaults(s.document),
                                                 'usos': v})


def test_las_ordenes_cuelgan_sus_fichas_de_la_ventana(plugin, qapp):
    """A command's context (PluginContext) has the window as host: the sheets
    must be available there too (before, only tools had them)."""
    from PySide6.QtWidgets import QMainWindow
    s = Session(plugin)
    bd = _mod(s, 'bim_dialogs')
    win = QMainWindow()
    assert bd.available(type('C', (), {'host': win})())
    assert not bd.available(type('C', (), {'host': object()})())

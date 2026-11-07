# SPDX-License-Identifier: GPL-3.0-or-later
"""Usos del edificio, altura habitable por tipo de estancia, paso libre DB-SUA e iconos."""
import re
from importlib import import_module
from pathlib import Path

import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401  (fixture)
from tests.test_recintos import _cmd_ctx, _vivienda
from tests.test_wall_tools import Session

ROOT = Path(__file__).resolve().parents[1]


def _mod(s, name):
    return import_module(s.plugin.tools['PILAR'].__module__.rsplit('.', 1)[0] + '.' + name)


def test_usos_independientes_y_exportados(plugin):
    s = Session(plugin)
    _vivienda(s)
    out = []
    ctx = _cmd_ctx(s)
    ctx.echo = out.append
    cmd = s.plugin.commands['USOSARQ']
    assert cmd(ctx)['tipo_edificio_cee'] == 'ViviendaUnifamiliar'
    cmd(ctx, 'edificio', 'EdificioUsoTerciario')
    cmd(ctx, 'dbhe', 'otros', 'media', '12')
    cmd(ctx, 'dbsi', 'Docente')
    cmd(ctx, 'edificio', 'Chalet')                       # no admitido: no cambia nada
    assert any('valores admitidos' in o for o in out)
    r = s.tool('RECINTO')
    r.on_point((2, 2))
    data = s.export(None)
    assert data['project']['TipoDeEdificio'] == 'EdificioUsoTerciario'
    assert data['project']['UsoDBHE'] == 'otros usos' and data['project']['CargaInternaDBHE'] == 'media'
    sp = next(e for e in data['elements'] if e['ifc_class'] == 'IfcSpace')
    assert sp['psets']['ARQ_Usos']['UsoDBSI'] == 'Docente'
    s.history.undo()                                      # deshacer el recinto
    s.history.undo()                                      # y la clasificación DB-SI
    assert cmd(ctx)['uso_dbsi'] == 'Residencial Vivienda'


def test_bano_habitable_a_2_20(plugin):
    sm = _mod(Session(plugin), 'superficies')
    room = {'area': 4.0, 'outer': [(0, 0), (2, 0), (2, 2), (0, 2)]}
    assert sm.evaluate({'name': 'Baño', 'height': 2.25}, room)['habitable']
    assert sm.evaluate({'name': 'Pasillo', 'height': 2.20}, room)['habitable']
    ev = sm.evaluate({'name': 'Dormitorio', 'height': 2.25}, room)
    assert not ev['habitable'] and ev['computable'] == pytest.approx(4.0)


def test_paso_libre_db_sua(plugin):
    op = _mod(Session(plugin), 'openings')
    base = {'type': 'door', 'offset': 0, 'width': 0.885, 'sill': 0, 'height': 2.1}
    assert op.clear_width(base) == pytest.approx((0.825, 0.785))
    assert op.sua_accessible(base)
    assert not op.sua_accessible({**base, 'width': 0.785})                # hoja de 725
    assert op.sua_accessible({**base, 'width': 0.83, 'operation': 'SLIDING', 'frame_width': 0.0})
    assert not op.sua_accessible({**base, 'width': 1.45, 'leaves': 2, 'leaf': 0.695, 'leaf2': 0.695})
    assert op.sua_accessible({**base, 'width': 1.45, 'leaves': 2})                # 825 + 565


def test_todos_los_iconos_existen():
    src = (ROOT / 'arquitectura' / '__init__.py').read_text(encoding='utf-8')
    names = set(re.findall(r'glyph / "([a-z]+\.svg)"', src))
    assert len(names) >= 25
    for n in names:
        svg = (ROOT / 'arquitectura' / 'icons' / n).read_text(encoding='utf-8')
        assert svg.startswith('<svg') and 'viewBox="0 0 24 24"' in svg, n

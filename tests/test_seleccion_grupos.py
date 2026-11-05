# SPDX-License-Identifier: GPL-3.0-or-later
"""Fase 1 — un muro se selecciona, copia y desplaza como objeto completo.

Caso real (Windows, 5-11-2026): con el eje BIM en una capa apagada, el
usuario designó las líneas de contorno visibles y las copió; quedó un
«recinto fantasma» dibujado sin muros BIM. Ahora cada muro es un GRUPO
seleccionable nativo (eje + sus líneas) y UNIONESARQ repara lo que dejen los
comandos genéricos. Todo con IngeCAD oficial: Document, History, la
expansión de selección por grupos (core.groups.expand) y COPY/MOVE reales.
"""
import shutil
import sys

import ezdxf
import pytest
from core import actions
from core.groups import expand

from tests.test_ingecad_integration import ctx_for, plugin, reactor_on  # noqa: F401  (fixtures)


def _arch():
    return sys.modules[[m for m in sys.modules if m.endswith('.architectural') and 'arquitectura' in m][0]]


def _kind(document, kind):
    a = _arch()
    return [e for e in document.doc.modelspace() if (a.metadata(e) or {}).get('kind') == kind]


def _groups(document):
    return [(n, g) for n, g in document.doc.groups if n.startswith('ARQ_')]


def _validar(plugin, ctx):
    from importlib import import_module
    q = import_module(plugin.commands['ARQVALIDAR'].__module__)
    return q.audit_architecture(ctx.host.document)['incidencias']


def _pick_wall(host, line):
    """What IngeCAD's selection takes when the user clicks ``line``."""
    db = host.document.doc.entitydb
    return [db.get(h) for h in expand(host.document, {line.dxf.handle})]


@pytest.mark.parametrize('name', ['34.dxf', '35.dxf', '36.dxf'])
def test_un_grupo_por_muro_y_deshacer(plugin, tmp_path, name):
    ctx, host, out = ctx_for(name, tmp_path)
    assert not _groups(host.document)
    plugin.commands['UNIONESARQ'](ctx)
    walls = _kind(host.document, 'wall')
    groups = _groups(host.document)
    assert len(groups) == len(walls)
    for _n, g in groups:
        kinds = sorted((_arch().metadata(e) or {}).get('kind') for e in g)
        assert kinds.count('wall') == 1 and kinds.count('junction_edge') >= 2
        assert int(g.dxf.selectable) == 1
    names = sorted(n for n, _ in groups)
    host.history.undo()
    assert not _groups(host.document)
    host.history.redo()
    assert sorted(n for n, _ in _groups(host.document)) == names
    assert not [i for i in _validar(plugin, ctx) if 'Contorno' in i or 'grupo' in i]


def test_pinchar_una_linea_selecciona_el_muro(plugin, tmp_path):
    ctx, host, out = ctx_for('36.dxf', tmp_path)
    plugin.commands['UNIONESARQ'](ctx)
    a = _arch()
    line = _kind(host.document, 'junction_edge')[0]
    owner = a.metadata(line)['wall_ids'][0]
    picked = _pick_wall(host, line)
    kinds = [(a.metadata(e) or {}).get('kind') for e in picked]
    assert kinds.count('wall') == 1
    assert a.metadata(next(e for e in picked if a.metadata(e)['kind'] == 'wall'))['id'] == owner
    assert all(a.metadata(e).get('wall_ids', [owner]) == [owner] for e in picked)


def test_recinto_fantasma_detectado_y_limpiado(plugin, tmp_path):
    """El caso de Windows: copiar solo las líneas visibles (sin grupos)."""
    ctx, host, out = ctx_for('36.dxf', tmp_path)
    plugin.commands['UNIONESARQ'](ctx)
    lines = _kind(host.document, 'junction_edge')
    n = len(lines)
    host.history.execute(actions.copy_entities(lines[:8], 0.0, 40.0))
    assert len(_kind(host.document, 'junction_edge')) == n + 8
    issues = _validar(plugin, ctx)
    assert any('8 línea(s) sin muro BIM' in i for i in issues), issues
    plugin.commands['UNIONESARQ'](ctx)
    assert len(_kind(host.document, 'junction_edge')) == n
    assert not [i for i in _validar(plugin, ctx) if 'Contorno' in i]
    host.history.undo()                      # UNIONESARQ deshecho: vuelve el fantasma
    assert len(_kind(host.document, 'junction_edge')) == n + 8


def test_copiar_muro_designado_por_su_contorno(plugin, tmp_path):
    ctx, host, out = ctx_for('36.dxf', tmp_path)
    plugin.commands['UNIONESARQ'](ctx)
    a = _arch()
    nwalls = len(_kind(host.document, 'wall'))
    line = _kind(host.document, 'junction_edge')[0]
    original = next(e for e in _pick_wall(host, line) if a.metadata(e)['kind'] == 'wall')
    host.history.execute(actions.copy_entities(_pick_wall(host, line), 0.0, 40.0))
    walls = _kind(host.document, 'wall')
    assert len(walls) == nwalls + 1                       # el objeto BIM viaja con su dibujo
    assert any('duplicado' in i for i in _validar(plugin, ctx))
    plugin.commands['UNIONESARQ'](ctx)
    ids = [a.metadata(w)['id'] for w in walls]
    assert len(set(ids)) == nwalls + 1
    copy = max(walls, key=lambda w: int(w.dxf.handle, 16))
    assert a.metadata(copy)['copied_from'] == a.metadata(original)['id']
    assert a.metadata(copy)['a'][1] == pytest.approx(a.metadata(original)['a'][1] + 40)
    assert len(_groups(host.document)) == nwalls + 1
    assert not [i for i in _validar(plugin, ctx)
                if 'duplicado' in i or 'Contorno' in i or 'grupo' in i]
    data = plugin.commands['EXPORTARBIM'](ctx, str(tmp_path / 'c.arqbim'))
    assert sum(e['ifc_class'] == 'IfcWall' for e in data['elements']) == nwalls + 1
    assert len({e['guid'] for e in data['elements']}) == len(data['elements'])
    host.history.undo()                                   # un paso: identidad y grupos vuelven
    assert len({a.metadata(w)['id'] for w in walls}) == nwalls
    assert len(_groups(host.document)) == nwalls


def test_desplazar_muro_mantiene_dibujo_y_sincroniza(plugin, tmp_path):
    ctx, host, out = ctx_for('34.dxf', tmp_path)
    plugin.commands['UNIONESARQ'](ctx)
    a = _arch()
    line = _kind(host.document, 'junction_edge')[0]
    picked = _pick_wall(host, line)
    wall = next(e for e in picked if a.metadata(e)['kind'] == 'wall')
    ay = a.metadata(wall)['a'][1]
    host.history.execute(actions.move_entities(picked, 0.0, 0.5))
    # el eje CAD y su contorno se movieron juntos; el XDATA aún no
    assert a.metadata(wall)['a'][1] == pytest.approx(ay)
    assert any('eje CAD diferente' in i for i in _validar(plugin, ctx))
    out.clear()
    plugin.commands['UNIONESARQ'](ctx)
    assert any('actualizados desde la geometría CAD' in o for o in out), out
    assert a.metadata(wall)['a'][1] == pytest.approx(ay + 0.5)
    assert not [i for i in _validar(plugin, ctx) if 'eje CAD' in i or 'Contorno' in i]


def test_grupos_se_guardan_en_el_dxf(plugin, tmp_path):
    ctx, host, out = ctx_for('35.dxf', tmp_path)
    plugin.commands['UNIONESARQ'](ctx)
    n = len(_groups(host.document))
    path = tmp_path / 'guardado.dxf'
    host.document.doc.saveas(path)
    again = ezdxf.readfile(path)
    groups = [(k, g) for k, g in again.groups if k.startswith('ARQ_')]
    assert len(groups) == n and all(int(g.dxf.selectable) == 1 for _k, g in groups)


def test_con_reactor_la_copia_queda_completa_sin_unionesarq(plugin, tmp_path, reactor_on):
    ctx, host, out = ctx_for('36.dxf', tmp_path)
    plugin.commands['UNIONESARQ'](ctx)
    a = _arch()
    nwalls = len(_kind(host.document, 'wall'))
    nlines = len(_kind(host.document, 'junction_edge'))
    line = _kind(host.document, 'junction_edge')[0]
    host.history.execute(actions.copy_entities(_pick_wall(host, line), 0.0, 40.0))
    walls = _kind(host.document, 'wall')
    assert len({a.metadata(w)['id'] for w in walls}) == nwalls + 1
    assert len(_groups(host.document)) == nwalls + 1
    assert not [i for i in _validar(plugin, ctx)
                if 'duplicado' in i or 'Contorno' in i or 'grupo' in i]
    host.history.undo()                                   # COPIA + reparación: un paso
    assert len(_kind(host.document, 'wall')) == nwalls
    assert len(_kind(host.document, 'junction_edge')) == nlines
    assert len(_groups(host.document)) == nwalls


def test_lineas_desvinculadas_no_se_guardan_y_rehacer_conserva_objetos(plugin, tmp_path):
    ctx, host, out = ctx_for('36.dxf', tmp_path)
    old = len(_kind(host.document, 'junction_edge'))
    assert old > 0                                   # 36.dxf trae el contorno v1.4
    plugin.commands['UNIONESARQ'](ctx)
    lines = sorted(e.dxf.handle for e in _kind(host.document, 'junction_edge'))
    groups = sorted(n for n, _ in _groups(host.document))
    for _ in range(2):
        host.history.undo()
        assert len(_kind(host.document, 'junction_edge')) == old
        host.history.redo()
        assert sorted(e.dxf.handle for e in _kind(host.document, 'junction_edge')) == lines
        assert sorted(n for n, _ in _groups(host.document)) == groups
    path = tmp_path / 'g.dxf'
    host.document.doc.saveas(path)
    again = ezdxf.readfile(path)
    a = _arch()
    saved = [e for e in again.modelspace() if (a.metadata(e) or {}).get('kind') == 'junction_edge']
    assert sorted(e.dxf.handle for e in saved) == lines
    auditor = again.audit()
    assert not auditor.has_errors, [str(e) for e in auditor.errors]

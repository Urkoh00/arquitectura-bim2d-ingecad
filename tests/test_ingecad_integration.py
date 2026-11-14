"""The plugin loaded by IngeCAD's REAL loader (core.plugins.load_plugin),
commands run through a real Document + History (undo/redo). No stubs of
IngeCAD itself: only the window is replaced by a minimal host."""
import sys, json, shutil
from pathlib import Path
import pytest
from core.document import Document
from core.commands import History
from core.plugins import load_plugin, PluginContext

PLUG = Path(__file__).resolve().parents[1] / 'arquitectura'
DXF = Path(__file__).resolve().parent / 'dxf'

class Tools:
    def __init__(self, history): self.history = history
    def _execute(self, cmd): self.history.execute(cmd)

class Host:
    def __init__(self, document):
        self.document = document
        self.history = History(document)
        self.tools = Tools(self.history)

@pytest.fixture(scope='module')
def plugin(tmp_path_factory):
    d = tmp_path_factory.mktemp('plugins') / 'arquitectura'
    shutil.copytree(PLUG, d)
    lp = load_plugin(d, bundled=False)
    assert lp.available, lp.reason
    return lp.spec

def ctx_for(name, tmp_path):
    src = tmp_path / name
    shutil.copy(DXF / name, src)
    document = Document.load(src)
    host = Host(document)
    out = []
    return PluginContext(host=host, echo=out.append), host, out

def junction_edges(spec_module, document):
    return [e for e in document.doc.modelspace()
            if (spec_module.metadata(e) or {}).get('kind') == 'junction_edge']

def test_spec(plugin):
    assert plugin.version == '1.22.0-dev'
    assert 'EXPORTARBIM' in plugin.commands and 'UNIONESARQ' in plugin.commands

@pytest.mark.parametrize('name,expected', [('36.dxf', 16), ('35.dxf', 16), ('34.dxf', 8)])
def test_unionesarq_with_undo(plugin, tmp_path, name, expected):
    ctx, host, out = ctx_for(name, tmp_path)
    arch = sys.modules[[m for m in sys.modules if m.endswith('.architectural') and 'arquitectura' in m][0]]
    before = len(junction_edges(arch, host.document))
    plugin.commands['UNIONESARQ'](ctx)
    assert any('16' in o or str(expected) in o for o in out), out
    segs = junction_edges(arch, host.document)
    assert len(segs) == expected
    assert all(len(arch.metadata(e)['wall_ids']) == 1 for e in segs)
    host.history.undo()
    assert len(junction_edges(arch, host.document)) == before
    host.history.redo()
    assert len(junction_edges(arch, host.document)) == expected

def test_exportarbim(plugin, tmp_path):
    ctx, host, out = ctx_for('34.dxf', tmp_path)
    dest = tmp_path / 'modelo.arqbim'
    data = plugin.commands['EXPORTARBIM'](ctx, str(dest))
    assert dest.is_file(), out
    assert sum(e['ifc_class'] == 'IfcWall' for e in data['elements']) == 4
    assert sum(e['ifc_class'] == 'IfcColumn' for e in data['elements']) == 6
    again = json.loads(dest.read_text())
    assert [e['guid'] for e in again['elements']] == [e['guid'] for e in data['elements']]

def test_copy_blocks_export_until_unionesarq(plugin, tmp_path):
    """A generic COPY duplicates the XDATA id: the export does not stop (the
    operator decides, 9-11-2026) but leaves the copy out and says so;
    UNIONESARQ gives the copy (newest handle) a new identity and then it is
    exported too."""
    ctx, host, out = ctx_for('36.dxf', tmp_path)
    msp = host.document.doc.modelspace()
    arch = sys.modules[[m for m in sys.modules if m.endswith('.architectural') and 'arquitectura' in m][0]]
    walls = [e for e in msp if (arch.metadata(e) or {}).get('kind') == 'wall']
    wall = walls[0]
    copy = wall.copy(); msp.add_entity(copy); copy.translate(0, 40, 0)
    data = plugin.commands['EXPORTARBIM'](ctx, str(tmp_path / 'x.arqbim'))
    assert any('duplicado' in o.lower() for o in out)
    assert sum(e['ifc_class'] == 'IfcWall' for e in data['elements']) == len(walls)
    plugin.commands['UNIONESARQ'](ctx)
    assert any('identidad BIM nueva' in o for o in out), out
    assert arch.metadata(copy)['copied_from'] == arch.metadata(wall)['id']
    assert 'copied_from' not in arch.metadata(wall)
    data = plugin.commands['EXPORTARBIM'](ctx, str(tmp_path / 'y.arqbim'))
    assert data is not None
    assert sum(e['ifc_class'] == 'IfcWall' for e in data['elements']) == len(walls) + 1

def test_move_uses_cad_axis(plugin, tmp_path):
    """MOVE with a generic command: XDATA a/b goes stale; the exported axis is the CAD one."""
    ctx, host, out = ctx_for('36.dxf', tmp_path)
    msp = host.document.doc.modelspace()
    arch = sys.modules[[m for m in sys.modules if m.endswith('.architectural') and 'arquitectura' in m][0]]
    wall = next(e for e in msp if (arch.metadata(e) or {}).get('kind') == 'wall')
    wall.translate(0, 1, 0)
    data = plugin.commands['EXPORTARBIM'](ctx, str(tmp_path / 'm.arqbim'))
    el = next(e for e in data['elements'] if e['id'] == arch.metadata(wall)['id'])
    assert el['params']['a'][1] == pytest.approx(arch.metadata(wall)['a'][1] + 1)
    assert any('eje CAD' in i for i in data['issues'])


# -- with IngeCAD's plugin reactors (IngeCAD 0.8: core.commands.register_reactor) ---

def _arch():
    return sys.modules[[m for m in sys.modules if m.endswith('.architectural') and 'arquitectura' in m][0]]

@pytest.fixture
def reactor_on(plugin):
    from core import commands
    if not hasattr(commands, 'register_reactor'):
        pytest.skip('IngeCAD sin reactores para plugins (anterior a 0.8)')
    for r in plugin.reactors:
        commands.register_reactor(r, 'arquitectura-pruebas')
    yield
    commands.unregister_reactors('arquitectura-pruebas')

def _walls(document):
    a = _arch()
    return [e for e in document.doc.modelspace() if (a.metadata(e) or {}).get('kind') == 'wall']

def test_reactor_move_syncs_xdata_and_outline_one_undo(plugin, tmp_path, reactor_on):
    from core import actions
    ctx, host, out = ctx_for('36.dxf', tmp_path)
    plugin.commands['UNIONESARQ'](ctx)
    a = _arch()
    wall = _walls(host.document)[0]
    before = dict(a.metadata(wall))
    host.history.execute(actions.move_entities([wall], 0.0, 1.0))
    after = a.metadata(wall)
    assert after['id'] == before['id']
    assert after['a'][1] == pytest.approx(before['a'][1] + 1)
    assert not any('eje CAD' in i for i in
                   plugin.commands['EXPORTARBIM'](ctx, str(tmp_path / 'm.arqbim'))['issues'])
    host.history.undo()                                   # ONE undo
    assert a.metadata(wall)['a'] == before['a']

def test_reactor_copy_gets_new_identity(plugin, tmp_path, reactor_on):
    from core import actions
    ctx, host, out = ctx_for('36.dxf', tmp_path)
    plugin.commands['UNIONESARQ'](ctx)
    n = len(_walls(host.document))
    wall = _walls(host.document)[0]
    host.history.execute(actions.copy_entities([wall], 0.0, 40.0))
    walls = _walls(host.document)
    ids = [_arch().metadata(w)['id'] for w in walls]
    assert len(walls) == n + 1 and len(set(ids)) == n + 1
    data = plugin.commands['EXPORTARBIM'](ctx, str(tmp_path / 'c.arqbim'))
    assert data is not None and sum(e['ifc_class'] == 'IfcWall' for e in data['elements']) == n + 1
    host.history.undo()
    assert len(_walls(host.document)) == n

def test_reactor_mirror_keep_source(plugin, tmp_path, reactor_on):
    from core import actions
    ctx, host, out = ctx_for('34.dxf', tmp_path)
    plugin.commands['UNIONESARQ'](ctx)
    sel = list(_walls(host.document))
    host.history.execute(actions.mirror_entities(sel, (0, 30), (100, 30), keep_source=True))
    ids = [_arch().metadata(w)['id'] for w in _walls(host.document)]
    assert len(ids) == 8 and len(set(ids)) == 8
    data = plugin.commands['EXPORTARBIM'](ctx, str(tmp_path / 'r.arqbim'))
    assert data and not data['issues']


# -- fallos vistos en Windows (5-11-2026) ---------------------------------------------

def test_unionesarq_pide_regeneracion(plugin):
    mod = sys.modules[[m for m in sys.modules if m.endswith('.wall_network') and 'arquitectura' in m][0]]
    assert mod.RegenerateContoursCommand.needs_regen is True

def test_exportarbim_dialogo_con_ventana_real(plugin, tmp_path, monkeypatch):
    """ctx.host es la ventana principal: host.window es un MÉTODO de Qt."""
    from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog, QWidget
    app = QApplication.instance() or QApplication([])
    src = tmp_path / '34.dxf'; shutil.copy(DXF / '34.dxf', src)
    class Win(QMainWindow):
        pass
    win = Win()
    win.document = Document.load(src)
    win.history = History(win.document)
    win.tools = Tools(win.history)
    dest = tmp_path / 'dlg.arqbim'
    seen = {}
    def fake(parent, *a, **k):
        seen['parent'] = parent
        if not (parent is None or isinstance(parent, QWidget)):
            raise TypeError('wrong argument types')
        return str(dest), ''
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', staticmethod(fake))
    out = []
    data = plugin.commands['EXPORTARBIM'](PluginContext(host=win, echo=out.append))
    assert seen['parent'] is win, out
    assert data is not None and dest.is_file(), out

def test_contorno_igual_al_validado_v142(plugin):
    """El contorno nuevo de 36.dxf coincide línea a línea con 36_contornos_v1.4.2.dxf."""
    import ezdxf
    arch = _arch()
    def segs(doc):
        out = set()
        for e in doc.modelspace():
            if e.dxftype() == 'LINE' and (arch.metadata(e) or {}).get('kind') == 'junction_edge':
                a = (round(e.dxf.start.x, 6), round(e.dxf.start.y, 6)); b = (round(e.dxf.end.x, 6), round(e.dxf.end.y, 6))
                out.add(tuple(sorted((a, b))))
        return out
    ref = segs(ezdxf.readfile(DXF / '36_contornos_v1.4.2.dxf'))
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        ctx, host, out = ctx_for('36.dxf', Path(d))
        plugin.commands['UNIONESARQ'](ctx)
        new = segs(host.document.doc)
    assert len(ref) == 16 and new == ref, (sorted(ref - new), sorted(new - ref))

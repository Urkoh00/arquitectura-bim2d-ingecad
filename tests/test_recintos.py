# SPDX-License-Identifier: GPL-3.0-or-later
"""Recintos (IfcSpace) por clic, asociativos a los muros, sobre IngeCAD real."""
import pytest
from shapely.geometry import Polygon
from shapely.ops import unary_union

from arquitectura.geom import junctions as J
from arquitectura.geom import solids as S
from arquitectura.geom import spaces as SP
from core import actions

from tests.test_ingecad_integration import plugin  # noqa: F401  (fixture)
from tests.test_wall_tools import Session, draw


def _vivienda(s):
    """8 x 5 m de muros de 0,30 al eje y un tabique de 0,10 en x = 4."""
    t = s.tool('MURO')
    t.thickness, t.reference = 0.30, 'eje'
    draw(t, (0, 0), (8, 0), (8, 5), (0, 5), (0, 0))
    t = s.tool('MURO')
    t.thickness = 0.10
    draw(t, (4, 0.15), (4, 4.85))                   # T en ambos extremos


def _spaces(s):
    return [e for e in s.document.doc.modelspace() if (s.meta(e) or {}).get('kind') == 'space']


def _labels(s):
    return [e for e in s.document.doc.modelspace() if (s.meta(e) or {}).get('kind') == 'space_label']


def test_recintos_por_clic_superficies_exactas(plugin):
    s = Session(plugin)
    _vivienda(s)
    t = s.tool('RECINTO')
    t.on_option('n')
    t.on_option('Salón')
    t.on_point((2, 2))
    t.on_point((6, 2))
    t.on_point((2, 3))                              # la misma estancia: rechazado
    t.on_point((4, 2))                              # dentro del tabique: rechazado
    t.on_point((20, 20))                            # fuera del edificio: rechazado
    sp = _spaces(s)
    assert [s.meta(e)['name'] for e in sp] == ['Salón', 'Recinto 2']
    assert [s.meta(e)['area'] for e in sp] == pytest.approx([3.80 * 4.70, 3.80 * 4.70])
    assert any('ya es el recinto' in o for o in s.out)
    assert any('dentro de un muro' in o for o in s.out)
    assert any('no está cerrada' in o for o in s.out)
    assert len(_labels(s)) == 2 and '17,86 m²' in _labels(s)[0].dxf.text
    assert not [i for i in s.issues() if 'Recinto' in i or 'Contorno' in i]


def test_exportacion_ifcspace_y_muros_exteriores(plugin, tmp_path):
    s = Session(plugin)
    _vivienda(s)
    t = s.tool('RECINTO')
    t.on_option('a')
    t.on_option('2,50')
    t.on_point((2, 2))
    data = s.export(tmp_path)
    space = next(e for e in data['elements'] if e['ifc_class'] == 'IfcSpace')
    q = space['quantities']
    assert q['NetFloorArea'] == pytest.approx(17.86) and q['Height'] == pytest.approx(2.5)
    assert q['NetVolume'] == pytest.approx(17.86 * 2.5)
    assert q['NetPerimeter'] == pytest.approx(2 * (3.8 + 4.7))
    faces = [(f['outer'], f['holes']) for f in space['faces']]
    assert S.face_volume(faces) == pytest.approx(17.86 * 2.5)        # sólido estanco
    walls = [e for e in data['elements'] if e['ifc_class'] == 'IfcWall']
    ext = sorted(e['psets']['Pset_WallCommon']['IsExternal'] for e in walls)
    assert ext == [False, True, True, True, True]                    # el tabique es interior
    # recintos + huellas = superficie bruta, sin solapes ni huecos
    polys = [Polygon(o, h) for e in data['elements'] for o, h in e['footprint']]
    assert sum(p.area for p in polys) == pytest.approx(unary_union(polys).area, abs=1e-9)


def test_recinto_sigue_al_tabique_y_deshacer(plugin):
    s = Session(plugin)
    _vivienda(s)
    t = s.tool('RECINTO')
    t.on_point((2, 2))
    t.on_point((6, 2))
    a0, b0 = (s.meta(e)['area'] for e in _spaces(s))
    tab = [w for w in s.walls().values() if s.meta(w)['thickness'] == 0.1][0]
    s.history.execute(actions.move_entities([tab], 1.0, 0.0))     # MOVE genérico del eje
    s.plugin.commands['UNIONESARQ'](_cmd_ctx(s))
    a1, b1 = (s.meta(e)['area'] for e in _spaces(s))
    assert a1 == pytest.approx(a0 + 4.70) and b1 == pytest.approx(b0 - 4.70)
    assert '22,56 m²' in ' '.join(e.dxf.text for e in _labels(s))
    s.history.undo()                                               # UNIONESARQ deshecho
    assert [s.meta(e)['area'] for e in _spaces(s)] == pytest.approx([a0, b0])
    assert len(_labels(s)) == 2


def test_pilar_exento_es_una_isla(plugin):
    s = Session(plugin)
    _vivienda(s)
    from importlib import import_module
    cols = import_module(s.plugin.tools['PILAR'].__module__.rsplit('.', 1)[0] + '.columns')
    s.history.execute(cols.column_command((2.0, 2.0), {'shape': 'rect', 'width': 0.30, 'depth': 0.30,
                                                       'rotation': 0.0, 'height': 2.7, 'base': 0.0}))
    s.plugin.commands['UNIONESARQ'](_cmd_ctx(s))
    t = s.tool('RECINTO')
    t.on_point((1, 1))
    sp = _spaces(s)[0]
    assert s.meta(sp)['area'] == pytest.approx(17.86 - 0.09)
    assert len(s.meta(sp)['islands']) == 1


def test_copiar_un_recinto_a_otra_estancia(plugin):
    s = Session(plugin)
    _vivienda(s)
    t = s.tool('RECINTO')
    t.on_point((2, 2))
    src = _spaces(s)[0]
    s.history.execute(actions.copy_entities([src], 4.0, 0.0))     # copia al otro lado del tabique
    s.plugin.commands['UNIONESARQ'](_cmd_ctx(s))
    sp = _spaces(s)
    ids = {s.meta(e)['id'] for e in sp}
    assert len(sp) == 2 and len(ids) == 2                           # identidad nueva
    seeds = sorted(s.meta(e)['seed'][0] for e in sp)
    assert seeds == pytest.approx([2.0, 6.0])                       # la semilla viajó con la copia
    assert not [i for i in s.issues() if 'Recinto' in i]


def test_recinto_abierto_avisa(plugin):
    s = Session(plugin)
    _vivienda(s)
    t = s.tool('RECINTO')
    t.on_point((2, 2))
    west = [w for w in s.walls().values()
            if s.meta(w)['a'] == pytest.approx([0, 5]) and s.meta(w)['b'] == pytest.approx([0, 0])][0]
    s.history.execute(actions.EraseCommand([west]))
    issues = s.issues()
    assert any('no está cerrado' in i for i in issues), issues


def _cmd_ctx(s):
    from core.plugins import PluginContext

    class Tools:
        def _execute(self, cmd):
            s.history.execute(cmd)

    class Host:
        document = s.document
        tools = Tools()
    return PluginContext(host=Host(), echo=s.out.append)

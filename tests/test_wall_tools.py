# SPDX-License-Identifier: GPL-3.0-or-later
"""Fase 2 — herramientas de dibujo de muros sobre IngeCAD real.

Document y History reales; la herramienta recibe clics y texto como desde
la línea de órdenes. ``pick_entity`` imita al de IngeCAD: la entidad más
próxima en una capa encendida (el eje BIM vive en una capa apagada, así que
se designa el muro por su contorno, como hace el usuario)."""
import math
import sys
from dataclasses import dataclass

import pytest
from shapely.geometry import Polygon
from shapely.ops import unary_union

from core.commands import History
from core.document import Document
from tools.base import ToolContext

from tests.test_ingecad_integration import plugin  # noqa: F401  (fixture)


def _arch():
    return sys.modules[[m for m in sys.modules if m.endswith('.architectural') and 'arquitectura' in m][0]]


def _plugin_module(plugin, name):
    mod = plugin.tools['MURO'].__module__.rsplit('.', 1)[0]
    return sys.modules[mod + '.' + name]


@dataclass
class Window:
    document: object


class Services:
    def __init__(self, document):
        self.window = Window(document)

    def pick_entity(self, point, radius=0.05):
        doc = self.window.document.doc
        best = None
        for e in doc.modelspace():
            layer = doc.layers.get(e.dxf.layer) if e.dxf.layer in doc.layers else None
            if layer is not None and layer.is_off():
                continue
            segs = []
            if e.dxftype() == 'LINE':
                segs = [((e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y))]
            elif e.dxftype() == 'LWPOLYLINE':
                pts = [tuple(p) for p in e.get_points('xy')]
                segs = list(zip(pts, pts[1:] + (pts[:1] if e.closed else [])))
            elif e.dxftype() == 'ARC':
                c, r = e.dxf.center, e.dxf.radius
                ang = math.degrees(math.atan2(point[1] - c.y, point[0] - c.x)) % 360
                t0, t1 = e.dxf.start_angle % 360, e.dxf.end_angle % 360
                inside = (t0 <= ang <= t1) if t0 <= t1 else (ang >= t0 or ang <= t1)
                d = abs(math.dist(point, (c.x, c.y)) - r)
                if inside and d <= radius and (best is None or d < best[0]):
                    best = (d, e)
            for a, b in segs:
                d = _dist(point, a, b)
                if d <= radius and (best is None or d < best[0]):
                    best = (d, e)
        return best[1] if best else None


def _dist(p, a, b):
    ab = (b[0] - a[0], b[1] - a[1])
    L2 = ab[0] ** 2 + ab[1] ** 2
    t = 0 if L2 == 0 else max(0, min(1, ((p[0] - a[0]) * ab[0] + (p[1] - a[1]) * ab[1]) / L2))
    return math.dist(p, (a[0] + ab[0] * t, a[1] + ab[1] * t))


class Session:
    def __init__(self, plugin):
        self.plugin = plugin
        self.document = Document.new()
        self.history = History(self.document)
        self.out = []
        self.services = Services(self.document)

    def tool(self, name):
        ctx = ToolContext(execute=self.history.execute, prompt=self.out.append,
                          echo=self.out.append, finish=lambda: self.out.append('<fin>'),
                          services=self.services)
        t = self.plugin.tools[name](ctx)
        t.start()
        return t

    def walls(self):
        a = _arch()
        return {a.metadata(e)['id']: e for e in self.document.doc.modelspace()
                if (a.metadata(e) or {}).get('kind') == 'wall'}

    def meta(self, e):
        return _arch().metadata(e)

    def issues(self):
        from importlib import import_module
        q = import_module(self.plugin.commands['ARQVALIDAR'].__module__)
        return q.audit_architecture(self.document)['incidencias']

    def export(self, tmp_path):
        from importlib import import_module
        ex = import_module(self.plugin.commands['EXPORTARBIM'].__module__.rsplit('.', 1)[0] + '.exchange')
        return ex.build(self.document.doc)


def draw(t, *pts, values=()):
    for v in values:
        t.on_option(v)
    for p in pts:
        t.on_point(p)
    t.on_enter()


def _plan_union(data):
    polys = [Polygon(o, h) for e in data['elements'] for o, h in e['footprint']]
    return unary_union(polys), sum(p.area for p in polys)


def _host(s):
    t = s.tool('MURO')
    t.thickness, t.reference = 0.30, 'eje'
    draw(t, (0, 0), (10, 0))
    return t


# --- MURO -----------------------------------------------------------------------

def test_muro_invertir_cara_e_igual(plugin):
    s = Session(plugin)
    _host(s)
    t = s.tool('MURO')
    t.reference = 'izquierda'
    t.on_option('F5')
    assert t.reference == 'derecha'
    t.on_option('i')
    assert t.reference == 'izquierda'
    t.thickness = 0.09
    t.on_option('G')
    t.on_point((5, 0.15))                          # clic en la cara del muro existente
    assert t.thickness == pytest.approx(0.30) and t.reference == 'eje'


def test_muro_terminado_en_cara_proxima_hace_T(plugin, tmp_path):
    s = Session(plugin)
    _host(s)
    t = s.tool('MURO')
    t.thickness, t.reference = 0.20, 'eje'
    draw(t, (5, 4), (5, 0.15))
    walls = list(s.walls().values())
    assert len(walls) == 2
    host = next(w for w in walls if s.meta(w)['thickness'] == 0.3)
    assert s.meta(host)['a'] == [0, 0] and s.meta(host)['b'] == [10, 0]     # intacto
    data = s.export(tmp_path)
    assert data['joins']['tees'] and not data['issues']
    assert not s.issues() or not [i for i in s.issues() if 'Contorno' in i or 'grupo' in i]


def test_muro_terminado_en_cara_alejada_hace_L_y_un_deshacer(plugin, tmp_path):
    s = Session(plugin)
    _host(s)
    host_id = next(iter(s.walls()))
    t = s.tool('MURO')
    t.thickness, t.reference = 0.20, 'eje'
    draw(t, (6, 4), (6, -0.15))
    walls = s.walls()
    assert len(walls) == 2 and host_id in walls                 # el anfitrión conserva su ID
    hm = s.meta(walls[host_id])
    assert hm['a'] == pytest.approx([0, 0]) and hm['b'] == pytest.approx([6, 0])
    new = next(w for k, w in walls.items() if k != host_id)
    assert s.meta(new)['b'] == pytest.approx([6, 0])
    data = s.export(tmp_path)
    assert not data['joins']['tees'] and data['joins']['nodes']
    union, total = _plan_union(data)
    assert total == pytest.approx(union.area, abs=1e-9)
    ideal = unary_union([Polygon([(0, -0.15), (6.1, -0.15), (6.1, 0.15), (0, 0.15)]),
                         Polygon([(5.9, -0.15), (6.1, -0.15), (6.1, 4), (5.9, 4)])])
    assert union.symmetric_difference(ideal).area < 1e-9
    assert not [i for i in s.issues() if 'Contorno' in i or 'grupo' in i or 'eje CAD' in i]
    s.history.undo()                                           # un paso: muro nuevo + recorte
    walls = s.walls()
    assert list(walls) == [host_id] and s.meta(walls[host_id])['b'] == [10, 0]
    s.history.redo()
    assert len(s.walls()) == 2


def test_L_desplaza_las_carpinterias_del_tramo_conservado(plugin):
    s = Session(plugin)
    _host(s)
    host_id, host = next(iter(s.walls().items()))
    arch_v10 = _plugin_module(plugin, 'architectural_v10')
    s.history.execute(arch_v10.create_opening(host, 6.0, 0.8, 0.0, 2.1, kind='puerta'))
    t = s.tool('MURO')
    t.thickness, t.reference = 0.20, 'eje'
    draw(t, (3, 4), (3, -0.15))                    # conserva el tramo final (7 m > 3 m)
    assert s.meta(s.walls()[host_id])['a'] == pytest.approx([3, 0])
    door = next(e for e in s.document.doc.modelspace()
                if (s.meta(e) or {}).get('kind') == 'opening')
    assert s.meta(door)['offset'] == pytest.approx(3.0)        # misma posición absoluta
    pts = [tuple(p) for p in door.get_points('xy')]
    assert min(p[0] for p in pts) == pytest.approx(6.0)
    s.history.undo()
    assert s.meta(door)['offset'] == pytest.approx(6.0)


def test_L_que_cortaria_una_carpinteria_se_rechaza(plugin):
    s = Session(plugin)
    _host(s)
    host_id, host = next(iter(s.walls().items()))
    arch_v10 = _plugin_module(plugin, 'architectural_v10')
    s.history.execute(arch_v10.create_opening(host, 1.0, 0.8, 0.0, 2.1, kind='puerta'))
    t = s.tool('MURO')
    t.thickness = 0.2
    draw(t, (3, 4), (3, -0.15))
    assert any('no se pudo hacer la esquina' in o for o in s.out), s.out[-5:]
    assert len(s.walls()) == 1 and s.meta(s.walls()[host_id])['a'] == [0, 0]


# --- MUROPARALELO ----------------------------------------------------------------

def _room(s):
    t = s.tool('MURO')
    t.thickness, t.reference = 0.30, 'eje'
    draw(t, (0, 0), (5, 0), (5, 4), (0, 4), (0, 0))


def test_muro_paralelo_dentro_de_un_recinto(plugin, tmp_path):
    s = Session(plugin)
    _room(s)
    n = len(s.walls())
    t = s.tool('MUROPARALELO')
    t.on_option('e')
    t.on_option('0,10')
    t.on_option('2')                        # de los dos tipos de 0,10, el tabique de LHD
    t.on_option('1,5')
    t.on_point((2.5, 0.15))                        # cara interior del muro sur
    t.on_point((2.5, 2.0))                         # lado de la paralela: hacia el interior
    t.on_point((2.5, 3.0))                         # lado del espesor: más allá
    t.on_enter()
    walls = s.walls()
    assert len(walls) == n + 1
    data = s.export(tmp_path)
    new = [e for e in data['elements'] if e['params']['thickness'] == pytest.approx(0.1)][0]
    assert new['quantities']['GrossFootprintArea'] == pytest.approx(0.10 * 4.70)
    assert len([x for x in data['joins']['tees']]) == 2
    union, total = _plan_union(data)
    assert total == pytest.approx(union.area, abs=1e-9)
    assert not [i for i in s.issues() if 'Contorno' in i or 'grupo' in i]


# --- ESTIRAMURO / PIVOTAMURO ------------------------------------------------------

def test_estira_muro_hasta_la_cara_de_otro(plugin, tmp_path):
    s = Session(plugin)
    _host(s)
    t = s.tool('MURO')
    t.thickness = 0.2
    draw(t, (5, 4), (5, 2))
    free_id = [k for k, w in s.walls().items() if s.meta(w)['thickness'] == 0.2][0]
    t = s.tool('ESTIRAMURO')
    t.on_point((5.1, 2.05))                        # contorno del muro libre, cerca de su extremo
    t.on_point((8.0, 0.15))                        # cara del muro anfitrión
    m = s.meta(s.walls()[free_id])
    assert m['b'] == pytest.approx([5, 0.15]) and m['id'] == free_id
    data = s.export(tmp_path)
    assert data['joins']['tees']
    s.history.undo()
    assert s.meta(s.walls()[free_id])['b'] == pytest.approx([5, 2])


def test_pivota_muro(plugin, tmp_path):
    s = Session(plugin)
    _host(s)
    t = s.tool('MURO')
    t.thickness = 0.2
    draw(t, (5, 4), (5, 0.15))                     # T
    pid = [k for k, w in s.walls().items() if s.meta(w)['thickness'] == 0.2][0]
    t = s.tool('PIVOTAMURO')
    t.on_point((5.1, 3.9))                         # cerca del extremo superior
    t.on_point((7, 4))
    m = s.meta(s.walls()[pid])
    assert m['a'] == pytest.approx([7, 4]) and m['b'] == pytest.approx([5, 0.15])
    data = s.export(tmp_path)
    assert data['joins']['tees'] and not data['issues']          # T oblicua
    union, total = _plan_union(data)
    assert total == pytest.approx(union.area, abs=1e-9)

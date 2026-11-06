# SPDX-License-Identifier: GPL-3.0-or-later
"""Fase 2 (repaso del 6-11-2026): tipos de muro, cara automática,
MUROPARALELO de tres clics y encadenado, ESTIRAMURO a punto/cara, DIVIDEMURO."""
import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401  (fixture)
from tests.test_recintos import _cmd_ctx, _spaces
from tests.test_wall_tools import Session, _host, _room, draw


def _new_walls(s, before):
    return {k: w for k, w in s.walls().items() if k not in before}


# --- tipos de muro -------------------------------------------------------------

def test_tiposmuro_lista_anade_quita_y_deshace(plugin):
    s = Session(plugin)
    ctx = _cmd_ctx(s)
    plugin.commands['TIPOSMURO'](ctx)
    assert any('Tabicón 0,1' in o for o in s.out)
    plugin.commands['TIPOSMURO'](ctx, 'Ladrillo', 'perforado', '0,115', 'Cerámico')
    plugin.commands['TIPOSMURO'](ctx, '-Tabique')
    from importlib import import_module
    pa = import_module(plugin.commands['PARAMETROSARQ'].__module__)
    types = pa.load_defaults(s.document)['wall_types']
    names = [t['name'] for t in types]
    assert 'Ladrillo perforado' in names and 'Tabique' not in names
    assert next(t for t in types if t['name'] == 'Ladrillo perforado')['thickness'] == 0.115
    s.history.undo()
    assert 'Tabique' in [t['name'] for t in pa.load_defaults(s.document)['wall_types']]


def test_muro_opcion_tipo(plugin):
    s = Session(plugin)
    t = s.tool('MURO')
    t.on_option('T')
    t.on_option('2')                       # Tabicón
    assert t.thickness == pytest.approx(0.10) and t.bim['type_name'] == 'Tabicón'
    t.on_option('T')
    t.on_option('un')                      # «Un pie» por el principio del nombre
    assert t.thickness == pytest.approx(0.25)
    draw(t, (0, 0), (4, 0))
    w = next(iter(s.walls().values()))
    assert s.meta(w)['type_name'] == 'Un pie' and s.meta(w)['thickness'] == 0.25


# --- cara automática ----------------------------------------------------------

def test_cara_automatica_al_arrancar_en_una_esquina(plugin):
    s = Session(plugin)
    _room(s)                                           # muros de 0,30 al eje
    before = set(s.walls())
    t = s.tool('MURO')
    t.thickness, t.reference = 0.10, 'izquierda'       # cuerpo hacia el muro oeste: imposible
    draw(t, (0.15, 0.15), (0.15, 2.0))
    new = _new_walls(s, before)
    assert len(new) == 1
    m = s.meta(next(iter(new.values())))
    assert m['reference'] == 'derecha'                 # cambiada sola, hacia la estancia
    assert any('cara cambiada automáticamente' in o for o in s.out)
    data = s.export(None)
    el = next(e for e in data['elements'] if e['id'] == m['id'])
    assert el['quantities']['GrossFootprintArea'] == pytest.approx(0.10 * 1.85)   # dentro de la estancia
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    polys = [Polygon(o, h) for e in data['elements'] for o, h in e['footprint']]
    assert sum(q.area for q in polys) == pytest.approx(unary_union(polys).area, abs=1e-9)


def test_cara_automatica_no_actua_en_el_vacio(plugin):
    s = Session(plugin)
    t = s.tool('MURO')
    t.thickness, t.reference = 0.10, 'izquierda'
    draw(t, (20, 20), (20, 22))
    assert s.meta(next(iter(s.walls().values())))['reference'] == 'izquierda'


# --- MUROPARALELO -----------------------------------------------------------------

def test_paralelo_centrado_en_un_eje(plugin):
    s = Session(plugin)
    s.document.doc.modelspace().add_line((0, 0), (6, 0))          # un eje de replanteo
    t = s.tool('MUROPARALELO')
    t.on_option('e')
    t.on_option('0,20')
    t.on_option('0,10')                     # distancia = medio espesor
    t.on_point((3, 0))                      # la línea
    t.on_point((3, 1))                      # paralela por encima
    t.on_point((3, -1))                     # espesor hacia la línea: centrado
    m = s.meta(next(iter(s.walls().values())))
    from arquitectura.geom import drafting as D
    f = D.Frame(m['a'], m['b'], m['thickness'], m['reference'])
    assert (f.point(0, f.lo)[1], f.point(0, f.hi)[1]) in ((pytest.approx(-0.1), pytest.approx(0.1)),
                                                          (pytest.approx(0.1), pytest.approx(-0.1)))


def test_paralelo_encadenado(plugin):
    s = Session(plugin)
    _room(s)
    before = set(s.walls())
    t = s.tool('MUROPARALELO')
    t.on_option('e')
    t.on_option('0,10')
    t.on_option('1')
    t.on_point((2.5, 0.15))                 # cara interior del muro sur
    t.on_point((2.5, 2.0))
    t.on_point((2.5, 3.0))                  # primer tabique: caras en y = 1,15 y 1,25
    t.on_point((2.5, 2.0))                  # clic en vacío: lado de la siguiente
    t.on_point((2.5, 3.5))                  # espesor: segundo tabique a 1 m del primero
    new = [s.meta(w) for w in _new_walls(s, before).values()]
    assert len(new) == 2
    ys = sorted({round(y, 6) for m in new for y in (m['a'][1], m['b'][1])})
    assert ys == pytest.approx([1.15, 2.25])            # líneas de referencia (caras próximas)
    data = s.export(None)
    assert len([x for x in data['joins']['tees']]) == 4 and not data['issues']


# --- ESTIRAMURO ---------------------------------------------------------------------

def test_estira_a_un_punto_libre_acorta(plugin):
    s = Session(plugin)
    t = s.tool('MURO')
    t.thickness = 0.2
    draw(t, (0, 0), (5, 0))
    wid = next(iter(s.walls()))
    t = s.tool('ESTIRAMURO')
    t.on_point((4.9, 0.1))                  # cara, cerca del extremo final
    t.on_point((3.0, 2.0))                  # punto libre: se proyecta sobre la dirección
    assert s.meta(s.walls()[wid])['b'] == pytest.approx([3.0, 0.0])


def test_estira_hasta_cara_alejada_hace_L(plugin):
    s = Session(plugin)
    _host(s)                                # (0,0)-(10,0), 0,30 al eje
    host_id = next(iter(s.walls()))
    t = s.tool('MURO')
    t.thickness = 0.2
    draw(t, (6, 4), (6, 2))
    wid = [k for k in s.walls() if k != host_id][0]
    t = s.tool('ESTIRAMURO')
    t.on_point((6.1, 2.05))
    t.on_point((8.0, -0.15))                # cara ALEJADA del anfitrión
    assert s.meta(s.walls()[wid])['b'] == pytest.approx([6, 0])
    assert s.meta(s.walls()[host_id])['b'] == pytest.approx([6, 0])      # recortado
    data = s.export(None)
    assert not data['joins']['tees'] and not data['issues']
    s.history.undo()
    assert s.meta(s.walls()[host_id])['b'] == [10, 0]


# --- DIVIDEMURO ---------------------------------------------------------------------

def test_divide_en_tres_partes_iguales_hasta_el_muro_de_enfrente(plugin):
    s = Session(plugin)
    t = s.tool('MURO')
    t.thickness, t.reference = 0.30, 'eje'
    draw(t, (0, 0), (8, 0), (8, 5), (0, 5), (0, 0))
    before = set(s.walls())
    t = s.tool('DIVIDEMURO')
    t.on_option('3')
    t.on_option('e')
    t.on_option('0,10')
    t.on_point((0.15, 0.15))                # cara interior del muro sur, de izq. a dcha.
    t.on_point((7.85, 0.15))
    new = [s.meta(w) for w in _new_walls(s, before).values()]
    assert sorted(round(m['a'][0], 6) for m in new) == pytest.approx([2.70, 5.30])
    assert all(m['b'][1] == pytest.approx(4.85) for m in new)
    r = s.tool('RECINTO')
    for x in (1.0, 4.0, 7.0):
        r.on_point((x, 2.0))
    assert [s.meta(e)['area'] for e in _spaces(s)] == pytest.approx([2.5 * 4.7] * 3)


# --- PARTEMURO / BORRATRAMO / UNIRMURO ------------------------------------------------

def _openings(s):
    return [e for e in s.document.doc.modelspace() if (s.meta(e) or {}).get('kind') == 'opening']


def _door(s, wall, offset, kind='puerta'):
    from tests.test_wall_tools import _plugin_module
    v10 = _plugin_module(s.plugin, 'architectural_v10')
    s.history.execute(v10.create_opening(wall, offset, 0.8, 0.0 if kind == 'puerta' else 1.0,
                                         2.1 if kind == 'puerta' else 1.2, kind=kind))


def test_partemuro_lleva_la_puerta_al_tramo_nuevo_y_deshace(plugin):
    s = Session(plugin)
    _host(s)
    hid, host = next(iter(s.walls().items()))
    _door(s, host, 7.0)
    t = s.tool('PARTEMURO')
    t.on_point((1.0, 0.15))                 # el muro, por su contorno
    t.on_point((3.0, 0.0))
    t.on_point((4.0, 0.0))
    walls = s.walls()
    assert len(walls) == 2 and s.meta(walls[hid])['b'] == pytest.approx([3, 0])
    nid = [k for k in walls if k != hid][0]
    assert s.meta(walls[nid])['a'] == pytest.approx([4, 0])
    door = _openings(s)[0]
    assert s.meta(door)['wall_id'] == nid and s.meta(door)['offset'] == pytest.approx(3.0)
    assert min(p[0] for p in door.get_points('xy')) == pytest.approx(7.0)
    data = s.export(None)
    assert not data['issues'] and len(data['elements']) == 2
    s.history.undo()
    assert list(s.walls()) == [hid] and s.meta(door)['wall_id'] == hid
    assert s.meta(door)['offset'] == pytest.approx(7.0)


def test_partemuro_sobre_una_puerta_se_rechaza(plugin):
    s = Session(plugin)
    _host(s)
    hid, host = next(iter(s.walls().items()))
    _door(s, host, 3.2)
    t = s.tool('PARTEMURO')
    t.on_point((1.0, 0.15))
    t.on_point((3.0, 0.0))
    t.on_point((4.0, 0.0))
    assert len(s.walls()) == 1 and any('carpintería en el tramo' in o for o in s.out)


def test_borratramo_quita_el_brazo_de_una_cruz(plugin):
    s = Session(plugin)
    _host(s)                                # H: (0,0)-(10,0)
    hid = next(iter(s.walls()))
    t = s.tool('MURO')
    t.thickness = 0.10
    draw(t, (5, -3), (5, 3))                # V cruza H
    vid = [k for k in s.walls() if k != hid][0]
    t = s.tool('BORRATRAMO')
    t.on_point((5.05, 2.0))                 # brazo superior de V
    m = s.meta(s.walls()[vid])
    assert m['a'] == pytest.approx([5, -3]) and m['b'] == pytest.approx([5, 0])
    data = s.export(None)
    assert data['joins']['tees'] and not data['issues']
    v = next(e for e in data['elements'] if e['id'] == vid)
    assert v['quantities']['GrossFootprintArea'] == pytest.approx(0.10 * (3 - 0.15))


def test_borratramo_central_parte_y_aislado_borra(plugin):
    s = Session(plugin)
    _host(s)
    hid = next(iter(s.walls()))
    for x in (3, 7):
        t = s.tool('MURO')
        t.thickness = 0.10
        draw(t, (x, -2), (x, 2))
    t = s.tool('BORRATRAMO')
    t.on_point((5.0, 0.15))                 # H entre los dos cruces
    hm = s.meta(s.walls()[hid])
    assert hm['b'] == pytest.approx([3, 0])
    assert any(s.meta(w)['a'] == pytest.approx([7, 0]) and s.meta(w)['thickness'] == 0.3
               for w in s.walls().values())
    t = s.tool('MURO')
    draw(t, (20, 20), (24, 20))
    n = len(s.walls())
    t = s.tool('BORRATRAMO')
    t.on_point((22, 20.0 + s.meta(list(s.walls().values())[-1])['thickness'] / 2))
    assert len(s.walls()) == n - 1


def test_unirmuro_une_y_reubica_la_ventana(plugin):
    s = Session(plugin)
    t = s.tool('MURO')
    t.thickness = 0.25
    draw(t, (0, 0), (4, 0))
    t = s.tool('MURO')
    t.thickness = 0.25
    draw(t, (5, 0), (10, 0))
    ids = list(s.walls())
    first, second = ids[0], ids[1]
    _door(s, s.walls()[second], 1.0, kind='ventana')
    t = s.tool('UNIRMURO')
    t.on_point((2.0, 0.125))
    t.on_point((7.0, 0.125))
    walls = s.walls()
    assert list(walls) == [first]
    m = s.meta(walls[first])
    assert m['a'] == pytest.approx([0, 0]) and m['b'] == pytest.approx([10, 0])
    win = _openings(s)[0]
    assert s.meta(win)['wall_id'] == first and s.meta(win)['offset'] == pytest.approx(6.0)
    s.history.undo()
    assert len(s.walls()) == 2 and s.meta(win)['wall_id'] == second


def test_deshacer_un_borrado_devuelve_el_grupo_del_muro(plugin):
    s = Session(plugin)
    t = s.tool('MURO')
    draw(t, (0, 0), (4, 0))
    t = s.tool('MURO')
    draw(t, (5, 0), (10, 0))
    t = s.tool('UNIRMURO')
    t.on_point((2.0, s.meta(next(iter(s.walls().values())))['thickness'] / 2))
    t.on_point((7.0, s.meta(next(iter(s.walls().values())))['thickness'] / 2))
    assert len(s.walls()) == 1
    s.history.undo()
    assert len(s.walls()) == 2
    assert not [i for i in s.issues() if 'grupo' in i or 'Contorno' in i]

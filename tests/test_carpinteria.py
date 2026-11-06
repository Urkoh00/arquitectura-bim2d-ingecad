# SPDX-License-Identifier: GPL-3.0-or-later
"""Carpinterías (puertas, ventanas, huecos) en muros y tabiques, sobre IngeCAD real.

Vivienda de 8 x 5 m con muros de 0,30 al eje y un tabique de 0,10 en x = 4:
cara interior del muro sur en y = 0,15, paramentos libres de x 0,15 a 3,95
(estancia 1) y de 4,05 a 7,85 (estancia 2)."""
import pytest

from arquitectura.geom import solids as S
from core import actions

from tests.test_ingecad_integration import plugin  # noqa: F401  (fixture)
from tests.test_recintos import _cmd_ctx, _spaces, _vivienda
from tests.test_wall_tools import Session


def _openings(s):
    return [e for e in s.document.doc.modelspace() if (s.meta(e) or {}).get('kind') == 'opening']


def _symbols(s, ident=None):
    return [e for e in s.document.doc.modelspace() if (s.meta(e) or {}).get('kind') == 'opening_symbol'
            and (ident is None or s.meta(e)['opening_id'] == ident)]


def _lines(s):
    out = []
    for e in s.document.doc.modelspace():
        if (s.meta(e) or {}).get('kind') == 'junction_edge':
            out.append(((round(e.dxf.start.x, 6), round(e.dxf.start.y, 6)),
                        (round(e.dxf.end.x, 6), round(e.dxf.end.y, 6))))
    return out


def _wall(s, a, b):
    return next(w for w in s.walls().values()
                if s.meta(w)['a'] == pytest.approx(list(a)) and s.meta(w)['b'] == pytest.approx(list(b)))


def _regen(s):
    s.plugin.commands['UNIONESARQ'](_cmd_ctx(s))


def test_puerta_libre_corta_el_muro_con_mochetas_y_dibuja_la_hoja(plugin):
    s = Session(plugin)
    _vivienda(s)
    t = s.tool('CARPINTERIA')
    t.on_point((1.0, 0.15))             # la jamba de la bisagra, en la cara interior
    t.on_point((2.0, 1.0))              # se extiende hacia +x y abre hacia el interior
    [door] = _openings(s)
    m = s.meta(door)
    south = _wall(s, (0, 0), (8, 0))
    assert m['wall_id'] == s.meta(south)['id'] and m['type'] == 'door' and m['schema'] == 3
    assert m['offset'] == pytest.approx(1.0) and m['width'] == pytest.approx(0.825 + 0.06)
    assert (m['hinge'], m['side'], m['leaves']) == (0, 1, 1)
    # el contorno se interrumpe en el hueco y aparecen las dos mochetas
    lines = _lines(s)
    for x in (1.0, 1.885):
        assert any(abs(a[0] - x) < 1e-6 and abs(b[0] - x) < 1e-6 and
                   sorted((a[1], b[1])) == pytest.approx([-0.15, 0.15]) for a, b in lines), x
    assert not any(a[1] == b[1] == 0.15 and min(a[0], b[0]) < 1.4 < max(a[0], b[0]) for a, b in lines)
    # hoja de 0,825 desde la bisagra, a 90°, y su arco de giro
    sym = _symbols(s, m['id'])
    arcs = [e for e in sym if e.dxftype() == 'ARC']
    assert len(arcs) == 1 and arcs[0].dxf.radius == pytest.approx(0.825)
    assert (arcs[0].dxf.center.x, arcs[0].dxf.center.y) == pytest.approx((1.03, 0.15))
    leaf = [e for e in sym if e.dxftype() == 'LINE'][0]
    assert (leaf.dxf.end.x, leaf.dxf.end.y) == pytest.approx((1.03, 0.975))
    # el portador está en la capa oculta y forma grupo con su símbolo
    assert s.document.doc.layers.get(door.dxf.layer).is_off()
    pick = s.services.pick_entity((1.03, 0.6))
    assert pick is not None and s.meta(pick)['kind'] == 'opening_symbol'
    from core.groups import expand
    assert door.dxf.handle in expand(s.document, {pick.dxf.handle})
    # la estancia no se une a través de la puerta y la auditoría está limpia
    r = s.tool('RECINTO')
    r.on_point((2, 2))
    assert s.meta(_spaces(s)[0])['area'] == pytest.approx(3.8 * 4.7)
    assert not [i for i in s.issues() if 'Contorno' in i or 'Hueco' in i]


def test_ventana_a_distancia_fija_centrada_y_maxima(plugin):
    s = Session(plugin)
    _vivienda(s)
    t = s.tool('CARPINTERIA')
    t.on_option('v')
    t.on_option('m')
    t.on_option('d 0,10')
    t.on_point((7.5, 0.15))             # cerca de la esquina de x = 7,85
    t.on_option('m')
    t.on_option('c')
    t.on_point((1.0, 4.85))             # muro norte, dibujado de (8,5) a (0,5)
    t.on_option('m')
    t.on_option('maxima')
    t.on_point((5.0, 4.85))
    ops = sorted((s.meta(e) for e in _openings(s)), key=lambda m: m['offset'])
    by_x = {}
    for e in _openings(s):
        p = e.get_points('xy')
        by_x[round((p[0][0] + p[1][0]) / 2, 6)] = s.meta(e)
    xs = sorted(by_x)
    # distancia fija: lado derecho a 0,10 de la esquina interior x = 7,85
    assert xs[-1] == pytest.approx(7.85 - 0.10 - 0.60)
    assert by_x[xs[-1]]['hinge'] == 1 and by_x[xs[-1]]['sill'] == pytest.approx(0.90)
    # centrada en el paramento interior de la estancia 1 (0,15 .. 3,95)
    assert xs[0] == pytest.approx(2.05)
    # longitud máxima en la estancia 2 del muro norte: todo el paramento
    assert xs[1] == pytest.approx(5.95)
    assert by_x[xs[1]]['width'] == pytest.approx(3.80)
    assert len(ops) == 3 and all(o['type'] == 'window' for o in ops)
    # una ventana dibuja marco, vidrio, la división de sus dos hojas y el alféizar exterior
    kinds = sorted(e.dxftype() for e in _symbols(s, by_x[xs[0]]['id']))
    assert kinds == ['LINE', 'LINE', 'LWPOLYLINE', 'LWPOLYLINE']
    assert not [i for i in s.issues() if 'Contorno' in i]


def test_no_cabe_no_crea_nada(plugin):
    s = Session(plugin)
    _vivienda(s)
    t = s.tool('CARPINTERIA')
    t.on_option('v')
    t.on_option('5')                    # un número: el ancho
    t.on_option('m')
    t.on_option('c')
    t.on_point((1.0, 0.15))
    assert not _openings(s)
    assert any('no cabe' in o and '3,800' in o for o in s.out)


def test_puerta_en_tabique_ocupa_su_espesor_y_sigue_al_tabique(plugin):
    s = Session(plugin)
    _vivienda(s)
    t = s.tool('CARPINTERIA')
    t.on_option('m')
    t.on_option('c')
    t.on_point((3.95, 2.0))             # cara del tabique hacia la estancia 1
    [door] = _openings(s)
    m = s.meta(door)
    tab = [w for w in s.walls().values() if s.meta(w)['thickness'] == 0.1][0]
    assert m['wall_id'] == s.meta(tab)['id']
    assert m['offset'] + m['width'] / 2 == pytest.approx(4.7 / 2)
    frames = [e for e in _symbols(s, m['id']) if e.dxftype() == 'LWPOLYLINE']
    xs = sorted({round(p[0], 6) for e in frames for p in e.get_points('xy')})
    assert xs == pytest.approx([3.95, 4.05])                 # cerco = espesor del tabique
    r = s.tool('RECINTO')
    r.on_point((2, 2))
    r.on_point((6, 2))
    assert [s.meta(e)['area'] for e in _spaces(s)] == pytest.approx([3.8 * 4.7] * 2)
    # MOVE del tabique: la puerta va con él, sin cambiar su posición en el tabique
    s.history.execute(actions.move_entities([tab], 1.0, 0.0))
    _regen(s)
    pts = door.get_points('xy')
    assert pts[0][0] == pytest.approx(5.0) and s.meta(door)['offset'] == pytest.approx(m['offset'])
    assert all(abs(p[0] - 5.0) < 0.051 for e in _symbols(s, m['id']) if e.dxftype() == 'LWPOLYLINE'
               for p in e.get_points('xy'))


def test_mover_copiar_y_borrar_con_el_muro(plugin):
    s = Session(plugin)
    _vivienda(s)
    t = s.tool('CARPINTERIA')
    t.on_point((1.0, 0.15))
    t.on_enter()
    [door] = _openings(s)
    ident = s.meta(door)['id']
    # MOVE de la puerta a lo largo del muro
    s.history.execute(actions.move_entities([door], 1.0, 0.0))
    _regen(s)
    assert s.meta(door)['offset'] == pytest.approx(2.0) and s.meta(door)['id'] == ident
    # COPY al muro norte: identidad nueva, nuevo anfitrión, aspecto conservado
    s.history.execute(actions.copy_entities([door], 0.0, 5.0))
    _regen(s)
    north = _wall(s, (8, 5), (0, 5))
    copy = next(e for e in _openings(s) if e is not door)
    cm = s.meta(copy)
    assert cm['id'] != ident and cm['wall_id'] == s.meta(north)['id']
    assert cm['offset'] == pytest.approx(8 - 2.0 - cm['width']) and cm['hinge'] == 1
    assert len(_symbols(s, cm['id'])) == 4                  # 2 jambas del cerco, hoja y arco
    # ERASE del muro sur: su puerta desaparece con él; deshacer la recupera
    south = _wall(s, (0, 0), (8, 0))
    s.history.execute(actions.EraseCommand([south]))
    _regen(s)
    assert door not in _openings(s) and not _symbols(s, ident)
    s.history.undo()
    s.history.undo()
    assert door in _openings(s) and _symbols(s, ident)


def test_sustituir_modelo_y_girar(plugin):
    s = Session(plugin)
    _vivienda(s)
    t = s.tool('CARPINTERIA')
    t.on_point((1.0, 0.15))
    t.on_enter()
    [door] = _openings(s)
    ident, w0 = s.meta(door)['id'], s.meta(door)['width']
    t.on_option('b')                    # bisagra al otro lado
    assert s.meta(door)['hinge'] == 1
    t.on_option('s')                    # abre hacia el exterior
    assert s.meta(door)['side'] == -1
    arc = [e for e in _symbols(s, ident) if e.dxftype() == 'ARC'][0]
    assert arc.dxf.center.y == pytest.approx(-0.15)         # el cerco pasa a la cara a la que abre
    t.on_option('hojas')
    t.on_option('2')
    t.on_point((1.855, -0.6))           # pinchar la hoja: sustituye el modelo
    m = s.meta(door)
    assert m['id'] == ident and m['leaves'] == 2 and m['width'] == pytest.approx(w0)
    assert m['leaf'] + m['leaf2'] == pytest.approx(w0 - 0.06)
    assert len([e for e in _symbols(s, ident) if e.dxftype() == 'ARC']) == 2
    s.history.undo()
    assert s.meta(door)['leaves'] == 1


def test_exporta_puerta_que_rellena_su_hueco(plugin):
    s = Session(plugin)
    _vivienda(s)
    t = s.tool('CARPINTERIA')
    t.on_point((1.0, 0.15))
    t.on_enter()
    t.on_option('v')
    t.on_option('m')
    t.on_option('c')
    t.on_point((6.0, 0.15))
    data = s.export(None)
    assert not data['issues']
    south = next(e for e in data['elements'] if e['ifc_class'] == 'IfcWall'
                 and e['params']['a'] == pytest.approx([0, 0]) and e['params']['b'] == pytest.approx([8, 0]))
    door = next(e for e in data['elements'] if e['ifc_class'] == 'IfcDoor')
    win = next(e for e in data['elements'] if e['ifc_class'] == 'IfcWindow')
    voids = {o['guid']: o for o in south['openings']}
    assert door['fills'] in voids and win['fills'] in voids
    assert door['guid'] not in voids                         # la puerta conserva la identidad del registro
    assert door['quantities']['Width'] == pytest.approx(0.885)
    assert door['quantities']['Height'] == pytest.approx(2.10)
    assert door['volume'] == pytest.approx(0.885 * 0.15 * 2.10)
    assert win['psets']['Pset_WindowCommon']['IsExternal'] is True
    faces = [(f['outer'], f['holes']) for f in door['faces']]
    assert S.face_volume(faces) == pytest.approx(door['volume'])
    # muro sur: volumen bruto menos los dos huecos
    gross = south['quantities']['GrossVolume']
    holes = 0.885 * 2.10 * 0.30 + 1.20 * 1.20 * 0.30
    assert south['volume'] == pytest.approx(gross - holes)


def test_hojas_normalizadas_apertura_e_insercion_por_el_centro(plugin):
    s = Session(plugin)
    _vivienda(s)
    t = s.tool('CARPINTERIA')
    t.on_option('n')
    t.on_option('72')                   # hoja normalizada de 725 mm
    t.on_option('t')
    t.on_option('corredera')
    t.on_option('m')
    t.on_option('d 1,00')
    t.on_option('i')
    t.on_option('medio')                # la distancia es al centro del hueco
    t.on_point((1.0, 0.15))
    [door] = _openings(s)
    m = s.meta(door)
    assert m['leaf'] == pytest.approx(0.725) and m['operation'] == 'SLIDING'
    assert m['offset'] + m['width'] / 2 == pytest.approx(0.15 + 1.00)    # centro a 1 m de la esquina
    sym = _symbols(s, m['id'])
    assert not [e for e in sym if e.dxftype() == 'ARC']                   # corredera: sin arco de giro
    assert len([e for e in sym if e.dxftype() == 'LWPOLYLINE']) == 3      # 2 jambas + hoja
    t.on_option('v')
    t.on_option('t')
    t.on_option('f')                    # ventana fija: una hoja
    t.on_option('m')
    t.on_option('c')
    t.on_point((6.0, 0.15))
    win = next(s.meta(e) for e in _openings(s) if s.meta(e)['type'] == 'window')
    assert win['operation'] == 'FIXED' and win['leaves'] == 1 and win['face'] == 'interior'
    data = s.export(None)
    w = next(e for e in data['elements'] if e['ifc_class'] == 'IfcWindow')
    d = next(e for e in data['elements'] if e['ifc_class'] == 'IfcDoor')
    assert w['psets']['ARQ_IngeCAD']['Apertura'] == 'fija'
    assert d['psets']['ARQ_IngeCAD']['Apertura'] == 'corredera'


def test_recinto_hasta_el_falso_techo(plugin):
    s = Session(plugin)
    _vivienda(s)
    r = s.tool('RECINTO')
    r.on_option('f')
    r.on_option('2,50')
    r.on_point((2, 2))
    r.on_option('f')
    r.on_option('0')                    # sin falso techo: hasta el forjado (altura del muro)
    r.on_point((6, 2))
    data = s.export(None)
    sp = sorted((e for e in data['elements'] if e['ifc_class'] == 'IfcSpace'),
                key=lambda e: e['params']['seed'][0])
    assert sp[0]['quantities']['Height'] == pytest.approx(2.50)
    assert sp[0]['quantities']['FinishCeilingHeight'] == pytest.approx(2.50)
    assert sp[0]['quantities']['NetVolume'] == pytest.approx(17.86 * 2.50)
    assert sp[0]['psets']['ARQ_Recinto']['Techo'] == 'falso techo'
    assert sp[1]['quantities']['Height'] == pytest.approx(2.70)
    assert 'FinishCeilingHeight' not in sp[1]['quantities']


def test_falso_techo_se_exporta_como_ifccovering_coplanario(plugin):
    s = Session(plugin)
    _vivienda(s)
    r = s.tool('RECINTO')
    r.on_option('f')
    r.on_option('2,55')
    r.on_point((2, 2))
    t = s.tool('CARPINTERIA')
    t.on_point((1.0, 0.15))             # bisagra en s0, abre hacia +y (interior)
    t.on_enter()
    data = s.export(None)
    techo = next(e for e in data['elements'] if e['ifc_class'] == 'IfcCovering')
    space = next(e for e in data['elements'] if e['ifc_class'] == 'IfcSpace')
    assert techo['enums'] == {'PredefinedType': 'CEILING'}
    zs_space = max(v[2] for f in space['faces'] for v in f['outer'])
    zs_techo = min(v[2] for f in techo['faces'] for v in f['outer'])
    assert zs_space == pytest.approx(2.55) and zs_techo == pytest.approx(2.55)
    assert techo['volume'] == pytest.approx(17.86 * 0.015)
    door = next(e for e in data['elements'] if e['ifc_class'] == 'IfcDoor')
    assert door['enums'] == {'PredefinedType': 'DOOR', 'OperationType': 'SINGLE_SWING_LEFT'}

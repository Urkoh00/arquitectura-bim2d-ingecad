# SPDX-License-Identifier: GPL-3.0-or-later
"""IngeCAD's own editing orders on BIM elements are accepted, with the
official IngeCAD and no hook (user, 9-11-2026: «no deseo hacer un programa
dentro de otro»; audit ARQ-AUD-0003, 0015, 0021, 0022).

IngeCAD transforms each element's reference frame (XDATA 1011/1012) with
the entity; regenerating (any plugin order, UNIONESARQ) or exporting reads
the transformation from it."""
import pytest

from core import actions
from core.commands import History
from core.document import Document

from arquitectura import exchange as E
from arquitectura import frame as FR
from arquitectura import openings as OP
from arquitectura.architectural import _xdata, metadata
from arquitectura.architectural_v10 import create_wall
from arquitectura.geom import junctions as J
from arquitectura.wall_network import RegenerateContoursCommand


def document():
    d = Document.new()
    d.doc.header['$INSUNITS'] = 6
    for name in ['ARQ-MUROS', 'ARQ-MUROS3D', 'ARQ-HUECOS3D', 'ARQ-RECINTOS']:
        d.doc.layers.add(name)
    return d, History(d)


def wall(h, a=(0, 0), b=(5, 0), t=0.2, **kw):
    c = create_wall(a, b, t, 3, **kw)
    h.execute(c)
    return c.entity


def door(d, w):
    wm = metadata(w)
    m = OP.normalise(dict(kind='opening', schema=3, id='door', wall_id=wm['id'], offset=1.0, width=0.9,
                          sill=0.0, height=2.1, type='door'))
    spec = J.walls_from_records([(wm['id'], wm)])[0]
    e = d.doc.modelspace().add_lwpolyline(OP.carrier_points(spec, m))
    _xdata(d.doc.modelspace(), e, m)
    return e


def column(d, center=(0, 0), w=0.4, dp=0.2, **kw):
    m = dict(kind='column', schema=2, id='col', shape='rect', width=w, depth=dp, rotation=0,
             center=list(center), height=3, base=0, **kw)
    x, y = center
    e = d.doc.modelspace().add_lwpolyline([(x - w / 2, y - dp / 2), (x + w / 2, y - dp / 2),
                                           (x + w / 2, y + dp / 2), (x - w / 2, y + dp / 2)], close=True)
    _xdata(d.doc.modelspace(), e, m)
    return e


def bim(d):
    return [e for e in d.doc.modelspace() if (metadata(e) or {}).get('kind') in FR.KINDS]


def test_el_marco_viaja_con_la_entidad():
    d, h = document()
    w = wall(h)
    assert not FR.moved(FR.read_frame(w))
    h.execute(actions.rotate_entities([w], (0, 0), 90))
    aff = FR.Affine(FR.read_frame(w))
    assert aff.point((1, 0)) == pytest.approx([0, 1]) and not aff.mirrored
    h.undo()
    assert not FR.moved(FR.read_frame(w))


def test_simetria_cambia_lado_de_muro_y_puerta():                          # 0021
    d, h = document()
    w = wall(h, reference='izquierda')
    o = door(d, w)
    h.execute(RegenerateContoursCommand())
    h.execute(actions.mirror_entities(bim(d), (-1, 1), (6, 1), False))
    h.execute(RegenerateContoursCommand())
    assert metadata(w)['reference'] == 'derecha' and metadata(o)['side'] == -1
    el = next(x for x in E.build(d.doc)['elements'] if x['ifc_class'] == 'IfcWall')
    ys = [p[1] for f in el['faces'] for p in f['outer']]
    assert (min(ys), max(ys)) == pytest.approx((1.8, 2.0))   # its body, mirrored too
    assert not FR.moved(FR.read_frame(w))                  # the data is current again


def test_simetria_y_deshacer_sin_regenerar_no_cambia_nada():
    """IngeCAD undoes a polyline MIRROR without restoring its XDATA: the
    frame would say «mirrored»; its stored outline shows it is stale."""
    d, h = document()
    w = wall(h, reference='izquierda')
    h.execute(actions.mirror_entities(bim(d), (-1, 1), (6, 1), False))
    h.undo()
    h.execute(RegenerateContoursCommand())
    assert metadata(w)['reference'] == 'izquierda' and metadata(w)['a'] == pytest.approx([0, 0])


def test_girar_toda_la_planta_lleva_el_punto_interior():                    # 0022
    d, h = document()
    ps = [(0, 0), (5, 0), (5, 4), (0, 4)]
    for a, b in zip(ps, ps[1:] + ps[:1]):
        wall(h, a, b)
    e = d.doc.modelspace().add_lwpolyline([(.1, .1), (4.9, .1), (4.9, 3.9), (.1, 3.9)], close=True)
    _xdata(d.doc.modelspace(), e, dict(kind='space', schema=3, id='room', seed=[.5, 1], ref_vertex=[.1, .1],
                                       height=2.7, base=0, area=18.24))
    h.execute(RegenerateContoursCommand())
    h.execute(actions.rotate_entities(bim(d), (0, 0), 90))
    h.execute(RegenerateContoursCommand())
    assert metadata(e)['seed'] == pytest.approx([-1, .5])
    assert any(x['id'] == 'room' for x in E.build(d.doc)['elements'])


def test_escalar_pilar_cambia_su_seccion_sin_inventar_revestimiento():     # 0015
    d, h = document()
    c = column(d)
    h.execute(actions.scale_entities([c], (0, 0), 2))
    els = E.build(d.doc)['elements']                       # exported before regenerating
    assert len(els) == 1 and els[0]['volume'] == pytest.approx(0.8 * 0.4 * 3 * 2)   # alto x2 también
    h.execute(RegenerateContoursCommand())
    m = metadata(c)
    assert (m['width'], m['depth']) == pytest.approx((0.8, 0.4)) and not m.get('cover')


def test_pilar_movido_se_exporta_donde_esta():                             # 0003
    d, h = document()
    c = column(d)
    before = dict(metadata(c))
    h.execute(actions.move_entities([c], 10, 0))
    el = E.build(d.doc)['elements'][0]
    xs = [p[0] for f in el['faces'] for p in f['outer']]
    assert (min(xs), max(xs)) == pytest.approx((9.8, 10.2))
    assert metadata(c) == before                           # exporting does not write


def test_perfil_metalico_escalado_pasa_a_seccion_generica_y_avisa():
    d, h = document()
    c = column(d, shape_override=None)
    m = metadata(c)
    m.update(shape='steel', profile='HEB 200')
    m.pop('shape_override', None)
    _xdata(d.doc.modelspace(), c, m)
    h.execute(actions.scale_entities([c], (0, 0), 2))
    cmd = RegenerateContoursCommand()
    h.execute(cmd)
    assert metadata(c)['shape'] == 'rect'
    assert any('HEB 200' in i and 'genérica' in i for i in cmd.issues)


def test_escalar_muro_escala_espesor_y_capas():
    d, h = document()
    w = wall(h, t=0.2)
    m = metadata(w)
    m['layers'] = [[0.05, 'Yeso'], [0.15, 'Ladrillo']]
    _xdata(d.doc.modelspace(), w, m)
    h.execute(actions.scale_entities([w], (0, 0), 0.5))
    h.execute(RegenerateContoursCommand())
    m = metadata(w)
    assert m['thickness'] == pytest.approx(0.1) and m['b'] == pytest.approx([2.5, 0])
    assert [t for t, _ in m['layers']] == pytest.approx([0.025, 0.075])
    assert m['height'] == pytest.approx(1.5)


def test_deshacer_regeneracion_y_orden_vuelve_al_original():
    d, h = document()
    w = wall(h, reference='izquierda')
    o = door(d, w)
    original = (dict(metadata(w)), dict(metadata(o)))
    h.execute(actions.mirror_entities(bim(d), (-1, 1), (6, 1), False))
    h.execute(RegenerateContoursCommand())
    h.undo()                                               # the regeneration
    h.undo()                                               # IngeCAD's mirror
    h.execute(RegenerateContoursCommand())
    assert metadata(w)['reference'] == original[0]['reference']
    assert metadata(o)['side'] == original[1]['side']
    assert not FR.moved(FR.read_frame(w))


def test_copia_y_rehacer_conservan_anfitrion():                            # 0003/0013
    d, h = document()
    w = wall(h)
    door(d, w)
    h.execute(RegenerateContoursCommand())
    h.execute(actions.copy_entities(bim(d), 0, 10))
    h.execute(RegenerateContoursCommand())
    before = E.build(d.doc)
    h.undo()
    h.redo()
    after = E.build(d.doc)
    assert {x['id'] for x in before['elements']} == {x['id'] for x in after['elements']}
    assert sorted(len(x['openings']) for x in after['elements'] if x['ifc_class'] == 'IfcWall') == [1, 1]

# SPDX-License-Identifier: GPL-3.0-or-later
"""Geometry and history fixes from the independent audit of v1.15
(ARQ-AUD-0002, 0004, 0006, 0016, 0023); tests adapted from the ones
delivered with it, against the official IngeCAD."""
from types import SimpleNamespace

import pytest

from core.commands import History
from core.document import Document

from arquitectura import exchange as E
from arquitectura.architectural import metadata
from arquitectura.architectural_v10 import create_wall
from arquitectura.geom import polygon as P
from arquitectura.geom.solids import face_volume
from arquitectura.transactions import apply_architectural_change
from arquitectura.wall_network import RegenerateContoursCommand


def document():
    d = Document.new()
    d.doc.header['$INSUNITS'] = 6
    for name in ['ARQ-MUROS', 'ARQ-MUROS3D', 'ARQ-HUECOS3D', 'ARQ-RECINTOS']:
        d.doc.layers.add(name)
    return d, History(d)


def wall(h, a=(0, 0), b=(5, 0), **kw):
    c = create_wall(a, b, .2, 3, **kw)
    h.execute(c)
    return c.entity


def test_muros_a_distinta_altura_no_se_recortan():                       # 0002
    d, h = document()
    wall(h)
    wall(h, base=10, level='Alta')
    els = E.build(d.doc)['elements']
    assert [e['volume'] for e in els] == pytest.approx([3, 3])


def test_solape_parcial_en_altura_volumen_correcto():                    # 0002
    d, h = document()
    wall(h)
    wall(h, base=1)
    data = E.build(d.doc)
    assert [el['volume'] for el in data['elements']] == pytest.approx([3, 1])
    for el in data['elements']:
        assert face_volume([(f['outer'], f.get('holes', [])) for f in el['faces']]) == pytest.approx(el['volume'])


def test_la_curvatura_sale_del_dibujo():                                  # 0004
    d, h = document()
    e = wall(h, bulge=.5)
    e.set_points([(0, 0, 0), (5, 0, 0)], format='xyb')      # enderezado con IngeCAD
    el = E.build(d.doc)['elements'][0]
    assert not el['params'].get('bulge') and el['volume'] == pytest.approx(3)


def test_area_no_depende_de_la_distancia_al_origen():                    # 0016
    p = [(0, 0), (5, 1.234), (4, .321), (.1, -.25)]
    q = [(x + 5e6, y + 5e6) for x, y in p]
    assert P.area(q) == pytest.approx(P.area(p), abs=1e-8)


def test_fallo_al_regenerar_no_deja_restos(monkeypatch):                  # 0006
    d, h = document()
    wall(h)
    msp = d.doc.modelspace()
    before = {e.dxf.handle for e in msp}
    original = msp.add_line
    calls = [0]

    def fail(*args, **kw):
        calls[0] += 1
        if calls[0] == 2:
            raise RuntimeError('fallo provocado')
        return original(*args, **kw)
    monkeypatch.setattr(msp, 'add_line', fail)
    with pytest.raises(RuntimeError, match='provocado'):
        h.execute(RegenerateContoursCommand())
    assert {e.dxf.handle for e in msp} == before
    assert not any((metadata(e) or {}).get('kind') == 'junction_edge' and e.is_alive
                   for e in d.doc.entitydb.values())


def test_rehacer_no_acumula_contornos():                                  # 0023
    d, h = document()
    apply_architectural_change(SimpleNamespace(document=d, execute=h.execute), create_wall((0, 0), (5, 0), .2, 3))
    before = len(d.doc.entitydb)
    for _ in range(100):
        h.undo()
        h.redo()
    assert len(d.doc.entitydb) == before

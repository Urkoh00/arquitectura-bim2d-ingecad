# SPDX-License-Identifier: GPL-3.0-or-later
"""Revisión general (v1.28): persistencia completa y coste por cambio.

1. Guardar en DXF con IngeCAD y volver a abrir deja el MISMO modelo BIM:
   el contrato que va a IngeTrazo es idéntico antes y después.
2. Con muchos recintos, un cambio no recalcula la unión de toda la red una
   vez por recinto (v1.27: 2,7 s por muro con cien recintos).
3. Los niveles comprueban las carpinterías de cada muro sin recorrer el
   dibujo una vez por muro.
"""
import json
from importlib import import_module

import pytest
from core.document import Document
from core.commands import History

from tests.test_ingecad_integration import plugin  # noqa: F401  (fixture)
from tests.test_wall_tools import Services, Session, draw


def _module(s, name):
    root = s.plugin.commands['EXPORTARBIM'].__module__.rsplit('.', 1)[0]
    return import_module(root + '.' + name)


def _building(s, k=3, w=4.0):
    """k x k habitaciones conectadas, con una puerta y un recinto en cada una."""
    for j in range(k + 1):
        t = s.tool('MURO'); t.thickness, t.reference = 0.20, 'eje'
        draw(t, *[(i * w, j * w) for i in range(k + 1)])
    for i in range(k + 1):
        for j in range(k):
            t = s.tool('MURO'); t.thickness, t.reference = 0.20, 'eje'
            draw(t, (i * w, j * w + 0.10), (i * w, (j + 1) * w - 0.10))
    for j in range(k):
        for i in range(k):
            t = s.tool('CARPINTERIA'); t.preview_entities((i * w + 1.0, j * w + 0.10)); t.on_option("0,40")
            t = s.tool('RECINTO'); t.on_point((i * w + 2.0, j * w + 2.0))


def _contract(s, doc):
    data = _module(s, 'exchange').build(doc)
    data.pop('created', None)
    for key in ('generated', 'timestamp', 'date'):
        data.pop(key, None)
    return data


def test_guardar_y_reabrir_conserva_el_modelo_bim(plugin, tmp_path):
    s = Session(plugin)
    _building(s, k=2)
    t = s.tool('PILAR')
    if hasattr(t, 'on_point'):
        t.on_point((4.0, 4.0))
    before = _contract(s, s.document.doc)
    path = tmp_path / 'vivienda.dxf'
    s.document.save_as(path)
    again = Document.load(path)
    s2 = Session(plugin)
    s2.document, s2.history, s2.services = again, History(again), Services(again)
    after = _contract(s2, again.doc)
    assert json.dumps(after, sort_keys=True) == json.dumps(before, sort_keys=True)
    kinds = {e['ifc_class'] for e in before['elements']}
    assert {'IfcWall', 'IfcDoor', 'IfcSpace'} <= kinds


def test_la_red_se_une_una_vez_por_cambio_no_una_por_recinto(plugin, monkeypatch):
    s = Session(plugin)
    _building(s, k=3)                                   # 9 recintos
    SP = _module(s, 'geom.spaces')
    calls = []
    real = SP._all_pieces
    monkeypatch.setattr(SP, '_all_pieces', lambda r: calls.append(1) or real(r))
    t = s.tool('MURO'); t.thickness, t.reference = 0.10, 'eje'
    draw(t, (2.0, 0.10), (2.0, 3.90))
    assert 0 < len(calls) <= 4, len(calls)            # una por red (útil, total…), no 9+


def test_niveles_indexan_las_carpinterias_una_vez(plugin, monkeypatch):
    s = Session(plugin)
    _building(s, k=2)
    WC = _module(s, 'wall_constraints')
    LV = _module(s, 'levels')
    calls = []
    real = WC.openings_by_wall
    monkeypatch.setattr(WC, 'openings_by_wall', lambda d: calls.append(1) or real(d))
    catalog = LV.load(s.document)
    steps = LV.catalog_steps(s.document, catalog)
    assert steps and len(calls) <= 1


@pytest.mark.parametrize("typed, thickness, point", [
    ("0,25", 0.25, False),          # coma decimal: costumbre española
    ("0.25", 0.25, False),
    ("1,2", 1.2, False),
    ("25", 0.25, False),            # centímetros, con aviso
    ("250", 0.25, False),           # milímetros, con aviso
    ("3,4", None, True),            # no es un espesor: el punto 3,4 de IngeCAD
    ("12,5", None, True),
])
def test_espesor_escrito_en_muro(plugin, typed, thickness, point):
    s = Session(plugin)
    t = s.tool('MURO')
    handled = t.on_option(typed)
    if point:
        assert handled is False and t.thickness == pytest.approx(0.30)
    else:
        assert handled is True and t.thickness == pytest.approx(thickness)


def test_espesor_absurdo_se_rechaza(plugin):
    s = Session(plugin)
    t = s.tool('MURO')
    assert t.on_option("5000") is True
    assert t.thickness == pytest.approx(0.30)
    assert any("fuera de rango" in str(x) for x in s.out)

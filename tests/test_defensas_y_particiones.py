# SPDX-License-Identifier: GPL-3.0-or-later
"""Defensas (DEFENSA) y particiones virtuales (PARTICIONVIRTUAL), v1.29, sobre IngeCAD real.

Las dos vienen de las herramientas BIM de arquitectura de referencia:
- defensa: barandilla, balaustrada o antepecho que se dibuja como un muro,
  cierra recintos (una terraza) y se exporta como IfcRailing (o IfcWall
  PARAPET si es macizo);
- partición virtual: línea sin espesor que separa dos recintos sin muro
  entre ellos (cocina abierta y salón)."""
import json

import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401  (fixture)
from tests.test_recintos import _spaces
from tests.test_wall_tools import Session, draw


def _box(s, w=8.0, h=5.0, t=0.30):
    m = s.tool('MURO')
    m.thickness, m.reference = t, 'eje'
    draw(m, (0, 0), (w, 0), (w, h), (0, h), (0, 0))


def _el(data, cls):
    return [e for e in data['elements'] if e['ifc_class'] == cls]


# --- DEFENSA -------------------------------------------------------------------------
def test_defensa_por_defecto_es_una_barandilla(plugin):
    s = Session(plugin)
    t = s.tool('DEFENSA')
    assert (t.thickness, t.height) == pytest.approx((0.05, 1.10))
    draw(t, (0, 0), (4, 0))
    [w] = s.walls().values()
    m = s.meta(w)
    assert m['wall_category'] == 'defensa' and m['defense_type'] == 'barandilla'
    assert m['void_ratio'] == pytest.approx(0.85) and m['height'] == pytest.approx(1.10)
    assert w.dxf.layer.startswith('ARQ-DEFENSAS')


def test_opciones_antepecho_y_huecos(plugin):
    s = Session(plugin)
    t = s.tool('DEFENSA')
    t.on_option('p')                                   # antepecho macizo
    assert (t.thickness, t.bim['void_ratio']) == pytest.approx((0.15, 0.0))
    assert t.on_option('h') is True and 'macizo' in str(s.out[-1])
    t.on_option('b')
    t.on_option('h'); t.on_option('60')
    assert t.bim['void_ratio'] == pytest.approx(0.60)
    t.on_option('a'); t.on_option('0,80')              # altura baja: aviso del DB-SUA 1
    assert any('DB-SUA 1' in str(x) for x in s.out)


def test_exportacion_barandilla_y_antepecho(plugin, tmp_path):
    s = Session(plugin)
    t = s.tool('DEFENSA')
    draw(t, (0, 0), (4, 0))
    t = s.tool('DEFENSA')
    t.on_option('p')
    draw(t, (0, 2), (4, 2))
    data = s.export(tmp_path)
    [rail] = _el(data, 'IfcRailing')
    assert rail['enums']['PredefinedType'] == 'GUARDRAIL'
    assert rail['psets']['Pset_RailingCommon']['Height'] == pytest.approx(1.10)
    assert rail['psets']['ARQ_Defensa']['PorcentajeHuecos'] == pytest.approx(85.0)
    solid = 4.0 * 0.05 * 1.10
    assert 0 < rail['volume'] < 0.5 * solid           # pasamanos y montantes, no un prisma
    [parapet] = [e for e in _el(data, 'IfcWall') if e['enums']['PredefinedType'] == 'PARAPET']
    assert parapet['volume'] == pytest.approx(4.0 * 0.15 * 1.10)
    # el sólido de la barandilla es cerrado: lo comprueba el validador de la extensión
    from ingetrazo_ext import arquitectura_bim as X
    X.validate_contract(json.loads(json.dumps(data)))


def test_una_defensa_no_admite_carpinterias(plugin):
    s = Session(plugin)
    t = s.tool('DEFENSA')
    t.on_option('p')
    draw(t, (0, 0), (4, 0))
    c = s.tool('CARPINTERIA')
    c.preview_entities((2.0, 0.075))
    c.on_option('0,50')
    assert not [e for e in s.document.doc.modelspace() if (s.meta(e) or {}).get('kind') == 'opening']


def test_la_defensa_cierra_una_terraza(plugin):
    s = Session(plugin)
    m = s.tool('MURO')
    m.thickness, m.reference = 0.30, 'eje'
    draw(m, (0, 3), (0, 0), (6, 0), (6, 3))           # tres lados de muro
    t = s.tool('DEFENSA')
    draw(t, (0, 3), (6, 3))                           # la barandilla cierra el cuarto
    r = s.tool('RECINTO')
    r.on_point((3.0, 1.5))
    [sp] = _spaces(s)
    assert s.meta(sp)['area'] == pytest.approx((6 - 0.30) * (3 - 0.15 - 0.025), abs=1e-6)


# --- PARTICIONVIRTUAL --------------------------------------------------------------
def test_particion_virtual_reparte_el_recinto(plugin, tmp_path):
    s = Session(plugin)
    _box(s)                                            # interior 7,70 x 4,70
    p = s.tool('PARTICIONVIRTUAL')
    draw(p, (3.0, 0.0), (3.0, 5.0))                   # del eje de un muro al del otro
    for seed in ((1.5, 2.5), (5.5, 2.5)):
        r = s.tool('RECINTO')
        r.on_point(seed)
    a, b = sorted(s.meta(e)['area'] for e in _spaces(s))
    assert a == pytest.approx((3.0 - 0.15) * 4.70)
    assert b == pytest.approx((8.0 - 0.15 - 3.0) * 4.70)
    assert a + b == pytest.approx(7.70 * 4.70)        # sin pérdida de área
    data = s.export(tmp_path)
    [vp] = data['virtual_partitions']
    assert vp['ifc_class'] == 'IfcVirtualElement' and len(vp['points']) == 2
    assert all(sp['params']['virtual_boundaries'] == [vp['id']] for sp in _el(data, 'IfcSpace'))
    assert not [e for e in data['elements'] if e['ifc_class'] == 'IfcVirtualElement']


def test_particion_que_no_cruza_no_separa(plugin):
    s = Session(plugin)
    _box(s)
    p = s.tool('PARTICIONVIRTUAL')
    draw(p, (3.0, 0.0), (3.0, 3.0))                   # se queda a medio camino
    r = s.tool('RECINTO')
    r.on_point((1.5, 2.5))
    [sp] = _spaces(s)
    assert s.meta(sp)['area'] == pytest.approx(7.70 * 4.70)


def test_mover_la_particion_rehace_los_recintos_y_se_deshace(plugin):
    s = Session(plugin)
    _box(s)
    p = s.tool('PARTICIONVIRTUAL')
    draw(p, (3.0, 0.0), (3.0, 5.0))
    r = s.tool('RECINTO')
    r.on_point((1.5, 2.5))
    [sp] = _spaces(s)
    assert s.meta(sp)['area'] == pytest.approx(2.85 * 4.70)
    [vp] = [e for e in s.document.doc.modelspace() if (s.meta(e) or {}).get('kind') == 'virtual_partition']
    assert vp.dxf.linetype in ('DASHED', 'Continuous')
    # edición nativa de IngeCAD (pinzamientos): la geometría manda y el reactor regenera
    from core.actions import TransformCommand
    from ezdxf.math import Matrix44
    from importlib import import_module
    WN = import_module(s.plugin.commands['EXPORTARBIM'].__module__.rsplit('.', 1)[0] + '.wall_network')
    s.history.execute(TransformCommand('MOVE', [vp], Matrix44.translate(1.0, 0.0, 0.0)))
    s.history.execute(WN.RegenerateContoursCommand())   # lo que hace el reactor en IngeCAD
    [sp] = _spaces(s)
    assert s.meta(sp)['area'] == pytest.approx(3.85 * 4.70)
    s.history.undo()
    s.history.undo()
    [sp] = _spaces(s)
    assert s.meta(sp)['area'] == pytest.approx(2.85 * 4.70)


def test_particion_en_l(plugin):
    s = Session(plugin)
    _box(s)
    p = s.tool('PARTICIONVIRTUAL')
    draw(p, (3.0, 0.0), (3.0, 2.0), (8.0, 2.0))       # encierra la esquina inferior derecha
    r = s.tool('RECINTO')
    r.on_point((5.5, 1.0))
    [sp] = _spaces(s)
    assert s.meta(sp)['area'] == pytest.approx((7.85 - 3.0) * (2.0 - 0.15))


# --- RG-01 (revisión de Codex): medidas negativas de carpintería -----------------
def test_cerco_negativo_se_rechaza_y_un_registro_antiguo_se_senala(plugin):
    from importlib import import_module
    s = Session(plugin)
    _box(s)
    root = s.plugin.commands['EXPORTARBIM'].__module__.rsplit('.', 1)[0]
    V10 = import_module(root + '.architectural_v10')
    A = import_module(root + '.architectural')
    IG = import_module(root + '.integrity')
    wall = next(iter(s.walls().values()))
    with pytest.raises(ValueError, match='cerco'):
        V10.create_opening(wall, 2.0, 1.2, 0.9, 1.2, kind='ventana', frame_width=-0.05)
    s.history.execute(V10.create_opening(wall, 2.0, 1.2, 0.9, 1.2, kind='ventana'))
    [win] = [e for e in s.document.doc.modelspace() if (s.meta(e) or {}).get('kind') == 'opening']
    old = dict(s.meta(win), frame_width=-0.05)        # un dibujo antiguo con la medida imposible
    A._xdata(s.document.doc.modelspace(), win, old)
    texts = [p['text'] for p in IG.audit(s.document.doc)]
    assert any('cerco negativo' in t for t in texts)
    assert s.meta(win)['frame_width'] == pytest.approx(-0.05)   # se señala, no se corrige en silencio

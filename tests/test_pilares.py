# SPDX-License-Identifier: GPL-3.0-or-later
"""Pilares: perfiles normalizados, colocación a distancia de paramentos,
pilares embebidos en muros y recintos que descuentan lo que sobresale."""
import math

import pytest
from shapely.geometry import Polygon
from shapely.ops import unary_union

from arquitectura import profiles as PR
from arquitectura import sections as SEC
from core import actions

from tests.test_ingecad_integration import plugin  # noqa: F401  (fixture)
from tests.test_recintos import _cmd_ctx, _spaces
from tests.test_wall_tools import Session, draw


# --- tablas y geometría de perfiles -------------------------------------------------

@pytest.mark.parametrize("family", ["IPE", "HEA", "HEB", "IPN", "UPN"])
def test_contornos_reproducen_el_area_de_tabla(family):
    for size in getattr(PR, family):
        p = {"family": family, "size": size}
        polys = [Polygon(q) for q in PR.outlines(p)]
        assert all(q.is_valid for q in polys)
        assert sum(q.area for q in polys) == pytest.approx(PR.nominal_area(p), rel=0.009), (family, size)


def test_dos_upn():
    caj = PR.parse("2UPN 160 cajon")
    emp = PR.parse("2upn 160 empresillado 0,10")
    assert PR.envelope(caj) == pytest.approx((0.130, 0.160))           # 2 · 65 mm
    assert PR.envelope(emp) == pytest.approx((0.230, 0.160))           # + 100 mm
    a, b = (Polygon(q) for q in PR.outlines(emp))
    assert a.intersection(b).area == 0
    assert PR.nominal_area(caj) == pytest.approx(2 * 24.0e-4)
    with pytest.raises(ValueError):
        PR.parse("IPE 210")


def test_seccion_tecleada():
    assert SEC.parse_section("30x40") == {"shape": "rect", "width": 0.30, "depth": 0.40}
    assert SEC.parse_section("0,25x0,25")["width"] == pytest.approx(0.25)
    assert SEC.parse_section("D35") == {"shape": "circ", "radius": 0.175}
    assert SEC.parse_section("heb 160")["profile"] == "HEB 160"
    v = {"shape": "rect", "width": 0.3, "depth": 0.3, "cover": 0.02, "rotation": 30}
    g = SEC.column_geometry((1, 1), v)
    assert Polygon(g["footprint"]).area == pytest.approx(0.34 ** 2)
    assert Polygon(g["sections"][0]).area == pytest.approx(0.09)
    # el pilar rectangular ya respeta la rotación
    assert math.degrees(math.atan2(g["footprint"][1][1] - g["footprint"][0][1],
                                   g["footprint"][1][0] - g["footprint"][0][0])) == pytest.approx(30)


def test_enganches():
    v = {"shape": "rect", "width": 0.4, "depth": 0.2}
    assert SEC.center_from_anchor((0, 0), v, 1) == pytest.approx((0.2, 0.1))   # esquina inf. izq.
    assert SEC.center_from_anchor((0, 0), v, 9) == pytest.approx((-0.2, -0.1))
    assert SEC.center_from_anchor((0, 0), v, 5) == pytest.approx((0, 0))


# --- colocación sobre IngeCAD real ---------------------------------------------------

def _cerramiento(s, t=0.30):
    """8 x 5 m de muros de 0,30 al eje: caras exteriores en x=-0,15 / y=-0,15."""
    w = s.tool('MURO')
    w.thickness, w.reference = t, 'eje'
    draw(w, (0, 0), (8, 0), (8, 5), (0, 5), (0, 0))


def _columns(s):
    return [e for e in s.document.doc.modelspace() if (s.meta(e) or {}).get('kind') == 'column']


def test_pilar_de_esquina_a_5_cm_de_las_caras_exteriores(plugin, tmp_path):
    s = Session(plugin)
    _cerramiento(s)
    t = s.tool('PILAR')
    t.on_option('s')
    t.on_option('0,30x0,30')
    t.on_option('p')
    t.on_option('0,05')
    t.on_point((4.0, -0.15))                 # cara exterior del muro sur
    t.on_point((-0.15, 2.5))                 # cara exterior del muro oeste
    t.on_point((1.0, 1.0))                   # hacia dentro del edificio
    assert _columns(s), s.out[-6:]
    c = _columns(s)[0]
    xs = [p[0] for p in c.get_points('xy')]
    ys = [p[1] for p in c.get_points('xy')]
    assert (min(xs), min(ys), max(xs), max(ys)) == pytest.approx((-0.10, -0.10, 0.20, 0.20))
    # corta la cara interior (0,15) y sobresale 5 cm hacia la estancia
    data = s.export(tmp_path)
    assert not data['issues']
    polys = [Polygon(o, h) for e in data['elements'] for o, h in e['footprint']]
    assert sum(q.area for q in polys) == pytest.approx(unary_union(polys).area, abs=1e-9)
    r = s.tool('RECINTO')
    r.on_point((4.0, 2.5))
    area = s.meta(_spaces(s)[0])['area']
    assert area == pytest.approx(7.70 * 4.70 - 0.05 * 0.05)    # descuenta lo que sobresale


def test_perfil_heb_con_recubrimiento_y_revestimiento(plugin, tmp_path):
    s = Session(plugin)
    _cerramiento(s)
    t = s.tool('PILAR')
    t.on_option('s')
    t.on_option('HEB 160')
    t.on_option('c')
    t.on_option('0,03')
    t.on_option('p')
    t.on_option('0,05')
    t.on_point((4.0, -0.15))
    t.on_point((-0.15, 2.5))
    t.on_point((1.0, 1.0))
    s.plugin.commands['UNIONESARQ'](_cmd_ctx(s))
    details = [e for e in s.document.doc.modelspace() if (s.meta(e) or {}).get('kind') == 'column_detail']
    assert len(details) == 1                                           # el perfil, dibujado
    data = s.export(tmp_path)
    col = next(e for e in data['elements'] if e['ifc_class'] == 'IfcColumn')
    cov = next(e for e in data['elements'] if e['ifc_class'] == 'IfcCovering')
    a_heb = PR.nominal_area(PR.parse('HEB 160'))
    assert col['quantities']['CrossSectionArea'] == pytest.approx(a_heb, rel=0.009)
    assert col['psets']['ARQ_Perfil']['Masa_kg_m'] == pytest.approx(42.6, abs=0.1)
    box = 0.22 * 0.22                                                  # (0,16 + 2·0,03)²
    assert col['quantities']['CrossSectionArea'] + cov['quantities']['GrossArea'] == pytest.approx(box)
    assert col['volume'] + cov['volume'] == pytest.approx(box * col['params']['height'])
    assert not data['issues']


def test_ipe_a_distancia_de_un_paramento_con_autorrotacion(plugin, tmp_path):
    s = Session(plugin)
    w = s.tool('MURO')
    w.thickness, w.reference = 0.30, 'eje'
    draw(w, (0, 0), (8, 6))                                             # muro inclinado
    t = s.tool('PILAR')
    t.on_option('s')
    t.on_option('IPE 200')
    t.on_option('u')
    t.on_option('0,05')
    ang = math.atan2(6, 8)
    n = (-math.sin(ang), math.cos(ang))
    face = (4.0 + n[0] * 0.15, 3.0 + n[1] * 0.15)                       # cara izquierda
    t.on_point(face)
    t.on_point((face[0] + n[0] * 0.5, face[1] + n[1] * 0.5))           # lado de la cara
    m = s.meta(_columns(s)[0])
    assert m['rotation'] == pytest.approx(math.degrees(ang))
    w_, d_ = SEC.local_size(m)
    # su cara más próxima, a 0,05 de la cara del muro (fuera del muro)
    cx, cy = m['center']
    dist = (cx - face[0]) * n[0] + (cy - face[1]) * n[1]
    assert dist == pytest.approx(0.05 + d_ / 2)


def test_giro_generico_actualiza_la_rotacion(plugin, tmp_path):
    s = Session(plugin)
    t = s.tool('PILAR')
    t.on_option('s')
    t.on_option('HEB 200')
    t.on_point((3.0, 3.0))
    c = _columns(s)[0]
    s.history.execute(actions.rotate_entities([c], (3.0, 3.0), 30.0))
    s.plugin.commands['UNIONESARQ'](_cmd_ctx(s))
    assert s.meta(c)['rotation'] == pytest.approx(30.0)
    det = next(e for e in s.document.doc.modelspace() if (s.meta(e) or {}).get('kind') == 'column_detail')
    sec = SEC.column_geometry(s.meta(c)['center'], s.meta(c))['sections'][0]
    got = [c for p in det.get_points('xy') for c in p[:2]]
    assert got == pytest.approx([c for p in sec for c in p])


def test_dos_upn_en_cajon(plugin, tmp_path):
    s = Session(plugin)
    t = s.tool('PILAR')
    t.on_option('s')
    t.on_option('2UPN 160 cajon')
    t.on_option('e')
    t.on_option('1')                                                    # esquina inf. izq.
    t.on_point((0.0, 0.0))
    data = s.export(tmp_path)
    col = next(e for e in data['elements'] if e['ifc_class'] == 'IfcColumn')
    cov = next(e for e in data['elements'] if e['ifc_class'] == 'IfcCovering')
    assert cov['type_name'] == 'Interior del cajeado del perfil'
    assert col['quantities']['CrossSectionArea'] + cov['quantities']['GrossArea'] == pytest.approx(0.13 * 0.16)
    xs = [p[0] for p in _columns(s)[0].get_points('xy')]
    assert min(xs) == pytest.approx(0.0)

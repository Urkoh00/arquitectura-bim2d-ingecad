# SPDX-License-Identifier: GPL-3.0-or-later
"""COTAMUROS: two clicks across the walls dimension every face (the derived
outline, the same the 3D model uses), as ordinary IngeCAD dimensions."""
import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401  (fixture)
from tests.test_recintos import _vivienda
from tests.test_wall_tools import Session


def _dims(s):
    return [e for e in s.document.doc.modelspace() if e.dxftype() == 'DIMENSION']


def test_cotas_a_traves_de_los_muros(plugin):
    s = Session(plugin)
    _vivienda(s)                          # 8 x 5, muros de 0,30 al eje; tabique de 0,10 en x = 4
    t = s.tool('COTAMUROS')
    t.on_point((-1, 2.5))
    t.on_point((9, 2.5))
    dims = _dims(s)
    # caras en x = -0,15  0,15  3,95  4,05  7,85  8,15 -> 5 cotas + la total
    assert len(dims) == 6
    values = sorted(round(d.get_measurement(), 3) for d in dims)
    assert values == pytest.approx(sorted([0.30, 3.80, 0.10, 3.80, 0.30, 8.30]))
    assert all(d.dxf.layer == 'ARQ-COTAS' and d.dxf.dimstyle == 'ARQ' for d in dims)
    st = s.document.doc.dimstyles.get('ARQ')
    assert st.dxf.dimtxt == pytest.approx(0.20) and st.dxf.dimdec == 2
    s.history.undo()                      # una sola operación deshacible
    assert not _dims(s)
    t = s.tool('COTAMUROS')
    t.on_option('o')                      # sin total
    t.on_option('t')
    t.on_option('0,25')
    t.on_point((2, -1))
    t.on_point((2, 6))                    # atraviesa los dos muros horizontales
    dims = _dims(s)
    assert sorted(round(d.get_measurement(), 3) for d in dims) == pytest.approx([0.30, 0.30, 4.70])
    assert s.document.doc.dimstyles.get('ARQ').dxf.dimtxt == pytest.approx(0.25)


def test_cotamuros_sin_muros_no_dibuja(plugin):
    s = Session(plugin)
    _vivienda(s)
    t = s.tool('COTAMUROS')
    t.on_point((20, 20))
    t.on_point((30, 20))
    assert not _dims(s)


def test_cruces_con_arco():
    from arquitectura import cotas
    pts = cotas.crossings([('arc', (0, 0), 5.0, 0.0, 180.0), ('arc', (0, 0), 4.7, 0.0, 180.0)],
                          (0, -1), (0, 10))
    assert [round(p[1], 6) for p in pts] == [4.7, 5.0]


def test_cotas_de_fachada(plugin):
    """A line outside, along the façade: its corners and the door jambs,
    with the dimension line where it was drawn and the total beyond it."""
    s = Session(plugin)
    _vivienda(s)
    p = s.tool('PUERTAARQ')
    p.on_point((2, 0.15))
    p.on_point((3, 0.15))
    door = next(s.meta(e) for e in s.document.doc.modelspace() if (s.meta(e) or {}).get('kind') == 'opening')
    t = s.tool('COTAMUROS')
    t.on_point((-1, -0.8))
    t.on_point((9, -0.8))
    dims = _dims(s)
    values = sorted(round(d.get_measurement(), 3) for d in dims)
    assert len(dims) == 4 and values[-1] == pytest.approx(8.30)
    assert values[0] == pytest.approx(round(door['width'], 3))          # the hole
    assert sum(values[:-1]) == pytest.approx(8.30)
    chain = [d for d in dims if abs(d.get_measurement() - 8.30) > 1e-6]
    assert all(abs(d.dxf.defpoint.y + 0.8) < 1e-6 for d in chain)       # on the drawn line
    total = next(d for d in dims if abs(d.get_measurement() - 8.30) < 1e-6)
    assert total.dxf.defpoint.y < -0.8                                  # beyond it
    assert all(abs(d.dxf.defpoint2.y + 0.15) < 1e-6 for d in dims)      # measured on the face


def test_cota_minima_de_las_opciones_generales(plugin):
    """General options: distances shorter than the minimum are merged with
    the next one (the chain stays continuous), as the user's old CT did."""
    from importlib import import_module
    from arquitectura import cotas
    pts = [(0, 0), (0.3, 0), (4.1, 0), (4.2, 0), (8, 0), (8.3, 0)]
    assert cotas.thin_out(pts, 0) == pts
    assert cotas.thin_out(pts, 0.15) == [(0, 0), (0.3, 0), (4.1, 0), (8, 0), (8.3, 0)]
    assert cotas.thin_out(pts, 0.5) == [(0, 0), (4.1, 0), (8.3, 0)]
    s = Session(plugin)
    _vivienda(s)
    pa = import_module(s.plugin.tools['PILAR'].__module__.rsplit('.', 1)[0] + '.parameters_arq')
    values = pa.load_defaults(s.document)
    values['general']['cota_minima'] = 0.15
    s.history.execute(pa.SetArchitecturalDefaults(values))
    assert pa.general_options(s.document)['cota_minima'] == pytest.approx(0.15)
    t = s.tool('COTAMUROS')
    t.on_option('o')
    t.on_point((-1, 2.5))
    t.on_point((9, 2.5))
    values = sorted(round(d.get_measurement(), 3) for d in _dims(s))
    # the 0,10 partition is merged into the next room: 0,30 3,80 3,90 0,30
    assert values == pytest.approx(sorted([0.30, 3.80, 3.90, 0.30]))


def test_parametros_se_guardan_en_ascii(plugin, tmp_path):
    """The defaults go into the DXF as plain ASCII: an accent written raw
    made the file look like text of unknown encoding (prueba del 10-11)."""
    from importlib import import_module
    import ezdxf
    s = Session(plugin)
    pa = import_module(s.plugin.tools['PILAR'].__module__.rsplit('.', 1)[0] + '.parameters_arq')
    values = pa.load_defaults(s.document)
    values['column']['material'] = 'Hormigón armado'
    s.history.execute(pa.SetArchitecturalDefaults(values))
    path = tmp_path / 'p.dxf'
    s.document.doc.saveas(path)
    raw = path.read_bytes()
    assert all(b < 128 for b in raw), 'el DXF contiene bytes fuera de ASCII'
    again = ezdxf.readfile(path)
    s.document.doc = again
    assert pa.load_defaults(s.document)['column']['material'] == 'Hormigón armado'

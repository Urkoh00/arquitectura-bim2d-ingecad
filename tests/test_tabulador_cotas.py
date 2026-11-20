# SPDX-License-Identifier: GPL-3.0-or-later
"""Tab recorre las cotas temporales y fija su valor (v1.45), sobre IngeCAD real.

Misma vivienda de 8 x 5 m que test_cotas_temporales: el paramento libre del
muro sur en la estancia 1 va de x = 0,15 a x = 3,95 (cara interior y = 0,15)."""
import math

import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401  (fixture)
from tests.test_recintos import _vivienda
from tests.test_wall_tools import Session
from tests.test_carpinteria import _openings


def _texts(ents, color=None):
    return [e.dxf.text for e in ents if e.dxftype() == "TEXT" and (color is None or e.dxf.color == color)]


def _tab(t, text=""):
    from arquitectura import tabulador
    return tabulador.press(t, text)


def _muro(s, start=(10.0, 10.0)):
    t = s.tool('MURO')
    t.thickness, t.reference = 0.20, 'eje'
    t.on_point(start)
    return t


def _ultimo_muro(s):
    from arquitectura.architectural import metadata
    ws = [metadata(e) for e in s.document.doc.modelspace()
          if (metadata(e) or {}).get('kind') == 'wall' and e.dxftype() == 'LWPOLYLINE']
    return ws[-1]


def _extremos(m):
    a, b = m['a'], m['b']
    return (float(a[0]), float(a[1])), (float(b[0]), float(b[1]))


# --- muros -----------------------------------------------------------------------------
def test_tab_fija_longitud_y_angulo_e_intro_coloca(plugin):
    s = Session(plugin)
    t = _muro(s)
    t.preview_entities((13.0, 12.0))
    assert _tab(t, "5")                               # longitud fijada; activa: ángulo
    assert t.tab_field == "angle" and t.tab_locks == {"length": 5.0}
    ents = t.preview_entities((13.0, 12.0))
    assert "[5,00]" in _texts(ents, 3)                # fijada: verde y entre corchetes
    assert _texts(ents, 30) == [f"{math.degrees(math.atan2(2, 3)):.1f}°".replace(".", ",")]
    t.on_option("90")                                 # el ángulo + Intro: coloca
    a, b = _extremos(_ultimo_muro(s))
    assert a == pytest.approx((10.0, 10.0)) and b == pytest.approx((10.0, 15.0))
    assert t.tab_locks == {} and t.tab_field is None  # el tramo siguiente empieza de cero
    assert t.startpoint == pytest.approx((10.0, 15.0))


def test_angulo_fijado_y_la_longitud_sigue_al_cursor(plugin):
    s = Session(plugin)
    t = _muro(s)
    _tab(t)                                           # Tab sin valor: activa la longitud
    _tab(t)                                           # otra vez: el ángulo
    assert t.tab_field == "angle"
    _tab(t, "<30")                                    # «<30», como en la línea de órdenes
    assert t.tab_locks == {"angle": 30.0}
    t.on_point((14.0, 10.0))                          # clic: la proyección sobre los 30°
    a, b = _extremos(_ultimo_muro(s))
    L = 4.0 * math.cos(math.radians(30))
    assert b == pytest.approx((10.0 + L * math.cos(math.radians(30)),
                               10.0 + L * math.sin(math.radians(30))))


def test_shift_tab_vuelve_y_un_valor_malo_no_fija(plugin):
    s = Session(plugin)
    t = _muro(s)
    _tab(t)
    assert t.tab_field == "length"
    t.on_tab("", backwards=True)
    assert t.tab_field == "angle"
    _tab(t, "abc")
    assert t.tab_locks == {} and any("no es un valor" in str(x) for x in s.out)


def test_sin_tab_el_numero_sigue_siendo_de_ingecad(plugin):
    s = Session(plugin)
    t = _muro(s)
    assert t.on_option("3") is False                  # distancia directa del anfitrión, como antes


def test_tab_no_actua_antes_del_primer_punto(plugin):
    s = Session(plugin)
    t = s.tool('MURO')
    assert not _tab(t, "5")                           # Tab hace lo de siempre
    assert t.tab_locks == {}


# --- carpinterías ----------------------------------------------------------------------
def _door(s):
    t = s.tool('CARPINTERIA')
    return t, t._width()


def test_tab_recorre_izquierda_derecha_ancho(plugin):
    s = Session(plugin)
    _vivienda(s)
    t, _w = _door(s)
    t.preview_entities((1.0, 0.15))
    seen = []
    for _ in range(4):
        _tab(t)
        seen.append(t.dim_active)
    assert seen == ["right", "width", "left", "right"]
    ents = t.preview_entities((1.0, 0.15))
    assert len(_texts(ents, 30)) == 1                 # una sola cota activa


def test_izquierda_y_derecha_fijadas_dan_el_ancho(plugin):
    s = Session(plugin)
    _vivienda(s)
    t, _w = _door(s)
    t.preview_entities((1.0, 0.15))
    _tab(t, "0,50")                                   # izquierda 0,50
    _tab(t, "2,00")                                   # derecha 2,00
    assert set(t.tab_locks) == {"left", "right"} and t.dim_active == "width"
    assert not _openings(s)
    t.on_enter()
    [door] = _openings(s)
    assert s.meta(door)['offset'] == pytest.approx(0.65)
    assert s.meta(door)['width'] == pytest.approx(3.95 - 2.00 - 0.65)
    assert t.tab_locks == {}


def test_ancho_y_distancia_fijados(plugin):
    s = Session(plugin)
    _vivienda(s)
    t = s.tool('VENTANAARQ')
    t.preview_entities((2.0, 0.15))
    t.dim_active = "width"
    _tab(t, "1,20")                                   # ancho del hueco 1,20
    assert t.v['width'] == pytest.approx(1.20)
    assert t.dim_active == "left"
    t.on_option("0,30")                               # izquierda + Intro: coloca
    [w] = _openings(s)
    assert s.meta(w)['offset'] == pytest.approx(0.45)
    assert s.meta(w)['width'] == pytest.approx(1.20)


def test_ancho_de_puerta_fijado_ajusta_la_hoja(plugin):
    s = Session(plugin)
    _vivienda(s)
    t, _w = _door(s)
    t.preview_entities((2.0, 0.15))
    t.dim_active = "width"
    _tab(t, "0,90")
    assert t._width() == pytest.approx(0.90)
    assert t.v['leaf'] == pytest.approx(0.90 - 2 * t.v['frame_width'])


def test_clic_con_cotas_fijadas(plugin):
    s = Session(plugin)
    _vivienda(s)
    t, w = _door(s)
    t.preview_entities((1.0, 0.15))
    t.dim_active = "right"
    _tab(t, "0,40")
    t.on_point((1.0, 0.15))                           # el clic elige el muro; la cota manda
    [door] = _openings(s)
    assert s.meta(door)['offset'] == pytest.approx(3.95 - 0.40 - w)
    assert s.meta(door)['hinge'] == 1


def test_no_cabe_no_crea_y_conserva_lo_fijado(plugin):
    s = Session(plugin)
    _vivienda(s)
    t, _w = _door(s)
    t.preview_entities((1.0, 0.15))
    _tab(t, "2,00")
    _tab(t, "2,00")                                   # 2 + 2 > 3,80 de paramento
    t.on_enter()
    assert not _openings(s) and any("no queda hueco" in str(x) for x in s.out)
    assert set(t.tab_locks) == {"left", "right"}


def test_movercarp_tab_mueve_y_pasa_a_la_otra(plugin):
    s = Session(plugin)
    _vivienda(s)
    t, w = _door(s)
    t.preview_entities((1.0, 0.15))
    t.on_option("1,00")
    [door] = _openings(s)
    m = s.tool('MOVERCARP')
    assert not _tab(m, "0,40")                        # sin carpintería designada
    m.entity = door
    assert _tab(m, "0,40")
    assert s.meta(_openings(s)[0])['offset'] == pytest.approx(0.55)
    assert m.dim_active == "right"
    _tab(m, "0,30")
    assert s.meta(_openings(s)[0])['offset'] == pytest.approx(3.95 - 0.30 - w)


def test_utilidades_tab():
    from arquitectura import temp_dims as TD
    assert TD.next_field(TD.WALL_FIELDS, None) == "length"
    assert TD.next_field(TD.WALL_FIELDS, "angle") == "length"
    assert TD.next_field(TD.CARPENTRY_FIELDS, None, backwards=True) == "width"
    assert TD.parse_angle("<45,5°") == pytest.approx(45.5)
    assert TD.parse_angle("-90") == pytest.approx(270.0)
    assert TD.wall_end((0, 0), (3, 4), length=10) == pytest.approx((6, 8))
    assert TD.wall_end((0, 0), (3, 4), angle=0) == pytest.approx((3, 0))
    assert TD.wall_end((0, 0), (-3, 4), angle=0) is None
    assert TD.wall_end((0, 0), (5, 5), length=2, angle=90) == pytest.approx((0, 2))


def test_el_filtro_de_qt_lleva_tab_a_la_orden(plugin):
    """Con una ventana real: Tab sobre la línea de órdenes va a la orden que
    lo admite, con lo escrito; si no lo admite, Qt hace lo de siempre."""
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication, QLineEdit, QWidget
    from arquitectura import tabulador

    app = QApplication.instance() or QApplication([])

    class Line:
        def __init__(self):
            self.input = QLineEdit()
            self.out = []

        def echo(self, text):
            self.out.append(text)

    class Win(QWidget):
        pass

    class Changed:
        n = 0

        def emit(self):
            Changed.n += 1

    class Tool:
        got = None

        def tab_ready(self):
            return True

        def on_tab(self, text, backwards=False):
            Tool.got = (text, backwards)

    class Services:
        pass

    services = Services()
    services.window = Win()
    services.window.command_line = Line()
    services.changed = Changed()
    services.tool = Tool()

    class Ctx:
        pass

    ctx = Ctx()
    ctx.services = services
    assert tabulador.install(ctx)
    edit = services.window.command_line.input
    edit.setText("2,5")
    app.sendEvent(edit, QKeyEvent(QEvent.KeyPress, Qt.Key_Tab, Qt.NoModifier))
    assert Tool.got == ("2,5", False) and edit.text() == "" and Changed.n == 1
    services.tool = object()                          # una orden que no lo admite
    edit.setText("x")
    app.sendEvent(edit, QKeyEvent(QEvent.KeyPress, Qt.Key_Tab, Qt.NoModifier))
    assert edit.text() == "x" and Changed.n == 1

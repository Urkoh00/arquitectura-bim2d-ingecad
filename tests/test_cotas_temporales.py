# SPDX-License-Identifier: GPL-3.0-or-later
"""Cotas temporales al dibujar muros y colocar carpinterías (v1.26), sobre IngeCAD real.

Vivienda de 8 x 5 m (muros de 0,30 al eje, tabique de 0,10 en x = 4): la cara
interior del muro sur está en y = 0,15 y su paramento libre en la estancia 1
va de x = 0,15 a x = 3,95."""
import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401  (fixture)
from tests.test_recintos import _vivienda
from tests.test_wall_tools import Session
from tests.test_carpinteria import _openings


def _texts(ents):
    return [e.dxf.text for e in ents if e.dxftype() == "TEXT"]


def _active(ents):
    return [e.dxf.text for e in ents if e.dxftype() == "TEXT" and e.dxf.color == 30]


def _door_tool(s):
    t = s.tool('CARPINTERIA')
    w = t._width()
    return t, w


def test_cotas_al_pasar_por_el_muro_y_distancia_escrita(plugin):
    s = Session(plugin)
    _vivienda(s)
    t, w = _door_tool(s)
    ents = t.preview_entities((1.0, 0.15))            # cursor en la cara interior del muro sur
    texts = _texts(ents)
    # cadena: referencia izquierda | hueco | referencia derecha (paramento 0,15 … 3,95)
    assert "0,85" in texts and f"{w:.2f}".replace(".", ",") in texts
    assert f"{3.95 - 1.0 - w:.2f}".replace(".", ",") in texts
    assert _active(ents) == ["0,85"]                  # la cota activa, en otro color
    assert all(e.dxftype() in ("LINE", "TEXT") for e in ents)
    assert not _openings(s)                           # la vista previa no dibuja nada
    t.on_option("1,20")                               # escribir la distancia de la cota activa
    [door] = _openings(s)
    assert s.meta(door)['offset'] == pytest.approx(0.15 + 1.20)
    assert s.meta(door)['hinge'] == 0


def test_otra_cota_y_medida_al_centro(plugin):
    s = Session(plugin)
    _vivienda(s)
    t, w = _door_tool(s)
    t.preview_entities((2.0, 0.15))
    assert t.on_key("F6")                             # la cota activa pasa a la derecha
    t.on_option("0,50")
    [d1] = _openings(s)
    assert s.meta(d1)['offset'] == pytest.approx(3.95 - 0.50 - w)
    assert s.meta(d1)['hinge'] == 1
    t, w = _door_tool(s)
    t.on_option("eje")                                # medir al centro del hueco
    t.preview_entities((5.0, 0.15))                   # estancia 2: paramento 4,05 … 7,85
    t.on_option("1,00")
    d2 = next(o for o in _openings(s) if o is not d1 and s.meta(o)['id'] != s.meta(d1)['id'])
    assert s.meta(d2)['offset'] + w / 2 == pytest.approx(4.05 + 1.00)


def test_la_jamba_de_otra_carpinteria_es_referencia(plugin):
    s = Session(plugin)
    _vivienda(s)
    t, w = _door_tool(s)
    t.preview_entities((1.0, 0.15))
    t.on_option("0,30")                               # primera puerta: jamba en 0,45
    t, w = _door_tool(s)
    ents = t.preview_entities((3.0, 0.15))
    left = 0.45 + w                                   # la jamba derecha de la primera puerta
    assert t._hover[6] == pytest.approx(left)        # es la referencia izquierda
    assert _active(ents) == [f"{t._hover[3] - left:.2f}".replace(".", ",")]
    t.on_option("0,20")
    offsets = sorted(s.meta(o)['offset'] for o in _openings(s))
    assert offsets == pytest.approx([0.45, left + 0.20])


def test_no_cabe_no_crea_nada(plugin):
    s = Session(plugin)
    _vivienda(s)
    t, _w = _door_tool(s)
    t.preview_entities((1.0, 0.15))
    t.on_option("3,50")                               # más allá del paramento
    assert not _openings(s)
    assert any("no cabe" in str(x) for x in s.out)


def test_numero_grande_sigue_siendo_el_ancho_de_hoja(plugin):
    s = Session(plugin)
    _vivienda(s)
    t, _w = _door_tool(s)
    t.preview_entities((1.0, 0.15))
    t.on_option("72")                                 # hoja de 725 mm, como siempre
    assert not _openings(s) and t.v['leaf'] == pytest.approx(0.725)


def test_movercarp_con_cotas_conserva_la_identidad_y_se_deshace(plugin):
    s = Session(plugin)
    _vivienda(s)
    t, w = _door_tool(s)
    t.preview_entities((1.0, 0.15))
    t.on_option("1,00")
    [door] = _openings(s)
    ident = s.meta(door)['id']
    m = s.tool('MOVERCARP')
    m.entity = door                                   # (en IngeCAD: designarla con un clic)
    texts = _texts(m.preview_entities((0.0, 0.0)))
    assert "1,00" in texts
    m.on_option("0,40")
    [door] = _openings(s)
    assert s.meta(door)['id'] == ident and s.meta(door)['offset'] == pytest.approx(0.55)
    m.on_point((3.0, 0.15))                           # clic en el muro: el centro va allí
    [door] = _openings(s)
    assert s.meta(door)['offset'] + w / 2 == pytest.approx(3.0)
    m.on_option("5,00")                               # no cabe: no cambia
    assert s.meta(_openings(s)[0])['offset'] + w / 2 == pytest.approx(3.0)
    s.history.undo()
    assert s.meta(_openings(s)[0])['offset'] == pytest.approx(0.55)


def test_muro_muestra_longitud_angulo_y_distancia_a_paralelos(plugin):
    s = Session(plugin)
    _vivienda(s)
    t = s.tool('MURO')
    t.thickness, t.reference = 0.10, 'eje'
    t.on_point((1.0, 1.0))
    ents = t.preview_entities((3.5, 1.0))
    texts = _texts(ents)
    assert any(x.startswith("2,50") and "0,0°" in x for x in texts)
    # caras interiores de los muros sur (y = 0,15) y norte (y = 4,85)
    assert "0,85" in texts and "3,85" in texts


def test_utilidades(plugin):
    from arquitectura import temp_dims as TD
    assert TD.parse_length("125cm") == pytest.approx(1.25)
    assert TD.parse_length("1,5") == pytest.approx(1.5)
    with pytest.raises(ValueError):
        TD.parse_length("-1")
    class Ctx:
        services = None
    assert TD.world_per_px(Ctx()) == pytest.approx(0.01)
    with pytest.raises(ValueError):
        TD.placement_from_distance("left", 3.0, 0.0, 2.0, 0.9)

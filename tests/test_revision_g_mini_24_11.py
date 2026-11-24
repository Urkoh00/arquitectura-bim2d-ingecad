# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: lista de posibles errores de una revisión externa (24-11), segunda
#   lista. Cada prueba fija un error real comprobado; fallan sin la corrección.
import math

import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401  (fixture)
from tests.test_wall_tools import Session, draw
from tests.test_wall_tools_2 import _door, _openings


def test_cotamuros_con_dos_puntos_iguales_no_rompe():
    from arquitectura.cotas import facade_points
    assert facade_points([], (1.0, 1.0), (1.0, 1.0)) == ([], 0.0)


def test_unirmuro_de_muros_opuestos_conserva_la_carpinteria_en_su_sitio(plugin):  # noqa: F811
    s = Session(plugin)
    t = s.tool('MURO')
    t.thickness = 0.25
    draw(t, (0, 0), (4, 0))
    t = s.tool('MURO')
    t.thickness = 0.25
    draw(t, (10, 0), (5, 0))                       # dibujado en sentido contrario
    ids = list(s.walls())
    first, second = ids[0], ids[1]
    _door(s, s.walls()[second], 1.0)
    antes = dict(s.meta(_openings(s)[0]))
    u = s.tool('UNIRMURO')
    u.on_point((2.0, 0.0))
    u.on_point((7.0, 0.0))
    puerta = s.meta(_openings(s)[0])
    assert puerta['wall_id'] == first
    assert puerta['side'] == -int(antes.get('side') or 1)
    assert int(puerta['hinge']) == (0 if int(antes.get('hinge') or 0) else 1)
    # en el espacio sigue entre x = 8,2 y x = 9 (offset 1 desde x = 10)
    assert puerta['offset'] == pytest.approx(10 - 1.0 - 0.8)


def test_hojas_vacias_es_un_error_claro(plugin):  # noqa: F811
    s = Session(plugin)
    t = s.tool('CARPINTERIA')
    with pytest.raises(ValueError, match="número de hojas"):
        t._set("hojas", " ; ")


def test_forjado_con_nivel_inexistente_usa_el_activo():
    from arquitectura.slab_tools import _nivel
    data = {"active": "a", "levels": [{"id": "a", "name": "PB", "elevation": 0.0}]}
    assert _nivel(data, {"level_id": "borrado"})["id"] == "a"
    assert _nivel(data, {"level_id": None})["id"] == "a"


def test_ficha_de_barandilla_sin_separacion_no_da_keyerror():
    from arquitectura.element_sheets import validate
    assert validate("railing", {"length": 3.0, "height": 1.1})


def test_particion_virtual_toma_la_altura_hasta_el_nivel_siguiente(plugin):  # noqa: F811
    from arquitectura import levels as LV
    from arquitectura import particiones_virtuales as VP
    s = Session(plugin)
    ctx = s.tool("MURO").ctx
    data = LV.load(s.document)
    data["levels"].append({"id": "alta", "name": "Planta alta", "elevation": 2.85})
    LV.apply(ctx, data)
    _n, z, _i, altura = VP._level_of(s.document.doc)
    assert z == 0.0 and altura == pytest.approx(2.85)


def test_la_copia_de_una_particion_virtual_recibe_identidad_propia():
    from arquitectura import sync
    assert "virtual_partition" in sync.KINDS


def test_el_numero_y_el_uso_de_un_recinto_se_pueden_vaciar(monkeypatch):
    import arquitectura.arq_properties as AP
    import arquitectura.architectural_v10 as V10
    registro = {"kind": "space", "id": "r", "name": "Salón", "number": "3", "use": "Estar",
                "height": 2.5}

    class Orden:
        def __init__(self, entidad, d):
            self.d = d

    monkeypatch.setattr(AP, "metadata", lambda e: registro)
    monkeypatch.setattr(V10, "EditArchitecturalCommand", Orden)
    cmd = AP.space_change(object(), {"number": "", "use": ""})
    assert cmd.d["number"] == "" and cmd.d["use"] == ""


def test_defensa_no_se_convierte_en_muro_corriente(plugin):  # noqa: F811
    s = Session(plugin)
    t = s.tool("DEFENSA")
    for palabra in ("fachada", "particion", "tipo", "igual"):
        assert t.on_option(palabra) is True
        assert t.bim["wall_category"] == "defensa"
    assert not getattr(t, "capturing", False)


def test_pilar_seccion_invalida_no_cambia_los_valores(plugin, monkeypatch):  # noqa: F811
    import sys
    s = Session(plugin)
    t = s.tool("PILAR")
    CT = sys.modules[type(t).__module__]             # el módulo que usa la orden
    antes = dict(t.values)
    monkeypatch.setattr(CT.SEC, "local_footprint",
                        lambda v: (_ for _ in ()).throw(ValueError("sección imposible")))
    t.pending = "section"
    t.on_option("0,4x0,4")
    assert t.values == antes


def test_2upn_empresillado_con_separacion_negativa_se_rechaza():
    from arquitectura import profiles as PR
    with pytest.raises(ValueError, match="separación"):
        PR.parse("2UPN 100 empresillado -0,1".replace(",", "."))


def test_tipo_de_muro_nuevo_no_hereda_por_numero():
    """Un tipo llamado «2» heredaba la categoría del segundo tipo."""
    import inspect
    from arquitectura import parameters_arq as PA
    fuente = inspect.getsource(PA)
    assert "previous = find_wall_type(types, entry['name'])" not in fuente


def test_curva_casi_recta_no_divide_por_cero():
    from arquitectura import curved_carpentry as CC
    fuente = __import__("inspect").getsource(CC.pieces)
    assert "step=math.inf" in fuente
    # la expresión original da 0 con un radio enorme
    assert 2 * math.acos(max(-1., 1 - .002 / 1e15)) == 0.0

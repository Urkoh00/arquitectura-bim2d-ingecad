# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: distingue la hoja activa de una carpintería doble sin confundirla con su mano.
from copy import deepcopy
import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_fichas_tipos_usos import qapp  # noqa: F401
from tests.test_wall_tools import Session
from tests.escenarios_r27 import modulo
from tests.test_r27_creacion_texto import responder
from tests.test_r28_oscilobatiente import ventana


@pytest.mark.parametrize("lado", [1, -1])
@pytest.mark.parametrize("bisagra", [0, 1])
def test_el_valor_ausente_se_deduce_de_la_mano_existente(plugin, lado, bisagra):
    datos = modulo(plugin, "openings").normalise(ventana(leaves=2, side=lado, hinge=bisagra))
    assert datos["main_leaf"] == ("left" if (bisagra == 0) == (lado > 0) else "right")


@pytest.mark.parametrize("principal", ["left", "right"])
@pytest.mark.parametrize("lado", [1, -1])
def test_solo_la_principal_bascula_y_ambas_hojas_pueden_girar(plugin, principal, lado):
    aberturas = modulo(plugin, "openings")
    muro = modulo(plugin, "geom.junctions").Wall("muro", (0, 0), (8, 0), 0.3, "eje")
    datos = ventana(leaves=2, side=lado, main_leaf=principal)
    alzado = aberturas.simbolos_apertura_alzado(datos)
    assert len(alzado) == 3
    basculante = next(trazo for trazo in alzado if trazo[0][1] == trazo[-1][1])
    centro = basculante[1][0]
    izquierda_en_eje = (principal == "left") == (lado > 0)
    assert (centro < 1.6) == izquierda_en_eje
    planta = aberturas.plan_symbol(muro, datos)
    assert len([g for g in planta if g[0] == "arc"]) == 2
    assert len([g for g in planta if g[0] == "poly" and not g[2] and len(g[1]) == 3]) == 1


def test_la_principal_separa_tipos_y_la_mano_sigue_sin_separarlos(plugin):
    memoria = modulo(plugin, "memoria_carpinteria")
    muro = modulo(plugin, "geom.junctions").Wall("muro", (0, 0), (8, 0), 0.3, "eje")
    primera = ventana(id="a", leaves=2, main_leaf="left")
    opuesta = {**primera, "id": "b", "hinge": 1, "offset": 4.0}
    diferente = {**primera, "id": "c", "main_leaf": "right"}
    assert memoria.iguales(memoria.definir(muro, primera), memoria.definir(muro, opuesta))
    assert not memoria.iguales(memoria.definir(muro, primera), memoria.definir(muro, diferente))
    piezas = [pieza for registro in (primera, opuesta, diferente) for pieza in memoria.unidades(muro, registro)]
    grupos, _ = memoria.asignar_marcas(piezas)
    assert sorted(len(grupo["piezas"]) for grupo in grupos) == [1, 2]


def test_un_catalogo_v147_conserva_su_marca_al_anadir_la_principal(plugin):
    memoria = modulo(plugin, "memoria_carpinteria")
    muro = modulo(plugin, "geom.junctions").Wall("muro", (0, 0), (8, 0), 0.3, "eje")
    piezas = list(memoria.unidades(muro, ventana(id="a", leaves=2, main_leaf="left")))
    _, catalogo = memoria.asignar_marcas(piezas)
    antiguo = deepcopy(catalogo)
    antiguo["tipos"][0]["definicion"].pop("main_leaf", None)
    piezas += list(memoria.unidades(muro, ventana(id="b", leaves=2, main_leaf="right")))
    grupos, nuevo = memoria.asignar_marcas(piezas, antiguo)
    assert sorted(grupo["marca"] for grupo in grupos) == ["V1", "V2"]
    assert all("main_leaf" in tipo["definicion"] for tipo in nuevo["tipos"])


@pytest.mark.parametrize("orden", ["CARPINTERIA", "VENTANAARQ", "PUERTAARQ"])
def test_la_ficha_y_el_guion_comparten_la_principal_exterior(plugin, qapp, orden):
    sesion = Session(plugin)
    herramienta = sesion.tool(orden)
    ficha, leer = modulo(plugin, "bim_dialogs").carpentry_form(herramienta.ctx, {**herramienta.v, **herramienta.bim})
    ficha._arq["leaves"].setValue(2)
    selector = ficha._arq["main_leaf"]
    selector.setCurrentIndex(selector.findData("right"))
    datos_ficha = leer()
    variante = sesion.tool("-" + orden)
    responder(variante, {"leaves": "2", "main_leaf": "Derecha"})
    assert datos_ficha["main_leaf"] == variante.v["main_leaf"] == "right"
    assert datos_ficha["leaves"] == variante.v["leaves"] == 2
    ficha.close()

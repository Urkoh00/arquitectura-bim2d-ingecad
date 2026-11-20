# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: igualdad física, frentes de armario y marcas estables con tolerancia y sin redondeo.
from copy import deepcopy
import importlib
import pytest
from tests.test_ingecad_integration import plugin  # noqa: F401


def modulos(plugin):
    paquete = plugin.tools["MURO"].__module__.rsplit(".", 1)[0]
    memoria = importlib.import_module(paquete + ".memoria_carpinteria")
    geometria = importlib.import_module(paquete + ".geom.junctions")
    return memoria, geometria.Wall("muro", (0.0, 0.0), (12.0, 0.0), 0.3, "eje")


def registro(**cambios):
    return {
        "id": "puerta",
        "type": "door",
        "width": 0.885,
        "height": 2.1,
        "sill": 0.0,
        "offset": 1.0,
        **cambios,
    }


def test_mano_y_posicion_no_separan_marcas(plugin):
    memoria, muro = modulos(plugin)
    a = registro()
    b = registro(id="otra", side=-1, hinge=1, offset=4.0)
    assert memoria.iguales(memoria.definir(muro, a), memoria.definir(muro, b))
    piezas = list(memoria.unidades(muro, a)) + list(memoria.unidades(muro, b))
    grupos, catalogo = memoria.asignar_marcas(piezas)
    assert len(grupos) == 1 and grupos[0]["marca"] == "P1"
    assert len(grupos[0]["piezas"]) == 2
    assert len(catalogo["tipos"]) == 1


def test_medidas_cruzan_frontera_de_redondeo_con_tolerancia(plugin):
    memoria, muro = modulos(plugin)
    primera = memoria.definir(muro, registro(width=0.885000049))
    segunda = memoria.definir(muro, registro(width=0.885000051))
    assert memoria.iguales(primera, segunda)
    assert not memoria.iguales(primera, memoria.definir(muro, registro(width=0.886)))


def test_marcas_estables_altas_cambios_y_retiradas(plugin):
    memoria, muro = modulos(plugin)
    inicial = list(memoria.unidades(muro, registro()))
    grupos, catalogo = memoria.asignar_marcas(inicial)
    antes = deepcopy(catalogo)
    nuevos = list(memoria.unidades(muro, registro(id="nueva", offset=4.0)))
    grupos, catalogo = memoria.asignar_marcas(inicial + nuevos, catalogo)
    assert grupos[0]["marca"] == "P1" and len(grupos) == 1
    diferentes = list(memoria.unidades(muro, registro(width=1.085)))
    grupos, catalogo = memoria.asignar_marcas(diferentes, catalogo)
    assert grupos[0]["marca"] == "P2"
    assert [t["marca"] for t in catalogo["tipos"]] == ["P2"]
    assert antes["tipos"][0]["marca"] == "P1"


def test_materiales_y_operacion_separan_piezas(plugin):
    memoria, muro = modulos(plugin)
    inicial = memoria.definir(muro, registro())
    for cambios in ({"operation": "SLIDING"}, {"leaf_material": "Acero"}, {"sill": 0.1}):
        assert not memoria.iguales(inicial, memoria.definir(muro, registro(**cambios)))


def test_frentes_de_armario_salen_del_generador_existente(plugin):
    memoria, muro = modulos(plugin)
    piezas = list(
        memoria.unidades(
            muro,
            registro(
                cabinet=True,
                cabinet_mode="adosado",
                niche_depth=0.6,
                leaves=4,
                width=2.0,
                operation="SLIDING",
            ),
        )
    )
    assert len(piezas) == 4
    grupos, _ = memoria.asignar_marcas(piezas)
    assert len(grupos) == 1 and grupos[0]["marca"] == "A1"
    assert grupos[0]["definicion"]["leaves"] == 1
    assert grupos[0]["definicion"]["ancho"] < 0.5


def test_renombrar_valida_prefijo_y_no_modifica_catalogo(plugin):
    memoria, muro = modulos(plugin)
    _, catalogo = memoria.asignar_marcas(list(memoria.unidades(muro, registro())))
    nuevo = memoria.renombrar(catalogo, "P1", "P9")
    assert catalogo["tipos"][0]["marca"] == "P1"
    assert nuevo["tipos"][0]["marca"] == "P9"
    assert nuevo["siguientes"]["P"] == 10
    with pytest.raises(ValueError):
        memoria.renombrar(catalogo, "P1", "V1")

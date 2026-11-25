# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: el lado exterior se obtiene de la geometría, incluidos patios y recintos exteriores.
import pytest

from arquitectura.geom import junctions as J
from arquitectura.geom import spaces as SP


def anillo(prefijo, minimo, maximo, referencia="eje", invertir=False):
    x0, y0 = minimo
    x1, y1 = maximo
    puntos = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    if invertir:
        puntos.reverse()
    return [J.Wall(prefijo + str(i), a, b, 0.2, referencia)
            for i, (a, b) in enumerate(zip(puntos, puntos[1:] + puntos[:1]))]


@pytest.mark.parametrize("referencia", ["eje", "izquierda", "derecha"])
@pytest.mark.parametrize("invertir", [False, True])
def test_ambas_caras_dibujadas_y_ambos_sentidos_dan_el_exterior_geometrico(referencia, invertir):
    muros = anillo("m", (0, 0), (10, 8), referencia, invertir)
    resultado = J.solve(muros)
    esperado = "izquierda" if invertir else "derecha"
    assert SP.external_walls(resultado, con_lados=True) == {m.id: esperado for m in muros}
    assert SP.external_walls(resultado) == {m.id for m in muros}


def test_un_muro_abierto_no_tiene_un_lado_exterior_unico():
    resultado = J.solve([J.Wall("abierto", (0, 0), (5, 0), 0.3)])
    assert SP.external_walls(resultado, con_lados=True) == {"abierto": None}


def test_una_particion_aislada_dentro_del_edificio_no_es_una_fachada():
    muros = anillo("fachada", (0, 0), (10, 8))
    resultado = J.solve([*muros, J.Wall("particion", (2, 3), (6, 3), 0.1)])
    assert SP.external_walls(resultado) == {m.id for m in muros}


@pytest.mark.parametrize("exterior_cubierto", [False, True])
def test_un_patio_o_recinto_exterior_expone_la_cara_que_lo_limita(exterior_cubierto):
    muros = anillo("fachada", (0, 0), (12, 12)) + anillo("patio", (4, 4), (8, 8))
    resultado = J.solve(muros)
    patio, motivo = SP.space_at(resultado, (6, 6))
    assert not motivo
    patio["enclosure"] = "exterior_cubierto" if exterior_cubierto else "exterior_descubierto"
    lados = SP.external_walls(resultado, exteriores=[patio], con_lados=True)
    assert lados == {**{"fachada" + str(i): "derecha" for i in range(4)},
                     **{"patio" + str(i): "izquierda" for i in range(4)}}
    assert SP.external_walls(resultado) == {"fachada" + str(i) for i in range(4)}


def test_el_lado_exterior_de_un_muro_curvo_sigue_su_normal_local():
    muros = [J.Wall("arco1", (-4, 0), (4, 0), 0.2, bulge=1),
             J.Wall("arco2", (4, 0), (-4, 0), 0.2, bulge=1)]
    resultado = J.solve(muros)
    assert SP.external_walls(resultado, con_lados=True) == {"arco1": "derecha", "arco2": "derecha"}


@pytest.mark.parametrize("situacion,es_exterior", [
    ("interior", False),
    (None, False),
    ("sin_revisar", False),
    ("exterior_cubierto", True),
    ("exterior_descubierto", True),
])
def test_solo_un_recinto_exterior_declarado_orienta_el_anillo_interior(situacion, es_exterior):
    from arquitectura.capas_envolvente import lados_del_modelo

    muros = anillo("fachada", (0, 0), (12, 12)) + anillo("patio", (4, 4), (8, 8))
    resultado = J.solve(muros)
    recinto = {"seed": (6, 6), "height": 3}
    if situacion is not None:
        recinto["enclosure"] = situacion
    lados = lados_del_modelo(resultado, [("recinto", recinto, None)])
    esperados = {"fachada" + str(indice): "derecha" for indice in range(4)}
    if es_exterior:
        esperados.update({"patio" + str(indice): "izquierda" for indice in range(4)})
    assert lados == esperados

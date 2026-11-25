# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: posición del aislamiento con tipos explícitos de material y colocación sin voltear tipos antiguos.
import pytest

from arquitectura import capas_envolvente as C
from arquitectura.geom.junctions import Wall


CATALOGO = {"materiales": {
    "A": {"clase_constructiva": "aislante"},
    "F": {"clase_constructiva": "fabrica"},
    "R": {"clase_constructiva": "revestimiento"},
    "T": {"clase_constructiva": "trasdosado"},
}}


@pytest.mark.parametrize("capas,posicion", [
    ([[0.05, "A"], [0.2, "F"]], "exterior"),
    ([[0.01, "R"], [0.05, "A"], [0.19, "F"]], "exterior"),
    ([[0.1, "F"], [0.05, "A"], [0.1, "F"]], "camara"),
    ([[0.2, "F"], [0.05, "A"]], "interior"),
    ([[0.19, "F"], [0.05, "A"], [0.01, "T"]], "interior"),
])
def test_posicion_por_clasificacion_sin_inferir_los_nombres(capas, posicion):
    aislamiento, avisos = C.aislamiento(capas, CATALOGO)
    assert not avisos
    assert aislamiento == {"posicion": posicion, "espesor": 0.05, "material": "A"}


@pytest.mark.parametrize("catalogo", [{}, {"materiales": {"Lana mineral": {"tipo": "PROPERTIES"}}}])
def test_un_nombre_reconocible_sin_clase_constructiva_no_se_adivina(catalogo):
    aislamiento, avisos = C.aislamiento([[0.2, "F"], [0.05, "Lana mineral"]], catalogo)
    assert aislamiento is None
    assert avisos and any("clasifica" in aviso for aviso in avisos)


def test_acabados_a_ambos_lados_sin_hoja_no_determinan_el_exterior():
    aislamiento, avisos = C.aislamiento([[0.01, "R"], [0.05, "A"], [0.01, "R"]], CATALOGO)
    assert aislamiento is None
    assert avisos


@pytest.mark.parametrize("referencia", ["eje", "izquierda", "derecha"])
@pytest.mark.parametrize("lado", ["izquierda", "derecha"])
def test_las_capas_se_colocan_desde_la_cara_exterior_fisica(referencia, lado):
    muro = Wall("m", (0, 0), (5, 0), 0.3, referencia)
    registro = {"id": "m", "layers": [[0.1, "R"], [0.2, "F"]],
                "orden_capas": "exterior-interior", "cara_exterior": lado}
    capas, avisos = C.colocar(registro, muro, {})
    assert not avisos
    assert [c["material"] for c in capas] == ["R", "F"]
    assert capas[0]["min"] == pytest.approx(muro.hi - 0.1 if lado == "izquierda" else muro.lo)
    assert capas[0]["max"] == pytest.approx(muro.hi if lado == "izquierda" else muro.lo + 0.1)
    assert min(c["min"] for c in capas) == pytest.approx(muro.lo)
    assert max(c["max"] for c in capas) == pytest.approx(muro.hi)


def test_tipo_antiguo_sin_orden_no_se_reinterpreta_ni_se_voltea():
    registro = {"id": "m", "type_name": "Anterior", "layers": [[0.3, "F"]], "wall_category": "fachada"}
    copia = dict(registro)
    capas, avisos = C.colocar(registro, Wall("m", (0, 0), (4, 0), 0.3), {"m": "derecha"})
    assert capas is None
    assert any("Anterior" in aviso and "orden" in aviso for aviso in avisos)
    assert registro == copia


def test_un_exterior_auto_indeterminado_avisa_y_no_coloca_capas():
    registro = {"id": "m", "layers": [[0.3, "F"]], "orden_capas": "exterior-interior"}
    capas, avisos = C.colocar(registro, Wall("m", (0, 0), (4, 0), 0.3), {"m": None})
    assert capas is None
    assert any("exterior" in aviso for aviso in avisos)

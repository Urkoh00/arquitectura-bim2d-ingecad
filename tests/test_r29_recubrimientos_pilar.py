# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: recubrimientos de pilar por capas, con aislamiento deducido del muro.
from copy import deepcopy
import importlib

import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401


def modulo(plugin, nombre):
    paquete = plugin.tools["MURO"].__module__.rsplit(".", 1)[0]
    return importlib.import_module(paquete + "." + nombre)


CATALOGO = {"materiales": {
    "Ladrillo cerámico": {"clase_constructiva": "fabrica"},
    "Ladrillo hueco": {"clase_constructiva": "fabrica"},
    "Ladrillo": {"clase_constructiva": "fabrica"},
    "Lana mineral": {"clase_constructiva": "aislante"},
    "Corcho": {"clase_constructiva": "aislante"},
    "Revoco": {"clase_constructiva": "revestimiento"},
}}


def pilar(**cambios):
    return {
        "id": "pilar", "kind": "column", "shape": "rect", "center": [0, 0],
        "width": 0.3, "depth": 0.3, "height": 3.0, "base": 0.0,
        "cover": 0.07, "level_id": "baja", **cambios,
    }


def muro(**cambios):
    return {
        "id": "muro", "kind": "wall", "a": [-3, 0], "b": [3, 0],
        "thickness": 0.3, "height": 3.0, "base": 0.0,
        "wall_category": "fachada", "level_id": "baja",
        "orden_capas": "exterior-interior", "cara_exterior": "derecha",
        "layers": [[0.1, "Ladrillo cerámico"], [0.05, "Lana mineral"], [0.15, "Ladrillo hueco"]],
        **cambios,
    }


def resolver(plugin, datos=None, muros=None):
    datos = pilar() if datos is None else datos
    muros = [muro()] if muros is None else muros
    return modulo(plugin, "recubrimientos_pilar").resolver(datos, [(m["id"], m) for m in muros], CATALOGO)


def test_aislamiento_en_camara_reutiliza_material_y_espesor_sin_mutar_entradas(plugin):
    original = pilar()
    pared = muro()
    copia = deepcopy((original, pared))
    resuelto, avisos = resolver(plugin, original, [pared])
    assert not avisos
    assert resuelto["insulation_resolved_thickness"] == pytest.approx(0.05)
    assert resuelto["insulation_resolved_material"] == "Lana mineral"
    assert modulo(plugin, "recubrimientos_pilar").espesor_total(resuelto) == pytest.approx(0.12)
    assert (original, pared) == copia


@pytest.mark.parametrize("capas", [
    [[0.05, "Lana mineral"], [0.25, "Ladrillo hueco"]],
    [[0.01, "Revoco"], [0.05, "Lana mineral"], [0.24, "Ladrillo hueco"]],
])
def test_el_aislamiento_exterior_no_se_repite_en_el_pilar(plugin, capas):
    datos, avisos = resolver(plugin, muros=[muro(layers=capas)])
    assert datos["insulation_resolved_thickness"] == 0
    assert not avisos


@pytest.mark.parametrize("cambios", [
    {"base": 4.0, "level_id": "alta"},
    {"a": [-3, 5], "b": [3, 5]},
    {"wall_category": "particion"},
])
def test_otro_nivel_un_muro_lejano_y_un_particion_no_activan_aislamiento(plugin, cambios):
    datos, avisos = resolver(plugin, muros=[muro(**cambios)])
    assert datos["insulation_resolved_thickness"] == 0
    assert not avisos


def test_sin_capas_avisa_en_lugar_de_inventar_aislamiento(plugin):
    datos, avisos = resolver(plugin, muros=[muro(layers=[])])
    assert datos["insulation_resolved_thickness"] == 0
    assert any("sin capas" in aviso.lower() for aviso in avisos)


def test_con_y_sin_aislamiento_son_decisiones_explicitas(plugin):
    datos, avisos = resolver(plugin, pilar(
        insulation_mode="con", insulation_thickness=0.04, insulation_material="Corcho"
    ), [])
    assert not avisos
    assert datos["insulation_resolved_thickness"] == pytest.approx(0.04)
    assert datos["insulation_resolved_material"] == "Corcho"
    datos, avisos = resolver(plugin, pilar(insulation_mode="sin"))
    assert datos["insulation_resolved_thickness"] == 0


def test_proveedores_incompatibles_no_se_resuelven_eligiendo_un_material_arbitrario(plugin):
    otro = muro(id="otro", a=[0, -3], b=[0, 3], layers=[
        [0.1, "Ladrillo"], [0.04, "Corcho"], [0.16, "Ladrillo hueco"]
    ])
    datos, avisos = resolver(plugin, muros=[muro(), otro])
    assert datos["insulation_resolved_thickness"] == 0
    assert any("distintos" in aviso.lower() for aviso in avisos)


def test_cero_recubrimiento_no_crea_aislamiento_y_cover_numerico_se_conserva(plugin):
    datos, avisos = resolver(plugin, pilar(cover=0))
    assert modulo(plugin, "recubrimientos_pilar").espesor_total(datos) == 0
    assert not avisos
    datos, _ = resolver(plugin, pilar(cover=0.035), [])
    assert datos["cover"] == pytest.approx(0.035)


@pytest.mark.parametrize("campo,valor", [
    ("cover", -1), ("cover", float("nan")), ("insulation_mode", "inventado"),
    ("insulation_thickness", -1), ("insulation_thickness", float("inf")),
])
def test_datos_invalidos_se_rechazan(plugin, campo, valor):
    with pytest.raises(ValueError):
        resolver(plugin, pilar(**{campo: valor}))


def test_el_nucleo_no_resuelve_materiales_sin_clasificacion(plugin):
    modulo_recubrimiento = modulo(plugin, "recubrimientos_pilar")
    datos, avisos = modulo_recubrimiento.resolver(pilar(), [("muro", muro())])
    assert datos["insulation_resolved_thickness"] == 0
    assert any("clasifica" in aviso for aviso in avisos)


def test_el_tipo_antiguo_y_la_cara_auto_indeterminada_no_se_adivinan(plugin):
    pared = muro()
    pared.pop("orden_capas")
    datos, avisos = resolver(plugin, muros=[pared])
    assert datos["insulation_resolved_thickness"] == 0
    assert any("orden" in aviso for aviso in avisos)
    datos, avisos = resolver(plugin, muros=[muro(cara_exterior="auto")])
    assert datos["insulation_resolved_thickness"] == 0
    assert any("cara exterior" in aviso for aviso in avisos)


def test_el_contacto_fisico_prevalece_sobre_el_nombre_de_la_planta(plugin):
    datos, avisos = resolver(plugin, muros=[muro(level_id="otra")])
    assert not avisos
    assert datos["insulation_resolved_thickness"] == pytest.approx(0.05)

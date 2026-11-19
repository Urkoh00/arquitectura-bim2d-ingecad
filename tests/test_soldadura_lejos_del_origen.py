# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: los sólidos siguen cerrados lejos del origen y con giro; la
#   soldadura de vértices no depende de fronteras de redondeo.
"""Edificio girado en coordenadas UTM (incidencia de R25-P3b).

Con el edificio girado 27° y desplazado a (700000, 4600000), el validador de
la extensión rechazaba un muro («sólido abierto o caras mal orientadas»):
el mismo vértice salía como 700006,93538245 y 700006,9353824501, que round(·,
7) separa, y un plano de dintel a ambos lados de otra frontera dejaba una
cara interna. Ahora el sólido se calcula en coordenadas locales, los planos
y los vértices se agrupan con tolerancia y el validador suelda igual.
"""
import importlib.util
import json
import math
from collections import Counter
from pathlib import Path

import pytest

from tests.test_c1_d2 import bridge
from tests.test_ingecad_integration import plugin  # noqa: F401  (fixture)

RAIZ = Path(__file__).parents[1]


def _soldadura():
    spec = importlib.util.spec_from_file_location(
        "soldadura_prueba", RAIZ / "arquitectura" / "geom" / "soldadura.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_dos_copias_a_ambos_lados_de_una_frontera_de_redondeo_son_un_vertice():
    S = _soldadura().Soldador()
    a = (700006.93538245, 4600003.679656271, 0.0)
    b = (700006.9353824501, 4600003.679656271, 0.0)
    assert tuple(round(v, 7) for v in a) != tuple(round(v, 7) for v in b)
    assert S.indice(a) == S.indice(b) and S.punto(b) is S.punto(a)
    assert S.indice((700006.9353827, 4600003.679656271, 0.0)) != S.indice(a)


def test_la_tolerancia_debe_ser_positiva():
    with pytest.raises(ValueError):
        _soldadura().Soldador(0.0)


def _cerrado(caras, Soldador):
    s = Soldador()
    aristas, sentidos = Counter(), Counter()
    for cara in caras:
        for lazo in [cara["outer"]] + list(cara.get("holes") or []):
            k = [s.indice(p) for p in lazo]
            for a, b in zip(k, k[1:] + k[:1]):
                clave = tuple(sorted((a, b)))
                aristas[clave] += 1
                sentidos[clave] += 1 if a < b else -1
    return all(n == 2 for n in aristas.values()) and not any(sentidos.values())


@pytest.mark.parametrize("angulo", [0, 27, 33, 61, 118])
def test_el_edificio_lejano_y_girado_es_estanco_y_pasa_el_validador(plugin, tmp_path, angulo):
    spec = importlib.util.spec_from_file_location(
        "generar_r25", RAIZ / "scripts" / "generar_modelo_r25.py")
    generador = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generador)
    generador.generar(tmp_path, float(angulo), True)
    datos = json.loads((tmp_path / "modelo_sintetico.arqbim").read_text(encoding="utf-8"))
    Soldador = _soldadura().Soldador
    for elemento in datos["elements"]:
        if elemento["ifc_class"] in ("IfcWall", "IfcSlab"):
            assert _cerrado(elemento["faces"], Soldador), elemento["name"]
            x = elemento["faces"][0]["outer"][0][0]
            assert x > 699990                       # siguen en coordenadas absolutas
    bridge().validate_contract(datos)


def test_lejos_y_cerca_el_mismo_muro_tiene_el_mismo_volumen(plugin, tmp_path):
    spec = importlib.util.spec_from_file_location(
        "generar_r25b", RAIZ / "scripts" / "generar_modelo_r25.py")
    generador = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generador)
    volumenes = []
    for lejano in (False, True):
        destino = tmp_path / str(lejano)
        generador.generar(destino, 27.0, lejano)
        datos = json.loads((destino / "modelo_sintetico.arqbim").read_text(encoding="utf-8"))
        volumenes.append(sorted(e["quantities"]["NetVolume"] for e in datos["elements"]
                                if e["ifc_class"] == "IfcWall"))
    assert volumenes[1] == pytest.approx(volumenes[0], abs=1e-6)
    assert all(math.isfinite(v) for v in volumenes[1])

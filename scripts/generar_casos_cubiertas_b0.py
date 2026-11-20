# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: escribe ocho referencias sintéticas de cubiertas; sus paños se fijan a mano, sin esqueleto recto.
from copy import deepcopy
import json
from pathlib import Path

from validar_cubierta_b0 import TOLERANCIA, huella_entrada

DESTINO = Path(__file__).resolve().parents[1] / "tests/datos/cubiertas_b0"


def area_firmada(puntos):
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(puntos, puntos[1:] + puntos[:1])) / 2


def anillo(puntos, antihorario=True):
    return puntos if (area_firmada(puntos) > 0) == antihorario else list(reversed(puntos))


def crear(
    nombre,
    exterior,
    pendientes,
    panos,
    volumen,
    *,
    patios=(),
    pendientes_patios=(),
    vuelo=0.0,
    arranques=None,
    contorno_resuelto=None,
    eventos=(),
    volumen_fraccion=None,
):
    anillos = [exterior, *patios]
    lados = []
    aros = []
    for indice_anillo, puntos in enumerate(anillos):
        ident = f"{nombre}-anillo-{indice_anillo}"
        vertices = [
            {"id": f"{ident}-v{indice}", "xy": list(punto)} for indice, punto in enumerate(puntos)
        ]
        aros.append({"id": ident, "vertices": vertices})
        valores = pendientes if indice_anillo == 0 else pendientes_patios[indice_anillo - 1]
        for indice, pendiente in enumerate(valores):
            lados.append(
                {
                    "id": f"{ident}-e{indice}",
                    "ring_id": ident,
                    "start_vertex_id": vertices[indice]["id"],
                    "end_vertex_id": vertices[(indice + 1) % len(vertices)]["id"],
                    "role": "gable" if pendiente is None else "eave",
                    "slope": pendiente,
                    "start_offset": arranques[indice] if arranques and indice_anillo == 0 else 0.0,
                    "overhang": vuelo,
                }
            )
    modelo = {
        "schema": "arq.cubierta/v1",
        "kind": "roof",
        "id": f"cubierta-{nombre}",
        "name": "Referencia " + nombre,
        "level_id": "nivel-referencia",
        "base_offset": 0.0,
        "origin_xy": [0.0, 0.0],
        "mode": "manual",
        "outer": aros[0],
        "holes": aros[1:],
        "edges": lados,
        "thickness": {"value": 0.2, "direction": "vertical"},
        "material": "Material sintético sin propiedades térmicas",
        "layers": [],
        "support_slab_id": "forjado-referencia" if vuelo else None,
        "solution": None,
    }
    faldones = []
    for indice, (poligono, gradiente, ordenada, referencias) in enumerate(panos):
        faldones.append(
            {
                "id": f"{nombre}-faldon-{indice}",
                "source_edge_ids": [f"{nombre}-anillo-{aro}-e{lado}" for aro, lado in referencias],
                "outer": anillo([list(punto) for punto in poligono]),
                "holes": [],
                "plane": {"point": [0.0, 0.0, ordenada], "gradient": list(gradiente)},
            }
        )
    modelo["solution"] = {
        "algorithm": {"name": "referencia-manual", "version": "1"},
        "input_fingerprint": huella_entrada(modelo),
        "outer": [list(punto) for punto in (contorno_resuelto or exterior)],
        "holes": [[list(punto) for punto in patio] for patio in patios],
        "facets": faldones,
    }
    return {
        "case_id": nombre,
        "model": modelo,
        "expected": {
            "decision": "accept",
            "volume_below_local_zero": volumen,
            "exact_volume_fraction": volumen_fraccion,
            "events": [list(evento) for evento in eventos],
        },
    }


def cuatro_aguas(x0, y0, x1, y1):
    distancia = (y1 - y0) / 2
    izquierda = x0 + distancia
    derecha = x1 - distancia
    medio = (y0 + y1) / 2
    exterior = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    panos = [
        (
            [exterior[0], exterior[1], (derecha, medio), (izquierda, medio)],
            (0, 0.5),
            -0.5 * y0,
            [(0, 0)],
        ),
        ([exterior[1], exterior[2], (derecha, medio)], (-0.5, 0), 0.5 * x1, [(0, 1)]),
        (
            [exterior[2], exterior[3], (izquierda, medio), (derecha, medio)],
            (0, -0.5),
            0.5 * y1,
            [(0, 2)],
        ),
        ([exterior[3], exterior[0], (izquierda, medio)], (0.5, 0), -0.5 * x0, [(0, 3)]),
    ]
    return exterior, panos


def dos_aguas(nombre, pendiente_derecha=0.5, arranque_derecha=0.0):
    ancho = 6.0
    largo = 8.0
    encuentro = (pendiente_derecha * ancho + arranque_derecha) / (0.5 + pendiente_derecha)
    altura = 0.5 * encuentro
    exterior = [(0, 0), (ancho, 0), (ancho, largo), (0, largo)]
    panos = [
        ([(0, 0), (encuentro, 0), (encuentro, largo), (0, largo)], (0.5, 0), 0, [(0, 3)]),
        (
            [(encuentro, 0), (ancho, 0), (ancho, largo), (encuentro, largo)],
            (-pendiente_derecha, 0),
            pendiente_derecha * ancho + arranque_derecha,
            [(0, 1)],
        ),
    ]
    volumen = largo * (encuentro * altura + (ancho - encuentro) * (altura + arranque_derecha)) / 2
    return crear(
        nombre,
        exterior,
        [None, pendiente_derecha, None, 0.5],
        panos,
        volumen,
        arranques=[0, arranque_derecha, 0, 0],
        eventos=[(encuentro, 0, altura), (encuentro, largo, altura)],
    )


def casos():
    exterior, panos = cuatro_aguas(0, 0, 8, 6)
    primero = crear(
        "01_rectangulo_igual", exterior, [0.5] * 4, panos, 27.0, eventos=[(3, 3, 1.5), (5, 3, 1.5)]
    )
    yield primero
    yield dos_aguas("02_pendientes_distintas", 1.0)
    exterior_l = [(0, 0), (6, 0), (6, 2), (2, 2), (2, 6), (0, 6)]
    panos_l = [
        ([(0, 0), (6, 0), (5, 1), (1, 1)], (0, 0.5), 0, [(0, 0)]),
        ([(6, 0), (6, 2), (5, 1)], (-0.5, 0), 3, [(0, 1)]),
        ([(6, 2), (2, 2), (1, 1), (5, 1)], (0, -0.5), 1, [(0, 2)]),
        ([(2, 2), (2, 6), (1, 5), (1, 1)], (-0.5, 0), 1, [(0, 3)]),
        ([(2, 6), (0, 6), (1, 5)], (0, -0.5), 3, [(0, 4)]),
        ([(0, 6), (0, 0), (1, 1), (1, 5)], (0.5, 0), 0, [(0, 5)]),
    ]
    yield crear(
        "03_planta_l",
        exterior_l,
        [0.5] * 6,
        panos_l,
        14 / 3,
        eventos=[(1, 1, 0.5), (5, 1, 0.5), (1, 5, 0.5)],
        volumen_fraccion=[14, 3],
    )
    exterior_p = [(0, 0), (10, 0), (10, 10), (0, 10)]
    patio = [(3, 3), (3, 7), (7, 7), (7, 3)]
    panos_p = [
        ([(0, 0), (10, 0), (8.5, 1.5), (1.5, 1.5)], (0, 0.5), 0, [(0, 0)]),
        ([(10, 0), (10, 10), (8.5, 8.5), (8.5, 1.5)], (-0.5, 0), 5, [(0, 1)]),
        ([(10, 10), (0, 10), (1.5, 8.5), (8.5, 8.5)], (0, -0.5), 5, [(0, 2)]),
        ([(0, 10), (0, 0), (1.5, 1.5), (1.5, 8.5)], (0.5, 0), 0, [(0, 3)]),
        ([(3, 3), (1.5, 1.5), (1.5, 8.5), (3, 7)], (-0.5, 0), 1.5, [(1, 0)]),
        ([(3, 7), (1.5, 8.5), (8.5, 8.5), (7, 7)], (0, 0.5), -3.5, [(1, 1)]),
        ([(7, 7), (8.5, 8.5), (8.5, 1.5), (7, 3)], (0.5, 0), -3.5, [(1, 2)]),
        ([(7, 3), (8.5, 1.5), (1.5, 1.5), (3, 3)], (0, -0.5), 1.5, [(1, 3)]),
    ]
    yield crear(
        "04_patio",
        exterior_p,
        [0.5] * 4,
        panos_p,
        31.5,
        patios=[patio],
        pendientes_patios=[[0.5] * 4],
        eventos=[(1.5, 1.5, 0.75), (8.5, 8.5, 0.75)],
    )
    ampliado, panos_v = cuatro_aguas(-0.5, -0.5, 8.5, 6.5)
    yield crear(
        "05_vuelo",
        exterior,
        [0.5] * 4,
        panos_v,
        245 / 6,
        vuelo=0.5,
        contorno_resuelto=ampliado,
        eventos=[(3, 3, 1.75), (5, 3, 1.75)],
        volumen_fraccion=[245, 6],
    )
    sexto = dos_aguas("06_arranques_distintos", 0.5, 1.0)
    sexto["expected"]["automatic_decision"] = "reject"
    yield sexto
    septimo = dos_aguas("07_pinones")
    septimo["expected"]["gable_triangle_areas"] = [4.5, 4.5]
    yield septimo
    octavo = deepcopy(primero)
    octavo["case_id"] = "08_casi_degenerado"
    octavo["expected"] = {
        "decision": "reject",
        "valid_variant_delta": 2 * TOLERANCIA,
        "rejected_variant_delta": TOLERANCIA / 2,
        "reason": "tolerancia",
    }
    modelo = octavo["model"]
    vertices = modelo["outer"]["vertices"]
    nuevo_id = modelo["outer"]["id"] + "-v4"
    vertices.append({"id": nuevo_id, "xy": [0, 6 - TOLERANCIA / 2]})
    ultimo = modelo["edges"][-1]
    ultimo["end_vertex_id"] = nuevo_id
    adicional = {
        **ultimo,
        "id": modelo["outer"]["id"] + "-e4",
        "start_vertex_id": nuevo_id,
        "end_vertex_id": vertices[0]["id"],
    }
    modelo["edges"].append(adicional)
    modelo["solution"]["facets"][-1]["source_edge_ids"].append(adicional["id"])
    modelo["solution"]["input_fingerprint"] = huella_entrada(modelo)
    yield octavo


def main():
    DESTINO.mkdir(parents=True, exist_ok=True)
    for caso in casos():
        (DESTINO / (caso["case_id"] + ".json")).write_text(
            json.dumps(caso, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        )


if __name__ == "__main__":
    main()

# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: fija ocho referencias analíticas y rechazos geométricos antes de implementar las cubiertas.
from copy import deepcopy
from fractions import Fraction
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys

import pytest

RAIZ = Path(__file__).resolve().parents[1]
RUTAS = sorted((RAIZ / "tests/datos/cubiertas_b0").glob("*.json"))
especificacion = importlib.util.spec_from_file_location(
    "validar_cubiertas_b0", RAIZ / "scripts/validar_cubierta_b0.py"
)
comprobador = importlib.util.module_from_spec(especificacion)
especificacion.loader.exec_module(comprobador)
TOLERANCIA = comprobador.TOLERANCIA


def cargar(numero):
    return json.loads(RUTAS[numero - 1].read_text())


def refrescar(modelo):
    modelo["solution"]["input_fingerprint"] = comprobador.huella_entrada(modelo)


def integrar(coeficientes, altura):
    return sum(
        coeficiente * altura ** (indice + 1) / (indice + 1)
        for indice, coeficiente in enumerate(map(Fraction, coeficientes))
    )


VOLUMENES = [
    integrar([48, -56, 16], Fraction(3, 2)),
    Fraction(6 * 2 * 8, 2),
    integrar([20, -48, 16], Fraction(1, 2)),
    integrar([84, -112], Fraction(3, 4)),
    integrar([63, -64, 16], Fraction(7, 4)),
    Fraction(8) * (Fraction(4 * 2, 2) + Fraction(2 * (2 + 1), 2)),
    Fraction(6 * 3 * 8, 4),
]


@pytest.mark.parametrize("numero,area", list(enumerate([48, 48, 20, 84, 63, 48, 48], start=1)))
def test_oraculos_tienen_cobertura_cotas_y_volumen_analitico(numero, area):
    caso = cargar(numero)
    antes = deepcopy(caso)
    resultado = comprobador.validar(caso["model"])
    assert resultado["area_planta"] == pytest.approx(area, abs=TOLERANCIA)
    esperado = float(VOLUMENES[numero - 1])
    assert resultado["volumen_bajo_cota_cero_local"] == pytest.approx(esperado, abs=TOLERANCIA)
    assert caso["expected"]["volume_below_local_zero"] == pytest.approx(esperado, abs=TOLERANCIA)
    assert resultado["volumen_material_vertical"] == pytest.approx(area * 0.2, abs=TOLERANCIA)
    if numero != 2:
        assert resultado["area_faldones"] == pytest.approx(area * math.sqrt(1.25), abs=TOLERANCIA)
    else:
        assert resultado["area_faldones"] == pytest.approx(
            32 * math.sqrt(1.25) + 16 * math.sqrt(2), abs=TOLERANCIA
        )
    assert caso == antes


def test_posicion_de_encuentro_usa_velocidad_inversa_de_pendiente():
    caso = cargar(2)
    izquierda = Fraction(1, 2)
    derecha = Fraction(1)
    tiempo = Fraction(6) / (1 / izquierda + 1 / derecha)
    posicion = tiempo / izquierda
    assert (posicion, tiempo) == (4, 2)
    assert caso["expected"]["events"] == [[4.0, 0, 2.0], [4.0, 8.0, 2.0]]
    # Estas dos cotas hacen fallar la confusión v=p, que desplazaría la cumbrera a x=2.
    for faldon in caso["model"]["solution"]["facets"]:
        assert comprobador.cota(faldon["plane"], (float(posicion), 4.0)) == pytest.approx(2.0)


def test_patio_no_tiene_faldon_que_lo_tape():
    from shapely.geometry import Polygon

    modelo = cargar(4)["model"]
    patio = Polygon([v["xy"] for v in modelo["holes"][0]["vertices"]])
    assert patio.area == 16.0
    assert len(modelo["solution"]["holes"]) == 1
    for faldon in modelo["solution"]["facets"]:
        assert Polygon(faldon["outer"], faldon["holes"]).intersection(patio).area <= TOLERANCIA**2


def test_vuelo_amplia_la_cubierta_sin_cambiar_el_soporte():
    modelo = cargar(5)["model"]
    antes = deepcopy(modelo)
    resultado = comprobador.validar(modelo)
    assert resultado["area_soporte"] == 48.0
    assert resultado["area_planta"] == 63.0
    assert resultado["volumen_bajo_cota_cero_local"] - 27 == pytest.approx(float(Fraction(83, 6)))
    assert modelo["support_slab_id"] == "forjado-referencia"
    assert modelo == antes


def test_arranques_distintos_tienen_referencia_manual_y_rechazo_automatico():
    modelo = cargar(6)["model"]
    assert comprobador.validar(modelo)["volumen_bajo_cota_cero_local"] == pytest.approx(56.0)
    modelo["mode"] = "automatic"
    refrescar(modelo)
    antes = deepcopy(modelo)
    with pytest.raises(ValueError, match="arranques a distinta cota"):
        comprobador.validar(modelo)
    assert modelo == antes


def test_pinones_no_generan_faldon_y_definen_dos_triangulos_de_cierre():
    modelo = cargar(7)["model"]
    pinones = {lado["id"] for lado in modelo["edges"] if lado["role"] == "gable"}
    assert len(pinones) == 2
    referencias = {
        identificador
        for faldon in modelo["solution"]["facets"]
        for identificador in faldon["source_edge_ids"]
    }
    assert not pinones & referencias
    for final in (0.0, 8.0):
        altura = max(
            comprobador.cota(f["plane"], (3.0, final)) for f in modelo["solution"]["facets"]
        )
        assert 6.0 * altura / 2 == pytest.approx(4.5)
    assert cargar(7)["expected"]["gable_triangle_areas"] == [4.5, 4.5]


def test_casi_degenerado_se_rechaza_y_la_variante_sobre_tolerancia_es_valida():
    caso = cargar(8)
    modelo = caso["model"]
    antes = deepcopy(modelo)
    with pytest.raises(ValueError, match="tolerancia"):
        comprobador.validar(modelo)
    assert modelo == antes
    modelo["outer"]["vertices"][-1]["xy"][1] = 6 - caso["expected"]["valid_variant_delta"]
    refrescar(modelo)
    assert comprobador.validar(modelo)["volumen_bajo_cota_cero_local"] == pytest.approx(27.0)


@pytest.mark.parametrize("numero", range(1, 8))
def test_coordenadas_topograficas_y_nivel_no_alteran_las_medidas_ni_ids(numero):
    modelo = cargar(numero)["model"]
    antes = comprobador.validar(modelo)
    identificadores = [f["id"] for f in modelo["solution"]["facets"]]
    modelo["origin_xy"] = [700000.0, 4600000.0]
    modelo["base_offset"] = 0.35
    modelo["level_id"] = "planta-primera"
    refrescar(modelo)
    assert comprobador.validar(modelo) == antes
    assert [f["id"] for f in modelo["solution"]["facets"]] == identificadores


@pytest.mark.parametrize(
    "cambio,mensaje",
    [
        (lambda m: m.update(schema="arq.cubierta/v99"), "Esquema"),
        (lambda m: m.pop("schema"), "Esquema"),
        (lambda m: m.update(base_offset=math.nan), "finitas"),
        (lambda m: m["edges"][0].update(slope=math.inf), "finitas"),
        (lambda m: m["thickness"].update(value=0), "Esquema"),
        (lambda m: m["edges"][0].update(overhang=-1), "Esquema"),
        (lambda m: m["edges"][0].update(slope=0), "positiva"),
        (lambda m: m["edges"][0].update(id=m["id"]), "repetido"),
        (lambda m: m["edges"][0].update(end_vertex_id="inexistente"), "exactamente un lado"),
        (
            lambda m: m["solution"]["facets"][0]["source_edge_ids"].append("inexistente"),
            "inexistente",
        ),
        (lambda m: m["solution"]["facets"][0]["plane"].update(gradient=[0, 0.4]), "pendiente"),
        (lambda m: m["solution"]["facets"][0]["plane"]["point"].__setitem__(2, 0.1), "arranque"),
        (lambda m: m["solution"]["facets"].pop(), "sin paño"),
    ],
)
def test_rechazos_preservan_la_entrada_y_dan_un_motivo(cambio, mensaje):
    modelo = cargar(1)["model"]
    cambio(modelo)
    if (
        modelo.get("solution")
        and math.isfinite(modelo.get("base_offset", 0))
        and all(math.isfinite(lado["slope"] or 0) for lado in modelo["edges"])
    ):
        refrescar(modelo)
    antes = deepcopy(modelo)
    with pytest.raises(ValueError, match=mensaje):
        comprobador.validar(modelo)
    # NaN no es igual a sí mismo: comparar su representación conserva también ese caso.
    assert json.dumps(modelo, sort_keys=True) == json.dumps(antes, sort_keys=True)


def test_cambiar_la_entrada_invalida_la_solucion_sin_rehacerla_en_silencio():
    modelo = cargar(1)["model"]
    modelo["edges"][0]["slope"] = 0.75
    antes = deepcopy(modelo)
    with pytest.raises(ValueError, match="desactualizada"):
        comprobador.validar(modelo)
    assert modelo == antes


def test_capas_deben_sumar_el_espesor_y_un_pinon_no_puede_tener_pano():
    modelo = cargar(7)["model"]
    modelo["layers"] = [{"id": "estrato", "material": "Material sintético", "thickness": 0.1}]
    refrescar(modelo)
    with pytest.raises(ValueError, match="no suman"):
        comprobador.validar(modelo)
    modelo["layers"][0]["thickness"] = 0.2
    modelo["solution"]["facets"][0]["source_edge_ids"].append(modelo["edges"][0]["id"])
    refrescar(modelo)
    with pytest.raises(ValueError, match="piñón"):
        comprobador.validar(modelo)


def test_espesor_normal_no_se_cuantifica_como_espesor_vertical():
    modelo = cargar(1)["model"]
    modelo["thickness"]["direction"] = "normal"
    refrescar(modelo)
    medidas = comprobador.validar(modelo)
    assert "volumen_material_vertical" not in medidas
    assert medidas["area_faldones"] > medidas["area_planta"]


def test_herramienta_de_diseno_no_importa_los_anfitriones(tmp_path):
    destino = tmp_path / "modulos.json"
    codigo = (
        "import importlib.util,json,sys; "
        f"sys.path.insert(0,{str(Path(comprobador.__file__).parent)!r}); "
        "import validar_cubierta_b0; "
        f"open({str(destino)!r},'w').write(json.dumps(sorted(sys.modules)))"
    )
    proceso = subprocess.run(
        [sys.executable, "-c", codigo], capture_output=True, text=True, timeout=20
    )
    assert proceso.returncode == 0, proceso.stderr
    modulos = json.loads(destino.read_text())
    assert not any(
        nombre == "core" or nombre.startswith(("core.", "PySide6", "ingetrazo"))
        for nombre in modulos
    )


def test_los_ocho_casos_son_reproducibles_y_la_herramienta_los_comprueba(monkeypatch, capsys):
    assert len(RUTAS) == 8
    monkeypatch.syspath_prepend(str(RAIZ / "scripts"))
    import generar_casos_cubiertas_b0

    assert list(generar_casos_cubiertas_b0.casos()) == [cargar(numero) for numero in range(1, 9)]
    comprobador.main([str(ruta) for ruta in RUTAS])
    resultados = json.loads(capsys.readouterr().out)
    assert len(resultados) == 8
    assert "rechazado" in resultados[-1]


def test_la_herramienta_rechaza_una_referencia_numerica_erronea(tmp_path):
    caso = cargar(1)
    caso["expected"]["volume_below_local_zero"] = 999
    ruta = tmp_path / "referencia_incorrecta.json"
    ruta.write_text(json.dumps(caso))
    with pytest.raises(ValueError, match="referencia analítica"):
        comprobador.main([str(ruta)])


def test_no_se_aceptan_patios_fuera_del_dominio():
    modelo = cargar(4)["model"]
    for vertice in modelo["holes"][0]["vertices"]:
        vertice["xy"][0] += 20
    refrescar(modelo)
    with pytest.raises(ValueError, match="patio fuera"):
        comprobador.validar(modelo)


def test_no_se_acepta_un_anillo_cruzado():
    modelo = cargar(1)["model"]
    vertices = modelo["outer"]["vertices"]
    vertices[1]["xy"], vertices[2]["xy"] = vertices[2]["xy"], vertices[1]["xy"]
    refrescar(modelo)
    with pytest.raises(ValueError, match="cruzado"):
        comprobador.validar(modelo)


def test_una_cubierta_plana_no_lleva_pesos_de_pendiente_cero_al_automatico():
    modelo = cargar(1)["model"]
    modelo["mode"] = "flat"
    for lado in modelo["edges"]:
        lado["slope"] = 0
    modelo["solution"] = None
    assert comprobador.validar(modelo)["estado"] == "sin resolver"
    modelo["mode"] = "automatic"
    with pytest.raises(ValueError, match="positiva"):
        comprobador.validar(modelo)

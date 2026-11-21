# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: las unidades de presentación no alteran entradas, geometría ni cantidades BIM.
from copy import deepcopy
import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_fichas_tipos_usos import qapp  # noqa: F401
from tests.test_wall_tools import Session
from tests.test_r27_creacion_texto import responder
from tests.test_r28_marcas_dibujo import modelo
from tests.test_r28a_plano import generar
from tests.escenarios_r27 import modulo


def configurar(sesion, precision):
    herramienta = sesion.tool("-PARAMETROSARQ")
    responder(herramienta, {"general.precision_medidas": precision})


def test_por_defecto_centimetros_y_cinco_centimetros_de_cota_minima(plugin):
    parametros = modulo(plugin, "parameters_arq")
    valores = parametros.general_options(Session(plugin).document)
    assert valores["cota_minima"] == 0.05
    assert valores["precision_medidas"] == "cm"


@pytest.mark.parametrize("precision,texto", [("Centímetros", "2,35"), ("Milímetros", "2,347")])
def test_la_cota_temporal_presenta_la_precision_sin_redondear_la_entrada_ni_el_contrato(
    plugin, precision, texto
):
    sesion = Session(plugin)
    configurar(sesion, precision)
    muro = sesion.tool("MURO")
    muro.on_point((0.0, 0.0))
    textos = [e.dxf.text for e in muro.preview_entities((2.347, 0.0)) if e.dxftype() == "TEXT"]
    assert texto in textos
    entrada = modulo(plugin, "temp_dims").parse_length("2,347")
    assert entrada == pytest.approx(2.347)
    muro.on_point((entrada, 0.0))
    muro.on_enter()
    registro = sesion.meta(next(iter(sesion.walls().values())))
    assert registro["b"][0] == pytest.approx(2.347)
    contrato = modulo(plugin, "exchange").build(sesion.document.doc)
    exportado = next(e for e in contrato["elements"] if e["ifc_class"] == "IfcWall")
    assert exportado["params"]["b"][0] == pytest.approx(2.347)
    assert exportado["quantities"]["Length"] == pytest.approx(2.347)


@pytest.mark.parametrize("precision,decimales", [("Centímetros", 2), ("Milímetros", 3)])
def test_memoria_usa_dimdec_y_texto_de_medidas_pero_areas_siempre_con_dos_decimales(
    plugin, precision, decimales
):
    sesion, _, _ = modelo(plugin)
    configurar(sesion, precision)
    generar(sesion, plugin)
    cotas = list(sesion.document.doc.modelspace().query("DIMENSION"))
    assert cotas and all(c.override().get("dimdec") == decimales for c in cotas)
    textos = [e.plain_text() for e in sesion.document.doc.modelspace().query("MTEXT")]
    assert any(("0,89 × 2,10" if decimales == 2 else "0,885 × 2,100") in t for t in textos)
    assert any("Hueco: 1,86 m²" in t for t in textos)


def test_los_campos_generales_son_iguales_en_ficha_y_texto_y_persisten(
    plugin, qapp, monkeypatch, tmp_path
):
    from PySide6.QtWidgets import QDialog
    from core.document import Document

    sesion = Session(plugin)
    parametros = modulo(plugin, "parameters_arq")
    antes = parametros.load_defaults(sesion.document)

    def aceptar(ficha):
        ficha._arq[("general", "precision_medidas")].setCurrentIndex(1)
        ficha._arq[("general", "cota_minima")].setValue(0.07)
        return QDialog.Accepted

    monkeypatch.setattr(QDialog, "exec", aceptar)
    ficha = modulo(plugin, "bim_dialogs").architectural_defaults_dialog(None, deepcopy(antes))
    herramienta = sesion.tool("-PARAMETROSARQ")
    responder(
        herramienta, {"general.precision_medidas": "Milímetros", "general.cota_minima": "0,07"}
    )
    assert parametros.load_defaults(sesion.document) == ficha
    ruta = tmp_path / "precision.dxf"
    sesion.document.save_as(ruta)
    assert parametros.load_defaults(Document.load(ruta)) == ficha
    sesion.history.undo()
    assert parametros.load_defaults(sesion.document) == antes


def test_cambiar_precision_invalida_la_presentacion_guardada_sin_modificar_fuentes(plugin):
    sesion, _, _ = modelo(plugin)
    plano = generar(sesion, plugin)
    fuentes = [
        deepcopy(sesion.meta(e))
        for e in sesion.document.doc.modelspace()
        if (sesion.meta(e) or {}).get("kind") in ("wall", "opening")
    ]
    configurar(sesion, "Milímetros")
    assert plano.avisos(sesion.document.doc)
    assert [
        sesion.meta(e)
        for e in sesion.document.doc.modelspace()
        if (sesion.meta(e) or {}).get("kind") in ("wall", "opening")
    ] == fuentes


@pytest.mark.parametrize(
    "precision,decimales,texto", [("Centímetros", 2, "2,35"), ("Milímetros", 3, "2,347")]
)
def test_cotamuros_anula_precision_y_conserva_medida_y_suma_tras_omitir_tramos(
    plugin, precision, decimales, texto
):
    import math

    sesion = Session(plugin)
    configurar(sesion, precision)
    cotas = modulo(plugin, "cotas")
    puntos = [(0.0, 0.0), (0.02, 0.0), (1.0, 0.0), (1.03, 0.0), (2.347, 0.0)]
    filtrados = cotas.thin_out(puntos, 0.05)
    assert all(math.dist(a, b) >= 0.05 for a, b in zip(filtrados, filtrados[1:]))
    assert sum(math.dist(a, b) for a, b in zip(filtrados, filtrados[1:])) == pytest.approx(2.347)
    sesion.history.execute(cotas._StyleCommand(0.20))
    for comando in cotas.dimension_commands(
        cotas.chain(filtrados, puntos[0], puntos[-1], total_offset=1.0), sesion.document
    ):
        sesion.history.execute(comando)
    dimensiones = list(sesion.document.doc.modelspace().query("DIMENSION"))
    assert all(d.override().get("dimdec") == decimales for d in dimensiones)
    total = dimensiones[-1]
    assert total.get_measurement() == pytest.approx(2.347)
    textos = [
        e.plain_text()
        for e in sesion.document.doc.blocks[total.dxf.geometry]
        if e.dxftype() in ("TEXT", "MTEXT")
    ]
    assert texto in textos


def test_las_notas_de_superficies_respetan_la_precision_sin_cambiar_las_areas(plugin):
    sesion = Session(plugin)
    superficies = modulo(plugin, "superficies")
    recinto = {"area": 3.1415926}
    antes = superficies.evaluate({"height": 1.0}, recinto, documento=sesion.document)
    configurar(sesion, "Milímetros")
    despues = superficies.evaluate({"height": 1.0}, recinto, documento=sesion.document)
    assert "1,50 m" in antes["notes"][0]
    assert "1,500 m" in despues["notes"][0]
    assert antes["useful"] == despues["useful"] == recinto["area"]


def test_las_cotas_temporales_de_crear_y_mover_carpinteria_usan_milimetros(plugin):
    sesion, _, _ = modelo(plugin)
    configurar(sesion, "Milímetros")
    crear = sesion.tool("CARPINTERIA")
    textos = [e.dxf.text for e in crear.preview_entities((2.0, 0.15)) if e.dxftype() == "TEXT"]
    assert "0,885" in textos
    mover = sesion.tool("MOVERCARP")
    mover.on_point((1.03, 0.6))
    assert mover.entity is not None
    textos = [e.dxf.text for e in mover.preview_entities((2.0, 0.15)) if e.dxftype() == "TEXT"]
    assert "0,885" in textos

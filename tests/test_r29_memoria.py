# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: reproduce las incidencias de la primera prueba del plano de carpintería.
import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_r28_marcas_dibujo import modelo
from tests.test_r28a_plano import generar
from tests.escenarios_r27 import modulo
from tests.escenario_r28 import modelo_carpinterias


@pytest.mark.parametrize("escala", [20, 25, 50])
def test_la_escala_de_cada_cota_es_la_de_la_ficha_sin_cambiar_el_estilo(plugin, escala):
    sesion, _, _ = modelo(plugin)
    dibujo = sesion.document.doc
    estilo = dibujo.dimstyles.new(
        "Escala cien",
        dxfattribs={"dimscale": 100.0, "dimtxt": 2.5, "dimasz": 1.8, "dimclrd": 3},
    )
    dibujo.header["$DIMSTYLE"] = estilo.dxf.name
    original = estilo.dxf.all_existing_dxf_attribs()
    generar(sesion, plugin, {"escala": "1:" + str(escala)})
    cotas = list(dibujo.modelspace().query("DIMENSION"))
    assert cotas
    for cota in cotas:
        anulacion = cota.override()
        assert anulacion.get("dimscale") == escala
        assert anulacion.get("dimtxt") * escala == pytest.approx(0.0025 * escala)
        assert anulacion.get("dimclrd") == 3
        bloque = dibujo.blocks[cota.dxf.geometry]
        textos = [entidad for entidad in bloque if entidad.dxftype() in ("TEXT", "MTEXT")]
        assert textos
        for texto in textos:
            altura = texto.dxf.height if texto.dxftype() == "TEXT" else texto.dxf.char_height
            assert altura == pytest.approx(0.0025 * escala)
    assert estilo.dxf.all_existing_dxf_attribs() == original


@pytest.mark.parametrize("mano,lado", [(0, 1), (1, 1), (0, -1), (1, -1)])
def test_la_leyenda_de_seccion_queda_debajo_de_todos_sus_trazos(plugin, mano, lado):
    from ezdxf import bbox

    sesion, _, arquitectura = modelo(plugin)
    for entidad in list(sesion.document.doc.modelspace()):
        if (sesion.meta(entidad) or {}).get("kind") == "opening":
            sesion.history.execute(arquitectura.edit_opening(entidad, hinge=mano, side=lado))
    generar(sesion, plugin)
    leyendas = []
    trazos = []
    for entidad in sesion.document.doc.modelspace():
        papel = (sesion.meta(entidad) or {}).get("role")
        if papel == "section_caption":
            leyendas.append(entidad)
        elif papel == "section":
            trazos.append(entidad)
    assert len(leyendas) == 1 and trazos
    assert bbox.extents(leyendas).extmax.y < bbox.extents(trazos).extmin.y


def test_las_cotas_distinguen_el_hueco_de_la_hoja_sin_alterar_la_medida(plugin):
    sesion, _, _ = modelo(plugin)
    generar(sesion, plugin)
    cotas = list(sesion.document.doc.modelspace().query("DIMENSION"))
    anchos = [c for c in cotas if sesion.meta(c)["dimension_kind"] in ("ancho", "hoja")]
    assert {sesion.meta(c)["dimension_kind"] for c in anchos} == {"ancho", "hoja"}
    for cota in anchos:
        tipo = sesion.meta(cota)["dimension_kind"]
        assert ("hueco" if tipo == "ancho" else "hoja") in cota.dxf.text.casefold()
        assert "<>" in cota.dxf.text
        assert cota.get_measurement() > 0


def test_la_tarjeta_sin_contenido_extra_no_reserva_un_bloque_vacio(plugin):
    from ezdxf import bbox

    sesion, _, _ = modelo(plugin)
    generar(sesion, plugin, {"modo": "Fichas"})
    derivados = [
        e for e in sesion.document.doc.modelspace() if (sesion.meta(e) or {}).get("schedule_id")
    ]
    marco = next(e for e in derivados if sesion.meta(e)["role"] == "frame_card")
    contenido = [e for e in derivados if e is not marco]
    margen = bbox.extents(contenido).extmin.y - bbox.extents([marco]).extmin.y
    assert margen == pytest.approx(2 * 0.0025 * 50)


def test_los_marcos_de_cada_fila_comparten_altura_ajustada_al_contenido(plugin):
    from ezdxf import bbox

    sesion = modelo_carpinterias(plugin)
    generar(sesion, plugin, {"modo": "Fichas"})
    marcos = [
        e
        for e in sesion.document.doc.modelspace()
        if (sesion.meta(e) or {}).get("role") == "frame_card"
    ]
    filas = {}
    for marco in marcos:
        limites = bbox.extents([marco])
        filas.setdefault(limites.extmax.y, []).append(limites)
    assert len(filas) == 3
    for cajas in filas.values():
        assert all(caja.extmin.y == pytest.approx(cajas[0].extmin.y) for caja in cajas)


def test_huecos_y_fijas_indican_no_procede_y_localizan_sin_repetir_la_planta(plugin, monkeypatch):
    from core import tables

    sesion = modelo_carpinterias(plugin)
    datos_tabla = []
    insertar = tables.insert_table

    def guardar_tabla(*args, **kwargs):
        datos_tabla.extend(kwargs["data"])
        return insertar(*args, **kwargs)

    monkeypatch.setattr(tables, "insert_table", guardar_tabla)
    generar(sesion, plugin)
    hueco = next(fila for fila in datos_tabla if fila[0].startswith("H"))
    fija = next(fila for fila in datos_tabla if fila[5] == "fija")
    assert hueco[4] == "—" and hueco[6] == fija[6] == "—"
    textos = [e.plain_text() for e in sesion.document.doc.modelspace().query("MTEXT")]
    assert any("Exterior · —" in texto for texto in textos)
    assert not any("sin mano" in texto for texto in textos)
    assert not any("— Planta" in fila[-1] for fila in datos_tabla)
    puerta = next(fila for fila in datos_tabla if fila[1] == "4" and fila[2] == "Puerta")
    assert "Planta baja / Salón" in puerta[-1]
    assert "Planta primera / Salón" in puerta[-1]

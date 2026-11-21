# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: verifica el plano real, sus marcas, rótulos, actualización y transacción completa.
from copy import deepcopy
import importlib

import pytest
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_fichas_tipos_usos import qapp  # noqa: F401
from tests.test_r27_creacion_texto import responder
from tests.test_r28_marcas_dibujo import modelo, registros
from tests.escenario_r28 import modelo_carpinterias
from tests.escenarios_r27 import modulo
from tests.verificacion_r27 import estado


def generar(sesion, plugin, valores=None):
    herramienta = sesion.tool("-MEMORIACARP")
    responder(herramienta, valores)
    herramienta.on_point((30.0, 30.0))
    return modulo(plugin, "memoria_plano")


def test_plano_real_crea_fichas_cotas_tabla_rotulos_y_un_solo_deshacer(plugin):
    sesion, _, _ = modelo(plugin)
    antes = estado(plugin, sesion.document)
    profundidad = sesion.history.depth
    plano = generar(sesion, plugin)
    assert sesion.history.depth == profundidad + 1, sesion.out
    existentes = plano.planos(sesion.document.doc)
    assert len(existentes) == 1, sesion.out
    _, datos = existentes[0]
    assert datos["rows"][0]["marca"] == "P1" and datos["rows"][0]["unidades"] == 2
    derivados = [
        e
        for e in sesion.document.doc.modelspace()
        if (sesion.meta(e) or {}).get("schedule_id") == datos["id"]
    ]
    assert len(derivados) == datos["detail_count"]
    assert any(e.dxftype() == "DIMENSION" for e in derivados)
    assert any(sesion.meta(e)["role"] == "table" for e in derivados)
    assert len([r for r in registros(sesion) if r["kind"] == "opening_mark"]) == 2
    assert all(sesion.document.doc.layers.get(e.dxf.layer).is_locked() for e in derivados)
    assert not plano.avisos(sesion.document.doc)
    despues = estado(plugin, sesion.document)
    sesion.history.undo()
    assert estado(plugin, sesion.document) == antes
    sesion.history.redo()
    assert estado(plugin, sesion.document) == despues


def test_actualizar_conserva_posicion_id_y_reemplaza_sin_duplicados(plugin):
    sesion, _, arquitectura = modelo(plugin)
    plano = generar(sesion, plugin)
    entidad, datos = plano.planos(sesion.document.doc)[0]
    identidad = datos["id"]
    puerta = next(
        e
        for e in sesion.document.doc.modelspace()
        if (sesion.meta(e) or {}).get("kind") == "opening"
    )
    cambio = arquitectura.edit_opening(puerta, width=1.085)
    modulo(plugin, "transactions").apply_architectural_change(
        sesion.tool("MURO").ctx, cambio, kind="opening"
    )
    assert plano.avisos(sesion.document.doc)
    assert sesion.meta(puerta)["mark"] == "P2"
    antes = estado(plugin, sesion.document)
    profundidad = sesion.history.depth
    herramienta = sesion.tool("-MEMORIACARP")
    herramienta.on_option("Actualizar")
    assert herramienta._campos_texto is None
    assert sesion.history.depth == profundidad + 1
    _, nuevos = plano.planos(sesion.document.doc)[0]
    assert nuevos["id"] == identidad and nuevos["insert"] == datos["insert"]
    assert len(nuevos["rows"]) == 2
    assert not plano.avisos(sesion.document.doc)
    assert (
        len(
            [
                e
                for e in sesion.document.doc.modelspace()
                if (sesion.meta(e) or {}).get("schedule_id") == identidad
            ]
        )
        == nuevos["detail_count"]
    )
    despues = estado(plugin, sesion.document)
    sesion.history.undo()
    assert estado(plugin, sesion.document) == antes
    sesion.history.redo()
    assert estado(plugin, sesion.document) == despues


@pytest.mark.parametrize("modo", ["tabla", "fichas", "todo"])
def test_contenido_y_guardado_dxf_desde_el_modelo_de_dos_plantas(plugin, tmp_path, modo):
    from core.document import Document
    from ingetrazo_ext.arquitectura_bim import validate_contract

    sesion = modelo_carpinterias(plugin)
    plano = generar(sesion, plugin, {"modo": modo, "huecos": "No", "agrupar": "Planta"})
    _, datos = plano.planos(sesion.document.doc)[0]
    assert len({planta for fila in datos["rows"] for planta in fila["plantas"]}) == 2
    assert not any(fila["marca"].startswith("H") for fila in datos["rows"])
    papeles = {r.get("role") for r in registros(sesion) if r["kind"] == "carpentry_schedule_detail"}
    assert ("table" in papeles) == (modo != "fichas")
    assert ("dimension" in papeles) == (modo != "tabla")
    ruta = tmp_path / "memoria.dxf"
    sesion.document.save_as(ruta)
    recuperado = Document.load(ruta)
    assert plano.planos(recuperado.doc)[0][1] == datos
    assert not plano.avisos(recuperado.doc)
    validate_contract(modulo(plugin, "exchange").build(recuperado.doc))


def test_paridad_ficha_y_texto_incluye_todas_las_opciones(plugin, qapp):
    sesion, _, _ = modelo(plugin)
    herramienta = sesion.tool("-MEMORIACARP")
    inicial = deepcopy(herramienta.configuracion)
    ficha, leer = modulo(plugin, "memoria_tools").formulario(herramienta.ctx, inicial)
    ficha._arq["modo"].setCurrentIndex(ficha._arq["modo"].findData("fichas"))
    ficha._arq["agrupar"].setCurrentIndex(ficha._arq["agrupar"].findData("planta"))
    ficha._arq["escala"].setCurrentIndex(ficha._arq["escala"].findData(25))
    ficha._arq["huecos"].setChecked(False)
    ficha._arq["rotulos"].setChecked(False)
    ficha._arq["seccion"].setChecked(False)
    responder(
        herramienta,
        {
            "modo": "Fichas",
            "agrupar": "Planta",
            "escala": "1:25",
            "huecos": "No",
            "rotulos": "No",
            "seccion": "No",
        },
    )
    assert herramienta.configuracion == leer()
    ficha.close()


def test_filtrar_la_planta_baja_sin_abrir_niveles_incluye_sus_piezas(plugin):
    sesion, _, _ = modelo(plugin)
    nivel = modulo(plugin, "levels").load(sesion.document)["levels"][0]
    plano = generar(sesion, plugin, {"planta": nivel["name"]})
    assert plano.planos(sesion.document.doc)[0][1]["rows"][0]["unidades"] == 2


def test_actualizar_despues_de_borrar_todas_las_carpinterias_retira_marcas_y_vacia_plano(plugin):
    from core.actions import EraseCommand

    sesion, memoria, _ = modelo(plugin)
    plano = generar(sesion, plugin)
    originales = plano.planos(sesion.document.doc)[0][1]
    puertas = [
        e
        for e in sesion.document.doc.modelspace()
        if (sesion.meta(e) or {}).get("kind") == "opening"
    ]
    modulo(plugin, "transactions").apply_architectural_change(
        sesion.tool("MURO").ctx, EraseCommand(puertas), kind="opening"
    )
    antes = estado(plugin, sesion.document)
    plano.actualizar(sesion.tool("MURO").ctx)
    datos = plano.planos(sesion.document.doc)[0][1]
    assert datos["id"] == originales["id"] and datos["rows"] == []
    assert memoria.catalogo(sesion.document.doc)[1]["tipos"] == []
    assert not plano.avisos(sesion.document.doc)
    sesion.history.undo()
    assert estado(plugin, sesion.document) == antes


def test_biblioteca_ilegible_no_impide_el_plano_ni_inventa_u(plugin, monkeypatch):
    sesion, _, _ = modelo(plugin)

    def ilegible():
        raise ValueError("Biblioteca no válida")

    monkeypatch.setattr(modulo(plugin, "biblioteca_termica"), "cargar", ilegible)
    plano = generar(sesion, plugin)
    assert all(fila["u"] is None for fila in plano.planos(sesion.document.doc)[0][1]["rows"])
    assert not plano.avisos(sesion.document.doc)

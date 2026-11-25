# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: el tipo conserva su orden y el muro conserva su cara exterior en ficha, texto y Deshacer.
from copy import deepcopy
from types import SimpleNamespace

import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_fichas_tipos_usos import qapp  # noqa: F401
from tests.test_wall_tools import Session
from tests.escenarios_r27 import modulo


def test_un_tipo_antiguo_no_adquiere_orden_al_normalizar_y_el_nuevo_si(plugin):
    tipos = modulo(plugin, "parameters_arq")
    antiguo = {"name": "Anterior", "layers": [[0.3, "M"]]}
    assert "orden_capas" not in tipos.normalise_type(antiguo)
    assert tipos.nuevo_tipo([])["orden_capas"] == "exterior-interior"
    assert tipos.normalise_type({**antiguo, "orden_capas": "exterior-interior"})["orden_capas"] == "exterior-interior"
    assert all(t["orden_capas"] == "cara-dibujada" for t in tipos.load_defaults(Session(plugin).document)["wall_types"]
               if t["wall_category"] == "particion")


def test_crear_y_editar_cara_exterior_conserva_identidad_y_deshacer(plugin):
    sesion = Session(plugin)
    arquitectura = modulo(plugin, "architectural_v10")
    transacciones = modulo(plugin, "transactions")
    contexto = sesion.tool("MURO").ctx
    orden = arquitectura.create_wall((0, 0), (5, 0), 0.3, layers=[[0.3, "M"]],
                                     orden_capas="exterior-interior", cara_exterior="izquierda")
    transacciones.apply_architectural_change(contexto, orden)
    antes = deepcopy(sesion.meta(orden.entity))
    assert antes["cara_exterior"] == "izquierda"
    assert antes["orden_capas"] == "exterior-interior"
    cambio = arquitectura.edit_wall(orden.entity, cara_exterior="derecha")
    transacciones.apply_architectural_change(contexto, cambio)
    despues = sesion.meta(orden.entity)
    assert despues["id"] == antes["id"]
    assert despues["cara_exterior"] == "derecha"
    sesion.history.undo()
    assert sesion.meta(orden.entity) == antes
    sesion.history.redo()
    assert sesion.meta(orden.entity) == despues


def test_ficha_y_campos_textuales_comparten_la_cara_exterior(plugin, qapp):
    sesion = Session(plugin)
    valores = {**modulo(plugin, "parameters_arq").load_defaults(sesion.document)["wall"],
               "cara_exterior": "izquierda", "orden_capas": "exterior-interior"}
    contexto = sesion.tool("MURO").ctx
    ficha, leer = modulo(plugin, "bim_dialogs").wall_form(contexto, valores, [])
    try:
        selector = ficha._arq["cara_exterior"]
        assert selector.currentData() == "izquierda"
        selector.setCurrentIndex(selector.findData("derecha"))
        assert leer()["cara_exterior"] == "derecha"
    finally:
        ficha.close()
    campos, _cambiar = modulo(plugin, "linea_fichas").campos_muro(contexto, valores)
    assert any(campo.clave == "cara_exterior" for campo in campos)


def test_la_ficha_de_tipo_conserva_el_pendiente_hasta_que_se_revise(plugin, qapp):
    sesion = Session(plugin)
    fichas = modulo(plugin, "bim_dialogs")
    ficha, leer = fichas.wall_types_form(sesion.tool("MURO").ctx, [
        {"name": "Anterior", "layers": [[0.3, "M"]]},
    ])
    try:
        assert "orden_capas" not in leer()[0]
        selector = ficha._arq["orden_capas"]
        selector.setCurrentIndex(selector.findData("exterior-interior"))
        assert leer()[0]["orden_capas"] == "exterior-interior"
    finally:
        ficha.close()


def test_el_csv_conserva_ordenes_y_tipos_sin_revisar(plugin, tmp_path):
    sesion = Session(plugin)
    parametros = modulo(plugin, "parameters_arq")
    datos = parametros.load_defaults(sesion.document)
    datos["wall_types"] = [
        {"name": "Anterior", "layers": [[0.3, "M"]]},
        {"name": "Nuevo", "layers": [[0.3, "M"]], "orden_capas": "exterior-interior"},
    ]
    sesion.history.execute(parametros.SetArchitecturalDefaults(datos))
    ruta = tmp_path / "tipos.csv"
    contexto = SimpleNamespace(document=sesion.document, execute=sesion.history.execute, echo=sesion.out.append)
    parametros.tipos_muro(contexto, "exportar", str(ruta))
    assert ruta.is_file(), sesion.out
    otra = Session(plugin)
    contexto_otra = SimpleNamespace(document=otra.document, execute=otra.history.execute, echo=otra.out.append)
    parametros.tipos_muro(contexto_otra, "importar", str(ruta))
    tipos = {t["name"]: t for t in parametros.load_defaults(otra.document)["wall_types"]}
    assert "orden_capas" not in tipos["Anterior"]
    assert tipos["Nuevo"]["orden_capas"] == "exterior-interior"


def test_la_simetria_conserva_la_cara_fisica_exterior(plugin):
    from core import actions

    sesion = Session(plugin)
    orden = modulo(plugin, "architectural_v10").create_wall((0, 1), (5, 1), cara_exterior="izquierda")
    modulo(plugin, "transactions").apply_architectural_change(sesion.tool("MURO").ctx, orden)
    sesion.history.execute(actions.mirror_entities([orden.entity], (0, 0), (1, 0), keep_source=False))
    transformado = modulo(plugin, "frame").reconcile(orden.entity, sesion.meta(orden.entity))
    assert transformado["cara_exterior"] == "derecha"
    sesion.history.undo()
    assert modulo(plugin, "frame").reconcile(orden.entity, sesion.meta(orden.entity))["cara_exterior"] == "izquierda"


@pytest.mark.parametrize("campo,valor", [("cara_exterior", "inventada"), ("orden_capas", "inventado")])
def test_no_se_crea_un_muro_con_una_cara_o_un_orden_invalidos(plugin, campo, valor):
    arquitectura = modulo(plugin, "architectural_v10")
    with pytest.raises(ValueError):
        arquitectura.create_wall((0, 0), (5, 0), **{campo: valor})

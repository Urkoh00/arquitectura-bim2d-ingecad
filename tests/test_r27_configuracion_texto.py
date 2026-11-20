# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: configuración textual, catálogos y niveles conservan datos e historial.
from copy import deepcopy
import importlib
import pytest
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session
from tests.test_r27_creacion_texto import responder


def modulo(plugin, nombre):
    paquete = plugin.tools["MURO"].__module__.rsplit(".", 1)[0]
    return importlib.import_module(paquete + "." + nombre)


@pytest.mark.parametrize("orden", ["PARAMETROSARQ", "USOSARQ", "TIPOSMURO", "NIVELES"])
def test_configuracion_texto_acepta_por_defecto_y_deshace(plugin, orden):
    sesion = Session(plugin)
    parametros = modulo(plugin, "parameters_arq")
    niveles = modulo(plugin, "levels")
    antes = deepcopy(parametros.load_defaults(sesion.document))
    niveles_antes = deepcopy(niveles.load(sesion.document))
    herramienta = sesion.tool("-" + orden)
    responder(herramienta)
    despues = deepcopy(parametros.load_defaults(sesion.document))
    if orden == "TIPOSMURO":
        assert {t["name"]: t for t in despues["wall_types"]} == {
            t["name"]: t for t in antes["wall_types"]
        }
    niveles_despues = deepcopy(niveles.load(sesion.document))
    assert sesion.history.depth == 1
    sesion.history.undo()
    assert parametros.load_defaults(sesion.document) == antes
    assert niveles.load(sesion.document) == niveles_antes
    sesion.history.redo()
    assert parametros.load_defaults(sesion.document) == despues
    assert niveles.load(sesion.document) == niveles_despues


def test_parametros_unidades_acentos_y_configuracion_existente(plugin):
    sesion = Session(plugin)
    parametros = modulo(plugin, "parameters_arq")
    antes = parametros.load_defaults(sesion.document)
    herramienta = sesion.tool("-PARAMETROSARQ")
    responder(
        herramienta,
        {
            "wall.thickness": "250mm",
            "column.height": "350cm",
            "wall.name": "Muro térmico de baño",
            "general.norte": "27,5",
        },
    )
    despues = parametros.load_defaults(sesion.document)
    assert despues["wall"]["thickness"] == 0.25
    assert despues["column"]["height"] == 3.5
    assert despues["general"]["norte"] == 27.5
    assert despues["wall"]["name"] == "Muro térmico de baño"
    assert despues["wall_types"] == antes["wall_types"]
    assert despues["opening_types"] == antes["opening_types"]


def test_usos_independientes_se_guardan_en_un_paso(plugin):
    sesion = Session(plugin)
    herramienta = sesion.tool("-USOSARQ")
    responder(
        herramienta,
        {
            "tipo_edificio_cee": "EdificioUsoTerciario",
            "uso_dbhe": "Otros usos",
            "carga_dbhe": "Alta",
            "horario_dbhe": "24",
            "uso_dbsi": "Docente",
        },
    )
    valores = modulo(plugin, "parameters_arq").load_defaults(sesion.document)["usos"]
    assert valores == dict(
        tipo_edificio_cee="EdificioUsoTerciario",
        uso_dbhe="otros usos",
        carga_dbhe="alta",
        horario_dbhe="24",
        uso_dbsi="Docente",
    )
    assert sesion.history.depth == 1


def test_tipo_nuevo_renombrar_y_eliminar_sin_cambiar_otros(plugin):
    sesion = Session(plugin)
    parametros = modulo(plugin, "parameters_arq")
    antes = deepcopy(parametros.load_defaults(sesion.document)["wall_types"])
    herramienta = sesion.tool("-TIPOSMURO")
    responder(
        herramienta,
        {"accion": "Crear", "nombre": "Muro térmico", "capas": "0,02 Yeso + 0,1 Ladrillo"},
    )
    creados = parametros.load_defaults(sesion.document)["wall_types"]
    assert {t["name"]: t for t in creados if t["name"] != "Muro térmico"} == {
        t["name"]: t for t in antes
    }
    herramienta = sesion.tool("-TIPOSMURO")
    responder(
        herramienta, {"accion": "Editar", "anterior": "Muro térmico", "nombre": "Muro de baño"}
    )
    assert any(
        t["name"] == "Muro de baño" for t in parametros.load_defaults(sesion.document)["wall_types"]
    )
    herramienta = sesion.tool("-TIPOSMURO")
    responder(herramienta, {"accion": "Eliminar", "anterior": "Muro de baño"})
    assert {t["name"]: t for t in parametros.load_defaults(sesion.document)["wall_types"]} == {
        t["name"]: t for t in antes
    }
    assert sesion.history.depth == 3


def test_niveles_crear_cambiar_activo_y_asignar_conserva_identidad(plugin):
    sesion = Session(plugin)
    muro = sesion.tool("MURO")
    muro.on_point((0.0, 0.0))
    muro.on_point((4.0, 0.0))
    muro.on_enter()
    entidad = next(iter(sesion.walls().values()))
    identidad = sesion.meta(entidad)["id"]
    herramienta = sesion.tool("-NIVELES")
    responder(herramienta, {"accion": "Crear", "nombre": "Planta técnica", "cota": "350cm"})
    herramienta = sesion.tool("-NIVELASIGNAR")
    herramienta.on_selection([entidad])
    responder(herramienta, {"nivel": "Planta técnica", "conservar": "No"})
    assert sesion.meta(entidad)["id"] == identidad
    assert sesion.meta(entidad)["base"] == 3.5
    sesion.history.undo()
    assert sesion.meta(entidad)["base"] == 0.0
    sesion.history.redo()
    assert sesion.meta(entidad)["base"] == 3.5

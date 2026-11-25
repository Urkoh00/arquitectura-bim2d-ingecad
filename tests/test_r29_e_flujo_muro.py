# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: MURO lleva al tramo creado el orden y la cara elegidos en ficha o por doble clic.
from copy import deepcopy
from types import SimpleNamespace

import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_fichas_tipos_usos import qapp  # noqa: F401
from tests.test_wall_tools import Session
from tests.escenarios_r27 import modulo


@pytest.mark.parametrize("flujo", ["ficha", "doble_clic"])
def test_crear_muro_conserva_la_envolvente_del_modelo_o_de_su_ficha(plugin, qapp, monkeypatch, flujo):
    sesion = Session(plugin)
    datos = {**modulo(plugin, "parameters_arq").load_defaults(sesion.document)["wall"],
             "layers": [[0.05, "Acabado"], [0.25, "Hoja"]], "type_name": "Ensayo",
             "cara_exterior": "izquierda", "orden_capas": "exterior-interior"}
    if flujo == "ficha":
        fichas = modulo(plugin, "bim_dialogs")
        monkeypatch.setattr(fichas, "available", lambda contexto: True)
        monkeypatch.setattr(fichas, "wall_properties", lambda contexto, valores: deepcopy(datos))
    else:
        arquitectura = modulo(plugin, "architectural_v10")
        origen = arquitectura.create_wall((0, 0), (5, 0), **datos)
        modulo(plugin, "transactions").apply_architectural_change(sesion.tool("MURO").ctx, origen)
        contexto = SimpleNamespace(document=sesion.document, start_tool=lambda nombre: None)
        assert modulo(plugin, "double_click").on_double_click(contexto, origen.entity)
    herramienta = sesion.tool("MURO")
    herramienta.on_point((0, 2))
    herramienta.on_point((5, 2))
    herramienta.on_enter()
    nuevo = next(registro for entidad in sesion.document.doc.modelspace()
                 if (registro := sesion.meta(entidad) or {}).get("kind") == "wall"
                 and registro["a"] == [0.0, 2.0])
    assert nuevo["cara_exterior"] == "izquierda"
    assert nuevo["orden_capas"] == "exterior-interior"

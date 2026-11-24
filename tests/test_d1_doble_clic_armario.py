# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: la ficha propia del armario conserva su modelo al abrirse desde el dibujo.
from copy import deepcopy
from types import SimpleNamespace

import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_fichas_tipos_usos import qapp  # noqa: F401
from tests.test_wall_tools import Session
from tests.escenarios_r27 import modulo


@pytest.mark.parametrize("modo", ["adosado", "nicho"])
@pytest.mark.parametrize("aceptar", [False, True])
@pytest.mark.parametrize("por_simbolo", [False, True])
def test_doble_clic_armario_utiliza_su_ficha_y_conserva_el_modelo(
    plugin, qapp, monkeypatch, modo, aceptar, por_simbolo
):
    from PySide6.QtCore import QTimer

    sesion = Session(plugin)
    transacciones = modulo(plugin, "transactions")
    arquitectura = modulo(plugin, "architectural_v10")
    contexto_creacion = sesion.tool("MURO").ctx
    muro = arquitectura.create_wall((0, 0), (6, 0), 0.3, 2.7, wall_category="particion")
    transacciones.apply_architectural_change(contexto_creacion, muro)
    armarios = modulo(plugin, "cabinets")
    orden = armarios.create(muro.entity, 1.0, 1.2, 0.1 if modo == "nicho" else 0.6,
                            2.1, leaves=2, mode=modo, body_material="Madera de ensayo")
    transacciones.apply_architectural_change(contexto_creacion, orden, kind="opening")
    antes = deepcopy(sesion.meta(orden.entity))
    designado = orden.entity
    if por_simbolo:
        designado = next(
            entidad for entidad in sesion.document.doc.modelspace()
            if (sesion.meta(entidad) or {}).get("kind") == "opening_symbol"
            and sesion.meta(entidad).get("opening_id") == antes["id"]
        )
    original = armarios.form
    entradas = []

    def abrir(contexto, registro):
        entradas.append(deepcopy(registro))
        ficha, leer = original(contexto, registro)
        if aceptar:
            ficha._arq["body_material"].setText("Material de ensayo")
        QTimer.singleShot(0, ficha.accept if aceptar else ficha.reject)
        return ficha, leer

    monkeypatch.setattr(armarios, "form", abrir)
    monkeypatch.setattr(modulo(plugin, "bim_dialogs"), "available", lambda contexto: True)
    iniciadas = []
    contexto = SimpleNamespace(document=sesion.document, execute=sesion.history.execute,
                               echo=sesion.out.append, start_tool=iniciadas.append)
    assert modulo(plugin, "double_click").on_double_click(contexto, designado)
    assert not iniciadas
    assert len(entradas) == 1
    assert {clave: entradas[0][clave] for clave in antes} == antes
    esperado = deepcopy(antes)
    if aceptar:
        esperado["body_material"] = "Material de ensayo"
        # La edición común explicita el material principal vacío sin alterar las piezas.
        esperado.setdefault("material", "")
    despues = sesion.meta(orden.entity)
    assert despues == esperado
    if aceptar:
        sesion.history.undo()
        assert sesion.meta(orden.entity) == antes
        sesion.history.redo()
        assert sesion.meta(orden.entity) == despues

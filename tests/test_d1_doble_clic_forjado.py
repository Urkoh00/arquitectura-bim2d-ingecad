# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: el doble clic del forjado reutiliza su ficha, sin perder huecos ni identidad.
from copy import deepcopy
from types import SimpleNamespace

import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_fichas_tipos_usos import qapp  # noqa: F401
from tests.test_wall_tools import Session
from tests.escenarios_r27 import modulo


@pytest.mark.parametrize("aceptar", [False, True])
def test_doble_clic_forjado_abre_ficha_propia_y_conserva_huecos(plugin, qapp, monkeypatch, aceptar):
    from PySide6.QtCore import QTimer

    sesion = Session(plugin)
    forjados = modulo(plugin, "slabs")
    orden = forjados.apply_new(sesion.tool("MURO").ctx,
        [(0, 0), (6, 0), (6, 4), (0, 4)], [[(1, 1), (2, 1), (2, 2), (1, 2)]], thickness=0.25)
    antes = deepcopy(forjados.read(orden.entity))
    fichas = modulo(plugin, "slab_tools")
    original = fichas.form
    entradas = []

    def abrir(contexto, registro):
        entradas.append(deepcopy(registro))
        ficha, leer = original(contexto, registro)
        if aceptar:
            ficha._arq["material"].setText("Material de ensayo")
        QTimer.singleShot(0, ficha.accept if aceptar else ficha.reject)
        return ficha, leer

    monkeypatch.setattr(fichas, "form", abrir)
    monkeypatch.setattr(modulo(plugin, "bim_dialogs"), "available", lambda contexto: True)
    iniciadas = []
    contexto = SimpleNamespace(document=sesion.document, execute=sesion.history.execute,
                               echo=sesion.out.append, start_tool=iniciadas.append)
    assert modulo(plugin, "double_click").on_double_click(contexto, orden.entity)
    assert not iniciadas
    assert len(entradas) == 1
    assert entradas[0] == antes
    despues = forjados.read(orden.entity)
    esperado = deepcopy(antes)
    if aceptar:
        esperado["material"] = "Material de ensayo"
    assert despues == esperado
    if aceptar:
        sesion.history.undo()
        assert forjados.read(orden.entity) == antes
        sesion.history.redo()
        assert forjados.read(orden.entity) == despues

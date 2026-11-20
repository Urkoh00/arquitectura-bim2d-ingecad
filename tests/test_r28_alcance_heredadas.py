# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: las órdenes informativas explican su alcance sin modificar dibujo ni selección.
import importlib
import pytest
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session


@pytest.mark.parametrize(
    "orden,frase",
    [
        ("ELEMENTOS", "no activa"),
        ("SELATRIB", "no selecciona"),
        ("HIPERVINCULO", "no abre"),
        ("URL", "no abre"),
        ("LISTATEXTOS", "no copia"),
    ],
)
def test_aviso_y_ayuda_explican_la_limitacion_actual(plugin, orden, frase):
    sesion = Session(plugin)
    sesion.tool(orden)
    assert frase in "\n".join(sesion.out).lower()
    assert sesion.history.depth == 0
    assert not list(sesion.document.doc.modelspace())
    paquete = plugin.tools["MURO"].__module__.rsplit(".", 1)[0]
    ayuda = importlib.import_module(paquete + ".ayuda")
    filas = [fila for _, filas in ayuda.SECCIONES for fila in filas if orden in fila[0]]
    assert len(filas) == 1
    assert frase in " ".join([filas[0][1], *filas[0][2]]).lower()

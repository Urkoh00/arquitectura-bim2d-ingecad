# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: EXPORTARBIM sin ruta no intenta abrir un selector cuando no existe QApplication.
from tests.ejecucion_sin_qt_r27 import invocar_orden_sin_qt


def test_exportacion_sin_ruta_ni_qt_cancela_con_aviso():
    salida = invocar_orden_sin_qt("EXPORTARBIM")
    assert "-EXPORTARBIM" in salida
    assert "cancelado" in salida

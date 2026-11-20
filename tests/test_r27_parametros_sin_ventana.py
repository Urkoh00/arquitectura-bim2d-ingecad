# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: PARAMETROSARQ informa sin intentar construir una ficha cuando no existe QApplication.
from tests.ejecucion_sin_qt_r27 import invocar_orden_sin_qt


def test_parametros_sin_qt_informa_y_no_cambia_el_documento():
    salida = invocar_orden_sin_qt("PARAMETROSARQ")
    assert "-PARAMETROSARQ" in salida

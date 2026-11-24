# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: reproducciones de la designación entre niveles y de la referencia de carpintería.
import math

import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_fichas_tipos_usos import qapp  # noqa: F401
from tests.test_wall_tools import Session
from tests.escenarios_r27 import modulo


def test_puerta_convierte_el_ancho_actual_de_hojas_y_cerco_no_el_campo_oculto(plugin, qapp):
    sesion = Session(plugin)
    muro = modulo(plugin, "geom.junctions").Wall("curvo", (0, 0), (8, 0), 0.4, bulge=0.2)
    ficha, leer = modulo(plugin, "bim_dialogs").carpentry_form(sesion.tool("CARPINTERIA").ctx, {
        "type": "door", "operation": "SLIDING", "leaves": 2,
        "width": 0.9, "height": 2.1, "sill": 0, "curve_mode": "plana",
        "width_reference": "cuerda", "_wall_spec": muro,
    })
    try:
        campos = ficha._arq
        campos["leaf"].setValue(0.825)
        campos["leaf2"].setValue(0.725)
        campos["frame_width"].setValue(0.03)
        assert leer()["width"] == pytest.approx(1.61)
        campos["curve_mode"].setCurrentIndex(campos["curve_mode"].findData("curva"))
        campos["width_reference"].setCurrentIndex(campos["width_reference"].findData("eje"))
        esperado = 2 * muro.r * math.asin(1.61 / (2 * muro.r))
        assert leer()["width"] == pytest.approx(esperado, abs=5.1e-5)
    finally:
        ficha.close()

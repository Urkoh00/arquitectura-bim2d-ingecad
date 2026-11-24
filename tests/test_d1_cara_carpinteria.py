# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: reproducciones de la designación entre niveles y de la referencia de carpintería.

import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_fichas_tipos_usos import qapp  # noqa: F401
from tests.test_wall_tools import Session
from tests.escenarios_r27 import modulo


@pytest.mark.parametrize("cara_guardada", [1, -1])
@pytest.mark.parametrize("bulge", [0.2, -0.2])
def test_referencia_de_ventana_utiliza_la_cara_elegida_en_la_edicion(
    plugin, qapp, cara_guardada, bulge
):
    from PySide6.QtWidgets import QComboBox

    sesion = Session(plugin)
    muro = modulo(plugin, "geom.junctions").Wall("curvo", (0, 0), (8, 0), 0.4, bulge=bulge)
    ficha, leer = modulo(plugin, "bim_dialogs").carpentry_form(sesion.tool("CARPINTERIA").ctx, {
        "type": "window", "operation": "FIXED", "width": 1.0,
        "height": 1.2, "sill": 0.9, "curve_mode": "curva",
        "width_reference": "interior", "side": cara_guardada, "_wall_spec": muro,
    }, editing=True)
    try:
        caras = [control for control in ficha.findChildren(QComboBox)
                 if control.count() == 2 and control.itemData(0) == 1 and control.itemData(1) == -1]
        assert len(caras) == 1
        cara_elegida = -cara_guardada
        caras[0].setCurrentIndex(caras[0].findData(cara_elegida))
        referencia = ficha._arq["width_reference"]
        referencia.setCurrentIndex(referencia.findData("exterior"))
        interior = muro.hi if cara_elegida > 0 else muro.lo
        exterior = muro.lo if cara_elegida > 0 else muro.hi
        esperado = (muro.r - muro.d * exterior) / (muro.r - muro.d * interior)
        assert leer()["width"] == pytest.approx(esperado, abs=5.1e-5)
        assert leer()["side"] == cara_elegida
    finally:
        ficha.close()

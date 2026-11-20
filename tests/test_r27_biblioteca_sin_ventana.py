# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: importar una biblioteca sin ruta y sin Qt informa en lugar de abortar en un selector.
from tests.ejecucion_sin_qt_r27 import invocar_orden_sin_qt


def test_biblioteca_sin_ruta_ni_qt_informa_y_permite_indicar_archivo():
    preparacion = """
from arquitectura import biblioteca_termica
biblioteca_termica.catalogos_instalados = lambda: []
argumentos = ['importar']
"""
    salida = invocar_orden_sin_qt("BIBLIOTECAHE", preparacion)
    assert "indique el fichero" in salida

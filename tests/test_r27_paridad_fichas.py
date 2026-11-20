# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: la variante -ORDEN y la ficha dan los mismos datos con los valores por defecto (revisión de Claude, R27).
"""Si a la ficha se le añade un campo y a la variante no (o al revés), o
si un valor por defecto difiere, esta prueba falla: las dos formas de
responder no pueden separarse sin que se note. Ambas pasan por la misma
función ``normalizar_*``; se compara lo que devuelve en cada caso."""
import importlib
from copy import deepcopy

import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session
from tests.test_r27_creacion_texto import responder

CASOS = {'-MURO': 'normalizar_muro', '-PILAR': 'normalizar_pilar',
         '-CARPINTERIA': 'normalizar_carpinteria'}


# Las fija la orden al crear el elemento, no la persona: no son campos.
IGUALES_POR_LA_ORDEN = ('ifc_class', 'schema')


def _paquete(plugin):
    return plugin.tools['MURO'].__module__.rsplit('.', 1)[0]


@pytest.mark.parametrize('nombre', list(CASOS))
def test_ficha_y_variante_coinciden_con_los_valores_por_defecto(plugin, nombre, monkeypatch):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    pkg = _paquete(plugin)
    F = importlib.import_module(pkg + '.linea_fichas')
    D = importlib.import_module(pkg + '.bim_dialogs')
    original = getattr(F, CASOS[nombre])
    vistos = []

    def registrar(*args, **kw):
        salida = original(*args, **kw)
        vistos.append(deepcopy(salida))
        return salida

    monkeypatch.setattr(F, CASOS[nombre], registrar)
    sesion = Session(plugin)
    normal = sesion.tool(nombre[1:])                 # la orden con ficha, sin abrirla
    if nombre == '-MURO':
        _dlg, read = D.wall_form(normal.ctx, {**normal.bim, 'thickness': normal.thickness,
                                              'height': normal.height, 'base': normal.base,
                                              'reference': normal.reference})
    elif nombre == '-PILAR':
        _dlg, read = D.column_form(normal.ctx, deepcopy(normal.values),
                                   getattr(normal, 'anchor', 5))
    else:
        _dlg, read = D.carpentry_form(normal.ctx, {**normal.v, **normal.bim})
    read()
    ficha = vistos[-1]
    variante = sesion.tool(nombre)
    responder(variante)
    texto = vistos[-1]
    for k in IGUALES_POR_LA_ORDEN:
        ficha.pop(k, None), texto.pop(k, None)
    assert set(ficha) <= set(texto), sorted(set(ficha) - set(texto))
    # La variante puede devolver además el estado que la orden ya tenía
    # (bisagra, cara...), que no es un campo de la ficha.
    propio = set(getattr(normal, 'v', {})) | set(getattr(normal, 'bim', {}))
    assert set(texto) - set(ficha) <= propio, sorted(set(texto) - set(ficha) - propio)
    distintos = {}
    for k in ficha:
        a, b = ficha[k], texto[k]
        igual = a == pytest.approx(b) if isinstance(a, float) and isinstance(b, (int, float)) else a == b
        if not igual:
            distintos[k] = (a, b)
    assert not distintos

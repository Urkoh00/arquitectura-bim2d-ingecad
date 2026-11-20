# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: la reapertura de fichas textuales no captura las opciones ni los nombres del original.
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_r27_creacion_texto import responder
from tests.test_wall_tools import Session


def test_d_al_elegir_referencia_de_muro_sigue_siendo_derecha(plugin):
    herramienta = Session(plugin).tool('-MURO')
    responder(herramienta)
    herramienta.on_option('referencia')
    assert herramienta.on_option('d') is True
    assert herramienta._campos_texto is None
    assert herramienta.reference == 'derecha'


def test_d_como_nombre_de_recinto_no_abre_la_ficha(plugin):
    herramienta = Session(plugin).tool('-RECINTO')
    responder(herramienta)
    herramienta.on_option('nombre')
    herramienta.on_option('D')
    assert herramienta._campos_texto is None
    assert herramienta.next_name == 'D'

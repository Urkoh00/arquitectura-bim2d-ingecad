# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: las preguntas preservan nombres literales y aplican las unidades y precisión de las fichas.
import pytest
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session
from tests.test_r27_configuracion_texto import modulo
from tests.test_r27_creacion_texto import responder


def test_valores_por_defecto_con_comillas_y_precision(plugin):
    sesion = Session(plugin)
    parametros = modulo(plugin, 'parameters_arq')
    datos = parametros.load_defaults(sesion.document)
    datos['column']['name'] = '"Anterior"'
    datos['column']['height'] = 12345.1234
    sesion.history.execute(parametros.SetArchitecturalDefaults(datos))
    herramienta = sesion.tool('-PILAR')
    responder(herramienta)
    assert herramienta.values['name'] == '"Anterior"'
    assert herramienta.values['height'] == 12345.1234


def test_opciones_con_etiqueta_ambigua_se_pueden_elegir_sin_cambiar_nombre(plugin):
    campos = modulo(plugin, 'linea_campos')
    campo = campos.Campo('tipo', 'Tipo', 'opcion', (('Genérico', None), ('Genérico', 'Genérico')))
    with pytest.raises(ValueError, match='ambiguo'):
        campo.leer('Genérico')
    assert campo.leer('#1') is None
    assert campo.leer('#2') == 'Genérico'


@pytest.mark.parametrize('entrada,esperado', [('123,45mm', .1235), ('12.345cm', .1235), ('0.12345m', .1235)])
def test_precision_de_ficha_en_medidas(plugin, entrada, esperado):
    campo = modulo(plugin, 'linea_campos').Campo('valor', 'Medida', 'numero')
    assert campo.leer(entrada) == esperado

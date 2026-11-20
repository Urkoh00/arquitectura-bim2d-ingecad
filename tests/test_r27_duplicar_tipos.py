# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: crear y duplicar tipos por texto conserva el original y comparte los valores de la ficha.
from copy import deepcopy
import pytest
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_r27_configuracion_texto import modulo
from tests.test_r27_creacion_texto import responder
from tests.test_wall_tools import Session


@pytest.mark.parametrize('accion', ['crear', 'duplicar'])
def test_crear_o_duplicar_tipo_por_texto_conserva_catalogo_y_deshacer(plugin, accion):
    sesion = Session(plugin)
    parametros = modulo(plugin, 'parameters_arq')
    antes = deepcopy(parametros.load_defaults(sesion.document)['wall_types'])
    original = antes[0] if accion == 'duplicar' else None
    esperado = parametros.nuevo_tipo(antes, original)
    herramienta = sesion.tool('-TIPOSMURO')
    responder(herramienta, {'accion': accion})
    despues = parametros.load_defaults(sesion.document)['wall_types']
    assert parametros.find_wall_type(despues, esperado['name']) == esperado
    assert {t['name']: t for t in despues if t['name'] != esperado['name']} == {t['name']: t for t in antes}
    assert sesion.history.depth == 1
    sesion.history.undo()
    assert parametros.load_defaults(sesion.document)['wall_types'] == antes
    sesion.history.redo()
    assert parametros.load_defaults(sesion.document)['wall_types'] == despues

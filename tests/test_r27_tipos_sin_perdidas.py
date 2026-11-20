# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: aceptar la ficha o cambiar capas por texto no altera categoría ni precisión del tipo.
from copy import deepcopy
from types import SimpleNamespace
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_fichas_tipos_usos import qapp  # noqa: F401
from tests.test_r27_configuracion_texto import modulo
from tests.test_wall_tools import Session


def test_aceptar_ficha_de_tipos_conserva_espesor_exacto(plugin, qapp):
    sesion = Session(plugin)
    parametros = modulo(plugin, 'parameters_arq')
    tipo = parametros.normalise_type({'name': 'Tipo preciso', 'wall_category': 'medianera',
                                     'layers': [[.0123456789, 'Yeso'], [.0789123456, 'Fábrica']]})
    contexto = SimpleNamespace(host=None, services=None)
    dialogo, leer = modulo(plugin, 'bim_dialogs').wall_types_form(contexto, [tipo])
    assert leer() == [tipo]
    dialogo.close()


def test_editar_capas_por_texto_conserva_la_categoria(plugin):
    sesion = Session(plugin)
    parametros = modulo(plugin, 'parameters_arq')
    antes = deepcopy(parametros.load_defaults(sesion.document))
    tipo = antes['wall_types'][0]
    contexto = SimpleNamespace(document=sesion.document, execute=sesion.history.execute,
                              echo=sesion.out.append, host=None, services=None)
    parametros.tipos_muro(contexto, tipo['name'] + ' = 0,08 Fábrica')
    despues = parametros.find_wall_type(parametros.load_defaults(sesion.document)['wall_types'], tipo['name'])
    assert despues['wall_category'] == tipo['wall_category']
    assert despues['thickness'] == .08

# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: el catálogo textual conserva espesores exactos y materiales con separadores.
from copy import deepcopy
import importlib
from types import SimpleNamespace
import pytest
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session


def parametros(plugin):
    paquete = plugin.tools['MURO'].__module__.rsplit('.', 1)[0]
    return importlib.import_module(paquete + '.parameters_arq')


@pytest.mark.parametrize('material', ['Montante + lana mineral', 'Refuerzo + 2 capas',
                                    'Material; especial', 'Acabado "interior"'])
def test_formula_conserva_material_y_precision(plugin, material):
    modulo = parametros(plugin)
    tipo = modulo.normalise_type({'name': 'Tipo sintético', 'layers': [[.0125, material], [.0125, 'Yeso']]})
    texto = modulo.layers_text(tipo)
    assert modulo.parse_type(tipo['name'] + ' = ' + texto) == tipo


def test_exportar_importar_csv_recupera_catalogo_completo(plugin, tmp_path):
    sesion = Session(plugin)
    modulo = parametros(plugin)
    valores = modulo.load_defaults(sesion.document)
    valores['wall_types'].append(modulo.normalise_type({'name': 'Tipo; sintético',
        'layers': [[.0125, 'Material; especial + 2 capas'], [.0125, 'Yeso']]}))
    sesion.history.execute(modulo.SetArchitecturalDefaults(valores))
    originales = deepcopy(valores['wall_types'])
    ctx = SimpleNamespace(document=sesion.document, execute=sesion.history.execute,
                          echo=sesion.out.append, host=None, services=None)
    ruta = tmp_path / 'catalogo.csv'
    modulo.tipos_muro(ctx, 'exportar', str(ruta))
    valores['wall_types'] = []
    sesion.history.execute(modulo.SetArchitecturalDefaults(valores))
    modulo.tipos_muro(ctx, 'importar', str(ruta))
    recuperados = modulo.load_defaults(sesion.document)['wall_types']
    assert {t['name']: t for t in recuperados} == {t['name']: t for t in originales}, sesion.out
    sesion.history.undo()
    assert modulo.load_defaults(sesion.document)['wall_types'] == []
    sesion.history.redo()
    assert modulo.load_defaults(sesion.document)['wall_types'] == recuperados


def test_csv_capa_sin_material_conserva_categoria(plugin, tmp_path):
    sesion = Session(plugin)
    modulo = parametros(plugin)
    valores = modulo.load_defaults(sesion.document)
    tipo = modulo.normalise_type({'name': 'Medianera sin material', 'layers': [[.25, '']],
                                  'wall_category': 'medianera'})
    valores['wall_types'] = [tipo]
    sesion.history.execute(modulo.SetArchitecturalDefaults(valores))
    ctx = SimpleNamespace(document=sesion.document, execute=sesion.history.execute,
                          echo=sesion.out.append, host=None, services=None)
    ruta = tmp_path / 'catalogo.csv'
    modulo.tipos_muro(ctx, 'exportar', str(ruta))
    valores['wall_types'] = []
    sesion.history.execute(modulo.SetArchitecturalDefaults(valores))
    modulo.tipos_muro(ctx, 'importar', str(ruta))
    assert modulo.load_defaults(sesion.document)['wall_types'] == [tipo]

# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: controles de recubrimiento y clasificación explícita guardados en el dibujo.
from copy import deepcopy

import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_fichas_tipos_usos import qapp  # noqa: F401
from tests.test_wall_tools import Session
from tests.escenarios_r27 import modulo


def test_los_pilares_nuevos_tienen_particion_de_siete_centimetros(plugin):
    datos = modulo(plugin, 'parameters_arq').load_defaults(Session(plugin).document)['column']
    assert datos['cover'] == pytest.approx(0.07)
    assert datos['insulation_mode'] == 'auto'


def test_guardar_y_editar_pilar_conserva_los_controles_y_un_deshacer(plugin):
    sesion = Session(plugin)
    columnas = modulo(plugin, 'columns')
    transacciones = modulo(plugin, 'transactions')
    datos = {**modulo(plugin, 'parameters_arq').load_defaults(sesion.document)['column'],
             'cover': 0.07, 'cover_type': '', 'cover_material': 'Hoja de recubrimiento',
             'insulation_mode': 'con', 'insulation_thickness': 0.045,
             'insulation_material': 'Aislante de ensayo'}
    orden = columnas.column_command((2, 2), datos)
    transacciones.apply_architectural_change(sesion.tool('PILAR').ctx, orden, kind='column')
    entidad = next(e for e in sesion.document.doc.modelspace()
                   if (sesion.meta(e) or {}).get('kind') == 'column')
    antes = deepcopy(sesion.meta(entidad))
    for campo in ('cover_type', 'cover_material', 'insulation_mode', 'insulation_thickness', 'insulation_material'):
        assert antes[campo] == datos[campo]
    cambio = columnas.EditColumnCommand(entidad, {**antes, 'insulation_mode': 'sin'})
    transacciones.apply_architectural_change(sesion.tool('PILAR').ctx, cambio, kind='column')
    assert sesion.meta(entidad)['insulation_mode'] == 'sin'
    sesion.history.undo()
    assert sesion.meta(entidad) == antes
    sesion.history.redo()
    assert sesion.meta(entidad)['id'] == antes['id']


def test_ficha_y_texto_piden_los_mismos_datos_de_recubrimiento(plugin, qapp):
    sesion = Session(plugin)
    datos = modulo(plugin, 'parameters_arq').load_defaults(sesion.document)['column']
    ficha, leer = modulo(plugin, 'bim_dialogs').column_form(sesion.tool('PILAR').ctx, datos)
    try:
        for campo in ('cover_type', 'cover_material', 'insulation_mode', 'insulation_thickness', 'insulation_material'):
            assert campo in ficha._arq
        ficha._arq['insulation_mode'].setCurrentIndex(ficha._arq['insulation_mode'].findData('con'))
        ficha._arq['insulation_thickness'].setValue(0.045)
        assert leer()['insulation_mode'] == 'con'
        assert leer()['insulation_thickness'] == pytest.approx(0.045)
        campos = modulo(plugin, 'linea_fichas').campos_pilar(datos)
        assert {c.clave for c in campos} >= {'cover_type', 'cover_material', 'insulation_mode',
                                          'insulation_thickness', 'insulation_material'}
    finally:
        ficha.close()


def test_clases_constructivas_son_del_dibujo_y_no_del_nombre(plugin):
    sesion = Session(plugin)
    parametros = modulo(plugin, 'parameters_arq')
    datos = parametros.load_defaults(sesion.document)
    datos['general']['materiales_constructivos'] = {'X': 'aislante', 'Y': 'fabrica'}
    sesion.history.execute(parametros.SetArchitecturalDefaults(datos))
    assert parametros.load_defaults(sesion.document)['general']['materiales_constructivos'] == {'X': 'aislante', 'Y': 'fabrica'}
    campos, valores = modulo(plugin, 'linea_configuracion').campos_parametros(datos)
    assert any(c.clave == 'materiales.X' for c in campos)
    assert valores['materiales.X'] == 'aislante'
    sesion.history.undo()
    assert parametros.load_defaults(sesion.document)['general']['materiales_constructivos'] == {}


def test_no_admite_clases_inventadas_ni_nombres_duplicados(plugin):
    parametros = modulo(plugin, 'parameters_arq')
    datos = parametros.load_defaults(Session(plugin).document)
    for clases in ({'A': 'deducido'}, {'A': 'aislante', 'a': 'hoja'}):
        datos['general']['materiales_constructivos'] = clases
        with pytest.raises(ValueError):
            parametros.validate_defaults(datos)

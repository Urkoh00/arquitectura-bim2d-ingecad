# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: Planos 2D ofrece el tabique y conserva los datos térmicos sin mostrarlos.
from copy import deepcopy

from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_fichas_tipos_usos import qapp  # noqa: F401
from tests.test_wall_tools import Session
from tests.escenarios_r27 import modulo


def test_planos_solo_ofrece_tabique_y_la_ficha_no_pierde_aislamiento(plugin, qapp, monkeypatch):
    sesion = Session(plugin)
    datos = {**modulo(plugin, 'parameters_arq').load_defaults(sesion.document)['column'],
             'insulation_mode': 'con', 'insulation_thickness': 0.045,
             'insulation_material': 'Aislante de ensayo'}
    fichas = modulo(plugin, 'bim_dialogs')
    monkeypatch.setenv('ARQ_PERFIL', 'planos')
    ficha, leer = fichas.column_form(sesion.tool('PILAR').ctx, datos)
    try:
        assert not ficha._arq['cover'].isHidden()
        for campo in ('insulation_mode', 'insulation_thickness', 'insulation_material'):
            assert ficha._arq[campo].isHidden(), campo
        plano = leer()
        campos = modulo(plugin, 'linea_fichas').campos_pilar(deepcopy(datos))
        assert 'cover' in {campo.clave for campo in campos if campo.visible(datos)}
        assert not any(campo.clave.startswith('insulation_') and campo.visible(datos) for campo in campos)
    finally:
        ficha.close()
    monkeypatch.setenv('ARQ_PERFIL', 'termico')
    ficha, leer = fichas.column_form(sesion.tool('PILAR').ctx, datos)
    try:
        assert not ficha._arq['insulation_mode'].isHidden()
        assert leer() == plano
        assert plano['insulation_mode'] == 'con'
        assert plano['insulation_thickness'] == 0.045
    finally:
        ficha.close()


def test_planos_crea_el_tabique_y_cambiar_perfil_no_cambia_el_contrato(plugin, monkeypatch):
    sesion = Session(plugin)
    monkeypatch.setenv('ARQ_PERFIL', 'planos')
    datos = modulo(plugin, 'parameters_arq').load_defaults(sesion.document)['column']
    orden = modulo(plugin, 'columns').column_command((0, 0), datos)
    modulo(plugin, 'transactions').apply_architectural_change(sesion.tool('PILAR').ctx, orden, kind='column')
    intercambio = modulo(plugin, 'exchange')
    antes = [deepcopy(sesion.meta(e)) for e in sesion.document.doc.modelspace()]
    contrato = intercambio.build(sesion.document.doc)
    capas = [e for e in contrato['elements'] if e['ifc_class'] == 'IfcCovering']
    assert [e['enums']['PredefinedType'] for e in capas] == ['CLADDING']
    assert abs(capas[0]['quantities']['NetVolume'] - (0.44 ** 2 - 0.3 ** 2) * 3) < 1e-9
    for perfil in ('bim', 'termico', 'planos'):
        monkeypatch.setenv('ARQ_PERFIL', perfil)
        assert intercambio.build(sesion.document.doc) == contrato
        assert [sesion.meta(e) for e in sesion.document.doc.modelspace()] == antes


def test_planos_no_ofrece_clasificacion_ni_avisos_termicos(plugin, monkeypatch):
    from tests.test_r29_e_pilar_geometria import insertar, pared

    sesion = Session(plugin)
    pared(sesion, plugin)
    insertar(sesion, plugin, centro=(0, 0))
    parametros = modulo(plugin, 'parameters_arq').load_defaults(sesion.document)
    configuracion = modulo(plugin, 'linea_configuracion')
    auditoria = modulo(plugin, 'quality')
    monkeypatch.setenv('ARQ_PERFIL', 'planos')
    campos, valores = configuracion.campos_parametros(parametros)
    assert not any(c.clave.startswith(('materiales.', 'column.insulation_')) and c.visible(valores) for c in campos)
    assert not any('clasifica' in aviso for aviso in auditoria.audit_architecture(sesion.document)['incidencias'])
    monkeypatch.setenv('ARQ_PERFIL', 'termico')
    assert any('clasifica' in aviso for aviso in auditoria.audit_architecture(sesion.document)['incidencias'])

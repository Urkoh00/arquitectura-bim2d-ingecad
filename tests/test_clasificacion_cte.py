# SPDX-License-Identifier: GPL-3.0-or-later
"""Clasificación normativa de recintos (CTE e ITC-BT-25): catálogo, propuesta por
uso, ficha, persistencia en el recinto y exportación como conjunto de propiedades."""
import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401  (fixture)
from tests.test_recintos import _spaces, _vivienda
from tests.test_wall_tools import Session
from tests.test_fichas import _mod, _Ctx, qt  # noqa: F401  (fixture)


def test_catalogo_completo(plugin):
    CU = _mod(Session(plugin), 'cte_usos')
    assert CU.KEYS == ('SI', 'SUA4', 'SUA9_RECINTO', 'SUA9_UNIDAD', 'HE', 'HE3', 'HR', 'HS2',
                       'HS3', 'HS6', 'ITC_BT_25')
    n = {k: len(v) for k, v in CU.LABELS.items()}
    assert n == {'SI': 46, 'SUA4': 7, 'SUA9_RECINTO': 8, 'SUA9_UNIDAD': 3, 'HE': 3, 'HE3': 22,
                 'HR': 14, 'HS2': 1, 'HS3': 7, 'HS6': 2, 'ITC_BT_25': 9}
    for labels in CU.LABELS.values():
        assert len(set(labels)) == len(labels)


def test_propuesta_por_uso_y_validacion(plugin):
    CU = _mod(Session(plugin), 'cte_usos')
    p = CU.propose('Dormitorio')
    assert p['HR'] == 'Protegido (Dormitorio)' and p['HS3'] == 'Resto de dormitorios'
    assert p['SI'] == 'Residencial vivienda (Plantas de vivienda)' and p['HE'].startswith('Habitable')
    assert CU.propose('baño')['HS3'] == 'Locales húmedos'
    assert CU.propose('Garaje')['HR'] == 'Garaje' and 'SI' in CU.propose('Garaje')
    assert CU.propose('Sala de máquinas') == {} and CU.propose('Dormitorio', residential=False) == {}
    assert CU.validate({'HR': '', 'HS6': 'Habitable'}) == {'HS6': 'Habitable'}
    with pytest.raises(ValueError):
        CU.validate({'HR': 'Dormitorio'})          # etiqueta de otro conjunto
    with pytest.raises(ValueError):
        CU.validate({'XX': 'Habitable'})


def test_ficha_de_recinto_con_clasificacion(plugin, qt):
    bd = _mod(Session(plugin), 'bim_dialogs')
    dlg, read = bd.space_form(_Ctx(), {'name': 'Dormitorio 1', 'height': 2.5,
                                       'cte': {'HS6': 'Habitable'}}, by_use=True)
    w = dlg._arq
    assert w['cte']['HS6'].currentData() == 'Habitable'
    w['use'].setText('Dormitorio')
    w['propose'].click()
    v = read()
    assert v['cte']['HR'] == 'Protegido (Dormitorio)' and v['cte']['ITC_BT_25'] == 'Dormitorios'
    w['cte']['HS2'].setCurrentIndex(1)
    assert read()['cte']['HS2'] == 'Almacén de contenedores'


def test_recinto_guarda_y_exporta_la_clasificacion(plugin, tmp_path):
    s = Session(plugin)
    _vivienda(s)
    t = s.tool('RECINTO')
    t.apply_sheet({'name': 'Dormitorio 1', 'use': 'Dormitorio', 'height': 2.5,
                   'cte': {'HR': 'Protegido (Dormitorio)', 'HS3': 'Dormitorio principal'}})
    t.on_point((2, 2))
    sp = _spaces(s)[0]
    assert s.meta(sp)['cte'] == {'HR': 'Protegido (Dormitorio)', 'HS3': 'Dormitorio principal'}
    data = s.export(tmp_path)
    space = next(e for e in data['elements'] if e['ifc_class'] == 'IfcSpace')
    assert space['psets']['ARQ_ClasificacionCTE'] == {'HR': 'Protegido (Dormitorio)',
                                                       'HS3': 'Dormitorio principal'}
    # PROPIEDADESARQ la cambia en un solo paso, y Deshacer la devuelve
    P = _mod(s, 'arq_properties')
    s.history.execute(P.space_change(sp, {'cte': {'HR': 'Habitable'}}))
    assert s.meta(_spaces(s)[0])['cte'] == {'HR': 'Habitable'}
    s.history.undo()
    assert s.meta(_spaces(s)[0])['cte']['HS3'] == 'Dormitorio principal'

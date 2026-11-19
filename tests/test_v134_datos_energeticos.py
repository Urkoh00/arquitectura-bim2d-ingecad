# SPDX-License-Identifier: GPL-3.0-or-later
"""v1.34: datos que piden los programas de cálculo energético.

- el norte del proyecto (PARAMETROSARQ > General) viaja en el contrato;
- cada recinto lleva su tipo IFC (INTERNAL, o EXTERNAL si es exterior);
- cada forjado tiene clase: forjado (FLOOR), solera (BASESLAB, contra el
  terreno) o cubierta (ROOF), con su IsExternal.
Valores tomados de un IFC de referencia de un modelador comercial y de los
requisitos públicos de los generadores de modelo analítico.
"""
import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401  (fixture)
from tests.test_r12_conversion import module
from tests.test_wall_tools import Session, draw

OUTER = [(0, 0), (6, 0), (6, 4), (0, 4)]


def _el(data, cls):
    return [e for e in data['elements'] if e['ifc_class'] == cls]


# --- norte del proyecto ----------------------------------------------------------
def test_el_norte_por_defecto_es_cero(plugin):
    s = Session(plugin)
    assert s.export(None)['project']['north_deg'] == 0.0


@pytest.mark.parametrize('dado, esperado', [(30.0, 30.0), (350.0, -10.0), (-200.0, 160.0)])
def test_el_norte_de_parametrosarq_viaja_normalizado(plugin, dado, esperado):
    s = Session(plugin)
    P = module(s, 'parameters_arq')
    values = P.load_defaults(s.document)
    values['general']['norte'] = dado
    s.history.execute(P.SetArchitecturalDefaults(values))
    assert s.export(None)['project']['north_deg'] == pytest.approx(esperado)
    s.history.undo()
    assert s.export(None)['project']['north_deg'] == 0.0


def test_un_norte_no_numerico_se_rechaza(plugin):
    s = Session(plugin)
    P = module(s, 'parameters_arq')
    values = P.load_defaults(s.document)
    values['general']['norte'] = 'norte'
    with pytest.raises(ValueError, match='norte'):
        P.validate_defaults(values)


# --- tipo de los recintos --------------------------------------------------------
def test_el_recinto_es_internal(plugin):
    s = Session(plugin)
    m = s.tool('MURO')
    m.thickness, m.reference = 0.30, 'eje'
    draw(m, (0, 0), (6, 0), (6, 4), (0, 4), (0, 0))
    s.tool('RECINTO').on_point((3, 2))
    [sp] = _el(s.export(None), 'IfcSpace')
    assert sp['enums'] == {'PredefinedType': 'INTERNAL'}
    assert sp['psets']['Pset_SpaceCommon']['IsExternal'] is False


# --- clase de los forjados -------------------------------------------------------
@pytest.mark.parametrize('clase, tipo, exterior, terreno', [
    ('forjado', 'FLOOR', False, False),
    ('solera', 'BASESLAB', True, True),
    ('cubierta', 'ROOF', True, False),
])
def test_clase_del_forjado_en_la_exportacion(plugin, clase, tipo, exterior, terreno):
    s = Session(plugin)
    S = module(s, 'slabs')
    S.apply_new(s.tool('MURO').ctx, OUTER, slab_kind=clase)
    [slab] = _el(s.export(None), 'IfcSlab')
    assert slab['enums']['PredefinedType'] == tipo
    assert slab['psets']['Pset_SlabCommon']['IsExternal'] is exterior
    assert slab['psets']['ARQ_Forjado']['ContactoTerreno'] is terreno


def test_un_forjado_antiguo_es_forjado_y_una_clase_falsa_se_rechaza(plugin):
    s = Session(plugin)
    S = module(s, 'slabs')
    rec = S.validate({'kind': 'slab', 'id': 'x', 'outer': OUTER, 'holes': [],
                      'base': -0.2, 'thickness': 0.2})
    assert rec['slab_kind'] == 'forjado'
    with pytest.raises(ValueError, match='Clase de forjado'):
        S.validate({**rec, 'slab_kind': 'tejado'})


def test_forjado_por_teclado_elige_la_clase(plugin):
    s = Session(plugin)
    t = s.tool('FORJADO')
    assert t.on_option('s') is True
    for p in OUTER:
        t.on_point(p)
    t.on_enter()
    t.on_enter()
    [slab] = _el(s.export(None), 'IfcSlab')
    assert slab['enums']['PredefinedType'] == 'BASESLAB'


def test_editar_la_clase_conserva_la_identidad_y_se_deshace(plugin):
    s = Session(plugin)
    S = module(s, 'slabs')
    T = module(s, 'slab_tools')
    S.apply_new(s.tool('MURO').ctx, OUTER)
    [e] = [x for x in s.document.doc.modelspace() if (s.meta(x) or {}).get('kind') == 'slab']
    before = s.meta(e)['id']
    values = {'name': 'Solera', 'material': 'Hormigón', 'thickness': 0.15, 'top_offset': 0.0,
              'slab_kind': 'solera'}
    s.history.execute(T.edit_change(s.tool('MURO').ctx, e, values))
    assert s.meta(e)['slab_kind'] == 'solera' and s.meta(e)['id'] == before
    s.history.undo()
    assert S.read(e)['slab_kind'] == 'forjado'


@pytest.mark.parametrize('clase, tipo', [('forjado', 'Forjado 20 cm'), ('solera', 'Solera 20 cm'),
                                         ('cubierta', 'Cubierta plana 20 cm')])
def test_el_forjado_lleva_tipo_para_el_modelo_analitico(plugin, clase, tipo):
    """El generador del modelo analítico agrupa por tipo y lo exige en todos los
    elementos: un forjado sin tipo propio lo recibe por su clase y su canto."""
    s = Session(plugin)
    S = module(s, 'slabs')
    S.apply_new(s.tool('MURO').ctx, OUTER, slab_kind=clase)
    [slab] = _el(s.export(None), 'IfcSlab')
    assert slab['type_name'] == tipo

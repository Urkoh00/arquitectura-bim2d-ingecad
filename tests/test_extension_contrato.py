# SPDX-License-Identifier: GPL-3.0-or-later
"""The IngeTrazo extension checks the whole contract before anything
enters IngeTrazo (independent audit of v1.15, ARQ-AUD-0012, and the
possible finding 26: a space with wall layers), and moves far models the
way IngeTrazo's own importers do (formats/recenter.py: beyond 100 km)."""
import copy

import pytest

from core.commands import History
from core.document import Document

from arquitectura import exchange as E
from arquitectura.architectural_v10 import create_wall
from ingetrazo_ext import arquitectura_bim as X


def contract(dx=0.0, dy=0.0):
    d = Document.new()
    for name in ['ARQ-MUROS', 'ARQ-MUROS3D', 'ARQ-HUECOS3D', 'ARQ-RECINTOS']:
        d.doc.layers.add(name)
    h = History(d)
    for a, b in [((0, 0), (5, 0)), ((5, 0), (5, 4))]:
        h.execute(create_wall((a[0] + dx, a[1] + dy), (b[0] + dx, b[1] + dy), .2, 3))
    return E.build(d.doc)


def test_un_contrato_correcto_pasa():
    data = contract()
    assert X.validate_contract(data) is data


@pytest.mark.parametrize('damage, message', [
    (lambda d: d['elements'][1].update(guid=d['elements'][0]['guid']), 'GlobalId'),
    (lambda d: d['elements'][1].update(id=d['elements'][0]['id']), 'Identificador'),
    (lambda d: d['elements'][0].update(ifc_class='IfcRoof'), 'Clase'),
    (lambda d: d['elements'][0]['faces'].pop(), 'abierto'),
    (lambda d: d['elements'][0].update(volume=-1), 'volumen'),
    (lambda d: d.update(units='mm'), 'Unidades'),
])
def test_contratos_danados_se_rechazan(damage, message):
    data = copy.deepcopy(contract())
    damage(data)
    with pytest.raises(ValueError, match=message):
        X.validate_contract(data)


def test_cada_clase_solo_lleva_lo_suyo():                                 # posible hallazgo 26
    data = copy.deepcopy(contract())
    wall = data['elements'][0]
    space = copy.deepcopy(wall)
    space.update(id='room', guid='0' * 22, ifc_class='IfcSpace', material_layers=[[0.2, 'Ladrillo']])
    space.pop('openings', None)
    data['elements'].append(space)
    with pytest.raises(ValueError, match='material_layers'):
        X.validate_contract(data)


def test_la_definicion_guarda_planta_y_capas():                          # 0014
    data = copy.deepcopy(contract())
    data['elements'][0]['material_layers'] = [[0.2, 'Ladrillo']]
    kept = X.definition(data)['elements'][0]
    assert kept['level'] == data['elements'][0]['level'] and kept['material_layers']


def test_coordenadas_lejanas_con_la_regla_de_ingetrazo():
    assert X.survey_offset(contract()) is None
    assert X.survey_offset(contract(3000, 0)) is None             # 3 km: se queda donde está
    off = X.survey_offset(contract(500000.4, 4200000.7))          # UTM
    assert off == (500000.0, 4200000.0, 0.0)                     # metros enteros, esquina baja


def _door_like(data):
    """A door-class element with pieces (only the contract is checked)."""
    door = copy.deepcopy(data['elements'][0])
    door.update(id='puerta', guid='1' * 22, ifc_class='IfcDoor', name='Puerta')
    door.pop('openings', None)
    door['parts'] = [{'name': 'Marco', 'role': 'frame', 'material': 'Madera', 'volume': 1.0}]
    for f in door['faces']:
        f['part'] = 0
    data['elements'].append(door)
    return door


def test_las_piezas_de_una_carpinteria_se_comprueban():                  # R10, S1
    data = copy.deepcopy(contract())
    door = _door_like(data)
    assert X.validate_contract(data) is data
    assert X.definition(data)['elements'][-1]['parts'][0]['material'] == 'Madera'
    door['faces'][0]['part'] = 3
    with pytest.raises(ValueError, match='pieza inexistente'):
        X.validate_contract(data)
    data = copy.deepcopy(contract())
    data['elements'][0]['parts'] = [{'name': 'Marco'}]
    with pytest.raises(ValueError, match='parts'):
        X.validate_contract(data)



def test_falta_modulo_de_sincronizacion_da_mensaje_claro(tmp_path):
    """Sin _arqbim_sync.py, la importación se detiene antes de tocar nada y dice qué copiar."""
    import importlib.util
    import shutil
    from pathlib import Path
    src = Path(__file__).resolve().parents[1] / "ingetrazo_ext" / "arquitectura_bim.py"
    copia = tmp_path / "arquitectura_bim.py"
    shutil.copy(src, copia)                     # sin su compañero _arqbim_sync.py
    spec = importlib.util.spec_from_file_location("arqbim_sin_sync", copia)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    class App:
        openers = {}
        def add_file_opener(self, suffix, fn): self.openers[suffix] = fn
        def add_menu_action(self, *a, **k): pass
        def document_data(self, default=None): raise AssertionError("no debe leer el documento")

    app = App()
    mod.setup(app)
    with pytest.raises(RuntimeError, match="Falta _arqbim_sync.py"):
        next(iter(app.openers.values()))(str(tmp_path / "x.arqbim"))

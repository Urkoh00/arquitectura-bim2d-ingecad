# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: cadena oficial de recubrimientos; conserva sólidos y registra los límites del IFC.
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session
from tests.escenarios_r27 import modulo
from tests.test_r29_e_pilar_geometria import insertar


CADENA = r'''
import json
from pathlib import Path
import sys
sys.path[:0] = sys.argv[1:3]
import arquitectura_bim as extension
from core.scene import Scene
from formats.igz import save_scene, load_into
from formats.ifc import save_ifc
import ifcopenshell
import ifcopenshell.validate
import ifcopenshell.geom
import ifcopenshell.util.shape
import ifcopenshell.util.element

ruta = Path(sys.argv[3])
contrato = extension.read_contract(str(ruta))
escena = extension.build_scene(contrato)
extension.check_scene(escena, contrato)
save_scene(escena, ruta.with_suffix('.igz'))
leida = Scene()
load_into(leida, ruta.with_suffix('.igz'))
extension.check_scene(leida, contrato)
save_ifc(leida, str(ruta.with_suffix('.ifc')))
modelo = ifcopenshell.open(str(ruta.with_suffix('.ifc')))
registro = ifcopenshell.validate.json_logger()
ifcopenshell.validate.validate(modelo, registro, express_rules=True)
esperados = {elemento['enums']['PredefinedType']: elemento for elemento in contrato['elements']
             if elemento['ifc_class'] == 'IfcCovering'}
resultados = []
for elemento in modelo.by_type('IfcCovering'):
    tipo = str(elemento.PredefinedType)
    geometria = ifcopenshell.geom.create_shape(ifcopenshell.geom.settings(), elemento).geometry
    volumen = abs(ifcopenshell.util.shape.get_volume(geometria))
    cantidades = ifcopenshell.util.element.get_psets(elemento).get('Qto_CoveringBaseQuantities', {})
    esperado = esperados[tipo]
    assert abs(volumen - esperado['quantities']['NetVolume']) < 1e-7, (tipo, volumen)
    resultados.append({'tipo': tipo, 'volumen_geometrico': volumen,
                       'volumen_contrato': esperado['quantities']['NetVolume'],
                       'superficie_contrato': esperado['quantities']['NetArea'],
                       'superficie_ifc': cantidades.get('NetArea'),
                       'host_contrato': esperado['host']})
salida = {'errores_express': len(registro.statements), 'recubrimientos': resultados,
          'relaciones_ifc_con_el_pilar': len(modelo.by_type('IfcRelCoversBldgElements'))}
ruta.with_suffix('.resultado.json').write_text(json.dumps(salida, indent=2) + '\n')
print(json.dumps(salida))
assert not registro.statements, registro.statements
assert set(esperados) == {resultado['tipo'] for resultado in resultados} == {'CLADDING', 'INSULATION'}
'''


@pytest.mark.skipif(not os.environ.get('INGETRAZO_SRC'), reason='requiere las fuentes del IngeTrazo vigente')
def test_cadena_oficial_recubrimientos_igz_ifc(plugin, tmp_path):
    sesion = Session(plugin)
    insertar(sesion, plugin, insulation_mode='con', insulation_thickness=0.05)
    ruta = tmp_path / 'recubrimientos.arqbim'
    modulo(plugin, 'exchange').write(sesion.document.doc, str(ruta))
    extension = str(Path(__file__).resolve().parents[1] / 'ingetrazo_ext')
    resultado = subprocess.run([sys.executable, '-I', '-c', CADENA,
                               os.environ['INGETRAZO_SRC'], extension, str(ruta)],
                              capture_output=True, text=True, timeout=240,
                              env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'})
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    informe = json.loads(resultado.stdout.strip().splitlines()[-1])
    assert informe['errores_express'] == 0
    # No se certifican las superficies ni la asociación si el escritor las omite.
    # Sus valores se guardan en el informe para la propuesta al anfitrión.
    assert {e['tipo'] for e in informe['recubrimientos']} == {'CLADDING', 'INSULATION'}

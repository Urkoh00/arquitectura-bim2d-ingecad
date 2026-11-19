# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: verifica huecos, relaciones, posiciones y volumen neto del consumidor.
import importlib.util
import json
import math
from pathlib import Path
import sys

import numpy as np
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element as elementos
import ifcopenshell.util.placement as colocaciones
import ifcopenshell.util.shape as formas
import ifcopenshell.validate


def verificar(carpeta):
    ruta = Path(__file__).resolve().parents[1] / 'ingetrazo_ext/arquitectura_bim.py'
    especificacion = importlib.util.spec_from_file_location('extension_arq', ruta)
    extension = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(extension)
    contrato, escena, solidos = extension.to_igz(
        carpeta / 'modelo_sintetico.arqbim', carpeta / 'modelo_sintetico.igz')
    from formats.ifc import save_ifc
    salida = carpeta / 'modelo_sintetico.ifc'
    save_ifc(escena, salida)
    modelo = ifcopenshell.open(str(salida))
    registro = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate(str(salida), registro, express_rules=True)
    assert not registro.statements, registro.statements
    origen = np.array(extension.survey_offset(contrato) or (0., 0., 0.))
    opciones = ifcopenshell.geom.settings()
    opciones.set(opciones.USE_WORLD_COORDS, True)
    sin_restar = ifcopenshell.geom.settings()
    sin_restar.set(sin_restar.USE_WORLD_COORDS, True)
    sin_restar.set('disable-opening-subtractions', True)
    etiquetas = {grupo.ifc['guid']: grupo.ifc for grupo in escena.groups}
    anfitriones = []
    huecos = []
    carpinterias = []
    por_guid = {objeto.GlobalId: objeto for objeto in modelo.by_type('IfcProduct')}
    for elemento in contrato['elements']:
        objeto = por_guid[elemento['guid']]
        if elemento['ifc_class'] in ('IfcWall', 'IfcSlab'):
            volumen_contrato = elemento['quantities']['NetVolume']
            forma_lector = ifcopenshell.geom.create_shape(opciones, objeto)
            forma_brep = ifcopenshell.geom.create_shape(sin_restar, objeto)
            volumen_lector = formas.get_volume(forma_lector.geometry)
            volumen_brep = formas.get_volume(forma_brep.geometry)
            assert math.isclose(volumen_lector, volumen_contrato, rel_tol=1e-5, abs_tol=1e-5)
            assert math.isclose(volumen_lector, volumen_brep, rel_tol=1e-5, abs_tol=1e-5)
            anfitriones.append({'nombre': elemento['name'], 'volumen_contrato': volumen_contrato,
                                'volumen_brep_ya_cortado': volumen_brep,
                                'volumen_aplicando_huecos': volumen_lector})
        if elemento['ifc_class'] in ('IfcDoor', 'IfcWindow') and elemento.get('fills'):
            hueco = modelo.by_guid(elemento['fills'])
            assert elementos.get_filled_void(objeto) == hueco
            assert objeto.ObjectPlacement.PlacementRelTo == hueco.ObjectPlacement
            forma = ifcopenshell.geom.create_shape(opciones, objeto)
            geometria = forma.geometry
            vertices = np.array(geometria.verts).reshape(-1, 3)
            originales = np.array([punto for cara in elemento['faces']
                                   for punto in cara['outer']]) - origen
            error = max(min(np.linalg.norm(punto - original) for original in originales)
                        for punto in vertices)
            assert error < 1e-5, (elemento['name'], error)
            carpinterias.append({'nombre': elemento['name'], 'hueco': hueco.GlobalId,
                                  'error_maximo_vertices': error,
                                  'matriz_mundial': colocaciones.get_local_placement(
                                      objeto.ObjectPlacement).tolist()})
        for fuente in elemento.get('openings', []):
            hueco = modelo.by_guid(fuente['guid'])
            assert elementos.get_voided_element(hueco) == objeto
            assert elementos.get_container(hueco, should_get_direct=True) is None
            assert not hueco.ContainedInStructure
            assert hueco.ObjectPlacement.PlacementRelTo == objeto.ObjectPlacement
            representacion = hueco.Representation.Representations[0]
            forma = ifcopenshell.geom.create_shape(opciones, hueco)
            geometria = forma.geometry
            vertices = np.array(geometria.verts).reshape(-1, 3)
            originales = np.array([punto for cara in fuente['faces']
                                   for punto in cara['outer']]) - origen
            error = max(min(np.linalg.norm(punto - original) for original in originales)
                        for punto in vertices)
            assert error < 1e-5, (fuente['name'], error)
            etiqueta = next(dato for dato in etiquetas[elemento['guid']]['openings']
                            if dato['guid'] == fuente['guid'])
            cantidades = elementos.get_psets(hueco, qtos_only=True)[
                'Qto_OpeningElementBaseQuantities']
            for nombre, valor in etiqueta['quantities'].items():
                assert math.isclose(cantidades[nombre], valor, rel_tol=1e-12, abs_tol=1e-12)
            assert hueco.PredefinedType == etiqueta['predefined']
            fila = {'nombre': fuente['name'], 'guid': hueco.GlobalId,
                    'anfitrion': elemento['name'], 'predefined': hueco.PredefinedType,
                    'geometria': representacion.RepresentationType,
                    'cantidades': {nombre: cantidades[nombre] for nombre in etiqueta['quantities']},
                    'carpinterias': [rel.RelatedBuildingElement.Name for rel in hueco.HasFillings],
                    'limite_mundial_minimo': vertices.min(axis=0).tolist(),
                    'limite_mundial_maximo': vertices.max(axis=0).tolist(),
                    'error_maximo_vertices': error,
                    'matriz_mundial': colocaciones.get_local_placement(
                        hueco.ObjectPlacement).tolist()}
            if representacion.RepresentationType == 'SweptSolid':
                fila['profundidad_geometrica'] = representacion.Items[0].Depth
            huecos.append(fila)
    assert len(huecos) == len(modelo.by_type('IfcOpeningElement'))
    assert len(huecos) == len(modelo.by_type('IfcRelVoidsElement'))
    assert len(carpinterias) == len(modelo.by_type('IfcRelFillsElement'))
    resumen = {'errores_express': 0, 'desplazamiento_escena': origen.tolist(),
               'consumidor': 'IfcOpenShell geom; sustracciones activadas y desactivadas',
               'anfitriones': anfitriones, 'huecos': huecos,
               'carpinterias': carpinterias, 'solidos_igz': solidos,
               'avisos_de_origen': contrato.get('issues', [])}
    (carpeta / 'comprobacion.json').write_text(
        json.dumps(resumen, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(carpeta.name, '0 errores EXPRESS;', len(huecos), 'huecos;',
          len(carpinterias), 'rellenos; volúmenes netos conservados')


if __name__ == '__main__':
    verificar(Path(sys.argv[1]).resolve())

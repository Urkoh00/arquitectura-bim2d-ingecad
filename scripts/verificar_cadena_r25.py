# Resumen: contrasta ejes, capas y volúmenes con el lector geométrico independiente.
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
    desplazamiento = np.array(extension.survey_offset(contrato) or (0., 0., 0.))
    opciones = ifcopenshell.geom.settings()
    opciones.set(opciones.USE_WORLD_COORDS, True)
    comprobaciones = []
    por_guid = {objeto.GlobalId: objeto for objeto in modelo.by_type('IfcProduct')}
    for elemento in contrato['elements']:
        objeto = por_guid[elemento['guid']]
        forma = ifcopenshell.geom.create_shape(opciones, objeto)
        volumen = formas.get_volume(forma.geometry)
        previo = next(fila[3] for fila in solidos if fila[1] == elemento['id'])
        assert math.isclose(volumen, previo, rel_tol=1e-5, abs_tol=1e-5)
        fila = {'nombre': elemento['name'], 'volumen_contrato': previo,
                'volumen_ifc_geom': volumen}
        if elemento['ifc_class'] == 'IfcWall':
            parametros = elemento['params']
            inicio = np.array([*parametros['a'], parametros['base']]) - desplazamiento
            final = np.array([*parametros['b'], parametros['base']]) - desplazamiento
            direccion = final - inicio
            longitud = np.linalg.norm(direccion[:2])
            direccion /= longitud
            normal = np.array([-direccion[1], direccion[0], 0.])
            matriz = colocaciones.get_local_placement(objeto.ObjectPlacement)
            assert np.allclose(matriz[:3, 3], inicio, atol=1e-6, rtol=0)
            assert np.allclose(matriz[:3, 0], direccion, atol=1e-9)
            assert np.allclose(matriz[:3, 1], normal, atol=1e-9)
            etiqueta = next(grupo.ifc for grupo in escena.groups
                            if grupo.ifc['guid'] == elemento['guid'])
            assert np.allclose(etiqueta['axis']['start'], inicio, atol=1e-9)
            assert np.allclose(etiqueta['axis']['end'], final, atol=1e-9)
            uso = elementos.get_material(objeto)
            limites = [uso.OffsetFromReferenceLine]
            for capa in uso.ForLayerSet.MaterialLayers:
                limites.append(limites[-1] + capa.LayerThickness)
            vertices = np.array(forma.geometry.verts).reshape(-1, 3)
            originales = np.array([punto for cara in elemento['faces']
                                   for punto in cara['outer']]) - desplazamiento
            error = max(min(np.linalg.norm(punto - original) for original in originales)
                        for punto in vertices)
            assert error < 1e-5, error
            # En los encuentros a inglete no todas las caras son paralelas al eje.
            # Se contrastan los vértices completos; las interfaces se expresan como
            # planos (origen y normal) en el mismo sistema que el dibujo.
            espesor = parametros['thickness']
            referencia = parametros['reference']
            desfase_dibujo = {'eje': -espesor / 2, 'izquierda': 0.,
                             'derecha': -espesor}[referencia]
            capas_dibujo = elemento.get('material_layers') or [{'thickness': espesor}]
            limites_dibujo = [desfase_dibujo]
            for capa in capas_dibujo:
                limites_dibujo.append(limites_dibujo[-1] + capa['thickness'])
            assert np.allclose(limites, limites_dibujo, atol=1e-9)
            planos = []
            for limite_ifc, limite_dibujo in zip(limites, limites_dibujo):
                punto_ifc = (matriz @ [0., limite_ifc, 0., 1.])[:3]
                punto_dibujo = inicio + limite_dibujo * normal
                assert np.allclose(punto_ifc, punto_dibujo, atol=1e-6, rtol=0)
                planos.append(punto_ifc.tolist())
            eje = next(rep for rep in objeto.Representation.Representations
                       if rep.RepresentationIdentifier == 'Axis')
            assert math.isclose(eje.Items[0].Points[1].Coordinates[0], longitud)
            fila.update(eje_x=matriz[:3, 0].tolist(), eje_y=matriz[:3, 1].tolist(),
                        desplazamiento=uso.OffsetFromReferenceLine,
                        interfaces_capas=planos, normal_interfaces=normal.tolist(),
                        error_maximo_vertices=error)
        comprobaciones.append(fila)
    resumen = {'errores_express': 0, 'desplazamiento_escena': desplazamiento.tolist(),
               'consumidor': 'IfcOpenShell geom, USE_WORLD_COORDS',
               'elementos': comprobaciones}
    (carpeta / 'comprobacion.json').write_text(
        json.dumps(resumen, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(carpeta.name, '0 errores EXPRESS;', len(comprobaciones), 'volúmenes comprobados')


if __name__ == '__main__':
    verificar(Path(sys.argv[1]).resolve())

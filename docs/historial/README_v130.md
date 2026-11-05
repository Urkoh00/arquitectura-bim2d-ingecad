# Arquitectura para IngeCAD — v1.3.0 (experimental)

## Cambios
- `MURO`: cada tramo nuevo es una **LWPOLYLINE ABIERTA** de dos vértices, eje o línea de referencia, con XDATA `ARQINGECAD` y un ID BIM único. No se crean dos huellas independientes.
- `ARQ-MUROS3D` conserva la referencia fuente (oculta durante la regeneración); `ARQ-MUROS` contiene segmentos derivados para la representación en planta, con referencias `wall_ids`. Estas líneas **no son objetos BIM independientes**.
- `PARAMETROSARQ`: cuadro Qt que guarda parámetros iniciales **por dibujo** mediante XRECORD `ARQUITECTURA_PARAMETROS` dentro del diccionario raíz DXF. Se conserva tras guardar/reabrir. La modificación es deshacible y NO modifica elementos existentes.
- Los diálogos de `MURO` y `PILAR` arrancan con los nuevos valores. Puertas y ventanas almacenan valores iniciales previstos, sin retomar todavía su desarrollo.
- `ARQMIGRAR`: conversión voluntaria de registros de muro antiguos (`POINT` o huella poligonal cerrada) a eje abierto. Antes de usarla, guardar una copia DXF.

## Valores iniciales (modificables)
- Muros: 0,30 m espesor; 2,70 m altura; cota 0; referencia Eje. Clase BIM prevista: `IfcWall`.
- Pilares: rectangulares 0,30 × 0,30 m; radio alternativo 0,15 m; altura 2,70 m. Clase BIM prevista: `IfcColumn`.
- Puertas (reservado): 0,90 × 2,10 m; antepecho 0.
- Ventanas (reservado): 1,20 × 1,20 m; antepecho 1,00 m.
- Los valores numéricos se interpretan en **unidades de dibujo**, cuya correspondencia con metros debe verificarse mediante UNITS. No se ha implementado conversión automática.

## Prueba recomendada
1. Crear un DXF nuevo; `ARQDIAG` debe mostrar 1.3.0.
2. `PARAMETROSARQ`: ajustar el espesor de muro a 0,30 m, aceptar, guardar DXF, cerrar y reabrir. Comprobar que persiste.
3. `MURO`: confirmar la ficha inicial y dibujar dos tramos. Comprobar contornos y `PROPIEDADESARQ` en un tramo exterior no ambiguo.
4. `PILAR`: comprobar los valores iniciales de su cuadro y modificar la forma.
5. Deshacer y Rehacer sobre el dibujo nuevo. Verificar persistencia XDATA con `ARQVALIDAR`.
6. En una **copia** de un dibujo anterior, ejecutar `ARQMIGRAR` y `UNIONESARQ`.

## Limitaciones
- Encuentros en L/T/X: algoritmo de contorno heredado, aún no resuelto para tolerancias, prolongaciones automáticas ni todos los casos CAD reales.
- Los segmentos visibles continúan siendo líneas DXF derivadas y no una entidad compuesta nativa en el panel Propiedades.
- La operación de selección/modificación sobre contornos ambiguos sigue siendo limitada.
- Sin validación GUI en IngeCAD Windows ni verificación de extremo a extremo IGZ → IFC.
- `PARAMETROSARQ` afecta solo a nuevos elementos. No debe utilizarse para cambiar los espesores de muros ya existentes.

## Pruebas ejecutadas
- 5 pruebas nuevas con ezdxf y dobles de la API de IngeCAD (valores, guardado, deshacer, eje 2D, edición y migración).
- 5 pruebas de regresión heredadas de la v1.2.2, superadas.
- Compilación de todos los módulos con `compileall`.
- **NO** se ha ejecutado el cuadro Qt (PySide6 no está instalado en el entorno de pruebas).

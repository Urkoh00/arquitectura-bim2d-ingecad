# Arquitectura para IngeCAD 1.5.0 — experimental

Fecha: 2026-11-04. Basada en el ZIP v1.4.2 facilitado en el proyecto.

## Cambios

1. **Encuentros de muros:** `joined_wall_sources` calcula prolongaciones de los extremos en L y T para ejes que formen un ángulo superior a 12° respecto al paralelismo. Usa la cara remota del muro anfitrión, su espesor y referencia (eje/izquierda/derecha), sin trasladar los ejes de origen ni forzar uniones entre muros separados. Los cruces X se obtienen mediante la unión de las huellas y recorte de las aristas interiores. Conserva `UNIONESARQ`.
2. **Pilares BIM:** nuevas secciones `hex` y `oct`, con radio circunscrito en metros y giro en grados. Se añaden al diálogo `PILAR`, edición `PROPIEDADESARQ` y valores por defecto de `PARAMETROSARQ`. Los valores anteriores siguen siendo válidos.
3. **IGZ:** DXF e IGZ comparten generador puro de secciones poligonales (`sections.py`). El puente sigue utilizando `Scene`, `Mesh`, `Group`, `save_scene` OFICIALES de IngeTrazo. Ahora relee el archivo con `load_into` y verifica número, identificadores BIM, clases y geometrías antes de considerarlo exportado. El fichero final se publica solo tras superar esta verificación.
4. **Iconos:** el ZIP de iconos contiene 7 SVG editables tal como estaban en v1.4.2. No se ha modificado su estilo.

## Limitaciones comprobadas

- Las uniones 2D no realizan una booleana 3D. Los sólidos de muros contiguos pueden solaparse en IGZ. No se considera resuelto el modelo BIM constructivo en los encuentros.
- El algoritmo no realiza un ajuste de ejes separados; tampoco resuelve encuentros casi paralelos (menos de 12°) ni paredes curvas.
- Los polígonos hexagonal y octogonal son **regulares**, definidos por radio a vértice y giro, no por distancia entre caras. No hay sección irregular.
- Los datos `group.ext.arquitectura` se conservan en IGZ. El exportador IFC actual de IngeTrazo NO convierte automáticamente todos esos campos en `IfcPropertySet`, ni construye relaciones IFC de uniones/huecos.
- Para `CONFIGIGZ` se precisa la carpeta del código fuente de IngeTrazo y su Python con PySide6. Un `.exe` portable por sí solo no cumple esos requisitos. El adaptador no copia ni reimplementa el formato IGZ.
- **No probado en Windows real con IngeCAD 0.7.0 ni ejecutado con un IngeTrazo real en este entorno**. La verificación de reapertura IGZ queda pendiente del entorno de la instalación del usuario.

## Pruebas realizadas

11 pruebas locales sobre la geometría y datos; ejecutadas con `pytest` y `shapely` únicamente como comprobador geométrico de referencia (NO son dependencias del plugin). Incluyen casos ortogonales y oblicuos L/T/X, muros de espesores desiguales, secciones de 4/6/8/48 lados, validación de PARAMETROSARQ, el DXF real `36.dxf`, extracción de elementos de `34.dxf`, y formación de diez grupos BIM independientes mediante una simulación de los objetos Qt/IngeTrazo. Esa simulación no equivale a una validación del serializador real.

## Secuencia de prueba en Windows

1. Guardar una copia del DXF, desactivar plugin previo e instalar 1.5.0. Reiniciar IngeCAD y ejecutar `ARQDIAG` (debe indicar **1.5.0**).
2. Ejecutar `PARAMETROSARQ`, sección Pilares: elegir «Hexagonal regular», radio 0,20 m, giro 0°. Ejecutar `PILAR`, marcar centro. Repetir con «Octogonal regular», giro 22,5°. Comprobar `PROPIEDADESARQ`, guardar y reabrir.
3. Crear L, T y X con espesores 0,30 y 0,45 m. Añadir encuentro a 45°. Ejecutar `UNIONESARQ` y verificar las esquinas exteriores e interiores, deshacer y rehacer.
4. Instalar IngeTrazo junto con su código fuente y dependencias Python. Ejecutar `CONFIGIGZ`, seleccionar raíz con `formats/igz.py` y Python correspondiente; ejecutar `EXPORTARIGZ` y abrir el resultado en IngeTrazo.
5. Comprobar en IngeTrazo cada grupo (`IfcWall`/`IfcColumn`), su `source_id` y la conservación de `group.ext.arquitectura`. La posterior exportación IFC es una prueba independiente.

No ejecutar `ARQMIGRAR` en el original: usar una copia.

# Arquitectura IngeCAD v1.4.0 — Exportación IGZ de muros y pilares

Versión experimental; se basa en v1.3.2 y conserva sus herramientas de dibujo.

## Arquitectura de la exportación

- **Origen**: DXF de IngeCAD. Se leen solo entidades con XDATA `ARQINGECAD` (`kind=wall`/`column`), no líneas regeneradas `junction_edge`.
- **Intercambio**: especificación JSON temporal en metros.
- **Salida**: proceso independiente ejecutado bajo el entorno de IngeTrazo. Reutiliza `core.scene.Scene`, `core.group.Group`, `core.mesh.Mesh` y `formats.igz.save_scene` de **IngeTrazo**, sin reimplementar su escritor.
- **Muros**: grupos separados `IfcWall`, prismas según eje, referencia, espesor, cota y altura; huecos del registro antiguo se subdividen en prismas, sin una operación booleana definitiva.
- **Pilares**: grupos separados `IfcColumn`, sección rectangular o poligonal de 48 lados para sección circular.
- **Identidad**: `group.ext['arquitectura']['source_id']` guarda el identificador del DXF. `group.ifc` guarda clase y nombre IFC. `group.ext` guarda material, nivel, dimensiones y tipo.
- **Precaución**: `group.ext` se conserva en IGZ, pero la versión inspeccionada del escritor IFC de IngeTrazo no vuelca automáticamente esas propiedades a IfcPropertySet. La geometría de encuentros muro-muro/muro-pilar NO se fusiona en 3D. No se generan puertas y ventanas BIM independientes.

## Configuración y uso en Windows

1. Sustituye la extensión anterior por esta versión y reinicia IngeCAD. Ejecuta `ARQDIAG`, que debe indicar **1.4.0**.
2. Ejecuta `CONFIGIGZ` (menú Arquitectura > Intercambio 3D) e indica:
   - **Carpeta del código fuente de IngeTrazo**: debe contener `formats/igz.py` y `core/scene.py`.
   - **Python IngeTrazo**: ruta completa a `python.exe` de un entorno donde `import PySide6` y las dependencias de IngeTrazo funcionen. El `.exe` empaquetado de IngeTrazo **no equivale** a este intérprete.
   - Se guardan localmente en QSettings, no en el DXF. También pueden configurarse con `INGETRAZO_ROOT` e `INGETRAZO_PYTHON`.
3. Abre un DXF con muros/pilares BIM, por ejemplo `34.dxf`. Ejecuta `EXPORTARIGZ` o elige Exportar modelo IGZ en el menú.
4. Selecciona la ruta de destino. El programa muestra recuento de muros y pilares y no conserva un archivo parcial si el escritor falla.
5. Abre el archivo con **esa misma versión del código de IngeTrazo** y verifica que el árbol contiene objetos `IfcWall` e `IfcColumn`. Revisa las propiedades BIM e intenta exportar a IFC, recordando las limitaciones anteriores.

## Unidades y seguridad

`$INSUNITS=6` (metros) es compatible. En un dibujo con `$INSUNITS=0`, se advierte que se interpretan las coordenadas como metros. Con centímetros, milímetros u otra unidad declarada, se detiene la exportación para evitar errores silenciosos de escala. El origen DXF no se modifica.

## Pruebas realizadas

- `34.dxf` se lee como **4 muros y 6 pilares**, con 10 IDs únicos.
- Pruebas aisladas de la creación de escena con módulos simulados: muros+pilares, solo muros, solo pilares, altura/posición: **4/4**.
- Sintaxis Python e integridad del ZIP comprobadas.
- **Pendiente**: ejecución real del escritor oficial y apertura IGZ desde IngeTrazo en Windows; no se declara interoperabilidad IFC completa.

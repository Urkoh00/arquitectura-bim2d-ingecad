# Arquitectura para IngeCAD — 1.1.0 EXPERIMENTAL

## Interfaz gráfica coherente con IngeCAD e IngeTrazo

- Cuadros de diálogo nativos PySide6 (`QDialog`, `QFormLayout`, `QGroupBox`, `QDoubleSpinBox`, `QDialogButtonBox`), con tema Qt heredado de IngeCAD, sin CSS propio.
- Iconos SVG originales de 24 × 24 píxeles: trazo claro y acento azul, estilo de dibujo lineal comparable al de `views/icons.py` de IngeCAD.
- Mantiene **entrada por comandos** cuando no hay aplicación Qt o ventana anfitriona; no sustituye el motor CAD.
- `MURO` abre la ficha antes de dibujar y reutiliza los parámetros durante toda la secuencia.
- `PUERTAARQ` y `VENTANAARQ` solicitan primero el muro; después abren una ficha con dimensiones y datos BIM.
- `EDITARARQ` abre la ficha correspondiente al elemento seleccionado y ejecuta la edición por comandos deshacibles.

## Datos conservados

Muros: nombre, tipo, material, nivel, espesor, altura, cota, cara de referencia, identificador interno y clase IFC prevista.

Carpinterías: nombre, tipo, material, operación de apertura, anchura, altura, antepecho, distancia de inserción, identificador y vínculo al muro.

Se guardan en XDATA del DXF. El puente IGZ guarda los datos de **muros** en `group.ext['arquitectura']` y los identifica como `IfcWall` mediante `group.ifc`. Los datos de **huecos** se guardan dentro de la extensión del muro anfitrión, pero aún no son objetos `IfcDoor` / `IfcWindow` independientes en el IGZ.

## Límites conocidos (no confundir con BIM terminado)

1. Los iconos y fichas se han desarrollado, pero no se han ejecutado dentro de IngeCAD para Windows: falta validación visual y funcional con el usuario.
2. Los encuentros L/T/X no tienen aún una unión booleana de contornos.
3. Los huecos no recortan físicamente los paramentos de planta del DXF, aunque el puente 3D genera segmentos macizos alrededor de ellos.
4. `formats/ifc.py` de IngeTrazo aún no convierte automáticamente todos los parámetros de `group.ext` en `IfcPropertySet` ni representa las relaciones `IfcRelVoidsElement` / `IfcRelFillsElement`.
5. No se certifica compatibilidad integral IGZ→IFC: se necesita ejecutar y comprobar el proceso con el entorno real de IngeTrazo.
6. Las dimensiones se expresan en metros, como en la versión 1.0; no se ha implementado todavía conversión automática desde unidades distintas en DXF.

## Fuentes de diseño y API

- https://github.com/ingelibre/ingecad/blob/main/views/icons.py
- https://github.com/ingelibre/ingecad/blob/main/views/units_dialog.py
- https://github.com/ingelibre/ingecad/blob/main/views/qselect_dialog.py
- https://github.com/ingelibre/ingecad/blob/main/docs/plugins.md
- https://github.com/ingelibre/ingetrazo/blob/main/views/preferences_dialog.py
- https://github.com/ingelibre/ingetrazo/blob/main/formats/igz.py
- https://github.com/ingelibre/ingetrazo/blob/main/formats/ifc.py

## Primera prueba en IngeCAD

1. Copiar por seguridad la carpeta de plugin anterior.
2. Instalar o sustituir la extensión desde **Herramientas → Gestionar extensiones**.
3. Ejecutar `MURO`, aceptar los parámetros y dibujar al menos dos puntos.
4. Ejecutar `PUERTAARQ` y seleccionar un muro creado con `MURO`.
5. Ejecutar `EDITARARQ` y cambiar el tipo, material o alguna dimensión.
6. Guardar y volver a abrir el DXF. Comprobar los cambios y las opciones de Deshacer.

La generación de IGZ requiere todavía el entorno y las dependencias de IngeTrazo indicadas en el README anterior.

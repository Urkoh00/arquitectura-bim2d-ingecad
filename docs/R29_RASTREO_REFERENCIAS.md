# R29-F — rastreo nativo de referencias

La interacción de colocar puntos utiliza el OTRACK de IngeCAD 0.8.0. No se
mantiene un rastreador del plugin ni se añaden puntos o líneas al modelo para
simular referencias. Esta revisión no modifica IngeCAD ni IngeTrazo.

## Fases de cada orden

| Orden | Designación de un objeto | Colocación con referencias |
| --- | --- | --- |
| MURO, MUROCURVO | Elección del tipo por texto | Puntos de trazado |
| MUROPARALELO | Línea base inicial | Lado, cuerpo y lado de paralelas sucesivas |
| ESTIRAMURO, PIVOTAMURO | Muro y extremo | Nuevo extremo |
| PILAR | — | Centro |
| CARPINTERIA | El mismo punto determina muro y jamba | Jamba y dirección de apertura |
| MOVERCARP | Carpintería existente | Nuevo emplazamiento |
| ARMARIOBIM | El mismo punto determina muro y frente | Frente y cara de acceso |
| RECINTO | — | Punto interior |
| FORJADO | — | Vértices |

`entity_picker` indicaba selección pura durante toda la orden en cinco casos.
El controlador nativo omite referencias y OTRACK cuando esa propiedad es cierta.
Ahora solo se mantiene en las fases de designación de objetos. La jamba de una
carpintería o el frente de un armario son posiciones, aunque el punto también
determine el muro. Se conservan las órdenes geométricas, las identidades y las
transacciones existentes. PIVOTAMURO comparte la corrección con ESTIRAMURO.

## Prueba de comportamiento

`tests/ventana_otrack_r29.py` construye un dibujo sintético con las órdenes
reales y abre MainWindow. Acepta las fichas por su botón, escribe las respuestas
de preparación, pulsa F11 y detiene el cursor sobre un extremo de cara. Después
mueve el cursor cerca de su alineación, captura la guía y hace clic. Un observador
registra el punto recibido y llama al método original sin cambiarlo.

Se comprueban la adquisición, la guía nativa, la diferencia entre el cursor y el
punto alineado, el punto entregado, la conservación de identidades y referencias
a muro/nivel y un Deshacer/Rehacer exacto. Se completa la operación, no se da por
terminada por ver un indicador. La batería usa Qt sin servidor de ventanas; el
mismo guion se recorre en X11 para capturar el resultado visible.

## Extremos de caras y ejes

Los ejes de MURO son polilíneas DXF reales, autoritativas, con sus extremos y
curvatura. Aunque su representación esté oculta, el motor de referencias de
IngeCAD 0.8.0 los indexa. Se ensaya por separado el extremo de una cara y el del
eje, sin encender capas, cambiar su visibilidad ni añadir entidades auxiliares.

Revisión de la API y del recorrido nativo:

- `tools/base.py`: `entity_picker` controla selección frente a entrada de puntos.
  `extra_osnaps()` añade modos nativos, no coordenadas aportadas por el plugin.
- `core/plugins.py`: `PluginSpec` admite controladores de pinzamientos, sin un
  proveedor adicional de puntos para OTRACK.
- `core/snap.py`: `SnapEngine` obtiene los extremos de las entidades DXF reales.
- `views/tool_controller.py`: el controlador adquiere por pausa y resuelve la
  alineación. La primera construcción asíncrona de las cachés puede inhibir la
  búsqueda al abrir el dibujo: se espera antes de iniciar cada ensayo.

No hace falta implantar un proveedor de puntos ni sustituir el rastreador para
este caso en 0.8.0. La comprobación del eje se hace con el mismo guion que la de
las caras, completando la operación y su Deshacer/Rehacer. Esta observación
se limita a la versión ensayada y al modelo sintético: no se extiende una API
interna ni se añade código de compatibilidad para otras versiones.

No se ha modificado IngeCAD o IngeTrazo ni comunicado nada a terceros.
No se ha usado ninguna biblioteca de SketchUp.

## Texto propuesto para el manual

Pulse F11 para activar o desactivar el rastreo de referencias. Si no aparece
OTRACK en la barra de estado, abra su menú de personalización (botón ≡ o botón
derecho sobre la barra) y muestre esa opción. Detenga un momento el cursor sobre
un extremo visible: aparece una marca de adquisición. Al alejarse siguiendo su
alineación aparece una guía discontinua; el clic coloca el punto sobre ella.
Las fases de seleccionar un objeto mantienen el cursor libre. Después de
designarlo, las fases de colocar puntos admiten el rastreo.

Se pueden adquirir extremos de caras y de los ejes BIM. Al abrir un dibujo,
espere a que termine su preparación antes de tomar las referencias.
Activar OTRACK no enciende capas ni altera el modelo.

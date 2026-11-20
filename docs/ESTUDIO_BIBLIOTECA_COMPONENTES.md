# Biblioteca de componentes — propuesta de diseño R28-C

Revisado el 21-11-2026 según la adenda. Plugin v1.46.0-dev `78c528b`; IngeCAD 0.8.0 `32a15cb`;
IngeTrazo 0.6.2.1 `8dbed761`. **Solo estudio: no se registra COMPONENTE ni se
integran bibliotecas, mallas o símbolos nuevos en esta entrega parcial.**

## 1. Flujo y relación con las herramientas actuales

El componente propuesto tiene una definición propia y una instancia colocada.
La definición contiene planta, cuerpo 3D, unidades, ejes, parámetros y licencia;
la instancia contiene identidad, referencia a la definición, transformación y
alojamiento. Cambiar un tamaño o una mano debe afectar a las dos representaciones.
Si se cambia una medida física, la planta y la malla deben responder al mismo parámetro. La simplificación gráfica del símbolo 2D puede editarse sin alterar la pieza 3D: no se confunde la extensión de trazos o textos con su huella física.

La documentación pública de la herramienta comercial de arquitectura confirma
un flujo de categorías, elementos genéricos y biblioteca de usuario. Se toma solo
esa idea funcional; no se descarga ni copia ningún objeto, bloque, imagen,
miniatura o texto de su catálogo. [Referencia funcional pública](https://info.cype.com/es/tema/cype-architecture-introduccion-de-muebles-electrodomesticos-y-otros-elementos/).
Se ha leído el manual 2015 recibido por separado (19 páginas), especialmente los capítulos 6 y 7. El vídeo no se ha recibido por separado ni se ha examinado. El manual y su extracción quedan fuera de la entrega.

El recorrido propuesto es: elegir categoría o buscar; seleccionar definición;
previsualizar planta; elegir nivel, elevación y alojamiento; girar o cambiar mano;
colocar y repetir. Esc cancela sin dejar una definición importada a medias.
`-COMPONENTE` pregunta los mismos valores mediante `linea_campos` y pasa a la misma
herramienta de colocación, sin paletas ni selectores de archivo.

### Contraste funcional con el manual recibido

El capítulo 6 distingue carpinterías alojadas en muro de componentes generales del capítulo 7. En ambos casos el origen y los ejes condicionan la colocación; no basta con importar un fichero que se vea bien. El capítulo 7 permite modificar el símbolo de planta sin redibujar el cuerpo. El capítulo 10 muestra la importancia de mantener la asociación del conjunto al alternar representaciones.

| Función observada | Traducción propuesta para el plugin |
|---|---|
| Origen que corresponde al apoyo del objeto | Plano de apoyo explícito, origen y base ortonormal validados |
| Elección previa de los ejes | Paso de autoría con vista simultánea 2D/3D, sin depender de colores de ejes del programa de referencia |
| Inserción con previsualización | Misma herramienta de puntos de IngeCAD y confirmación transaccional |
| Elevación independiente de la altura de la pieza | Nivel + desfase; el alto del objeto permanece como otro parámetro |
| Edición de la representación de planta | Símbolo 2D personalizable y huella física separada; el símbolo no se extruye para inventar el cuerpo |
| Asociación entre representaciones | Identidad de instancia y definición conservadas al editar/copiar/guardar |

El flujo de consulta o importación de una galería que aparece en el manual no se adopta: la distribución propuesta usa contenido propio o libre con licencia comprobada. La necesidad del programa de referencia de agrupar el dibujo para alternar 2D/3D tampoco se traslada como requisito artificial: aquí ya existe una fuente BIM persistente y un contrato de sólidos. No se reproducen sus símbolos, capturas, teclas ni ejemplos de producto.

## 2. Lo que ya permite Palette en IngeCAD

La pestaña Palette de 0.8.0 es `views/styles_panel.py::StylesPanel`, insertada en
la barra lateral por `views/main_window.py`. Tiene categorías de texto, cotas,
tramas y bloques. La categoría BLOCK lista los bloques del dibujo con miniatura,
se actualiza y permite iniciar su inserción. Las pruebas
`tests/test_palette_blocks.py` comprueban miniaturas e inserción sin diálogo.

Es una base útil para símbolos 2D, pero **no se ha encontrado una API pública para
registrar un proveedor de componentes con malla, categorías y parámetros de
alojamiento**. Las propiedades de `PluginSpec` y `PluginContext.toolbar` no añaden
por sí solas esa capacidad. No se propone acceder a `_styles_panel` ni a
`_sidebar_tabs` como si fueran una API de plugins.

La aportación C-08/#151 trata controles/barras de complementos; no se da por
incorporada en la versión 0.8.0 ni por equivalente a una API de proveedores de
Palette. Conviene revisarla antes de proponer otra ampliación. Propuesta para un
encargo futuro: proveedor de biblioteca/miniaturas y una acción de inserción
mediante la herramienta del plugin, con contexto, activación y limpieza al
recargar el complemento. **Identificador pendiente**, sin comunicación externa.

Para una primera implementación que no modifique el anfitrión: botón en la barra
del plugin y una paleta propia no modal mediante Qt público. No se duplica la
administración de capas. El catálogo puede publicar sus bloques 2D en el dibujo
para que aparezcan también en Palette; sus metadatos 3D siguen perteneciendo a la
definición del componente y la inserción BIM usa COMPONENTE. Una inserción de
bloque ordinaria no debe prometer una instancia BIM si no pasa por esa validación.

Fuentes: [Palette y pruebas de IngeCAD 0.8.0](https://github.com/ingelibre/ingecad/blob/32a15cbd573b62f7c0d31aa6329d82fad55fb950/tests/test_palette_blocks.py),
[API de plugins](https://github.com/ingelibre/ingecad/blob/32a15cbd573b62f7c0d31aa6329d82fad55fb950/core/plugins.py).

## 3. Formato propuesto

Carpeta o paquete `arq.componente/v1` con `componente.json`, `planta.dxf`,
`cuerpo.glb`, `miniatura.png` y licencia. Las mallas son cerradas cuando se declaran
volúmenes; las superficies abiertas solo pueden declarar área y una condición
explícita de representación. No se inventa volumen de una caja envolvente.

Ejemplo de metadatos (diseño, no esquema ya adoptado):

```json
{
  "schema": "arq.componente/v1",
  "id": "generico-lavabo-060",
  "revision": 1,
  "nombre": "Lavabo 600",
  "categoria": "bano/lavabos",
  "units": "m",
  "ifc": {"class": "IfcSanitaryTerminal", "PredefinedType": "WASHHANDBASIN"},
  "planta": {"file": "planta.dxf", "block": "ARQ_LAVABO_060", "sha256": "..."},
  "cuerpo": {"file": "cuerpo.glb", "sha256": "...", "axis": "Y_UP"},
  "medidas": {"largo": 0.60, "ancho": 0.48, "alto": 0.20},
  "insercion": {"origen": [0, 0, 0], "suelo": 0, "elevacion": 0.80},
  "alojamientos": ["muro", "encimera"],
  "parametros": {"mano": ["izquierda", "derecha"], "giro": true},
  "licencia": {"spdx": "CC0-1.0", "autor": "contenido propio", "file": "LICENSE.txt"}
}
```

Referencia de ejes y unidades: [especificación glTF 2.0](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#coordinate-system-and-units).

GLB evita depender de referencias externas dispersas y conserva materiales; es
un formato abierto. glTF usa metros y eje Y vertical. El contrato del plugin usa
Z vertical: se fija una conversión de base explícita, por ejemplo
`(x, y, z) glTF → (x, -z, y) CAD`, y se comprueba su determinante positivo. El DXF
2D está en XY del componente con +Z como vertical. Esa transformación no se deja
a una preferencia del importador. OBJ podría ser un importador opcional, pero
requiere declarar unidades, ejes y materiales aparte; IGZ sería una alternativa
vinculada al anfitrión y no se recomienda como único formato de biblioteca.

La instancia conserva la definición y malla necesarias dentro del proyecto, sus
hashes, parámetros y transformación. No depende de que la biblioteca del usuario
siga instalada cuando se reabra el DXF o se exporte el contrato. Una revisión de
catálogo no sustituye automáticamente piezas ya colocadas: la actualización es
una operación explícita con Deshacer.

## 4. Creación desde una selección

La orden de autoría propuesta solicita selección, origen, eje X, vertical y plano
de apoyo. Se muestra qué punto quedará en el suelo, cara de muro o encimera. Debe
existir tanto representación 2D como cuerpo 3D; una selección de líneas no produce
por sí sola una geometría volumétrica fiable. Se admite asociar una malla propia
validada o generar un cuerpo a partir de parámetros geométricos definidos.

Antes de guardar se valida que parámetros, huella física y cuerpo coinciden y comparten enganche; el símbolo puede simplificar o anotar esa huella, que los identificadores no colisionan y que materiales/miniatura tienen
procedencia y licencia. El paquete no acepta rutas que escapen de su carpeta.
Se verifica el hash y se importa de forma atómica en la biblioteca de usuario;
un error no deja un catálogo parcialmente escrito.

El alojamiento se expresa mediante referencias: nivel y desfase para suelo;
identidad de muro, estación y cara para pared; identidad y coordenadas locales de
la superficie para encimera. Al desaparecer el anfitrión se avisa y se conserva
la instancia con alojamiento no resuelto; no se pega silenciosamente a otro muro.
Un cambio de mano corrige la orientación de las caras si la transformación cambia
la orientación del sistema, y mantiene las cantidades positivas.

## 5. Biblioteca del usuario y 30 elementos propios

La biblioteca del usuario vive fuera del repositorio y se importa, como la
biblioteca térmica. La del plugin es un conjunto pequeño independiente. El
código sigue bajo GPL-3.0-or-later. El propietario ha aprobado el 21-11-2026
**CC0-1.0 para el contenido geométrico y las miniaturas propios**, con manifiesto
y procedencia por elemento. Esa decisión ya está tomada; no autoriza a
relicenciar material ajeno ni significa que el catálogo esté producido.

Las medidas siguientes son **dimensiones nominales de un sistema modular**, no
mínimos reglamentarios ni certificaciones de accesibilidad. Cocina se coordina
con módulo 0,60 m. Debe poder cambiarse la medida antes de insertar. No se publican
activos de galerías externas.

| # | Componente propio | Largo × ancho × alto, m | Alojamiento |
|---:|---|---|---|
| 1 | Inodoro | 0,36 × 0,65 × 0,40 | Suelo |
| 2 | Inodoro suspendido | 0,36 × 0,55 × 0,35 | Muro |
| 3 | Bidé | 0,36 × 0,55 × 0,40 | Suelo |
| 4 | Lavabo | 0,60 × 0,48 × 0,20 | Muro/encimera |
| 5 | Lavabo doble | 1,20 × 0,50 × 0,20 | Encimera |
| 6 | Plato de ducha cuadrado | 0,90 × 0,90 × 0,05 | Suelo |
| 7 | Plato de ducha rectangular | 1,20 × 0,80 × 0,05 | Suelo |
| 8 | Bañera | 1,70 × 0,70 × 0,55 | Suelo |
| 9 | Mueble de lavabo | 0,60 × 0,48 × 0,80 | Suelo/muro |
| 10 | Espejo | 0,60 × 0,03 × 0,80 | Muro |
| 11 | Módulo bajo de cocina | 0,60 × 0,60 × 0,90 | Suelo |
| 12 | Módulo alto de cocina | 0,60 × 0,35 × 0,70 | Muro |
| 13 | Módulo cajonero | 0,40 × 0,60 × 0,90 | Suelo |
| 14 | Columna de cocina | 0,60 × 0,60 × 2,10 | Suelo |
| 15 | Fregadero | 0,80 × 0,50 × 0,20 | Encimera |
| 16 | Placa de cocción | 0,60 × 0,52 × 0,06 | Encimera |
| 17 | Horno | 0,60 × 0,60 × 0,60 | Mueble/suelo |
| 18 | Frigorífico | 0,60 × 0,65 × 1,85 | Suelo |
| 19 | Lavavajillas | 0,60 × 0,60 × 0,85 | Suelo |
| 20 | Lavadora | 0,60 × 0,60 × 0,85 | Suelo |
| 21 | Mesa de comedor | 1,20 × 0,80 × 0,75 | Suelo |
| 22 | Silla | 0,45 × 0,45 × 0,85 | Suelo |
| 23 | Cama individual | 0,90 × 1,90 × 0,50 | Suelo |
| 24 | Cama doble | 1,50 × 1,90 × 0,50 | Suelo |
| 25 | Mesilla | 0,50 × 0,40 × 0,50 | Suelo |
| 26 | Armario genérico | 1,20 × 0,60 × 2,10 | Suelo |
| 27 | Escritorio | 1,20 × 0,60 × 0,75 | Suelo |
| 28 | Cómoda | 0,90 × 0,45 × 0,85 | Suelo |
| 29 | Sofá | 1,80 × 0,85 × 0,85 | Suelo |
| 30 | Estantería | 0,80 × 0,30 × 1,80 | Suelo |

La clase IFC se asigna por función, no por aspecto. Lavabo: IfcSanitaryTerminal /
WASHHANDBASIN; inodoro: TOILETPAN; ducha: SHOWER; bañera: BATH; fregadero: SINK.
Cama, silla, mesa, escritorio, sofá y estantería tienen tipos de IfcFurniture.
Armarios y otros muebles sin enumeración adecuada usan USERDEFINED con ObjectType.
Electrodomésticos emplean IfcElectricAppliance, por ejemplo REFRIGERATOR,
DISHWASHER, WASHINGMACHINE y ELECTRICCOOKER; un horno no recibe una enumeración
OVEN inventada. Estas enumeraciones se han contrastado con el esquema IFC4 de
IfcOpenShell instalado, sin exportar ni atribuir al catálogo actual del anfitrión
clases que todavía no admite. La clasificación del espejo y los elementos mixtos
se fija en el encargo de catálogo, no se deduce de su miniatura.

## 6. IngeTrazo, contrato e IFC

En 0.6.2.1, `core/bim.py::IFC_CLASSES` no incluye IfcFurniture ni
IfcSanitaryTerminal ni IfcElectricAppliance. `formats/ifc.py` sustituye una clase
que no está en esa lista por IfcBuildingElementProxy. Es el antecedente **T-15,
#1293**, no un hallazgo nuevo al que asignar otro número.

El plugin debe guardar la clase prevista y el PredefinedType en el contrato y en
la instancia IGZ, y no reinterpretar un sanitario como un proxy «equivalente» a
efectos de cálculo. Si el escritor vigente solo puede producir un proxy, debe
advertirlo e identificar el elemento afectado. Conservar una etiqueta privada
con el nombre de la clase no sustituye a emitir la entidad IFC correcta.

Se propone un paquete de código **P-componentes, identificador/número pendiente**
para Claude: extender la admisión y selección de clases, validar sus enumeraciones
y ObjectType, conservar clase/propiedades al guardar IGZ y crear las entidades IFC
con su planta y cantidades. No basta con ampliar un desplegable. Debe aplicarse
sobre la pila vigente tras los paquetes anteriores, contrastando el estado de
#1293 y la cola antes de escribir código del anfitrión. R28 no modifica esa pila.

El contrato necesita un elemento por instancia, malla, transformación resuelta,
clase, tipo, materiales y cantidades reales; las definiciones compartidas pueden
optimizar almacenamiento, sin dar una sola identidad a todas las instancias.
Longitud/anchura/altura son nominales declaradas o calculadas según el contrato;
NetVolume sale del cuerpo cerrado, no de multiplicar las tres medidas exteriores
de un lavabo hueco. La exportación debe distinguir cuerpo y puertas de un armario
para que no haya doble conteo.

Fuentes: [catálogo vigente](https://github.com/ingelibre/ingetrazo/blob/8dbed761dca99dcae76efd9cd3025bfa5b8014d8/core/bim.py),
[escritor IFC](https://github.com/ingelibre/ingetrazo/blob/8dbed761dca99dcae76efd9cd3025bfa5b8014d8/formats/ifc.py).

## 7. ARMARIOBIM, superficies y ocupación

ARMARIOBIM sigue siendo un elemento específico alojado en muro, con cuerpo y
frentes. No se convierte automáticamente en un componente genérico ni pierde sus
identidades de frentes; MEMORIACARP sigue consumiéndolos desde `cabinets.fronts`.
BLOQUE conserva su geometría antigua y sus avisos; promover una instancia antigua
requiere seleccionar una definición y confirmar dimensiones/alojamiento.

La condición de mobiliario fijo es un dato explícito. Los objetos móviles no
restan automáticamente superficie útil ni cambian la ocupación DB-SI. Para los
fijos se reutiliza el criterio existente de armarios y la política declarada en
el dibujo, con la normativa y uso correspondientes. No basta con que una malla
toque el suelo para clasificarla como cerramiento.

Debe distinguirse superficie útil de un informe, recinto IFC, espacio térmico y
superficie usada para ocupación. Restar una huella de mueble en un listado no
autoriza a recortar también el volumen térmico ni a crear fronteras IFC nuevas.
Se documenta qué cantidad cambia con cada política y se comprueba que el criterio
no se aplica dos veces a un armario que ya participa en el cálculo actual.

## 8. Fases, pruebas y decisiones pendientes

| Fase | Entregable | Estimación |
|---|---|---:|
| C0 | Esquema, transformaciones y tres componentes piloto propios | 2–3 jornadas |
| C1 | Definición/instancia, inserción y -COMPONENTE, Undo/Redo | 4–6 |
| C2 | Biblioteca usuario, importación y paleta con miniaturas | 4–6 |
| C3 | Alojamiento y edición paramétrica compartida 2D/3D | 4–7 |
| C4 | Propuesta IFC sobre la cola vigente y aceptación externa | 3–5 |
| C5 | Catálogo de 30 componentes, licencias y documentación | 4–6 |

Pruebas mínimas: origen/ejes/elevación, giro y reflexión; identidad al copiar;
medidas de planta/malla; muro y encimera movidos o eliminados; reapertura sin
biblioteca instalada; revisión de catálogo sin sustitución silenciosa; hashes y
rutas inválidos; licencia ausente; cancelación sin residuos; DXF/DWG con acentos;
paridad ficha/texto y ventana real; IFC con clase y planta previstas, volumen real
y aceptación en una aplicación externa. No se dan por aprobadas antes de existir
la implementación.

Decisiones para Claude: aceptar GLB como cuerpo canónico; elegir paleta inicial frente a pedir proveedor nativo; fijar
clasificación de los componentes mixtos; dar número y turno al paquete de clases
IFC. El diseño aprovecha lo comprobado de los anfitriones y deja separados los
puntos que requieren una API o una implementación futura.

No se ha instalado ni usado ninguna biblioteca de SketchUp. No se han descargado
componentes de terceros ni copiado material comercial. Solo se han consultado
fuentes públicas y código para lectura, sin modificar IngeCAD ni IngeTrazo.

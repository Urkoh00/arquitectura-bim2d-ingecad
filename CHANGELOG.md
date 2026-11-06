# Arquitectura para IngeCAD v1.6.0-dev — motor de nodos y huella única 2D/3D (EXPERIMENTAL)

Fecha: 5-11-2026. Base: v1.5.1. Distribución de ensayo: no sustituye la versión de trabajo.

## Qué cambia

1. **`geom/` (nuevo, Python puro, sin dependencias):**
   - `geom/junctions.py`: motor de encuentros por nodos. Esquinas L con inglete exacto
     a cualquier ángulo y con espesores distintos, uniones T (el muro pasante conserva su
     huella), cruces X, nodos de 3 o más muros, escalones colineales, referencias de eje
     o de cara, y esquinas dibujadas hasta la cara (caso `35.dxf`). Cada muro recibe UNA
     huella propia; las huellas no se solapan entre sí ni con los pilares.
   - `geom/solids.py`: sólido 3D estanco de cada muro a partir de esa misma huella, con
     puertas y ventanas como huecos reales (sin caras interiores).
   - `geom/polygon.py`: núcleo de polígonos (recortes convexos y pegado de piezas).
2. **`UNIONESARQ`** usa el motor nuevo dentro del mismo comando con deshacer/rehacer. Cada
   línea del contorno conserva el ID del muro al que pertenece.
3. **`EXPORTARBIM` (nuevo):** escribe un `.arqbim` (JSON, contrato versionado) con la geometría
   final, los GUID IFC estables, nivel, material, tipo, Psets, cantidades y huecos. Ya no
   hace falta configurar fuentes ni un Python de IngeTrazo.
4. **Extensión para IngeTrazo** (`ingetrazo_ext/arquitectura_bim.py`, en el ZIP): abre los
   `.arqbim` desde IngeTrazo instalado o portable y los inserta como grupos BIM etiquetados.
5. **Eje CAD como fuente de verdad:** la exportación toma el eje de la polilínea visible; si el
   XDATA `a/b` quedó desfasado (MOVE/ROTATE/MIRROR genéricos) lo avisa. Un ID duplicado
   (COPY) bloquea la exportación con un mensaje claro.
6. **`reactor.py`:** si IngeCAD incorpora el gancho de reactores propuesto (parche en
   `upstream/ingecad/`), tras MOVE/COPY/MIRROR/ROTATE el plugin reasigna ID a las copias,
   sincroniza el XDATA y regenera el contorno **en el mismo paso de deshacer**. En un IngeCAD
   sin el gancho, el plugin funciona como antes.
7. `EXPORTARIGZ`/`CONFIGIGZ` siguen disponibles como «puente antiguo».

## Reglas del motor (explícitas)

- Tolerancia de mismo punto: 1 mm. Nada se une por simple proximidad.
- Esquina dibujada hasta la cara: se une si cada extremo cae dentro de la franja del otro
  muro, cerca de su extremo.
- T: el extremo dentro de la franja de otro muro (lejos de sus extremos) se prolonga hasta la
  cara opuesta y se recorta contra el pasante.
- Ángulo mínimo entre muros: 5°. Por debajo se tratan como paralelos.
- Inglete máximo: 6 × espesor. Por encima, corte recto.
- Propiedad de solapes: pilar > muro. En una T gana el pasante. En los demás casos decide
  `join_priority` (XDATA, opcional), luego el espesor y luego el orden de dibujo.

## Pruebas (carpeta `tests/` del ZIP)

| Archivo | Qué comprueba |
|---|---|
| `test_junctions.py` | 66 casos L/T/X/nodos/colineal/caras/proximidad/pilares, contrastados con shapely |
| `test_dxf_regression.py` | `34.dxf`, `35.dxf`, `36.dxf`: solape 0, geometría ideal y 8 líneas por recinto (16 en 35/36) |
| `test_solids.py` | Sólidos estancos; volumen = área en planta × altura − huecos |
| `test_ingecad_integration.py` | Plugin cargado con el **cargador real** de IngeCAD, `Document`/`History` reales, deshacer/rehacer, COPY/MOVE/MIRROR |

Para ejecutarlas hacen falta las fuentes de IngeCAD en `PYTHONPATH` y `pytest`, `ezdxf` y
`shapely` (shapely solo se usa en las pruebas).

## v1.6.1-dev (5-11-2026, tras la primera prueba en Windows)

- `UNIONESARQ` no se veía hasta regenerar la pantalla: el comando ahora pide la regeneración
  a IngeCAD (`needs_regen`).
- `EXPORTARBIM` (y el antiguo `EXPORTARIGZ`) fallaban al abrir el diálogo de guardar: se pasaba
  como ventana padre el método `window` de Qt en lugar de la ventana. Nuevo `compat.dialog_parent`.
- Regresión: el contorno de `36.dxf` coincide línea a línea con `36_contornos_v1.4.2.dxf` (16 líneas).

## v1.6.2-dev (6-11-2026) — Fase 1: el muro se maneja como un objeto

Problema visto en Windows: el eje BIM del muro está en una capa apagada y lo visible son
líneas de contorno derivadas. Al copiar esas líneas quedaba un «recinto fantasma»: dibujado,
pero sin muros BIM.

- **Un grupo nativo por muro** (`ARQ_<handle>`): eje + sus líneas de contorno, con el indicador
  *seleccionable* de los grupos de IngeCAD. Al pinchar o designar por ventana cualquier línea
  del muro se selecciona el muro completo, y COPIAR, DESPLAZAR, BORRAR o SIMETRÍA actúan sobre
  el objeto BIM y su dibujo a la vez. Los grupos se guardan en el DXF (diccionario ACAD_GROUP).
- **`UNIONESARQ` repara lo que dejan los comandos genéricos**, en un solo paso de deshacer:
  - una copia (mismo ID que su original) recibe identidad nueva con `copied_from`; el original,
    el de handle más antiguo, conserva la suya;
  - un eje o un pilar desplazado actualiza `a`/`b`/`center` desde la geometría CAD;
  - regenera el contorno, eliminando las líneas sobrantes, y rehace los grupos.
  Funciona con IngeCAD oficial; con el gancho de reactores propuesto ocurre automáticamente al
  terminar la COPIA o el DESPLAZAMIENTO.
- `UNIONESARQ` ya no destruye entidades: igual que el BORRAR de IngeCAD, desvincula las líneas
  antiguas y las conserva, y deshacer/rehacer devuelve los mismos objetos. Corrige un fallo al
  deshacer una COPIA reparada por el reactor.
- **`ARQVALIDAR`** compara el contorno del dibujo con el que producen los muros: avisa de
  líneas sin muro BIM (recinto fantasma), de líneas que faltan y de muros sin grupo.
- `EXPORTARBIM` con identificadores duplicados indica ahora que `UNIONESARQ` lo resuelve.
- Pruebas: `tests/test_seleccion_grupos.py` (selección por grupos real de IngeCAD, COPY/MOVE
  reales, recinto fantasma, guardado en DXF, deshacer/rehacer). 95 correctas + 4 omitidas con
  IngeCAD oficial; 99 con el gancho de reactores.

## v1.7.0-dev (6-11-2026) — Fase 2: dibujo de muros

- **`MURO`**:
  - **I** o **F5** cambia la cara por la que se dibuja (cuerpo del muro a un lado u otro de la
    línea trazada). F5 funciona como tecla mientras `MURO` está activo; IngeCAD no la usa.
  - **G** (iGual) toma espesor, altura, cota, referencia, tipo, material y planta de un muro
    existente designado por su contorno.
  - **Gesto T/L**: terminar el muro en la cara **próxima** de otro hace una T; terminar en la
    cara **alejada** hace una L y recorta el otro muro, que conserva su parte más larga y su
    identidad BIM. Sus carpinterías mantienen la posición; si el recorte eliminara una, la
    esquina se rechaza con un aviso. Todo en un solo paso de deshacer.
- **`MUROPARALELO`**: muro paralelo a una cara (o a cualquier línea) a una distancia dada, en
  el lado que se indica; sus extremos se ajustan a las caras de los muros vecinos, también
  oblicuos, para que formen T. Repetible.
- **`ESTIRAMURO`**: alarga o acorta el extremo designado de un muro hasta una línea límite.
- **`PIVOTAMURO`**: mueve un extremo de un muro; el otro queda fijo.
- **Motor de encuentros** (fallo encontrado por las pruebas de esta fase):
  - El centro del nodo es el cruce de los **ejes**, no el de las líneas de referencia. Con un
    muro referido a su cara, la huella se partía con un solape.
  - Dos extremos cuyos ejes terminan en el mismo punto forman una esquina aunque se hayan
    dibujado por caras distintas (antes, a 45°, se tomaba por T).
- Pruebas nuevas: `test_drafting.py` (46 casos de geometría contra el motor y shapely),
  `test_wall_tools.py` (las herramientas con Document/History reales) y `test_f5_ventana.py`
  (F5 en la ventana real de IngeCAD, en un proceso aparte).
- **`RECINTO`** (espacios BIM básicos, véase `docs/DISENO_ESPACIOS.md`):
  - Con un clic dentro de una estancia se crea un recinto `IfcSpace`: contorno exacto entre las
    caras de muros y pilares, con los pilares exentos descontados como islas, y etiqueta con
    nombre y superficie. Opciones antes del clic: Nombre, Altura y Uso.
  - Es **asociativo**: guarda el punto interior y `UNIONESARQ` recalcula su contorno, superficie
    y etiqueta cuando se mueven los muros. Copiar un recinto lleva su punto con él y le da
    identidad nueva.
  - Se rechaza, con un aviso, un clic dentro de un muro, en una estancia abierta o en una
    estancia que ya es otro recinto. `ARQVALIDAR` avisa de recintos abiertos, duplicados o
    desactualizados.
  - Exportación: `IfcSpace` con `Qto_SpaceBaseQuantities` (Height, Gross/NetFloorArea,
    Gross/NetPerimeter, Gross/NetVolume), `Pset_SpaceCommon` y `ARQ_Recinto`. En IngeTrazo van
    en la capa `ARQ-RECINTOS`, apagada y semitransparente.
  - **Muros exteriores automáticos:** `Pset_WallCommon.IsExternal` se calcula; es exterior el muro
    que tiene una cara en el contorno exterior del edificio.
  - Pendiente de las decisiones del usuario: criterio de superficie útil y altura (hoy, superficie
    libre entre caras y altura = altura de muro por defecto, modificable).
  - El exportador IFC actual de IngeTrazo contiene los `IfcSpace` en la planta en lugar de
    agregarlos (errores de reglas IFC4). Corrección preparada en
    `docs/propuestas_upstream/ingetrazo/0002-…`: con ella, el IFC de prueba da 0 errores.

## v1.8.0-dev (6-11-2026) — muros y tabiques: segundo repaso del programa de referencia

Repaso a fondo de manuales, ayuda y vídeos (fotograma a fotograma) centrado en muros y tabiques.

- **Tipos de muro con nombre** (`IfcWallType`): Tabique, Tabicón, Medio pie, Un pie, Pie y medio y
  Dos pies, editables por dibujo con `TIPOSMURO` (listar, `TIPOSMURO Nombre 0,12 [material]`,
  `TIPOSMURO -Nombre`). En `MURO`, `MUROPARALELO` y `DIVIDEMURO`, la opción **T** elige el tipo por
  número o por el principio del nombre.
- **Cambio automático de cara**: un muro que arranca en la cara de otro o en una esquina interior
  cambia solo de cara si la elegida invadiría el muro existente (F5 la sigue invirtiendo).
- **`MUROPARALELO`** de tres clics: línea base, lado de la paralela y lado del espesor (con
  distancia = medio espesor y el espesor hacia la línea, queda centrado en un eje). Tras un muro,
  un clic en vacío crea el siguiente paralelo a partir del recién hecho (encadenado). La distancia
  se cambia tecleándola en cualquier momento.
- **`ESTIRAMURO`** como «estirar/acortar»: hasta un punto libre (sobre la dirección del muro), una
  línea o la cara de otro muro (cara próxima = T; alejada = L, que recorta ese muro); también con
  la longitud tecleada.
- **`DIVIDEMURO`**: divide un tramo en N partes iguales (luces libres iguales) con muros
  perpendiculares hacia la izquierda del sentido indicado; longitud dada o hasta el muro de enfrente.
- **`BORRATRAMO`**: borra el tramo de muro entre dos cruces (o entre un cruce y el extremo) y
  rehace los encuentros; el tramo central parte el muro en dos.
- **`PARTEMURO` / `UNIRMURO`**: abre un vano partiendo el muro en dos (las carpinterías pasan al
  tramo que las contiene; un vano sobre una carpintería se rechaza) / une dos muros alineados del
  mismo espesor (el primero conserva su identidad y recibe las carpinterías del segundo).
- Corrección: al deshacer el borrado de un muro, su grupo de selección se restaura en el orden
  correcto.
- Pruebas: `tests/test_wall_tools_2.py` (15 casos con Document/History reales).

## v1.8.1-dev (6-11-2026) — espesor total primero; tipos multicapa

Petición del usuario: los nombres tradicionales (tabique, tabicón, pies) ya no describen lo que
se construye; hacen falta muchos más tipos (Termoarcilla, placa de yeso laminado, multicapa) y
el dato principal es el **espesor total**.

- **`MURO`**: antes del primer punto, un número tecleado es el **espesor total**. Si un solo tipo
  del catálogo lo tiene, se aplica; si varios, se elige por número (Intro = muro genérico); si
  ninguno, muro genérico «Muro 0,33». Después del primer punto un número sigue siendo la
  longitud. `MUROPARALELO` y `DIVIDEMURO` siguen la misma regla con la opción E.
- **Tipos multicapa**: cada tipo es una lista de capas (espesor y material) desde la cara
  dibujada; el espesor total es su suma. El muro guarda sus capas, y la exportación las lleva en
  `material_layers` y en el Pset `ARQ_Capas` (el IFC `IfcMaterialLayerSet` queda pendiente de
  IngeTrazo). Se avisa si las capas no suman el espesor.
- **Catálogo por defecto** (editable por dibujo): PYL 78/48, 98/48, 100/70, 120/70, 120/90 y 140/90
  (designación espesor total / montante, Placo); Termoarcilla 14, 19, 24 y 29 (Hispalyt);
  tabique de LHD 7 guarnecido; una fachada multicapa de ejemplo. Se retiran los nombres
  tradicionales.
- **`TIPOSMURO`**: lista agrupada por espesor total; `TIPOSMURO 0,24` muestra las capas de los
  tipos de ese espesor; `TIPOSMURO Nombre = 0,015 Yeso + 0,07 LHD + 0,015 Yeso` crea un tipo
  multicapa; `TIPOSMURO importar ruta.csv` / `exportar ruta.csv` («Nombre;capas» o
  «Nombre;espesor;material»), para cargar catálogos completos de una vez.

## v1.9.0-dev (6-11-2026) — pilares embebidos y metálicos

- **`PILAR`** nuevo:
  - **Secciones** tecleadas con S: rectangular (`0,30x0,30`, `30x40` en cm), circular (`D0,35`) y
    **perfiles metálicos** IPE, IPN, HEA, HEB, UPN, **2 UPN en cajón** y **2 UPN empresillados**
    con su separación.
  - **9 puntos de enganche** (teclado numérico: 7 8 9 / 4 5 6 / 1 2 3), **G** gira 90°, **R** ángulo
    tecleado, **A** autorrotación según el muro o la línea bajo el cursor.
  - **P, a distancia de dos paramentos:** clic en dos caras (o líneas) y en la esquina donde va el
    pilar; sus lados quedan a d1 y d2 de ellas. Es el caso del pilar de fachada retranqueado 5 cm
    de las caras exteriores que corta la cara interior del muro.
  - **U, a distancia de un paramento** (pilares intermedios de fachada).
  - **C, recubrimiento.**
- **Tablas de perfiles** con sus fuentes en `profiles.py`. Los contornos son exactos, con alas
  inclinadas (IPN 14 %, UPN 8 % / 5 %) y radios de acuerdo, y reproducen el área de tabla con un
  desvío máximo del 0,8 % (IPE/HEA/HEB ≤ 0,41 %).
- **Modelo:** la huella del pilar (lo que corta el muro y rodea el recinto) incluye el recubrimiento
  o el cajeado del perfil; la sección real (hormigón o perfil) es el `IfcColumn`; la diferencia se
  exporta como `IfcCovering` («Recubrimiento» o «Interior del cajeado del perfil»). Muros, pilares,
  revestimientos y recintos siguen teselando la planta sin huecos ni solapes.
- El perfil se dibuja en planta dentro de su contorno y forma grupo de selección con el pilar;
  `UNIONESARQ` lo regenera. Un giro con `GIRA` de IngeCAD actualiza la rotación del pilar.
- Exportación: `ARQ_Perfil` (designación, área nominal, masa kg/m) y `NetWeight`.
- Corrección: el pilar rectangular ignoraba la rotación.
- **Recintos:** descuentan la parte del pilar que sobresale del muro (prueba con el pilar de
  esquina: 5 × 5 cm).
- Cadena completa probada: plano → `.arqbim` → IngeTrazo (8 elementos estancos) → IFC (0 errores
  con la corrección de `IfcSpace` propuesta).

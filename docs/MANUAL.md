# Manual de Arquitectura para IngeCAD — versión 1.44.0-dev

Versión 1.44.0-dev · 19-11-2026

> Copia del manual publicado como documento en claude.ai; se regenera con cada versión.

## Qué es

Arquitectura es un plugin de IngeCAD para dibujar plantas en 2D en las que cada muro, pilar, puerta, ventana y recinto es desde el principio un objeto BIM, que se lleva a IngeTrazo y se exporta a IFC sin redibujar nada. Este manual corresponde a la versión **1.44.0-dev** y se actualiza con cada versión.

Cada elemento guarda su identidad persistente, su clase IFC, su geometría editable en planta, sus parámetros 3D (altura, espesor, cota), sus propiedades constructivas (tipo, material, capas) y su nivel. Las carpinterías conocen su muro y los recintos siguen a los muros que los cierran.

```
IngeCAD + plugin  ──EXPORTARBIM──▶  .arqbim  ──Importar .arqbim──▶  IngeTrazo (IGZ)  ──Exportar IFC──▶  IFC
 (planta 2D BIM)                 (sólidos 3D, datos)              (grupos BIM)
```

El plugin calcula una sola vez la huella final de cada elemento, con los encuentros resueltos y sin solapes; de ella salen el contorno en planta, los recintos, el sólido 3D y las cantidades. Es software libre (GPL-3.0) y experimental.

**Documentación para el cálculo energético.** Otro objetivo del plugin es generar, desde el mismo dibujo, la documentación —fundamentalmente gráfica— que necesitan los programas reconocidos para verificar el DB-HE y certificar la eficiencia energética (HULC, CYPETHERM HE Plus, SG SAVE, CE3X, CERMA y otros): plantas con recintos, orientación y norte; cerramientos clasificados (fachada, medianera, cubierta, solera, contacto con el terreno) con sus superficies por orientación; huecos de cada cerramiento; y longitudes de los puentes térmicos por tipo. Los programas que leen IFC lo reciben a través de IngeTrazo; para los que se introducen a mano, el plugin dará los planos y las tablas listos para transcribir. Está en desarrollo: desde la 1.34 el modelo ya lleva el norte, la clase de cada forjado y el tipo de cada muro y recinto.

## Instalación

El plugin se instala copiando una carpeta en IngeCAD, y la extensión copiando todo el contenido de su carpeta en IngeTrazo. No hace falta instalar Python aparte.

**Requisitos.** La última versión publicada de IngeCAD y de IngeTrazo; hoy, IngeCAD 0.8.0 e IngeTrazo 0.6.2.1. Los dos programas publican versiones nuevas casi cada semana, con muchos cambios en cada una, así que el plugin solo se desarrolla y se prueba con la última de cada uno: no use versiones anteriores.

**En IngeCAD**

1. Descomprima el ZIP de la versión, por ejemplo `Arquitectura_IngeCAD_v1.44.0-dev.zip`.
2. Copie la carpeta `arquitectura` en la carpeta de plugins de IngeCAD.
3. Reinicie IngeCAD. Aparece el menú *Arquitectura* y su barra de herramientas.
4. Escriba `ARQDIAG` en la línea de órdenes para comprobar que la versión cargada es la que acaba de copiar.

**En IngeTrazo**

1. Abra *Extensiones > Abrir carpeta de plugins*.
2. Copie en ella **todo el contenido** de la carpeta `ingetrazo_ext` del ZIP: `arquitectura_bim.py`, `_arqbim_sync.py`, `_arq_edit.py` y la subcarpeta `arq_shared` (desde la 1.30). Si falta algo, la importación se detiene y avisa. Reinicie IngeTrazo después de actualizar.
3. Reinicie IngeTrazo. Aparece la orden *Importar arquitectura IngeCAD (.arqbim)…*.

**Para actualizar**, sustituya la carpeta `arquitectura` y el contenido de la extensión por los de la versión nueva. Mientras el plugin esté en desarrollo no se garantiza que los dibujos hechos con versiones anteriores del plugin se lean igual: guarde antes una copia y, si alguno se ve desactualizado, ejecute `UNIONESARQ`.

El plugin es experimental: no lo use todavía en proyectos reales sin guardar antes una copia.

## Conceptos básicos

Cada elemento es un objeto BIM con identidad propia; las líneas que se ven en planta se calculan a partir de él y no se editan a mano.

**El objeto y su dibujo.** Un muro se guarda como su línea de referencia (un eje CAD oculto) más sus datos: espesor, altura, cota, referencia, tipo, material, nivel e identificador. El contorno visible, con los encuentros resueltos, se deriva de esos datos. Lo mismo ocurre con pilares, carpinterías y recintos.

**Referencia del muro.** La línea que se dibuja puede ser el *eje* o una de las caras. Con *izquierda*, el cuerpo queda a la izquierda del sentido de dibujo; con *derecha*, a la derecha. `F5` o la opción `I` invierten la cara mientras se dibuja.

**Capas.**

| Capa | Contiene | Visible |
| --- | --- | --- |
| ARQ-MUROS | Contorno de muros calculado (líneas y arcos) | Sí |
| ARQ-MUROS3D | Ejes de los muros con sus datos BIM | No, se apaga sola |
| ARQ-PILARES | Pilares | Sí |
| ARQ-HUECOS3D | Portadores de las carpinterías con sus datos | No, se apaga sola |
| ARQ-CARPINTERIA | Símbolos de puertas y ventanas | Sí |
| ARQ-RECINTOS | Contornos y rótulos de los recintos | Sí |
| ARQ-PLANO-ORIGEN | Líneas de un plano convertido con LINEASAMURO | No |

**Regeneración.** Cada orden del plugin recalcula los encuentros y el contorno en el mismo paso, y se deshace con un solo `Deshacer`. Tras editar con órdenes genéricas de IngeCAD (desplazar, copiar, simetría, estirar el eje), ejecute `UNIONESARQ`: lee el dibujo, actualiza los datos y regenera.

**El dibujo manda, y las órdenes de IngeCAD valen.** Los elementos BIM se pueden desplazar, girar, escalar, reflejar y copiar con las órdenes de IngeCAD. Cada elemento lleva un marco de referencia invisible que IngeCAD transforma con él. Al regenerar (cualquier orden del plugin o `UNIONESARQ`) o al exportar, el plugin lee la transformación y ajusta los datos BIM:

- espesores y capas al escalar;
- sección de los pilares;
- lado del muro y cara hacia la que abre la puerta en una simetría;
- punto interior de los recintos.

Nada se rechaza. Si algo no se puede representar exactamente, se avisa: por ejemplo, un perfil metálico escalado pasa a sección rectangular genérica. Una copia recibe un identificador nuevo y el original conserva el suyo.

**El ajuste es inmediato.** Tras la orden de IngeCAD, el plugin regenera el plano en el mismo paso de deshacer, sin necesidad de `UNIONESARQ`, y un solo `Deshacer` lo devuelve todo a como estaba.

**Doble clic.** Al hacer doble clic sobre un elemento:

- **un muro** (cualquiera de sus líneas): arranca `MURO` con su espesor, altura, cota, cara, tipo y capas;
- **una puerta o ventana**: arranca `CARPINTERIA` con su modelo;
- **un pilar**: arranca `PILAR` con su sección;
- **un recinto**: abre su ficha.

Es la forma más rápida de seguir dibujando «como ese». También lo hacen la opción `G` de `MURO` y `PROPIEDADESARQ`.

**Selección.** Cada muro forma un grupo con su eje y sus líneas de contorno: al designar cualquiera de sus líneas se designa el muro entero. No borre ni mueva solo las líneas del contorno; `ARQVALIDAR` avisa si quedan líneas sin muro.

**Una sola geometría.** La planta, los recintos, el sólido 3D y el IFC salen de la misma huella calculada. Un encuentro correcto en planta es también correcto en 3D.

## Parámetros, tipos de muro y usos del edificio

Los valores por defecto, el catálogo de tipos de muro y los usos se guardan dentro del propio DXF; cambiarlos no modifica los elementos ya dibujados.

**PARAMETROSARQ** abre una ficha con los valores de partida: espesor 0,30 m, altura 3,00 m, cota 0 y referencia por el eje para los muros; pilar de 0,30 × 0,30 m; puerta de 2,10 m de altura; ventana de 1,20 × 1,20 m con antepecho de 1,00 m. Se deshace con `Deshacer`.

**Opciones generales.** La pestaña *General* de la misma ficha elige la forma de trabajar con el dibujo:

- **Trabajar con usos de recinto.** Si se activa, la ficha de recinto pide el uso y es el uso el que decide la clasificación; el nombre es libre y no la cambia. Si no se activa, la decide el nombre y la ficha no pide el uso. La clasificación determina, por ejemplo, la altura habitable de 2,20 m en baños y pasillos.
- **Cota mínima.** `COTAMUROS` no acota distancias menores que esta y las suma a la siguiente.
- **Norte (desde la 1.34).** Dirección del norte geográfico, en grados en sentido horario desde el eje +Y del dibujo (0 = norte arriba), la misma convención que Herramientas ▸ Norte de IngeTrazo. Viaja en la exportación: IngeTrazo lo recibe como norte de la escena y lo necesitan los programas de cálculo energético para orientar las fachadas.

Aquí se guardan también las capas y la tolerancia que usa `LINEASAMURO`.

**TIPOSMURO** gestiona el catálogo. Sin argumentos abre una ficha con la lista de tipos y las capas de cada uno, donde se crean, duplican y eliminan tipos y se añaden, quitan y ordenan capas. Las formas de la tabla sirven desde la línea de órdenes. Cada tipo es una lista de capas, contadas desde la cara dibujada hacia el cuerpo del muro; su espesor total es la suma de las capas.

| Escriba | Hace |
| --- | --- |
| `TIPOSMURO` | Lista los tipos, agrupados por espesor total |
| `TIPOSMURO 0,24` | Muestra los tipos de 0,24 m con sus capas |
| `TIPOSMURO Nombre 0,12 material` | Añade o cambia un tipo de una capa |
| `TIPOSMURO Nombre = 0,015 Yeso + 0,07 LHD` | Añade o cambia un tipo multicapa |
| `TIPOSMURO -Nombre` | Quita un tipo |
| `TIPOSMURO importar ruta.csv` | Lee líneas `Nombre;capas` o `Nombre;espesor;material` |
| `TIPOSMURO exportar ruta.csv` | Guarda el catálogo |

El catálogo inicial trae tabiques de placa de yeso laminado y fábricas de termoarcilla. Al dibujar un muro, escriba primero el espesor total: si hay un solo tipo con ese espesor se aplica; si hay varios, se elige de una lista.

**USOSARQ** guarda tres clasificaciones independientes del edificio, que nunca se deducen unas de otras:

| Clasificación | Orden | Valores |
| --- | --- | --- |
| Tipo de edificio del certificado energético | `USOSARQ edificio <tipo>` | ViviendaUnifamiliar, BloqueDeViviendaCompleto, ViviendaIndividualEnBloque, EdificioUsoTerciario, LocalUsoTerciario |
| Uso DB-HE | `USOSARQ dbhe residencial` o `USOSARQ dbhe otros <carga> <horas>` | carga baja, media o alta; 8, 12, 16 o 24 horas |
| Uso DB-SI / DB-SUA | `USOSARQ dbsi <uso>` | texto libre: Residencial Vivienda, Docente, Administrativo… |

`USOSARQ` sin más abre una ficha con las tres clasificaciones (en «otros usos» del DB-HE, con su carga y su horario); con argumentos las cambia desde la línea de órdenes. Las tres clasificaciones se exportan al proyecto IFC y a cada espacio.

**BIBLIOTECAHE** guarda la biblioteca térmica del usuario: materiales (λ, densidad, calor específico, difusión de vapor o resistencia), composiciones por capas, vidrios (U y g⊥), marcos y huecos. El plugin **no distribuye** el catálogo de la Herramienta Unificada LIDER-CALENER: cada usuario lo importa una vez desde su instalación, como hacen otros programas de cálculo.

| Orden | Qué hace |
| --- | --- |
| `BIBLIOTECAHE importar` | Importa el `BDCatalogo.bdc` de la instalación (si hay uno en `C:\ProgramasCTEyCEE`) o el que se elija; también acepta el `.bdc.utf8.gz` del IETcc o un ZIP |
| `BIBLIOTECAHE importar <ruta>` | Importa ese fichero |
| `BIBLIOTECAHE buscar <texto>` | Materiales que contienen el texto, sin distinguir tildes ni mayúsculas |
| `BIBLIOTECAHE u <composición>` | U de una composición del catálogo como muro; con `/ techo` o `/ suelo`, como cubierta o como suelo sobre el exterior (resistencias superficiales del DA DB-HE/1) |
| `BIBLIOTECAHE` | Muestra el fichero, el catálogo de origen y los recuentos |

La biblioteca se guarda en la carpeta de configuración del usuario (en Windows, `%APPDATA%\IngeCAD\arquitectura\biblioteca_termica.json`) y sirve para todos los proyectos; no se copia al dibujo. Las referencias rotas del propio catálogo se avisan al importar. La U que calcula sirve para tantear tipos de muro mientras se dibuja; no sustituye a los programas reconocidos.

## Muros rectos

`MURO` dibuja muros encadenados como una polilínea; cada tramo es un muro BIM (IfcWall) con sus encuentros ya resueltos.

**MURO.** Antes del primer punto, un número se lee como el **espesor total** y el programa ofrece los tipos de muro que lo tienen. Después, un número es la longitud del tramo en la dirección del cursor. `Intro` empieza un tramo nuevo; otro `Intro` termina. Al empezar, la ficha de muro permite elegir un tipo del catálogo: muestra sus capas y fija el espesor; «Genérico» deja el espesor libre.

**Escribir el espesor.** En IngeCAD, `x,y` es un punto y los decimales llevan punto. El plugin acepta también la coma decimal para el espesor (`0,25`), pero solo cuando el valor es un espesor razonable, hasta 1,5 m. Si no lo es, se toma como punto: `3,4` empieza el muro en el punto (3, 4). Un número sin coma mayor de 1,5 se entiende en **centímetros** hasta 100 (`25` = 0,25 m) y en **milímetros** hasta 1500 (`250` = 0,25 m), y el programa dice cómo lo ha leído. Un valor fuera de esos márgenes se rechaza con un aviso. Lo mismo vale en `MUROPARALELO` y `MUROCURVO`.

**DEFENSA (desde la 1.29).** Dibuja barandillas, balaustradas y antepechos (petos) igual que un muro: por puntos, por una cara o por el eje. Forma encuentros con los muros y **cierra recintos**, por ejemplo una terraza limitada por su barandilla. Empieza como barandilla de 0,05 m de espesor y 1,10 m de altura. Opciones:

- `Barandilla`, `baLaustrada` y `antePecho` cambian el tipo y sus valores de partida. El antepecho es macizo, de 0,15 m.
- `Huecos` fija la proporción de huecos del alzado, en %. En 3D, la barandilla se construye con pasamanos y montantes dentro de la misma huella que se ve en planta.
- `Altura`, `Espesor`, `Cota` y `Referencia` funcionan como en MURO. Si la altura no llega a 1,10 m, avisa de lo que pide el DB-SUA 1: 0,90 m si el desnivel no supera 6 m, y 1,10 m en los demás casos.

Una defensa va en la capa `ARQ-DEFENSAS` y no admite carpinterías. Es un muro con la categoría «Defensa», así que se edita con las mismas órdenes que un muro. Se exporta como `IfcRailing` (GUARDRAIL o BALUSTRADE); el antepecho, como `IfcWall` PARAPET.

| Opción | Efecto |
| --- | --- |
| `T` | Elige un tipo del catálogo (ver TIPOSMURO) |
| `E` / `A` / `C` | Espesor, altura y cota de la base |
| `R` | Referencia: eje, izquierda o derecha |
| `I` o `F5` | Invierte la cara por la que se dibuja |
| `G` | Toma espesor, altura, tipo y material de otro muro que se designa |

**Cotas temporales al dibujar.** Tras el primer punto, `MURO` muestra junto al tramo su longitud y su ángulo (`2,24 <0,0°`), en naranja, y en azul la distancia desde el extremo del tramo hasta la cara paralela más cercana de otro muro a cada lado. Escribir un número da la longitud del tramo en la dirección del cursor (la distancia directa de IngeCAD). Las cotas tienen el mismo tamaño en pantalla con cualquier zoom y no se dibujan.

**Encuentros al dibujar.** Si un muro termina en la cara **cercana** de otro, se forma una **T**. Si termina en la cara **alejada**, se forma una **L**: el otro muro se recorta y conserva su parte más larga. Al empezar un muro en una cara o en una esquina interior, el programa elige la cara que no invade el muro existente; `F5` lo corrige.

**Órdenes de edición.** Todas conservan la identidad BIM del muro y sus carpinterías, y se deshacen en un paso.

| Orden | Qué hace |
| --- | --- |
| `MUROPARALELO` | Muro paralelo a una cara o línea: distancia, línea base, lado de la paralela y lado del espesor. Un clic en vacío encadena otro paralelo desde la cara alejada del último |
| `ESTIRAMURO` | Alarga o acorta el extremo designado hasta un punto, una línea o la cara de otro muro (T o L) |
| `PIVOTAMURO` | Mueve un extremo; el otro queda fijo |
| `DIVIDEMURO` | Divide el espacio entre dos puntos en N partes iguales con muros perpendiculares; con `L` fija su longitud, sin ella llegan al muro de enfrente |
| `BORRATRAMO` | Borra el tramo de muro entre dos cruces (o entre un cruce y el extremo) |
| `PARTEMURO` | Abre un vano a toda altura entre dos puntos: el muro queda en dos |
| `UNIRMURO` | Une dos muros alineados del mismo espesor; el primero conserva su identidad y recibe las carpinterías del segundo |

Si una edición dejaría una carpintería fuera del muro, la orden se detiene y no cambia nada.

**Propiedades.** `PROPIEDADESARQ` abre la ficha BIM del muro, pilar, carpintería o recinto designado; se designa por su contorno, su símbolo o su rótulo. Los cambios conservan la identidad del elemento y se deshacen en un paso. `EDITARARQ` hace lo mismo y, sin ficha disponible, edita los datos del muro por la línea de órdenes.

## Muros curvos

Un muro curvo es el mismo muro BIM que uno recto: sus caras son arcos concéntricos y admite las mismas órdenes, carpinterías y recintos. Cada muro llega como mucho a media circunferencia; un muro redondo son dos medios círculos.

**MUROCURVO.**

1. Indique el punto inicial y el punto final del muro.
2. Indique un punto de paso de la curva, o escriba la flecha en metros (positiva a la izquierda del sentido de dibujo).
3. El siguiente muro curvo empieza donde acabó el anterior; `Intro` deja de encadenar. El ORTO no afecta al punto de paso; sí a los extremos.

`E`, `A`, `C` y `R` funcionan como en MURO. Al crear el muro se indican su radio y su desarrollo.

**Muro circular.** En MUROCURVO, escriba `O`, indique el centro y después un punto de la línea de referencia (o escriba el radio). Se crean dos medias circunferencias unidas por sus extremos.

**CURVAMURO** curva un muro existente. Designélo y haga clic en un punto de paso, o escriba la flecha. Con `0` se endereza. Los extremos no se mueven, así que sus encuentros se conservan. Sus carpinterías mantienen su ancho real y su posición relativa en el muro; si alguna deja de caber, la orden no se aplica.

**Edición de muros curvos.**

| Orden | En un muro curvo |
| --- | --- |
| `ESTIRAMURO` | Lo alarga o acorta siguiendo su circunferencia, hasta un punto o hasta el corte con una línea |
| `PIVOTAMURO` | Mueve un extremo y conserva el ángulo de arco |
| `BORRATRAMO` | Borra el tramo entre cruces con otros muros, rectos o curvos |
| `PARTEMURO` | Abre un vano; quedan dos muros curvos sobre la misma circunferencia |
| `UNIRMURO` | Une dos muros curvos de la misma circunferencia y espesor, si el resultado no pasa de media circunferencia |

**Precisión.** En planta las caras se dibujan como arcos verdaderos. Para los recintos, el 3D y el IFC se sustituyen por cuerdas que se separan del arco 1 mm como máximo.

## Convertir un plano de líneas: LINEASAMURO

`LINEASAMURO` convierte un plano antiguo dibujado con líneas en muros, puertas, ventanas y vanos BIM, con un solo `Deshacer`.

**Cuadro de clasificación (desde la 1.20).** Al lanzar `LINEASAMURO` se abre un cuadro con las capas del plano. Asigne cada capa a muros, medianeras, tabiques, pilares, puertas, ventanas, vanos, rejas, barandillas o escaleras, o déjela sin convertir. Con «Designar gráficamente en el plano» puede asignar objetos sueltos con clics (pulse Intro para volver al cuadro); esas asignaciones prevalecen sobre la capa. Después enmarque la zona: verá los ejes previstos y el recuento de muros, huecos y pilares sin que el dibujo cambie. Intro o «Confirmar» aplica la conversión; «Cancelar» la descarta. También se leen rellenos y rayados simples y la geometría de los bloques, sin explotarlos. Rejas, barandillas y escaleras se clasifican pero todavía no se convierten. La opción «Diálogo» vuelve a abrir el cuadro.

**Carpintería en una sola capa (desde la 1.20.1).** Si puertas y ventanas están en la misma capa, asígnela a **«Carpintería (puerta o ventana según el dibujo)»**: cada hueco se lee por lo que tiene dibujado. Un giro (arco o polilínea con curva) hace una puerta, de una o dos hojas, con su mano y su cara de apertura; las líneas de marco y vidrio dentro del espesor del muro hacen una ventana; sin nada dibujado, es un vano. No hace falta separar puertas y ventanas en capas. Asignar la capa a «Puertas» o a «Ventanas» es una orden: convierte **todos** sus huecos en ese tipo. Las excepciones que el dibujo no distingue (puertas correderas o balconeras sin arco, que se leerían como ventanas) se corrigen con «Designar gráficamente», asignando esas líneas a «Puertas». La primera vez, el cuadro propone la categoría de cada capa por su nombre (*pared*, *pilar*, *carp*, *escal*…; las de *cámara* y *cota* quedan sin convertir), y lista también las capas de las entidades que están dentro de bloques: si la planta es un bloque, cada línea se clasifica por su propia capa. La altura de las puertas (2,10 m) y la de las ventanas (1,20 m con antepecho de 0,90 m) son valores por defecto: ajústelas después con `PROPIEDADESARQ`.

**Antes de convertir (desde la 1.20.2).** El plano debe estar **a escala real y en metros**: un muro de 25 cm debe medir 0,25. Muchos planos antiguos están dibujados a otra escala (1/4, 1/5…). Si los giros de las puertas miden menos de 0,35, `LINEASAMURO` se detiene sin tocar el dibujo y propone el factor; escale el dibujo con `ESCALA` desde un punto y repita. Las capas **apagadas o inutilizadas no se leen**: apague las de mobiliario, textos, sanitarios, escaleras o referencias en lugar de borrarlas. En «Designar gráficamente» puede pulsar objetos uno a uno o, pulsando en vacío, abrir una **ventana**: hacia la derecha toma lo que queda dentro; hacia la izquierda, lo que toca. También se reconocen huecos en muros curvos (dos arcos concéntricos interrumpidos), con carpintería plana en la cuerda.

**Revisar la previsualización (desde la 1.20.3).** Antes de confirmar, la planta muestra cada hueco con su símbolo: las puertas con su giro, las ventanas con su vidrio y los vanos con una X. Compruebe sobre todo las puertas dobles, las puertas de los tabiques finos y los pasos abiertos entre machones. Lo que salga mal se corrige con «Designar gráficamente» antes de confirmar, o después con `PROPIEDADESARQ`.

**Puertas dobles, jambas y correderas (desde la 1.22.1).** Dos giros con bisagras opuestas que abren hacia el mismo lado forman una puerta de dos hojas, también si son desiguales. El ancho del hueco se mide entre las jambas dibujadas (con 5 mm de tolerancia), no por el radio del giro. Las hojas paralelas solapadas de una corredera pueden ser de puerta o de ventana: si el dibujo no lo aclara, la vista previa avisa y deja un vano; desígnelas como «Puertas» o «Ventanas». Lo mismo ocurre con la corredera de bolsillo. Los encuentros oblicuos en L, T o X se distinguen mejor de los huecos.

**Zona de lectura visible (desde la 1.22.2).** Al elegir la zona, se dibuja el rectángulo desde la primera esquina y se resaltan las líneas de las capas clasificadas que se van a leer: hacia la derecha, las que quedan dentro; hacia la izquierda, las que toca. En `TIPOSMURO` se ve el **espesor total** de cada tipo, suma de sus capas; la ficha del muro avisa si su espesor no coincide con el del tipo.

**Ventanas, correderas y armarios (desde la 1.22.3).** De cada ventana se lee el marco entre las jambas: profundidad y retranqueo respecto a la cara. El lado exterior sale del contorno del edificio o de un alféizar claro. Los arcos de giro reconocidos se retiran del dibujo original con la conversión. Las correderas de dos hojas aparcadas por fuera del muro se detectan, pero hay que confirmarlas como «Puertas». Los **armarios empotrados** tienen categoría propia (`ARQ-ARMARIOS`): por ahora su dibujo se conserva y en su zona no se corta el muro de lado a lado; el nicho BIM llegará más adelante. Las **escaleras** clasificadas se conservan como dibujo, con un aviso de cuántos objetos hay, hasta que exista la orden ESCALERA. En dibujos nuevos conviene separar capas: `ARQ-MUROS`, `ARQ-TABIQUES`, `ARQ-PUERTAS`, `ARQ-VENTANAS` y `ARQ-ARMARIOS`, que el cuadro reconoce; los tabiques se exportan como tabiques (`IfcWall` PARTITIONING). La capa de pilares se llama `ARQ-PILARES`, y `ARQMIGRAR` renombra la antigua `ARQ-PILAres`.

**Armarios empotrados con ARMARIOBIM (desde la 1.23).** Designe el muro o tabique anfitrión y rellene la ficha: ancho, fondo, altura, cota de base, número de hojas y apertura (corredera o abatible). El armario es un **nicho** que no atraviesa el muro: este conserva el espesor restante en planta, en 3D y en sus cantidades, y los frentes se exportan como puertas de armario. Si después reduce el espesor del muro, la orden avisa antes de que el nicho llegue a atravesarlo. En `LINEASAMURO` puede activar **rangos de espesor independientes** para muros, medianeras y tabiques, para que no se emparejen caras de categorías distintas.

1. Dibuje o importe el plano con líneas, polilíneas y arcos en capas que no empiecen por ARQ.
2. Ejecute `LINEASAMURO` y enmarque con dos clics la zona que quiere convertir.
3. Revise el resultado con `PROPIEDADESARQ` y `ARQVALIDAR`.

**Qué reconoce.**

- Dos líneas paralelas separadas un espesor de muro son las caras de un muro recto.
- Dos arcos concéntricos separados un espesor de muro son un muro curvo. Valen entidades ARC y tramos curvos de polilínea; si abarcan más de media circunferencia, se crean dos muros.
- Un hueco del tamaño de una carpintería en un muro recto es una puerta si tiene un giro dibujado, una ventana si tiene vidrio y un vano si no tiene nada.

**Opciones.**

| Opción | Efecto | Por defecto |
| --- | --- | --- |
| `E` | Espesor mínimo y máximo de muro | 0,07 y 0,50 m |
| `A` | Altura de los muros | 3,00 m |
| `O` | Qué hacer con las líneas de origen: ocultar (en la capa apagada ARQ-PLANO-ORIGEN), borrar o conservar | ocultar |
| `K / L / R` | Capas de las caras de muro, de los pilares y de la carpintería; se guardan en el dibujo | reconocidas por su nombre |
| `P` | Desviación admitida entre las dos caras de un muro antiguo | 0,005 m (0,03 en levantamientos) |

**Planos reales.** LINEASAMURO está pensado también para planos de estudio dibujados por capas:

- **Capas por nombre.** Reconoce las capas por su nombre: *pared* o *muro* para las caras, *pilar* para los pilares, *carp*, *puerta* o *ventana* para la carpintería. Las opciones `K`, `L` y `R` las fijan. Así, las escaleras, las cotas, el mobiliario y las líneas de cámara (capas con *cámara* o *aislamiento*) no se leen como muros.
- **Bloques.** Si la planta está dentro de un bloque, la lee sin modificarlo.
- **Medianeras.** Una medianera dibujada con su cara interior se cierra con la línea paralela más próxima de otra capa, normalmente el límite con el vecino.
- **Pilares.** Los dibujados como contorno cerrado se convierten en `PILAR`.
- **Líneas sin pareja.** Las líneas de muro que se quedan sin pareja no se ocultan: quedan seleccionadas para revisarlas o dibujar esos muros con `MURO`.

Las puertas se crean de 2,10 m de altura; las ventanas, de 1,20 m con antepecho de 0,90 m. Los muros se crean por su eje. Ajuste tipos, alturas y carpinterías después.

La lectura del plano usa el módulo libre `walldetect` del proyecto cad2ingetrazo (GPL-3.0), incorporado sin cambios.

**Entrada revisada (capas REV-\*).** Un plano preparado y revisado fuera de IngeCAD puede llegar con sus elementos en capas `REV-*` (por ejemplo `REV-MURO-CARA`, `REV-PUERTA`, `REV-VENTANA`) y, junto al DXF, un fichero de procedencia con el mismo nombre más `.procedencia.json` (para `plano.dxf`, `plano.dxf.procedencia.json`). Ese fichero declara el papel y el estado de cada capa REV-\* (y, si hace falta, de cada objeto), que el plano está en metros con la escala comprobada y que la revisión está terminada; lleva además la huella SHA-256 del DXF, de modo que cualquier cambio en el plano lo invalida.

- `LINEASAMURO` busca el fichero al empezar. También se carga con la opción `Procedencia` (y después la ruta) o desde el cuadro de clasificación, que muestra el estado de cada capa.
- Solo se convierten las **caras de muro, puertas y ventanas confirmadas**. Los ejes, y todo lo pendiente, rechazado o candidato, se quedan como dibujo.
- Si un muro tiene una interrupción sin puerta ni ventana confirmada, se conserva como dibujo y se avisa: el plugin no inventa el vano ni lo rellena.
- **Sin fichero de procedencia válido**, `LINEASAMURO` trabaja como siempre, pero las capas REV-\* no se reconocen por su nombre ni se usan como apoyo.
- La fuente original (croquis, foto o PDF) solo se cita por nombre; el plugin no la abre.

El contrato completo, con un ejemplo, está en `docs/ENTRADA_REVISADA.md` dentro del ZIP.

## Pilares

`PILAR` coloca pilares BIM (IfcColumn) que cortan los muros que atraviesan; los recintos los rodean.

**Secciones** (opción `S`):

| Escriba | Sección |
| --- | --- |
| `0,30x0,30` o `30x40` | Rectangular, en metros o en centímetros |
| `D0,35` | Circular de 0,35 m de diámetro |
| `IPE 200`, `IPN 160`, `HEA 200`, `HEB 160`, `UPN 120` | Perfil metálico |
| `2UPN 160 cajon` | Dos UPN en cajón |
| `2UPN 160 empresillado 0,10` | Dos UPN empresillados, separados 0,10 m |

**Colocación.**

- **Libre:** se coloca por uno de 9 puntos de enganche (`E` 1-9, como el teclado numérico; 5 es el centro). También se elige en la ficha del pilar, con un botón por esquina, por mitad de cara y para el centro. El punto se marca con las referencias a objetos de IngeCAD (extremo, punto medio, intersección, rejilla…).
- **`G`** gira 90°. **`A`** lo orienta solo según el muro o la línea bajo el cursor.
- **`P` a distancia de dos paramentos:** se designan dos caras de muro (o líneas) y se hace clic en la esquina; las caras del pilar quedan a las distancias indicadas. Es el caso habitual de fachada, con 0,05 m.
- **`U` a distancia de un paramento:** una cara y un punto a lo largo de ella.
- **`C` recubrimiento:** añade un forro alrededor de la sección. Un pilar aislado se recubre entero; si corta un muro, solo la parte que queda fuera de él, y el muro ocupa el resto. En el IFC, el revestimiento mide su superficie vista.

Cada pilar es un solo paso de `Deshacer`, con los muros y recintos ya actualizados. En el cálculo de superficie útil, los pilares de hasta 100 cm² de sección no se descuentan.

## Carpinterías: puertas, ventanas y huecos

`CARPINTERIA` inserta puertas (IfcDoor), ventanas (IfcWindow) y huecos sin carpintería en un muro o tabique. Cada una abre su hueco en el muro, en planta y en 3D, y lo acompaña si el muro se mueve. `PUERTAARQ`, `VENTANAARQ` y `HUECOARQ` son la misma orden con ese tipo de partida.

**Representación en planta.** Las puertas se dibujan con las jambas del cerco con su rebaje, la hoja con su grueso (4 cm) y el arco de giro. Las ventanas se dibujan con las jambas, los perfiles de cada hoja con su vidrio, la marca de encuentro entre hojas y el alféizar cerrando el hueco. Las correderas muestran sus carriles. El símbolo se regenera con la carpintería: si cambia el muro o la ficha, cambia el dibujo. En 3D, la carpintería se construye con sus piezas reales, a partir de los mismos datos: el marco (un anillo alrededor del hueco; en las puertas, con un umbral de 5 mm), las hojas donde cierran, los perfiles y el vidrio de cada hoja de ventana y el alféizar. Cada pieza lleva su material; el vidrio se ve translúcido en IngeTrazo.

**Ficha de carpintería.** Al empezar la orden se abre una ficha, como en MURO y PILAR, con el modelo que se va a insertar: tipo (puerta, ventana o hueco), apertura, hojas, hoja normalizada o a medida, segunda hoja, ancho del hueco, altura, antepecho, ajuste y medidas del cerco, remate, nombre, tipo, material y clase IFC. En las puertas muestra al momento el paso libre según el DB-SUA. Si se cancela, la orden termina. La opción `D` la vuelve a abrir durante la orden; las opciones de la tabla siguen sirviendo para cambios rápidos. A la derecha de la ficha, un dibujo del alzado y de la planta muestra el resultado mientras se define, y debajo se indican el paso libre y las piezas que tendrá en 3D. En la ficha se eligen también los materiales del marco, las hojas, el vidrio y el alféizar. Si el cerco no cabe en el hueco, la ficha lo explica y no deja aceptar.

**Editar una carpintería existente.** `PROPIEDADESARQ` sobre su símbolo abre la misma ficha, con su posición en el muro: distancia desde el inicio, cara hacia la que abre y bisagra. Conserva su identidad.

**Uso básico.** Haga clic en la cara del muro hacia la que abre la carpintería. En modo *Libre*, un segundo clic indica hacia dónde se extiende desde ese punto; `Intro` la extiende hacia el lado más largo. Si hace clic sobre una carpintería existente, se sustituye su modelo y se conserva su identidad.

**Cotas temporales.** Al pasar el cursor por un muro, `CARPINTERIA` muestra, sin dibujarlas, la distancia desde cada lado del hueco hasta la referencia más cercana de ese muro (el final del paramento libre o la jamba de otra carpintería) y, en la otra cara, el ancho del hueco. La cota **activa** va en naranja y las demás en azul. Escriba un número (`1,20`, `1.20` o `120cm`) y el hueco se coloca a esa distancia de la referencia activa, sin hacer clic. `F6` o la opción `Cota` pasa a la otra cota; `F4` o la opción `Eje` alterna entre medir hasta la jamba o hasta el centro del hueco. Si el hueco no cabe a esa distancia, no se crea nada y se avisa. Un número mayor de 30 sigue siendo el ancho de la hoja (`72` = hoja de 725 mm).

**MOVERCARP** mueve una carpintería ya colocada con las mismas cotas: designe la carpintería y escriba la distancia de la cota activa, o haga clic en el muro para llevar allí su centro. Conserva su identidad BIM y se deshace con un solo `Deshacer`. `Intro` suelta la carpintería para designar otra.

**Opciones.**

| Opción | Efecto |
| --- | --- |
| `P` / `V` / `H` | Puerta, ventana o hueco |
| `N` o un número | Ancho de hoja (puerta) o de hueco. `62`, `72`, `82`, `92` son las hojas de 625, 725, 825 y 925 mm; un valor mayor que 10 se lee en centímetros |
| `Hojas` | 1 o 2 hojas; `2 0,625` fija la hoja principal |
| `T` | Apertura: abatible o corredera (puertas); abatible, corredera o fija (ventanas) |
| `L` / `A` | Altura y antepecho |
| `M` | Colocación: Libre, Distancia *d* a la esquina, Centrada en la cara, Exterior (centrada en la otra cara), Máxima |
| `I` | Punto de inserción para la distancia: jamba (lateral) o centro (medio) |
| `C` | Ajuste del cerco en el espesor: interior, medio o exterior |
| `E` | Cerco: ancho y profundidad |
| `R` | Remate de ventana: alféizar, vierteaguas o ventanal |
| `B` / `S` | Invierte la bisagra o el sentido de la última carpintería |

**Valores de partida.** Puerta de una hoja de 825 mm, cerco de 3 cm (hueco de 0,885 m) y 2,10 m de altura. Ventana de 1,20 × 1,20 m, dos hojas abatibles, antepecho de 0,90 m y alféizar. Hueco de 0,90 × 2,10 m.

**Hojas y accesibilidad.** UNE 56803 normaliza las hojas de 625, 725 y 825 mm; la de 925 mm es una medida comercial y el programa lo avisa. Al crear una puerta se muestra su paso libre: el DB-SUA pide 0,80 m en el marco y 0,78 m con la hoja abierta para un itinerario accesible. El valor real depende del cerco del fabricante.

**En muros curvos** la carpintería es plana: va sobre la cuerda entre las dos jambas, que son radiales. El ancho que se indica es el de la carpintería (la cuerda). Si la curva es tan cerrada que el cerco no cabe en el espesor del muro, el programa lo avisa.

En planta, el símbolo (hoja y giro, cerco, vidrio, alféizar) se dibuja en la capa ARQ-CARPINTERIA y se agrupa con la carpintería.

## Niveles, categorías de muro y armarios

**Nivel activo.** La barra de herramientas Arquitectura muestra la capa activa, la lista de **niveles** y tres botones para el nivel elegido: **Encendido/Apagado**, **Utilizable/Inutilizado** y **Bloqueado/Desbloqueado**. Si la barra está oculta, actívela en el gestor de plugins. Los botones cambian las capas de ese nivel con las órdenes de capas de IngeCAD, y se deshacen con `Deshacer`. Si se cambia una de esas capas desde IngeCAD, el selector lo refleja; si las capas de un nivel no coinciden, indica «mixto» y no se pueden crear elementos en él hasta igualarlas. Con el nivel bloqueado, las órdenes del plugin no editan sus elementos, tampoco un muro que pase por él. Apagar o inutilizar solo afecta a la vista: la exportación conserva el modelo completo.

Las capas de cada nivel llevan `@` y una clave fija del nivel; su descripción tiene el nombre, que se puede cambiar sin afectarlas. Esta organización se activa desde `NIVELES`; abrir un dibujo no cambia sus capas. Con la barra oculta se usa la orden `NIVELES ESTADO <id> on|frozen|locked 0|1`.

**Categoría del muro.** `MURO`, su ficha y `TIPOSMURO` ofrecen **Fachada**, **Tabique**, **Medianera** y **Muro de sótano**, que van a las capas `ARQ-MUROS`, `ARQ-TABIQUES`, `ARQ-MEDIANERAS` y `ARQ-SOTANO`. Cambiar la categoría cambia la capa y conserva la identidad BIM. Al exportar, el tabique es `IfcWall` PARTITIONING; la fachada, USERDEFINED con ObjectType EXTERNALWALL; la medianera, USERDEFINED con PARTYWALL; y el muro de sótano, USERDEFINED con BASEMENTWALL, como los escribe un modelador IFC de referencia y como los piden los programas de cálculo energético. Fachada, medianera y sótano son exteriores (`IsExternal`), y medianera y sótano llevan su marca (medianera, contacto con el terreno). `LINEASAMURO` usa las mismas categorías. `ARQMIGRAR` asigna categoría a los muros antiguos y avisa para revisar medianeras y sótanos.

**Muro hasta un nivel.** Por defecto, el muro tiene **altura fija**, como siempre. En su ficha se puede elegir **Hasta un nivel**, con nivel base, nivel superior y un desfase en cada uno; la altura resultante se muestra sin poder editarla:

`altura = elevación superior + desfase de coronación − elevación base − desfase de base`

Si cambia la elevación de un nivel, se recalculan los muros, forjados y recintos afectados con un solo `Deshacer`. No se acepta una altura nula o negativa, un nivel eliminado ni un cambio que deje sin cabida a una carpintería. Un muro que atraviesa varias plantas se dibuja en cada una, y cada recinto toma solo su tramo. Las carpinterías de ese muro se sitúan respecto a su arranque: en una planta alta, indique el antepecho medido desde la base del muro.

**Armarios.** `ARMARIOBIM` crea por defecto un armario **adosado**: designe la cara del muro y la posición, y fije ancho, fondo, altura, material y hojas (abatibles o correderas). Ocupa planta delante del muro, **no lo corta**. Según el criterio de PARAMETROSARQ > General, «Armarios en la superficie útil», cuenta como superficie útil («Computan», por defecto: el Decreto 10/2019 de Extremadura solo descuenta tabiques y divisiones, pilares y conductos de más de 100 cm², el suelo de menos de 1,50 m de altura libre y la escalera; los armarios los trata como mobiliario) o se descuenta («Descuentan», como división interior fija). El espacio IFC del recinto llega siempre hasta los muros, con el armario dentro, como en CYPE: su generador del modelo analítico lo exige. El modo **Empotrado / nicho** es el anterior, y los armarios ya dibujados siguen como nichos. Un nicho en una fachada, medianera o muro de sótano quita espesor al muro y debilita su aislamiento térmico y acústico, así que ARMARIOBIM y la exportación avisan. Ambos modos requieren un muro recto. Se exporta como `IfcBuildingElementProxy` (tipo ARMARIO\_FIJO), porque IngeTrazo todavía no ofrece `IfcFurniture`, y sus frentes como `IfcDoor`. Actualice también el fichero de IngeTrazo junto con el plugin.

**Iconos y ficha de carpintería.** Todas las órdenes del menú tienen icono, y `LINEASAMURO` está justo antes de «Intercambio BIM». En la ficha de carpintería, la planta y el alzado se dibujan a la misma escala, sin solaparse, con las medidas al pie.

**Límite del IFC de IngeTrazo.** El exportador IFC oficial de IngeTrazo crea todavía una sola planta, relaciona mal los recintos y no transmite el tipo de muro, sus propiedades ni sus cantidades. La geometría es correcta y el fichero de IngeTrazo conserva todos los datos, pero el IFC aún no tiene la semántica completa. Se han propuesto a IngeTrazo las correcciones (norte, propiedades, tipos y plantas); este apartado cambiará cuando se publiquen.

## Recintos y superficies útiles

Un recinto (IfcSpace) se crea con un clic dentro de la estancia y sigue a los muros: si se mueve un muro, su contorno y su superficie se recalculan al regenerar.

**Ficha de recinto.** Al empezar RECINTO se abre una ficha para los recintos que se van a crear: nombre, número, uso, tipo (interior o exterior cubierto), altura libre, falso techo y nivel. La opción `D` la vuelve a abrir. Para cambiar un recinto existente, use `PROPIEDADESARQ` sobre su contorno o su rótulo.

**Clasificación normativa (desde la 1.21).** La ficha del recinto tiene un grupo con **una etiqueta por documento**: CTE DB SI (uso y ocupación), DB SUA 4 (alumbrado), DB SUA 9 (uso del recinto y unidad de uso accesible), DB HE, DB HE 3 (iluminación), DB HR (recinto protegido, habitable, de actividad…), DB HS 2, DB HS 3, DB HS 6 (radón) e ITC-BT-25 (puntos de utilización). Deje en «—» los que no apliquen. El botón **«Proponer según el uso (vivienda)»** rellena lo que se deduce del uso: un dormitorio es recinto protegido (DB HR), dormitorio en DB HS 3 y en la ITC-BT-25, habitable acondicionado (DB HE)… Revise la propuesta: en edificios que no son viviendas la clasificación depende de la actividad y la elige usted. Se guarda en el recinto, se cambia con `PROPIEDADESARQ` o con doble clic y se exporta en el grupo de propiedades `ARQ_ClasificacionCTE`. La clasificación **no comprueba el cumplimiento** de ninguna norma.

**Altura por envolvente y recinto por polilínea (desde la 1.25).** Si hay forjados, `RECINTO` calcula la altura libre por defecto: el suelo es la cara superior del forjado inferior y el techo, la cara inferior del forjado superior del nivel activo, o el falso techo si lo hay. Una cubierta inclinada sobre un forjado horizontal no recorta el recinto. Sin forjado superior se usa la altura de la ficha. La opción `Altura` fija una altura manual y `Envolvente` vuelve al cálculo. Los recintos anteriores conservan su altura manual. Si el forjado tiene huecos o no cubre todo el recinto, se calcula por zonas: la ficha muestra el límite superior, la altura libre **máxima** y el volumen neto exacto. La opción `Polilínea` dibuja el recinto punto a punto (puede ser cóncavo; sin arcos), con la longitud junto al cursor; Intro cierra, `Retroceder` quita el último punto y `Clic` vuelve a la detección por muros. Ese contorno sigue a la polilínea si se mueve o se editan sus vértices.

**RECINTO.** Haga clic dentro de una estancia cerrada por muros, tabiques o pilares. Opciones:

| Opción | Efecto |
| --- | --- |
| `N` Nombre | Nombre del siguiente recinto; si no se da, se numeran (Recinto 1, 2…) |
| `A` Altura | Altura libre |
| `F` Falso techo | Altura libre bajo el falso techo; `0` vuelve a «hasta el forjado». Se exporta un IfcCovering de techo |
| `T` Tipo | Interior o exterior cubierto (terraza, balcón, porche, galería, tendedero) |
| `U` Uso | Uso de la estancia (texto) |

**PARTICIONVIRTUAL (desde la 1.29).** Separa dos recintos que no tienen muro entre ellos, como la cocina abierta y el salón. Se dibuja por puntos, como una polilínea, e `Intro` termina. Conviene que empiece y acabe sobre un muro, en su cara o en su eje: si se queda corta, no separa nada. RECINTO la usa como borde, y la suma de las superficies de los dos lados es exactamente la de la estancia completa. Es una línea de trazos en la capa `ARQ-PARTICIONES-VIRTUALES`, del nivel activo, y se edita con las órdenes de IngeCAD (pinzamientos, DESPLAZA…): los recintos se rehacen solos. No tiene volumen ni aparece en 3D. En la exportación viaja como límite de los recintos, porque IngeTrazo todavía no escribe `IfcVirtualElement` en el IFC.

El rótulo muestra el nombre y la superficie útil, y «(computa X)» cuando la superficie computable es distinta.

**SUPERFICIES** escribe el cuadro de superficies en la línea de órdenes y lo dibuja en la planta, con la esquina superior izquierda en el punto que se indique. El cuadro tiene las columnas Nº, Recinto, Uso, superficie útil, coeficiente, superficie computable, altura y habitable, los totales y el criterio de cómputo, y va en la capa ARQ-CUADROS. La opción A actualiza en su sitio el cuadro ya dibujado y T cambia la altura del texto (0,20 m a escala 1:100). Dibujarlo se deshace en un paso. Aplica el Decreto 10/2019 de Extremadura (art. 2.3 y 2.4):

- **Superficie útil:** la cerrada por la cara interior de los cerramientos. No incluye tabiques ni puertas, ni pilares o conductos de más de 100 cm² de sección; los de hasta 100 cm² sí se cuentan.
- **Altura libre menor de 1,50 m:** no computa.
- **Espacio exterior cubierto** de 0,50 m de fondo o más: computa el 50 %; con menos fondo, nada.
- **Superficie útil habitable:** la de altura libre de al menos 2,50 m; en baños, aseos, vestíbulos, pasillos y distribuidores basta con 2,20 m (el tipo de estancia se reconoce por su uso o por su nombre, según las opciones generales).

El cuadro da la superficie útil interior, la de espacios exteriores al 50 %, la computable total y la habitable. Cada recinto exporta estos valores en el grupo de propiedades `ARQ_Recinto` del IFC.

**Normativa por defecto: Extremadura.** El cómputo de superficies aplica el Decreto 10/2019 de la Junta de Extremadura y, con él, que los armarios computan como superficie útil. La escalera interior, que el decreto descuenta, aún no se modela. La accesibilidad (Decreto 135/2018 de Extremadura, que remite al CTE DB-SUA para el interior de las viviendas) todavía no se comprueba.

## Cotas automáticas: COTAMUROS

`COTAMUROS` acota con dos clics:

- **A través de los muros.** Si la línea atraviesa muros, acota en cadena todas las caras, pilares y jambas que cruza.
- **Por fuera, junto a una fachada.** Si la línea va por fuera, paralela a una fachada y a menos de 3 m, acota las esquinas y los huecos de esa fachada. La línea de cota queda donde se dibujó.

Añade la cota total más allá de la cadena; la opción `O` la quita o la vuelve a poner. La opción `T` cambia la altura del texto (0,20 m a escala 1:100). La orden sigue pidiendo líneas hasta pulsar Intro, y cada línea se deshace en un paso.

Los puntos salen del mismo contorno que el modelo 3D, así que las cotas miden las caras reales. Son cotas normales de IngeCAD, que se editan con sus herramientas. Van en la capa `ARQ-COTAS` con el estilo `ARQ`: metros, dos decimales con coma y trazo oblicuo. No son asociativas: si se mueve un muro, hay que volver a acotar.

## Comprobaciones y reparación

Antes de exportar, ejecute `ARQVALIDAR`; si avisa de algo, `UNIONESARQ` suele repararlo.

| Orden | Qué hace | ¿Modifica el dibujo? |
| --- | --- | --- |
| `ARQVALIDAR` | Cuenta muros, pilares, huecos y segmentos y avisa de incidencias: líneas de contorno sin muro BIM (copiadas o movidas solas), contorno desactualizado, datos dañados | No |
| `UNIONESARQ` | Lee el dibujo, da identidad nueva a las copias, actualiza los datos BIM desde la geometría CAD y regenera contornos, símbolos y recintos | Sí, en un paso de `Deshacer` |
| `DIAGNOSTICOARQ` | Lista los encuentros L, T y X entre ejes de muros | No |
| `ARQMIGRAR` | Convierte muros de versiones anteriores del plugin a ejes BIM y regenera | Sí, en un paso de `Deshacer` |
| `ARQDIAG` | Muestra la versión cargada y el estado del plugin | No |

Que `ARQVALIDAR` no avise de nada no garantiza que el 3D o el IFC sean válidos: comprueba la integridad del dibujo y de sus datos, no la geometría final en IngeTrazo.

## Exportación a IngeTrazo e IFC

El modelo pasa a IngeTrazo como un fichero `.arqbim` que ya lleva la geometría 3D de cada elemento; IngeTrazo no la recalcula, solo la representa y la escribe en IFC.

**Comprobación antes de exportar.** `EXPORTARBIM` revisa antes el dibujo y busca:

- datos BIM ilegibles;
- elementos sin identidad o con la identidad de otro (una copia);
- puertas y ventanas sin muro;
- huecos que no caben en su muro o se solapan;
- medidas imposibles.

Si encuentra alguno, abre un cuadro con la lista. Al seleccionar un problema, sus elementos se resaltan en el dibujo. Usted decide entre exportar sin los elementos marcados o cancelar para corregirlos. `ARQVALIDAR` informa de lo mismo sin exportar.

1. En IngeCAD, ejecute `EXPORTARBIM` y elija dónde guardar el `.arqbim`. El dibujo debe estar en metros. Al terminar, el programa resume cuántos muros, pilares, puertas, ventanas, huecos y recintos ha exportado y el volumen construido.
2. En IngeTrazo, use *Importar arquitectura IngeCAD (.arqbim)…*. Cada elemento llega como un grupo con su clase IFC, nombre, identificador estable (GlobalId), planta, material, tipo, propiedades, cantidades y huecos. La extensión comprueba que cada sólido sea estanco y que su volumen coincida con el exportado; si algo falla, lo explica en un diálogo.
3. Guarde en IGZ: la definición arquitectónica completa viaja dentro del archivo y se conserva al volver a abrirlo.
4. Exporte a IFC desde IngeTrazo.

**Qué contiene el IFC.**

| Elemento | Clase | Datos destacados |
| --- | --- | --- |
| Muro | IfcWall | Longitud (desarrollada si es curvo), altura, espesor, volumen; capas del tipo; si es exterior (calculado) |
| Pilar | IfcColumn | Sección, perfil metálico y masa |
| Hueco | IfcOpeningElement | Vacío en su muro o forjado, con su tipo (hueco pasante o nicho) y sus medidas: ancho, alto y fondo (espesor del muro o canto del forjado); en un forjado no rectangular, su área |
| Puerta / ventana | IfcDoor / IfcWindow | Rellena su hueco; tipo de apertura; paso libre DB-SUA; piezas (marco, hojas, vidrio, alféizar) con su material |
| Recinto | IfcSpace | Superficie útil y computable, si es habitable, usos |
| Falso techo | IfcCovering | Placa de 15 mm bajo el techo del recinto |

**Estado.** Con la versión oficial actual de IngeTrazo, el IFC no relaciona aún las puertas y ventanas con su hueco ni escribe sus tipos de apertura, y coloca los recintos de una forma que el validador marca como error. Las correcciones están preparadas para proponerlas a su desarrollador. Con ellas, los modelos de prueba dan 0 errores en IfcOpenShell. La extensión valida el fichero completo antes de importarlo. Los modelos a más de 100 km del origen (coordenadas UTM) se desplazan cerca del origen con la misma regla que IngeTrazo aplica a cualquier fichero, y se avisa del desplazamiento.

**Volver a importar (desde la 1.20).** Si cambia el plano en IngeCAD, exporte de nuevo el `.arqbim` y vuelva a abrirlo en IngeTrazo: el modelo se **actualiza** en lugar de duplicarse. Los elementos se reconocen por su identificador BIM; los cambiados se sustituyen, los nuevos se añaden y los borrados se retiran, todo en un solo `Deshacer`. Copie en la carpeta de extensiones de IngeTrazo todo el contenido de `ingetrazo_ext`. Los modelos importados con versiones anteriores no se actualizan solos: bórrelos antes de la primera reimportación.

**Cambiar tipos desde IngeTrazo (desde la 1.30).** IngeTrazo puede proponer cambios, pero el edificio sigue definiéndose en IngeCAD:

1. En IngeTrazo, seleccione un muro, una puerta, una ventana o un armario importado. El panel **Propiedades de Arquitectura** muestra su clase, su tipo y sus medidas. Al seleccionar un muro, puede elegir también sus huecos.
2. Cambie el tipo, la apertura, las hojas, los materiales o los perfiles: el elemento se regenera al momento con el mismo código del plugin, en un solo `Deshacer` de IngeTrazo.
3. Los cambios que alteran la planta, como el espesor del muro, el tamaño o la posición de un hueco, la altura o la categoría, quedan **pendientes**: el modelo conserva la geometría anterior y el panel lo avisa. Se resuelven al volver a IngeCAD, que recalcula encuentros y recintos.
4. **Guardar como tipo** añade el tipo al catálogo propuesto.
5. **Exportar cambios a IngeCAD** escribe un fichero `.arqcambios` con lo propuesto.
6. En IngeCAD, `SINCRONIZARARQ` lee ese fichero y comprueba que el dibujo es el mismo. Si algo ha cambiado también en IngeCAD, lo muestra como **conflicto** y usted decide, elemento por elemento, qué conservar; por defecto se conserva lo de IngeCAD. Un dibujo distinto se rechaza. Todo se comprueba antes en una copia y se aplica en un solo `Deshacer`.
7. Exporte de nuevo con `EXPORTARBIM` y reimporte: los dos programas quedan iguales.

Para poder editarlos, los modelos exportados con versiones anteriores deben exportarse de nuevo. Los movimientos o ediciones libres hechos con otras herramientas de IngeTrazo no vuelven a IngeCAD.

## Niveles y forjados

`NIVELES` abre el catálogo de plantas (nombre y elevación en metros) y permite elegir el **nivel activo**, que reciben los muros, pilares y forjados nuevos. La primera vez que se confirma, los elementos existentes pasan a «Planta baja» sin cambiar sus cotas ni sus identificadores; abrir o leer un dibujo no lo cambia. `NIVELES MIGRAR` hace esa asignación sin diálogo. Renombrar un nivel conserva su identidad; cambiar su elevación desplaza los elementos asociados. No se puede eliminar una planta que tenga elementos. El nivel activo no oculta las demás plantas. `NIVELASIGNAR` pasa la selección a otro nivel, conservando su cota absoluta o alineándola con el nivel; las puertas siguen a su muro.

**Cota de un nivel.** La elevación de cada nivel es la **cara superior de su forjado estructural**, con el mismo criterio que CYPE: la altura de planta es la distancia entre las caras superiores de los forjados de dos plantas seguidas. El forjado o la solera de un nivel queda por debajo de su cota (por ejemplo, una solera de 0,40 m en «Planta baja» va de −0,40 a 0,00), y los muros, pilares y recintos arrancan en ella. Los solados no se modelan: la cota no es la del suelo terminado.

`FORJADO` crea un forjado **horizontal**: indique nombre, material, espesor y desfase de la **cara superior** respecto al nivel activo (el espesor crece hacia abajo). Dibuje el contorno en planta y pulse Intro; con la opción `Hueco` dibuje cada hueco y ciérrelo con Intro; otro Intro confirma todo. Esc cancela; `Retroceder` o `U` quita el último punto. Se admiten contornos cóncavos con huecos interiores que no se corten. `HUECOFORJADO` añade un hueco a un forjado existente. Desde la 1.34 cada forjado tiene clase: forjado entre plantas (se exporta como IfcSlab FLOOR), solera apoyada en el terreno (BASESLAB, exterior y en contacto con el terreno) o cubierta plana (ROOF, exterior); se elige en la ficha o, antes del primer punto, con las opciones Forjado, Solera o Cubierta. Las propiedades (nombre, material, clase, espesor, desfase, quitar huecos) se cambian con `PROPIEDADESARQ`. El sombreado del forjado guarda su contorno real: no lo borre como si fuera auxiliar. Los forjados inclinados, la cubierta y el falso techo llegarán más adelante.

Con niveles o forjados, el intercambio usa `.arqbim` v3 y necesita la extensión de IngeTrazo actualizada. IngeTrazo conserva los niveles y los identificadores en el IGZ, pero su IFC todavía escribe una sola planta «Storey» y no relaciona los huecos de forjado.

## Ejes estructurales (rejillas) y carpintería curva

**EJES** (o `REJILLA`) dibuja la malla de ejes de una vez: origen, ángulo y separaciones en cada dirección, como lista o en la forma `3x5,40 4,20` (tres vanos de 5,40 y uno de 4,20). Una dirección se numera (1, 2, 3…) y la otra con letras mayúsculas, saltando I, O y Ñ; después de Z siguen AA, AB… Admite prefijo y sufijo. Los ejes sobresalen del contorno, llevan burbuja (círculo o hexágono) con su identificador en uno o ambos extremos y van en la capa `ARQ-EJES`, en trazo y punto gris fino. La opción «Suelto» crea un eje por dos puntos. Se acotan solos (cadena y total) y las cotas se regeneran al mover un eje.

**Ficha de la rejilla (desde la 1.22.2).** Indique primero cuántos ejes hay en X y en Y; aparece una tabla con la distancia de cada vano, que puede ser distinta en cada uno, con el total de cada dirección y el botón «Todas iguales». Al aceptar, la malla completa sigue al cursor: pulse el punto de inserción (con referencias a objetos o escribiendo coordenadas) y, si lo desea, dé el giro. En `EDITAREJE`, la opción «Separaciones» cambia la distancia de un vano y desplaza los ejes siguientes junto con sus pilares, en un solo `Deshacer`.

**EDITAREJE** mueve un eje, cambia sus extremos y su burbuja o renumera desde él. **PILARESENEJES** coloca pilares de la sección elegida en todas las intersecciones o en las de una zona, en un solo `Deshacer`. Un pilar colocado en una intersección guarda su **marca** (por ejemplo `B-3`), que se ve en su ficha y se exporta; al mover el eje, sus pilares lo siguen. Si mueve ejes con órdenes genéricas de IngeCAD y algún pilar no los sigue, `ACTUALIZAEJES` los pone al día. IngeTrazo no admite todavía rejillas en el IFC: viajan como datos en el `.arqbim` y la marca del pilar aparece en su nombre (`[B-3]`).

**Carpintería en muros curvos.** La ficha de carpintería permite elegir **plana** (en la cuerda entre las jambas) o **curva**: la ventana fija, la ventana corredera y la puerta corredera siguen el arco del muro, con el mismo facetado en planta y en 3D. Las puertas y ventanas abatibles curvas no se admiten (aviso). El ancho y la posición se miden sobre el arco, por el eje o por una cara. La posición en el espesor admite también **«a distancia»**: un retranqueo desde la cara de apertura o la opuesta, que debe caber en el espesor. `CURVAMURO` conserva las carpinterías y su posición. El IFC de IngeTrazo todavía no conserva las dimensiones ni las relaciones de los huecos curvos.

## Referencia rápida de órdenes

`AYUDAARQ` abre un cuadro con todas las órdenes agrupadas por tema, un buscador y, al elegir una orden, sus opciones. Si no hay ventana, escribe la misma lista, ordenada, en la línea de órdenes.

| Orden | Para qué | Barra |
| --- | --- | --- |
| `MURO` | Muros rectos encadenados | Sí |
| `MUROCURVO` | Muro curvo por tres puntos o flecha; `O` circular | Sí |
| `CURVAMURO` | Curvar o enderezar un muro | No |
| `MUROPARALELO` | Muro paralelo a una cara o línea | Sí |
| `ESTIRAMURO` | Alargar o acortar un muro | Sí |
| `PIVOTAMURO` | Mover un extremo de muro | No |
| `DIVIDEMURO` | Dividir un espacio con muros iguales | No |
| `BORRATRAMO` | Borrar un tramo entre cruces | No |
| `PARTEMURO` | Abrir un vano y partir el muro | No |
| `UNIRMURO` | Unir dos muros alineados o de la misma circunferencia | No |
| `LINEASAMURO` | Convertir un plano de líneas | Sí |
| `PILAR` | Pilares de hormigón o metálicos | Sí |
| `CARPINTERIA` | Puertas, ventanas y huecos | Sí |
| `PUERTAARQ` / `VENTANAARQ` / `HUECOARQ` | CARPINTERIA con ese tipo | Sí |
| `RECINTO` | Espacio BIM con un clic | Sí |
| `SUPERFICIES` | Cuadro de superficies útiles | Sí |
| `COTAMUROS` | Cotas automáticas a través de los muros o de una fachada | Sí |
| `PROPIEDADESARQ` | Ficha BIM del elemento | Sí |
| `EDITARARQ` | Editar datos por línea de órdenes | No |
| `PARAMETROSARQ` | Valores de partida | No |
| `TIPOSMURO` | Catálogo de tipos de muro | No |
| `USOSARQ` | Usos del edificio | No |
| `BIBLIOTECAHE` | Biblioteca térmica: importar el catálogo de la Herramienta Unificada, buscar materiales y U de composiciones | No |
| `UNIONESARQ` | Sincronizar y regenerar | Sí |
| `ARQVALIDAR` | Validar el dibujo | Sí |
| `DIAGNOSTICOARQ` | Listar encuentros | No |
| `ARQMIGRAR` | Convertir dibujos de versiones anteriores | No |
| `EXPORTARBIM` | Exportar a IngeTrazo (.arqbim) | Sí |
| `ARQDIAG` / `AYUDAARQ` | Diagnóstico y ayuda | No |

**Órdenes heredadas.** El submenú «Herramientas antiguas (sin datos BIM)» reúne utilidades de versiones antiguas que dibujan geometría sin datos BIM y no se exportan al modelo: PUERTA, VENTANA, ARMARIO, CAMARA, ESCALERA, SUPERFICIE, BLOQUE, TRAMA, MEMORIACARP, VERTPOLY, LISTATEXTOS, SELATRIB, ELEMENTOS, HIPERVINCULO, CURVAS3D. Para el modelo BIM use las órdenes de la tabla.

## Limitaciones conocidas

Estas son las limitaciones conocidas de la versión 1.44.0-dev; cada versión actualiza esta lista.

- **Plataforma:** las pruebas automáticas se ejecutan en Linux con la última versión oficial de IngeCAD y de IngeTrazo, pero sin pantalla. Solo se prueba con la última versión de cada programa, porque ambos publican casi cada semana.
- **Muros curvos:** cada muro llega como mucho a media circunferencia (un muro redondo son dos). MUROPARALELO y DIVIDEMURO solo toman líneas rectas como referencia. El gesto de esquina en L al terminar un MURO solo recorta muros rectos.
- **Carpinterías:** en muros curvos son planas; no hay carpintería curva. Faltan armarios, memoria de carpintería, catálogo de modelos, lucernarios y borrar la carpintería dejando el vano.
- **LINEASAMURO:** no reconoce puertas ni ventanas en muros curvos. Las medianeras toman el espesor hasta la línea paralela más próxima de otra capa: revise su espesor.
- **Recintos:** una sola altura por recinto (no calcula descuelgues parciales); las escaleras no se descuentan todavía.
- **Edificio:** aún no hay plantas múltiples, forjados, escaleras ni barandillas. Las cotas de COTAMUROS no son asociativas: si se mueve un muro, hay que volver a acotar. Una simetría de un muro respecto de su propio eje no cambia su lado; para eso use la cara (I o F5) o su ficha.
- **IFC con IngeTrazo oficial:** ver *Exportación a IngeTrazo e IFC*.

## Novedades por versión

| Fecha | Versión | Novedades |
| --- | --- | --- |
| 19-11-2026 | 1.44.0-dev | Los muros envían al IFC su superficie de paramento bruta y neta (descontados los huecos), también en muros curvos y con puertas hasta el suelo |
| 19-11-2026 | 1.43.0-dev | Las herramientas antiguas (CURVAS3D, VERTPOLY...) preguntan como avisos de la orden, sin que reaparezcan avisos de otras órdenes; CURVAS3D aclara que ARQ-CURVAS3D es la capa del resultado |
| 19-11-2026 | 1.42.0-dev | PARAMETROSARQ vuelve a abrir su ficha (fallo de la 1.37); AYUDAARQ es un cuadro con las órdenes por temas, buscador y detalle, y ya incluye todas las órdenes del plugin |
| 19-11-2026 | 1.41.0-dev | Cada hueco viaja con su tipo (pasante o nicho) y sus medidas reales para el IFC; con la mejora de IngeTrazo, sale vinculado a su muro y a su puerta o ventana, y el modelo analítico de la plataforma de cálculo lo reconoce |
| 19-11-2026 | 1.40.0-dev | Nueva orden BIBLIOTECAHE: biblioteca térmica del usuario importada del catálogo de la Herramienta Unificada (no se distribuye con el plugin), búsqueda de materiales y U de composiciones |
| 19-11-2026 | 1.39.0-dev | Cada forjado lleva tipo IFC (por defecto, su clase y su canto: «Solera 20 cm»), que exige el modelo analítico de BIMserver.center |
| 19-11-2026 | 1.38.0-dev | Altura por defecto de muros y pilares: 3,00 m. Normativa por defecto, Extremadura: los armarios computan como superficie útil. Cota de nivel = cara superior del forjado estructural, como en CYPE (documentado) |
| 19-11-2026 | 1.37.0-dev | Armarios: el espacio IFC llega siempre hasta los muros, como en CYPE; la superficie útil descuenta o computa los armarios según el criterio elegido en PARAMETROSARQ; aviso al empotrar un armario en una fachada, medianera o muro de sótano |
| 19-11-2026 | 1.36.0-dev | Eje de los muros hacia el IFC: con las ampliaciones propuestas a IngeTrazo, cada muro recto tiene su propia orientación y las capas quedan bien situadas también en los muros girados. Corrección: los edificios girados en coordenadas UTM (lejos del origen) ya no dan sólidos abiertos al pasar a IngeTrazo |
| 19-11-2026 | 1.35.0-dev | Capas de material de los muros hacia el IFC: cada muro transmite su composición por capas y la posición de la primera capa respecto a su línea de referencia (eje, izquierda o derecha). Con las ampliaciones propuestas a IngeTrazo, el IFC lleva tipos compartidos y conjuntos de capas. Límite: en los muros girados, la dirección de las capas aún no es fiable |
| 19-11-2026 | 1.34.0-dev | Datos para el cálculo energético: norte del proyecto (PARAMETROSARQ > General), clase del forjado (forjado, solera o cubierta) y tipo IFC de los recintos (INTERNAL o EXTERNAL) |
| 19-11-2026 | 1.33.0-dev | Tipo IFC de los muros como en un IFC de referencia: fachada EXTERNALWALL, medianera PARTYWALL y muro de sótano BASEMENTWALL (USERDEFINED con ObjectType); el tabique sigue PARTITIONING |
| 18-11-2026 | 1.32.0-dev | Entrada revisada de LINEASAMURO: un DXF con su fichero de procedencia (plano.dxf.procedencia.json) convierte solo las caras, puertas y ventanas confirmadas; las capas REV-\* nunca se reconocen por su nombre |
| 18-11-2026 | 1.31.0-dev | Retirado el puente antiguo a IngeTrazo (EXPORTARIGZ, CONFIGIGZ) y las órdenes 3D experimentales MURO3D y HUECO3D; el paso a IngeTrazo es EXPORTARBIM con la extensión |
| 18-11-2026 | 1.30.0-dev | Cambiar tipos desde IngeTrazo con vuelta a IngeCAD (panel de propiedades, .arqcambios, SINCRONIZARARQ con conflictos); medidas negativas de carpintería rechazadas y señaladas en ARQVALIDAR; la extensión se instala copiando toda su carpeta |
| 18-11-2026 | 1.29.0-dev | DEFENSA (barandilla, balaustrada o antepecho; IfcRailing) y PARTICIONVIRTUAL (límite de recinto sin muro); guía del código y resúmenes en español en cada módulo |
| 17-11-2026 | 1.28.0-dev | Revisión general: planos grandes hasta seis veces más rápidos; el espesor escrito en MURO se lee en m, cm o mm y «3,4» es un punto; guardar y reabrir conserva el modelo BIM (prueba nueva) |
| 16-11-2026 | 1.27.0-dev | Iconos en todas las órdenes; selector de nivel con encendido, inutilizado y bloqueado; categoría del muro (fachada, tabique, medianera, sótano) con su capa; muro hasta un nivel con desfases; armario adosado; vista previa de carpintería a una sola escala |
| 16-11-2026 | 1.26.0-dev | Cotas temporales: CARPINTERIA muestra las distancias a las referencias del muro y coloca el hueco con la distancia escrita (F6 cambia de cota, F4 mide al eje); MOVERCARP mueve una carpintería con sus cotas; MURO muestra longitud, ángulo y distancia a los muros paralelos |
| 16-11-2026 | 1.25.0-dev | RECINTO con altura libre por envolvente (forjados y falso techo, por zonas) y recinto por polilínea |
| 16-11-2026 | 1.24.0-dev | Niveles (NIVELES, NIVELASIGNAR) y forjados horizontales con huecos (FORJADO, HUECOFORJADO); .arqbim v3 |
| 15-11-2026 | 1.23.0-dev | ARMARIOBIM: armario empotrado como nicho parcial; LINEASAMURO con retornos escalonados de fachada y rangos de espesor por categoría |
| 15-11-2026 | 1.22.3-dev | LINEASAMURO: marco y retranqueo de ventanas, arcos retirados, puerta junto a muro transversal, correderas exteriores, armarios y aviso de escaleras; capa ARQ-PILARES; cotas de rejilla fuera de las burbujas |
| 15-11-2026 | 1.22.2-dev | EJES con tabla de separaciones y punto de inserción; LINEASAMURO muestra y resalta la zona; espesor total de los tipos de muro |
| 14-11-2026 | 1.22.1-dev | LINEASAMURO: puertas dobles de dos hojas, ancho entre jambas, correderas ambiguas señaladas para designar y encuentros oblicuos |
| 14-11-2026 | 1.22.0-dev | Ejes estructurales (EJES, EDITAREJE, PILARESENEJES, ACTUALIZAEJES) con marca de pilar; carpintería curva en muros curvos; retranqueo de la carpintería a una distancia de la cara |
| 14-11-2026 | 1.21.0-dev | Clasificación normativa de los recintos: una etiqueta por documento del CTE y de la ITC-BT-25, propuesta según el uso y exportación en ARQ\_ClasificacionCTE |
| 14-11-2026 | 1.20.3-dev | LINEASAMURO reconoce mejor puertas dobles, tabiques finos cortados por los marcos, machones y entradas retranqueadas; previsualización con símbolos de puerta, ventana y vano |
| 14-11-2026 | 1.20.2-dev | LINEASAMURO: detecta planos que no están a escala real y propone el factor; no lee capas apagadas; designación con ventana; huecos en muros curvos; identificadores estables al Deshacer/Rehacer |
| 14-11-2026 | 1.20.1-dev | LINEASAMURO: categoría «Carpintería» para puertas y ventanas en una misma capa (las distingue el dibujo); la planta dentro de un bloque se clasifica por las capas de sus entidades; el cuadro propone categorías por el nombre de la capa; aviso si falta \_arqbim\_sync.py en IngeTrazo |
| 14-11-2026 | 1.20.0-dev | Reimportar un .arqbim en IngeTrazo actualiza el modelo sin duplicarlo (un solo Deshacer); LINEASAMURO con cuadro de clasificación por capas y clics, rellenos y bloques, previsualización y confirmación; fichas auxiliares de viga, pasamanos, barandilla y reja |
| 14-11-2026 | 1.19.0-dev | Puertas y ventanas en 3D con sus piezas (marco, hojas, perfiles, vidrio y alféizar) y su material; ficha de carpintería con dibujo del alzado y la planta, materiales por pieza y validación; aviso del DB-SUA reducido a lo que comprueba |
| 10-11-2026 | 1.18.0-dev | Tras la primera prueba en Windows: fichas de tipos de muro (TIPOSMURO y la ficha de MURO) y de usos del CTE (USOSARQ); punto de inserción del pilar en su ficha y referencias a objetos de IngeCAD al colocarlo; recubrimiento de pilares solo por fuera de los muros; ORTO sin efecto en el punto de paso de los muros curvos; carpintería más rápida y sin falsos «no cabe»; DXF en ASCII |
| 9-11-2026 | 1.17.0-dev | Auditoría independiente integrada: comprobación antes de exportar con elementos resaltados; órdenes de IngeCAD aceptadas; encuentros por alturas; extensión que valida el contrato y admite coordenadas UTM; LINEASAMURO para planos reales (capas, bloques, medianeras, pilares); opciones generales; con IngeCAD 0.8 (en desarrollo), sincronización inmediata, doble clic y F5 por la vía oficial |
| 9-11-2026 | 1.16.0-dev | La importación en IngeTrazo ya no falla en planos lejos del origen; SUPERFICIES dibuja el cuadro en la planta; COTAMUROS (cotas automáticas); símbolos de puertas y ventanas más detallados; menú «Herramientas antiguas»; pruebas también en Windows y dentro del ZIP |
| 7-11-2026 | 1.15.0-dev | Fichas de carpintería y de recinto; PROPIEDADESARQ y EDITARARQ editan carpinterías, huecos y recintos; EXPORTARBIM cuenta puertas, ventanas y huecos |
| 7-11-2026 | 1.14.1-dev | Corrige que MURO y las demás órdenes no crearan elementos en IngeCAD («No module named 'shapely'»); el plugin ya solo usa lo que instala IngeCAD |
| 7-11-2026 | 1.14.0-dev | Edición de muros curvos (estirar, pivotar, borrar tramo, partir, unir); CURVAMURO lleva las carpinterías; muro circular; LINEASAMURO reconoce arcos; sólidos estancos también en precisión simple; este manual |
| 7-11-2026 | 1.13.0-dev | Muros curvos (MUROCURVO, CURVAMURO) y carpinterías planas en ellos |
| 7-11-2026 | 1.12.0-dev | LINEASAMURO, USOSARQ, paso libre DB-SUA, altura habitable por tipo de estancia, iconos nuevos |
| 6-11-2026 | 1.11.0-dev | Superficie útil según el Decreto 10/2019 de Extremadura; SUPERFICIES |
| 6-11-2026 | 1.10.0–1.10.2-dev | Carpinterías en muros y tabiques; falsos techos; tipos IFC de carpintería |
| 6-11-2026 | 1.9.0-dev | Pilares embebidos y metálicos |
| 6-11-2026 | 1.7.0–1.8.1-dev | Herramientas de dibujo de muros; espesor total primero; tipos multicapa |
| 6-11-2026 | 1.6.2-dev | El muro se maneja como un objeto (grupos, sincronización) |

El detalle técnico de cada versión está en `CHANGELOG.md`, dentro del ZIP y del repositorio.

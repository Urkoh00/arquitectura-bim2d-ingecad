# Manual de Arquitectura para IngeCAD

Versión 1.18.0-dev · 10-11-2026

> Copia del manual publicado como documento en claude.ai; se regenera con cada versión.

## Qué es

Arquitectura es un plugin de IngeCAD para dibujar plantas en 2D en las que cada muro, pilar, puerta, ventana y recinto es desde el principio un objeto BIM, que se lleva a IngeTrazo y se exporta a IFC sin redibujar nada. Este manual corresponde a la versión **1.18.0-dev** y se actualiza con cada versión.

Cada elemento guarda su identidad persistente, su clase IFC, su geometría editable en planta, sus parámetros 3D (altura, espesor, cota), sus propiedades constructivas (tipo, material, capas) y su nivel. Las carpinterías conocen su muro y los recintos siguen a los muros que los cierran.

```
IngeCAD + plugin  ──EXPORTARBIM──▶  .arqbim  ──Importar .arqbim──▶  IngeTrazo (IGZ)  ──Exportar IFC──▶  IFC
 (planta 2D BIM)                 (sólidos 3D, datos)              (grupos BIM)
```

El plugin calcula una sola vez la huella final de cada elemento, con los encuentros resueltos y sin solapes; de ella salen el contorno en planta, los recintos, el sólido 3D y las cantidades. Es software libre (GPL-3.0) y experimental.

## Instalación

El plugin se instala copiando una carpeta en IngeCAD, y la extensión copiando un fichero en IngeTrazo. No hace falta instalar Python aparte.

**En IngeCAD**

1. Descomprima el ZIP de la versión, por ejemplo `Arquitectura_IngeCAD_v1.18.0-dev.zip`.
2. Copie la carpeta `arquitectura` en la carpeta de plugins de IngeCAD.
3. Reinicie IngeCAD. Aparece el menú *Arquitectura* y su barra de herramientas.
4. Escriba `ARQDIAG` en la línea de órdenes para comprobar que la versión cargada es la que acaba de copiar.

**En IngeTrazo**

1. Abra *Extensiones > Abrir carpeta de plugins*.
2. Copie en ella `ingetrazo_ext/arquitectura_bim.py`, que va dentro del ZIP.
3. Reinicie IngeTrazo. Aparece la orden *Importar arquitectura IngeCAD (.arqbim)…*.

**Para actualizar**, sustituya la carpeta `arquitectura` y el fichero de la extensión por los de la versión nueva. Los dibujos hechos con versiones anteriores se siguen leyendo. Si alguno se ve desactualizado, ejecute `UNIONESARQ`.

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
| ARQ-PILAres | Pilares | Sí |
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

**Con IngeCAD 0.8 o posterior (publicada el 10-11-2026)** el ajuste es inmediato. Tras la orden de IngeCAD, el plugin regenera el plano en el mismo paso de deshacer, sin necesidad de `UNIONESARQ`, y un solo `Deshacer` lo devuelve todo a como estaba. Con versiones anteriores, el ajuste se hace en la siguiente orden del plugin o con `UNIONESARQ`.

**Doble clic (IngeCAD 0.8 o posterior; con la 0.7, use EDITARARQ).** Al hacer doble clic sobre un elemento:

- **un muro** (cualquiera de sus líneas): arranca `MURO` con su espesor, altura, cota, cara, tipo y capas;
- **una puerta o ventana**: arranca `CARPINTERIA` con su modelo;
- **un pilar**: arranca `PILAR` con su sección;
- **un recinto**: abre su ficha.

Es la forma más rápida de seguir dibujando «como ese». En versiones anteriores de IngeCAD, la opción `G` de `MURO` y `PROPIEDADESARQ` hacen lo mismo.

**Selección.** Cada muro forma un grupo con su eje y sus líneas de contorno: al designar cualquiera de sus líneas se designa el muro entero. No borre ni mueva solo las líneas del contorno; `ARQVALIDAR` avisa si quedan líneas sin muro.

**Una sola geometría.** La planta, los recintos, el sólido 3D y el IFC salen de la misma huella calculada. Un encuentro correcto en planta es también correcto en 3D.

## Parámetros, tipos de muro y usos del edificio

Los valores por defecto, el catálogo de tipos de muro y los usos se guardan dentro del propio DXF; cambiarlos no modifica los elementos ya dibujados.

**PARAMETROSARQ** abre una ficha con los valores de partida: espesor 0,30 m, altura 2,70 m, cota 0 y referencia por el eje para los muros; pilar de 0,30 × 0,30 m; puerta de 2,10 m de altura; ventana de 1,20 × 1,20 m con antepecho de 1,00 m. Se deshace con `Deshacer`.

**Opciones generales.** La pestaña *General* de la misma ficha elige la forma de trabajar con el dibujo:

- **Trabajar con usos de recinto.** Si se activa, la ficha de recinto pide el uso y es el uso el que decide la clasificación; el nombre es libre y no la cambia. Si no se activa, la decide el nombre y la ficha no pide el uso. La clasificación determina, por ejemplo, la altura habitable de 2,20 m en baños y pasillos.
- **Cota mínima.** `COTAMUROS` no acota distancias menores que esta y las suma a la siguiente.

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

## Muros rectos

`MURO` dibuja muros encadenados como una polilínea; cada tramo es un muro BIM (IfcWall) con sus encuentros ya resueltos.

**MURO.** Antes del primer punto, un número se lee como el **espesor total** y el programa ofrece los tipos de muro que lo tienen. Después, un número es la longitud del tramo en la dirección del cursor. `Intro` empieza un tramo nuevo; otro `Intro` termina. Al empezar, la ficha de muro permite elegir un tipo del catálogo: muestra sus capas y fija el espesor; «Genérico» deja el espesor libre.

| Opción | Efecto |
| --- | --- |
| `T` | Elige un tipo del catálogo (ver TIPOSMURO) |
| `E` / `A` / `C` | Espesor, altura y cota de la base |
| `R` | Referencia: eje, izquierda o derecha |
| `I` o `F5` | Invierte la cara por la que se dibuja |
| `G` | Toma espesor, altura, tipo y material de otro muro que se designa |

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
| `A` | Altura de los muros | 2,70 m |
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

**Representación en planta.** Las puertas se dibujan con las jambas del cerco con su rebaje, la hoja con su grueso (4 cm) y el arco de giro. Las ventanas se dibujan con las jambas, los perfiles de cada hoja con su vidrio, la marca de encuentro entre hojas y el alféizar cerrando el hueco. Las correderas muestran sus carriles. El símbolo se regenera con la carpintería: si cambia el muro o la ficha, cambia el dibujo.

**Ficha de carpintería.** Al empezar la orden se abre una ficha, como en MURO y PILAR, con el modelo que se va a insertar: tipo (puerta, ventana o hueco), apertura, hojas, hoja normalizada o a medida, segunda hoja, ancho del hueco, altura, antepecho, ajuste y medidas del cerco, remate, nombre, tipo, material y clase IFC. En las puertas muestra al momento el paso libre según el DB-SUA. Si se cancela, la orden termina. La opción `D` la vuelve a abrir durante la orden; las opciones de la tabla siguen sirviendo para cambios rápidos.

**Editar una carpintería existente.** `PROPIEDADESARQ` sobre su símbolo abre la misma ficha, con su posición en el muro: distancia desde el inicio, cara hacia la que abre y bisagra. Conserva su identidad.

**Uso básico.** Haga clic en la cara del muro hacia la que abre la carpintería. En modo *Libre*, un segundo clic indica hacia dónde se extiende desde ese punto; `Intro` la extiende hacia el lado más largo. Si hace clic sobre una carpintería existente, se sustituye su modelo y se conserva su identidad.

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

## Recintos y superficies útiles

Un recinto (IfcSpace) se crea con un clic dentro de la estancia y sigue a los muros: si se mueve un muro, su contorno y su superficie se recalculan al regenerar.

**Ficha de recinto.** Al empezar RECINTO se abre una ficha para los recintos que se van a crear: nombre, número, uso, tipo (interior o exterior cubierto), altura libre, falso techo y nivel. La opción `D` la vuelve a abrir. Para cambiar un recinto existente, use `PROPIEDADESARQ` sobre su contorno o su rótulo.

**RECINTO.** Haga clic dentro de una estancia cerrada por muros, tabiques o pilares. Opciones:

| Opción | Efecto |
| --- | --- |
| `N` Nombre | Nombre del siguiente recinto; si no se da, se numeran (Recinto 1, 2…) |
| `A` Altura | Altura libre |
| `F` Falso techo | Altura libre bajo el falso techo; `0` vuelve a «hasta el forjado». Se exporta un IfcCovering de techo |
| `T` Tipo | Interior o exterior cubierto (terraza, balcón, porche, galería, tendedero) |
| `U` Uso | Uso de la estancia (texto) |

El rótulo muestra el nombre y la superficie útil, y «(computa X)» cuando la superficie computable es distinta.

**SUPERFICIES** escribe el cuadro de superficies en la línea de órdenes y lo dibuja en la planta, con la esquina superior izquierda en el punto que se indique. El cuadro tiene las columnas Nº, Recinto, Uso, superficie útil, coeficiente, superficie computable, altura y habitable, los totales y el criterio de cómputo, y va en la capa ARQ-CUADROS. La opción A actualiza en su sitio el cuadro ya dibujado y T cambia la altura del texto (0,20 m a escala 1:100). Dibujarlo se deshace en un paso. Aplica el Decreto 10/2019 de Extremadura (art. 2.3 y 2.4):

- **Superficie útil:** la cerrada por la cara interior de los cerramientos. No incluye tabiques ni puertas, ni pilares o conductos de más de 100 cm² de sección; los de hasta 100 cm² sí se cuentan.
- **Altura libre menor de 1,50 m:** no computa.
- **Espacio exterior cubierto** de 0,50 m de fondo o más: computa el 50 %; con menos fondo, nada.
- **Superficie útil habitable:** la de altura libre de al menos 2,50 m; en baños, aseos, vestíbulos, pasillos y distribuidores basta con 2,20 m (el tipo de estancia se reconoce por su uso o por su nombre, según las opciones generales).

El cuadro da la superficie útil interior, la de espacios exteriores al 50 %, la computable total y la habitable. Cada recinto exporta estos valores en el grupo de propiedades `ARQ_Recinto` del IFC.

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
| Hueco | IfcOpeningElement | Vacío en su muro |
| Puerta / ventana | IfcDoor / IfcWindow | Rellena su hueco; tipo de apertura; paso libre DB-SUA |
| Recinto | IfcSpace | Superficie útil y computable, si es habitable, usos |
| Falso techo | IfcCovering | Placa de 15 mm bajo el techo del recinto |

**Estado.** Con la versión oficial actual de IngeTrazo, el IFC no relaciona aún las puertas y ventanas con su hueco ni escribe sus tipos de apertura, y coloca los recintos de una forma que el validador marca como error. Las correcciones están preparadas para proponerlas a su desarrollador. Con ellas, los modelos de prueba dan 0 errores en IfcOpenShell. La extensión valida el fichero completo antes de importarlo. Los modelos a más de 100 km del origen (coordenadas UTM) se desplazan cerca del origen con la misma regla que IngeTrazo aplica a cualquier fichero, y se avisa del desplazamiento.

## Referencia rápida de órdenes

`AYUDAARQ` muestra esta lista en la línea de órdenes.

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
| `UNIONESARQ` | Sincronizar y regenerar | Sí |
| `ARQVALIDAR` | Validar el dibujo | Sí |
| `DIAGNOSTICOARQ` | Listar encuentros | No |
| `ARQMIGRAR` | Convertir dibujos de versiones anteriores | No |
| `EXPORTARBIM` | Exportar a IngeTrazo (.arqbim) | Sí |
| `ARQDIAG` / `AYUDAARQ` | Diagnóstico y ayuda | No |

**Órdenes heredadas.** El submenú «Herramientas antiguas (sin datos BIM)» reúne utilidades de versiones antiguas que dibujan geometría sin datos BIM y no se exportan al modelo: PUERTA, VENTANA, ARMARIO, CAMARA, ESCALERA, MURO3D, HUECO3D, SUPERFICIE, BLOQUE, TRAMA, MEMORIACARP, VERTPOLY, LISTATEXTOS, SELATRIB, ELEMENTOS, HIPERVINCULO, CURVAS3D y el puente antiguo CONFIGIGZ / EXPORTARIGZ. Para el modelo BIM use las órdenes de la tabla.

## Limitaciones conocidas

Estas son las limitaciones conocidas de la versión 1.18.0-dev; cada versión actualiza esta lista.

- **Plataforma:** las pruebas automáticas se ejecutan en Linux y en Windows con IngeCAD oficial (las versiones 0.7.0 y 0.8.0), pero sin pantalla. El usuario probó la v1.17 en Windows 10 con IngeCAD 0.8 e IngeTrazo 0.6.1: la cadena hasta el IFC funcionó; las correcciones de la v1.18 salen de esa prueba.
- **Muros curvos:** cada muro llega como mucho a media circunferencia (un muro redondo son dos). MUROPARALELO y DIVIDEMURO solo toman líneas rectas como referencia. El gesto de esquina en L al terminar un MURO solo recorta muros rectos.
- **Carpinterías:** en muros curvos son planas; no hay carpintería curva. Faltan armarios, memoria de carpintería, catálogo de modelos, lucernarios y borrar la carpintería dejando el vano.
- **LINEASAMURO:** no reconoce puertas ni ventanas en muros curvos. Las medianeras toman el espesor hasta la línea paralela más próxima de otra capa: revise su espesor.
- **Recintos:** una sola altura por recinto (no calcula descuelgues parciales); las escaleras no se descuentan todavía.
- **Edificio:** aún no hay plantas múltiples, forjados, escaleras ni barandillas. Las cotas de COTAMUROS no son asociativas: si se mueve un muro, hay que volver a acotar. Una simetría de un muro respecto de su propio eje no cambia su lado; para eso use la cara (I o F5) o su ficha.
- **IFC con IngeTrazo oficial:** ver *Exportación a IngeTrazo e IFC*.

## Novedades por versión

| Fecha | Versión | Novedades |
| --- | --- | --- |
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

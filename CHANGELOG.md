# Arquitectura para IngeCAD v1.6.0-dev — motor de nodos y huella única 2D/3D (EXPERIMENTAL)

Fecha: 5-11-2026. Base: v1.5.1. Distribución de ensayo: no sustituye la versión de trabajo.

## 1.18.0-dev — 2026-11-10

Responde a la primera prueba del usuario con IngeCAD 0.8 e IngeTrazo 0.6.1 en Windows 10: la cadena completa
funcionó (dos IFC sin errores de validación). Corrige lo que señaló y añade las fichas que pidió.

### Fichas
- **TIPOSMURO** sin argumentos abre el catálogo de tipos de muro del dibujo: cada tipo con sus capas (espesor
  y material, desde la cara dibujada), su espesor total, nuevo, duplicar, eliminar y ordenar capas.
- **La ficha de MURO** elige el tipo del catálogo y muestra sus capas; el espesor sale de ellas. Si luego se
  cambia el espesor a mano, el muro deja de llevar unas capas que ya no suman.
- **USOSARQ** sin argumentos abre la ficha de usos del edificio: certificado energético, DB-HE (con carga y
  horario en «otros usos») y DB-SI/DB-SUA.
- **El uso del recinto** se elige de una lista de usos habituales, o se escribe.
- **La ficha de PILAR** elige el punto de inserción (cuatro esquinas, mitad de las caras o centro, como el
  teclado numérico), el recubrimiento y el perfil metálico.
- Las órdenes cuelgan sus fichas de la ventana de IngeCAD. Antes solo lo hacían las herramientas: el cuadro de
  problemas de EXPORTARBIM y la ficha de recinto al hacer doble clic no llegaban a abrirse.

### Correcciones
- **PILAR usa las referencias a objetos de IngeCAD** (extremo, punto medio, intersección, rejilla...) al
  colocar el pilar. Antes la herramienta se declaraba «de designación» y recibía el cursor sin forzar; ahora
  solo lo es mientras pide caras de muro (opciones P y U).
- **Recubrimiento de pilares**: un pilar aislado se recubre entero; uno que corta un muro, solo por la parte
  que queda fuera de él. Los muros recuperan la parte del recubrimiento que quedaba dentro. La superficie del
  IfcCovering es ahora la superficie vista (caras al aire por la altura); el área en planta va en
  ARQ_Recubrimiento.
- **MUROCURVO y CURVAMURO con el ORTO activo**: el punto de paso del arco ya no se fuerza a la recta de los
  extremos, que daba un muro recto o un error. Se usa `Tool.ortho_applies` de IngeCAD.
- **Carpintería más rápida**: con el plano de la prueba (11 muros, dos curvos y cuatro pilares) el análisis
  de la vista previa pasa de 0,66 s a 0,14 s, y colocar una puerta, de unos 2 s a 0,3 s. Mismo resultado:
  cajas envolventes antes de intersecar, puntos ordenados al partir aristas y triangulación que solo prueba
  vértices cóncavos.
- **Falso «no cabe»** al colocar una puerta cuando la cara opuesta del muro estaba partida por un pilar u otro
  muro: se tomaba el tramo más largo de esa cara y no el que queda enfrente del clic.
- **Codificación del DXF**: los parámetros del dibujo se guardaban con acentos sin escapar en un DXF que se
  declara ANSI_1252. Ahora el DXF es todo ASCII.

### IngeTrazo (registro T-06, sin enviar)
- La medición (metrado) de un muro curvo en IngeTrazo es la superficie de su huella, no la de su paramento:
  IngeTrazo mide el muro por su cara mayor, y un muro curvo son muchas caras pequeñas. Además sustituye las
  cantidades exactas que envía el plugin (longitud 16,62 m pasa a 0,62 m). Se documenta; no se envía hasta que
  respondan #1221 y #1222.

## 1.17.0-dev — 2026-11-09

Integra la auditoría independiente de la v1.15 (25 hallazgos), con las decisiones del usuario: el plugin
funciona siempre con IngeCAD e IngeTrazo oficiales, nada se bloquea sin explicación y las órdenes de
IngeCAD se aceptan.

### Comprobación antes de exportar
- EXPORTARBIM revisa el dibujo antes de escribir el modelo:
  - datos BIM ilegibles;
  - elementos sin identidad o con identidad copiada (también recintos);
  - puertas y ventanas sin muro;
  - huecos que no caben o se solapan;
  - medidas imposibles.
- Si encuentra algo, abre un cuadro con la lista. Al seleccionar un problema se resaltan sus elementos en el
  dibujo. El operador decide entre exportar sin ellos o cancelar y corregir. Antes, esos elementos se perdían
  sin aviso o se exportaba un modelo con identidades repetidas.
- ARQVALIDAR informa de lo mismo.
- Hallazgos de la auditoría: ARQ-AUD-0001, 0005, 0013 y 0024.

### Órdenes de IngeCAD sobre elementos BIM
- Mover, girar, escalar, simetría y copiar funcionan con el IngeCAD oficial y sin parches. Cada elemento lleva
  un marco de referencia invisible que IngeCAD transforma con él. Al regenerar o exportar, el plugin lee la
  transformación y ajusta los datos BIM:
  - espesores y capas de los muros;
  - sección de los pilares;
  - lado del muro y cara hacia la que abre la puerta (en la simetría);
  - punto interior del recinto.
- Nada se rechaza. Lo que no se puede representar exactamente se avisa: un perfil metálico escalado pasa a
  sección rectangular genérica.
- Hallazgos de la auditoría: ARQ-AUD-0003, 0015, 0021 y 0022.

### Geometría e historial
- Los encuentros se resuelven por bandas de altura: dos muros que no comparten altura no se recortan (0002).
- La curvatura de un muro se toma del dibujo (0004).
- Áreas y volúmenes no dependen de la distancia al origen (0016).
- Una regeneración que falla no deja restos (0006).
- Rehacer no acumula contornos (0023).

### Extensión de IngeTrazo
- Valida el contrato entero antes de importar (0012):
  - identidades y GlobalId únicos;
  - sólidos cerrados;
  - huecos dentro de su muro;
  - relaciones hueco–relleno;
  - cada clase solo con sus atributos (por ejemplo, un recinto no puede llevar capas de muro).
- Las coordenadas lejanas siguen la regla oficial de IngeTrazo (`formats/recenter.py`): a más de 100 km, el
  modelo se desplaza cerca del origen en metros enteros, se avisa y se guarda el desplazamiento. Un segundo
  modelo usa el mismo desplazamiento.
- Si IngeTrazo ofrece importar geometría y datos en un solo paso, se usa; si no, se importa como hasta ahora.
- La definición guardada conserva la planta y las capas de material (0014).
- Probado con IngeTrazo 0.6.1 oficial con 12 modelos (el plano del usuario, coordenadas UTM, 3 km, 100 huecos,
  muros curvos…): 0 errores en IfcOpenShell. El IFC de IngeTrazo oficial todavía no escribe los huecos ni sus
  relaciones; las propuestas para IngeTrazo están preparadas.

### LINEASAMURO para planos reales
Probado con el plano 563 del usuario.
- Reconoce las capas por su nombre: muros (pared/muro), pilares y carpintería. Las opciones `K`, `L` y `R` las
  fijan y quedan guardadas en el dibujo. Escaleras, cotas y cámaras ya no se leen como muros.
- Lee las plantas que están dentro de un bloque, sin modificarlo.
- Reconoce las medianeras dibujadas con una sola cara: las cierra con la línea paralela más próxima de otra
  capa, normalmente el límite con el vecino.
- Los pilares dibujados como contorno cerrado pasan a PILAR.
- La opción `P` fija la tolerancia de paralelismo para muros antiguos.
- Las líneas de muro que se quedan sin pareja no se ocultan: quedan seleccionadas para revisarlas.

### IngeCAD 0.8: lo oficial, cuando existe
IngeCAD 0.8.0, todavía en desarrollo (la versión publicada es la 0.7.0), incorpora lo que este plugin había
pedido. Se usa cuando está presente; con IngeCAD 0.7, la versión instalable hoy, todo sigue como antes y está
probado.
- **Reactores.** Tras mover, girar, escalar, hacer una simetría o copiar con IngeCAD, el plano se regenera
  solo, en el mismo paso de deshacer; ya no hace falta `UNIONESARQ`.
- **Doble clic.** Sobre un muro arranca MURO con sus propiedades; sobre una carpintería, CARPINTERIA con su
  modelo; sobre un pilar, PILAR con su sección; sobre un recinto, abre su ficha.
- **F5.** Llega a MURO por la vía oficial (`Tool.on_key`); el atajo provisional queda solo para versiones
  anteriores. Con IngeCAD 0.8 los dos a la vez cambiaban la cara dos veces: era el fallo de la integración
  continua.
- **Selección.** La selección y el encuadre de los elementos con problemas usan las funciones oficiales.

### Opciones generales (PARAMETROSARQ, pestaña General)
- Trabajar con usos de recinto (0025): con usos, la ficha pide el uso y es el uso el que clasifica el recinto;
  sin usos, lo clasifica el nombre.
- Cota mínima de COTAMUROS.

## 1.16.0-dev — 2026-11-09

### Corregido
- **La importación en IngeTrazo fallaba** con «Volumen distinto … 0.278689 != 0.278775» en un plano real
  situado a unos 35 m del origen. IngeTrazo 0.6.1 calcula el volumen con números de 32 bits en
  coordenadas absolutas y, lejos del origen, pierde unas décimas de litro. La extensión ahora:
  - exige a IngeTrazo solo que cada sólido sea estanco;
  - comprueba el volumen con su propio cálculo de 64 bits, referido a un vértice del sólido;
  - muestra el error en un diálogo si la importación falla, en vez de cerrarse en silencio.

  Probado con el plano del usuario (`Pruebadwg.arqbim`) en IngeTrazo 0.6.1 sin cambios: 23 elementos,
  todos estancos, e IFC escrito. Anotado como T-01 en `docs/REGISTRO_UPSTREAM.md`.

### Añadido
- **SUPERFICIES dibuja el cuadro de superficies en el plano**, en el punto que se indique. Columnas: Nº,
  Recinto, Uso, superficie útil, coeficiente, superficie computable, altura y si es habitable. Incluye los
  totales y el criterio de cómputo.
  - Se dibuja en la capa `ARQ-CUADROS`. `A` actualiza el cuadro existente en su sitio y `T` cambia la
    altura del texto.
  - Se crea y se deshace en una sola operación.
- **COTAMUROS: cotas automáticas.** Se dibuja una línea con dos clics:
  - si atraviesa los muros, acota en cadena todas las caras, pilares y jambas que cruza;
  - si va por fuera y paralela a una fachada, acota sus esquinas y sus huecos.

  Añade la cota total; la opción `O` la quita. Los puntos salen del mismo contorno que el modelo 3D.
  Son cotas normales de IngeCAD en la capa `ARQ-COTAS`, con el estilo `ARQ` (metros, dos decimales con
  coma y trazo oblicuo).
- **Símbolos de carpintería más detallados en planta:**
  - puertas con jambas de cerco con rebaje y hoja dibujada con su grueso;
  - ventanas con perfiles de hoja, vidrio, marca de encuentro entre hojas y alféizar cerrado;
  - correderas con sus carriles.
- **Pruebas en Windows.** La integración continua pasa las pruebas también en Windows. Es una prueba sin
  pantalla, no la del IngeCAD instalado, que sigue pendiente.

### Cambiado
- **Menú.** Las órdenes que dibujan sin datos BIM se han pasado al submenú «Herramientas antiguas (sin
  datos BIM)»: PUERTA, VENTANA, MURO3D, ESCALERA, TRAMA y otras. Los submenús principales son
  Construcción, Documentación e Intercambio BIM, y solo contienen órdenes BIM.
- **El ZIP de la versión incluye las pruebas** (`tests/`), `scripts/` y `docs/`, con las propuestas
  enviadas a IngeCAD e IngeTrazo. Así, quien instala desde el ZIP puede pasar `python -m pytest -q`.

## 1.15.0-dev — 2026-11-07

### Añadido
- **Ficha de carpintería.** CARPINTERIA, PUERTAARQ, VENTANAARQ y HUECOARQ abren al empezar una ficha, como
  MURO y PILAR. La ficha recoge:
  - el tipo (puerta, ventana o hueco), la apertura y el número de hojas;
  - la hoja, con las medidas UNE 56803 o la comercial de 925 mm, y la segunda hoja;
  - el ancho del hueco, la altura, el antepecho, el ajuste del cerco, el cerco y el remate;
  - el nombre, el tipo, el material y la clase IFC.

  En las puertas muestra al momento el paso libre según DB-SUA. La opción `D` la vuelve a abrir.
- **Ficha de recinto.** RECINTO abre al empezar una ficha con el nombre, el número, el uso, si es interior
  o exterior cubierto, la altura libre, el falso techo y el nivel. La opción `D` la vuelve a abrir.
- **PROPIEDADESARQ y EDITARARQ reconocen carpinterías, huecos y recintos.** Se designan por su símbolo, su
  portador, su contorno o su rótulo, y se editan en su ficha conservando su identidad.
  - Una carpintería puede cambiar de modelo, de medidas y de posición.
  - En un muro curvo, el ancho de la carpintería es el plano.
- EXPORTARBIM informa también de cuántas puertas, ventanas y huecos ha exportado. Antes solo contaba muros,
  pilares y recintos, aunque las carpinterías ya se exportaban.

## 1.14.1-dev — 2026-11-07

### Corregido
- **MURO no creaba ningún tramo en IngeCAD** («No module named 'shapely'»). El cálculo de superficie útil,
  añadido en la v1.11, usaba la biblioteca shapely, que IngeCAD no instala. Como se ejecuta en cada
  regeneración, fallaba cualquier orden que creara o cambiara un elemento. Las pruebas no lo detectaron
  porque su entorno sí tiene shapely. Ahora ese cálculo usa solo Python (casco convexo y rectángulo mínimo).
- Pruebas nuevas (`tests/test_sin_dependencias.py`):
  - el código del plugin y de la extensión solo puede importar la biblioteca estándar, IngeCAD y lo que
    instala su `requirements.txt`;
  - una sesión completa (muros, pilar, muro curvo, ventana, recinto, SUPERFICIES y exportación) se ejecuta
    con shapely bloqueado.

## 1.14.0-dev — 2026-11-07

### Añadido
- **Manual de uso** (`docs/MANUAL.md`, también en el ZIP): se actualiza con cada versión. Una prueba
  comprueba que corresponde a la versión del plugin y que documenta todas las órdenes de la barra.
- **Edición de muros curvos:**
  - ESTIRAMURO los alarga o acorta siguiendo su circunferencia, hasta un punto o hasta el corte con una línea;
  - PIVOTAMURO mueve un extremo y conserva el ángulo de arco;
  - BORRATRAMO borra el tramo entre cruces con muros rectos o curvos;
  - PARTEMURO abre un vano y deja dos muros sobre la misma circunferencia;
  - UNIRMURO une dos muros curvos de la misma circunferencia.
- **CURVAMURO con carpinterías:** al curvar o enderezar un muro, sus puertas y ventanas conservan su ancho
  real y su posición relativa. Si alguna deja de caber, no se aplica nada.
- **Muro circular:** opción `O` de MUROCURVO, con centro y punto o radio. Son dos medias circunferencias.
- **LINEASAMURO reconoce arcos:** dos arcos concéntricos (ARC o tramos curvos de polilínea) separados un
  espesor de muro son un muro curvo.

### Corregido
- Sólidos 3D: los vértices separados menos de 1 µm se funden en uno. Una jamba que caía a una fracción de
  micra de un vértice de una cara curva dejaba dos puntos que la precisión simple de IngeTrazo fundía, y el
  muro dejaba de ser estanco (encontrado con una ventana en un muro circular). Lo cubre una prueba.
- ARQVALIDAR distingue los arcos por su punto medio. Las dos mitades de un muro circular comparten
  extremos y se contaban como líneas sobrantes.
- La ayuda (AYUDAARQ) mostraba «v0.8»; ahora muestra la versión real, definida en un solo sitio.

### Limitaciones conocidas
- MUROPARALELO y DIVIDEMURO solo toman referencias rectas.
- El gesto de esquina en L al terminar un MURO solo recorta muros rectos.
- LINEASAMURO no reconoce puertas ni ventanas en muros curvos.

## 1.13.0-dev — 2026-11-07

### Añadido
- **Muros curvos.** Un muro curvo es el mismo muro BIM que uno recto, con su curvatura (`bulge`) en el
  registro y en el eje CAD (un arco de polilínea). Sus caras son arcos concéntricos verdaderos.
  - El motor de encuentros los resuelve con los mismos tres pasos que los rectos. Las esquinas se calculan
    donde se cruzan de verdad las caras: recta con circunferencia o dos circunferencias. Valen para L, T
    contra un muro curvo, cruces, nudos de tres muros y referencia por una cara.
  - La huella se sigue en cuerdas de 1 mm como máximo. Planta, recintos, 3D e IFC usan los mismos polígonos.
  - En planta las caras curvas se dibujan como arcos (ARC). ARQVALIDAR las compara igual que las rectas.
  - Los recintos se cierran contra caras curvas, con su superficie.
  - El IFC lleva la longitud desarrollada y, en los parámetros, el radio y el centro.
  - **MUROCURVO** dibuja un muro curvo: punto inicial, punto final y punto de paso (o la flecha en metros).
    Encadena el siguiente muro desde el final.
  - **CURVAMURO** curva un muro existente por un punto de paso o una flecha. Con 0 lo endereza.
    Sus extremos, y por tanto sus encuentros, no cambian.
  - Una simetría u otra edición del eje en IngeCAD se recoge en UNIONESARQ y en el reactor: el dibujo manda.
- **Carpinterías en muros curvos:** puertas, ventanas y huecos.
  - El hueco tiene jambas radiales y caras curvas, en planta, en 3D y en el vacío IFC.
  - La carpintería es plana y va sobre la cuerda entre sus jambas, dentro de la banda que es muro en las
    jambas y en el centro. Si no cabe un cerco plano en el espesor, se avisa.
  - El ancho que se pide es el de la carpintería (la cuerda); el registro guarda además su desarrollo
    sobre el muro.
- Iconos MUROCURVO y CURVAMURO; MUROCURVO entra en la barra.

### Limitaciones conocidas
- Hasta media circunferencia por muro: no hay muros circulares completos.
- ESTIRAMURO, PIVOTAMURO, BORRATRAMO, PARTEMURO y UNIRMURO aún no trabajan con muros curvos (lo dicen
  al designarlos). Un muro con carpinterías no se curva.
- LINEASAMURO no reconoce todavía arcos como caras de muro.

## 1.12.0-dev — 2026-11-07

### Añadido
- **LINEASAMURO**: convierte las líneas de un plano antiguo (dos clics enmarcan la zona) en muros con su
  espesor, y los huecos con giro o acristalamiento dibujados en puertas, ventanas o vanos, en un solo paso
  de deshacer. Las líneas de origen pasan a la capa apagada ARQ-PLANO-ORIGEN (o se borran / conservan).
  Lectura geométrica de `cad2ingetrazo` (GPL-3.0-or-later), incorporada sin cambios en `arquitectura/vendor/`.
- **USOSARQ**: tres clasificaciones independientes del edificio: tipo para la certificación energética,
  uso DB-HE (residencial / otros, con carga interna y horario) y uso DB-SI. Se exportan al proyecto IFC
  y a cada espacio (`ARQ_Usos`).
- Paso libre DB-SUA de cada puerta (≥ 0,80 m en el marco y ≥ 0,78 m abierta), en el eco al crearla y en el IFC.
- Altura habitable por tipo de estancia: 2,50 m en general y 2,20 m en baños, aseos, vestíbulos, pasillos
  y distribuidores (Decreto 10/2019, Anexo I).
- La hoja de 925 mm se avisa como medida comercial (UNE 56803 normaliza 625, 725 y 825).
- IngeTrazo: la definición arquitectónica completa viaja en `scene.plugin_data` y se conserva en el IGZ.
- **Iconos nuevos** (25) para menús y barra de herramientas, dibujados como un plano: un muro son sus dos
  caras, una puerta su hoja y su giro, un pilar un cuadrado aspado. Siguen la paleta de IngeCAD (trazo
  claro, acento azul acero, amarillo solo para lo que se borra) y se generan con `scripts/iconos.py`.
  La barra queda con 15 órdenes.

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

## v1.10.0-dev (6-11-2026) — carpinterías en muros y tabiques

- **`CARPINTERIA`** (y `PUERTAARQ`, `VENTANAARQ`, `HUECOARQ`, que arrancan con ese tipo): un clic
  en la **cara del muro o tabique hacia la que abre** inserta la carpintería; el muro se reconoce
  por la línea pinchada, sin seleccionarlo antes. La orden sigue activa para la siguiente.
  - **Tipos:** puerta de 1 o 2 hojas (hoja principal y segunda), ventana de N hojas con alféizar,
    vierteaguas o ventanal, y hueco sin carpintería (vano).
  - **Colocación:** libre (el clic es la jamba de la bisagra; el segundo clic da el sentido a lo
    largo del muro y la cara a la que abre; Intro, hacia el lado más largo), **a distancia fija** de
    la esquina más próxima del paramento, **centrada** en el paramento pinchado, **centrada en el de
    la otra cara** y, en ventanas y huecos, **longitud máxima**. El paramento libre es el tramo de
    cara entre encuentros; si no cabe, se dice cuánto mide y no se crea nada.
  - **Cerco:** ancho de jamba (puerta 3 cm: el hueco es la hoja + 6 cm) y profundidad (0 =
    automática: 15 cm en puertas y 5 cm en ventanas, nunca más que el muro; en un tabique ocupa su
    espesor); enrasado con la cara a la que abre, centrado o con la otra cara.
  - **B** cambia la bisagra y **S** el sentido de la última; pinchar una carpintería existente
    **sustituye su modelo** conservando su identidad y su centro (y su ancho, si no se tecleó otro).
- **Planta:** el contorno del muro se interrumpe en el hueco y se dibujan las **mochetas**. Puertas:
  jambas del cerco, hoja y arco de giro; ventanas: marco, vidrio, divisiones de hojas y remate
  exterior. Todo se deriva del registro y lo regenera `UNIONESARQ`; el portador del registro va en
  la capa oculta de huecos y forma grupo de selección con su dibujo. Los recintos no se unen a
  través de las puertas.
- **Asociatividad:** mover el muro arrastra sus carpinterías; mover una carpintería cambia su
  posición en el muro; copiarla a otro muro la aloja en él con identidad nueva; borrar el muro
  borra sus carpinterías (deshacer las recupera). Registro de esquema 3; los de esquema 2 se
  actualizan solos al regenerar.
- **Exportación:** cada puerta o ventana es un `IfcDoor`/`IfcWindow` (con la identidad del
  registro, alto y ancho totales, `Pset_DoorCommon`/`Pset_WindowCommon.IsExternal` y hojas, hoja,
  cerco o antepecho y remate en `ARQ_IngeCAD`) que **rellena** el `IfcOpeningElement` de su muro.
  Propuesta a IngeTrazo `0003` para escribir `IfcRelFillsElement`: con ella, cadena completa
  (2 puertas, 1 ventana, 1 vano, 2 recintos) → IFC con 0 errores en IfcOpenShell (reglas EXPRESS).

## v1.10.1-dev (6-11-2026) — carpinterías y recintos: criterios del usuario

- **Ajuste del cerco** como en los modeladores BIM habituales: plano **interior** (hacia el que
  abre la puerta o la ventana), **medio** o **exterior**; las ventanas pasan a ir por defecto
  ajustadas al plano interior.
- **Hojas normalizadas:** `72`, `82`, `92` (y `62`) dan hojas de 725, 825, 925 (625) mm; un ancho
  mayor de 10 se lee en centímetros.
- **Tipo de apertura (T):** puerta abatible o corredera (1 o 2 hojas, dibujadas solapadas en la cara a
  la que abren, con la dirección de corrida); ventana abatible, corredera (hojas en dos carriles) o
  fija (una hoja). Se exporta en `ARQ_IngeCAD.Apertura`, junto con el `Ajuste`.
- **Punto de inserción (I):** lateral (jamba) o medio (centro del hueco) para la colocación a
  distancia fija.
- **RECINTO, F falso techo:** el recinto es el volumen de aire hasta el falso techo (altura libre
  bajo él); 0 vuelve a «hasta el forjado». Se exporta `FinishCeilingHeight` y `ARQ_Recinto.Techo`;
  la altura, el volumen y el sólido del `IfcSpace` usan esa altura.
- Cadena completa con puerta corredera, ventanas corredera y fija, vano y recintos con falso techo:
  IFC con 0 errores en IfcOpenShell (con las propuestas 0002 y 0003 a IngeTrazo).

## v1.10.2-dev (6-11-2026) — falsos techos y tipos IFC de carpintería

- **Falso techo:** un recinto con falso techo exporta también su `IfcCovering` (tipo
  `CEILING`, 15 mm por defecto) con el contorno del recinto, apoyado en su cara superior. La cara
  superior del espacio queda así coplanaria con la del elemento que lo cierra, como piden las
  herramientas de análisis térmico. Va a la capa `ARQ-TECHOS` en IngeTrazo.
- **Puertas y ventanas:** `PredefinedType` y `OperationType` (abatible a izquierda o derecha,
  corredera, doble hoja) o `PartitioningType` (1, 2 o 3 hojas) en el IFC. La propuesta `0004` a
  IngeTrazo escribe estos atributos enumerados; 0 errores en IfcOpenShell.
- **CARPINTERIA:** si el clic cae sobre otra entidad dibujada en la cara del muro (el contorno de un
  recinto, una cota), el muro se busca geométricamente.

## Registro de IngeCAD e IngeTrazo (6-11-2026)

- `docs/REGISTRO_UPSTREAM.md`: errores, inconsistencias y carencias de IngeCAD e IngeTrazo, con
  evidencia, estado, parche y rodeo en el plugin. Una prueba exige que todo parche propuesto figure
  en él. Nueva inconsistencia de IngeCAD reproducida: borrar una entidad de un grupo y deshacer
  tras guardar la deja fuera del grupo (C-02).

## v1.11.0-dev (6-11-2026) — superficie útil según el Decreto 10/2019 de Extremadura

- **Superficie útil de cada recinto** según el art. 2.3 del decreto: la cerrada por la cara interior
  de los cerramientos, descontando tabiquería y puertas (el recinto se detiene en las caras de sus
  muros, así que el paso de una puerta no computa) y los elementos estructurales verticales,
  canalizaciones o conductos de más de 100 cm² de sección. Los de hasta 100 cm² **no se descuentan**.
  El suelo con altura libre menor de 1,50 m no computa.
- **RECINTO, T tipo:** interior o **exterior cubierto** (terraza, galería, balcón, tendedero,
  porche). Computa el 50 % si su fondo es de al menos 50 cm, y se exporta con `IsExternal`.
- **Superficie útil habitable:** recintos interiores con altura libre de al menos 2,50 m. Es un
  parámetro: la cifra exacta está en el anexo del decreto y debe comprobarse.
- La etiqueta del recinto muestra la superficie útil y, si difiere, la computable. El `IfcSpace`
  lleva en `ARQ_Recinto` la superficie útil, el coeficiente, la superficie computable, si es
  habitable y el criterio aplicado. Su geometría y `NetFloorArea` siguen siendo las reales, entre
  caras, coplanarias con los elementos que lo limitan.
- **`SUPERFICIES`:** cuadro de superficies útiles de todos los recintos, con los totales interior,
  exterior computable, útil computable y habitable.
- Pendiente: descontar las escaleras interiores, cuando se modelen.

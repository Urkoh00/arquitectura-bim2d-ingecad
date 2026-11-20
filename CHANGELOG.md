# Arquitectura para IngeCAD v1.6.0-dev — motor de nodos y huella única 2D/3D (EXPERIMENTAL)

Fecha: 5-11-2026. Base: v1.5.1. Distribución de ensayo: no sustituye la versión de trabajo.

## 1.46.0-dev — 2026-11-20

Repaso de todas las órdenes (encargo R27, desarrollado por Codex y revisado por Claude).

- **Variantes `-ORDEN` sin cuadros de diálogo.** 25 órdenes con ficha tienen ya una variante que pregunta
  todo por la línea de órdenes: `-MURO`, `-PILAR`, `-PILARESENEJES`, `-CARPINTERIA`, `-PUERTAARQ`,
  `-VENTANAARQ`, `-HUECOARQ`, `-ARMARIOBIM`, `-FORJADO`, `-RECINTO`, `-EJES`, `-REJILLA`, `-PARAMETROSARQ`,
  `-USOSARQ`, `-TIPOSMURO`, `-NIVELES`, `-NIVELASIGNAR`, `-PROPIEDADESARQ`, `-EDITARARQ`, `-EDITAREJE`,
  `-LINEASAMURO`, `-EXPORTARBIM`, `-SINCRONIZARARQ`, `-BIBLIOTECAHE` y `-AYUDAARQ`. Intro acepta el valor
  entre `<>`, `Anterior` vuelve al campo previo y Esc cancela. Dan los mismos datos que la ficha, porque usan
  las mismas funciones de validación y las mismas operaciones; una prueba de paridad lo vigila.
- **Defectos corregidos** (cada uno con su prueba):
  - EJES ya no se interrumpe con entradas no válidas; EDITAREJE, NIVELES, NIVELASIGNAR, PARAMETROSARQ,
    EXPORTARBIM, BIBLIOTECAHE y SINCRONIZARARQ no se cierran sin ventana: avisan y remiten a su variante;
  - BLOQUE no falla al pulsar un punto antes de elegir el tipo;
  - ESCALERA y las demás órdenes antiguas se deshacen en un solo paso, y las coordenadas escritas llegan
    al punto en vez de tomarse como opción;
  - TIPOSMURO: el intercambio CSV conserva categoría, espesores de capa y materiales con «+»; aceptar la
    ficha ya no redondea las capas, y editar un tipo por texto conserva su categoría;
  - PILAR acepta los nombres completos de sus opciones y valida medidas y giros antes de cambiar nada;
  - CARPINTERIA y RECINTO aceptan opciones con espacios («Tipo de apertura», «Falso techo») y nombres
    con espacios;
  - TRAMA ya no deja una trama vacía fuera del historial;
  - ARMARIOBIM no confunde sus teclas con las cotas de CARPINTERIA;
  - la validación de contornos comprueba cada planta y las bandas de altura, y los grupos de muro
    conservan su identificador al regenerar y al deshacer;
  - la primera activación de niveles regenera los contornos en la misma operación;
  - EXPORTARBIM avisa si la ruta no se puede escribir.
- **Tab y C-16.** Las órdenes con cotas temporales siguen el contrato `Tool.on_tab` propuesto a IngeCAD
  (#155). Si IngeCAD ofrece Tab a la orden, el plugin no instala su filtro de teclado.
- Repaso de las 90 órdenes, sin ventana y en la ventana real de IngeCAD: sin excepciones, con Deshacer,
  Rehacer, validación y guardado en DXF y DWG.

## 1.45.0-dev — 2026-11-20

- **Tab recorre las cotas temporales y fija su valor.** Al dibujar un muro, Tab pasa de la longitud al
  ángulo y vuelve; si antes de pulsarlo se escribe un valor, esa cota queda fijada (en verde y entre
  corchetes) y se activa la siguiente. Lo que no está fijado sigue al cursor: con el ángulo fijado, la
  longitud es la proyección del cursor; con la longitud fijada, la dirección es la del cursor. Intro, o un
  valor e Intro, o un clic, colocan el tramo. Mayús+Tab vuelve a la cota anterior.
- En **CARPINTERIA, PUERTAARQ, VENTANAARQ y HUECOARQ**, Tab recorre la distancia a la izquierda, a la
  derecha y el ancho del hueco. Fijar izquierda y derecha da el ancho; fijar el ancho cambia el del modelo
  (en una puerta, el de la hoja). Intro o un clic en la cara del muro colocan la carpintería; si no cabe,
  se avisa y lo fijado se conserva. En **MOVERCARP**, un valor y Tab mueven la carpintería y activan la otra
  cota.
- El ángulo del muro se muestra como cota propia (arco desde la horizontal), separado de la longitud.
- Sin Tab todo funciona como antes: un número tras el primer punto es la distancia directa de IngeCAD.
- IngeCAD 0.8 solo entrega a la orden las teclas F4 a F6; Tab se recoge con un filtro de teclado que
  actúa solo mientras una de estas órdenes lo admite. Se propondrá a IngeCAD que ofrezca Tab a la orden
  (C-16).

## 1.44.0-dev — 2026-11-19

- **Los muros envían su superficie de paramento al IFC** (`GrossSideArea` y `NetSideArea` en
  `Qto_WallBaseQuantities`): volumen entre espesor, exacta en muros rectos y curvos; la neta descuenta los
  huecos pasantes. IngeTrazo la tomaba de la cara mayor de la malla: en un muro curvo salía la huella
  (1,83 m² en lugar de 18,3 m²) y en un muro con una puerta hasta el suelo no se descontaba el hueco.
  Comprobado en el modelo de la tercera prueba: 21,60 → 19,71 m² con la puerta de 0,90 × 2,10.

## 1.43.0-dev — 2026-11-19

- **Herramientas antiguas (CURVAS3D, VERTPOLY, ESCALERA...): sus preguntas salen como avisos de la orden.**
  Antes las escribían como mensajes y la línea de órdenes de IngeCAD repetía, junto a cada respuesta, el
  último aviso de otra orden (en CURVAS3D aparecía el menú de PEDIT). Un contexto propio convierte en aviso
  toda línea que termina en dos puntos; no se toca el código de cada herramienta.
- CURVAS3D aclara que ARQ-CURVAS3D es la **capa** donde quedan las polilíneas 3D, no una orden.
- Las herramientas antiguas se conservan, por indicación del propietario.

## 1.42.0-dev — 2026-11-19

- **Corregido: PARAMETROSARQ no abría su ficha** («NameError: name 'QComboBox' is not defined»). Faltaba
  una importación desde la v1.37, al añadir «Armarios en la superficie útil». Prueba nueva que abre la ficha.
- **AYUDAARQ es ahora un cuadro de diálogo**: órdenes agrupadas por tema (muros; pilares y rejillas;
  puertas, ventanas y armarios; forjados y niveles; recintos y superficies; cotas y capas; datos BIM y
  comprobación; intercambio BIM y energía; configuración; herramientas antiguas), con buscador y el
  detalle de opciones de la orden elegida. Sin ventana se escribe el mismo texto, ordenado, en la línea
  de órdenes.
  - Añade las 23 órdenes que faltaban (FORJADO, NIVELES, TIPOSMURO, DEFENSA, EJES, UNIONESARQ…) y quita
    la entrada repetida de PILAR.
  - Una prueba exige que la ayuda tenga exactamente las órdenes registradas.
- Se quitan de comentarios y textos del plugin los nombres comerciales que se habían colado en la v1.37
  (regla del proyecto).

## 1.41.0-dev — 2026-11-19

- **Huecos con medidas reales en el IFC (R26-P4, Codex; revisado e integrado por Claude).** La extensión
  envía con cada hueco su tipo (`OPENING`, o `RECESS` para un nicho que no atraviesa el muro) y sus
  cantidades: ancho y alto del registro y espesor del muro como fondo. En forjados, el fondo es el canto;
  un contorno rectangular da sus lados reales y cualquier otro, su área exacta. El contrato `.arqbim` no
  cambia. Con la mejora P4 de IngeTrazo, cada hueco sale como `IfcOpeningElement` vinculado a su muro y
  a su puerta o ventana.
- `scripts/generar_modelo_r26.py aceptacion`: modelo de la tercera prueba en la plataforma de cálculo
  (hueco sin carpintería y cubierta).
- 25 pruebas nuevas.

## 1.40.0-dev — 2026-11-19

- **Nueva orden BIBLIOTECAHE: biblioteca térmica del usuario.** Importa el catálogo de la Herramienta
  Unificada LIDER-CALENER (`BDCatalogo.bdc` de la instalación, el `.bdc.utf8.gz` que publica el IETcc o
  un ZIP), como hacen otros programas de cálculo. El plugin **no distribuye** el catálogo.
  - Lee materiales (λ, ρ, cp, μ o resistencia), composiciones, vidrios (U y g⊥), marcos y huecos.
  - La guarda en la carpeta de configuración del usuario, para todos los proyectos; no va al dibujo.
  - `BIBLIOTECAHE buscar texto` y `BIBLIOTECAHE u Composición [/ techo|suelo]` (U según el DA DB-HE/1).
  - Comprobado con el catálogo de 2015 y con el del IETcc: 761 materiales, 428 composiciones,
    258 vidrios, 17 marcos y 5 huecos; quedan 3 referencias rotas propias del catálogo, que se avisan.
- Es la base del futuro exportador a EnvolventeCTE (estudio del 19-11).
- 17 pruebas nuevas (una solo con un catálogo instalado).

## 1.39.0-dev — 2026-11-19

- **Cada forjado lleva tipo IFC.** El generador del modelo analítico de BIMserver.center (Open BIM Analytical
  Model) agrupa por tipo y lo exige en todos los elementos. Un forjado sin tipo propio lo recibe por su clase
  y su canto («Solera 20 cm», «Forjado 25 cm», «Cubierta plana 30 cm»).
- Comprobado con un IFC de aceptación del edificio sintético (cadena con las ampliaciones P0 a P3b propuestas
  a IngeTrazo): 0 errores EXPRESS, 8 tipos y norte a 30°. Faltan los huecos (P4, encargado).
- 3 pruebas nuevas; 886 en total.

## 1.38.0-dev — 2026-11-19

Valores por defecto según las indicaciones del propietario.

- **Altura por defecto de 3,00 m** (antes 2,70 m) en muros y pilares: PARAMETROSARQ, fichas, MURO, PILAR,
  LINEASAMURO y su plan de conversión.
- **Normativa por defecto, Extremadura (Decreto 10/2019, art. 2.3):** los armarios adosados **computan**
  como superficie útil (`armarios_superficie_util = 'computan'`). El decreto solo descuenta tabiquería y
  divisiones, pilares y conductos de más de 100 cm², suelo de menos de 1,50 m de altura libre y la escalera,
  y trata los armarios como mobiliario (anexo I, 2.1.A). «Descuentan» sigue disponible.
- **Cota de nivel = cara superior del forjado estructural**, el criterio de CYPE: la altura de planta es
  la distancia entre caras superiores de forjados, y la solera del IFC de referencia va de −0,40 a 0,00
  con «Planta baja» a 0,00. El plugin ya lo aplicaba; ahora está documentado en el manual.
- Pendientes anotados en el manual:
  - la escalera interior, que el decreto descuenta, aún no se modela;
  - la accesibilidad (Decreto 135/2018 de Extremadura y CTE DB-SUA) aún no se comprueba.

## 1.37.0-dev — 2026-11-19

Armarios: el espacio IFC sigue el criterio de CYPE (decisión del propietario, 19-11-2026).

- **El `IfcSpace` llega siempre a las caras de los muros.** El armario adosado ya no recorta su sólido ni
  descuenta `NetFloorArea` ni `NetVolume` en `Qto_SpaceBaseQuantities`. En CYPE el armario es mobiliario
  y no limita espacios, y su generador del modelo analítico exige que las caras del espacio coincidan con
  muros y forjados; un espacio recortado contra el armario no se interpretaría.
- **La superficie útil sigue su propio criterio**, elegible en PARAMETROSARQ > General, «Armarios en la
  superficie útil»:
  - «Descuentan» (por defecto): el armario es una división interior fija (vivienda protegida de Madrid,
    tasación);
  - «Computan»: el armario cuenta como superficie útil (habitabilidad de Baleares).

  Afecta a la superficie útil del recinto, al cuadro SUPERFICIES y a `ARQ_Recinto.SuperficieUtil`.
  `ARQ_Recinto` añade `SuperficieArmarios` (la planta de los armarios del recinto) y
  `ArmariosEnSuperficieUtil` (el criterio aplicado).
- **Aviso al empotrar un armario (nicho) en una fachada, medianera o muro de sótano:** el nicho quita espesor
  y debilita el aislamiento térmico y acústico, como los radiadores empotrados. Se avisa al crearlo con
  ARMARIOBIM y en la exportación. El armario adosado sigue siendo el modo por defecto.
- Estudio en el proyecto: `ESTUDIO_armarios_superficies_y_espacios_CYPE_2026-11-19.md`.
- 6 pruebas nuevas.

## 1.36.0-dev — 2026-11-19

Eje de los muros hacia el IFC (encargo R25, paquete P3b; trabajo de Codex, revisado e integrado), y sólidos
estancos lejos del origen.

- La extensión de IngeTrazo pasa en la etiqueta de cada muro recto su **línea de referencia** (`axis`): los
  extremos dibujados (`params.a` y `params.b`) a la cota de la base, con el mismo origen de escena que los
  vértices. Con la ampliación P3b propuesta a IngeTrazo, cada muro tiene una colocación propia (X a lo largo
  del muro, Y su normal izquierda) y una representación `Axis`, de modo que **la dirección de las capas es
  correcta también en los muros girados**. Los muros curvos no llevan eje.
- **Corrección: sólidos lejos del origen y girados.** Con el edificio girado y en coordenadas UTM
  (700000, 4600000), la extensión rechazaba algunos muros («sólido abierto o caras mal orientadas»).
  Había tres causas encadenadas:
  - el mismo vértice salía con dos valores separados por 1e-10 m, y redondear a 7 decimales los separaba;
  - un plano de dintel quedaba a ambos lados de otra frontera de redondeo y dejaba una cara interna;
  - quedaban púas de anchura nula en las jambas.

  Ahora el sólido se calcula en coordenadas locales (origen de metros enteros junto al muro). Los vértices y
  los planos se agrupan con tolerancia y no por redondeo (`geom/soldadura.py`), y se eliminan las púas. El
  validador de la extensión suelda igual.
- Scripts `generar_modelo_r25.py` y `verificar_cadena_r25.py` (edificio a cualquier ángulo, cerca o lejos
  del origen).
- 24 pruebas nuevas; 878 en total. La cadena completa da 0 errores EXPRESS a 0°, 27° y 61°, cerca y lejos del
  origen.

## 1.35.0-dev — 2026-11-19

Capas de material de los muros hacia el IFC (encargo R24, paquete P3 del plan de aportaciones a IngeTrazo;
trabajo de Codex revisado e integrado).

- La extensión de IngeTrazo pasa en la etiqueta de cada muro sus **capas** (`material_layers`, de la cara de
  referencia hacia dentro) y el **desplazamiento de la primera capa** (`layer_offset`). Este se calcula con la
  misma función que construye el sólido: −e/2 si la referencia es el eje, 0 si es la izquierda, −e si es la
  derecha. Las pruebas lo contrastan con las caras reales en cuatro orientaciones.
- Los demás elementos conservan `type` y `material`; las capas solo van en los muros.
- Con la ampliación P3 propuesta a IngeTrazo, el IFC lleva tipos compartidos (`IfcWallType`, `IfcDoorType`…),
  sus conjuntos de capas y su uso en cada muro. Con P2 y P3 juntos, el modelo sintético (tres fachadas,
  medianera, tabique, puerta, ventana, solera y dos recintos) da **0 errores EXPRESS**.
- **Límite conocido:** IngeTrazo aún no da a cada muro una colocación propia orientada según su eje, así que
  en los muros girados la dirección de las capas en el IFC no es fiable. Queda como paquete P3b.
- Scripts `generar_modelo_r24.py` y `verificar_cadena_r24.py` para reproducir la cadena con un modelo público.
- 18 pruebas nuevas; 854 en total.

## 1.34.0-dev — 2026-11-19

Datos que piden los programas de cálculo energético, según un IFC de referencia de un modelador comercial
y los requisitos públicos de los generadores de modelo analítico.

- **Norte del proyecto.** Nueva opción en PARAMETROSARQ › General, en grados en sentido horario desde +Y
  (0 = norte arriba). Viaja en el contrato (`project.north_deg`, normalizado a (−180, 180]), y la extensión
  lo pasa a la escena de IngeTrazo (`scene.north_deg`, Herramientas › Norte). Con la corrección
  propuesta en el PR #1498 de IngeTrazo, llega al IFC como `TrueNorth`.
- **Clase del forjado** (`slab_kind`):
  - forjado entre plantas: `FLOOR`;
  - **solera**: `BASESLAB`, exterior y en contacto con el terreno;
  - **cubierta plana**: `ROOF`, exterior.

  Se exporta con `Pset_SlabCommon.IsExternal` y con `ARQ_Forjado.Tipo` y `ContactoTerreno`. Se elige en la
  ficha de FORJADO o, antes del primer punto, con las opciones `Forjado`, `Solera` o `Cubierta`. Los forjados
  anteriores se leen como forjado entre plantas.
- **Tipo IFC de los recintos:** `INTERNAL`, o `EXTERNAL` para los exteriores cubiertos.
- Cadena comprobada con un modelo como el de la referencia (tres fachadas, medianera, tabique, puerta,
  ventana, solera y dos recintos):
  - con el IngeTrazo 0.6.2.1 oficial, el IFC sigue sin propiedades ni tipos (T-02 y T-05);
  - con las correcciones propuestas a IngeTrazo (T-17 y P1, plan de aportaciones), llegan 22 juegos de
    propiedades, los 10 identificadores, los tipos de todos los elementos y `TrueNorth`.
- 12 pruebas nuevas; 836 en total.

## 1.33.0-dev — 2026-11-19

Tipo IFC de los muros alineado con un IFC de referencia de un modelador comercial (prueba del
propietario: una medianera, tres muros de fachada, un tabique, una puerta, una ventana y una solera).
Son también los valores que piden los generadores de modelo analítico para el cálculo energético.

| Categoría | Antes | Ahora |
|---|---|---|
| Fachada | `STANDARD` | `USERDEFINED` + `ObjectType` `EXTERNALWALL` |
| Tabique | `PARTITIONING` | sin cambio |
| Medianera | `STANDARD` | `USERDEFINED` + `ObjectType` `PARTYWALL` |
| Muro de sótano | `STANDARD` | `USERDEFINED` + `ObjectType` `BASEMENTWALL` |

- `IsExternal` no cambia: verdadero en fachada, medianera y sótano, como en la referencia.
- La tabla está en `wall_categories.IFC_TYPES`, y `ifc_type()` da el par de cada categoría.
- El IFC de IngeTrazo 0.6.2.1 sigue perdiendo `PredefinedType` y `ObjectType` (T-02, T-05). Los
  valores viajan en el contrato y en el IGZ.

## 1.32.0-dev — 2026-11-18

Integra la **entrada revisada de LINEASAMURO** (R22, punto 3), entrega de Codex sobre la v1.31
(`2a2b4a0`), verificada por SHA-256 y revisada por Claude. 824 pruebas (71 nuevas) con IngeCAD 0.8.0.

- **Contrato `arq.entrada-revisada/v1`** (`entrada_revisada.py`, `docs/ENTRADA_REVISADA.md`): un DXF
  `plano.dxf` puede llevar al lado `plano.dxf.procedencia.json`, con su SHA-256, unidades en metros,
  escala comprobada, revisión terminada y el papel y estado de cada capa `REV-*` (y, si hace falta, de
  cada entidad). Solo las caras de muro, puertas y ventanas **confirmadas** se convierten; ejes,
  pendientes, rechazados y candidatos no. La fuente original (croquis, foto, PDF) es informativa y el
  plugin nunca la abre.
- Sin procedencia válida, LINEASAMURO trabaja como siempre, pero **nunca** reconoce las capas `REV-*`
  por su nombre ni las usa como contexto o dentro de bloques.
- Si un muro tiene una interrupción sin puerta o ventana confirmada, se conserva como dibujo y se avisa;
  no se inventa ni vano ni relleno.
- Cualquier cambio del DXF, del JSON o del dibujo invalida la vista previa (se comprueban los hashes al
  analizar y al convertir).
- LINEASAMURO busca la procedencia al empezar; también se carga con la opción `Procedencia` o desde el
  cuadro de clasificación.
- Revisión de Claude: importaciones de `entrada_revisada` al principio de los módulos, no dentro de los
  bucles; la sección del manual pasa al manual principal.
- Cadena con IngeTrazo 0.6.2.1 (caso sintético de un muro): 3,24 m³ en el análisis, el contrato y el
  IFC, sin errores EXPRESS; el IFC sigue sin Psets ni tipos (T-02, T-05).

## 1.31.0-dev — 2026-11-18

- **Retirado el puente antiguo a IngeTrazo** por decisión del propietario: EXPORTARIGZ, CONFIGIGZ y las
  órdenes 3D experimentales MURO3D y HUECO3D, cuyos elementos solo leía ese puente (`igz_bridge.py`,
  `tools3d.py` y las funciones `wall_command`, `opening_command`, `partition_solids` y `export_spec` de
  `architectural.py`). El paso a IngeTrazo es EXPORTARBIM con la extensión. `ensure_arch_layers` pasa a
  `architectural.py`.
- `arquitectura/README.md` (un leeme de la v1.2 ya sin validez) se sustituye por una nota que remite al
  manual y a la guía del código.
- Solo se prueba con la última versión de IngeCAD (0.8.0) e IngeTrazo (0.6.2.1), por directriz del
  propietario.

## 1.30.0-dev — 2026-11-18

Integra **R21 de Codex** (cambiar tipos desde IngeTrazo con vuelta a IngeCAD) y su revisión general de la
v1.28, sobre la v1.29. Entrega verificada (SHA-256); 753 pruebas con IngeCAD 0.8 y 744 + 9 con la 0.7.

- **Panel «Propiedades de Arquitectura» en IngeTrazo** (`ingetrazo_ext/_arq_edit.py`): tipo, apertura,
  hojas, materiales y perfiles de muros, puertas, ventanas y armarios, regenerados con el mismo código del
  plugin. Los cambios que alteran la planta quedan pendientes hasta aceptarlos en IngeCAD.
- **`.arqcambios` y SINCRONIZARARQ** (`roundtrip.py`, `roundtrip_model.py`): comprobación del dibujo de
  origen, conflictos elemento a elemento (por defecto se conserva IngeCAD), validación en una copia y un
  solo Deshacer.
- **Instalación de la extensión:** ahora se copia **toda** la carpeta `ingetrazo_ext` (incluida
  `arq_shared`), y hay que reiniciar IngeTrazo. Los modelos antiguos deben exportarse de nuevo para ser
  editables.
- **RG-01 (revisión de Codex):** una carpintería con medidas negativas (cerco, hojas, retranqueo…) se
  rechaza en la ficha y al crearla o editarla, y ARQVALIDAR señala los registros antiguos sin corregirlos
  en silencio (`openings.dimension_problems`).
- **Integración (dirección técnica):**
  - `ingetrazo_ext/arq_shared/` ya no se guarda en el repositorio: se copia de la fuente al construir el
    ZIP y al pasar las pruebas, así no puede quedar desfasada. Incluye `defensas.py` y
    `particiones_virtuales.py`; la orden PARTICIONVIRTUAL pasa a `wall_tools.py`, porque
    `particiones_virtuales.py` debe poder cargarse sin IngeCAD.
  - **La guía del código va en cada ZIP con su versión** (`GUIA_DEL_CODIGO_v<versión>.md` en la raíz y en
    `docs/`); una prueba lo comprueba.

## 1.29.0-dev — 2026-11-18

Dos elementos nuevos, estudiados en los manuales de herramientas BIM de arquitectura que aportó el
propietario, y la primera etapa de ordenación del código. 738 pruebas con IngeCAD 0.8 y 729 + 9 con la
0.7; cadena real con IngeTrazo 0.6.2.1 comprobada.

- **DEFENSA** (`defensas.py`): barandilla, balaustrada o antepecho dibujado como un muro con la categoría
  «defensa». Hereda encuentros, niveles, edición y Deshacer; cierra recintos (terrazas); no admite
  carpinterías; avisa del DB-SUA 1 si mide menos de 1,10 m. Exporta `IfcRailing` (GUARDRAIL o BALUSTRADE)
  con `Pset_RailingCommon`, o `IfcWall` PARAPET si es macizo. En 3D, la barandilla lleva pasamanos y
  montantes dentro de la huella de planta. La extensión de IngeTrazo admite `IfcRailing` (capa
  ARQ-DEFENSAS): **actualice también el fichero de la extensión**.
- **PARTICIONVIRTUAL** (`particiones_virtuales.py`): línea sin espesor que separa recintos. El reparto
  (`geom/spaces.split_by_partitions`) es exacto: las superficies de los dos lados suman la de la estancia.
  Una partición que no cruza la estancia no separa. Se edita con órdenes de IngeCAD y los recintos se
  rehacen solos. En el contrato va en `virtual_partitions`, y cada recinto cita las suyas
  (`virtual_boundaries`). IngeTrazo no escribe aún `IfcVirtualElement`.
- **CARPINTERIA**: una distancia escrita que no cabe en el muro (por ejemplo, en una defensa) ahora
  se informa; antes interrumpía la orden con un error.
- **Código:** guía en español (`docs/GUIA_DEL_CODIGO.md`) y resumen en español en la cabecera de los
  60 módulos.

## 1.28.0-dev — 2026-11-17

Revisión general de la aplicación (dirección técnica). Informe completo en el proyecto:
`REVISION_GENERAL_v1.28_2026-11-17.md`.

- **Rendimiento en planos grandes.** Edificio de prueba con 220 muros, 100 recintos y 100 puertas:
  añadir un tabique pasa de 2,67 s a 0,46 s; una puerta, de 2,66 s a 0,43 s; RECINTO, de 0,62 s a
  0,12 s; EXPORTARBIM, de 3,08 s a 0,78 s. Tres causas, corregidas sin cambiar ningún resultado:
  - cada recinto recalculaba la unión de toda la red de muros (`geom/spaces.components` se guarda ahora
    en el resultado, que es definitivo);
  - los niveles buscaban las carpinterías de cada muro recorriendo el dibujo entero una vez por muro
    (`wall_constraints.openings_by_wall`, un recorrido);
  - el motor de encuentros probaba todas las parejas de muros; ahora solo las que pueden tocarse, por
    cajas que contienen todo lo que cada prueba acepta. Se ha comprobado con escenas aleatorias que el
    resultado es idéntico, no solo parecido, al del motor anterior.
- **Espesor escrito en MURO, MUROPARALELO y MUROCURVO.** Antes, `25` hacía un muro de 25 m y `3,4`
  uno de 3,4 m de espesor. Ahora la coma decimal vale para espesores de hasta 1,5 m; `3,4` es el
  punto (3, 4) de IngeCAD; un número mayor de 1,5 se lee en cm (hasta 100) o en mm (hasta 1500), con
  aviso; lo demás se rechaza.
- **Persistencia comprobada:** guardar el DXF con IngeCAD y reabrirlo da el mismo contrato BIM, byte a
  byte (prueba nueva).
- **Cadena con IngeTrazo 0.6.2.1 oficial** sobre un edificio de 84 muros, 36 puertas y 36 recintos:
  mismos recuentos y volúmenes en el IFC; solo los errores ya conocidos de T-03.
- Eliminadas 13 funciones sin uso en `wall_network.py` (−196 líneas).

## 1.27.0-dev — 2026-11-16

Integra R23 de Codex (observaciones del usuario a la v1.24), revisada y adaptada a la v1.26: SHA-256 correcto;
718 pruebas con IngeCAD 0.8 y 709 + 9 con la 0.7; cadena IGZ comprobada con IngeTrazo 0.6.1 y 0.6.2.

- Iconos en todas las órdenes del menú; LINEASAMURO justo antes de «Intercambio BIM».
- Ficha de carpintería: planta y alzado a la misma escala, sin solaparse, con las medidas al pie.
- **Nivel activo** en la barra de herramientas del plugin (IngeCAD 0.8), con encendido, inutilizado y
  bloqueado sobre las capas nativas de cada nivel; un nivel bloqueado no se edita. En 0.7, `NIVELES ESTADO`.
- **Categoría del muro**: fachada, tabique, medianera y sótano, cada una en su capa (`ARQ-MEDIANERAS` y
  `ARQ-SOTANO` nuevas); `IsExternal`, PARTITIONING y marcas de medianera y contacto con el terreno.
- **Muro hasta un nivel** con desfases (la altura fija sigue por defecto); la altura resultante sigue a los
  niveles en un solo Deshacer, y cada recinto toma solo su tramo.
- **Armario adosado** por defecto (no corta el muro, reduce la superficie útil); el nicho se conserva.
  Cuerpo como `IfcBuildingElementProxy` ARMARIO_FIJO; requiere actualizar la extensión de IngeTrazo.
- C-08 (controles de plugins en la barra de capas de IngeCAD) documentada, sin enviar.
- Revisión de la dirección: las comprobaciones de bloqueo salen enseguida cuando no hay capas bloqueadas ni
  niveles organizados por capas (con 200 muros, un muro nuevo pasaba de 0,27 s a 0,46 s; ahora 0,30 s), y el
  monitor de la barra se detiene si el anfitrión cambia, en lugar de fallar cada medio segundo.
- Límite conocido: el IFC oficial de IngeTrazo 0.6.x crea una sola planta, relaciona mal los recintos y no
  transmite tipos, propiedades ni cantidades; el IGZ sí conserva los datos.

## 1.26.0-dev — 2026-11-16

Cotas temporales al dibujar muros y colocar carpinterías, como en los programas BIM habituales. Desarrollo
de la dirección técnica; 682 pruebas con IngeCAD 0.8 y 673 + 9 con la 0.7; comprobado con capturas de la
interfaz real.

- **CARPINTERIA**: al pasar el cursor por un muro aparecen la distancia a la referencia de cada lado (fin del
  paramento libre o jamba de otra carpintería) y el ancho del hueco, este en la otra cara para no cruzar el
  giro. La cota activa va en naranja: escribir un número (`1,20`, `120cm`) coloca el hueco a esa distancia.
  `F6` u opción `Cota` cambia la cota activa; `F4` u opción `Eje` mide a la jamba o al centro del hueco.
  Un número mayor de 30 sigue siendo el ancho de hoja en milímetros/centímetros, como antes.
- **MOVERCARP** (nueva): designar una carpintería y moverla con sus cotas temporales, escribiendo la distancia
  o con un clic en el muro (centro). Conserva la identidad BIM; un solo Deshacer; no la mueve si no cabe.
- **MURO**: muestra la longitud y el ángulo del tramo (`2,24 <0,0°`) y la distancia desde su extremo a la cara
  paralela más cercana a cada lado. Un número escrito es la longitud (distancia directa de IngeCAD).
- Las cotas no se dibujan: IngeCAD 0.8 las muestra como entidades virtuales con texto real, de tamaño
  constante en pantalla; en IngeCAD 0.7 solo se muestran sus líneas.

## 1.25.0-dev — 2026-11-16

Integra R16-3 de Codex (recintos limitados por la envolvente), revisada: SHA-256 correcto; 674 pruebas con
IngeCAD 0.8 y 665 + 9 con la 0.7; volúmenes analíticos y cadena IGZ/IFC comprobados.

- **RECINTO por envolvente** (por defecto): suelo en la cara superior del forjado inferior y techo en la cara
  inferior del forjado superior del nivel activo; con falso techo, bajo él. Los faldones futuros no recortan
  un recinto cubierto por forjado horizontal. Sin límite superior se usa la altura de reserva; `Altura` fija
  una altura manual y `Envolvente` vuelve al cálculo. Los recintos antiguos conservan su altura manual.
- Huecos y cobertura parcial de forjados por zonas: `Height` es la altura libre máxima y `NetVolume` el
  volumen exacto por zonas, contrastado con la malla estanca.
- **RECINTO por polilínea** (también cóncavo), con longitud temporal junto al cursor; el contorno sigue a la
  polilínea al moverla, copiarla o editar sus vértices. Un solo Deshacer.
- La ficha muestra el límite superior, la altura libre máxima y el volumen neto.
- Fuera de alcance: AJUSTARRECINTO por cubierta y forjado inclinado (R16-4).

## 1.24.0-dev — 2026-11-16

Integra la entrega R16-0 + R16-1/2 de Codex (inicio de la fase 5), revisada: SHA-256 correcto; 649 pruebas
con IngeCAD 0.8 y 640 + 9 con la 0.7 (32 nuevas). Cadena IGZ/IFC comprobada con IngeTrazo 0.6.1 y 0.6.2.

### Niveles (R16-1)
- **NIVELES:** catálogo de plantas (nombre y elevación) y nivel activo, que se aplica a muros, pilares y
  forjados nuevos. La primera confirmación (o `NIVELES MIGRAR`) asigna lo existente a «Planta baja» sin
  cambiar cotas ni identificadores; abrir un dibujo no lo migra. Cambiar la elevación desplaza los elementos
  del nivel; no se elimina una planta con elementos.
- **NIVELASIGNAR:** pasa la selección a otro nivel, conservando la cota absoluta o alineándola. Las puertas
  siguen a su muro.

### Forjados (R16-2)
- **FORJADO:** horizontal, con nombre, material, espesor (crece hacia abajo) y desfase de la cara superior
  respecto al nivel; contorno por puntos (también cóncavo) y huecos interiores con la opción `Hueco`.
- **HUECOFORJADO:** añade huecos a un forjado existente. Edición desde Propiedades; un Deshacer.
- `.arqbim` v3 (solo si hay niveles o forjados; los dibujos sin ellos siguen en v1/v2). Hay que actualizar
  la extensión de IngeTrazo.

### IngeTrazo
- Sus exportadores (0.6.1 y 0.6.2) siguen escribiendo una única planta «Storey» y no exportan el catálogo de
  niveles al IFC (T-03). El catálogo y los identificadores sí se conservan en el IGZ.

Pendiente: R16-3 (recintos limitados por forjado, cubierta o falso techo) y R16-4 (cubierta y falso techo).

## 1.23.0-dev — 2026-11-15

Integra la entrega R14-e de Codex, revisada: SHA-256 correcto; 617 pruebas con IngeCAD 0.8 y 608 + 9 con la
0.7. Cadena `.arqbim` → IGZ → IFC comprobada con IngeTrazo 0.6.1 y 0.6.2 (sin errores de esquema; volumen
del muro con nicho correcto).

- **ARMARIOBIM:** armario empotrado como **nicho parcial** en su muro anfitrión (ancho, fondo, altura, base,
  hojas y apertura corredera o abatible); el muro conserva el espesor restante en planta, 3D y cantidades.
  Los frentes son `IfcDoor` de armario. Si se reduce el espesor del muro, se valida antes para que el nicho
  no pase a ser un corte pasante.
- **LINEASAMURO:**
  - recupera los retornos escalonados de fachada cuyo solape es menor que la longitud mínima;
  - **rangos de espesor independientes** para muros, medianeras y tabiques (opción en la ficha), sin
    emparejar caras de categorías distintas.
- El IFC de IngeTrazo sigue omitiendo las relaciones de hueco y los atributos del frente (T-04, T-02).

## 1.22.3-dev — 2026-11-15

Integra la entrega R14-d + R19 de Codex (pruebas del usuario con planos reales, sin incluirlos), revisada:
SHA-256 correcto; 552 pruebas con IngeCAD 0.8 y 543 + 9 con la 0.7. En los dos planos de prueba: una puerta
más (13), los 28 huecos anteriores conservados, 11 de 11 ventanas con marco medido y los arcos de giro
retirados del dibujo original.

### LINEASAMURO
- **Ventanas:** se lee el marco entre jambas, su profundidad y su retranqueo (posición «a distancia»); el
  lado exterior sale de la envolvente o de un alféizar inequívoco.
- **Arcos de giro** reconocidos se retiran con la conversión (iban quedando en la capa original).
- **Puerta junto a un muro transversal** (extremo libre): se recupera si hay arco real.
- **Correderas por el exterior** del muro o tabique (dos hojas aparcadas fuera): se reconocen como pareja y
  piden «Puertas» para confirmarse.
- **Retornos cortos de fachada** apoyados en ambos lados: se recuperan (no explica todos los casos).
- **Armarios:** categoría propia; la geometría que no se interpreta ya no se oculta, y no se cortan muros de
  lado a lado en su zona. El nicho parcial BIM está diseñado (docs/R14d_R19.md) pero no implementado.
- **Escaleras:** aviso con el número de objetos clasificados que se conservan como dibujo.
- **Capas:** `guess_roles` reconoce ARQ-MUROS, ARQ-TABIQUES, ARQ-PUERTAS, ARQ-VENTANAS y ARQ-ARMARIOS; los
  tabiques se exportan como `IfcWall` PARTITIONING.

### Capas y rejilla
- `ARQ-PILAres` pasa a **`ARQ-PILARES`**; ARQMIGRAR renombra la capa de dibujos anteriores en un Deshacer.
- `ARQ-HIPERVINCULOS` ya no se crea con las demás capas: solo al usar HIPERVINCULO.
- **Rejilla:** las cotas quedan fuera de las burbujas y su texto tiene tamaño propio en mm de papel, editable.

Pendiente: fachada del plano concreto, nichos de armario, rangos mixtos de espesor, revisión visual en Windows.

## 1.22.2-dev — 2026-11-15

Integra la entrega R18 de Codex (fallos de uso encontrados por el usuario en Windows), revisada: SHA-256
correcto; 521 pruebas con IngeCAD 0.8 y 512 + 9 con la 0.7.

- **EJES no dejaba situar la rejilla:** la ficha creaba los botones Aceptar/Cancelar pero no los colocaba
  (también la de EDITAREJE). Ahora: número de ejes en X y en Y, **tabla de separaciones** por vano con
  totales y «Todas iguales», punto de inserción con la malla en vista previa y giro opcional. EDITAREJE
  cambia una separación y desplaza los ejes siguientes y sus pilares, en un solo Deshacer.
- **LINEASAMURO:** la zona se dibuja como rectángulo desde la primera esquina y se **resaltan** las entidades
  de las capas clasificadas que se leerán; usa la designación de IngeCAD (ventana o captura) y pasa esos
  mismos objetos al análisis.
- **Tipos de muro:** se muestra el **espesor total** (suma de capas) en la lista y en el detalle; la ficha
  MURO avisa si el espesor no coincide con el del tipo. Pendiente: exportar `IfcWallType`.

## 1.22.1-dev — 2026-11-14

Integra la entrega R14-c de Codex (LINEASAMURO tras la prueba del usuario con un plano real), revisada:
SHA-256 correcto, parche aplicado sobre 92eb4d9, 500 pruebas con IngeCAD 0.8 y 492 + 8 con la 0.7, y DXF de
ensayo sintéticos. Con el plano real del usuario (privado, ×4): 61 muros y 20 puertas (19 en la 1.22.0).

- **Puertas dobles:** dos giros con bisagras opuestas que abren al mismo lado hacen una puerta de dos hojas,
  también con hojas desiguales; el número de hojas se conserva hasta el registro BIM.
- **Ancho del hueco** medido entre jambas (tolerancia 5 mm), no por los radios de giro ni por un ancho de
  catálogo; con caras cortadas a distinta distancia, se toma la abertura común.
- **Correderas:** los paneles paralelos solapados pueden ser puerta o ventana; sin más datos se avisa y se
  deja un vano para que el usuario lo designe como Puertas o Ventanas. Igual con la corredera de bolsillo.
- **Encuentros oblicuos** (L, T y X): los espesores se proyectan según el ángulo antes de decidir si una
  interrupción es un encuentro o un hueco.

## 1.22.0-dev — 2026-11-14

Integra la entrega C1/D2 de Codex (encargos R13-A2 y R14), revisada: SHA-256 correcto, parche aplicado sobre
la v1.21 sin conflictos; 464 pruebas con IngeCAD 0.8 y 456 + 8 omitidas con la 0.7.

### Carpintería en el espesor del muro (A2)
- Posición «a distancia»: retranqueo desde la cara de apertura o la opuesta, validado contra el espesor.

### Carpintería curva (C1)
- En muros curvos, la ficha elige carpintería **plana** (en la cuerda) o **curva**: ventana fija, ventana
  corredera y puerta corredera siguen el arco, facetadas con la misma lista de estaciones en planta y en
  3D (flecha máxima 2 mm). Las abatibles curvas se rechazan con un aviso.
- Ancho y posición medidos sobre el arco (eje o cara). CURVAMURO conserva la carpintería y su posición.
- Pendiente: el IFC de IngeTrazo pierde las dimensiones y relaciones de los huecos curvos (T-09, T-04).

### Rejillas estructurales (D2)
- **EJES / REJILLA**: malla de una vez (`3x5,40 4,20`), números en una dirección y letras en la otra (sin I,
  O ni Ñ; después de Z, AA), prefijo y sufijo, burbujas en círculo o hexágono en ambos extremos, capa
  `ARQ-EJES` en trazo y punto gris fino. Eje suelto por dos puntos.
- **EDITAREJE** (mover, estilo, renumerar), **PILARESENEJES** (pilares en todas las intersecciones o en una
  zona, un Deshacer) y **ACTUALIZAEJES** (para IngeCAD 0.7).
- Un pilar en una intersección guarda su marca (por ejemplo `B-3`) y se mueve con el eje (reactores en 0.8).
  La marca viaja en `Pset_ColumnCommon.Reference` y, como IngeTrazo no escribe ese conjunto, también en el
  nombre exportado (`[B-3]`).
- Cotas en cadena y totales de la rejilla, regeneradas al mover un eje.
- Las rejillas viajan como datos (`reference_grids`) en `.arqbim` e IGZ; IngeTrazo no admite `IfcGrid`
  (T-14). Pendiente: ejes curvos o radiales y ortogonal según la rejilla.

## 1.21.0-dev — 2026-11-14

### Clasificación normativa de los recintos (CTE e ITC-BT-25)
- La ficha del recinto tiene un grupo nuevo con **una etiqueta por documento**: DB SI (uso y ocupación),
  DB SUA 4, DB SUA 9 (uso del recinto y unidad de uso), DB HE, DB HE 3, DB HR, DB HS 2, DB HS 3, DB HS 6 e
  ITC-BT-25. Son 11 conjuntos y 122 etiquetas, con las categorías de los propios documentos (catálogo
  facilitado por el usuario).
- «Proponer según el uso (vivienda)» rellena lo que se deduce sin ambigüedad del uso del recinto
  (Dormitorio → DB HR protegido, DB HS 3 dormitorio, ITC-BT-25 dormitorios…). El resto lo elige el usuario.
- La clasificación se guarda en el recinto, se edita con PROPIEDADESARQ o con doble clic (un Deshacer) y se
  exporta como conjunto de propiedades `ARQ_ClasificacionCTE`, que llega al IFC si IngeTrazo escribe los
  conjuntos propios (consulta #1222).
- Clasifica; **no comprueba el cumplimiento**. La densidad de ocupación del DB SI y su cálculo quedan para una
  versión posterior, con los valores verificados contra el texto oficial.

## 1.20.3-dev — 2026-11-14

Integra la entrega R14-b de Codex (calidad de LINEASAMURO), revisada: SHA-256 correcto, parche aplicado sobre
88f9756, 391 pruebas con IngeCAD 0.8 y 386 + 5 con la 0.7 reproducidas. Con un plano real del usuario
(privado, escalado ×4) pasa de 11 a 19 puertas reconocidas, con las mismas 16 ventanas, y desaparece el
muro duplicado de la entrada retranqueada.

- Trazos contiguos de una misma cara se reúnen antes de emparejar: tabiques de 0,10 cortados por los marcos.
- Puertas dobles con dos giros en las jambas, aunque no haya hoja dibujada; pivotes desplazados por el marco.
- Vidrio: cobertura acumulada de líneas fragmentadas, anclada a las jambas; tolera alféizar exterior.
- Machones alineados: cada discontinuidad se decide por separado (sin muros fantasma).
- Entrada retranqueada: el frente se separa solo con dos retornos y una puerta posterior dibujada.
- Previsualización con símbolos: puerta con su giro, ventana con su vidrio, vano con una X.
- Las desviaciones respecto al `walldetect` original de cad2ingetrazo están en `docs/DESVIACIONES_walldetect.md`.

## 1.20.2-dev — 2026-11-14

Prueba del usuario con un plano real de LINEASAMURO (privado; no se incorpora) y entrega R14 de Codex.

### Corregido (dirección técnica)
- **Planos que no están a escala real.** El plano de prueba estaba dibujado a 1/4: muros de 0,05–0,075 y
  giros de puerta de 0,20. LINEASAMURO lo trataba como metros y emparejaba líneas al azar (13 «muros» y 3
  huecos sin sentido). Ahora, si los giros de la carpintería miden menos de 0,35, **se detiene** sin tocar
  el dibujo y propone el factor (`ESCALA ×4`). Con el plano escalado salen 27 muros y 26 huecos.
- **Capas apagadas o inutilizadas.** Se leían igualmente. Ya no se convierten (salvo lo designado con
  clics); el aviso dice cuántos objetos se han omitido.
- **Designar con ventana.** «Designar gráficamente» solo admitía objetos uno a uno. Ahora, al pulsar en
  vacío, se abre una ventana: hacia la derecha toma lo que queda dentro; hacia la izquierda, lo que toca.

### Integrado de Codex (R14, revisado)
- Huecos en muros curvos reconocidos por LINEASAMURO (carpintería plana en la cuerda; la curva sigue
  pendiente).
- La previsualización dibuja los ejes curvos; la confirmación detecta cambios en definiciones de bloques
  y unidades; los identificadores de huecos se conservan al Deshacer/Rehacer; HATCH de aristas rectas.
- Reabrir el cuadro respeta las capas puestas en «No convertir».

## 1.20.1-dev — 2026-11-14

Revisión a fondo de LINEASAMURO para planos con la carpintería en una sola capa (puertas y ventanas
dibujadas con líneas y polilíneas, como en muchas aplicaciones LISP).

### Corregido
- **Carpintería en una capa.** El cuadro de R12 solo ofrecía «Puertas», «Ventanas» y «Vanos», y la categoría
  elegida se imponía a todos los huecos de esa capa: una capa con puertas y ventanas salía entera como
  puertas. Nueva categoría **«Carpintería (puerta o ventana según el dibujo)»**, que no impone tipo: el giro
  dibujado hace la puerta y las líneas de vidrio, la ventana. «Puertas» y «Ventanas» siguen siendo órdenes
  explícitas, también para excepciones designadas con clics (por ejemplo, una puerta corredera sin arco).
- **Planta dentro de un bloque.** Las entidades de un bloque se clasificaban con la capa de la referencia,
  no con la suya: todas las líneas del bloque recibían una única categoría. Ahora cada una va por su propia
  capa (la capa «0» toma la de la referencia, como en DXF), salvo que la referencia se designe con clics. El
  cuadro lista también las capas interiores de los bloques. Los votos de puerta y ventana y el tipo de muro
  (muro, medianera o tabique) se leen igualmente dentro de los bloques.

### Añadido
- El cuadro propone, la primera vez, la categoría de cada capa por su nombre (*pared*, *muro*, *pilar*,
  *carp*, *puert*, *ventan*, *escal*, *reja*, *barand*…); las de *cámara*, *aislamiento* y *cota* quedan sin
  convertir. El operador confirma o cambia.
- Si falta `_arqbim_sync.py` en IngeTrazo, la importación se detiene antes de tocar nada y explica qué copiar.

## 1.20.0-dev — 2026-11-14

Integra la entrega R12 de Codex (encargo de frentes abiertos), revisada por la dirección técnica: SHA-256
correctos, parche aplicado sobre 5e49bbe y las mismas cifras reproducidas (329 pruebas con IngeCAD 0.8; 324
y 5 omitidas con la 0.7; 6 pruebas aparte con el núcleo oficial de IngeTrazo 0.6.1).

### Reimportar en IngeTrazo sin duplicar (R12, F1)
- Volver a abrir un `.arqbim` **actualiza** el modelo en lugar de añadir otra copia.
  - Los elementos se reconocen por su identificador BIM.
  - Los cambiados se sustituyen conservando su objeto, los nuevos se añaden y los que ya no existen se retiran.
  - Todo es **un solo paso de Deshacer**. Si nada ha cambiado, no se toca la escena.
- Usa la orden de historial que IngeTrazo ofrece a las extensiones (`_arqbim_sync.py`, junto a la extensión;
  hay que copiar los dos ficheros).
- Límites: las importaciones anteriores a esta versión no se migran solas, y si chocan se rechazan. Dos
  modelos con el mismo nombre de fichero se tratan como el mismo.

### LINEASAMURO con clasificación (R12, F4)
- Al lanzarla se abre un **cuadro de clasificación**: cada capa se asigna a muros, medianeras, tabiques,
  pilares, puertas, ventanas, vanos, rejas, barandillas o escaleras, o se excluye.
  - «Designar gráficamente» permite asignar objetos con clics; prevalecen sobre la capa.
- Lee también **rellenos y rayados simples** (HATCH/SOLID) y la geometría de **bloques**, sin explotarlos.
- **Previsualización** de ejes y recuento antes de tocar el dibujo; Intro o «Confirmar» aplica, «Cancelar»
  descarta. Un Deshacer devuelve el plano original.
- Rejas, barandillas y escaleras se clasifican pero **quedan pendientes**: no se convierten todavía.
- Sin ventana (pruebas, scripts) se conservan las opciones de siempre (K/L/R).

### Fichas auxiliares (R12)
- `element_sheets.element_form` reúne las fichas de muro y pilar (con esquema de la sección) y prepara las de
  viga, pasamanos, barandilla y reja. Estas cuatro solo recogen parámetros: aún no hay orden que las inserte.

### Pruebas y estudios (R12)
- Regresiones de partición de polígonos (F5): sin cambios en el algoritmo.
- T-09 medido con el IngeTrazo oficial: un muro curvo de 4,44 m sale en el IFC con 0,33 m de longitud y 2,70 m
  de espesor; ya está cubierto por la consulta #1222.
- C-07: IngeCAD 0.8 guarda la XDATA con acentos correctamente; el aviso no se ha reproducido.

## 1.19.0-dev — 2026-11-14

Incorpora lo que la auditoría R10 de Codex propone y conviene ya (carpinterías 3D, ficha de carpintería,
identidad del intercambio, higiene del repositorio), tras evaluarla una a una.

### Carpinterías en 3D (R10, S1)
- **Puertas y ventanas ya no llegan a IngeTrazo como un bloque.** Cada una se construye con sus piezas reales:
  - el **marco**, un solo anillo alrededor del hueco (en una puerta, jambas, cabecero y un umbral de 5 mm);
  - las **hojas** donde cierran: una o dos en las puertas abatibles y fuera del cerco en las correderas;
  - en las ventanas, los cuatro **perfiles** de cada hoja con su **vidrio** (corredera en sus guías);
  - el **alféizar**, que sobresale de la fachada.
- **Mismo origen que la planta.** Las piezas salen del mismo registro y de las mismas reglas que el símbolo en
  planta (`openings.carpentry_parts` junto a `plan_symbol`).
- **Una sola malla en IngeTrazo.** Todas las piezas van en la malla de la puerta o la ventana, con el material
  de cada pieza en sus caras (vidrio translúcido). Así el IFC las escribe todas en el mismo `IfcDoor` o
  `IfcWindow`, y IngeTrazo mide bien su ancho y su alto (`OverallWidth/OverallHeight`), porque la cara del
  marco es el contorno completo.
  - Un contenedor con piezas hijas, como hace el ejemplo Windowizer, se habría perdido en el IFC: es T-08,
    reproducido y registrado.
- **Datos de cada pieza.** El volumen es el de las piezas, no el del hueco. Las piezas (nombre, función,
  material y volumen) viajan en el `.arqbim` y en el IGZ, que sirve como base de una memoria de carpintería.

### Ficha de carpintería (R10, S2)
- **Vista previa** del alzado (desde la cara hacia la que abre) y de la planta, con las medidas.
  - Se dibuja con el mismo código que la planta y el 3D.
  - Se actualiza al cambiar cualquier dato.
- **Materiales por pieza:** marco, hojas, vidrio y alféizar.
  - Se guardan en la carpintería y llegan al 3D.
  - Al pasar de puerta a ventana, cambian a los habituales de cada tipo.
- **Validación:** un cerco más ancho que el hueco desactiva «Aceptar» y se explica.
  - La ficha indica qué piezas tendrá en 3D.
- **DB-SUA (R10, H12):** el aviso dice solo lo que comprueba, el ancho de paso de la puerta frente al anejo A
  («cumple / no cumple; no evalúa el itinerario»), y ya no habla de «válida» o «NO válida».

### Intercambio (R10, S3)
- El tipo de apertura viaja con su valor canónico (`SWINGING`, `SLIDING`, `SIDEHUNG`, `FIXED`), no con su
  nombre traducido.
- La extensión de IngeTrazo comprueba las piezas: índices de pieza válidos, y piezas solo en puertas y
  ventanas.

### Repositorio (R10, H07 y H08)
- La CI no se ejecuta por cambios solo de documentación, y un envío nuevo a la misma rama cancela el anterior.
- El README ya no copia cifras de pruebas que caducan.

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

### IngeTrazo (registro T-09, sin enviar)
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

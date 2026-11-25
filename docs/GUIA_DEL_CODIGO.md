# Guía del código del plugin Arquitectura

### R29-E: recubrimiento hacia el interior

Cada franja del pilar conserva los lados exteriores de sus muros de contacto
en `cover_sides`. La anulación explícita del muro prevalece sobre el contorno
geométrico; los patios declarados también son exteriores. No depende del perfil.
Antes de resolver encuentros, `geom.bands` recorta la huella del recubrimiento
por la cara interior y conserva completo el núcleo estructural. Las curvas
usan las mismas cuerdas del muro. Se descartan bandas separadas del núcleo por
el propio muro. Así planta, recintos, sólidos y cantidades comparten la huella.

Una fachada abierta sin lado decidido no recibe un forro exterior supuesto:
se conserva el núcleo y se avisa «interior indeterminado» también en Planos 2D.
La partición interior sigue recubriéndose hacia ambos recintos. Las cantidades
de área comprueban que la cara expuesta pertenezca al material, para no medir
la cara desnuda del núcleo como si fuera revestimiento.
Pruebas: `test_r29_e_cierre_interior.py`, incluidas referencias de cara,
sentidos de dibujo, patio, curva, cantidades analíticas y Deshacer/Rehacer.

### R29-E: controles del recubrimiento y catálogo del dibujo

Las fichas y preguntas consultan `perfiles.incluye(perfil_activo(), TERMICO)`
para ofrecer aislamiento y clasificación constructiva. En Planos 2D solo se
ofrece la partición. Leer la ficha conserva los datos ocultos y la auditoría
omite sus avisos térmicos. La resolución geométrica y el contrato no consultan
el perfil: cambiarlo no modifica el modelo. `test_r29_e_perfiles.py` comprueba
campos, creación del tabique e igualdad completa del contrato entre perfiles.

`recubrimientos_pilar.aplicar_tipo` comparte la selección de partición entre
la ficha de PILAR y sus preguntas por texto. El registro conserva por separado
la partición, su material y el modo, espesor y material del aislamiento.
Los valores iniciales de los pilares nuevos incluyen una partición de 7 cm;
un `cover` numérico existente conserva su espesor, también si es cero.

`materiales_constructivos.py` valida las clases explícitas del catálogo
guardado en PARAMETROSARQ, pestaña Materiales constructivos. Su variante de
texto pregunta las mismas clases de los materiales de TIPOSMURO. La clase
ausente queda sin resolver: no se deduce por el nombre ni por conductividad.
La integración geométrica se prueba por separado de estos controles.
Pruebas: `test_r29_e_pilar_configuracion.py` y paridad de fichas R27.

`resolver_franjas` separa las cotas de contacto de los muros: un pilar no
extiende a toda su altura el aislamiento encontrado en una sola planta.
`exchange.read_model` calcula una copia sin escribir el dibujo; las franjas
se usan en `geom.bands` para los mismos encuentros, recintos y sólidos.
Solo la regeneración transaccional guarda los resultados y el portador.
`RegenerateContoursCommand` conserva puntos, registro, marco e invisibilidad
anteriores para Deshacer/Rehacer, incluidos cambios de tipo y clasificación.

El portador completo de un pilar con partición se oculta; sus detalles
agrupados muestran núcleo y caras libres de cada capa en ARQ-PARTICIONES y
ARQ-AISLAMIENTOS. Así no se dibuja un anillo que invada los muros. Las capas
se exportan como IfcCovering CLADDING/INSULATION con host, franjas, material,
área expuesta y volumen. Si cambia el material entre alturas, cada material
aislante tiene una identidad derivada estable. Un espesor variable no se
reduce a una medida Width falsa. Las copias compartidas se generan desde
estas mismas fuentes, sin importar anfitriones al cargar sus módulos.
Pruebas analíticas, recintos, falta de clasificación, escala nativa y un
solo Deshacer: `test_r29_e_pilar_geometria.py`. Las limitaciones del escritor
IFC se comprueban en la cadena oficial y se documentan por separado.

### Cobertura de las copias cargadas por IngeCAD

Las pruebas de integración cargan una copia temporal del plugin, como el
cargador real. Medir solo el directorio original excluye esas ejecuciones.
`.coveragerc` incluye las copias y las fuentes compartidas generadas y las
asocia con su fichero original al combinar los datos. El `__init__.py`
generado de `arq_shared` se excluye porque no es copia del del plugin.

Se usa `pytest --cov --cov-config=.coveragerc`; `--cov=arquitectura` vuelve a
limitar la medición al directorio y no sirve para este cargador. La prueba
`test_cobertura_copias.py` ejecuta la soldadura desde una copia y comprueba
que sus líneas se atribuyen a `arquitectura/geom/soldadura.py`.

### Depuración D1: avisos nuevos y cierres de bucles

`tests/test_depuracion_estatica.py` ejecuta las reglas F, B023, B006, B008 y
E722 de Ruff. Compara cada aviso, con su multiplicidad, con el registro
`tests/ruff_admitido.json`; no se ignoran reglas ni ficheros enteros. Cambiar
la versión fijada de Ruff exige repetir el triaje. Las importaciones y
variables revisadas se conservan cuando no ocultan un fallo funcional.

`test_depuracion_cierres.py` comprueba los carriles alternos de los armarios,
la separación de categorías al convertir y la validación que ejecuta el
contorno de muro aunque se descarte su retorno. Los cierres señalados se
consumen antes de pasar a la siguiente iteración. No se aplican correcciones
sugeridas a esos cierres porque estas pruebas no reproducen el fallo.

### R29: adenda de manillas y memoria v3

`openings.alturas_manillas` comparte la validación de altura con la generación
de las piezas: las puertas abatibles llevan una pareja enfrentada en la hoja
activa, o en las dos hojas con `handles_mode=ambas`. En ventanas, `handles=2`
reparte dos palancas interiores a tercios de la hoja; una altura explícita es
el centro de la pareja. Se rechazan las parejas sin espacio suficiente, sin
encoger sus piezas. Las correderas y los frentes de armario conservan un tirador
por hoja activa. No se modelan cierres ni pestillos.

La ficha, sus variantes de texto, el catálogo, el contrato y la definición de
tipos comparten esos campos. En los registros anteriores, los valores ausentes
son `activa` y `1`. Solo los campos que modifican piezas separan tipos. El plano
de memoria pasa a versión 3; los planos v2 requieren Actualizar con el mismo
mecanismo de aviso y la misma identidad y posición que en C3.

Pruebas: `test_r29_adenda_manillas.py`, `test_r29_manillas.py` y
`test_r29_memoria_version.py`. La posible opción de tirador largo vertical
(`handle_kind`) queda como propuesta para una versión posterior.

### R29-E: núcleo integrado de recubrimientos

`recubrimientos_pilar.py` separa el espesor de la partición (`cover`) del
aislamiento resuelto y no modifica las entradas. Las fichas y la regeneración
usan sus mismas reglas; el contrato contiene las piezas de cada capa.

La heurística preliminar de primera cara y nombres de materiales queda
sustituida por el criterio recibido el 24-11: lado exterior geométrico,
orden explícito de capas y clasificación de materiales en el catálogo.
La colocación de las capas del muro ya llega a las fichas, al registro y al
contrato. El recubrimiento del pilar se integra por franjas de altura.
El criterio completo y los casos obligatorios constan en
`docs/REVISION_EXTERNA_D1_2026-11-24.md`. Las pruebas del núcleo no certifican
por sí solas el resultado: también se comprueban sólidos, recintos y persistencia.

Solo los recintos declarados `exterior_cubierto` o `exterior_descubierto`
exponen la cara del anillo interior: una clasificación desconocida no se
interpreta como exterior. Lo comprueba `test_r29_e_caras_exteriores.py`.

### R29-G: precisión de la carpintería curva

La ficha desactiva `facet_sagitta` cuando la geometría es plana y explica su
significado con una ayuda emergente. La variante por texto solo lo pregunta
al elegir geometría curva. Ambas conservan el mismo valor para reutilizarlo
si se cambia de geometría; la validación y el facetado siguen en
`curved_carpentry.py`. Pruebas: `tests/test_r29_precision_curva.py`.

Esta guía es para quien vaya a **leer, estudiar o mantener** el código. No sustituye al manual de uso (`docs/MANUAL.md`). Explica cómo está organizado el plugin, qué recorrido hace un elemento desde el clic hasta el IFC y dónde buscar cada cosa.

Versión de referencia: **1.48.21-dev**, con 86 módulos y unas 26 000 líneas en `arquitectura/`, más la extensión de IngeTrazo en `ingetrazo_ext/`.

---

## 1. La idea en cuatro frases

1. **El dibujo de IngeCAD es la única fuente.** Cada muro es una polilínea de IngeCAD (su eje o su cara de referencia) que lleva sus datos BIM en XDATA: identidad, espesor, altura, nivel, tipo… No hay otra base de datos.
2. **Todo lo demás se deriva y se regenera:** el contorno del muro con sus encuentros, los recintos, los símbolos de puertas, los rótulos y los grupos de selección. Tras cada cambio se borra y se vuelve a calcular. Así nunca queda nada desactualizado.
3. **Planta, 3D e IFC salen de la misma geometría.** El motor de encuentros (`geom/junctions.py`) calcula una sola huella por elemento. Con ella se dibuja la planta, se levanta el sólido 3D y se miden las cantidades.
4. **Cada orden es un solo paso de Deshacer**, aunque cambie muchas entidades (`transactions.py`).

---

## 2. Recorrido de un elemento: de un clic al IFC

```
 Usuario                IngeCAD + plugin                                   IngeTrazo
 ───────                ─────────────────                                  ─────────
 clic en MURO ──► wall_tools.MuroCarasTool  (interacción: puntos, opciones)
                     │  crea la orden
                     ▼
                architectural_v10.create_wall  (registro BIM + polilínea + XDATA)
                     │
                     ▼
                transactions.apply_architectural_change   ← un solo Deshacer
                     │  ejecuta la orden y después…
                     ▼
                wall_network.RegenerateContoursCommand (regeneración)
                     ├─ exchange.read_model ............ lee muros, pilares y huecos del dibujo
                     ├─ geom/bands.solve_records ....... encuentros por franjas de altura
                     │     └─ geom/junctions.solve ..... UNA huella por muro
                     ├─ dibuja contornos, símbolos y rótulos
                     └─ space_envelope.outline ......... recintos (geom/spaces)

 EXPORTARBIM ──► bim_export → exchange.build ──► fichero .arqbim (JSON)
                     ├─ geom/solids ......... sólidos 3D cerrados desde la misma huella
                     └─ cantidades, Psets, relaciones
                                                     │
                                                     ▼
                                    ingetrazo_ext/arquitectura_bim.py
                                    (valida el contrato y crea los grupos)
                                                     │
                                                     ▼
                                            IGZ  ──►  IFC (exportador de IngeTrazo)
```

**Si una edición se hace con órdenes de IngeCAD** (DESPLAZA, GIRA, pinzamientos), la detecta `reactor.py`. Este lanza la misma regeneración, y `frame.py` traduce el movimiento a los datos BIM.

---

## 3. Mapa de módulos por capas

Las capas van de abajo (geometría pura, sin IngeCAD) a arriba (órdenes que ve el usuario). **Una capa solo usa las de debajo.**

### 3.1 Geometría pura: `geom/` (no importa nada de IngeCAD)
Se puede probar sin IngeCAD. Es la parte más delicada y la mejor probada.

| Módulo | Qué hace |
|---|---|
| `geom/polygon.py` | Núcleo de polígonos: área, recorte por semiplano, trozos convexos, unión (`merge`), resta. |
| `geom/junctions.py` | **Motor de encuentros.** De los muros (eje, espesor, referencia) a una huella por muro: esquinas, T, cruces, encuentros a cara, pilares embebidos. |
| `geom/bands.py` | Encuentros por franjas de altura (muros de distinta altura) y la entrada de pilares. Lleva las particiones virtuales al resultado. |
| `geom/spaces.py` | Recintos: el hueco que dejan los muros alrededor de un punto, el reparto por particiones virtuales y los muros exteriores. |
| `geom/solids.py` | Sólidos 3D cerrados desde las huellas: prismas, muros con huecos, comprobación de caras. |
| `geom/curves.py` | Arcos de los muros curvos; `MAX_SWEEP` (350°) es el arco mayor de un muro. |
| `geom/drafting.py` | Las decisiones geométricas de los gestos de dibujo (dónde termina un muro, qué cara se pincha…). |
| `geom/curved_drafting.py` | Los mismos gestos cuando la referencia es un arco: esquina en L contra un muro curvo, paralela a un arco o círculo, división radial, alargar hasta caras curvas. Python puro. |

### 3.2 Elementos BIM: registro, creación y edición
| Módulo | Qué hace |
|---|---|
| `architectural.py` | Lectura y escritura de los datos BIM en XDATA (`metadata`, `_xdata`) y la comprobación de un muro con sus huecos (`validate_wall`). |
| `architectural_v10.py` | **Crear y editar** muros y carpinterías (`create_wall`, `edit_wall`, `create_opening`, `edit_opening`). Es el núcleo actual, aunque su nombre diga «v10». |
| `wall_categories.py` | Categorías de muro (fachada, partición, medianera, sótano, defensa) y sus capas; `layer_name` conserva ARQ-TABIQUES en dibujos sin migrar. |
| `vistas_arq.py` | SECCIONARQ y ALZADOARQ: dibujan y regeneran (Actualizar) las vistas derivadas, con su ancla, sus detalles y la marca en planta. |
| `geom/vistas.py` | Corte y proyección de los sólidos del contrato con una cámara horizontal y eliminación exacta de líneas ocultas (Python puro). |
| `catalogo_constructivo.py` | CATALOGOEC: catálogo de elementos constructivos del usuario (IFC importados), contraste con la biblioteca térmica del Ministerio y tipos de muro. |
| `wall_constraints.py` | Altura del muro de nivel a nivel (restricción superior). |
| `defensas.py` | Barandillas, balaustradas y antepechos: un muro con categoría «defensa». |
| `particiones_virtuales.py` | Límites de recinto sin muro, y su orden. |
| `perfiles.py` | Perfiles de trabajo (Planos 2D, Modelo BIM, Modelo Térmico): órdenes ofrecidas, campos térmicos de las fichas y avisos de ARQVALIDAR. No cambian el modelo. `ARQ_PERFIL` fuerza uno; las pruebas usan el térmico. |
| `openings.py` | Carpinterías: hueco, piezas (marco, hojas, vidrio), símbolo en planta y medidas. |
| `curved_carpentry.py` | Carpintería curva en muros curvos. |
| `cabinets.py` | Armarios adosados y empotrados. |
| `columns.py`, `sections.py`, `profiles.py` | Pilares: huella, secciones y perfiles de acero. |
| `slabs.py` | Forjados: el sombreado de IngeCAD es su geometría. |
| `levels.py`, `level_layers.py` | Niveles del edificio y sus estados (encendido, inutilizado, bloqueado) sobre las capas de IngeCAD. |
| `parameters_arq.py` | Valores por defecto del dibujo, tipos de muro y usos. |
| `grids.py` | Rejillas de ejes estructurales. |

### 3.3 Regeneración y coherencia
| Módulo | Qué hace |
|---|---|
| `transactions.py` | Una acción arquitectónica = un paso de Deshacer (orden + regeneración). |
| `wall_network.py` | **La regeneración:** contornos, recintos, rótulos, símbolos y grupos de selección. |
| `space_envelope.py` | Contorno y altura libre de un recinto (forjados, falsos techos y particiones). |
| `superficies.py` | Superficie útil según criterio normativo y tabla de superficies. |
| `reactor.py`, `frame.py`, `sync.py` | Ediciones hechas con órdenes de IngeCAD: detección, traducción y resincronización. |
| `integrity.py`, `quality.py` | Comprobaciones antes de exportar (ARQVALIDAR) que informan sin bloquear. |
| `migration.py` | Migración de dibujos antiguos (ARQMIGRAR). |

### 3.4 Intercambio con IngeTrazo
| Módulo | Qué hace |
|---|---|
| `exchange.py` | **El contrato `.arqbim`:** `read_model` lee el dibujo y `build` compone elementos, sólidos, cantidades, Psets, niveles y relaciones. |
| `bim_export.py` | Orden EXPORTARBIM (escribe el fichero). |
| `ingetrazo_ext/arquitectura_bim.py` | Extensión de IngeTrazo: valida el contrato y crea grupos, capas y materiales. |
| `ingetrazo_ext/_arqbim_sync.py` | Reimportación por identificador, sin duplicar. |
| `ingetrazo_ext/_arq_edit.py` | Panel «Propiedades de Arquitectura» en IngeTrazo: proponer cambios de tipo y medidas y exportar el `.arqcambios`. |
| `ingetrazo_ext/arq_shared/` | **Copia generada** del código del plugin que necesita la extensión (geometría, carpinterías, contrato). La crea `scripts/bundle_roundtrip.py` al construir el ZIP y al pasar las pruebas. **No se edita ni se guarda en el repositorio**: se corrige la fuente en `arquitectura/`. |
| `roundtrip.py`, `roundtrip_model.py` | Ida y vuelta con IngeTrazo: instantánea del dibujo en el contrato, propuestas de cambio, conflictos y SINCRONIZARARQ. |

### 3.5 Órdenes (interacción con el usuario)
Las órdenes solo interactúan: piden puntos, leen opciones y crean las órdenes de 3.2. No contienen geometría propia.

| Módulo | Órdenes |
|---|---|
| `wall_tools.py` | MURO, DEFENSA, PARTICIONVIRTUAL, MUROPARALELO, ESTIRAMURO, PIVOTAMURO, BORRATRAMO, PARTEMURO, UNIRMURO, DIVIDEMURO, RECINTO |
| `curve_tools.py` | MUROCURVO, CURVAMURO |
| `opening_tools.py` | CARPINTERIA, PUERTAARQ, VENTANAARQ, HUECOARQ, MOVERCARP |
| `temp_dims.py` | Cotas temporales de MURO y CARPINTERIA |
| `tabulador.py` | Tab recorre las cotas temporales y fija su valor (filtro de teclado mientras la orden lo admite) |
| `column_tools.py` | PILAR |
| `cabinet_tools.py` | ARMARIOBIM (la geometría está en `cabinets.py`) |
| `roundtrip.py` | SINCRONIZARARQ |
| `slab_tools.py` | FORJADO, HUECOFORJADO |
| `grid_tools.py`, `grids.py` | EJES, EDITAREJE, REJILLA, PILARESENEJES, ACTUALIZAEJES |
| `levels.py` | NIVELES, NIVELASIGNAR |
| `entrada_revisada.py` | Contrato de procedencia, hashes y autorización por capa/entidad de las entradas revisadas. |
| `convert_tools.py` y `conversion_*.py` | LINEASAMURO (de un plano de líneas a muros BIM) |
| `cotas.py` | COTAMUROS |
| `superficies.py` | SUPERFICIES |
| `arq_properties.py`, `tools_v10.py`, `double_click.py` | PROPIEDADESARQ, EDITARARQ, doble clic |
| `parameters_arq.py` | PARAMETROSARQ, TIPOSMURO, USOSARQ |
| `quality.py`, `migration.py`, `bim_export.py` | ARQVALIDAR, ARQMIGRAR, EXPORTARBIM |
| `bim_dialogs.py`, `element_sheets.py`, `conversion_dialog.py` | Fichas (ventanas de propiedades) |
| `__init__.py` | Registro del plugin, menú y barra. Además, las **herramientas heredadas** de la v1.5 (PUERTA, VENTANA, ARMARIO, ESCALERA, CAPASARQ, URL, VERTICES…), en el menú «Herramientas antiguas». |

### 3.6 Utilidades
`compat.py` (adaptación a la API de IngeCAD), `cte_usos.py` (clasificación normativa de recintos), `vendor/` (copias de bibliotecas que IngeCAD no instala).

---

## 4. Convenciones

- **Datos BIM:** `metadata(entidad)` los lee y `_xdata(msp, entidad, registro)` los escribe. Son un diccionario JSON con, al menos, `kind` (`wall`, `column`, `opening`, `space`, `slab`, `virtual_partition`…), `id` (identidad persistente, uuid) y `schema`. **Nunca se escribe XDATA a mano fuera de esas funciones.**
- **Órdenes deshacibles:** todo cambio pasa por una orden de IngeCAD (`AddEntityCommand`, `EditArchitecturalCommand`…) y, si toca la planta, por `apply_architectural_change`.
- **Errores de usuario:** las funciones de 3.2 lanzan `ValueError` con un mensaje en español. Las órdenes de 3.5 lo capturan y lo muestran (`ctx.echo`). La orden sigue viva.
- **Versiones del anfitrión (directriz del propietario, 18-11-2026):** IngeCAD e IngeTrazo aún no son estables, así que **solo se trabaja con la última versión publicada de cada uno** (hoy IngeCAD 0.8.0 e IngeTrazo 0.6.2.1). No hace falta probar ni mantener versiones anteriores. El código que ya distingue versiones (`hasattr`) puede quedarse, pero no se añade más.
- **Archivos antiguos (misma directriz):** el plugin aún no se usa profesionalmente, así que no hace falta que los dibujos o contratos de versiones anteriores sigan funcionando. Las migraciones no son prioritarias. Esto cambiará cuando la depuración coincida con un IFC que pueda entregarse con confianza a otras aplicaciones de cálculo (térmico, estructural, instalaciones): desde entonces, la compatibilidad con archivos anteriores será obligatoria.
- **Sin marcas comerciales** en código, comentarios ni interfaz. Se describe el comportamiento, no el programa que lo inspira.
- **Código que viaja a IngeTrazo:** los módulos de `scripts/bundle_roundtrip.py` (geometría, carpinterías, contrato, defensas, particiones) **no pueden importar IngeCAD al cargarse**. Si necesitan algo del anfitrión, lo importan dentro de la función que lo usa.
- **Estilo:** una instrucción por línea, nombres descriptivos y un comentario que explique el porqué de cada paso no evidente. El código compacto de varias instrucciones por línea (como el de R21) se irá reescribiendo en la etapa 3.
- **Idioma:** los mensajes al usuario están en español. Los comentarios antiguos están en inglés. Los módulos nuevos (`defensas.py`, `particiones_virtuales.py`) y los resúmenes de cabecera están ya en español, y los demás se irán pasando por etapas (apartado 8).

---

## 5. Cómo añadir un elemento nuevo (ejemplo real: v1.29)

La v1.29 añadió dos elementos por caminos distintos. Sirven de plantilla.

### Camino A: el elemento es una variante de otro. Ejemplo: la **defensa** como muro.
1. **Vocabulario y reglas** en un módulo propio (`defensas.py`): tipos, valores por defecto, comprobación, clase IFC y sólido 3D.
2. **Categoría** en `wall_categories.py` (nombre y capa).
3. **Datos admitidos** en `create_wall` y `edit_wall` (`architectural_v10.py`), y comprobación en `validate_wall`.
4. **Orden:** una subclase de la orden existente (`DefensaTool(MuroCarasTool)`) que cambia valores de partida y opciones.
5. **Exportación:** en `exchange.build`, la rama de la categoría (clase IFC, Psets, sólido).
6. **Extensión de IngeTrazo:** admitir la clase IFC y su capa.
7. **Registro:** `__init__.py` (orden, menú e icono en `icons/`) y la capa en `LAYERS`.
8. **Pruebas** (`tests/test_defensas_y_particiones.py`) y **manual**.

Todo lo demás (encuentros, recintos, niveles, Deshacer, edición) se hereda.

### Camino B: el elemento es nuevo. Ejemplo: la **partición virtual**.
1. **Módulo propio** (`particiones_virtuales.py`): `kind`, capa, `read(drawing)` y `create(...)` (una orden deshacible). La orden de usuario va en `wall_tools.py`, porque el módulo no debe importar IngeCAD: viaja también a IngeTrazo.
2. **Dónde interviene:** aquí, en los recintos. `solve_records(..., partitions)` la lleva al resultado y `geom/spaces.split_by_partitions` reparte el recinto.
3. **Edición nativa:** añadir el `kind` a `reactor.KINDS`.
4. **Capa** en `transactions.apply_architectural_change`.
5. **Exportación** en `exchange.build`.
6. Registro, pruebas y manual, como en A.

---

## 6. Pruebas

```bash
INGECAD_SRC=/ruta/a/ingecad QT_QPA_PLATFORM=offscreen python3 -m pytest -q
```

- Las pruebas usan **IngeCAD real** (solo la última versión publicada) y cargan el plugin como lo hace IngeCAD. La sesión de prueba (`tests/test_wall_tools.Session`) simula clics y opciones: `draw(s.tool('MURO'), (0, 0), (5, 0))`.
- Cada versión pasa todas las pruebas en ambas versiones de IngeCAD antes de publicarse.
- `tests/test_revision_persistencia_y_escala.py` vigila dos cosas: que guardar y reabrir no cambie el modelo, y que el coste por cambio no vuelva a crecer con el número de recintos.
- La cadena completa con IngeTrazo real (`.arqbim → IGZ → IFC`) se ensaya fuera del repositorio, con las fuentes oficiales de IngeTrazo (pendiente P5: incorporarla como prueba opcional).

---

## 7. Dónde buscar cuando algo falla

| Síntoma | Dónde mirar |
|---|---|
| Un encuentro de muros mal resuelto en planta | `geom/junctions.py` (`solve`) |
| La planta bien y el 3D mal | `geom/solids.py`, y `exchange.build` para el elemento |
| Un recinto que no se cierra o mide mal | `geom/spaces.py` (`space_at`, `split_by_partitions`) y `space_envelope.py` |
| Una orden no hace lo que debe | El módulo de la orden (apartado 3.5) |
| Algo se desactualiza tras una orden de IngeCAD | `reactor.py`, `frame.py`, `wall_network.py` |
| IngeTrazo rechaza el fichero | `ingetrazo_ext/arquitectura_bim.py` (`validate_contract`) |
| El IFC sale incompleto | Casi siempre es IngeTrazo: véase el registro de errores (T-02, T-03, T-05, T-15) |
| Lentitud con planos grandes | `wall_network.py` (regeneración), `geom/spaces.components` y `geom/junctions` |

---

## 8. Plan de ordenación del código (en curso)

| Etapa | Contenido | Estado |
|---|---|---|
| 1 | Esta guía y un **resumen en español** en la cabecera de cada módulo | **Hecho en la v1.29** |
| 2 | Cambiar de nombre `architectural_v10.py` → `elementos.py` y `tools_v10.py` → `muro_base.py`. Llevar las herramientas heredadas de `__init__.py` a `heredadas.py`. Dividir `wall_tools.py` (1700 líneas) en un módulo por familia de órdenes | Tras integrar R21-a, para no chocar con el trabajo de Codex |
| 3 | Documentar en español todas las funciones públicas (hoy, el 28 % de 1222 funciones y clases), empezando por el núcleo: `geom/junctions`, `geom/spaces`, `geom/solids`, `exchange` y `wall_network` | Después de la etapa 2 |
| 4 | Retirar el puente antiguo (EXPORTARIGZ, CONFIGIGZ, MURO3D, HUECO3D: `igz_bridge.py` y `tools3d.py`) | **Hecho en la v1.31**, por decisión del propietario |


### R24-P3: capas de material hacia IFC

La extensión `ingetrazo_ext/arquitectura_bim.py` añade `material_layers` y
`layer_offset` a las etiquetas de los muros, conservando los datos del contrato.
El desplazamiento reutiliza `geom/junctions.offsets`, a través de la copia
generada: eje `-e/2`, izquierda `0`, derecha `-e`. No se modifica la geometría
ni se versiona `arq_shared/`. Los demás elementos conservan sus etiquetas
`type` y `material` y no reciben capas. Las pruebas están en
`tests/test_r24_materiales.py`; se compara el desplazamiento con los vértices
reales de muros con varias orientaciones. El escritor de IngeTrazo se amplía
en una propuesta independiente sobre P1, sin un escritor alternativo.

El ejemplo público se genera con `scripts/generar_modelo_r24.py` desde órdenes
de IngeCAD y se comprueba con `scripts/verificar_cadena_r24.py` en IngeTrazo.
Este último valida la relectura IGZ, las capas y los tipos; exige los tres
errores de recintos pendientes de P2 y no los presenta como una validación
IFC completa. Ambos scripts reciben la carpeta de resultados como argumento.

### R25-P3b: línea de referencia del muro

La extensión añade `axis` únicamente a los muros rectos. Sus extremos son
`params.a` y `params.b`, a la cota absoluta `params.base`, restando el mismo
origen de escena que los vértices. No se deduce el eje del contorno ni se
mueve la línea cuando cambia la referencia de espesor. Los muros curvos
conservan la exportación anterior. Las pruebas están en `tests/test_r25_eje.py`.

`scripts/generar_modelo_r25.py` recibe carpeta, ángulo y, opcionalmente,
`lejano`; crea el edificio mediante órdenes de IngeCAD. El verificador
`scripts/verificar_cadena_r25.py` se ejecuta en el entorno de IngeTrazo y
comprueba la cadena con IfcOpenShell geom, incluyendo las interfaces de
las capas, los vértices mundiales y los volúmenes.

### Soldadura de vértices (`geom/soldadura.py`)

`Soldador` une los puntos a menos de una tolerancia (1e-7 m por defecto)
buscando en la celda del punto y en sus 26 vecinas, así que no tiene las
fronteras de `round()`: dos copias del mismo vértice a 1e-10 m se unen siempre.
Lo usan `geom/solids.py::boundary` (vértices y planos) y el validador de
contratos de la extensión. `boundary` calcula además en coordenadas locales
(resta un origen de metros enteros y lo suma al final) y limpia los lazos
(`_clean_loop`: repetidos seguidos y púas A→B→A). Pruebas:
`tests/test_soldadura_lejos_del_origen.py`.

### Herramientas antiguas (`ArchitectureTool` y `_ContextoPregunta`)

Las herramientas v0.7 se conservan (decisión del propietario). Escriben sus
preguntas con `echo`; `_ContextoPregunta` envuelve su contexto y manda como
aviso (`prompt`) toda línea que termina en dos puntos, para que IngeCAD no
repita con la respuesta el aviso de otra orden.

### Ayuda (`ayuda.py`, orden AYUDAARQ)

`SECCIONES` es la única fuente de la ayuda: órdenes agrupadas por tema, con un
resumen de una línea y sus opciones. `dialogo` la muestra en un cuadro con
buscador, árbol por secciones y detalle; `texto` la escribe ordenada en la
línea de órdenes cuando no hay ventana. `tests/test_ayuda_y_parametros.py`
exige que la ayuda contenga exactamente las órdenes registradas en
`PluginSpec` (herramientas y órdenes), de modo que una orden nueva sin ayuda,
o una ayuda de una orden retirada, hace fallar la batería. La misma prueba
comprueba que el código no lleva nombres comerciales.

### Biblioteca térmica (`biblioteca_termica.py`, orden BIBLIOTECAHE)

El plugin no distribuye el catálogo de la Herramienta Unificada: el usuario
importa su `BDCatalogo.bdc` (de la instalación, el `.bdc.utf8.gz` del IETcc o
un ZIP). `importar` lee los bloques BDL `MATERIAL`, `LAYERS`, `GLASS-TYPE`,
`NAME-FRAME` y `GAP` (g⊥ = SHADING-COEF × 0,86, criterio del IETcc), normaliza
los espacios repetidos de los nombres y avisa de las referencias rotas sin
descartarlas. `guardar` escribe un JSON atómico en la carpeta de configuración
del usuario (`ARQ_BIBLIOTECA_TERMICA` la cambia), nunca en el dibujo ni en el
repositorio. `u_opaco` calcula la U con las resistencias superficiales del
DA DB-HE/1. Es la base de E1–E3 (exportador a EnvolventeCTE). Pruebas:
`tests/test_biblioteca_termica.py` (BDL sintético; con `ARQ_BDC_PRUEBA`
también el catálogo instalado).

### Catálogo de elementos constructivos (`catalogo_constructivo.py`, orden CATALOGOEC)

v1.48.1. Mismo criterio que la biblioteca térmica: el plugin lleva solo el
lector; el usuario importa los IFC4 que exporta la aplicación web del
catálogo autonómico y el resultado va a un JSON de su carpeta de
configuración (`ARQ_CATALOGO_CONSTRUCTIVO` lo cambia). `leer_step` es un
lector STEP mínimo (sin IfcOpenShell): quita los comentarios `/* */`,
decodifica `\S\`, `\X\` y `\X2\` y repara `IFCREAL(15,00)`.
`soluciones_de` toma cada `IfcWallType`, `IfcSlabType` o `IfcRoofType` con
su conjunto de capas y sus conjuntos de propiedades; la clave es el código
de la solución (los GlobalId del catálogo se repiten entre ficheros). Los
textos con coma decimal son números y un 0 en magnitudes que no pueden ser
nulas (`SIN_CERO`) es «sin dato». `importar` acumula ficheros y avisa si un
código llega con datos distintos.

**Rango de las fuentes.** La biblioteca del Ministerio prevalece y no puede
haber contradicciones: `tipo_de_muro` solo copia nombres de material y
espesores (las propiedades térmicas se leen siempre de `biblioteca_termica`
por nombre) y `contrastar` compara solo materiales de **nombre idéntico**
(sin tildes, mayúsculas ni espacios repetidos), avisa de cada diferencia y
calcula la U con el Ministerio cuando todas las capas tienen
correspondencia. Las referencias al catálogo estatal solo se anotan si el
fichero las declara. Pruebas: `tests/test_catalogo_constructivo.py` (IFC
sintéticos; con `ARQ_CEC_PRUEBA` también una carpeta de IFC reales).

### Secciones y alzados (`geom/vistas.py`, `vistas_arq.py`)

v1.48.2. Primera vía de la 1.0: directa en IngeCAD, sin pasar por
IngeTrazo. La entrada son las caras de `exchange.build`, las mismas que van
al IFC, de modo que planta, 3D y vistas no pueden contradecirse.

- `Camara(p, q, lado, seccion, profundidad)`: coordenadas (s, z, t). Ese
  triedro no es directo, así que la normal de cada cara se calcula en el
  sistema del dibujo y se proyecta (`normal_local`).
- `cortes`: intersección de cada cara con t = 0, emparejando los cruces a lo
  largo de la recta (vale para caras cóncavas y con huecos) y encadenando los
  segmentos con la soldadura por tolerancia.
- `vistos`: aristas de las caras que miran a la cámara, recortadas a la franja
  de la línea. Para cada cara que puede taparlas (rejilla de 1 m), los tramos
  ocultos se calculan exactamente: cruces con sus bordes y el punto donde la
  arista atraviesa su plano. La superficie cortada tapa como una cara en t = 0.
- Juntas: una arista colineal con la de otra cara coplanaria situada al otro
  lado no se dibuja, entre dos masas (`MASIVOS`) o dentro de una misma pieza.
  Las piezas de una carpintería sí marcan sus líneas.
- `_sin_duplicados`: une los tramos colineales solapados, agrupando rectas por
  ángulo y distancia con la soldadura, sin redondear.

Aspecto (v1.48.3): las opciones generales `vista_relleno` (color, rayado
diagonal o cruzado), `vista_color` (gama de grises, `GAMA`) y `grosor_corte`,
`grosor_tierra` y `grosor_visto` (`GROSORES`, en mm) se aplican a las capas
`ARQ-VISTA-*` al generar cada vista. Lo que cambia en capas ya existentes se
guarda en `capas_cambiadas`, y el Deshacer lo restituye. La línea de tierra es
la cota ±0,00 en `ARQ-VISTA-TIERRA`. Los petos y barandillas de cubierta
(defensas) salen sin código propio, porque son elementos del contrato.

`VistaArq` (Command) sigue el patrón del plano de carpintería: ancla con los
datos, detalles etiquetados con `view_id`, grupo y capas `ARQ-VISTA-*`.
Actualizar sustituye todos los detalles en un Deshacer. Pruebas:
`tests/test_vistas_geometria.py` (cajas sintéticas con resultados calculados a
mano) y `tests/test_vistas_arq.py` (casa en la sesión real; con
`ARQ_VISTAS_DXF` guarda un DXF para revisarlo a ojo).

### Particiones (antes «tabiques»)

v1.48.1. La categoría `particion` sustituye a `tabique` y la capa
`ARQ-PARTICIONES` a `ARQ-TABIQUES`. Compatibilidad: `wall_categories.ALIASES`
lee `tabique`; `conversion_plan.role_name` lee el papel `tabiques`;
`layer_name(cat, capas)` devuelve ARQ-TABIQUES si el dibujo solo tiene esa,
y `_ensure_layers` no crea la nueva en él. `ARQMIGRAR` (`PartitionLayers`)
renombra ARQ-TABIQUES y sus capas por nivel, en el mismo Deshacer. Pruebas:
`tests/test_particiones_nombre.py`.

### R26-P4: huecos y medidas reales en el IFC

La extensión transmite `predefined` y `quantities` junto a la geometría ya
recentrada del hueco. En muros, usa las medidas del registro y el espesor;
los nichos llevan `RECESS` y su fondo. El contrato `.arqbim` no cambia.

En forjados, `Depth` es siempre el espesor. El contorno procede del
`footprint` o de las caras superiores. Se identifica un rectángulo por sus
cuatro vértices, ángulos rectos y lados opuestos iguales usando la tolerancia
de `geom/soldadura.py`: `Width` es el lado mayor real y `Height` el menor.
Para un contorno no rectangular se envía únicamente su `Area` exacta en
planta y `Depth`. No se usan cajas envolventes para inventar medidas.
El área se calcula trasladando primero el origen para evitar cancelaciones
en coordenadas topográficas. La copia compartida de la soldadura es la
misma que utiliza el validador de la extensión, sin importar IngeCAD.

`tests/test_r26_huecos.py` cubre rectángulos girados, círculo facetado, L,
fronteras de redondeo, puertas, ventanas, huecos libres y nichos.
`scripts/generar_modelo_r26.py` añade los casos de ensayo de P4, un forjado
con los cuatro contornos y el caso `aceptacion` (hueco sin carpintería y
cubierta de 30 cm sobre muros y recintos de 2,70 m), que es el modelo de la
prueba en la plataforma de cálculo; `scripts/verificar_cadena_r26.py` compara las
relaciones, las posiciones y el volumen leído con y sin sustracciones de
huecos por IfcOpenShell. Cada script se ejecuta en el entorno de su anfitrión.

### Variantes por línea de órdenes (R27)

`linea_campos.py` contiene las preguntas, sus valores por defecto y la lectura
con coma o punto y unidades explícitas. `ContextoLinea` conserva el contexto
real y señala que esa orden no debe abrir fichas. `PreguntasTexto` es una
mezcla de la herramienta nativa: no crea otra geometría ni otra historia.
Mientras se pide un texto, las palabras no se interpretan como referencias
a objetos. Al terminar las preguntas vuelven los mismos handlers nativos,
incluidas sus cotas temporales, referencias geométricas y validaciones.

`linea_fichas.py` describe los campos editables y sus condiciones (por ejemplo,
la altura fija o la derivada de niveles). Las fichas Qt y la entrada textual
usan los mismos normalizadores de muros, pilares y carpinterías para que no
se calculen de dos maneras las capas, el perfil o el ancho de una puerta.
`linea_ordenes.py` registra las variantes de creación con guion. Los campos
identificadores no se exponen para editarlos y una pregunta cancelada no
modifica el dibujo.

Las herramientas antiguas agrupan sus órdenes ya ejecutadas mediante
`History.fold`: crear varias líneas y capas sigue siendo un único Deshacer.
Las entradas inválidas de ejes conservan la fase, muestran el motivo y
permiten reintentar; un clic prematuro en BLOQUE conserva la elección de tipo.

`linea_configuracion.py` presenta por texto los parámetros, usos, tipos de muro,
niveles y asignación de nivel. Comparte las funciones de guardado con las fichas;
los identificadores de nivel se eligen por nombre y no se editan. En preguntas con
nombres coincidentes se puede elegir una opción mediante `#` y su número.

`linea_edicion.py` pregunta los valores de las fichas de elementos y ejes. Las
propiedades se aplican mediante `arq_properties.cambio_propiedades`; la ficha de
ejes y su variante comparten `GridEditTool.apply_axis`. Las coordenadas se editan
sin sustituir las identidades BIM ni las referencias a rejillas.

`linea_archivos.py` sustituye selectores de archivo y decisiones de conflictos
por preguntas. La lectura de cambios y el resultado final se comparten con la
sincronización con ficha; no cambia el contrato ni se añade una migración.

`linea_conversion.py` pregunta la clasificación, procedencia, rangos y asignación
gráfica de LINEASAMURO. Reutiliza `Classification`, el plan de solo lectura y la
confirmación transaccional. Nunca permite convertir REV-* por su nombre de capa.

`tests/escenarios_r27.py`, `tests/ventana_r27.py` y `tests/verificacion_r27.py`
preparan modelos sintéticos, ejecutan las órdenes por teclado en MainWindow y
registran historial, datos BIM y guardado real en DXF/DWG. Sus informes distinguen
la ejecución de la orden de las comprobaciones adicionales; un proceso sin
excepciones no demuestra por sí solo que el resultado sea correcto.

El recorrido R27 espera al renderizado antes de cerrar la ventana y conserva el
título de un selector mientras existe su objeto Qt. Para Deshacer/Rehacer, las
cotas comparan también el contenido de sus bloques gráficos anónimos: cambiar
el nombre interno del bloque no cambia la cota. Se comparan todos los datos BIM,
la geometría y la XDATA; la visibilidad DXF omitida equivale a su valor cero.

`linea_campos.entrada_con_prefijo` permite escribir `x 3x5` y `renumerar 4` sin
que el espacio confirme solo la primera palabra. Consulta la entrada de la
ventana mediante el contexto; no captura las coordenadas ni cambia IngeCAD.
La restauración de grupos en `sync.py` reutiliza sus manejadores antes de añadir
los miembros, para conservar también sus referencias DXF al deshacer.

El recorrido de ventana acepta también respuestas de prueba con tecla (F4, F5,
F6, Tab y Mayús+Tab). Activa la ventana después de cerrar una ficha y registra
el estado antes y después de la tecla, para comprobar la entrega del teclado sin
confundir la falta de activación de la pantalla virtual con un fallo de la orden.

Los campos de forjado comparten también `normalizar_forjado` con su ficha.
`parameters_arq.nuevo_tipo` centraliza Nuevo y Duplicar del catálogo tanto en Qt
como en texto. La precisión de cada pregunta coincide con la de su control;
mostrar un valor legible no modifica el valor almacenado al aceptar Intro.

Para reproducir opciones de archivo o campos condicionales, el recorrido admite
`R27_ORDEN_INICIAL` (orden con argumentos), `R27_ARCHIVO` (ruta que se teclea en
el selector real) y `R27_VALORES` (objeto JSON con respuestas por clave de campo).
Son datos del ensayo: la aplicación sigue recibiendo las respuestas por teclado.

`tests/ejecucion_sin_qt_r27.py` ejecuta órdenes en un proceso sin QApplication:
permite detectar un aborto de un selector o ficha sin cerrar pytest. Se usa para
parámetros, biblioteca, exportación y sincronización; el caso de niveles conserva
su comprobación aislada. `tests/probar_eje_sin_ventana.py` comprueba el mismo
límite para la edición de ejes. Las órdenes con ficha informan cuando falta Qt;
las variantes con guion continúan por texto. Una sincronización con conflictos
sin ventana no aplica cambios y remite a la decisión textual.

### Memoria de carpinterías (R28)

`memoria_carpinteria.py` es la definición pura de las piezas y sus marcas.
Obtiene medidas, materiales y plantillas del mismo `openings.carpentry_parts`
que usa el 3D, incluidos los desarrollos curvos y los frentes de `cabinets.fronts`.
La igualdad compara medidas con `geom.soldadura.TOLERANCIA`; no redondea claves,
y excluye la posición y la mano. La asignación devuelve un catálogo nuevo sin
escribir en el dibujo: sus contadores conservan la retirada de números y sus
marcas se reutilizan solo para piezas que siguen siendo iguales. Los grupos
comparan todos sus miembros, para evitar cadenas no transitivas de tolerancia.

`memoria_modelo.py` recorre las fuentes BIM, distingue los frentes de armario y
prepara una transacción para guardar `mark` en cada registro y el catálogo en un
POINT invisible con XDATA propia. La lectura nunca modifica el dibujo. La marca
manual se valida al reagrupar: renombra todas las piezas iguales y rechaza una
marca que ya describe otra pieza; `mark_manual` distingue la intención del usuario
de la marca automática que debe cambiar al cambiar las medidas. Las fichas y
las preguntas de R27 exponen `mark` mediante el mismo normalizador.

Los avisos y la ayuda de ELEMENTOS, SELATRIB, HIPERVINCULO, URL y LISTATEXTOS
explican su alcance informativo. Este cambio no altera sus menús ni ejecuta
selecciones, enlaces o copias nuevas. MEMORIACARP se rehace por separado a partir
de las fuentes BIM; no se confunde la aclaración de avisos con esa implementación.

El recorrido de ventana de R27 admite `R27_VALORES_CUADRO` para teclear campos
QLineEdit de una ficha real antes de aceptarla. R28 lo usa para comparar la edición
de `mark` en PROPIEDADESARQ y su variante; el ensayo conserva las identidades y
comprueba que la variante no abre cuadros.

### Plano de carpintería derivado (R28-A)

`memoria_tools.py` registra MEMORIACARP y -MEMORIACARP. La primera ofrece Ficha o
Actualizar antes de abrir un cuadro, de modo que Actualizar no pregunta nada.
La segunda usa PreguntasTexto. Ambas comparten `campos_memoria` y
`normalizar_memoria` de `linea_fichas.py`; las preguntas no tienen otro generador.
La escala inicial se lee de General → Escala de documentación, también editable
en -PARAMETROSARQ, y queda guardada en la configuración de cada plano.

`memoria_modelo.filas` filtra por planta/huecos, agrupa por marca o marca/planta,
cuenta unidades y manos vistas desde el exterior, consulta recintos y el espesor
de muro más frecuente. Las áreas de vidrio proceden de las piezas cerradas de
openings. La U solo se estima si coinciden exactamente los nombres normalizados
de vidrio y marco de la biblioteca: se pondera por áreas y se identifica «sin ψ»;
si faltan datos se muestra «sin datos», sin asignar valores genéricos.

`memoria_dibujo.py` utiliza las plantillas de `carpentry_parts`, sus desarrollos y
los símbolos comunes de `simbolos_apertura_alzado`. Las cotas son DIMENSION con
el estilo activo del dibujo, con anulación DIMSCALE igual a 20, 25 o 50. Los
tamaños gráficos se expresan en metros de papel, conservando las proporciones
de flechas y separaciones del estilo y un texto de 2,5 mm. No se modifica el
estilo del usuario. La geometría se dibuja en metros a tamaño
real. La tabla reutiliza `core.tables.insert_table`: en IngeCAD 0.8.0 ya produce
LINE/TEXT estables, por lo que no se introduce otro ACAD_TABLE ni un motor de tabla.

`memoria_plano.PlanoMemoria` conserva inserción, configuración, filas y huellas de
fuente/biblioteca en un POINT con XDATA `carpentry_schedule`. Cada derivado lleva
`carpentry_schedule_detail`, versión y `schedule_id`. Las capas de plano y cotas
se crean bloqueadas; Actualizar las escribe mediante su propia transacción.
Sus grupos ARQMEM_ son independientes de los grupos de fuentes ARQ_. Se guardan
las entidades y sus bloques de cotas para recuperar el mismo estado al deshacer.

La regeneración común recalcula marcas cuando existe catálogo y reconstruye los
rótulos `opening_mark`, incorporados al grupo de su carpintería. No rehace un
plano por sorpresa: ARQVALIDAR avisa cuando la planta o la biblioteca lo dejan
obsoleto. Actualizar reemplaza los derivados en su sitio, en un solo Deshacer.


### Continuidad de cubiertas: adenda 2, fuera de R28-A

La base futura de B2 es `roof_tile_tool.py` de PESI3D/ingetrazo-roof-tiles v1.3 y
`roof_any.py` de equipexq/archxq-it-lite v0.13.0, adaptado del primero con crédito.
Claude comunica GPL-3.0-or-later y pesos por lado/velocidad cero en piñones.
Antes de proponer una incorporación deben pasar los ocho casos de B0 y comprobar
patios y arranques distintos. Se anotarán los copyrights y la procedencia exactos
en la cabecera de cualquier módulo reutilizado y aquí, sin retirar «o posterior»
ni créditos. Las mejoras se ofrecerán a los autores, sin mantener una copia
divergente sin avisar. La estimación se rehace sobre esa base. Véase
`docs/ADENDA_2_R28_BASE_B2.md`. R28-A no incorpora ninguno de esos módulos.

### Presentación de medidas (R29-B)

`presentacion.py` centraliza los dos o tres decimales de longitud y las
anulaciones DIMDEC, DIMDSEP, DIMZIN y DIMLFAC de las cotas del plugin. Solo
produce textos y parámetros gráficos: nunca devuelve coordenadas redondeadas.
La mitad exacta se escribe siempre por exceso (0,885 → «0,89»), con una holgura
de una millonésima de la última cifra para que el error de coma flotante del
cálculo no cambie el texto; no se usa `round()`.
Lee `general.precision_medidas` (cm por defecto, o mm) y las fichas y preguntas
de PARAMETROSARQ guardan la misma configuración. La cota mínima nueva es 0,05 m;
los dibujos que guardaban otro valor lo conservan.

Las cotas temporales reciben el documento desde MURO, CARPINTERIA y MOVERCARP;
las fichas y la tabla de memoria usan el mismo formateador. Las áreas siguen
con dos decimales. COTAMUROS conserva la orden nativa de DIMENSION y aplica
las anulaciones antes de su único renderizado; su eliminación de tramos cortos
mantiene los extremos y la suma real de la cadena. SUPERFICIES usa la precisión
solo para las longitudes de las notas, no para calcular áreas o decidir usos.
Cambiar la precisión invalida la presentación guardada de MEMORIACARP; Actualizar
la rehace en su posición, sin modificar las fuentes BIM.

### Hoja principal en carpinterías dobles (R29-C)

`openings.normalise` añade `main_leaf` sin cambiar el esquema 3: izquierda o
derecha vistas desde el exterior. Si falta, la deduce de la bisagra y la cara
guardadas. `indice_hoja_principal` traduce esa elección al índice a lo largo del
muro; planta y alzado lo comparten para limitar la basculación a una hoja.
Las dos hojas mantienen su apertura lateral. Los anchos `leaf` y `leaf2`
siguen describiendo las hojas desde el inicio del muro, para conservar las
dimensiones y posiciones existentes; la ficha aclara ese significado.

Ficha, variantes textuales y catálogo comparten `main_leaf`. Solo separa tipos
de memoria cuando hay dos hojas; la mano continúa excluida. Un catálogo de
v1.47 sin ese campo conserva su marca en la primera agrupación compatible;
si ahora se divide en dos principales distintas, la otra recibe una marca
nueva. Una vez escrito el catálogo nuevo, las comparaciones son estrictas.
La ficha y la tabla de memoria muestran la principal y el contrato la conserva.

`openings._con_manilla` añade una única palanca cerrada a la hoja activa,
también en correderas. Las fijas y los vanos no la tienen. La altura automática
es 1,05 m desde el suelo en puertas y el centro de la hoja en ventanas; una
altura explícita fuera de la hoja se rechaza. Se admite `handle_height` y
`handle_material` en ficha y texto. Las manillas curvas reutilizan la
transformación de las piezas planas de `curved_carpentry`, sin otro generador.

La manilla es una parte `handle` del mismo IfcDoor/IfcWindow; no se crea otro
elemento BIM. La vista previa y la memoria proyectan esa misma pieza. La
igualdad de tipos usa su altura efectiva y material: automática y explícita
iguales no separan tipos. En el IGZ viaja tanto la geometría pintada como la
descripción de la pieza. La exportación IFC depende del escritor del anfitrión;
el informe de entrega distingue las comprobaciones geométricas de las
limitaciones de asociación de materiales de ese escritor.

En planta se mantiene el símbolo habitual. Se propone una marca de manilla
solo a 1:20 como opción futura; no se impone ahora. El recorrido real de R29
amplía el ayudante QTest de R27 para teclear controles numéricos y materiales
editables; no modifica la interacción del producto ni al anfitrión.

### D1: designación de elementos que atraviesan niveles

`level_layers.target_available` comprueba el tramo vertical y el estado nativo
de la categoría en la planta activa. Si todavía no existe esa capa, consulta
el estado que heredaría al crearla; comparte `_estado_capa_nueva` con
`RouteLevels`. Consultar no crea capas ni modifica el dibujo. Una categoría
ya existente conserva sus estados propios.

Los estados mixtos se resuelven igual que en la creación: solo un apagado,
una inutilización o un bloqueo comunes imponen ese estado a la categoría
nueva. Sin capas de la planta, se heredan los de la categoría base si existe.
`test_d1_designacion_niveles.py` comprueba pilares y particiones que nacen
más abajo, los límites verticales y las restricciones nativas de capa.

### D1: ancho visible al convertir una referencia de puerta

La ficha obtiene el ancho de una puerta plana de `openings.door_width`,
el mismo cálculo de hojas y cerco que usa `normalizar_carpinteria`.
`reference_changed` consulta el modo anterior a la señal: el selector ya
contiene el modo nuevo cuando se ejecuta. Para una carpintería curva o una
ventana utiliza el campo de ancho. La conversión sigue delegada en
`span_of` y `measure_of`, sin duplicar geometría.

La conversión también utiliza la cara seleccionada en la ficha de edición;
cuando no hay control de posición, conserva la cara del registro.
`test_d1_cara_carpinteria.py` cambia ambas caras sobre arcos de los dos
sentidos y verifica la medida sobre el radio de la referencia elegida.

### Cotas: constructor público de la orden nativa

`cotas.dimension_commands` usa `core.actions.AddDimensionCommand(factory)`,
el constructor público documentado de la orden de IngeCAD 0.8.0. La
fábrica entrega la cota de ezdxf con sus anulaciones antes del renderizado.
No se lee ni se sustituye `_factory` ni otro atributo interno del anfitrión.
La distancia firmada se obtiene proyectando el punto de posición sobre la
normal del segmento; no se redondean sus puntos.

La orden nativa conserva la capa, el bloque gráfico y Deshacer/Rehacer;
solo se crea un bloque de cota por ejecución y no se cambia el estilo
compartido. `test_cotas_api_publica.py` prueba la misma operación con una
orden que solo expone el contrato público, en dos orientaciones y con las
dos precisiones. No hace falta proponer ni modificar una API de IngeCAD
para este caso.

### D1: ficha propia de forjado por doble clic

`arq_properties.editar_propiedades` concentra la elección de ficha y la
misma transacción que usa PROPIEDADESARQ. El doble clic sobre un forjado
reutiliza esta función: lee el modelo completo con `slabs.read`, conserva
contorno, huecos e identidad y aplica `slab_tools.edit_change`. Cancelar
no crea una orden de dibujo. El ensayo abre la ficha real y comprueba su
edición y Deshacer/Rehacer, sin duplicar validadores ni regeneradores.

El doble clic distingue también los armarios de las otras carpinterías.
Abre `cabinets.form` con el modelo completo mediante la misma función, sin
convertirlo en una puerta ni iniciar CARPINTERIA. Las pruebas cubren cuerpo
y símbolo, modos adosado y nicho, cancelación, conservación de todos los
campos existentes y Deshacer/Rehacer. La ficha podrá incorporar «Frente en
partición» sin añadir otro recorrido de edición; esa función la integra
Claude y no se implementa en este cambio.

### D1: desfase real del pilar vinculado a ejes

Al actualizar sin un gesto previo de ejes, RegenerateGrid obtiene el
desfase del centro reconciliado mediante current_link. Una transformación
nativa del pilar ya no se pierde por leer su desfase antiguo. Al mover
los ejes se conserva el cálculo sobre su estado anterior, para que los
pilares los sigan. El índice de ejes se reutiliza en current_link, sin
recorrer el dibujo por cada pilar. Los ensayos usan las órdenes nativas
y los reactores públicos de IngeCAD 0.8.0, incluidas rejillas giradas.

Para integrar E, el criterio vigente sustituye al preliminar del núcleo:
la geometría determina el exterior, con anulación cara_exterior por muro;
los nuevos tipos de envolvente se ordenan exterior-interior y los tipos
sin campo de orden conservan su significado con aviso. Los materiales
se clasifican por catálogo, sin deducir su tipo del nombre. Véase
docs/REVISION_EXTERNA_D1_2026-11-24.md.

### R29-E: lado exterior geométrico

`geom.spaces.external_walls(..., con_lados=True)` devuelve el lado
izquierdo o derecho de las caras expuestas. Si ambas están expuestas, el
resultado es indeterminado. La llamada sin ese argumento conserva el
conjunto de identificadores. Los componentes interiores aislados no se
confunden con el contorno del edificio.

Las regiones exteriores declaradas se reciben con `exteriores`: incluyen
patios y espacios exteriores cubiertos, con sus islas. Las sondas salen
de las caras reales de los polígonos y usan la normal local del muro,
también en curvas. Un extremo expuesto no decide por sí solo el lado.
Los ensayos comprueban ambas referencias de cara y sentidos de dibujo,
particiones interiores aisladas, patios, porches y muros curvos.

### R29-E: catálogo constructivo y posición del aislamiento

`capas_envolvente.py` separa `clase_constructiva` de las propiedades térmicas
del catálogo. Las clases son aislante, fábrica/hoja, revestimiento,
trasdosado y cámara. Un material sin clasificación impide resolver el
automático. No se infieren clases por nombre, grupo o conductividad.

`aislamiento` distingue exterior, cámara e interior por las hojas a ambos
lados de la capa aislante. Los casos sin una posición única generan aviso.
`colocar` obtiene intervalos físicos de cada capa desde la cara exterior
resuelta, respetando la referencia geométrica del muro. No reinterpreta
un tipo antiguo sin orden.

El núcleo de `recubrimientos_pilar` recibe explícitamente catálogo y lados
resueltos. Solo aplica aislamiento automático interior o de cámara. El
contacto se comprueba en geometría y altura, no por igualdad de nombres de
planta. Los modos manuales conservan su definición. La conexión con las
fichas, la regeneración y las piezas exportadas usa ese mismo núcleo.

### R29-E: orden del tipo y cara exterior del muro

Los tipos nuevos de envolvente se crean con `orden_capas=exterior-interior`;
los de partición, con `cara-dibujada`. Normalizar un tipo guardado sin el
campo no lo añade. Las fichas y -TIPOSMURO permiten revisar el orden y el
CSV lo conserva en una cuarta columna; un CSV sin orden no se reinterpreta.

`cara_exterior` se guarda por muro: auto, izquierda o derecha. La ficha y
las preguntas de texto comparten la validación con creación, edición y
propuestas de cambio. La simetría intercambia las caras explícitas para
conservar la cara física; auto se vuelve a resolver por geometría. Las
referencias, las identidades y Deshacer/Rehacer siguen sus órdenes nativas.

El módulo puro capas_envolvente se copia al construir la extensión porque
la validación de muros también se usa allí. No importa ningún anfitrión.

### R29-E: colocación exportada y revisión de solo lectura

`capas_envolvente.lados_del_modelo` combina las franjas verticales del
mismo resultado geométrico que usa el contrato. Los recintos exteriores
cubiertos o descubiertos aportan sus regiones; no se deducen del nombre.
Si un muro expone caras distintas en distintas franjas, su lado único
queda indeterminado.

`exchange.wall_type_data` conserva orden y anulación, y añade a params el
lado resuelto y los intervalos físicos `capas_colocadas`. Los nombres y
espesores del conjunto material siguen sin alterarse. No coloca capas
con un lado indeterminado ni reinterpreta tipos sin orden. ARQVALIDAR
comparte las mismas reglas y deduplica el aviso del tipo sin regrabarlo.
La situación «exterior descubierto» representa el patio explícito y no
computa superficie útil; no se etiqueta un recinto por su texto libre.

Estos datos conservan la colocación de origen. El escritor IFC del
anfitrión sigue siendo experimental y no se afirma que materialice todos
los intervalos ni las relaciones de material. Los recubrimientos del pilar
ya viajan como sólidos separados; el escritor IFC vigente aún no conserva
su superficie expuesta ni la relación con el pilar. La prueba de cadena
registra esos límites sin presentarlos como una medición IFC certificada.

Leer una fórmula de capas no permite saber si pertenece a un tipo nuevo
o a uno anterior. `parse_type` conserva ese hecho; la acción de crear
un tipo añade su orden, no el analizador de texto. Así, copiar una fórmula
no reinterpreta el tipo y la exportación/importación conserva su estado.

La herramienta MURO copia los controles de colocación desde la ficha y
al retomar un modelo por doble clic mediante `datos_de_colocacion`. No
copia identidades ni resultados derivados del tramo anterior. La prueba
de ventana detecta la diferencia entre mostrar la selección en la ficha
y conservarla realmente en el nuevo registro.

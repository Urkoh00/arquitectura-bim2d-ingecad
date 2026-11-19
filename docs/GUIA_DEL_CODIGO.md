# Guía del código del plugin Arquitectura

Esta guía es para quien vaya a **leer, estudiar o mantener** el código. No sustituye al manual de uso (`docs/MANUAL.md`). Explica cómo está organizado el plugin, qué recorrido hace un elemento desde el clic hasta el IFC y dónde buscar cada cosa.

Versión de referencia: **1.35.0-dev**, con 64 módulos y unas 20 000 líneas en `arquitectura/`, más la extensión de IngeTrazo en `ingetrazo_ext/`.

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
| `geom/curves.py` | Arcos de los muros curvos. |
| `geom/drafting.py` | Las decisiones geométricas de los gestos de dibujo (dónde termina un muro, qué cara se pincha…). |

### 3.2 Elementos BIM: registro, creación y edición
| Módulo | Qué hace |
|---|---|
| `architectural.py` | Lectura y escritura de los datos BIM en XDATA (`metadata`, `_xdata`) y la comprobación de un muro con sus huecos (`validate_wall`). |
| `architectural_v10.py` | **Crear y editar** muros y carpinterías (`create_wall`, `edit_wall`, `create_opening`, `edit_opening`). Es el núcleo actual, aunque su nombre diga «v10». |
| `wall_categories.py` | Categorías de muro (fachada, tabique, medianera, sótano, defensa) y sus capas. |
| `wall_constraints.py` | Altura del muro de nivel a nivel (restricción superior). |
| `defensas.py` | Barandillas, balaustradas y antepechos: un muro con categoría «defensa». |
| `particiones_virtuales.py` | Límites de recinto sin muro, y su orden. |
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

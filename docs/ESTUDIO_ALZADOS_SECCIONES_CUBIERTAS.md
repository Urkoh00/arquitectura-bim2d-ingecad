# Alzados, secciones y cubiertas — propuesta de diseño R28-B

Revisado el 21-11-2026 según la adenda del propietario. Base del plugin: v1.46.0-dev, `78c528bb7cc6123e33a43443e945fe91d200e998`.
IngeCAD 0.8.0: `32a15cbd573b62f7c0d31aa6329d82fad55fb950`.
IngeTrazo 0.6.2.1: `8dbed761dca99dcae76efd9cd3025bfa5b8014d8`.

**Solo estudio. No se ha integrado código de cubiertas, proyección o secciones.**
La propuesta se organiza en siete bloques, equivalentes a unas siete páginas al
maquetar; el número de páginas final depende de la tipografía. Las estimaciones
son jornadas de desarrollo y validación, no compromisos de fecha.

## 1. Decisión y antecedentes comprobados

Se recomienda conservar dos responsabilidades: el plugin define la cubierta y
sus sólidos; IngeTrazo produce inicialmente las vistas con el motor que ya tiene,
y devuelve DXF a IngeCAD. No hace falta escribir primero otro eliminador de líneas
ocultas. La capacidad de obtener vistas sin abandonar IngeCAD podría añadirse
más tarde mediante un servicio de proyección compartido, después de estabilizar
los resultados de referencia.

La lectura de IngeTrazo 0.6.2.1 confirma estas piezas:

| Fuente | Capacidad existente | Consecuencia |
|---|---|---|
| `core/section.py::SectionPlane` | Plano por origen y normal, corte activo y opciones de relleno | Reutilizar plano y convención del semiespacio conservado |
| `core/hlr.py::collect_geometry` | Extrae geometría visible y transformaciones de grupos | No proyectar la geometría local ignorando sus instancias |
| `core/hlr.py::clip_to_section`, `section_loops` | Recorta triángulos/aristas y reconstruye contornos del corte | El corte no es una simple silueta de la malla |
| `core/hlr.py::hlr_drawing` | Líneas visibles, ocultas, perfiles y corte, con opción de capas | Hay un motor HLR existente que merece una prueba de aceptación |
| `views/composer.py`, `compute_annotations` | Vistas de hojas y proveedores de anotaciones de extensión | Cotas y marcas pueden suministrarse en las hojas |
| `formats/dxf_out.py::save_dxf_layers` | Exporta líneas, rellenos SOLID y textos en metros | Existe una vía de retorno 2D al CAD |

El inspector de sólidos ayuda a examinar geometría; no sustituye al compositor ni
a HLR. Un plano de sección de visualización tampoco modifica la topología del
modelo. La propuesta usa sus resultados de documentación, sin convertir un corte
de pantalla en la fuente geométrica del edificio.

En IngeCAD se ha revisado el registro de órdenes y los módulos `core/` y `tools/`:
no se ha encontrado un equivalente operativo de FLATSHOT/SECTIONPLANE en la base
0.8.0. Sí hay líneas, polilíneas, rellenos, cotas, bloques y hojas que sirven como
destino de una vista 2D. Es una conclusión de lectura del código, no una prueba de
cada función no documentada del anfitrión.

Fuentes reproducibles: [IngeTrazo 0.6.2.1, HLR](https://github.com/ingelibre/ingetrazo/blob/8dbed761dca99dcae76efd9cd3025bfa5b8014d8/core/hlr.py),
[secciones](https://github.com/ingelibre/ingetrazo/blob/8dbed761dca99dcae76efd9cd3025bfa5b8014d8/core/section.py) y
[retorno DXF](https://github.com/ingelibre/ingetrazo/blob/8dbed761dca99dcae76efd9cd3025bfa5b8014d8/formats/dxf_out.py).

## 2. Modelo de cubierta y relación con el forjado

La clase actual «Cubierta» de FORJADO es una losa horizontal. No se cambia su
geometría cuando el usuario dibuja una cubierta inclinada. Se propone una fuente
`roof`, con identidad propia, que opcionalmente referencia el forjado soporte.

Datos mínimos: `id`, `schema`, nombre, nivel base y desfase; contorno exterior y
patios; lados con identidad persistente; tipo de cada lado (alero, piñón o borde
manual), pendiente, cota de arranque y vuelo; espesor y criterio de medición
(normal al faldón o vertical, explícito); material/capas; referencia opcional a
forjado soporte; solución calculada y versión del algoritmo.

Cada faldón tiene identidad estable vinculada al lado o a una partición manual,
un plano, su contorno 3D y huecos, espesor y orientación de capas. Cumbreras,
limatesas, limahoyas y aleros se derivan de la solución, con referencias a los
faldones incidentes. No se guardan aristas inconexas como otra cubierta editable.

Para una pendiente `p` y distancia interior `d` al lado de arranque:

`z = z_arranque + p · d`.

La interfaz admite porcentaje y grados, pero el dato almacenado es la pendiente
adimensional positiva; `p = tan(ángulo)`. «Piñón» es un borde vertical sin faldón
propio, no una pendiente infinita ni un peso cero. Las normales de las caras y el
espesor se comprueban sobre los sólidos, no con la orientación visual de la vista.

La cubierta plana es un caso explícito. Una pendiente cero no se entrega a un
algoritmo que exige pesos positivos. La solución plana puede incluir pendientes
de evacuación por paños manuales, sin representar esas pequeñas pendientes como
una cubierta horizontal distinta de la que realmente se calcula.

Si existe un forjado soporte, ambos permanecen identificados. El usuario decide
si la cubierta es la propia losa inclinada o una envolvente sobre otra losa. El
exportador no debe contar dos veces el mismo volumen. Una restricción de muro o
recinto hacia cubierta apunta a la fuente y calcula su límite con la misma cara
inferior resuelta; no a una cota máxima común a todo el recinto.

## 3. Trazado: vía Python aprobada y solución manual inicial

**Decisión del propietario del 21-11:** B1 comienza por faldones manuales; B2
parte de `bpypolyskel`, con el algoritmo en Python dentro de `arquitectura/geom/`.
La propuesta anterior de un adaptador C++ queda sustituida. No se traduce CGAL,
no se enlaza con él ni se distribuye. Podrá servir como contraste local opcional;
no se ha ejecutado ese contraste ni incorporado ninguna biblioteca en R28.

`bpypolyskel` admite contornos con patios y reconstruye caras de cubiertas. En el
commit examinado **no es todavía una dependencia Python pura distribuible**:
`bpyeuclid.py` importa `mathutils`, una extensión compilada. `polygonize` admite
`holesInfo`, altura o una pendiente `tan` común; `unitVectors` son direcciones,
no pesos. No hay pendientes distintas por lado en esa interfaz. El apéndice
compara las tres alternativas con su revisión y licencia concretas.

B2 requiere estos bloques, cada uno con su prueba:

1. Fijar la revisión de procedencia; conservar autoría, licencia GPL-3.0-only,
   avisos, enlace y relación de cambios. No copiar ejemplos de edificios ajenos.
   Guardar solo el subconjunto necesario en un subpaquete de `arquitectura/geom/`,
   con su `LICENSE` y `PROCEDENCIA.md`; no modificar la licencia de código ajeno.
2. Sustituir `mathutils` por vectores y operaciones propias en Python, incluidas
   normalización, productos e intersecciones que utiliza realmente el algoritmo.
   `numpy` es una alternativa autorizada, pero los vectores pequeños propios
   evitan añadir también esa dependencia binaria. Separar este cambio del de
   pesos y contrastar primero la solución no ponderada con geometría sintética.
3. Incorporar identidad y pendiente por **lado original**, conservarlas al
   dividir/fusionar frentes y recalcular tiempos de eventos de arista y de
   partición. La posición en planta no se obtiene escalando después la altura de
   un esqueleto no ponderado: cambiar las pendientes cambia también las aristas.
4. Definir piñones como restricciones explícitas, sin faldón propio. Una
   restricción estacionaria puede intervenir en el frente; no se simula con una
   pendiente arbitrariamente grande ni se pasa un peso cero a una API que exige
   pesos positivos. Hay que tratar sus encuentros y el cierre vertical.
5. Reconstruir los paños conservando la incidencia lado/paño, patios y eventos
   simultáneos. Podar demostraciones, dependencias y ramas que no se utilicen,
   después de fijar pruebas de regresión. Validar dominios, cierre y volumen con
   las mismas tolerancias geométricas del plugin.

Con pendiente `p > 0`, distancia interior `d` y alero común, `z = z0 + p*d`.
Si el tiempo representa altura, la velocidad del frente es **`v = 1/p`**. Para
normal interior unitaria `n`, su línea satisface `n·x = c + v*t`. La intersección
de líneas móviles da la trayectoria del vértice; los tiempos de colisión y los
eventos de división se recalculan con esas velocidades. No basta con añadir un
campo de peso ni con reutilizar las bisectrices de igual velocidad.

Las cotas de arranque distintas tampoco se resuelven solo con pesos: requieren
frentes con arranques desfasados o paños manuales. Hasta implementarlo, B2 debe
rechazar de forma explícita los casos automáticos fuera de alcance. El estado
previo queda intacto y el usuario puede resolverlos mediante B1.

La interfaz propia recibe anillos orientados, lados identificados y restricciones;
devuelve paños, encuentros e incidencias, sin tipos de una biblioteca en el
contrato BIM. El éxito se mide con los ocho casos siguientes, no con una cifra
de edificios procesados que publique un autor.

Casos de aceptación del solucionador:

| Caso | Qué debe comprobarse |
|---|---|
| Rectángulo con pendientes iguales | Cumbrera central y volumen analítico |
| Rectángulo con pendientes distintas | Desplazamiento de la cumbrera y cotas de encuentro |
| L | Eventos en vértices entrantes, sin paños fuera del dominio |
| Patio | Anillo interior, drenaje y hueco sin cerrar con una cara falsa |
| Vuelo de alero | Contorno exterior desplazado sin desplazar el muro soporte |
| Lados a distinta cota | Encuentros compatibles o rechazo explícito de restricciones contradictorias |
| Piñones | Borde sin faldón, cierre vertical definido por los paños vecinos |
| Caso casi degenerado | Incidencia reproducible; nunca un sólido de espesor o área cero |

## 4. Una geometría para planta, 3D e IFC

La solución produce las caras exteriores/interiores del sólido y sus líneas de
encuentro. La planta dibuja su proyección: contornos de faldones, aleros, limas,
cumbreras, flechas de pendiente y cotas de puntos significativos. Las aristas
interiores entre triángulos de una misma cara plana no son líneas arquitectónicas.

El plugin mantiene una función de sólidos independiente del anfitrión. Recibe
los mismos parámetros y solución de paños que usa la representación en planta,
y usa `geom/solids.py` y soldadura con tolerancia para construir y comprobar
caras cerradas. No se añade un segundo generador de cubiertas en IngeTrazo.

Se propone un `IfcRoof` como conjunto y `IfcSlab` con `PredefinedType=ROOF` para
sus paños construidos. La geometría/volumen pertenece a los paños; el conjunto no
repite esas mallas como cantidades sumables. El forjado soporte, si es otra pieza
real, conserva su propio `IfcSlab`. Los huecos requieren anfitrión y sustracción
coherentes, con identificadores estables de la cubierta y del paño afectado.

El contrato actual no demuestra una relación general de agregación de cubierta.
Hace falta diseñar una relación explícita padre/hijos, validarla en la extensión
y en el escritor IFC y comprobar `IfcRelAggregates`, materiales y cantidades. No
basta con que exista el nombre IfcRoof en el catálogo de clases de IngeTrazo.
La ampliación se propondrá después de contrastar la cola vigente; **número de
paquete e identificador pendientes**, asignados por Claude. R28 no modifica ese
escritor ni prepara un PR externo.

Pruebas: igualdad del volumen de la solución y del contrato; ausencia de caras
internas duplicadas; cantidades por paño y conjunto sin doble suma; techo plano y
con patio; persistencia de identidad al cambiar una pendiente; un recinto bajo
varios faldones con volumen analítico; validación IFC y aceptación en la aplicación
de cálculo. La validación EXPRESS por sí sola no acredita esa aceptación.

## 5. Alzados y secciones: dos vías

| Criterio | Plugin en IngeCAD | IngeTrazo y retorno |
|---|---|---|
| Geometría fuente | Sólidos del contrato, directamente | Las mismas mallas cargadas por la extensión |
| HLR | Habría que adaptar un servicio o implementarlo y validarlo | Ya existe `hlr_drawing` y tratamiento del corte |
| Uso del propietario | Flujo inmediato dentro del CAD | Paso por IngeTrazo, compositor y exportación |
| Presentación | Cotas y estilos CAD disponibles | Hojas y anotaciones disponibles; DXF de retorno existente |
| Riesgo principal | Duplicar un motor y sus errores numéricos | Asociatividad e identidad entre el modelo y la vista retornada |
| Recomendación | Segunda fase si hace falta flujo directo | Primera vía de aceptación y referencia geométrica |

La cámara ortográfica se define con origen, dirección y vector vertical, además
del plano de corte opcional y el rango de profundidad. La escala se aplica a
representación/anotaciones, no a la geometría en metros. Las cotas de nivel toman
una referencia absoluta declarada y la elevación calculada, no la coordenada Y de
un texto dibujado en el alzado.

Para devolver una vista se propone DXF acompañado de un manifiesto con versión,
hash del DXF, identidad y hash del modelo fuente, cámara, corte, unidades, clases
de línea y transformaciones. IngeCAD importa la geometría en un bloque identificado
como derivado y recuerda la inserción. `Actualizar` solo reemplaza ese bloque si
el manifiesto coincide con el modelo solicitado; un archivo modificado a mano no
se acepta como actualización automática silenciosa.

Las vistas tendrán identidades independientes: dos secciones del mismo edificio
no se sobreescriben. Las notas del usuario quedan fuera de la colección derivada,
o se vinculan a una referencia geométrica explícita. Una actualización reemplaza
la vista y sus cotas dependientes en un solo Deshacer; una referencia eliminada
queda señalada, no desplazada a una arista parecida por proximidad.

## 6. Convenciones de representación

Propuesta inicial: cortado 0,50 mm; silueta 0,35; visto próximo 0,25; lejano 0,13;
oculto 0,13 discontinuo; cotas/anotación 0,18. Son opciones del estilo, no normas
universales. Las clases de línea se almacenan por separado para que la tabla de
plumas del dibujo pueda cambiar los valores sin recalcular la geometría.

El relleno de corte conserva los patios y huecos. Una cara coplanaria con el
plano se trata mediante una convención determinista documentada, con casos de
prueba a ambos lados de la tolerancia. Debe distinguirse arista real, silueta,
arista de triangulación y borde del corte. Transparentar una hoja de vidrio en
pantalla no resuelve por sí solo su regla de ocultación en documentación.

Las carpinterías reutilizarán las plantillas desarrolladas de R28-A; posición y
ocultación vienen de la proyección de su sólido. Las fichas de memoria no se pegan
como símbolos flotantes delante de un alzado si sus jambas están ocultas por otro
elemento. Para vistas curvas o vistas oblicuas debe definirse si se representa
el desarrollo o la proyección; ambas se rotulan de forma distinta.

## 7. Encargos propuestos y cierre de diseño

| Fase | Entregable | Estimación | Criterio de salida |
|---|---|---:|---|
| B0 | Modelo de datos y 8 casos analíticos de cubierta | 2–3 jornadas | Contrato y alcance aprobados |
| B1 | Faldones manuales, planta y sólido único | 5–8 | Volumen y encuentros, recintos, DXF/DWG, Undo/Redo |
| B2 | Derivación Python de bpypolyskel: vectores, pesos, piñones y reconstrucción | 15–25 jornadas | Los 8 casos analíticos; sin dependencia C++/mathutils; Windows/Linux |
| B3 | Relación Roof/Slab en contrato y propuesta IFC | 3–5 | Jerarquía y cantidades sin duplicados; aceptación externa |
| B4 | Prueba de alzado/sección en compositor y retorno DXF | 3–5 | Dos cámaras, corte con huecos, acentos y escala |
| B5 | Actualizar asociativo, estilos y cotas de nivel | 4–6 | Cambios, eliminación de fuentes, Undo/Redo exactos |

Primero B0/B1 y la prueba pequeña de B4: despejan la geometría y la reutilización.
B2 no bloquea un trazado manual correcto. El principal riesgo no es dibujar una
línea de cumbrera: es conservar consistencia entre encuentros, sólidos, recintos,
capas, jerarquía IFC y documentación tras una edición.

Se ha leído el manual 2015 recibido como PDF (19 páginas), incluidos los capítulos 6, 7 y 10 sobre componentes y asociación 2D/3D. Es una referencia funcional; no contiene un diseño de cubiertas o de HLR que se deba trasplantar al plugin. Por ello se mantiene el principio de sólidos compartidos y se reutilizan las capacidades examinadas de IngeTrazo. El vídeo no se ha recibido por separado ni se ha examinado. El manual y su extracción no se distribuyen. No se ha instalado ni usado ninguna biblioteca de SketchUp.


## Apéndice A. Comparación de esqueletos rectos Python (21-11-2026)

Consulta de fuentes primarias, fijadas por commit. Es una lectura de código y
licencias, **no un ensayo de las bibliotecas ni una integración**. «No» en pesos
significa que no se ha encontrado un parámetro de velocidad/peso por lado en las
interfaces inspeccionadas; una pendiente global no satisface ese requisito.

| Candidata y revisión | Licencia comprobada | Patios / pesos por lado | Dependencias y mantenimiento observado | Esfuerzo previsto para pesos |
|---|---|---|---|---|
| `prochitecture/bpypolyskel`, `bd1ce5b2e9dc2028595e6a3e116926e1c58e45dd` | GPL-3.0-only, declarado literalmente en `pyproject.toml`; `LICENSE` GPLv3 | Sí, `polygonize(..., holesInfo=...)`; **no**: `tan` y `height` globales | Núcleo Python; `bpyeuclid.py` importa `mathutils`; grafo de caras usa biblioteca estándar. HEAD consultado 13-03-2026, repositorio no archivado; contiene pruebas con patios y polígonos cóncavos | Alto: líneas móviles, trayectorias, tiempos de colapso/división, eventos simultáneos y caras ponderadas. Aproximadamente 8–15 jornadas solo para pesos y sus pruebas; además vectores, piñones y aceptación completa |
| `Botffy/polyskel`, `c4f855e29f848a0dd627e0b2d5280187c982e887` | **LGPL-3.0**, según `LICENSE` (LGPLv3, no MIT); no se ha encontrado una concesión adicional «or later» que permita afirmarla | Sí, `skeletonize(polygon, holes=None)`; **no** | Núcleo depende de `euclid3`; Pillow se usa para demostración. HEAD consultado 12-10-2020, no archivado; el README reconoce casos incorrectos del algoritmo/implementación | Alto/muy alto: mismo problema cinético y reconstrucción de paños adicional; 12–20 jornadas para pesos, sin contar corregir degeneraciones heredadas |
| `ladybug-tools/ladybug-geometry-polyskel`, `c2666796a0e04c3c62f736994a996581901c25ff` | **AGPL-3.0**, `LICENSE` AGPLv3 y `setup.py`; no se presupone una concesión «or later» | Sí, `skeleton_as_subtree_list` / `skeleton_as_edge_list`, ambas con `holes`; **no** | Depende de `ladybug-geometry==1.35.10` en la revisión leída; contiene métodos de polígonos y pruebas. HEAD 12-11-2026 (actualiza dependencia), no archivado: actividad reciente no equivale a corrección demostrada | Alto: 10–18 jornadas para pesos y sus pruebas, con adaptación a sus tipos geométricos; añadir extracción de paños de cubierta y piñones |

Los intervalos son estimaciones de ingeniería sujetas a B0, no resultados de un
prototipo. El número de líneas (aproximadamente 1178 en el núcleo bpypolyskel,
517 en el original y 860 en el de Ladybug) no mide robustez ni esfuerzo. En la
opción elegida B2 completo se estima en 15–25 jornadas; si B0 detecta ambigüedades
numéricas, se desglosa otro encargo. B1 continúa siendo útil por sí mismo.

**Licencias y distribución.** La combinación de código propio GPL-3.0-or-later
con GPL-3.0-only se distribuye bajo términos compatibles de GPLv3, conservando los
avisos concretos de cada fuente; no se cambia a «or later» el subpaquete ajeno.
Hay que incluir texto de licencia, autoría, código fuente correspondiente y
cambios/fechas de la derivación. LGPLv3 permite utilizar el original con sus
obligaciones de biblioteca y de sus modificaciones; no debe rotularse como MIT.

AGPLv3 puede combinarse con GPLv3 conforme a sus secciones 13; hay que conservar
las obligaciones aplicables a cada parte y facilitar el código fuente
correspondiente. Si una versión modificada ofrece interacción remota por red,
AGPLv3 §13 exige que esos usuarios puedan obtener su fuente. Usar el plugin solo
localmente no convierte automáticamente su salida DXF/IFC en AGPL ni impone un
servicio en red, pero una futura versión remota sí requeriría revisar ese punto.
La actividad reciente de Ladybug no justifica introducir esa dependencia extra
frente a la vía elegida. No se ha incorporado código de ninguna candidata y la
licencia del plugin permanece GPL-3.0-or-later.

**Fuentes fijadas:**

- [bpypolyskel: licencia y paquete](https://github.com/prochitecture/bpypolyskel/blob/bd1ce5b2e9dc2028595e6a3e116926e1c58e45dd/pyproject.toml),
  [algoritmo y `polygonize`](https://github.com/prochitecture/bpypolyskel/blob/bd1ce5b2e9dc2028595e6a3e116926e1c58e45dd/bpypolyskel/bpypolyskel.py),
  [dependencia mathutils](https://github.com/prochitecture/bpypolyskel/blob/bd1ce5b2e9dc2028595e6a3e116926e1c58e45dd/bpypolyskel/bpyeuclid.py),
  [grafo de caras](https://github.com/prochitecture/bpypolyskel/blob/bd1ce5b2e9dc2028595e6a3e116926e1c58e45dd/bpypolyskel/poly2FacesGraph.py).
- [polyskel: LGPLv3](https://github.com/Botffy/polyskel/blob/c4f855e29f848a0dd627e0b2d5280187c982e887/LICENSE),
  [algoritmo](https://github.com/Botffy/polyskel/blob/c4f855e29f848a0dd627e0b2d5280187c982e887/polyskel.py),
  [limitaciones declaradas](https://github.com/Botffy/polyskel/blob/c4f855e29f848a0dd627e0b2d5280187c982e887/README.md).
- [Ladybug: AGPLv3](https://github.com/ladybug-tools/ladybug-geometry-polyskel/blob/c2666796a0e04c3c62f736994a996581901c25ff/LICENSE),
  [declaración de licencia](https://github.com/ladybug-tools/ladybug-geometry-polyskel/blob/c2666796a0e04c3c62f736994a996581901c25ff/setup.py),
  [algoritmo](https://github.com/ladybug-tools/ladybug-geometry-polyskel/blob/c2666796a0e04c3c62f736994a996581901c25ff/ladybug_geometry_polyskel/polyskel.py),
  [dependencia](https://github.com/ladybug-tools/ladybug-geometry-polyskel/blob/c2666796a0e04c3c62f736994a996581901c25ff/requirements.txt).
- [GPLv3 §13](https://www.gnu.org/licenses/gpl-3.0.html#section13) y
  [AGPLv3 §13](https://www.gnu.org/licenses/agpl-3.0.html#section13).

### Aceptación obligatoria antes de integrar B2

Los ocho casos del apartado 3 son requisito de salida, aunque el cambio inicial
solo sustituya vectores. B0 fijará coordenadas, tolerancias y resultados exactos:

1. Rectángulo 8 × 6 m, cuatro pendientes 0,5 y aleros a z=0: cumbrera a 1,5 m,
   longitud 2 m, volumen bajo faldones **27 m³**; comprobar por integración de las
   secciones horizontales `(8-4z)*(6-4z)`, para `0≤z≤1,5`.
2. Rectángulo de 6 m entre aleros de pendientes 0,5 y 1, con piñones a 8 m de
   separación: encuentro a 4 m del primer alero, z=2 m y volumen **48 m³**.
   Detecta confundir velocidad con pendiente.
3. L: usar una descomposición independiente en paños con planos explícitos;
   comprobar punto del evento entrante, unión de dominios, sin solape y volumen
   por integración de esos paños, no contra otra salida del mismo algoritmo.
4. Patio: anillo interior abierto hasta arriba, dominio de paños igual a exterior
   menos patio; sin tapas falsas y volumen por secciones analíticas por tramos.
5. Vuelo: desplazar el alero la distancia normal indicada; soporte e ID del muro
   permanecen; contrastar dimensión exterior y aumento de volumen calculado.
6. Arranques distintos: planos conocidos compatibles con aristas a igual z, o
   rechazo explícito del automático con estado previo intacto. No simularlos
   desplazando vértices de una solución incompatible.
7. Piñones: ausencia de faldón de borde, cierre vertical sin espesor cero y
   unión de los dos paños vecinos; contrastar área triangular y volumen.
8. Casi degenerado: variar una coordenada a ambos lados de la tolerancia;
   incidencias deterministas y sin caras nulas; resultado válido o rechazo
   informado, sin corrupción del modelo ni cambios parciales al deshacer.

R28 entrega esta especificación. No afirma que los ocho ensayos del solucionador
estén ejecutados: B1/B2 siguen siendo encargos posteriores de diseño aprobado.

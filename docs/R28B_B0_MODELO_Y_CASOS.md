# R28-B0: modelo de cubierta y ocho referencias analíticas

21-11-2026. Propuesta para revisión de Claude, sobre v1.46.0-dev,
`3a7537a8f8086cbc0ca6c7b020546123f5d3abe9` de `main`.

El encargo de continuidad es el estudio R28-B revisado el 21-11. Esta entrega
prepara **B0**, la primera fila de su tabla de fases. No implementa B1, B2 ni
las vistas de B4/B5. La revisión del modelo y su alcance precede a B1. El plugin
conserva sus órdenes y su contrato de exportación actuales.

## 1. Contraste con el código vigente

La diferencia de esta base respecto de `78c528b`, citada en el estudio, es el
script sintético `scripts/generar_modelo_espacios.py`. No ha cambiado la geometría
del plugin. `main` todavía no incorpora los parciales de R28-A: no se reaplican
sus parches ni se presenta MEMORIACARP como terminada.

- `slabs.py` representa «Cubierta plana» como una losa horizontal.
- No hay fuente `roof`, orden de faldones, esqueleto ponderado ni solución de
  encuentro cubierta/recinto implementados.
- `space_envelope.py` deja las cubiertas y falsos techos independientes para el
  desarrollo posterior; no puede recibir ahora una cota máxima en sustitución
  de la superficie inferior real de una cubierta.
- La geometría compartida se empaqueta mediante `bundle_roundtrip.py`.
  Esta propuesta no añade un generador en IngeTrazo ni modifica su escritor IFC.
- IngeCAD 0.8.0 e IngeTrazo 0.6.2.1 siguen siendo las últimas publicaciones
  consultadas. No se ensayan versiones anteriores ni se preparan migraciones.

## 2. Fuente propuesta: `arq.cubierta/v1`

El esquema verificable está en `docs/esquemas/cubierta-v1.schema.json`.
**Es un esquema de fuente propuesto, distinto del contrato `.arqbim` actual.**
Añadirlo al dibujo, exportarlo o admitirlo en la extensión requiere B1/B3; la
existencia de este JSON no concede esas capacidades al plugin.

| Dato | Significado y unidad |
|---|---|
| `schema`, `kind`, `id`, `name` | Versión exacta, `roof`, identidad persistente y nombre |
| `level_id`, `base_offset` | Nivel identificado y desfase vertical, en metros |
| `origin_xy` | Traslación al sistema del dibujo; los contornos usan XY locales en metros |
| `mode` | `manual`, `automatic` o `flat`, sin convertir un modo en otro al leer |
| `outer`, `holes` | Anillo exterior antihorario y patios horarios; cada anillo y vértice tiene ID |
| `edges` | Un registro por tramo consecutivo, referido a IDs de anillo/vértices |
| `thickness` | Valor positivo y criterio `vertical` o `normal`, explícitos |
| `material`, `layers` | Material y estratos de exterior a interior; si hay estratos, suman el espesor |
| `support_slab_id` | Referencia opcional al forjado soporte, sin copiarlo ni sumar su volumen |
| `solution` | `null` mientras no esté resuelta; después, resultado derivado con versión y huella de entrada |

Un lado guarda `id`, `ring_id`, `start_vertex_id`, `end_vertex_id`, `role`,
`slope`, `start_offset` y `overhang`. Su papel es `eave` (alero con faldón),
`gable` (piñón sin faldón) o `manual`. `slope` es la pendiente adimensional;
`start_offset` es la cota relativa del alero y `overhang` su vuelo en metros.
Los piñones y bordes manuales llevan pendiente `null`, no infinita ni cero.
En modo plano el alero admite pendiente cero; el modo inclinado la exige positiva.

El contorno fuente es la línea de referencia del apoyo, anterior al vuelo. La
solución contiene el contorno exterior y los patios resultantes del vuelo. Para
un anillo orientado con material a su izquierda, la normal `n` apunta al dominio;
el alero se desplaza `-n * overhang`. Un vuelo excesivo que cierre un patio o
produzca un cruce se rechaza, sin sustituirlo por otro contorno silenciosamente.
En B0 se comprueban desplazamientos por intersección de rectas; no hay propagación
cinética ni resolución de un esqueleto. No se admite corregir un contorno inválido
con `buffer(0)` ni con redondeo de coordenadas.

Los IDs no se deducen de índices, coordenadas ni posiciones en una lista. Los
alias legibles de los ejemplos se asignan una vez. B1 generará UUID al crear;
conservará los de lados, vértices y paños que sobrevivan a una edición. Un lado
eliminado no se sustituye por otro por proximidad. Los paños pueden referir varios
lados colineales: así no hace falta borrar IDs para simplificar un contorno.

## 3. Resultado manual de referencia

`solution` contiene:

- `algorithm.name` y `algorithm.version`: procedencia del cálculo. En los ejemplos
  son `referencia-manual` y `1`; no se ha ejecutado una biblioteca automática.
- `input_fingerprint`: SHA-256 del JSON canónico de toda la fuente, excluyendo
  `solution`. Orden de claves estable, UTF-8 y números finitos, sin `round()`.
- `outer` y `holes`: dominio resuelto tras vuelos.
- `facets`: paños con ID, `source_edge_ids`, contorno, patios y un plano afín.

Cada plano guarda `point = [x0, y0, z0]` y `gradient = [gx, gy]`:

`z_local(x,y) = z0 + gx*(x-x0) + gy*(y-y0)`.

En el dibujo, `XY = origin_xy + XY_local` y
`Z = elevación(level_id) + base_offset + z_local`.
No se resta una gran coordenada topográfica en cada producto cruzado ni se guarda
la cota absoluta del nivel en todos los vértices derivados.

Para un alero de pendiente `p`, normal interior `n` y punto fuente `a`:

`z_local(x) = start_offset + p * (n·(x-a) + overhang)`.

Los planos incidentes deben dar la misma cota en toda arista común. La partición
cubre exactamente el dominio, sin paños fuera, solapes ni tapas sobre los patios.
Cada alero tiene paño asociado y ningún piñón lo genera. Las referencias de
cumbreras, limas y encuentros se derivarán de esa incidencia en B1, conservando
IDs de fuente; no se mantendrá una segunda red editable de aristas inconexas.

**Lectura y caché.** Una entrada distinta invalida la solución; el comprobador no
la recalcula ni modifica el objeto. Un esquema desconocido o ausente se rechaza.
El comprobador B0 verifica la geometría suministrada, no la disponibilidad de un
algoritmo por su nombre. B1 deberá aceptar para reutilización solo las versiones
de algoritmo que implemente. No se prepara compatibilidad con esquemas antiguos.

## 4. Qué miden los ejemplos

Se distinguen cuatro cantidades:

1. Área del soporte, antes del vuelo.
2. Área de cubierta proyectada en planta, descontando patios.
3. Área real de los paños: `A_planta * sqrt(1 + gx² + gy²)` para cada plano.
4. Integral de altura sobre la cota cero **local**, `∫ z_local dA`.

La cuarta es el volumen analítico bajo los planos superiores respecto de esa
referencia; **no es el volumen de material de cubierta ni el NetVolume de un
recinto**. Para un recinto real habrá que recortar su dominio y usar la superficie
inferior, restando su suelo y resolviendo todos los límites superiores en B1.

Los ejemplos usan espesor **vertical** de 0,20 m. En esa construcción la envolvente
material por dominio vertical tiene volumen `A_planta * 0,20`; no se le suma el
del forjado soporte. El espesor normal se admite como dato, pero B0 no cuantifica
su sólido ni sus encuentros. B1 debe desplazar los planos la distancia normal y
recortar sus encuentros; no puede sustituirlo por un espesor vertical de 0,20 m.
No se dan por comprobadas mallas cerradas, IFC ni cantidades normales en B0.

## 5. Ocho referencias y derivación independiente

Los JSON de `tests/datos/cubiertas_b0/` son modelos sintéticos independientes.
Los paños son explícitos; el generador de datos no calcula un esqueleto. Las
pruebas contrastan sus integrales de plano con las fórmulas siguientes, que no
dependen de cómo triangule el futuro solucionador.

| Caso | Dominio y restricciones | Resultado que debe preservar B1/B2 |
|---|---|---|
| 01. Rectángulo igual | 8 × 6 m, cuatro pendientes 0,5, aleros a 0 | Cumbrera `(3,3,1.5)`–`(5,3,1.5)`; área 48 m²; volumen bajo planos 27 m³ |
| 02. Pendientes distintas | 6 × 8 m, izquierda 0,5, derecha 1 y extremos piñones | Cumbrera x=4, z=2; área 48 m²; volumen 48 m³ |
| 03. L | `(0,0),(6,0),(6,2),(2,2),(2,6),(0,6)`, pendiente 0,5 | Encuentro entrante `(1,1,0.5)`; área 20 m²; volumen 14/3 m³ |
| 04. Patio | Exterior 10 × 10 m, patio de 4 × 4 entre coordenadas 3 y 7; pendiente 0,5 en ambos anillos | Dominio 84 m², patio 16 m² abierto; encuentro a z=0,75; volumen 31,5 m³ |
| 05. Vuelo | Apoyo 8 × 6, vuelo 0,5 m, pendiente 0,5 | Cubierta 9 × 7 m, soporte intacto; cumbrera a 1,75; volumen 245/6 m³ |
| 06. Arranques distintos | 6 × 8 m, pendientes 0,5; alero izquierdo a 0 y derecho a 1 | Manual: x=4, z=2, volumen 56 m³. Automático: rechazo explícito hasta resolver arranques desfasados |
| 07. Piñones | 6 × 8 m, dos pendientes 0,5 y dos extremos piñones | Dos paños, ninguno de piñón; z=1,5; volumen 36 m³; cierres triangulares de referencia 4,5 m² cada uno |
| 08. Casi degenerado | Rectángulo del caso 01 con un tramo adicional colineal | Longitud T/2: rechazo. Longitud 2T: conserva dominio y volumen 27 m³, con ambos IDs de lado |

Con `T = geom/soldadura.TOLERANCIA = 1e-7 m`. Se compara por distancia, sin
claves redondeadas. Para errores de dominio en área se usa `T * perímetro`, con
un mínimo de referencia de 1 m; no se compara un área directamente con metros.
Los lados de longitud menor o igual a T se rechazan. El determinante normalizado
de dos direcciones usa un umbral numérico de paralelismo adimensional separado;
la comprobación final de distancia y geometría conserva T en metros.

Derivaciones por secciones horizontales:

- Caso 01: `A(z)=(8-4z)(6-4z)`, entre 0 y 3/2. Su integral es 27.
- Caso 02: con tiempo igual a altura, `v_izq=2` y `v_der=1`;
  `2t=6-t`, por tanto t=2, x=4. Se integra el triángulo 6×2 a lo largo de 8 m.
  Utilizar `v=p` daría una cumbrera incorrecta en x=2.
- Caso 03: `A(z)=20-48z+16z²`, entre 0 y 1/2. Su integral es 14/3.
- Caso 04: `A(z)=(10-4z)²-(4+4z)²=84-112z`, entre 0 y 3/4. Integral 63/2.
- Caso 05: `A(z)=(9-4z)(7-4z)`, entre 0 y 7/4. Integral 245/6;
  el aumento respecto del caso 01 es 83/6, sin cambiar el área de apoyo.
- Caso 06: `z=0,5x` hasta x=4 y `z=4-0,5x` de 4 a 6; integrar y multiplicar
  por 8 da `8*(4+3)=56`.
- Caso 07: sección triangular 6×1,5/2, longitud 8: volumen 36.
- Caso 08: el tramo añadido no cambia el dominio ni el plano; comprueba la
  frontera de rechazo geométrico, no una corrección silenciosa de la entrada.

Las áreas triangulares de piñón son referencias de cierre del espacio bajo los
paños, no cantidades de otro faldón. B1 decidirá cómo se ajusta el cerramiento
vertical real y cerrará el espesor del sólido; no debe sumarlas como losa de techo.

## 6. Ejecución y dependencias de desarrollo

```sh
python -m pip install -r requirements-dev.txt
python scripts/validar_cubierta_b0.py tests/datos/cubiertas_b0/*.json
INGECAD_SRC=/ruta/ingecad QT_QPA_PLATFORM=offscreen python -m pytest -q
```

`jsonschema` valida el documento de diseño y Shapely actúa como oráculo geométrico
independiente en esta herramienta de desarrollo. **No se añaden al plugin ni a
su paquete instalable.** No hay dependencia de CGAL, mathutils ni de un adaptador
C++. No se ha incorporado código de las candidatas del estudio B2.

`generar_casos_cubiertas_b0.py` reproduce los ocho JSON de forma determinista;
las pruebas comparan los archivos con esa reproducción y verifican también las
fórmulas independientes, no solo la salida del generador. El comprobador devuelve
mediciones o rechaza con motivo en español, sin escribir ni alterar la entrada.
No importa IngeCAD, IngeTrazo ni Qt, lo que se comprueba en un proceso aislado.

## 7. Alcance concreto de B1 después de esta revisión

La siguiente entrega partirá del commit resultante de integrar la propuesta
revisada. Debe implementar la fuente en XDATA mediante las funciones existentes,
crear/editar paños manuales y obtener una única solución para planta, 3D y límites
inferiores. Cada acción será una transacción con sus dependientes y un Deshacer.

B1 verificará: IDs y referencias al editar, Deshacer/Rehacer, eliminar un apoyo o
nivel referenciado, recintos bajo varios paños con volumen analítico, espesor y
encuentros de sólidos cerrados, DXF/DWG y ficha/variante textual sin diálogos.
El esquema propuesto no suplanta esas pruebas de aplicación.

Actualización de continuidad, adenda 2 del propietario (21-11): B2 partirá del
esqueleto de «Tejados y tejas» y de ArchXQ, conservando procedencia/licencias.
Esta decisión sustituye a bpypolyskel; B2 no entra en R28. B3 resolverá las relaciones
IfcRoof/IfcSlab con sus cantidades sin duplicación; no se cambia ahora el escritor
de IngeTrazo. B4/B5 continuarán las vistas y su actualización. La memoria de
carpinterías pendiente en R28-A se mantiene como trabajo distinto.

# Diseño: espacios (recintos) BIM para cálculo energético

Estado (6-11-2026): **implementados los recintos básicos** en v1.7.0-dev (orden `RECINTO`: contorno, islas, superficie, perímetro, volumen, asociatividad por punto semilla, `IsExternal` de los muros). Pendientes: separaciones virtuales, límites de espacio de 1.º y 2.º nivel, suelos y techos, y las decisiones del final de este documento.

## Por qué importan

Para un cálculo térmico o energético, el modelo debe responder, sin ambigüedad, a tres preguntas:
qué recintos hay, qué superficie y volumen tiene cada uno, y qué separa a cada recinto del
exterior, del terreno o del recinto vecino, con qué superficie y por qué elemento. Un programa
de cálculo que lee el IFC obtiene eso de `IfcSpace` y de sus **límites de espacio**
(`IfcRelSpaceBoundary`). Si los límites tienen huecos o solapes, o si una cara de muro no se sabe
a qué recinto da, el cálculo falla o, peor, da un resultado erróneo sin avisar.

## Por qué el plugin está bien situado

El motor de encuentros (`geom/junctions.py`) ya obtiene la **huella exacta y sin solapes** de cada
muro y pilar, y cada cara conserva el muro al que pertenece. Los recintos son exactamente las
regiones cerradas que quedan entre esas huellas. Su contorno es, cara a cara, el de los muros
que los rodean, sin tolerancias ni reconstrucción posterior. Es el mismo principio que aplicamos
a muros y pilares: **planta, 3D e IFC salen de una sola definición**.

## Modelo de datos

**Recinto** (`kind: "space"`, clase `IfcSpace`):

- Una polilínea cerrada en la capa `ARQ-RECINTOS`, que es su representación visible, con un
  **punto semilla** en XDATA: el punto interior que marcó el usuario.
- Identidad persistente (`id` y GUID IFC estable, como los muros), nombre (`Dormitorio 1`),
  número o código (`Reference`) y uso (habitable / no habitable; acondicionado / no
  acondicionado).
- Planta (`level`), cota del suelo y altura libre: hasta la cara inferior del forjado superior,
  o hasta el falso techo si se indica.

**Asociatividad:** el contorno no se guarda como verdad, sino que se **recalcula desde la semilla**
en cada `UNIONESARQ`. Si un muro se desplaza, el recinto lo sigue. Si la semilla queda dentro de un
muro o la región deja de estar cerrada, el recinto se marca como incidencia; nunca se rellena
en silencio.

**Separación virtual:** para dividir un espacio abierto (salón-comedor-cocina) sin muro, una línea
de separación (`kind: "space_separator"`, `IfcVirtualElement`) actúa como límite.

## Cálculo

1. **Regiones:** unión de las huellas de muros y pilares de la planta. Las regiones interiores del
   complemento son los recintos candidatos, y la región no acotada es el exterior.
2. **Recinto = región que contiene la semilla.** Se calcula con el mismo núcleo de polígonos
   (`geom/polygon.py`), sin dependencias nuevas.
3. **Las puertas no abren el recinto:** el hueco de una puerta es un límite físico (la propia
   puerta), no una fuga. Por eso las regiones se calculan sobre la huella completa del muro,
   antes de restar huecos.
4. **Fugas:** si la semilla cae en la región exterior, se avisa: «el recinto no está cerrado; falta
   un muro o una separación», señalando la abertura más probable.

## Límites de espacio (`IfcRelSpaceBoundary`)

- **Primer nivel:** cada tramo de cara de muro o pilar que toca el recinto, con el elemento que lo
  forma. El motor ya conoce, para cada tramo de contorno, su muro.
- **Segundo nivel** (el que usan los programas de cálculo energético): cada tramo de primer nivel
  se divide según lo que hay **al otro lado** del muro (otro recinto, exterior o terreno). Se
  emparejan las dos caras de un mismo muro entre recintos vecinos (`CorrespondingBoundary`), y las
  ventanas y puertas se incluyen como límites propios dentro del límite del muro que las aloja.
  En planta esto es directo: cada pieza de muro tiene dos caras, y cada cara da a una única
  región.
- **Suelo y techo:** se añaden en la Fase 4, cuando existan forjados, con la misma regla.

**Consecuencia útil:** un muro cuya cara da al exterior queda identificado automáticamente como
**exterior** (`Pset_WallCommon.IsExternal = true`). Esa propiedad decide la envolvente térmica y
hoy la introduce el usuario a mano.

## Propiedades y cantidades

- `Pset_SpaceCommon`: Reference, IsExternal = false, PubliclyAccessible, HandicapAccessible.
- Uso y acondicionamiento en un Pset propio (`ARQ_Recinto`) hasta fijar la correspondencia con la
  normativa aplicable.
- `Qto_SpaceBaseQuantities`: Height, FinishCeilingHeight, GrossFloorArea, NetFloorArea,
  GrossPerimeter, NetPerimeter, GrossVolume, NetVolume.

## Exportación

El contrato `.arqbim` añade elementos `IfcSpace` (huella, alturas, límites con referencia al muro,
la cara y el recinto contiguo). El IFC debe **agregar** cada `IfcSpace` a su planta
(`IfcRelAggregates`), no contenerlo. Hoy el exportador de IngeTrazo lo contiene, y IfcOpenShell lo
rechaza con 2 errores de reglas IFC4 (comprobado el 6-11-2026; véase `propuestas_upstream/`). Los
límites de espacio tampoco existen aún en IngeTrazo. Ambas cosas se propondrán a su desarrollador
cuando responda a las propuestas en curso.

## Pruebas previstas

- Suma de recintos + huellas de muros y pilares = superficie bruta de la planta, sin solapes ni
  huecos (con shapely como oráculo independiente, igual que los encuentros).
- Cada tramo de cara de muro pertenece a un único recinto o al exterior, por cada lado.
- Pares de límites de segundo nivel: misma superficie y normales opuestas.
- Recintos asociativos: mover un muro cambia el área del recinto y deshacer la restaura.
- Fuga: un muro que no cierra produce una incidencia, no un recinto erróneo.
- IFC validado con IfcOpenShell, incluidas las reglas.

## Decisiones pendientes del usuario

1. **Criterio de superficie útil:** qué se descuenta (pilares exentos o adosados, conductos,
   zonas de altura reducida) según la normativa que deba cumplirse.
2. **Altura del recinto:** hasta el forjado (volumen bruto) o hasta el falso techo (volumen neto),
   o ambas.
3. **Clasificación de uso** que necesita el programa de cálculo con que se trabaje.

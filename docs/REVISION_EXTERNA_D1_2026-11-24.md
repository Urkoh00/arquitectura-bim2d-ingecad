# Revisión externa D1 — 24-11-2026

## Base comprobada

Propuesta sobre v1.48.14-dev, `434cc00bf4db12342e8759faa7daa14f4c4437de`,
comunicado como último main de `Urkoh00/Arquitectura-bim2d-dev`.

Las sumas de los dos ZIP aportados coinciden con SHA256SUMS. Se han
reconstruido los veinte parches hasta 1f80eaf y los dos siguientes
hasta 434cc00; se han comparado los 369 archivos
seguidos con el ZIP de fuentes: no hay diferencias ni archivos sobrantes.
El árbol de esa base es `d3aecb3b51852b8b3ee914b819bdfad83e192856`.
La reconstrucción tiene identificadores locales distintos por los metadatos
de aplicación de los parches; no se presentan como commits del main remoto.

El parcial 02 ya está incluido en esta base: no se vuelve a aplicar.
Los fallos reproducidos primero en la copia disponible se han vuelto a
comprobar en esta base antes de preparar la nueva entrega.

## 1. Categoría ausente en la planta activa

Un pilar o una partición que nace a 0 m y llega a 6 m ocupa la planta
activa a 3 m aunque aún no exista allí su capa de categoría. Exigirla
impedía designarlo hasta crear otro elemento de esa categoría en la planta.

La propuesta consulta los estados que heredaría la capa nativa al crearla,
sin crearla. Comparte esa resolución con RouteLevels y conserva los estados
propios de las categorías existentes. El intervalo vertical semiabierto
excluye los elementos que terminan justo en la cota activa. No añade un
almacén paralelo de estados. Los estados mixtos siguen el criterio de
creación existente; una categoría ya creada usa sus estados propios.

## 2. Referencias de carpintería

Se corrigen dos defectos en commits independientes:

- La puerta plana toma el ancho de hojas y cerco mediante door_width,
  compartido con normalizar_carpinteria. Una cuerda de 1,61 m en el muro
  sintético se convierte en 1,611612… m de arco; el campo oculto inicial
  de 0,90 m ya no interviene. Se utiliza el modo anterior a la señal,
  porque el selector contiene ya el nuevo cuando se ejecuta la conversión.
- La conversión lee la cara seleccionada en edición. Cuatro ensayos
  combinan ambas caras iniciales y ambos sentidos del arco, verificando
  la razón analítica de radios interior/exterior.

Los límites de comparación de los controles Qt contemplan sus cuatro
decimales; no se redondea la geometría para decidir igualdades. La
conversión sigue utilizando span_of y measure_of.

## 3. Doble clic de forjados y armarios

Se reutiliza la edición de PROPIEDADESARQ mediante editar_propiedades:
una sola elección de ficha, validación y transacción. El forjado abre
slab_tools.form con slabs.read; el armario abre cabinets.form con todos
sus datos. No se inicia CARPINTERIA para un armario.

Los ensayos de forjado verifican contorno, huecos, identidad, edición,
cancelación y Deshacer/Rehacer. Los de armario abarcan designación del
cuerpo y del símbolo, modos adosado y nicho, edición y cancelación.
La identidad, referencias, dimensiones y datos específicos se conservan.
La edición común explicita material principal vacío si no estaba escrito,
sin cambiar los materiales por pieza. Cada corrección tiene su commit.

No se desarrolla el nuevo armario «Frente en partición»: lo integra Claude.
La selección de ficha seguirá usando la función común al ampliarla.

## 4. Cotas sin sustituir atributos internos de IngeCAD

Se usa el constructor público documentado AddDimensionCommand(factory),
con una fábrica que entrega la cota de ezdxf y sus anulaciones antes del
renderizado. No se lee ni se sustituye c._factory. La distancia firmada
se calcula con la normal al segmento, sin redondear puntos.

El comando nativo conserva capa, bloque gráfico y Deshacer/Rehacer.
Las pruebas ejecutan cotas ortogonales y oblicuas con ambas precisiones
a través de una orden que solo expone su contrato público; comprueban
medida, precisión, un bloque por ejecución, limpieza al deshacer y que
el estilo compartido no cambia. No se modifica el anfitrión ni hace falta
proponer una API nueva para resolver este caso.

## 5. Pilar vinculado movido con órdenes nativas

ACTUALIZAEJES reutilizaba el desfase guardado aunque la geometría del pilar
ya hubiera cambiado por DESPLAZA, GIRA, ESCALA o SIMETRIA. La actualización
volvía a colocar el pilar en el cruce antiguo.

Sin un gesto de ejes anterior, RegenerateGrid usa current_link sobre el
registro reconciliado para guardar el desfase real, conservando la
posición. Si hay un gesto anterior de ejes, mantiene el cálculo existente
sobre los ejes y centros anteriores, para que el pilar siga sus ejes.
Se comparte el índice de ejes de la regeneración, evitando recorrer
el dibujo de nuevo por cada pilar.

Ocho ensayos combinan cuatro transformaciones nativas y dos orientaciones
de rejilla. Comprueban posición, identidad, vínculo, Deshacer/Rehacer y
que al mover después un eje el pilar sigue conservando su desfase.

## 6. Longitudes de huecos y detalles — con R30

La comprobación de igual longitud en entrada_revisada.filtrar_huecos se
incorporará con R30, conforme al encargo. No se adelanta en este parcial.

## Criterio recibido para integrar E

La geometría decide el lado exterior: se ampliará external_walls para
devolverlo, incluyendo patios y recintos «exterior cubierto». El campo por
muro cara_exterior permite forzar izquierda/derecha; auto no adivina si
el edificio abierto, una medianera u otro caso impide decidir.

Los tipos nuevos de envolvente tendrán orden exterior-interior. Los de
partición conservan el orden desde la cara dibujada. Un tipo sin campo de
orden conserva su significado actual y ARQVALIDAR avisa una vez. No se
voltean los dibujos existentes.

El catálogo clasifica los materiales y su posición entre fábricas,
revestimientos y trasdosados determina si el aislamiento es exterior,
de cámara o interior. Se retira la deducción por nombre del núcleo E1
antes de integrarlo. Un material sin clasificar genera aviso y no se
resuelve. Se probarán ambas caras dibujadas, patio, medianera y tipo antiguo.
Esta integración no se presenta como terminada en el parcial D1.

## Continuación de R29

Esta entrega parcial no completa R29: siguen la integración de E, F y H–K.
Después irán las cubiertas inclinadas de contorno convexo, incluidas en
la 1.0 por la instrucción más reciente, y R30. De R31 solo entra ahora
«Frente en partición», a cargo de Claude; el resto queda para después.
No se publican propuestas, incidencias ni comentarios externos.

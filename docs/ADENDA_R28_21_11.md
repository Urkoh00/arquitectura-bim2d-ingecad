# R28: aplicación de la adenda del 21-11-2026

Base v1.46.0-dev, `78c528bb7cc6123e33a43443e945fe91d200e998`.
Se entregan propuestas para que Claude revise e integre. R28-A continúa abierto:
la nueva MEMORIACARP aún no está conectada al catálogo ni dibuja el plano final.

## Decisiones aplicadas

- **Contenido propio de componentes: CC0-1.0**, aprobado por el propietario.
  El código propio sigue bajo GPL-3.0-or-later. La biblioteca de componentes
  permanece como estudio; no se entregan activos de terceros ni el catálogo.
- **Ventanas oscilobatientes: implementadas** mediante `operation=TILTANDTURN`,
  `hinge=0|1` y `side=+1|-1`. La ficha y `-VENTANAARQ` muestran la operación y la
  bisagra. El tipo sigue siendo ventana, con marco/hoja/vidrio cerrados en 3D.
- **Cubiertas: estudio actualizado**, con B1 manual antes de B2 Python derivado
  de bpypolyskel, eliminación de mathutils, velocidades `1/pendiente`, piñones y
  procedencia/licencia dentro de `arquitectura/geom/`. No se ha implementado B2.
  CGAL queda como referencia local opcional; no se traduce ni se distribuye.

## Datos y representación de la oscilobatiente

No se cambia el esquema ni se migra ningún archivo: la operación es un valor
nuevo del catálogo actual de ventanas y utiliza la bisagra y la cara existentes.
`hinge=0` designa la jamba inicial según el eje a→b del muro; `hinge=1`, la final.
Vista en planta, para `side=+1` esas manos son izquierda/derecha en el alzado
interior mostrado en la ficha; para `side=-1` se invierte esa lectura. En el modelo
sintético se utilizan ambas manos con `side=+1`. El lado se conserva al editar.
Para varias hojas, la mano indicada corresponde a la primera hoja y se alterna.

La planta combina el giro lateral con una V esquemática de basculación. El
alzado combina los triángulos lateral y basculante, con vértice de basculación en
la base de la hoja. Son símbolos de funcionamiento; no deforman ni abren el
sólido físico. Una oscilobatiente verdaderamente curva se rechaza: requiere otra
solución de herraje/geometría, fuera de esta adenda. Una pieza plana alojada en
un muro curvo conserva el recorrido común de la cuerda.

La colocación recibe una mano calculada por el sentido del segundo punto; para
TILTANDTURN respeta la mano expresamente elegida en la ficha/texto. `B` permite
invertir posteriormente la bisagra mediante la edición transaccional existente.
Las demás operaciones mantienen su criterio de colocación previo.

## Funciones compartidas, sin duplicar el generador

| Recorrido | Funciones reutilizadas |
|---|---|
| Ficha y `-VENTANAARQ` | `linea_fichas.normalizar_carpinteria`; catálogo `openings.OPERATIONS` / `OPERATION_NAMES` |
| Vista previa y dibujo en planta | `openings.plan_symbol` y el marco local del muro (`spec.point` / `proxy`) |
| Alzado de la ficha y futuras fichas de memoria | `openings.simbolos_apertura_alzado`, función pura extraída de la ficha y ampliada con la basculación |
| Piezas 3D y contrato | `openings.carpentry_parts`, `filling_box` y `exchange._filling`; se preservan `operation` y `hinge` en `params` |
| Agrupación y marcas | `memoria_carpinteria.definir` / `asignar_marcas` y `memoria_modelo.preparar`; la operación distingue tipos, la mano no |
| Deshacer/Rehacer y regeneración | `architectural_v10.create_opening`, `edit_opening` y `transactions.apply_architectural_change` |

No se añade un generador de sólidos a IngeTrazo. El empaquetado de su extensión
sigue copiando los módulos compartidos con `scripts/bundle_roundtrip.py`.

## Modelo propio y pruebas

`tests/escenario_r28.py` genera dos plantas de cotas 0 y 3,2 m con ejes XY
coincidentes y niveles identificados. Incluye ocho puertas planas (ambas manos,
una/dos hojas y correderas), una puerta corredera curva, cinco ventanas (fija,
abatible, corredera y dos oscilobatientes), un hueco y un armario de tres frentes.
No tiene aún recintos ni el plano de memoria final: se completarán al conectar A.

Las dos oscilobatientes tienen la misma definición física: se agrupan bajo una
marca, con mano y nivel por unidad. La prueba contrasta el catálogo después de
Deshacer/Rehacer, DXF y contrato. Las pruebas de ventana real insertan ambas manos
por `VENTANAARQ` y `-VENTANAARQ`, usando teclado incluso en el selector. La variante
con guion debe abrir cero cuadros. El modo `R28_COMPROBAR_DWG=1` añade reapertura
DXF/DWG con LibreDWG oficial y validación del contrato, así como idempotencia de
UNIONESARQ y ausencia de nuevas incidencias en ARQVALIDAR.

Texto para el manual de la parte implementada: «En VENTANAARQ elija Apertura →
Oscilobatiente y la jamba de la bisagra. En -VENTANAARQ responda Oscilobatiente
(o TILTANDTURN) y Bisagra Inicial/Final. La vista previa muestra planta y alzado;
el 3D representa la carpintería cerrada. La operación no está disponible para
puertas ni para hojas realmente curvas».

## Estudios y alcance de la entrega

El estudio B incluye la comparación por commit de bpypolyskel (GPL-3.0-only),
polyskel original (LGPLv3) y ladybug-geometry-polyskel (AGPLv3), sus patios, ausencia
de pesos por lado, mantenimiento y esfuerzo estimado. Conserva los ocho casos
analíticos como requisito de B2; todavía no se han ensayado esas bibliotecas.
El estudio C registra CC0 como decisión tomada, sin volver a pedir aprobación.

No se han modificado IngeCAD ni IngeTrazo. No se ha instalado ni usado una
biblioteca de SketchUp. El manual recibido y su extracción permanecen fuera de
la entrega. Solo se incluyen modelos sintéticos propios y código del plugin.

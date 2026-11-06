# Registro de errores, inconsistencias y carencias de IngeCAD e IngeTrazo

Este registro reúne lo que el desarrollo del plugin Arquitectura ha encontrado en los dos programas
anfitriones. Recoge también las consultas ya enviadas a sus desarrolladores. Se actualiza en cada
versión del plugin. Una prueba automática (`tests/test_registro_upstream.py`) comprueba que todos
los parches de `docs/propuestas_upstream/` figuran aquí.

**Política de envío (6-11-2026):** no se envían más consultas hasta que respondan las dos primeras
(IngeTrazo #1221 y #1222). Lo que no se ha enviado queda preparado: reproducción, parche y pruebas.

**Evidencia:**
- **[A]** reproducido con el código oficial, con una prueba o un script;
- **[B]** deducido de la lectura del código, sin reproducir;
- **[U]** sin comprobar.

Todo se ha comprobado en Linux. **Nada se ha comprobado aún en Windows.**

**Versiones examinadas:**
- IngeCAD `main` @ `b625489` (29-10-2026);
- IngeTrazo `main` @ `e61132a` (1-11-2026).

El 6-11-2026 no había commits nuevos en ninguno de los dos.

**Estados:**
- *Enviada*: con incidencia abierta;
- *Preparada*: parche y pruebas listos, sin enviar;
- *Documentada*: descrita, sin parche;
- *Resuelta*: corregida upstream.

---

## IngeTrazo

| Ref. | Tipo | Asunto | Evidencia | Estado | Parche | Rodeo en el plugin |
|---|---|---|---|---|---|---|
| T-01 | Error | El volumen BIM pierde precisión lejos del origen (`core.bim.face_set_volume` en float32): un pilar de 0,27 m³ da +0,5 % a 300 m y −73 % a 3 km | [A] | **Enviada** [#1221](https://github.com/ingelibre/ingetrazo/issues/1221) (5-11-2026). Abierta, sin respuesta (6-11-2026) | `ingetrazo/0001-…` (parte `core/bim.py`) | Cantidades exactas calculadas en el plugin |
| T-02 | Carencia | El exportador IFC no usa las claves extra de `group.ifc` (GUID estable, planta, Psets, material, tipo, cantidades, huecos `IfcOpeningElement` + `IfcRelVoidsElement`) | [A] | **Enviada** [#1222](https://github.com/ingelibre/ingetrazo/issues/1222) (5-11-2026). Abierta, sin respuesta (6-11-2026) | `ingetrazo/0001-…` (parte `formats/ifc.py`) | Ninguno posible: sin el parche, el IFC pierde esa información |
| T-03 | Error | `IfcSpace` se escribe dentro de `IfcRelContainedInSpatialStructure` en vez de agregarse a la planta con `IfcRelAggregates`: 3 errores de reglas IFC4 en IfcOpenShell con 2 recintos | [A] | Preparada | `ingetrazo/0002-…` | Aviso en `EXPORTARBIM` |
| T-04 | Carencia | Las puertas y ventanas no se relacionan con su hueco (`IfcRelFillsElement`) | [A] | Preparada | `ingetrazo/0003-…` | Clave `group.ifc['fills']` ya exportada |
| T-05 | Carencia | Los atributos enumerados se escriben siempre `$`: un falso techo no puede ser `IfcCovering .CEILING.` ni una puerta indicar `OperationType`, ni una ventana `PartitioningType` | [A] | Preparada | `ingetrazo/0004-…` | Clave `group.ifc['enums']` ya exportada; Pset `ARQ_IngeCAD` |
| T-06 | Carencia | No se escriben capas de material (`IfcMaterialLayerSet` / `IfcMaterialLayerSetUsage`): un muro multicapa llega con un único material | [B] | Documentada | — | Pset `ARQ_Capas` con espesores y materiales |
| T-07 | Carencia | No se escriben límites de espacio (`IfcRelSpaceBoundary`, 1.º/2.º nivel), útiles para el análisis térmico | [B] | Documentada | — | Recintos coplanarios con muros y falso techo, de los que pueden deducirse |
| T-08 | Carencia | Solo se escriben tipos (`IfcRelDefinesByType`) para muro, pilar, losa, viga y miembro; puertas, ventanas y revestimientos quedan sin tipo (`_TYPE_CLASSES` en `formats/ifc.py`) | [B] | Documentada | — | Nombre del tipo en el Pset |

## IngeCAD

| Ref. | Tipo | Asunto | Evidencia | Estado | Parche | Rodeo en el plugin |
|---|---|---|---|---|---|---|
| C-01 | Carencia | No hay reactores para plugins tras órdenes genéricas (COPY, MOVE, MIRROR, ROTATE, ERASE). Solo existe el reactor interno de cotas asociativas | [A] | Preparada | `ingecad/0001-…` (generaliza el reactor DIMASSOC, 72 líneas) | `UNIONESARQ` sincroniza al final, en un solo paso de deshacer |
| C-02 | Inconsistencia | Al borrar una entidad que pertenece a un grupo, el grupo sigue apuntando a ella. Al guardar, el miembro desaparece del grupo; si después se deshace el borrado, la entidad vuelve sin su grupo (`EraseCommand` desvincula, pero no toca los grupos) | [A] (script de reproducción abajo) | Documentada | — | `DropGroupsCommand` quita y restaura los grupos del plugin alrededor de cada borrado |
| C-03 | Carencia | Las herramientas de plugin no reciben el doble clic (`MainWindow.on_canvas_double_click` no tiene gancho) | [A] | Documentada | — | Editar con `EDITARARQ` |
| C-04 | Carencia | Las herramientas de plugin no reciben teclas de función (F5 está libre en IngeCAD) | [A] | Documentada | — | Atajo de ventana temporal mientras la herramienta está activa; opción tecleada I |
| C-05 | Carencia | El modo ortogonal solo sigue el ángulo del SCP; no hay ortogonal relativo a un elemento, que es lo útil para dibujar muros oblicuos | [A] | Documentada | — | Ninguno |

---

## Reproducciones

### C-02: grupos tras borrar y deshacer

```python
import ezdxf
from core.document import Document
from core.commands import History
from core import actions

d = Document(ezdxf.new()); msp = d.doc.modelspace()
a = msp.add_line((0, 0), (1, 0)); b = msp.add_line((0, 1), (1, 1))
g = d.doc.groups.new("G"); g.set_data([a, b]); g.dxf.selectable = 1
h = History(d)
h.execute(actions.EraseCommand([a]))
# el grupo sigue listando la entidad borrada
d.doc.saveas("g.dxf")    # al guardar, el miembro borrado se elimina del grupo
h.undo()
# la línea vuelve al dibujo, pero ya no pertenece al grupo
```

Resultado (IngeCAD `b625489`, ezdxf 1.4): grupo `['2F', '30']` tras borrar; `['30']` al releer el
fichero y tras deshacer. Se espera que el grupo recupere la línea al deshacer. Una solución mínima:
que `EraseCommand` guarde la pertenencia a grupos y la restaure en `undo`.

---

## Historial

- **6-11-2026:** se crea el registro. Se añade C-02 (reproducido) y se comprueba que #1221 y #1222
  siguen sin respuesta.
- **6-11-2026:** se preparan T-04 (v1.10.0) y T-05 (v1.10.2).
- **6-11-2026:** se prepara T-03 (v1.7.0).
- **5-11-2026:** se envían T-01 y T-02; se prepara C-01.

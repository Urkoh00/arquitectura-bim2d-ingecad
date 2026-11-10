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
| T-01 | Error | El volumen BIM pierde precisión lejos del origen (`core.bim.face_set_volume` en float32): un pilar de 0,27 m³ da +0,5 % a 300 m y −73 % a 3 km | [A] | **Enviada** [#1221](https://github.com/ingelibre/ingetrazo/issues/1221) (5-11-2026). Abierta, sin respuesta (9-11-2026); IngeTrazo 0.6.1 (8-11-2026) sigue igual | `ingetrazo/0001-…` (parte `core/bim.py`) | Cantidades exactas calculadas en el plugin. **Efecto real el 9-11-2026:** la comprobación de la extensión comparaba ese volumen en float32 y rechazaba la importación de un plano dibujado a 35 m del origen (una puerta: 0,278689 frente a 0,278775 m³). La extensión mide ahora en doble precisión respecto a un vértice del sólido |
| T-02 | Carencia | El exportador IFC no usa las claves extra de `group.ifc` (GUID estable, planta, Psets, material, tipo, cantidades, huecos `IfcOpeningElement` + `IfcRelVoidsElement`) | [A] | **Enviada** [#1222](https://github.com/ingelibre/ingetrazo/issues/1222) (5-11-2026). Abierta, sin respuesta (9-11-2026) | `ingetrazo/0001-…` (parte `formats/ifc.py`) | Ninguno posible: sin el parche, el IFC pierde esa información |
| T-03 | Error | `IfcSpace` se escribe dentro de `IfcRelContainedInSpatialStructure` en vez de agregarse a la planta con `IfcRelAggregates`: 3 errores de reglas IFC4 en IfcOpenShell con 2 recintos | [A] | Preparada | `ingetrazo/0002-…` | Aviso en `EXPORTARBIM` |
| T-04 | Carencia | Las puertas y ventanas no se relacionan con su hueco (`IfcRelFillsElement`) | [A] | Preparada | `ingetrazo/0003-…` | Clave `group.ifc['fills']` ya exportada |
| T-05 | Carencia | Los atributos enumerados se escriben siempre `$`: un falso techo no puede ser `IfcCovering .CEILING.` ni una puerta indicar `OperationType`, ni una ventana `PartitioningType`. Otra extensión, cad2ingetrazo, ya escribe `group.ifc['predefined']`, `['object_type']` y `['load_bearing']`, que el exportador ignora. **Antes de enviar hay que acordar unos nombres de clave comunes** (`predefined` frente a `enums`) | [A] | Preparada; nombres de clave por acordar | `ingetrazo/0004-…` | Clave `group.ifc['enums']` ya exportada; Pset `ARQ_IngeCAD` |
| T-06 | Defecto | La medición de un `IfcWall` curvo es la superficie de su huella y no la de su paramento: `core/bim.py class_quantities` toma la cara de mayor área como paramento, y un muro curvo son muchas caras pequeñas, de modo que gana la cara superior. Además IngeTrazo sustituye las cantidades que trae el elemento (prueba del 10-11: un muro de 16,62 m × 0,10 sale con `Length` 0,615, `Width` 2,7 y metrado 1,66 m²). Propuesta: medir el paramento como la suma de las caras verticales de un lado (o área lateral = volumen / espesor) y respetar `Qto_*` ya presentes | [A] | Documentada, sin enviar (esperando #1221/#1222) | — | El `.arqbim` lleva las cantidades exactas del plugin |
| T-06 | Carencia | No se escriben capas de material (`IfcMaterialLayerSet` / `IfcMaterialLayerSetUsage`): un muro multicapa llega con un único material | [B] | Documentada | — | Pset `ARQ_Capas` con espesores y materiales |
| T-07 | Carencia | No se escriben límites de espacio (`IfcRelSpaceBoundary`, 1.º/2.º nivel), útiles para el análisis térmico | [B] | Documentada | — | Recintos coplanarios con muros y falso techo, de los que pueden deducirse |
| T-08 | Carencia | Solo se escriben tipos (`IfcRelDefinesByType`) para muro, pilar, losa, viga y miembro; puertas, ventanas y revestimientos quedan sin tipo (`_TYPE_CLASSES` en `formats/ifc.py`) | [B] | Documentada | — | Nombre del tipo en el Pset |

### Otras extensiones de IngeTrazo con las mismas necesidades (estudio del 7-11-2026)

- **cad2ingetrazo 3.x** (GPL-3.0-or-later): marca sus grupos con `group.ifc` (clase, nombre, `predefined`, `object_type`, `load_bearing`). No escribe `IfcSpace`, plantas ni huecos relacionados: le afectan T-02, T-03, T-04 y T-05.
- **ArchXQ IT Lite 0.11** (GPL-3.0-or-later): guarda su modelo en `scene.plugin_data`, la ranura de datos que IngeTrazo reserva a cada extensión dentro del IGZ, y no marca clases IFC. Su IFC sale sin semántica BIM.

Las correcciones propuestas son generales: servirían a todas las extensiones de arquitectura, no solo a este plugin. Es un argumento a favor cuando se presenten.

## IngeCAD

| Ref. | Tipo | Asunto | Evidencia | Estado | Parche | Rodeo en el plugin |
|---|---|---|---|---|---|---|
| C-01 | Carencia | No hay reactores para plugins tras órdenes genéricas (COPY, MOVE, MIRROR, ROTATE, ERASE). Solo existe el reactor interno de cotas asociativas | [A] | **Resuelta en IngeCAD 0.8.0** (en desarrollo) (9-11-2026: `PluginSpec.reactors`, «proposed by the architecture plugin») | `ingecad/0001-…` (ya no hace falta) | El plugin usa el reactor oficial si existe; sin él, `UNIONESARQ` |
| C-02 | Inconsistencia | Al borrar una entidad que pertenece a un grupo, el grupo sigue apuntando a ella. Al guardar, el miembro desaparece del grupo; si después se deshace el borrado, la entidad vuelve sin su grupo (`EraseCommand` desvincula, pero no toca los grupos) | [A] (script de reproducción abajo) | **Resuelta en IngeCAD 0.8.0** (en desarrollo) («ERASE takes a member out of its group, U puts it back») | — | `DropGroupsCommand` se mantiene para versiones anteriores |
| C-03 | Carencia | Las herramientas de plugin no reciben el doble clic (`MainWindow.on_canvas_double_click` no tiene gancho) | [A] | **Resuelta en IngeCAD 0.8.0** (en desarrollo) (`PluginSpec.on_double_click`) | — | Doble clic en muro, carpintería, pilar o recinto (v1.17); `EDITARARQ` en versiones anteriores |
| C-04 | Carencia | Las herramientas de plugin no reciben teclas de función (F5 está libre en IngeCAD) | [A] | **Resuelta en IngeCAD 0.8.0** (en desarrollo) (`Tool.on_key`, teclas F4, F5 y F6) | — | F5 por `on_key`; atajo de ventana solo en versiones anteriores |
| C-05 | Carencia | El modo ortogonal solo sigue el ángulo del SCP; no hay ortogonal relativo a un elemento, que es lo útil para dibujar muros oblicuos | [A] | **Propuesta enviada** el 10-11-2026: variable SNAPANG de AutoCAD (#135) | — | Ninguno |
| C-06 | Inconsistencia | Deshacer una SIMETRÍA (`TransformCommand` con `upright`) de una entidad OCS, por ejemplo una polilínea, restaura sus propiedades y vértices pero no su XDATA, aunque la simetría sí transformó los puntos y vectores de XDATA (1011/1012). Las demás órdenes se deshacen con la matriz inversa y dejan la XDATA bien. Reproducción: polilínea con XDATA 1011; SIMETRÍA sin conservar el original; deshacer: los vértices vuelven y el punto 1011 queda reflejado | [A] (confirmada en 0.8.0) | **Enviada** el 10-11-2026 como solicitud de cambio a ingelibre/ingecad (rama `fix-mirror-undo-xdata`): `_restore_entity` restaura también la XDATA; prueba nueva con polilínea, círculo, texto y línea; la suite de IngeCAD no cambia | — | El marco de referencia del plugin guarda también el contorno y se ignora si la geometría volvió a su sitio (`frame.read_frame`) |

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

- **10-11-2026 (noche):** primera prueba del usuario con IngeCAD 0.8 e IngeTrazo 0.6.1 en Windows 10: la cadena funciona y los dos IFC validan sin errores. En el metrado de IngeTrazo aparece T-06 (muros curvos medidos por su huella).
- **10-11-2026:** IngeCAD publica la 0.8.0 (la víspera estaba solo en la rama principal). Se envían a IngeCAD dos solicitudes de cambio desde Urkoh00/ingecad: la corrección de C-06 (`fix-mirror-undo-xdata`) y la variable SNAPANG para C-05 (`snapang`, #135). Las pruebas de IngeCAD esperan a que el mantenedor las autorice, como es habitual en una primera contribución.
- **9-11-2026 (noche, 3):** C-06 se confirma en IngeCAD 0.8.0 y se prepara la corrección (una línea en `core/actions.py` y una prueba). Con ella, la suite de IngeCAD da los mismos resultados (2568 superadas; los 8 fallos son del entorno sin pantalla y ocurren igual sin el cambio) y el plugin pasa sus 287 pruebas. No se ha enviado.
- **9-11-2026 (noche, 2):** la rama principal de IngeCAD prepara la 0.8.0 (aún sin publicar; la última publicada es la 0.7.0, del 29-10) con un nivel 2 del contrato de plugins. Resuelve C-01 (reactores; el código cita la propuesta de este plugin), C-02 (grupos tras borrar y deshacer), C-03 (doble clic) y C-04 (teclas de función para la herramienta activa). Además añade transacciones, selección y encuadre para plugins, pinzamientos propios, filtros de entrada y `api_version`. La v1.17 los usa cuando existen y mantiene sus rodeos para versiones anteriores. Siguen abiertas C-05 (ortogonal por elemento) y C-06 (deshacer SIMETRÍA y XDATA).

- **9-11-2026 (noche):** al aceptar las órdenes de IngeCAD sobre elementos BIM, se encuentra C-06. Se adopta la regla oficial de IngeTrazo para coordenadas lejanas (`formats/recenter.py`) en la extensión. La auditoría independiente de la v1.15 trae parches para IngeCAD (reactores, grupos tras borrar y deshacer) e IngeTrazo (GUID estables, `IfcSpace`, `IfcRelFillsElement`, atributos enumerados, volumen, importación en un paso). Se consolidarán con T-03 a T-05 y C-01 a C-02. No se envía nada hasta que respondan #1221 y #1222.

- **9-11-2026:** T-01 impedía importar en IngeTrazo 0.6.1 un plano lejos del origen (lo vio el usuario). Rodeo en la extensión: volumen en doble precisión. #1221 y #1222 siguen sin respuesta; no se envía nada nuevo.
- **7-11-2026:** se estudian las extensiones ArchXQ IT Lite, cad2ingetrazo y BlackFox-CAD. T-05 queda pendiente de acordar los nombres de clave con lo que ya usa cad2ingetrazo.
- **6-11-2026:** se crea el registro. Se añade C-02 (reproducido) y se comprueba que #1221 y #1222
  siguen sin respuesta.
- **6-11-2026:** se preparan T-04 (v1.10.0) y T-05 (v1.10.2).
- **6-11-2026:** se prepara T-03 (v1.7.0).
- **5-11-2026:** se envían T-01 y T-02; se prepara C-01.

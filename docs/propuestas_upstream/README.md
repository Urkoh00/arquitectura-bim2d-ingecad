# Propuestas a IngeCAD e IngeTrazo

Parches **propuestos**, no aplicados. Se discuten con su desarrollador mediante incidencias;
el plugin se adapta a lo que él decida.

| Proyecto | Incidencia | Tema | Parche | Estado |
|---|---|---|---|---|
| IngeTrazo | [#1221](https://github.com/ingelibre/ingetrazo/issues/1221) | Volumen BIM impreciso lejos del origen (`core.bim.face_set_volume`, float32) | `ingetrazo/` (parte `core/bim.py`) | Abierta, 5-11-2026 |
| IngeTrazo | [#1222](https://github.com/ingelibre/ingetrazo/issues/1222) | El exportador IFC usa las claves extra de `group.ifc` (guid, planta, Psets, material, tipo, cantidades, huecos) | `ingetrazo/` (parte `formats/ifc.py`) | Abierta, 5-11-2026 |
| IngeCAD | — (pendiente) | Reactores de plugin tras comandos genéricos (COPY/MOVE/MIRROR) en el mismo paso de deshacer | `ingecad/` | Sin presentar: se esperará a la respuesta de las de IngeTrazo |
| IngeTrazo | — (pendiente) | `IfcSpace` se escribe dentro de `IfcRelContainedInSpatialStructure` y no se agrega a la planta: 2 errores de reglas IFC4 en IfcOpenShell; faltan `IfcRelSpaceBoundary` | `ingetrazo/0002-…` (3 líneas efectivas: agregar con `IfcRelAggregates`) | Comprobado el 6-11-2026: con el parche, 0 errores; se presentará tras la respuesta a #1221/#1222 |
| IngeTrazo | — (pendiente) | Puertas y ventanas sin `IfcRelFillsElement`: el IFC no dice qué hueco rellena cada una. Clave `group.ifc['fills']` con el GlobalId del hueco | `ingetrazo/0003-…` (11 líneas) | Comprobado el 6-11-2026 con 2 puertas, 1 ventana y 1 vano: 0 errores (IfcOpenShell, reglas EXPRESS); sin presentar |
| IngeTrazo | — (pendiente) | Atributos enumerados siempre `$`: un falso techo no puede ser `IfcCovering .CEILING.` ni una puerta decir cómo abre. Clave `group.ifc['enums']` (PredefinedType, OperationType, PartitioningType) | `ingetrazo/0004-…` | Comprobado el 6-11-2026: falso techo `.CEILING.`, puertas abatible y corredera, ventanas de 1 y 2 hojas; 0 errores; pruebas IFC/BIM de IngeTrazo correctas; sin presentar |

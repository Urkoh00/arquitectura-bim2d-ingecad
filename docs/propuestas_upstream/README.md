# Propuestas a IngeCAD e IngeTrazo

Parches **propuestos**, no aplicados. Se discuten con su desarrollador mediante incidencias;
el plugin se adapta a lo que él decida.

| Proyecto | Incidencia | Tema | Parche | Estado |
|---|---|---|---|---|
| IngeTrazo | [#1221](https://github.com/ingelibre/ingetrazo/issues/1221) | Volumen BIM impreciso lejos del origen (`core.bim.face_set_volume`, float32) | `ingetrazo/` (parte `core/bim.py`) | Abierta, 5-11-2026 |
| IngeTrazo | [#1222](https://github.com/ingelibre/ingetrazo/issues/1222) | El exportador IFC usa las claves extra de `group.ifc` (guid, planta, Psets, material, tipo, cantidades, huecos) | `ingetrazo/` (parte `formats/ifc.py`) | Abierta, 5-11-2026 |
| IngeCAD | — (pendiente) | Reactores de plugin tras comandos genéricos (COPY/MOVE/MIRROR) en el mismo paso de deshacer | `ingecad/` | Sin presentar: se esperará a la respuesta de las de IngeTrazo |
| IngeTrazo | — (pendiente) | `IfcSpace` se escribe dentro de `IfcRelContainedInSpatialStructure` y no se agrega a la planta: 2 errores de reglas IFC4 en IfcOpenShell; faltan `IfcRelSpaceBoundary` | `ingetrazo/0002-…` (3 líneas efectivas: agregar con `IfcRelAggregates`) | Comprobado el 6-11-2026: con el parche, 0 errores; se presentará tras la respuesta a #1221/#1222 |

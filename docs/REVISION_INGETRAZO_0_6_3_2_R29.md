# Revisión de IngeTrazo 0.6.3.2 para R29

24-11-2026. Se trabaja con la última versión publicada, no con 0.6.2.1.
Fuentes oficiales: etiqueta `v0.6.3.2`, revisión `78defb95`.

- [Notas de publicación](https://github.com/ingelibre/ingetrazo/releases/tag/v0.6.3.2).
- [API de recursos](https://github.com/ingelibre/ingetrazo/blob/v0.6.3.2/docs/resource_api.md).
- [Paquetes portables](https://github.com/ingelibre/ingetrazo/blob/v0.6.3.2/docs/resource_bundle.md).
- [Automatización](https://github.com/ingelibre/ingetrazo/blob/v0.6.3.2/docs/ai-bridge.es.md).
- [Escritor IFC](https://github.com/ingelibre/ingetrazo/blob/v0.6.3.2/formats/ifc.py).

## Qué cambia para el proyecto

| Novedad | Comprobación | Aplicación al plugin |
|---|---|---|
| Recursos genéricos, bibliotecas y `.iglib` | Lectura de API y pruebas oficiales de recursos y paquetes | Reutilizar en la futura biblioteca de componentes; las extensiones siguen siendo dueñas del formato y significado BIM. API experimental: no dar por definitivo el contrato. |
| Caja de sección de seis planos, en modelo y hojas | Lectura de `core/section.py` y pruebas oficiales | Estudiar su reutilización al encargar alzados/secciones; no escribir ahora otro recortador en R29. |
| Componentes anidados y copias vinculadas, biblioteca del usuario | Anunciado en la publicación; no se ha realizado aquí un ensayo visual completo de ese flujo | Base prometedora para componentes; no sustituye los parámetros ni la identidad del modelo de IngeCAD. |
| Hojas, leyendas, índice y navegación | Anunciado en la publicación | Revisar en su encargo de documentación; no se han medido aquí sus tiempos ni probado todas sus ventanas. |
| MCP con operaciones nombradas y modo sin ventana | Documentación oficial leída | Facilita futuros recorridos reproducibles. No se ha abierto ningún servidor ni enviado comunicaciones. |
| IFC4.3 y bloque `delivery`, georreferencia y norte | Código y prueba existente de contrato → IGZ → IFC | Mantener la adaptación de Claude ya integrada; leer las reglas del anfitrión en vez de duplicarlas. |
| Mover o borrar un hueco conserva las zonas del muro | Corrección anunciada en 0.6.3.2 | Es relevante para el trabajo directo en IngeTrazo. El plugin ya lleva huecos y piezas desde una definición común: no activar un segundo recorte automáticamente. No se ha ensayado aquí ese gesto visual nativo. |

Las cifras de rendimiento de las notas son del mantenedor. Esta revisión no
las presenta como mediciones propias.

## Pruebas ejecutadas en esta versión

1. Los tests oficiales `test_resource_api.py`, `test_resource_bundle.py` y
   `test_section_box.py`: **67 correctos y 1 omitido**. Son comprobaciones de
   estas capacidades concretas, no la batería completa de IngeTrazo.
2. La prueba del plugin `test_cadena_completa_con_ingetrazo`: contrato,
   construcción de escena, guardado y relectura IGZ y escritor IFC oficial.
   Se mantienen los tipos predefinidos e IsExternal de los muros del ejemplo,
   con cero errores EXPRESS.
3. Modelo sintético propio con muro, puerta y oscilobatiente doble: una manilla
   por carpintería. El IGZ conserva las piezas, su material y geometría. El IFC
   contiene un IfcDoor y un IfcWindow, sin otro elemento BIM para las manillas;
   los volúmenes geométricos leídos con IfcOpenShell coinciden con la suma de
   piezas del contrato, dentro de 1e-7 m³. Cero errores EXPRESS.

Se entregan los scripts, datos y resultados de esta última comprobación.
La pintura de caras y el registro de piezas del IGZ no equivalen a una
asociación IFC de materiales por pieza.

## Límites que siguen siendo importantes

El ejemplo de carpinterías ha comprobado lo siguiente en el escritor oficial:

- Los GUID de puerta y ventana del contrato no se conservan como GlobalId IFC.
- No se crean relaciones `IfcRelFillsElement`: el ejemplo produce cero.
- El IFC solo declara el material global del muro («Sin definir»); no asocia
  Acero a la manilla ni los demás materiales a sus piezas. El IGZ sí conserva
  esa información. Por ello, el requisito de R29-C de material de la manilla
  **no está resuelto en el IFC final por el escritor actual**.
- Las áreas IFC no coinciden con las del contrato: puerta de 1,20 × 2,10 m,
  2,52 m² en el contrato frente a 0,1659 m² en Qto_DoorBaseQuantities; ventana
  de 1,20 × 1,20 m, 1,44 m² frente a 0,23 m² en Qto_WindowBaseQuantities.
  Anchura y altura sí coinciden en este caso. El escritor toma el área neta
  de una cara del modelo en vez del valor canónico etiquetado por la extensión.

Los dos primeros límites se corresponden con las aportaciones anteriores
P1–P4; no se declaran resueltos por las novedades de georreferencia o IFC4.3.
La asociación de materiales de cada pieza queda anotada para revisión como
**identificador pendiente**, con este caso sintético reproducible. No se abre
una incidencia, no se modifica IngeTrazo y no se crea otro escritor IFC.
La discrepancia de áreas queda también con **identificador pendiente** para
contrastar sus antecedentes. Propuesta: que el escritor consuma las cantidades
canónicas ya etiquetadas, con su validación, en vez de inferirlas de una pieza
del conjunto. Los dos casos y sus Psets completos están en el resultado JSON.

Un IFC sin errores EXPRESS puede seguir siendo semánticamente incompleto.
La validación anterior comprueba sintaxis, geometría y casos indicados; no
autoriza a declarar terminado el intercambio para cálculo profesional.

Para R29-E, el catálogo actual admite `IfcCovering`, y sus reglas incluyen
CLADDING e INSULATION. Se podrá usar esa vía con su material por elemento.
El catálogo no incluye `IfcFurniture` ni `IfcSanitaryTerminal`: la futura
biblioteca aún debe tener en cuenta esa limitación.

## Procedencia y alcance

No se han modificado IngeCAD ni IngeTrazo. No se ha instalado ni usado una
biblioteca de SketchUp; no se han abierto ni copiado `_skp` o `_openskp` de
cad2ingetrazo. No se incluye material comercial ni planos del propietario.
Los ensayos y la entrega solo contienen modelos sintéticos propios.

La nueva base del plugin es `ed930df`, de `r29-parcial-codex`: reúne la
recuperación A/B, el redondeo por exceso de Claude y `main` v1.48.0-dev. Las
mejoras se proponen contra esa base, no contra `b151e84`.

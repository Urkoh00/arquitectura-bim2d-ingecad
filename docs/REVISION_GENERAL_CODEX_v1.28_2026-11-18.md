# Revisión general independiente — Arquitectura para IngeCAD v1.28

18-11-2026. Revisión solicitada por el propietario, además de R21. Se examina el
plugin y su extensión; no ARQBIM DETECT ni el visor. No se modifica ningún motor
oficial. No se envían incidencias ni mensajes externos.

## Opinión técnica

La herramienta tiene una base geométrica bien defendida: registros BIM únicos,
identidad persistente, huella constructiva compartida, alturas por niveles y
operaciones reversibles. La v1.28 supera sus 729 pruebas de partida en IngeCAD
0.8, incluidos persistencia DXF, geometría, recintos y rendimiento. Es un avance
real respecto a un generador de líneas o una exportación 3D sin asociaciones.

Todavía la considero una herramienta experimental, adecuada para ensayos y
trabajo controlado. El punto más débil es la confianza en el intercambio final:
que IGZ conserve un dato no acredita que el IFC lo haya recibido. El segundo es
la validación desigual entre formularios, normalizadores y exportación; el
hallazgo siguiente demuestra una laguna que la suite previa no detectaba.

No aconsejo abrir más familias antes de reforzar esa validación y hacer una
aceptación interactiva en Windows de dibujo, selección, capas, sincronización y
recuperación tras errores. Esta recomendación no implica cambiar el orden de
trabajo fijado por Claude y el propietario.

## Incidencias y límites, por prioridad

### RG-01 — Confirmado: ancho de marco negativo aceptado

Prioridad media; defecto del plugin, previo a R21. Con las funciones públicas
existentes se crea una ventana con `frame_width=-0.05`. La ficha conserva ese
valor; su función `problems()` devuelve una lista vacía; `integrity.audit()`
no informa incidencias y el contrato pasa `validate_contract`.

Reproducción: `scripts/review_v128.py`, ejecutado sobre **r21-base intacta**,
no sobre el parche. Evidencia: `review_v128.json`. No se ha escrito XDATA a mano.

Causa observable: `_spin()` admite medidas negativas, `carpentry_form.problems`
solo comprueba que el marco no sea demasiado grande y `carpentry_parts` limita
internamente su ancho a cero. El registro conserva una medida imposible mientras
el generador la interpreta de otro modo. Debe rechazarse en la validación común
y señalarse en ARQVALIDAR, sin corregir registros existentes en silencio.
R21 rechaza esa medida en sus propuestas; **no se presenta este cambio como una
corrección completa de la ficha original**. Se comunica para que Claude lo
integre como reparación independiente.

### RG-02 — Confirmado: pérdida semántica en el IFC oficial

Prioridad alta para una entrega BIM. Cadena sintética oficial con IngeTrazo 0.6.2:
se exportan 8 objetos (4 muros, ventana, puerta de armario, cuerpo y recinto),
pero el IFC contiene **cero IfcPropertySet y cero IfcRelDefinesByType**. Además,
IfcSpace produce dos errores EXPRESS: WR31 y WR41. El modelo IGZ conserva los
registros y el ciclo R21 funciona. Son limitaciones conocidas de T-02/T-03/T-05,
no una pérdida causada por R21. No se aplica ningún parche a formats/ifc.py.

Consecuencia: un IFC visualmente correcto no garantiza clasificaciones,
materiales, cantidades declaradas ni relaciones espaciales correctas. Mantener
el informe de validación como evidencia de cada ensayo y comunicar estas
limitaciones en la entrega final. No afirmar conformidad IFC total.

### RG-03 — Límite comprobado: armario fijo como proxy

El cuerpo se genera como IfcBuildingElementProxy, no IfcFurniture, por la lista
de clases del anfitrión. R23 lo declara y la v1.28 lo registra en T-15. Conserva
su geometría y su identidad; la clasificación de mobiliario sigue pendiente del
anfitrión. No se debe renombrar un proxy como si ya fuera IfcFurniture.

### RG-04 — Revisión de arquitectura y usabilidad

Observación de código, no fallo funcional reproducido: varias funciones de
geometría y clases de interacción conviven en módulos muy grandes. Al reutilizar
cabinets en IngeTrazo aparecía una dependencia de opening_tools y del núcleo CAD.
R21 separa únicamente CabinetTool en cabinet_tools.py para compartir el mismo
motor sin copiar lógica ni cargar la aplicación CAD. Recomiendo continuar esa
separación gradualmente, con pruebas, sin una reescritura general.

La instalación de la extensión exige ahora copiar una carpeta completa. El
panel indica si debe reexportarse un contrato antiguo y el manual R21 actualiza
el procedimiento. Un instalador o comprobación de integridad de la extensión
sería una mejora de producto; no forma parte de esta entrega.

## Cobertura y límites de esta revisión

- ZIP recibido: SHA256 `8b8de4f87c7b3f263720f6612eb38ac6dae6cfe898e5d1ef779363fe20c0112f`.
- Coincidencia comprobada de los archivos del ZIP con los blobs Git del commit
  `9a19bd97a680f782fe4534786c68aef9fdf5da2d`; el único fichero adicional es
  `MANUAL.md`. No se deduce la procedencia solo del nombre de versión.
- Base intacta: 729 pruebas correctas en 0.8. R21 tiene verificaciones adicionales
  de conflictos, catálogo, recintos, persistencia y Deshacer/Rehacer.
- Fuentes oficiales de IngeCAD 0.8/0.7 e IngeTrazo 0.6.1/0.6.2, sin cambios.
- Interfaz Qt offscreen y modelos sintéticos. No se afirma una prueba de usuario
  en Windows, GPU o sesión gráfica interactiva de un edificio real.
- No se emplean ni publican planos privados. No se ha leído el informe completo
  de revisión de Claude, que el ZIP cita pero no incluye; esta opinión es propia.

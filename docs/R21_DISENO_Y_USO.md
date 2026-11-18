# R21 — Edición de tipos y vuelta a IngeCAD

Base: ZIP v1.28.0-dev aportado por el propietario. Parche local; no modifica los
motores oficiales. IngeCAD sigue siendo la definición autorizada del edificio.

1. Instalar el plugin parcheado en IngeCAD. Copiar **todo** `ingetrazo_ext/` a la
   carpeta de extensiones de IngeTrazo, incluidos `_arq_edit.py`, `_arqbim_sync.py`
   y `arq_shared/`. Las antiguas instrucciones de «dos ficheros» quedan superadas.
2. EXPORTARBIM vuelve a crear el `.arqbim`. Los contratos antiguos se pueden
   importar, pero para editarlos deben exportarse otra vez con esta versión.
3. Seleccionar un muro, puerta, ventana o armario importado en IngeTrazo. El panel
   «Propiedades de Arquitectura» muestra clase, tipo y dimensiones. Al seleccionar
   un muro, el selector de elemento permite acceder a sus huecos sin carpintería.
   El desplegable de tipos ofrece los tipos de muro del dibujo y las carpinterías
   guardadas o presentes en él, filtradas por clase y modo de armario.
4. Aplicar una propuesta es un único Deshacer de IngeTrazo. Apertura, hojas,
   materiales y perfiles se generan con el código exacto del plugin. Cambios de
   tamaño, espesor, posición transversal, altura, antepecho o categoría quedan
   pendientes: el modelo muestra su geometría anterior hasta aceptar en IngeCAD.
   El panel lo avisa; guardar IGZ conserva origen, propuestas y estado pendiente.
5. «Guardar como tipo» guarda un tipo en el catálogo propuesto. Para sustituir un
   tipo existente se utiliza su mismo nombre explícitamente; esto no convierte
   automáticamente todos los ejemplares de ese tipo.
6. «Exportar cambios a IngeCAD» escribe `.arqcambios`, JSON versión 1, en metros,
   con ID del dibujo, fingerprint de la definición importada, ID BIM, valores
   anteriores/nuevos y catálogo anterior/nuevo. No contiene código ejecutable.
7. SINCRONIZARARQ comprueba el dibujo y la revisión. Ante cualquier cambio en la
   revisión muestra todos los elementos afectados como conflictos; por defecto
   conserva IngeCAD. Se decide aplicar/conservar por elemento y por catálogo.
   Un elemento eliminado no se recrea en silencio. Un dibujo distinto se rechaza.
8. Todas las propuestas aceptadas se validan en una copia del dibujo, con las
   funciones existentes edit_wall/edit_opening y regeneración real. Después se
   aplican sobre el original con encuentros y recintos en un solo Deshacer. Las
   capas bloqueadas conservan las restricciones nativas.
9. EXPORTARBIM y reimportar: se conservan identificadores; las propuestas quedan
   confirmadas por la definición nueva. La segunda reimportación idéntica es nula.

## Código compartido y límites

`scripts/bundle_roundtrip.py` copia literalmente la geometría del plugin a
`ingetrazo_ext/arq_shared/`. MANIFEST.json y una prueba comprueban cada copia.
El paquete no ejecuta `arquitectura/__init__.py` ni importa el núcleo de IngeCAD.
La interacción CabinetTool se separa en cabinet_tools.py; su geometría permanece
única en cabinets.py. No se añade dependencia externa a la extensión.

El fingerprint cubre registros reconciliados, niveles, catálogo e identidad del
DXF, no la fecha del archivo, la ruta local ni sus caras trianguladas. Los
contratos con registros duplicados/no reconciliados o catálogo dañado conservan
la exportación previa con omisiones, pero no reciben una definición editable.

No se sincronizan movimientos, escalados ni edición libre de caras realizados
con otras herramientas de IngeTrazo. No se resuelven encuentros/recintos allí.
La selección se observa cada 250 ms usando API pública; T-16 propone una señal.
Persisten las limitaciones del IFC oficial registradas en T-02/T-03/T-05/T-15.

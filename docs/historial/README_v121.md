# Arquitectura 1.2.1 — revisión experimental

Novedad: `PROPIEDADESARQ` permite acceder a la ficha de propiedades de un muro desde su contorno regenerado, y editar pilares. La herramienta solicita seleccionar con un clic un muro, un segmento de su contorno visible o un pilar. En límites compartidos informa de ambigüedad.

IMPORTANTE: IngeCAD no admite aún grupos BIM de extensiones en su panel Propiedades sin ampliar su API. El comando abre fichas BIM nativas de Qt, no añade grupos al panel.

Para regenerar los contornos y sus relaciones con los muros originales, utilice `UNIONESARQ`. El fichero IGZ sigue siendo experimental y no está validado extremo a extremo.

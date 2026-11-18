# T-16 — Notificación pública de selección para paneles de extensiones

18-11-2026. Propuesta local, **sin enviar**. El encargo R21 la denominaba T-15;
la base v1.28 ya utiliza T-15 para IfcFurniture. Se conserva esa referencia y
se asigna T-16 a esta propuesta, sin alterar el historial.

## API comprobada

Fuentes oficiales intactas: IngeTrazo 0.6.1 (`ffc7187`) y 0.6.2 (`bebde88`).
`views/extension_api.py`: `add_panel`, `scene`, `viewport`, `document_data`,
`on_document_changed` y `add_menu_action` permiten el panel y los comandos
reversibles de R21. No hace falta una API nueva para regenerar geometría.
No existe un método público `on_selection_changed`; el panel debe observar
`scene.selection`. R21 emplea un QTimer de 250 ms, con padre QWidget y una
firma de selección/documento/versión para evitar reconstruirlo continuamente.
Se destruye con el panel y resuelve el documento activo en cada consulta.

## Propuesta

`ExtensionApp.on_selection_changed(callback)` con la selección del documento
activo, también al vaciarla, cambiar de pestaña, cerrar documento y deshacer.
La extensión no debería conectar señales privadas ni tener que sondear.
Se recomienda igualmente una operación pública para ejecutar un Command
sobre geometría + datos de extensión y notificar el cambio en un solo paso.
En las versiones probadas se utiliza `app.viewport.history.execute`.

## Antecedentes revisados, solo lectura

Búsqueda acotada de incidencias de ingelibre/ingetrazo:
`extension selection properties` (18-11-2026): #1222 trata los datos IFC,
#87 la estructura de proyecto y #470 reúne mejoras generales de interfaz.
El registro local ya sigue #1333 sobre ganchos de extensión. Estos antecedentes
están relacionados, pero no acreditan que exista la suscripción de selección
necesaria en las dos versiones examinadas. No se afirma una búsqueda exhaustiva.
No se han abierto incidencias, PR ni enviado comentarios o mensajes.

# C-08 — controles de plugins junto a la capa activa

Estado: propuesta local solicitada por el propietario, 16-11-2026. **No enviada.**
No contiene un parche del anfitrión ni autoriza modificarlo o contactar con sus desarrolladores.

## Necesidad y solución actual

Arquitectura necesita mostrar el nivel activo y sus estados de capa junto a la
capa activa, en las herramientas habituales. IngeCAD 0.8 expone `ctx.toolbar()`:
se puede añadir un QWidget al QToolBar propio del plugin. Se usa esa vía pública;
el selector muestra también la capa activa leída del documento, sin duplicar su
estado ni inventar otro sistema de encendido, congelación o bloqueo.
IngeCAD 0.7 carece de ese acceso: conserva NIVELES y NIVELES ESTADO, sin excepciones
por ausencia del control. El control no se instala si el usuario oculta la barra. Un monitor Qt con referencia débil al host detecta la aparición de la barra mediante su handle público; no guarda estados de capa. El cierre del host y la recarga sustituyen o retiran ese monitor.

No hay en el contrato público examinado un punto de inserción de controles dentro
de la barra de capas o de la barra de estado. No se accede a sus atributos privados.

## Revisión de antecedentes

Fuentes examinadas: IngeCAD 0.8, commit 32a15cbd573b62f7c0d31aa6329d82fad55fb950,
y 0.7, 50e524dd4f3b2ece1eca427d4de4a00ba257f545; core/plugins.py,
core/layers.py y docs/plugins.md. La API 0.8 ofrece ToolbarSpec, toolbar(),
on_document_open y on_regen_done, además de las filas de propiedades.
LayerPropertyCommand ya resuelve on/frozen/locked: C-08 no solicita otro motor de capas.

Revisado REGISTRO_UPSTREAM: C-01 a C-06 tratan reactores, grupos, doble clic,
teclas, ortogonalidad y SIMETRÍA/XDATA; no satisfacen esta necesidad.
Consultas de solo lectura en ingelibre/ingecad: «plugin toolbar», «plugin status bar»
y «layer plugin». La primera devuelve #44 y #48; las otras no devuelven resultados.
#44 pide una guía de plugins más completa y #48 trata el tema visual/decoraciones,
no una API de inserción en esas barras. No se ha encontrado una propuesta equivalente
en esta revisión acotada; no es una afirmación sobre toda la historia del repositorio.

- https://github.com/ingelibre/ingecad/issues/44
- https://github.com/ingelibre/ingecad/issues/48

## Contrato propuesto (para discusión, no implementado en IngeCAD)

Un método público que registre un control por plugin e ID estable, indicando
zona (`layers` o `status`) y ancla (`current_layer`, antes/después). El anfitrión
crearía y destruiría el QWidget, gestionaría recarga/desactivación, traducción,
visibilidad, orden y limpieza de conexiones. Devolvería un handle revocable.
Debe avisar del documento/capa activos y de la reconstrucción de la barra, para
refrescar el control sin temporizador ni referencias privadas a la ventana.

Los plugins antiguos siguen funcionando y los que no soporten la nueva API usan
su barra propia. Si se incorpora, Arquitectura trasladará el mismo selector a
la nueva ubicación; sus comandos y las capas DXF seguirán siendo la fuente del estado.

Aceptación propuesta: dos plugins con controles independientes; cambiar documento,
recargar/desactivar el plugin, ocultar/mostrar barras, Deshacer/Rehacer de estados,
traducción y barra estrecha. Ningún widget huérfano ni modificación del núcleo por el plugin.

# Arquitectura 1.1.3 — reparación del acceso al documento

**Causa confirmada por las capturas del usuario:** `ToolContext` no tiene atributo `document`. Las herramientas utilizan `ctx.services.window.document` y los comandos normales `ctx.document`. Se añade el módulo `compat.py` para resolver ambos contratos y se actualizan la creación de capas y los helpers de dibujo.

## Prueba recomendada

1. Desactivar la versión anterior en PLUGINS, instalar este ZIP, reactivar y reiniciar IngeCAD si el módulo sigue en memoria.
2. `ARQDIAG`: comprobar `Arquitectura 1.1.3`.
3. `MURO`: aceptar la ficha BIM, hacer clic en (0,0) y en (5,0) mediante el ratón. Debe aparecer un muro de 5 m y quedar el comando preparado para el siguiente tramo.
4. `PILAR`: clicar el punto central sin introducir `rect` (ya es el valor inicial). Debe dibujar un pilar de 0,30 × 0,30 m. Para cambiar dimensiones: `rect`, ancho, alto, centro.
5. Guardar DXF y reabrir; comprobar las entidades y la reversión con Deshacer.

**Limitaciones:** validación automatizada sobre fakes de la interfaz, no ejecución GUI Windows; IGZ–IFC no comprobado. No se modifica el motor ni se alteran las funciones BIM todavía incompletas.

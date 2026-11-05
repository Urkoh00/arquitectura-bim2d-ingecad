> **Actualización v1.5.1:** véase `README_v151.md`; XDATA compatible con límite 255 bytes, diagnóstico de divergencias CAD/BIM y corrección del giro de pilares. IGZ y uniones oblicuas siguen experimentales.

# Arquitectura para IngeCAD 1.2.0 — experimental

Plugin 2D con datos BIM en XDATA. Funciones en esta revisión:

- `MURO`: parámetros geométricos y BIM; dibujo continuo; previsualización temporal del contorno; regeneración automática de límites visibles de muros.
- `PILAR`: diálogo BIM nativo (rectangular/circular), dibujo continuo, previsualización y recorte de las aristas del muro que quedan detrás de su huella en planta.
- `UNIONESARQ`: recalcular límites de muro sobre los datos XDATA ya presentes.
- `DIAGNOSTICOARQ` / `ARQDIAG`: consultas y diagnóstico.
- `EXPORTARIGZ`: incluye muros y pilares a nivel de especificación. Requiere IngeTrazo configurado y no está validado de extremo a extremo.

Los muros se conservan como entidades originales XDATA en `ARQ-MUROS3D`, capa apagada; la representación de planta reconstruida se dibuja en `ARQ-MUROS`. Los pilares están en `ARQ-PILAres`. No se deben modificar esas capas manualmente mientras se comprueba este prototipo.

**Importante**: esta unión resuelve la representación plana, no la unión 3D de volúmenes. `EDITARARQ` no resuelve aún la selección de un muro a partir de los segmentos regenerados: pendiente de un enlace entre contorno visible e identificador del elemento. Para probar, utilice un dibujo nuevo.

Versión de referencia: IngeCAD 2D + IngeTrazo IGZ/IFC. Licencia GPL-3.0-or-later, compatible con las fuentes de código libre originales del plugin.

# Arquitectura 1.3.2 — Encuentros exteriores ortogonales (EXPERIMENTAL)

Corrección puntual de encuentros L y T cuyos ejes se cruzan exactamente (sin inventar proximidades). Para cada extremo, la representación del muro se prolonga hasta la cara alejada del muro anfitrión, sin cambiar la polilínea de referencia, XDATA ni el identificador BIM. Funciona con muros de diferente espesor y referencias eje/izquierda/derecha.

Los encuentros oblicuos y las uniones con ejes cercanos pero no coincidentes no quedan resueltos en esta entrega. Se mantienen capas derivadas ARQ-MUROS y ejes fuente ARQ-MUROS3D: sólo debe mostrarse normalmente ARQ-MUROS. Ninguna geometría IGZ/IFC ha sido validada aquí.

Pruebas headless: rectángulo real reproducido desde 34.dxf (4 esquinas), T y L con espesores diferentes. Sin prueba de ejecución en Windows.

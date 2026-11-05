# Arquitectura 1.4.1 — corrección de encuentros de extremos (experimental)

Corrige los encuentros ortogonales cuando un extremo se encuentra en la cara del muro perpendicular en vez de coincidir con su eje (caso 35.dxf, desfase 0,15 m). La prolongación se calcula hasta la cara remota del muro anfitrión, respetando espesores y referencia izquierda/derecha/eje.

No cambia ejes BIM, identificadores, parámetros ni el puente IGZ experimental de 1.4.0. No modifica las coordenadas guardadas en el DXF; solo el contorno regenerado.

Validar en copia de 35.dxf: instalar, verificar ARQDIAG 1.4.1 y ejecutar UNIONESARQ. La proximidad se admite solo cuando el extremo cae dentro del espesor del muro perpendicular. Los encuentros oblicuos, la conexión de extremos más alejados y la exportación real a IGZ siguen pendientes de validación.

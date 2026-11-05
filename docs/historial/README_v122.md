# Arquitectura 1.2.2 (experimental)
Mejoras: creación/edición de muros y pilares + regeneración de contornos en una sola entrada de Deshacer; conservación de procedencia BIM de segmentos regenerados al deshacer.

Instalación: desactivar versión anterior, instalar esta carpeta `arquitectura` mediante el gestor de extensiones, reiniciar IngeCAD. `ARQDIAG` debe indicar 1.2.2.

Prueba: MURO (dos clics), DESHACER, REHACER; segundo muro en T, DESHACER; PILAR sobre muro, DESHACER; guardar y abrir DXF; PROPIEDADESARQ sobre contorno exterior.

Pendientes: integración en panel Propiedades del núcleo (API no pública), geometría 3D de encuentros, IGZ/IFC validado, carpinterías con recortes de muro.

Véase `INFORME_v1.2.2.md` en el paquete de pruebas.

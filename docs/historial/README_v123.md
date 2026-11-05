# Arquitectura para IngeCAD 1.2.3 (experimental)

Revisión de seguridad de dibujo, sin nuevas geometrías ni modificación del núcleo de IngeCAD.

## Mejoras
- Operación compuesta con restitución de los pasos completados si falla la generación de contornos.
- Reconstrucción del contorno con restauración independiente de datos XDATA si falla su escritura.
- Nuevo comando `ARQVALIDAR`: auditoría de identificadores BIM, entidades, contornos, huecos huérfanos y unidades del DXF, **solo lectura**.
- Se mantienen `MURO`, `PILAR`, `PROPIEDADESARQ`, `UNIONESARQ` y la interfaz BIM de la versión 1.2.2.

## Prueba manual en Windows
1. Desactivar versión antigua, instalar nuevo ZIP, reiniciar, ejecutar `ARQDIAG`: debe decir 1.2.3.
2. Sobre un DXF nuevo, ejecutar `MURO`, aceptar ficha; seleccionar dos puntos. Confirmar contorno permanente y previsualización.
3. Añadir muro perpendicular; comprobar encuentro, Deshacer una vez, Rehacer una vez.
4. Ejecutar `PILAR`, insertar pilar en contacto con muro, verificar contorno y propiedades mediante `PROPIEDADESARQ`.
5. Ejecutar `ARQVALIDAR`, guardar DXF, reabrir y repetir `ARQVALIDAR`.
6. Si hay incidencia, adjuntar **texto de comandos completo**, archivo DXF de prueba y número de versión de IngeCAD.

## Advertencias
- Trabajar sobre una copia de prueba. No validado en aplicación Windows real.
- Las unidades de este prototipo se presuponen en **metros**: DXF `$INSUNITS=6`. Si no está definida esa variable, `ARQVALIDAR` lo indica. No cambia automáticamente el DXF.
- Los encuentros siguen siendo **2D**, no unión BRep 3D.
- `group.ext` en IGZ no equivale a exportar Psets ni relaciones IFC.
- El panel nativo de Propiedades no admite actualmente proveedores externos documentados; se mantiene `PROPIEDADESARQ`.
- No se amplían las carpinterías ni mediciones.

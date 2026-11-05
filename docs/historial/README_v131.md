# Arquitectura v1.3.1 — corrección del anclaje de ORTO

Se corrige `MuroTool.last_point`: al marcar el primer punto y cada extremo de un tramo se actualiza la referencia que usa el controlador de IngeCAD para ORTO, POLAR y seguimiento. Al iniciar un nuevo tramo independiente se elimina el ancla anterior. Se conserva la geometría BIM y el motor de encuentros de v1.3.0; **no** se declara corregida la unión automática de muros.

En IngeCAD: REJILLA (F7) controla la visualización; FORZC / SNAP (F9) el ajuste a la cuadrícula. Comprobar ambos con LINE y MURO.

Caso de ensayo `33.dxf`: la última arista de eje finaliza en X=3.65 mientras la primera comienza en X=3.50; la separación es de 0.15 m. La geometría no debe modificarse arbitrariamente por el plugin. La capa ARQ-MUROS3D almacena los ejes BIM y ARQ-MUROS la representación regenerable; activarlas ambas muestra líneas adicionales intencionadamente.

No se ha validado esta revisión en IngeCAD Windows; la corrección se limita al anclaje de entrada y no modifica el núcleo CAD.

# Arquitectura para IngeCAD v1.5.1 — revisión de integridad BIM (experimental)

Fecha: 5-11-2026. Base: v1.5.0. Distribución de ensayo; no sustituye la versión estable de referencia del usuario.

## Cambios incorporados

1. `PROPIEDADESARQ`: `EditColumnCommand` admite `rotation` para pilares `hex` y `oct`, con deshacer/rehacer.
2. `architectural._xdata`: JSON ASCII (escape Unicode) repartido en grupos DXF 1000 de hasta 200 bytes; cada grupo respeta el límite de 255 bytes. `metadata` concatena los registros para leerlos y conserva compatibilidad con JSON legado de un único grupo.
3. `ARQVALIDAR`: avisa de registros XDATA ilegibles o de >255 bytes, ejes de muro (LWPOLYLINE ABIERTA de dos vértices) que no coinciden con `a/b` almacenados y centros de pilares incoherentes con la sección gráfica. Conserva la detección de IDs duplicados y huecos huérfanos.
4. `ARQVALIDAR` ya no califica todas las polilíneas abiertas de muros actuales como muros antiguos: el aviso de geometría duplicada se limita a polilíneas CERRADAS.

## Lo que NO cambia

- Ninguna corrección automática de XDATA histórico ni IDs duplicados. Los registros antiguos se siguen leyendo; para normalizarlos debe existir una operación explícita y reversible de migración (pendiente).
- Ningún cambio al algoritmo de uniones en L/T/X ni a la exportación IGZ, que siguen siendo experimentales. No se ha resuelto todavía la diferencia entre la huella de unión 2D y los sólidos 3D, ni los ingletes oblicuos exactos, ni la conversión de propiedades BIM al IFC final.
- No se han probado los comandos en IngeCAD 0.7.0 para Windows ni la lectura IGZ con IngeTrazo real.

## Pruebas ejecutadas

`python test_v151.py` con ezdxf 1.4.4: 9/9 pruebas superadas, incluidas lectura DXF antigua y redondeo, advertencias, duplicados y undo del giro.
`python -m compileall`: correcto.
`ARQVALIDAR` aplicado mediante código a `34.dxf` y `36.dxf`: identifica registros XDATA de longitud excesiva y conserva las cuentas de entidades (34: cuatro muros y seis pilares; 36: ocho muros).

## Instalación y ensayos recomendados

1. Crear copia de seguridad de todos los DXF y de la carpeta del plugin 1.5.0.
2. Cerrar IngeCAD. Sustituir la carpeta `arquitectura` por la de este ZIP y reiniciar.
3. Ejecutar `ARQDIAG` (debe indicar 1.5.1), después `ARQVALIDAR` en una copia de `36.dxf`.
4. Dibujar pilar hexagonal/octogonal; editar giro con `PROPIEDADESARQ`; comprobar DESHACER/REHACER y guardar/reabrir.
5. Crear un muro y un pilar nuevos; guardar/reabrir el DXF y ejecutar `ARQVALIDAR`.
6. Repetir `UNIONESARQ` en una copia de `36.dxf`; comprobar que los encuentros siguen siendo como en v1.4.2.
7. Probar MOVE, ROTATE, COPY y MIRROR en copias: `ARQVALIDAR` advierte si geometría y metadatos se separan. No exportar IGZ de modelos con estas discrepancias.

## Directriz de ingeniería

La geometría CAD y el registro BIM son dos fuentes potencialmente incoherentes al aplicar comandos genéricos. Esta versión solo DIAGNOSTICA; no sincroniza ni repara. No hay garantías de fidelidad IGZ/IFC y no debe usarse para mediciones contractuales.

# Arquitectura v1.2.4 — modelo de muros sin geometría fuente duplicada

- Los nuevos muros se guardan como registros POINT con XDATA ARQINGECAD en la capa auxiliar `ARQ-MUROS3D`; no existe una segunda huella poligonal de muro en esa capa.
- Las líneas visibles de `ARQ-MUROS` se calculan a partir de los parámetros BIM, y conservan `wall_ids` en XDATA.
- El comando `ARQMIGRAR` transforma los muros antiguos (polilíneas BIM) en registros POINT; es deshacible junto con la regeneración. **Ejecutarlo únicamente sobre una copia del DXF.**
- `ARQVALIDAR` avisa de las entidades antiguas, y `UNIONESARQ` regenera los contornos.
- El panel nativo todavía identifica las líneas como LINE; consultar el objeto BIM con `PROPIEDADESARQ`.
- Esta revisión no aporta IFC validado ni corrige automáticamente el dibujo de carpinterías.
- Requiere pruebas de integración reales en IngeCAD Windows.

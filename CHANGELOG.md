# Arquitectura para IngeCAD v1.6.0-dev — motor de nodos y huella única 2D/3D (EXPERIMENTAL)

Fecha: 5-11-2026. Base: v1.5.1. Distribución de ensayo: no sustituye la versión de trabajo.

## Qué cambia

1. **`geom/` (nuevo, Python puro, sin dependencias):**
   - `geom/junctions.py`: motor de encuentros por nodos. Esquinas L con inglete exacto
     a cualquier ángulo y con espesores distintos, uniones T (el muro pasante conserva su
     huella), cruces X, nodos de 3 o más muros, escalones colineales, referencias de eje
     o de cara, y esquinas dibujadas hasta la cara (caso `35.dxf`). Cada muro recibe UNA
     huella propia; las huellas no se solapan entre sí ni con los pilares.
   - `geom/solids.py`: sólido 3D estanco de cada muro a partir de esa misma huella, con
     puertas y ventanas como huecos reales (sin caras interiores).
   - `geom/polygon.py`: núcleo de polígonos (recortes convexos y pegado de piezas).
2. **`UNIONESARQ`** usa el motor nuevo dentro del mismo comando con deshacer/rehacer. Cada
   línea del contorno conserva el ID del muro al que pertenece.
3. **`EXPORTARBIM` (nuevo):** escribe un `.arqbim` (JSON, contrato versionado) con la geometría
   final, los GUID IFC estables, nivel, material, tipo, Psets, cantidades y huecos. Ya no
   hace falta configurar fuentes ni un Python de IngeTrazo.
4. **Extensión para IngeTrazo** (`ingetrazo_ext/arquitectura_bim.py`, en el ZIP): abre los
   `.arqbim` desde IngeTrazo instalado o portable y los inserta como grupos BIM etiquetados.
5. **Eje CAD como fuente de verdad:** la exportación toma el eje de la polilínea visible; si el
   XDATA `a/b` quedó desfasado (MOVE/ROTATE/MIRROR genéricos) lo avisa. Un ID duplicado
   (COPY) bloquea la exportación con un mensaje claro.
6. **`reactor.py`:** si IngeCAD incorpora el gancho de reactores propuesto (parche en
   `upstream/ingecad/`), tras MOVE/COPY/MIRROR/ROTATE el plugin reasigna ID a las copias,
   sincroniza el XDATA y regenera el contorno **en el mismo paso de deshacer**. En un IngeCAD
   sin el gancho, el plugin funciona como antes.
7. `EXPORTARIGZ`/`CONFIGIGZ` siguen disponibles como «puente antiguo».

## Reglas del motor (explícitas)

- Tolerancia de mismo punto: 1 mm. Nada se une por simple proximidad.
- Esquina dibujada hasta la cara: se une si cada extremo cae dentro de la franja del otro
  muro, cerca de su extremo.
- T: el extremo dentro de la franja de otro muro (lejos de sus extremos) se prolonga hasta la
  cara opuesta y se recorta contra el pasante.
- Ángulo mínimo entre muros: 5°. Por debajo se tratan como paralelos.
- Inglete máximo: 6 × espesor. Por encima, corte recto.
- Propiedad de solapes: pilar > muro. En una T gana el pasante. En los demás casos decide
  `join_priority` (XDATA, opcional), luego el espesor y luego el orden de dibujo.

## Pruebas (carpeta `tests/` del ZIP)

| Archivo | Qué comprueba |
|---|---|
| `test_junctions.py` | 66 casos L/T/X/nodos/colineal/caras/proximidad/pilares, contrastados con shapely |
| `test_dxf_regression.py` | `34.dxf`, `35.dxf`, `36.dxf`: solape 0, geometría ideal y 8 líneas por recinto (16 en 35/36) |
| `test_solids.py` | Sólidos estancos; volumen = área en planta × altura − huecos |
| `test_ingecad_integration.py` | Plugin cargado con el **cargador real** de IngeCAD, `Document`/`History` reales, deshacer/rehacer, COPY/MOVE/MIRROR |

Para ejecutarlas hacen falta las fuentes de IngeCAD en `PYTHONPATH` y `pytest`, `ezdxf` y
`shapely` (shapely solo se usa en las pruebas).

## v1.6.1-dev (5-11-2026, tras la primera prueba en Windows)

- `UNIONESARQ` no se veía hasta regenerar la pantalla: el comando ahora pide la regeneración
  a IngeCAD (`needs_regen`).
- `EXPORTARBIM` (y el antiguo `EXPORTARIGZ`) fallaban al abrir el diálogo de guardar: se pasaba
  como ventana padre el método `window` de Qt en lugar de la ventana. Nuevo `compat.dialog_parent`.
- Regresión: el contorno de `36.dxf` coincide línea a línea con `36_contornos_v1.4.2.dxf` (16 líneas).

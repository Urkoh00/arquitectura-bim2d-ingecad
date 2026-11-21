# Adenda 2 al encargo R28 — base futura de B2

Claude, 21-11-2026. Texto comunicado por el propietario y leído durante el cierre
de R28-A. B2 queda fuera de esta entrega e irá en un encargo posterior.

En el catálogo de extensiones de IngeTrazo, Claude identifica dos esqueletos
rectos ponderados en Python puro, con licencia **GPL-3.0-or-later**:

- `roof_tile_tool.py`, de «Tejados y tejas»,
  [PESI3D/ingetrazo-roof-tiles](https://github.com/PESI3D/ingetrazo-roof-tiles), v1.3.
- `roof_any.py`, de ArchXQ IT Lite,
  [equipexq/archxq-it-lite](https://github.com/equipexq/archxq-it-lite), v0.13.0,
  adaptado del anterior con crédito.

Según esa revisión, ya resuelven pendientes por lado con velocidad `cot α`
(`1/tan α`, equivalente a `1/pendiente`) y piñones con velocidad cero.
Esta base sustituye a bpypolyskel para B2: mantiene la licencia «o posterior» y
ya admite pesos. No se propone volver a añadir una capacidad que ya tienen.

Antes de proponer código de B2:

1. Pasar los ocho casos aceptados de B0.
2. Comprobar patios y arranques a distinta cota. «Tejados y tejas» recibe una
   lista de polígonos, pero falta confirmar que represente patios; `roof_any.py`
   solo tiene contorno exterior. No se declara soporte de patios por el mero
   hecho de admitir varios polígonos.
3. Anotar el copyright y la procedencia exactos en la cabecera del módulo y en
   `docs/GUIA_DEL_CODIGO.md`, conservando licencia y créditos.

Las mejoras se ofrecerán a sus autores; no se mantendrá una copia divergente sin
avisar. La estimación de B2 debe rehacerse sobre estas fuentes y sus pruebas.
La comunicación y cualquier incorporación corresponden a ese encargo futuro,
con el protocolo del proyecto; no se envía ninguna comunicación desde R28-A.

En R28 solo se registra esta decisión. No se descargan ni incorporan estos
módulos, no se ejecutan como si ya hubieran superado B0 y no se inicia B1/B2.
B1 se encarga en R29 junto con las mejoras de LINEASAMURO, después de integrar R28-A.

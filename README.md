# Arquitectura BIM-2D para IngeCAD

Plugin de arquitectura para [IngeCAD](https://github.com/ingelibre/ingecad): dibujo de
plantas en 2D, con la agilidad de un CAD de arquitectura, en el que cada muro, pilar, puerta o
ventana es desde el principio un **objeto BIM** (identidad persistente, clase IFC, parámetros 3D,
propiedades y relaciones). El modelo se transfiere a
[IngeTrazo](https://github.com/ingelibre/ingetrazo), que lo representa en 3D y lo exporta a IFC.

```
IngeCAD + plugin Arquitectura  ──.arqbim──▶  IngeTrazo (extensión)  ──▶  IGZ  ──▶  IFC
       (planta 2D BIM)                          (modelo 3D)
```

**Estado: experimental (v1.22.0-dev).** No usar todavía en proyectos reales.

**Manual de uso:** [`docs/MANUAL.md`](docs/MANUAL.md) (también dentro del ZIP), actualizado en cada versión.

> Este repositorio es solo el plugin. No es un fork de IngeCAD ni de IngeTrazo, ni tiene
> relación con los visores BIM del mismo autor
> ([visor-bim-desktop](https://github.com/Urkoh00/visor-bim-desktop),
> [visor-unificado-bim](https://github.com/Urkoh00/visor-unificado-bim)).

## Principio

La planta 2D, el sólido 3D y el IFC salen de **una sola definición**: el plugin calcula una vez
la huella final de cada elemento (encuentros L/T/X resueltos, sin solapes) y de ella derivan el
contorno en planta, el sólido estanco y las cantidades. IngeTrazo no recalcula geometría.

## Qué hay

| Carpeta | Contenido |
|---|---|
| `arquitectura/` | El plugin de IngeCAD (comandos `MURO`, `PILAR`, `CARPINTERIA`, `RECINTO`, `UNIONESARQ`, `EXPORTARBIM`, `ARQVALIDAR`…) |
| `arquitectura/geom/` | Motor geométrico en Python puro: encuentros por nodos, polígonos, sólidos |
| `ingetrazo_ext/` | Extensión de IngeTrazo que abre los `.arqbim` como grupos BIM etiquetados |
| `tests/` | Pruebas automáticas (geometría contrastada con shapely, DXF reales, cargador real de IngeCAD) |
| `docs/` | Diseño de espacios (`DISENO_ESPACIOS.md`), historial de versiones |
| `docs/propuestas_upstream/` | Parches **propuestos** a IngeCAD e IngeTrazo (no aplicados; se discuten con su desarrollador) |

## Instalación en IngeCAD

1. Descargue el ZIP de la última versión (o genérelo con `python scripts/empaquetar.py`).
2. Copie la carpeta `arquitectura` en la carpeta de plugins de IngeCAD y reinicie.
3. Para IngeTrazo: copie `ingetrazo_ext/arquitectura_bim.py` en su carpeta de extensiones;
   aparecerá *Importar arquitectura IngeCAD (.arqbim)…*.

## Pruebas

```bash
git clone https://github.com/ingelibre/ingecad ../ingecad     # o defina INGECAD_SRC
pip install -r ../ingecad/requirements.txt -r requirements-dev.txt
python -m pytest -q
```

GitHub Actions las ejecuta en cada envío de código, en Linux y en Windows, contra la última
versión publicada de IngeCAD y contra su rama principal; el resultado de cada ejecución es el que
cuenta (las cifras no se copian aquí porque cambian con cada versión). Con un IngeCAD anterior a la
0.8, unas pocas pruebas se omiten: las que necesitan sus reactores oficiales. Son pruebas sin
pantalla: no sustituyen la prueba manual en el IngeCAD instalado.

## Colaboración con IngeCAD e IngeTrazo

Antes de implementar algo se busca si IngeCAD o IngeTrazo ya lo resuelven. Cuando falta algo o
se detecta un defecto, se documenta y se propone con humildad a su desarrollador mediante
incidencias en sus repositorios; este plugin se adapta a lo que él decida.

## Licencia

GPL-3.0-or-later, la misma que IngeCAD e IngeTrazo (el plugin importa el núcleo de IngeCAD).
Véase `LICENSE`.

Parte del código se ha desarrollado con ayuda de un asistente de IA (Claude, de Anthropic),
revisado y probado por el autor.

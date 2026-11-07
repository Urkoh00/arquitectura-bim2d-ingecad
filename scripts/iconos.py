# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate the plugin's toolbar/menu icons (SVG, 24 × 24).

Style of IngeCAD's own painted icons (views/icons.py): thin line art on a
transparent background for its dark interface, near-white ink (#f0f4f6,
1,4 px, round caps) for what exists, light steel blue (#8fb8d8) for what
the command makes or changes, and the eraser's warm yellow (#e3c26e) only
for what a command removes. The subjects are drawn as an architect's plan
shows them — a wall is two parallel faces, a door its leaf and swing, a
column a crossed square — so that the icon says what the command does.

Run:  python scripts/iconos.py   (writes arquitectura/icons/*.svg)
"""
from pathlib import Path

INK, ACC, RUB = "#f0f4f6", "#8fb8d8", "#e3c26e"
OUT = Path(__file__).resolve().parents[1] / "arquitectura" / "icons"


def svg(*items):
    body = "".join(items)
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">'
            f'<g fill="none" stroke-linecap="round" stroke-linejoin="round">{body}</g></svg>')


def path(d, c=INK, w=1.4, dash=None, fill="none"):
    extra = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<path d="{d}" stroke="{c}" stroke-width="{w}" fill="{fill}"{extra}/>'


def dot(x, y, r=1.6, c=ACC):
    return f'<circle cx="{x}" cy="{y}" r="{r}" fill="{c}" stroke="none"/>'


def arrow(x0, y0, x1, y1, c=ACC):
    """A shaft with a solid head at (x1, y1)."""
    import math
    a = math.atan2(y1 - y0, x1 - x0)
    s = 3.2
    p1 = (x1 - s * math.cos(a - 0.5), y1 - s * math.sin(a - 0.5))
    p2 = (x1 - s * math.cos(a + 0.5), y1 - s * math.sin(a + 0.5))
    return (path(f"M{x0} {y0} L{x1} {y1}", c, 1.3)
            + f'<path d="M{x1:.2f} {y1:.2f} L{p1[0]:.2f} {p1[1]:.2f} L{p2[0]:.2f} {p2[1]:.2f} Z" '
              f'fill="{c}" stroke="{c}" stroke-width="0.8"/>')


def hwall(x0, x1, y, t=4, c=INK, ends=True):
    """A horizontal wall in plan: two faces, closed at its ends."""
    d = f"M{x0} {y} H{x1} M{x0} {y + t} H{x1}"
    if ends:
        d += f" M{x0} {y} V{y + t} M{x1} {y} V{y + t}"
    return path(d, c)


ICONS = {
    # MURO: an L of wall drawn by its faces, the pen at its end
    "muro": svg(path("M3 21 V3 H21 M7 21 V7 H21 M3 21 H7 M21 3 V7"), dot(21, 5)),
    # MUROCURVO: a curved wall by its two concentric faces, the pen at its end
    "murocurvo": svg(path("M3 21 A18 18 0 0 1 21 3 M7 21 A14 14 0 0 1 21 7 M3 21 H7 M21 3 V7"),
                     dot(21, 5), dot(7.8, 9.3, 1.3, ACC)),
    # CURVAMURO: a straight wall bent through a point
    "curvamuro": svg(hwall(2, 22, 17, t=3.5), path("M2 13 Q12 1 22 13 M2 9 Q12 -3 22 9 M2 9 V13 M22 9 V13", ACC, 1.3),
                     dot(12, 5, 1.6, ACC)),
    # MUROPARALELO: an existing wall and the new one parallel to its face
    "muroparalelo": svg(hwall(3, 21, 3), hwall(3, 21, 16, c=ACC), arrow(12, 8.5, 12, 14.5)),
    # ESTIRAMURO: a wall run up to a line
    "estiramuro": svg(path("M20 3 V21", ACC), hwall(3, 12, 10), path("M12 10 H18 M12 14 H18", ACC, dash="2 2"),
                      arrow(13, 12, 18.5, 12)),
    # PIVOTAMURO: a wall turning round its other end
    "pivotamuro": svg(hwall(3, 18, 16), path("M3 16 L13.7 7 L16.3 10.1 L5.6 19.1 Z", ACC),
                      dot(3, 18, 1.8, INK), path("M20.5 15 A10 10 0 0 0 19 10", ACC, 1.3),
                      arrow(20.2, 13, 19.2, 10.2)),
    # DIVIDEMURO: a stretch divided by equal partitions
    "dividemuro": svg(hwall(2, 22, 3), path("M8 7 V21 M10 7 V21 M14 7 V21 M16 7 V21", ACC)),
    # BORRATRAMO: the stretch between two crossings removed
    "borratramo": svg(path("M7 3 V21 M10 3 V21 M14 3 V21 M17 3 V21"),
                      path("M2 10 H7 M2 14 H7 M17 10 H22 M17 14 H22"),
                      path("M10 10 H14 M10 14 H14", RUB, 1.6, dash="1.5 1.5")),
    # PARTEMURO: a wall opened in two
    "partemuro": svg(hwall(2, 9, 10), hwall(15, 22, 10), arrow(11, 12, 6.5, 12), arrow(13, 12, 17.5, 12)),
    # UNIRMURO: two aligned walls made one
    "unirmuro": svg(hwall(2, 9, 10), hwall(15, 22, 10), path("M9 10 H15 M9 14 H15", ACC, dash="2 1.5"),
                    arrow(5, 6, 10.5, 6), arrow(19, 6, 13.5, 6)),
    # LINEASAMURO: loose lines become a wall
    "lineasamuro": svg(path("M2 6 H9 M2 10 H9 M2 15 H9 M2 19 H9", INK, 1.1),
                       path("M15 6 H22 M15 10 H22 M15 6 V10 M22 6 V10 M15 15 H22 M15 19 H22 M15 15 V19 M22 15 V19", ACC),
                       arrow(10, 12.5, 14, 12.5, INK)),
    # PILAR: a column in plan, crossed, at a wall's corner
    "pilar": svg(path("M3 21 V9 M7 21 V13 M9 3 H21 M13 7 H21"),
                 path("M3 3 H13 V13 H3 Z M3 3 L13 13 M13 3 L3 13", ACC)),
    # PUERTA: a wall with a door: its leaf and swing
    "puerta": svg(hwall(2, 6, 16, ends=False), hwall(18, 22, 16, ends=False), path("M6 16 V20 M18 16 V20"),
                  path("M6 16 V4", ACC), path("M6 4 A12 12 0 0 1 18 16", ACC, 1.2)),
    # VENTANA: a wall with a window: its frame and glass
    "ventana": svg(hwall(2, 6, 10, ends=False), hwall(18, 22, 10, ends=False), path("M6 10 V14 M18 10 V14"),
                   path("M6 11 H18 M6 13 H18 M12 11 V13", ACC), path("M5 15.6 H19", INK, 1.0)),
    # HUECO: a plain opening, the lintel above it dashed
    "hueco": svg(hwall(2, 7, 10, ends=False), hwall(17, 22, 10, ends=False), path("M7 10 V14 M17 10 V14"),
                 path("M7 10 H17 M7 14 H17", ACC, 1.1, dash="1.6 1.6")),
    # CARPINTERIA: door and window in one wall
    "carpinteria": svg(path("M1.5 15 H3 M1.5 20 H3 M11 15 H13 M11 20 H13 M21 15 H22.5 M21 20 H22.5"),
                       path("M3 15 V20 M11 15 V20 M13 15 V20 M21 15 V20"),
                       path("M3 15 V7", ACC), path("M3 7 A8 8 0 0 1 11 15", ACC, 1.2),
                       path("M13 16.6 H21 M13 18.4 H21 M17 16.6 V18.4", ACC)),
    # RECINTO: a room picked inside its walls
    "recinto": svg(path("M2 2 H22 V22 H2 Z M5 5 H19 V19 H5 Z"),
                   path("M7 7 H17 V17 H7 Z", ACC, 1.1, dash="1.8 1.6"), dot(12, 12, 2.0)),
    # SUPERFICIES: a schedule of areas
    "superficies": svg(path("M4 3 H20 V21 H4 Z M4 8 H20 M4 13 H20 M4 17 H20 M13 3 V21"),
                       path("M15 10.5 H18 M15 15 H18 M15 19 H18", ACC, 1.6)),
    # PROPIEDADESARQ: the element's BIM data
    "propiedades": svg(path("M3 4 H15 V20 H3 Z"), path("M5.5 8 H12.5 M5.5 12 H12.5 M5.5 16 H10"),
                       f'<circle cx="18" cy="16" r="4.2" stroke="{ACC}" stroke-width="1.3" fill="none"/>',
                       path("M18 15.2 V18.2", ACC, 1.5), dot(18, 13.4, 0.9)),
    # EDITARARQ: a pencil on a wall
    "editar": svg(hwall(2, 14, 15), path("M13 12 L20 5 L22 7 L15 14 L12 15 Z", ACC)),
    # UNIONESARQ: a tee regenerated
    "uniones": svg(path("M2 4 H22 M2 8 H9 M13 8 H22 M9 8 V21 M13 8 V21"),
                   path("M16 15 A5 5 0 1 1 20.5 19.5", ACC, 1.3), arrow(21.5, 15.5, 21.6, 19.6)),
    # DIAGNOSTICOARQ: a tee under the magnifier
    "diagnostico": svg(path("M2 4 H22 M2 8 H9 M13 8 H14 M9 8 V21"),
                       f'<circle cx="16" cy="14" r="4.5" stroke="{ACC}" stroke-width="1.3" fill="none"/>',
                       path("M19.3 17.3 L22 20", ACC, 1.8)),
    # ARQVALIDAR: walls checked
    "validar": svg(hwall(2, 14, 4), path("M4 8 V20 M8 8 V20"), path("M11 15 L14.5 19 L22 9", ACC, 1.8)),
    # EXPORTARBIM: the plan raised to a model and sent out
    "exportarbim": svg(path("M3 9 L10 5 L17 9 L10 13 Z M3 9 V17 L10 21 V13 M17 9 V13"),
                       arrow(14, 17, 22, 17)),
    # TIPOSMURO: a wall's layers
    "tiposmuro": svg(path("M3 3 V21 M21 3 V21 M3 3 H21 M3 21 H21"), path("M7 3 V21 M17 3 V21", ACC),
                     path("M9 6 L15 6 M9 10 L15 10 M9 14 L15 14 M9 18 L15 18", INK, 1.0)),
    # USOSARQ: the building and its use classes
    "usos": svg(path("M3 21 V10 L10 4 L17 10 V21 Z M8 21 V15 H12 V21"),
                path("M19 8 H22 M19 12 H22 M19 16 H22", ACC, 1.6)),
    # PARAMETROSARQ: sliders
    "parametros": svg(path("M4 6 H20 M4 12 H20 M4 18 H20"), dot(9, 6, 2.2), dot(15, 12, 2.2), dot(7, 18, 2.2)),
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, text in ICONS.items():
        (OUT / f"{name}.svg").write_text(text, encoding="utf-8")
    print(f"{len(ICONS)} iconos en {OUT}")


if __name__ == "__main__":
    main()

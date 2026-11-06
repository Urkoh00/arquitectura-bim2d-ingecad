# SPDX-License-Identifier: GPL-3.0-or-later
"""Steel column sections: standard tables and exact plan outlines.

Dimensions in mm, area A in cm² (as published). Sources (consulted
6-11-2026):
  IPN: ArcelorMittal, Sections MB catalogue (IPN); flanges slope 14 %,
       flange thickness measured at b/4 from the toe.
  IPE, HEA, HEB: European beam section tables (EN 10365 series); root radii
       r are the standard ones, verified because A = 2·b·tf + (h−2·tf)·tw
       + (4−π)·r² reproduces every published area within 0.2 %.
  UPN: Stad, caractéristiques techniques des profils UPN; flanges slope
       8 % (UPN ≤ 300) and 5 % (UPN > 300), thickness measured at b/2 from
       the toe, toe radius r2 = r1/2. These conventions reproduce the
       published areas within 0.8 % (IPN within 0.6 %).

Outline convention: local x along the flanges (width b), local y along
the depth h, origin at the centre of the bounding box. A column's
rotation turns this frame; rotation 0 puts the flanges along world X.
"""
from __future__ import annotations

import math

# name: (h, b, tw, tf, r)  [mm], A [cm²]
IPE = {80: (80, 46, 3.8, 5.2, 5, 7.64), 100: (100, 55, 4.1, 5.7, 7, 10.32),
       120: (120, 64, 4.4, 6.3, 7, 13.21), 140: (140, 73, 4.7, 6.9, 7, 16.43),
       160: (160, 82, 5.0, 7.4, 9, 20.09), 180: (180, 91, 5.3, 8.0, 9, 23.95),
       200: (200, 100, 5.6, 8.5, 12, 28.48), 220: (220, 110, 5.9, 9.2, 12, 33.37),
       240: (240, 120, 6.2, 9.8, 15, 39.12), 270: (270, 135, 6.6, 10.2, 15, 45.95),
       300: (300, 150, 7.1, 10.7, 15, 53.81), 330: (330, 160, 7.5, 11.5, 18, 62.61),
       360: (360, 170, 8.0, 12.7, 18, 72.73), 400: (400, 180, 8.6, 13.5, 21, 84.46),
       450: (450, 190, 9.4, 14.6, 21, 98.82), 500: (500, 200, 10.2, 16.0, 21, 115.52),
       550: (550, 210, 11.1, 17.2, 24, 134.42), 600: (600, 220, 12.0, 19.0, 24, 155.98)}
HEA = {100: (96, 100, 5.0, 8.0, 12, 21.2), 120: (114, 120, 5.0, 8.0, 12, 25.3),
       140: (133, 140, 5.5, 8.5, 12, 31.4), 160: (152, 160, 6.0, 9.0, 15, 38.8),
       180: (171, 180, 6.0, 9.5, 15, 45.3), 200: (190, 200, 6.5, 10.0, 18, 53.8),
       220: (210, 220, 7.0, 11.0, 18, 64.3), 240: (230, 240, 7.5, 12.0, 21, 76.8),
       260: (250, 260, 7.5, 12.5, 24, 86.8), 280: (270, 280, 8.0, 13.0, 24, 97.3),
       300: (290, 300, 8.5, 14.0, 27, 112.5), 320: (310, 300, 9.0, 15.5, 27, 124.4),
       340: (330, 300, 9.5, 16.5, 27, 133.5), 360: (350, 300, 10.0, 17.5, 27, 142.8),
       400: (390, 300, 11.0, 19.0, 27, 159.0)}
HEB = {100: (100, 100, 6.0, 10.0, 12, 26.0), 120: (120, 120, 6.5, 11.0, 12, 34.0),
       140: (140, 140, 7.0, 12.0, 12, 43.0), 160: (160, 160, 8.0, 13.0, 15, 54.3),
       180: (180, 180, 8.5, 14.0, 15, 65.3), 200: (200, 200, 9.0, 15.0, 18, 78.1),
       220: (220, 220, 9.5, 16.0, 18, 91.0), 240: (240, 240, 10.0, 17.0, 21, 106.0),
       260: (260, 260, 10.0, 17.5, 24, 118.4), 280: (280, 280, 10.5, 18.0, 24, 131.4),
       300: (300, 300, 11.0, 19.0, 27, 149.1), 320: (320, 300, 11.5, 20.5, 27, 161.3),
       340: (340, 300, 12.0, 21.5, 27, 170.9), 360: (360, 300, 12.5, 22.5, 27, 180.6),
       400: (400, 300, 13.5, 24.0, 27, 197.8)}
# IPN: (h, b, tw, tf, r1, r2), A
IPN = {80: (80, 42, 3.9, 5.9, 3.9, 2.3, 7.57), 100: (100, 50, 4.5, 6.8, 4.5, 2.7, 10.6),
       120: (120, 58, 5.1, 7.7, 5.1, 3.1, 14.2), 140: (140, 66, 5.7, 8.6, 5.7, 3.4, 18.2),
       160: (160, 74, 6.3, 9.5, 6.3, 3.8, 22.8), 180: (180, 82, 6.9, 10.4, 6.9, 4.1, 27.9),
       200: (200, 90, 7.5, 11.3, 7.5, 4.5, 33.4), 220: (220, 98, 8.1, 12.2, 8.1, 4.9, 39.5),
       240: (240, 106, 8.7, 13.1, 8.7, 5.2, 46.1), 260: (260, 113, 9.4, 14.1, 9.4, 5.6, 53.3),
       280: (280, 119, 10.1, 15.2, 10.1, 6.1, 61.0), 300: (300, 125, 10.8, 16.2, 10.8, 6.5, 69.0),
       320: (320, 131, 11.5, 17.3, 11.5, 6.9, 77.7), 340: (340, 137, 12.2, 18.3, 12.2, 7.3, 86.7),
       360: (360, 143, 13.0, 19.5, 13.0, 7.8, 97.0), 380: (380, 149, 13.7, 20.5, 13.7, 8.2, 107.0),
       400: (400, 155, 14.4, 21.6, 14.4, 8.6, 117.7), 450: (450, 170, 16.2, 24.3, 16.2, 9.7, 146.9),
       500: (500, 185, 18.0, 27.0, 18.0, 10.8, 179.4), 550: (550, 200, 19.0, 30.0, 19.0, 11.9, 212.0),
       600: (600, 215, 21.6, 32.4, 21.6, 13.0, 253.7)}
# UPN: (h, b, tw, tf, r1), A
UPN = {80: (80, 45, 6.0, 8.0, 8, 11.0), 100: (100, 50, 6.0, 8.5, 8.5, 13.5),
       120: (120, 55, 7.0, 9.0, 9, 17.0), 140: (140, 60, 7.0, 10.0, 10, 20.4),
       160: (160, 65, 7.5, 10.5, 10.5, 24.0), 180: (180, 70, 8.0, 11.0, 11, 28.0),
       200: (200, 75, 8.5, 11.5, 11.5, 32.2), 220: (220, 80, 9.0, 12.5, 12.5, 37.4),
       240: (240, 85, 9.5, 13.0, 13, 42.3), 260: (260, 90, 10.0, 14.0, 14, 48.3),
       280: (280, 95, 10.0, 15.0, 15, 53.3), 300: (300, 100, 10.0, 16.0, 16, 58.8),
       320: (320, 100, 14.0, 17.5, 17.5, 75.8), 350: (350, 100, 14.0, 16.0, 16, 77.3),
       380: (380, 102, 13.5, 16.0, 16, 80.4), 400: (400, 110, 14.0, 18.0, 18, 91.5)}

FAMILIES = ("IPE", "IPN", "HEA", "HEB", "UPN", "2UPN")
STEEL_DENSITY = 7850.0          # kg/m³
_ARC = 6                        # segments per quarter rounding


def _arc(c, r, a0, a1, n=_ARC):
    return [(c[0] + r * math.cos(a0 + (a1 - a0) * i / n),
             c[1] + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]


def _foot(c, m, q):
    """Foot of the perpendicular from c onto y = m·x + q."""
    x = (c[0] + m * (c[1] - q)) / (1 + m * m)
    return (x, m * x + q)


def _flange_quadrant(h, b, tw, tf, r1, r2, slope, x_ref, web_x, toe_x):
    """Upper flange path from the outer flange face over the toe down to the
    web, in a frame where the web face is at x = web_x and the toe at
    x = toe_x (toe_x > web_x). The inner flange face is the line
    y = m·x + q, thickness tf measured x_ref from the web face."""
    m = slope
    # t(x') = tf + slope·(x_ref − x'), x' = x − web_x; inner face y = h/2 − t
    q = h / 2 - tf - slope * x_ref - slope * web_x
    k = math.sqrt(1 + m * m)
    pts = [(toe_x, h / 2)]
    if r2 > 0:
        c2 = (toe_x - r2, m * (toe_x - r2) + q + r2 * k)
        f2 = _foot(c2, m, q)
        a_start, a_end = 0.0, math.atan2(f2[1] - c2[1], f2[0] - c2[0])
        pts.append((toe_x, c2[1]))
        pts += _arc(c2, r2, a_start, a_end)[1:]
    else:
        pts.append((toe_x, m * toe_x + q))
    c1 = (web_x + r1, m * (web_x + r1) + q - r1 * k)
    f1 = _foot(c1, m, q)
    a_start = math.atan2(f1[1] - c1[1], f1[0] - c1[0])
    pts.append(f1)
    pts += _arc(c1, r1, a_start, math.pi)[1:]
    pts.append((web_x, 0.0))
    return pts


def _mirror_y(pts):
    return [(x, -y) for x, y in pts]


def _dedupe(pts, eps=1e-9):
    out = []
    for p in pts:
        if not out or math.dist(out[-1], p) > eps:
            out.append(p)
    if len(out) > 1 and math.dist(out[0], out[-1]) <= eps:
        out.pop()
    return out


def i_section(h, b, tw, tf, r1, r2=0.0, slope=0.0, ref="mid"):
    """Outline (mm) of an I section centred at the origin (ccw)."""
    L = (b - tw) / 2
    x_ref = {"mid": L / 2, "b4": L - b / 4}[ref]
    quad = _flange_quadrant(h, b, tw, tf, r1, r2, slope, x_ref, tw / 2, b / 2)
    # quadrant goes from (b/2, h/2) to (tw/2, 0): right half, top then bottom
    right = [(0.0, h / 2)] + quad + list(reversed(_mirror_y(quad))) + [(0.0, -h / 2)]
    left = [(-x, y) for x, y in reversed(right)]
    return _ccw(_dedupe(right + left))


def u_section(h, b, tw, tf, r1, r2, slope):
    """Outline (mm) of a U (UPN) section, bbox centred at the origin, web on
    the left (back at x = −b/2), toes at x = +b/2."""
    L = b - tw
    x_ref = L - b / 2
    web_x, toe_x = -b / 2 + tw, b / 2
    quad = _flange_quadrant(h, b, tw, tf, r1, r2, slope, x_ref, web_x, toe_x)
    top = [(-b / 2, h / 2)] + quad
    bottom = list(reversed(_mirror_y(quad))) + [(-b / 2, -h / 2)]
    return _ccw(_dedupe(top + bottom))


def _ccw(poly):
    a = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]))
    return poly if a > 0 else list(reversed(poly))


def area(poly):
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]))) / 2


# --- public API --------------------------------------------------------------

def parse(text):
    """'IPE 200', 'heb160', '2UPN 120 cajon', '2UPN 120 empresillado 0,10'
    -> {'family', 'size', 'mode', 'gap'} or None."""
    t = str(text).strip().upper().replace(",", ".")
    for fam in sorted(FAMILIES, key=len, reverse=True):
        if t.startswith(fam):
            rest = t[len(fam):].split()
            if not rest or not rest[0].isdigit():
                return None
            size = int(rest[0])
            table = UPN if fam == "2UPN" else globals()[fam]
            if size not in table:
                raise ValueError(f"{fam} {size} no está en la tabla ({', '.join(map(str, table))})")
            out = {"family": fam, "size": size}
            if fam == "2UPN":
                mode = (rest[1] if len(rest) > 1 else "CAJON").lower()
                if mode.startswith("caj") or mode.startswith("uni"):
                    out.update(mode="cajon", gap=0.0)
                elif mode.startswith("emp"):
                    gap = float(rest[2]) if len(rest) > 2 else 0.10
                    out.update(mode="empresillado", gap=gap)
                else:
                    raise ValueError("2UPN: indique «cajon» o «empresillado <separación m>»")
            return out
    return None


def designation(p):
    if p["family"] == "2UPN":
        if p["mode"] == "cajon":
            return f"2UPN {p['size']} en cajón"
        return f"2UPN {p['size']} empresillados a {p['gap']:g} m".replace(".", ",")
    return f"{p['family']} {p['size']}"


def outlines(p):
    """Section outlines in METRES, bbox centred at the origin: [polygon]."""
    fam, size = p["family"], p["size"]
    if fam in ("IPE", "HEA", "HEB"):
        h, b, tw, tf, r, _a = globals()[fam][size]
        polys = [i_section(h, b, tw, tf, r)]
    elif fam == "IPN":
        h, b, tw, tf, r1, r2, _a = IPN[size]
        polys = [i_section(h, b, tw, tf, r1, r2, 0.14, "b4")]
    else:
        h, b, tw, tf, r1, _a = UPN[size]
        u = u_section(h, b, tw, tf, r1, r1 / 2, 0.08 if size <= 300 else 0.05)
        if fam == "UPN":
            polys = [u]
        else:
            # two channels: «cajón» toes against toes (a closed box);
            # «empresillado» backs outward, toes inward, ``gap`` between toes
            g = 1000.0 * float(p.get("gap", 0.0)) if p.get("mode") == "empresillado" else 0.0
            dx = b / 2 + g / 2
            left = [(x - dx, y) for x, y in u]                      # toes toward +x
            right = [(-x + dx, y) for x, y in reversed(u)]          # mirrored
            polys = [_ccw(left), _ccw(right)]
    return [[(x / 1000.0, y / 1000.0) for x, y in poly] for poly in polys]


def envelope(p):
    """Bounding box (m) of the section: (width along x, depth along y)."""
    xs = [x for poly in outlines(p) for x, _y in poly]
    ys = [y for poly in outlines(p) for _x, y in poly]
    return max(xs) - min(xs), max(ys) - min(ys)


def nominal_area(p):
    """Published area, m² (two channels count twice)."""
    table = UPN if p["family"] == "2UPN" else globals()[p["family"]]
    a = table[p["size"]][-1] / 1e4
    return 2 * a if p["family"] == "2UPN" else a


def mass_per_metre(p):
    return nominal_area(p) * STEEL_DENSITY

# SPDX-License-Identifier: GPL-3.0-or-later
"""Column plan geometry, shared by the DXF entity, the junction engine and
the IngeTrazo export.

A column has
* a FOOTPRINT: the convex outline it occupies in plan (the visible DXF
  polyline; the junction engine cuts walls with it and rooms go round it);
  it includes the covering (``cover``, «recubrimiento»);
* its SECTIONS: what the column itself is made of (concrete section, or the
  real steel profile(s) from ``profiles``).

The difference footprint − sections, when it exists (a covering, or the
space a steel profile leaves inside its box), is exported as the column's
covering, so that walls + columns + coverings + rooms tile the plan exactly.

Local frame: x along the width (flanges of a steel profile), y along the
depth; ``rotation`` (degrees) turns it; ``center`` is the centre of the
footprint's bounding box.
"""
from __future__ import annotations

import math

SHAPES = {'rect', 'circ', 'hex', 'oct', 'steel'}


def _rot(pts, center, angle_deg):
    a = math.radians(float(angle_deg or 0.0))
    c, s = math.cos(a), math.sin(a)
    x0, y0 = float(center[0]), float(center[1])
    return [(x0 + x * c - y * s, y0 + x * s + y * c) for x, y in pts]


def _profile(values):
    from . import profiles as PR
    p = PR.parse(values.get('profile', ''))
    if p is None:
        raise ValueError('Perfil metálico no reconocido: ' + str(values.get('profile')))
    return p


def _local_sections(values):
    """Section polygons in the local frame (m)."""
    shape = values.get('shape', 'rect')
    if shape == 'rect':
        w, d = float(values['width']), float(values['depth'])
        if not all(map(math.isfinite, (w, d))) or min(w, d) <= 0:
            raise ValueError('Sección rectangular inválida')
        return [[(-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2)]]
    if shape == 'steel':
        from . import profiles as PR
        return PR.outlines(_profile(values))
    if shape not in ('circ', 'hex', 'oct'):
        raise ValueError('Forma de pilar desconocida: ' + str(shape))
    r = float(values['radius'])
    if not math.isfinite(r) or r <= 0:
        raise ValueError('Radio de pilar inválido')
    n = {'circ': 48, 'hex': 6, 'oct': 8}[shape]
    return [[(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n)) for i in range(n)]]


def local_size(values):
    """(width, depth) of the footprint's bounding box, covering included."""
    pts = local_footprint(values)
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return max(xs) - min(xs), max(ys) - min(ys)


def local_footprint(values):
    cover = float(values.get('cover') or 0.0)
    if not math.isfinite(cover) or cover < 0:
        raise ValueError('Recubrimiento inválido')
    shape = values.get('shape', 'rect')
    secs = _local_sections(values)
    if shape in ('circ', 'hex', 'oct'):
        r = float(values['radius']) + cover
        n = {'circ': 48, 'hex': 6, 'oct': 8}[shape]
        if shape == 'circ':
            r = r / math.cos(math.pi / n) if cover else r        # circumscribe the cover ring
        return [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n)) for i in range(n)]
    xs = [x for poly in secs for x, _y in poly]
    ys = [y for poly in secs for _x, y in poly]
    x0, x1, y0, y1 = min(xs) - cover, max(xs) + cover, min(ys) - cover, max(ys) + cover
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def column_geometry(center, values):
    """{'footprint': world polygon, 'sections': [world polygons]}."""
    x, y = float(center[0]), float(center[1])
    if not (math.isfinite(x) and math.isfinite(y)):
        raise ValueError('Posición de pilar inválida')
    rot = values.get('rotation') or 0.0
    return {'footprint': _rot(local_footprint(values), center, rot),
            'sections': [_rot(s, center, rot) for s in _local_sections(values)]}


def column_points(center, values):
    """The footprint (the DXF polyline). Kept for older callers."""
    return column_geometry(center, values)['footprint']


def anchor_offset(values, anchor):
    """Local offset of anchor 1..9 (numeric keypad: 7 8 9 / 4 5 6 / 1 2 3)
    from the centre of the footprint."""
    w, d = local_size(values)
    k = int(anchor)
    if not 1 <= k <= 9:
        raise ValueError('Enganche entre 1 y 9')
    ix, iy = (k - 1) % 3 - 1, (k - 1) // 3 - 1
    return ix * w / 2, iy * d / 2


def center_from_anchor(point, values, anchor):
    ax, ay = anchor_offset(values, anchor)
    a = math.radians(float(values.get('rotation') or 0.0))
    c, s = math.cos(a), math.sin(a)
    return (float(point[0]) - (ax * c - ay * s), float(point[1]) - (ax * s + ay * c))


def parse_section(text):
    """Typed section -> values to update. Accepts '0,30x0,30', '30x40' (cm),
    'D0,35' / 'Ø35' (circular), 'IPE 200', '2UPN 160 empresillado 0,10'."""
    from . import profiles as PR
    t = str(text).strip()
    p = PR.parse(t)
    if p is not None:
        return {'shape': 'steel', 'profile': PR.designation(p).replace(' en cajón', ' cajon')
                .replace(' empresillados a ', ' empresillado '),
                'material': 'Acero S275JR'}
    low = t.lower().replace(',', '.').replace(' ', '')

    def metres(v):
        v = float(v)
        return v / 100.0 if v > 3 else v
    if low[:1] in ('d', 'ø', 'o') and low[1:].replace('.', '', 1).isdigit():
        return {'shape': 'circ', 'radius': metres(low[1:]) / 2}
    if 'x' in low:
        a, b = low.split('x', 1)
        return {'shape': 'rect', 'width': metres(a), 'depth': metres(b)}
    raise ValueError('Sección no reconocida: use 0,30x0,30, D0,35, IPE 200, HEB 160, '
                     'UPN 120, 2UPN 160 cajon, 2UPN 160 empresillado 0,10')

# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: Contorno y límites verticales de un recinto (forjados, falso techo), común a planta, fichas
#   y exportación. Aplica las particiones virtuales.
#   (Guía del código: docs/GUIA_DEL_CODIGO.md)
"""Room footprint and horizontal limits, shared by plan, sheets and export.

Slab HATCHes are read through the existing slab reader. No roof geometry is
invented here: inclined slabs, roofs and independent ceilings belong to R16-4.
Legacy rooms keep their manual height until explicitly switched to automatic.
"""
from __future__ import annotations

import math

from .geom import polygon as P, solids as S, spaces as SP


def outline(record, result, entity=None):
    if record.get('boundary_mode', 'walls') not in ('walls', 'polyline'):
        raise ValueError('Modo de contorno de recinto no válido')
    if record.get('boundary_mode') != 'polyline':
        from .particiones_virtuales import segments_at
        base = float(record.get('base', 0))
        segs = segments_at(getattr(result, 'virtual_partitions', ()), base)
        return SP.space_at(SP.network_at(result, base), record['seed'], partitions=segs)
    from .slabs import region
    if entity is None:
        points = record['boundary']
    else:
        if entity.dxftype() != 'LWPOLYLINE' or not entity.closed:
            raise ValueError('El recinto por polilínea necesita un contorno cerrado')
        if any(abs(p[4]) > 1e-10 for p in entity.get_points()):
            raise ValueError('Recinto por polilínea: solo segmentos rectos')
        vertices = list(entity.vertices_in_wcs())
        if vertices and max(p.z for p in vertices)-min(p.z for p in vertices) > 1e-7:
            raise ValueError('El contorno del recinto debe ser horizontal')
        points = [(p.x, p.y) for p in vertices]
    geo = region(points)
    geo['perimeter'] = SP._perimeter(geo['outer'])
    return geo, ''


def boundaries(drawing, skip=()):
    """Current providers. R16-4 can extend this without changing room solids."""
    from .architectural import metadata
    from .slabs import read, region
    out = []
    for entity in drawing.modelspace():
        if entity.dxf.handle in skip or (metadata(entity) or {}).get('kind') != 'slab':
            continue
        slab = read(entity)
        out.append({**slab, 'pieces': region(slab['outer'], slab['holes'])['pieces'],
                    'limit_type': 'forjado'})
    return out


def resolve(record, room, limits=()):
    """Exact horizontal cell complex, including partial coverage and holes.

The source base is the level anchor; a lower slab's visible top is the floor.
Height is the maximum free height; the volume is integrated over the cells.
Manual mode ignores the envelope. A legacy ceiling is a cap at floor + manual
height; a lower slab underside still wins in automatic mode.
"""
    anchor = float(record.get('base', 0))
    manual = float(record['height'])
    if not math.isfinite(anchor) or not math.isfinite(manual) or manual <= 0:
        raise ValueError('Cota finita y altura manual positiva requeridas')
    if record.get('height_mode', 'manual') not in ('auto', 'manual'):
        raise ValueError('Modo de altura no válido')
    automatic = record.get('height_mode', 'manual') == 'auto'
    cells = [(piece, []) for piece in room['pieces']]
    if automatic:
        for limit in limits:
            for clipper in limit['pieces']:
                next_cells = []
                for piece, owners in cells:
                    inside = P.convex_intersection(piece, clipper)
                    if inside and P.area(inside) > 1e-10:
                        next_cells.append((inside, owners + [limit]))
                        next_cells.extend((p, owners) for p in P.convex_difference(piece, clipper))
                    else:
                        next_cells.append((piece, owners))
                cells = next_cells
    resolved, ceiling_cells, types, ids, floors = [], [], set(), set(), set()
    for piece, owners in cells:
        below = [s for s in owners if float(s['base']) <= anchor + 1e-8]
        floor = max(below, key=lambda s: float(s['base'])+float(s['thickness']), default=None)
        bottom = float(floor['base'])+float(floor['thickness']) if floor else anchor
        if floor:
            floors.add(floor['id'])
        above = [s for s in owners if float(s['base']) > anchor + 1e-8]
        top = min(above, key=lambda s: float(s['base']), default=None)
        kind = 'manual'
        upper = bottom + manual
        if top:
            upper, kind = float(top['base']), top['limit_type']
        if record.get('ceiling') and (not top or bottom+manual <= upper+1e-8):
            upper, kind = bottom+manual, 'falso techo'
        if top and kind != 'falso techo':
            ids.add(top['id'])
        if upper <= bottom+1e-8:
            raise ValueError('El límite superior no deja altura libre sobre el forjado inferior')
        types.add(kind)
        resolved.append((piece, (bottom, upper)))
        if kind == 'falso techo':
            thickness = float(record.get('ceiling_thickness') or .015)
            if not math.isfinite(thickness) or thickness <= 0:
                raise ValueError('El espesor del falso techo debe ser positivo')
            ceiling_cells.append((piece, (upper, upper+thickness)))
    faces = S.boundary(resolved)
    volume = sum(P.area(p)*(hi-lo) for p, (lo, hi) in resolved)
    return {'faces': faces, 'volume': volume, 'cells': resolved, 'ceiling_cells': ceiling_cells,
            'base': min(lo for _, (lo, hi) in resolved),
            'height': max(hi-lo for _, (lo, hi) in resolved),
            'upper_limit': ', '.join(sorted(types)), 'upper_limit_ids': sorted(ids),
            'lower_limit_ids': sorted(floors)}


def effective(record, envelope):
    return {**record, 'base': envelope['base'], 'height': envelope['height'],
            'upper_limit': envelope['upper_limit'],
            'upper_limit_ids': envelope['upper_limit_ids'],
            'lower_limit_ids': envelope['lower_limit_ids']}

# SPDX-License-Identifier: GPL-3.0-or-later
"""Junctions solved by height bands (independent audit of v1.15,
ARQ-AUD-0002: walls that do not share any height must not cut each other).

The heights where some wall or column starts or ends split the building
into bands; the junctions are solved in each band with the elements that
occupy it (the same band set is solved once).  Each wall keeps its
footprint per band, so its solid is exact, and the plan shows the union.
For a one-storey plan there is a single band and nothing changes.
Adapted from the correction delivered with that audit."""
from __future__ import annotations

import math

from . import junctions as J
from . import polygon as P


def solve_records(walls, columns):
    """Junction result with ``vertical_networks`` [((lo, hi), result)] and,
    per wall, ``bands`` [(lo, hi, geometry)] besides the usual fields."""
    specs = J.walls_from_records(walls)
    wall_z = {i: (float(m.get('base', 0)), float(m.get('base', 0)) + float(m['height'])) for i, m in walls}
    col_z = {i: (float(m.get('base', 0)), float(m.get('base', 0)) + float(m['height'])) for i, m in columns}
    heights = sorted({v for z in list(wall_z.values()) + list(col_z.values()) for v in z})
    combined = J.Result()
    combined.specs = {w.id: w for w in specs}
    combined.vertical_networks = []
    combined.columns = {i: m['polygon'] for i, m in columns}
    wall_bands = {w.id: [] for w in specs}
    cache = {}
    for lo, hi in zip(heights, heights[1:]):
        if hi - lo <= 1e-9:
            continue
        mid = lo + (hi - lo) / 2
        ws = [w for w in specs if wall_z[w.id][0] <= mid < wall_z[w.id][1]]
        cs = [(i, m['polygon']) for i, m in columns if col_z[i][0] <= mid < col_z[i][1]]
        if not ws and not cs:
            continue
        key = (tuple(w.id for w in ws), tuple(i for i, _ in cs))
        if key not in cache:
            cache[key] = J.solve(ws, cs)
        part = cache[key]
        combined.vertical_networks.append(((lo, hi), part))
        for ident, geo in part.walls.items():
            wall_bands[ident].append((lo, hi, geo))
    for ident, bands in wall_bands.items():
        projection, projected = [], set()
        for lo, hi, geo in bands:
            if id(geo) in projected:
                continue
            projected.add(id(geo))
            if not projection:
                projection.extend(geo['pieces'])
                continue
            previous = list(projection)
            additions = []
            for piece in geo['pieces']:
                fragments = [piece]
                for occupied in previous:
                    fragments = [q for f in fragments for q in P.convex_difference(f, occupied)]
                additions.extend(fragments)
            projection.extend(additions)
        combined.walls[ident] = dict(pieces=projection, loops=P.merge(projection),
                                     area=math.fsum(P.area(p) for p in projection), bands=bands)
    for part in cache.values():
        for field in ('nodes', 'tees', 'clips', 'warnings'):
            getattr(combined, field).extend(getattr(part, field))
    return combined

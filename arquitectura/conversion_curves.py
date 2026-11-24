# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: LINEASAMURO: une tramos de muro curvo detectados, solo a través de huecos comprobados.
#   Desde la v1.48: los huecos de un anillo o de un conjunto mayor que un muro curvo ya no se
#   pierden; el conjunto se reparte en muros de curves.MAX_SWEEP como máximo, con cada hueco
#   dentro de un solo muro.
#   (Guía del código: docs/GUIA_DEL_CODIGO.md)
"""Join detected circular wall runs only across evidenced openings.

Reuse the existing arc pairing and swing reader. The result is the normal
wall/opening records, not a second geometric representation. Unknown gaps
and planar frames that do not fit remain separate, with a warning.

What changed in v1.48
----------------------------------------
* The evidence for one gap (radial jambs, glazing arcs, swing chords, plane
  frame fit) is the same code as before, moved into ``_read_gap``.
* A gap is now looked for between EVERY pair of neighbouring runs of a circle,
  also across the angular seam and across the closing of a ring. Before, the
  largest uncovered interval was taken as the seam and never read, so a ring
  with a door lost the door without any warning.
* Runs joined through evidenced gaps form a *chain*. A wall record holds at
  most ``curves.MAX_SWEEP``, so a chain longer than that (a ring) is cut in
  solid wall, never inside an opening (``plan_cuts``). Before, such a chain
  was not joined and its door was lost with a warning.
"""
from __future__ import annotations
import math

TAU = math.tau
from .geom.curves import MAX_SWEEP
HALF = MAX_SWEEP + 1e-9        # the largest sweep of one wall record (curves.MAX_SWEEP)
GAP_MIN, GAP_MAX = .3, 2.4     # m of axis arc: smaller is not a door, wider is not read
CUT_MARGIN = .30               # m of solid wall kept between a cut and the nearest jamb


def plan_cuts(start, end, openings, radius, margin=CUT_MARGIN):
    """Angles at which to cut the chain ``start..end`` into walls of at most
    ``curves.MAX_SWEEP``, every cut in solid wall at least ``margin`` metres from a
    jamb. ``openings``: [(lo, hi)] inside the chain. [] if no cut is needed,
    None if no valid division exists."""
    total = end - start
    if total <= HALF:
        return []
    solid, cursor = [], start
    for lo, hi in sorted(openings):
        solid.append((cursor, lo))
        cursor = hi
    solid.append((cursor, end))
    m = margin / radius
    usable = [(a + m, b - m) for a, b in solid if b - a >= 2 * m]
    if not usable:
        return None
    first = math.ceil(total / HALF - 1e-12)
    for pieces in range(first, first + 3):
        cuts, ok = [], True
        for j in range(1, pieces):
            ideal = start + total * j / pieces
            best = min((min(max(ideal, a), b) for a, b in usable), key=lambda x: abs(x - ideal))
            if cuts and best <= cuts[-1] + 2 * m:
                ok = False
                break
            cuts.append(best)
        bounds = [start, *cuts, end]
        if ok and all(q - p <= HALF for p, q in zip(bounds, bounds[1:])):
            return cuts
    return None


def recover(curved, leaves):
    from .geom.junctions import Wall
    from . import convert_tools as C, openings as OP
    from .vendor import walldetect as WD
    wall_arcs=[arc for entity,role in leaves if role in {'muros','medianeras','particiones'}
               for arc in C._pieces(entity)[1]]
    groups = []
    for row in curved:
        a, b, thickness, bulge = row
        spec = Wall('candidate', a, b, thickness, 'eje', bulge=bulge)
        # The native reader produces counter-clockwise runs of at most pi.
        found = next((g for g in groups if math.dist(g[0].c, spec.c) < 1e-5
                      and abs(g[0].r-spec.r) < 1e-5
                      and abs(g[0].thickness-thickness) < 1e-6), None)
        if found is None:
            groups.append([spec])
        else:
            found.append(spec)
    result, openings, warnings = [], [], []

    def read_gap(spec, angle0, angle1):
        """Evidence for the gap between two axis angles: (kind, hinge, face) or None."""
        gap = (angle1-angle0)*spec.r
        def radial_edge(radius,angle,edge):
            return any(math.dist(center,spec.c)<1e-5 and abs(r-radius)<1e-5
                       and abs((bound-angle+math.pi)%TAU-math.pi)*spec.r<=.001
                       for center,r,first,last in wall_arcs
                       for bound in ([first] if edge=='start' else [last]))
        aligned=all(radial_edge(radius,angle0,'end') and radial_edge(radius,angle1,'start')
                    for radius in (spec.r-spec.thickness/2,spec.r+spec.thickness/2))
        if not aligned:
            warnings.append('Jambas curvas no radiales o desalineadas; fragmentos conservados')
            return None
        a = (spec.c[0]+spec.r*math.cos(angle0), spec.c[1]+spec.r*math.sin(angle0))
        b = (spec.c[0]+spec.r*math.cos(angle1), spec.c[1]+spec.r*math.sin(angle1))
        length = math.dist(a,b);u=((b[0]-a[0])/length,(b[1]-a[1])/length)
        middle=((a[0]+b[0])/2,(a[1]+b[1])/2)
        context=[];votes=set();arc_glass=False
        for entity, role in leaves:
            if role not in {'carpinteria','puertas','ventanas','vanos'}:
                continue
            _straight, arcs = C._pieces(entity)
            relevant=False
            for center, radius, t0, t1 in arcs:
                shift=TAU*round((angle0-t0)/TAU)
                overlap=min(angle1,t1+shift)-max(angle0,t0+shift)
                if (math.dist(center,spec.c)<1e-5
                        and abs(radius-spec.r)<spec.thickness/2+1e-6
                        and overlap>=.8*(angle1-angle0)):
                    arc_glass=True;relevant=True
            for seg in C._segments(entity):
                p=((seg[0]+seg[2])/2,(seg[1]+seg[3])/2)
                along=(p[0]-middle[0])*u[0]+(p[1]-middle[1])*u[1]
                across=abs((p[1]-middle[1])*u[0]-(p[0]-middle[0])*u[1])
                if abs(along)<=length/2+.08 and across<=length+spec.thickness:
                    context.append(list(seg)+[0]);relevant=True
            if relevant and role!='carpinteria':
                votes.add({'puertas':'door','ventanas':'window','vanos':'void'}[role])
        geometric = WD._gap_kind(middle,length,u,spec.thickness,context)
        if arc_glass:
            geometric=('window',0,0)
        if len(votes)>1:
            warnings.append('Hueco curvo con clasificaciones contradictorias; fragmentos conservados')
            return None
        if not (geometric or votes=={'void'}):
            return None
        answer=geometric or ('void',0,0)
        if votes:
            answer=(next(iter(votes)),answer[1],answer[2])
        # Existing carpentry is planar. Never join a wall if its opening would
        # later fail during regeneration/export. The test wall only needs the
        # radius, the thickness and the opening: a stub of solid on each side.
        if answer[0]!='void':
            stub=.3/spec.r
            trial=Wall('trial',
                (spec.c[0]+spec.r*math.cos(angle0-stub),spec.c[1]+spec.r*math.sin(angle0-stub)),
                (spec.c[0]+spec.r*math.cos(angle1+stub),spec.c[1]+spec.r*math.sin(angle1+stub)),
                spec.thickness,'eje',bulge=math.tan((angle1-angle0+2*stub)/4))
            try:
                OP.proxy(trial,{'offset':stub*spec.r,'width':gap})
            except ValueError:
                warnings.append('Hueco curvo: el cerco plano no cabe; fragmentos conservados')
                return None
        return answer

    def emit(spec, f0, f1, inside):
        """One wall record from axis angle f0 to f1 and its openings (lo, hi, answer)."""
        index = len(result)
        a = (spec.c[0]+spec.r*math.cos(f0), spec.c[1]+spec.r*math.sin(f0))
        b = (spec.c[0]+spec.r*math.cos(f1), spec.c[1]+spec.r*math.sin(f1))
        result.append((a, b, spec.thickness, math.tan((f1-f0)/4)))
        for lo, hi, kind, hinge, face in inside:
            openings.append((index, ((lo+hi)/2-f0)*spec.r, (hi-lo)*spec.r, kind, hinge, face))

    for group in groups:
        spec = group[0]
        runs = sorted(((s.t0 % TAU, s.t0 % TAU + s.sweep) for s in group))
        count = len(runs)
        # junction after run i: None = break (contiguous, unread or not evidenced),
        # else (gap in radians, answer)
        junctions = []
        for i in range(count):
            if count == 1:
                junctions.append(None)
                continue
            here, there = runs[i], runs[(i+1) % count]
            gap_angle = (there[0]-here[1]) % TAU
            if gap_angle > TAU-1e-6:
                gap_angle = 0.
            gap = gap_angle*spec.r
            if gap <= 1e-5:
                junctions.append(None)
                continue
            answer = None
            if GAP_MIN <= gap <= GAP_MAX:
                answer = read_gap(spec, here[1], here[1]+gap_angle)
            if answer:
                junctions.append((gap_angle, answer))
            else:
                if gap <= GAP_MAX:
                    warnings.append('Discontinuidad curva sin carpintería inequívoca; no se une')
                junctions.append(None)
        # Rotate to start after a break. A ring whose every junction is an
        # evidenced opening has no break: begin in the middle of its longest run.
        pieces = [list(r) for r in runs]
        if all(j is not None for j in junctions):
            longest = max(range(count), key=lambda k: runs[k][1]-runs[k][0])
            lo, hi = runs[longest]
            middle = (lo+hi)/2
            pieces[longest] = [middle, hi]
            tail = [lo, middle]
            order = list(range(longest, count))+list(range(longest))
            chain_runs = [(pieces[k][0], pieces[k][1]) for k in order]
            chain_junctions = [junctions[k] for k in order]
            chain_runs.append((tail[0]+TAU, tail[1]+TAU))
            segments_input = [(chain_runs, chain_junctions)]
        else:
            first = next(i for i, j in enumerate(junctions) if j is None)
            order = [(first+1+k) % count for k in range(count)]
            segments_input, run_list, junction_list = [], [], []
            for k in order:
                run_list.append(runs[k]); junction_list.append(junctions[k])
                if junctions[k] is None:
                    segments_input.append((run_list, junction_list[:-1]))
                    run_list, junction_list = [], []
        for run_list, junction_list in segments_input:
            # unwrap: each run starts where the previous one ended plus its gap
            solids, opens = [], []
            cursor = run_list[0][0]
            for k, (lo, hi) in enumerate(run_list):
                length = hi-lo
                solids.append((cursor, cursor+length))
                cursor += length
                if k < len(junction_list):
                    gap_angle, answer = junction_list[k]
                    opens.append((cursor, cursor+gap_angle, *answer))
                    cursor += gap_angle
            start, end = solids[0][0], solids[-1][1]
            cuts = plan_cuts(start, end, [(o[0], o[1]) for o in opens], spec.r)
            if cuts is None:
                warnings.append(f'Hueco curvo: el conjunto supera {math.degrees(MAX_SWEEP):g}° y no admite corte en muro macizo; '
                                'fragmentos conservados')
                for lo, hi in solids:
                    emit(spec, lo, hi, [])
                continue
            bounds = [start, *cuts, end]
            for f0, f1 in zip(bounds, bounds[1:]):
                emit(spec, f0, f1, [o for o in opens if f0-1e-9 <= o[0] and o[1] <= f1+1e-9])
    if openings:
        warnings.append('Huecos curvos: ancho y posición por arco de eje; carpintería plana existente, no curva')
    return result, openings, warnings

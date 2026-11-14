# SPDX-License-Identifier: GPL-3.0-or-later
"""Join detected circular wall runs only across evidenced openings.

Reuse the existing arc pairing and swing reader. The result is the normal
wall/opening records, not a second geometric representation. Unknown gaps
and planar frames that do not fit remain separate, with a warning.
"""
from __future__ import annotations
import math


def recover(curved, leaves):
    from .geom.junctions import Wall
    from . import convert_tools as C, openings as OP
    from .vendor import walldetect as WD
    wall_arcs=[arc for entity,role in leaves if role in {'muros','medianeras','tabiques'}
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
    for group in groups:
        # Rotate the angular seam into the largest uncovered interval. This
        # supports gaps spanning angle zero without joining a full circle.
        starts = sorted(s.t0 % math.tau for s in group)
        seam = max(starts, key=lambda s: (s-max((q for q in starts if q < s),
                      default=starts[-1]-math.tau)))
        intervals = sorted((((s.t0-seam) % math.tau,
                            (s.t0-seam) % math.tau + s.sweep, s) for s in group),
                           key=lambda x:x[0])
        start, end, spec = intervals[0]
        pending = []

        def flush():
            a = (spec.c[0]+spec.r*math.cos(seam+start), spec.c[1]+spec.r*math.sin(seam+start))
            b = (spec.c[0]+spec.r*math.cos(seam+end), spec.c[1]+spec.r*math.sin(seam+end))
            index = len(result)
            result.append((a, b, spec.thickness, math.tan((end-start)/4)))
            for lo, hi, kind, hinge, face in pending:
                openings.append((index, ((lo+hi)/2-start)*spec.r,
                                 (hi-lo)*spec.r, kind, hinge, face))

        for lo, hi, nxt in intervals[1:]:
            gap = (lo-end)*spec.r
            answer = None
            if .3 <= gap <= 2.4 and hi-start <= math.pi+1e-9:
                angle0, angle1 = seam+end, seam+lo
                def radial_edge(radius,angle,edge):
                    return any(math.dist(center,spec.c)<1e-5 and abs(r-radius)<1e-5
                               and abs((bound-angle+math.pi)%math.tau-math.pi)*spec.r<=.001
                               for center,r,first,last in wall_arcs
                               for bound in ([first] if edge=='start' else [last]))
                aligned=all(radial_edge(radius,angle0,'end') and radial_edge(radius,angle1,'start')
                            for radius in (spec.r-spec.thickness/2,spec.r+spec.thickness/2))
                if not aligned:
                    warnings.append('Jambas curvas no radiales o desalineadas; fragmentos conservados')
                    flush();start,end,spec=lo,hi,nxt;pending=[]
                    continue
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
                        shift=math.tau*round((angle0-t0)/math.tau)
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
                elif geometric or votes=={'void'}:
                    answer=geometric or ('void',0,0)
                    if votes:
                        answer=(next(iter(votes)),answer[1],answer[2])
                    # Existing carpentry is planar. Never join a wall if its
                    # opening would later fail during regeneration/export.
                    if answer[0]!='void':
                        trial=Wall('trial',
                            (spec.c[0]+spec.r*math.cos(seam+start),spec.c[1]+spec.r*math.sin(seam+start)),
                            (spec.c[0]+spec.r*math.cos(seam+hi),spec.c[1]+spec.r*math.sin(seam+hi)),
                            spec.thickness,'eje',bulge=math.tan((hi-start)/4))
                        try:
                            OP.proxy(trial,{'offset':(end-start)*spec.r,'width':gap})
                        except ValueError:
                            answer=None
                            warnings.append('Hueco curvo: el cerco plano no cabe; fragmentos conservados')
            if answer:
                pending.append((end,lo,*answer));end=hi
            else:
                if gap>1e-5 and gap<=2.4:
                    warnings.append('Discontinuidad curva sin carpintería inequívoca; no se une')
                flush();start,end,spec=lo,hi,nxt;pending=[]
        flush()
    if openings:
        warnings.append('Huecos curvos: ancho y posición por arco de eje; carpintería plana existente, no curva')
    return result, openings, warnings

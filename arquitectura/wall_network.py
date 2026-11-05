# SPDX-License-Identifier: GPL-3.0-or-later
"""Native 2D polygon boundary engine for wall-wall and wall-column junctions.

Uses only Python + ezdxf. DXF wall entities remain authoritative; outlines are
regenerated, never treated as new BIM objects. No dependence on shapely.
"""
from __future__ import annotations
import math
from core.commands import Command

TOL=1e-8

def cross(a,b):return a[0]*b[1]-a[1]*b[0]
def sub(a,b):return (a[0]-b[0],a[1]-b[1])
def interp(a,b,t):return (a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t)
def polygon_edges(p):return list(zip(p,p[1:]+p[:1]))
def contains(pt,poly):
    x,y=pt;inside=False
    for (a,b) in polygon_edges(poly):
        if (a[1]>y)!=(b[1]>y):
            xx=a[0]+(y-a[1])*(b[0]-a[0])/(b[1]-a[1])
            if xx>x:inside=not inside
    return inside

def split_t(a,b,c,d):
    r=sub(b,a);s=sub(d,c);q=sub(c,a);den=cross(r,s)
    if abs(den)<TOL:
        if abs(cross(q,r))>TOL:return []
        rr=r[0]**2+r[1]**2
        if rr<TOL:return []
        return [t for p in (c,d) if -TOL<(t:=((p[0]-a[0])*r[0]+(p[1]-a[1])*r[1])/rr)<1+TOL]
    t=cross(q,s)/den;u=cross(q,r)/den
    return [t] if -TOL<t<1+TOL and -TOL<u<1+TOL else []

def union_outline(polys,cutters=()):
    """Exterior lines of wall union, omitting linework hidden inside pillars.

    The pillar boundary itself stays in its own layer to retain its identity.
    Suitable for clean simple polygons; not a robust solid BRep boolean.
    """
    polygons=[list(p) for p in polys if len(p)>=3]
    if not polygons:return []
    all_edges=[edge for poly in polygons+list(cutters) for edge in polygon_edges(poly)]
    output=[];seen=set()
    def wall_inside(x):return any(contains(x,p) for p in polygons)
    def other_inside(x):return any(contains(x,p) for p in cutters)
    for poly in polygons:
        for a,b in polygon_edges(poly):
            ts=[0.,1.]
            for c,d in all_edges:
                ts.extend(t for t in split_t(a,b,c,d) if TOL<t<1-TOL)
            ts=sorted(set(round(t,10) for t in ts))
            for u,v in zip(ts,ts[1:]):
                if v-u<1e-9:continue
                p,q=interp(a,b,u),interp(a,b,v)
                dx=q[0]-p[0];dy=q[1]-p[1];l=math.hypot(dx,dy)
                if l<1e-8:continue
                mid=interp(p,q,.5);nx=-dy/l;ny=dx/l
                eps=min(1e-5,l*.001)
                left=(mid[0]+nx*eps,mid[1]+ny*eps)
                right=(mid[0]-nx*eps,mid[1]-ny*eps)
                il=wall_inside(left) and not other_inside(left)
                ir=wall_inside(right) and not other_inside(right)
                if il==ir:continue
                key=tuple(sorted(((round(p[0],7),round(p[1],7)),
                                  (round(q[0],7),round(q[1],7)))))
                if key not in seen:
                    seen.add(key);output.append((p,q))
    return output


def simplify_contour_segments(segments, wall_sources=None, precision=7):
    """Eliminate collinear split edges without losing BIM provenance.

    When wall_sources is supplied, return (a,b,wall_ids). Each merged edge
    keeps the union of the IDs carried by the original split edges. A shared
    edge legitimately has more than one owner; the editor must ask which.
    """
    def key(p):
        return (round(float(p[0]), precision), round(float(p[1]), precision))
    edges = {}
    for a, b in segments:
        owners=set(segment_owners(a,b,wall_sources)) if wall_sources is not None else set()
        a, b = key(a), key(b)
        if a == b:
            continue
        k = tuple(sorted((a,b)))
        edges.setdefault(k,set()).update(owners)
    while True:
        adjacency={}
        for a,b in edges:
            adjacency.setdefault(a,[]).append(b)
            adjacency.setdefault(b,[]).append(a)
        merged=False
        for v,neighbors in sorted(adjacency.items()):
            if len(neighbors)!=2:continue
            a,b=neighbors
            if a==b:continue
            va=sub(a,v);vb=sub(b,v)
            la=math.hypot(*va);lb=math.hypot(*vb)
            if la<1e-10 or lb<1e-10:continue
            if abs(cross(va,vb))>1e-8*la*lb:continue
            if va[0]*vb[0]+va[1]*vb[1]>=0:continue
            k1=tuple(sorted((v,a)));k2=tuple(sorted((v,b)))
            owner_ids=edges.pop(k1)|edges.pop(k2)
            k=tuple(sorted((a,b)))
            edges.setdefault(k,set()).update(owner_ids)
            merged=True
            break
        if not merged:break
    if wall_sources is None:
        return list(edges)
    return [(a,b,sorted(ids)) for (a,b),ids in edges.items()]


def joined_wall_sources(records, tolerance=1e-6, min_angle_degrees=12.0):
    """Extend ONLY terminal wall footprints to another wall's far face.

    Handles oblique L/T connections and different widths/references without
    changing the BIM axis. Crossing X footprints overlap naturally and need no
    extension. A nearly parallel intersection is intentionally not mitered.
    No global fuzzy snap: the endpoint must lie inside the host wall strip.
    """
    from .architectural_v10 import wall_corners
    result=[]
    min_sine=math.sin(math.radians(min_angle_degrees))
    for index,(ident,info) in enumerate(records):
        a=tuple(map(float,info['a']));b=tuple(map(float,info['b']))
        delta=sub(b,a);length=math.hypot(*delta)
        if length<1e-8:continue
        ux,uy=delta[0]/length,delta[1]/length
        u=(ux,uy)
        extension=[0.0,0.0]
        for i,p in enumerate((a,b)):
            outward=-1 if i==0 else 1
            for k,(_oid,other) in enumerate(records):
                if k==index:continue
                c=tuple(map(float,other['a']));d=tuple(map(float,other['b']))
                vd=sub(d,c);vlen=math.hypot(*vd)
                if vlen<1e-8:continue
                v=(vd[0]/vlen,vd[1]/vlen)
                denom=cross(v,u)  # dot(u,normal of host axis)
                if abs(denom)<min_sine:continue
                normal=(-v[1],v[0]);rel=sub(p,c)
                station=rel[0]*v[0]+rel[1]*v[1]
                # The projection must fall on the host's finite reference
                # segment. Do not infer junctions beyond its real ends.
                if station < -tolerance or station > vlen+tolerance:continue
                signed=rel[0]*normal[0]+rel[1]*normal[1]
                t=float(other['thickness'])
                ref=other.get('reference','eje')
                if ref=='eje': offsets=(-t/2,t/2)
                elif ref=='izquierda':offsets=(0.,t)
                elif ref=='derecha':offsets=(-t,0.)
                else:continue
                # Only endpoints actually in the cross-section of the other
                # wall can be completed. No arbitrary 15-cm snap tolerance.
                if signed<min(offsets)-tolerance or signed>max(offsets)+tolerance:
                    continue
                # Parametric displacement from this end to the TWO host faces.
                distances=[outward*(offset-signed)/denom for offset in offsets]
                extension[i]=max(extension[i],0.,*distances)
        aa=(a[0]-ux*extension[0],a[1]-uy*extension[0])
        bb=(b[0]+ux*extension[1],b[1]+uy*extension[1])
        result.append((ident,wall_corners(aa,bb,info['thickness'],info.get('reference','eje'))))
    return result


def _polygon(entity):
    return [tuple(p[:2]) for p in entity.get_points('xy')]


def _on_edge(point, a, b, tol=1e-6):
    """True when point belongs to the finite source edge within tolerance."""
    dx, dy = b[0]-a[0], b[1]-a[1]
    length2 = dx*dx+dy*dy
    if length2 < tol*tol:
        return False
    t = ((point[0]-a[0])*dx + (point[1]-a[1])*dy)/length2
    return -tol <= t <= 1+tol and abs(cross(sub(point,a),(dx,dy))) <= tol*math.sqrt(length2)


def segment_owners(a, b, walls):
    """Source BIM wall ids for a regenerated boundary segment.

    A shared boundary may correspond to multiple walls; never silently pick
    one for editing. `walls` is a sequence of (id, closed footprint).
    """
    mid = interp(a,b,.5)
    return sorted({ident for ident, poly in walls
                   if ident and any(_on_edge(mid,c,d) and _on_edge(a,c,d)
                                    and _on_edge(b,c,d)
                                    for c,d in polygon_edges(poly))})

class RegenerateContoursCommand(Command):
    name='ARQ REGENERAR ENCUENTROS'
    # Lines erased and redrawn plus a layer switched off: the overlay cannot
    # show that, only a regen can (without it UNIONESARQ looked like a no-op
    # until the user regenerated the screen).
    needs_regen = True
    def __init__(self):
        self.old_segments=None
        self.old_layer_off=None
    def _current(self,msp):
        from .architectural import metadata
        return [e for e in msp if (metadata(e) or {}).get('kind')=='junction_edge']
    def _clear(self,msp):
        current=self._current(msp)
        self.removed_handles=[e.dxf.handle for e in current]
        for e in current:msp.delete_entity(e)
    def _draw(self,msp,segments,wall_sources=(),restore=False):
        from .architectural import _xdata
        for record in segments:
            if restore:
                a,b,attrs,meta=record
            else:
                a,b,*given_ids=record
                attrs={'layer':'ARQ-MUROS'}
                meta={'kind':'junction_edge','schema':3,
                      'wall_ids':given_ids[0] if given_ids else segment_owners(a,b,wall_sources)}
            e=msp.add_line(a,b,dxfattribs=attrs)
            _xdata(msp,e,meta)
    def do(self,document):
        from .architectural import metadata,WALL_LAYER
        msp=document.doc.modelspace()
        if self.old_segments is None:
            import copy
            self.old_segments=[((e.dxf.start.x,e.dxf.start.y),(e.dxf.end.x,e.dxf.end.y),
                                {'layer':e.dxf.layer,'color':e.dxf.get('color',256),
                                 'linetype':e.dxf.get('linetype','ByLayer')},
                                copy.deepcopy(metadata(e))) for e in self._current(msp)]
            self.old_layer_off=document.doc.layers.get(WALL_LAYER).is_off() if WALL_LAYER in document.doc.layers else False
        # v1.6: one footprint per element from geom.junctions (the same
        # polygons go to IngeTrazo through exchange.py). CAD axes first.
        from .exchange import read_model
        from .geom import junctions as J
        records, columns, _ops, issues = read_model(document.doc, strict=False)
        result = J.solve(J.walls_from_records(records),
                         [(cid, m["polygon"]) for cid, m in columns])
        self.issues = issues + result.warnings
        self.result = result
        walls = [w for w in result.walls.values() if w["area"] > 0]
        new = J.plan_outline(result)
        if walls and not new:
            raise ValueError('No se obtuvo contorno exterior: se conserva la geometría original')
        try:
            self._clear(msp)
            self._draw(msp,new)
            if walls and WALL_LAYER in document.doc.layers:
                document.doc.layers.get(WALL_LAYER).off()
            document.dirty=True
            self.new_count=len(new)
        except Exception:
            # A failed derived update must not leave the model invisible.
            self._clear(msp)
            if self.old_segments:
                from .architectural import _xdata
                for a,b,attrs,meta in self.old_segments:
                    _xdata(msp, msp.add_line(a,b,dxfattribs=attrs), meta)
            if WALL_LAYER in document.doc.layers:
                layer=document.doc.layers.get(WALL_LAYER)
                layer.off() if self.old_layer_off else layer.on()
            raise
    def undo(self,document):
        from .architectural import WALL_LAYER
        msp=document.doc.modelspace();self._clear(msp)
        if self.old_segments:self._draw(msp,self.old_segments,restore=True)
        if WALL_LAYER in document.doc.layers:
            layer=document.doc.layers.get(WALL_LAYER)
            layer.off() if self.old_layer_off else layer.on()
        document.dirty=True

def regenerate_wall_outline(ctx):
    """Refresh joined wall boundary through normal IngeCAD undo history."""
    from .compat import require_document
    from core.layers import NewLayerCommand
    doc=require_document(ctx)
    if 'ARQ-MUROS' not in doc.doc.layers:
        ctx.execute(NewLayerCommand('ARQ-MUROS',color=8))
    cmd=RegenerateContoursCommand()
    ctx.execute(cmd)
    return cmd.new_count, getattr(cmd, 'issues', [])

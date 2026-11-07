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
    """UNIONESARQ: one undoable step that

    1. makes XDATA true to the drawing (copies get a new identity, moved
       axes/columns update a/b/center) -- see ``sync.sync_changes``;
    2. solves the junctions and redraws the plan outline (ARQ-MUROS);
    3. rebuilds one selectable group per wall (axis + its plan lines), so a
       pick on any visible line selects the whole wall;
    4. recomputes every space (room) from its seed point: outline, area and
       label follow the walls.

    Like IngeCAD's own ERASE, old lines are UNLINKED and kept, never
    destroyed: undo/redo put back the very same entities. That matters when
    this runs as a follow-up of the user's COPY (reactor): undoing the COPY
    must find its copied lines alive."""
    name='ARQ REGENERAR ENCUENTROS'
    # Lines erased and redrawn plus a layer switched off: the overlay cannot
    # show that, only a regen can (without it UNIONESARQ looked like a no-op
    # until the user regenerated the screen).
    needs_regen = True
    def __init__(self):
        self.removed=None       # old plan lines (unlinked, kept alive)
        self.added=[]           # new plan lines
        self.old_groups=None    # [(name, [handles], description)]
        self.old_layer_off=None
        self.sync=None          # [(entity, old_meta, new_meta)], fixed on first do
        self.groups=[]
        self.issues=[]
        self.new_count=0
        self.removed_handles=[]
        self.space_edits=[]     # [(entity, old_meta, new_meta, old_pts, new_pts)]
        self.added_labels=[]
        self.space_count=0
        self.opening_edits=[]   # [(entity, old_meta, new_meta, old_pts, new_pts)]
        self.orphans=[]         # openings whose wall was erased (unlinked)
        self.old_opening_layer_off=None
    def _current(self,msp,kind='junction_edge'):
        from .architectural import metadata
        return [e for e in msp if (metadata(e) or {}).get('kind')==kind]
    def _plan_spaces(self,document,result):
        """Space outlines/areas from their seeds (first do only)."""
        import copy
        from .architectural import metadata
        from .geom import spaces as SP
        comps=SP.components(result)
        seen={}
        for e in self._current(document.doc.modelspace(),'space'):
            m=metadata(e)
            label=m.get('name') or 'Recinto'
            room,why=SP.space_at(result,m['seed'],comps)
            if room is None:
                self.issues.append(f'Recinto {label}: '+('su punto interior queda dentro de un muro o pilar'
                                   if why=='muro' else 'no está cerrado (falta un muro o una separación)')
                                   +'; se conserva su contorno anterior')
                continue
            key=tuple(P_key(q) for q in room['outer'])
            if key in seen:
                self.issues.append(f'Recintos {seen[key]} y {label} ocupan la misma estancia')
            seen.setdefault(key,label)
            from . import superficies as SU
            room_u=SP.space_at(self.useful,m['seed'])[0] if getattr(self,'useful',None) is not None else None
            ev=SU.evaluate(m,room,room_u)
            new=copy.deepcopy(m)
            new.update(useful_area=ev['useful'],computable_area=ev['computable'])
            new.update(area=room['area'],perimeter=room['perimeter'],
                       islands=[[list(q) for q in h] for h in room['holes']],
                       ref_vertex=list(room['outer'][0]))
            pts=[tuple(q) for q in room['outer']]
            old_pts=[tuple(map(float,q)) for q in e.get_points('xy')]
            if new!=m or old_pts!=pts:
                self.space_edits.append((e,copy.deepcopy(m),new,old_pts,pts))
        self.space_count=len(self._current(document.doc.modelspace(),'space'))
    def _plan_openings(self,document,records):
        """Carrier of every door/window true to its wall (first do only).

        * the wall moved/rotated/stretched (MOVE of its group): the opening
          keeps its offset and its carrier is redrawn on the wall;
        * the carrier itself was moved/copied (MOVE/COPY of the door): its
          new position along the wall (or along another wall it now lies
          on) becomes the offset; a mirrored carrier swaps the hinge;
        * the wall was erased: the opening goes with it;
        * an older record (schema 2) is upgraded to schema 3."""
        import copy,math
        from .architectural import metadata
        from .geom import junctions as J
        from . import openings as OP
        specs={w.id:w for w in J.walls_from_records(records)}
        olds={}
        for e,old,new in self.sync or []:
            if (old or {}).get('kind')=='wall' and old.get('id')==new.get('id'):
                try:
                    olds[old['id']]=J.walls_from_records([(old['id'],old)])[0]
                except Exception:
                    pass
        self.opening_specs=specs
        news={}
        for e in self._current(document.doc.modelspace(),'opening'):
            m=metadata(e)
            label=m.get('name') or OP.NAMES.get(m.get('type'),'Carpintería')
            host=specs.get(m.get('wall_id'))
            pts=None
            if e.dxftype()=='LWPOLYLINE' and int(m.get('schema') or 2)>=3 and len(e)==2 and not e.closed:
                pts=[tuple(map(float,q)) for q in e.get_points('xy')]
            if host is None and pts is None:
                self.orphans.append(e)
                continue
            new=OP.normalise(copy.deepcopy(m))
            width=float(new['width'])
            if pts is not None:
                before=olds.get(new['wall_id'],host)
                same=before is not None and all(math.dist(p,q)<1e-6 for p,q in zip(pts,OP.carrier_points(before,new)))
                if not same:
                    best=None
                    for w in specs.values():
                        # both ends of the carrier lie on the wall's middle line
                        # (a chord of it on a curved wall)
                        (sa,oa),(sb,ob)=w.local(pts[0]),w.local(pts[1])
                        s=(sa+sb)/2
                        d=max(abs(oa-(w.lo+w.hi)/2),abs(ob-(w.lo+w.hi)/2))
                        if d<=(w.hi-w.lo)/2+1e-6 and -1e-6<=s<=w.length+1e-6:
                            key=(0 if w.id==new['wall_id'] else 1,d)
                            if best is None or key<best[0]:
                                best=(key,w,s)
                    if best is None:
                        if host is None:
                            self.orphans.append(e)
                            continue
                        self.issues.append(f'{label}: quedó fuera de su muro; vuelve a su posición')
                    else:
                        _k,host,s=best
                        new['wall_id']=host.id
                        new['offset']=s-width/2
                        dx,dy=pts[1][0]-pts[0][0],pts[1][1]-pts[0][1]
                        if dx*host.u[0]+dy*host.u[1]<0:
                            new['hinge']=1-int(new.get('hinge') or 0)     # mirrored
            if host is None:
                self.orphans.append(e)
                continue
            if new['offset']<-1e-9 or new['offset']+width>host.length+1e-9:
                self.issues.append(f'{label}: no cabe en su muro; se ajusta a su longitud')
                new['offset']=min(max(0.0,new['offset']),max(0.0,host.length-width))
            new_pts=OP.carrier_points(host,new)
            old_pts=[tuple(map(float,q)) for q in e.get_points('xy')] if e.dxftype()=='LWPOLYLINE' else None
            news.setdefault(new['wall_id'],[]).append(new)
            if new!=m or old_pts!=new_pts:
                self.opening_edits.append((e,copy.deepcopy(m),new,old_pts,new_pts))
        for wid,ops in news.items():
            ops.sort(key=lambda o:float(o['offset']))
            for a,b in zip(ops,ops[1:]):
                if float(a['offset'])+float(a['width'])>float(b['offset'])+1e-6:
                    self.issues.append(f"Carpinterías solapadas en el muro {wid[:8]}: "
                                       f"{a.get('name') or OP.NAMES[a['type']]} y {b.get('name') or OP.NAMES[b['type']]}")
        self.opening_records=news
        if self.orphans:
            self.issues.append(f'{len(self.orphans)} carpintería(s) eliminada(s) con su muro')
    def _apply_openings(self,document,which):
        from .architectural import _xdata
        msp=document.doc.modelspace()
        items=self.opening_edits if which=='new' else list(reversed(self.opening_edits))
        for e,old,new,old_pts,new_pts in items:
            if not e.is_alive:
                continue
            pts=new_pts if which=='new' else old_pts
            if pts is not None and e.dxftype()=='LWPOLYLINE':
                e.set_points(pts,format='xy')
                if which=='new':
                    e.closed=False
            _xdata(msp,e,new if which=='new' else old)
    def _opening_cuts(self):
        from . import openings as OP
        ops=[o for lst in getattr(self,'opening_records',{}).values() for o in lst]
        return OP.opening_cuts(self.opening_specs,ops)
    def _new_symbols(self,document):
        """Plan drawing of every door/window (frame, leaves and swing,
        glazing, sill), derived from its record."""
        from .architectural import _xdata
        from . import openings as OP
        msp=document.doc.modelspace()
        made=[]
        for wid,ops in getattr(self,'opening_records',{}).items():
            spec=self.opening_specs.get(wid)
            if spec is None:
                continue
            for o in ops:
                for item in OP.plan_symbol(spec,o):
                    attribs={'layer':OP.SYMBOL_LAYER}
                    if item[0]=='line':
                        d=msp.add_line(item[1],item[2],dxfattribs=attribs)
                    elif item[0]=='poly':
                        d=msp.add_lwpolyline(item[1],close=item[2],dxfattribs=attribs)
                    else:
                        d=msp.add_arc(item[1],item[2],item[3],item[4],dxfattribs=attribs)
                    _xdata(msp,d,{'kind':'opening_symbol','schema':1,'opening_id':o['id']})
                    made.append(d)
        return made
    def _apply_spaces(self,document,which):
        from .architectural import _xdata
        msp=document.doc.modelspace()
        items=self.space_edits if which=='new' else list(reversed(self.space_edits))
        for e,old,new,old_pts,new_pts in items:
            if not e.is_alive:
                continue
            e.set_points(new_pts if which=='new' else old_pts,format='xy')
            e.closed=True
            _xdata(msp,e,new if which=='new' else old)
    def _new_labels(self,document):
        from .architectural import metadata,_xdata
        msp=document.doc.modelspace()
        made=[]
        for e in self._current(msp,'space'):
            m=metadata(e)
            useful=float(m.get('useful_area',m.get('area',0)))
            comp=float(m.get('computable_area',useful))
            text=f"{m.get('name') or 'Recinto'}  {useful:.2f} m²"
            if abs(comp-useful)>1e-9:
                text+=f" (computa {comp:.2f})"
            text=text.replace('.',',')
            t=msp.add_text(text,dxfattribs={'layer':e.dxf.layer,'height':0.20})
            t.set_placement((float(m['seed'][0]),float(m['seed'][1])),align=_MIDDLE_CENTER())
            _xdata(msp,t,{'kind':'space_label','schema':1,'space_id':m['id']})
            made.append(t)
        return made
    def _new_lines(self,msp,segments):
        from .architectural import _xdata
        made=[]
        for item in segments:
            if item[0]=='arc':
                _k,c,r,t0,t1,ids=item[:6]
                e=msp.add_arc(c,r,t0,t1,dxfattribs={'layer':'ARQ-MUROS'})
            else:
                _k,a,b,ids=item
                e=msp.add_line(a,b,dxfattribs={'layer':'ARQ-MUROS'})
            _xdata(msp,e,{'kind':'junction_edge','schema':3,'wall_ids':ids})
            made.append(e)
        return made
    def _write_meta(self,document,which):
        from .architectural import _xdata
        msp=document.doc.modelspace()
        items=self.sync if which=='new' else list(reversed(self.sync))
        for e,old,new in items:
            if e.is_alive:
                _xdata(msp,e,new if which=='new' else old)
    def _group_lines(self,document):
        from .architectural import metadata
        from . import sync as SY
        SY.delete_groups(document.doc)
        by_wall={}
        for e in self.added:
            for ident in (metadata(e) or {}).get('wall_ids') or []:
                by_wall.setdefault(ident,[]).append(e)
        self.groups=SY.build_wall_groups(document.doc,by_wall)
        # a steel or covered column: its outline + the drawn profile, one pick
        details={}
        for e in self.added_labels:
            md=metadata(e) or {}
            cid=md.get('column_id') or md.get('opening_id')
            if cid: details.setdefault(cid,[]).append(e)
        for e in self._current(document.doc.modelspace(),'opening'):
            m=metadata(e)
            if m.get('id') in details:
                name=SY.GROUP_PREFIX+str(e.dxf.handle).upper()
                SY.create_group(document.doc,name,[e,*details[m['id']]],
                                f"{m.get('name') or 'Carpinteria'} BIM {m['id'][:8]} (Arquitectura)")
                self.groups.append(name)
        for e in self._current(document.doc.modelspace(),'column'):
            m=metadata(e)
            if m.get('id') in details:
                name=SY.GROUP_PREFIX+str(e.dxf.handle).upper()
                SY.create_group(document.doc,name,[e,*details[m['id']]],
                                f"{m.get('name') or 'Pilar'} BIM {m['id'][:8]} (Arquitectura)")
                self.groups.append(name)
    def _new_details(self,document):
        """Plan drawing of what is inside a column's outline: the steel
        profile(s), or the concrete section inside its covering."""
        from .architectural import metadata,_xdata
        from .sections import column_geometry
        msp=document.doc.modelspace()
        made=[]
        for e in self._current(msp,'column'):
            m=metadata(e)
            if m.get('shape')!='steel' and not float(m.get('cover') or 0):
                continue
            try:
                secs=column_geometry(m['center'],m)['sections']
            except Exception:
                continue
            for sec in secs:
                d=msp.add_lwpolyline(sec,close=True,dxfattribs={'layer':e.dxf.layer})
                _xdata(msp,d,{'kind':'column_detail','schema':1,'column_id':m['id']})
                made.append(d)
        return made
    def do(self,document):
        import copy
        from .architectural import metadata,WALL_LAYER
        msp=self.space(document)
        first=self.removed is None
        if first:
            from . import sync as SY
            self.removed=self._current(msp)
            self.opening_edits=[];self.orphans=[]
            self.old_groups=SY.snapshot_groups(document.doc)
            self.old_layer_off=document.doc.layers.get(WALL_LAYER).is_off() if WALL_LAYER in document.doc.layers else False
            self.sync=[(e,copy.deepcopy(metadata(e)),new) for e,new in SY.sync_changes(document.doc)]
            self.removed_labels=(self._current(msp,'space_label')+self._current(msp,'column_detail')
                                 +self._current(msp,'opening_symbol'))
            from .architectural import OPENING_LAYER
            self.old_opening_layer_off=(document.doc.layers.get(OPENING_LAYER).is_off()
                                        if OPENING_LAYER in document.doc.layers else None)
        self._write_meta(document,'new')
        try:
            if first:
                # v1.6: one footprint per element from geom.junctions (the same
                # polygons go to IngeTrazo through exchange.py). CAD axes first.
                from .exchange import read_model
                from .geom import junctions as J
                records, columns, _ops, issues = read_model(document.doc, strict=False)
                specs = J.walls_from_records(records)
                result = J.solve(specs, [(cid, m["polygon"]) for cid, m in columns])
                from .superficies import useful_result
                self.useful = useful_result(specs, columns)
                self.issues = issues + result.warnings
                self.result = result
                walls = [w for w in result.walls.values() if w["area"] > 0]
                self._plan_openings(document,records)
                segments = J.plan_items(result, self._opening_cuts())
                if walls and not segments:
                    raise ValueError('No se obtuvo contorno exterior: se conserva la geometría original')
                self.has_walls = bool(walls)
                self._plan_spaces(document,result)
            from . import sync as SY
            SY.delete_groups(document.doc)
            for e in self.removed:
                if e.is_alive and e.dxf.owner is not None:
                    msp.unlink_entity(e)
            for e in self.removed_labels:
                if e.is_alive and e.dxf.owner is not None:
                    msp.unlink_entity(e)
            for e in self.orphans:
                if e.is_alive and e.dxf.owner is not None:
                    msp.unlink_entity(e)
            self._apply_spaces(document,'new')
            self._apply_openings(document,'new')
            if first:
                from .openings import SYMBOL_LAYER
                if SYMBOL_LAYER not in document.doc.layers:
                    document.doc.layers.add(SYMBOL_LAYER,color=6)
                self.added=self._new_lines(msp,segments)
                self.added_labels=(self._new_labels(document)+self._new_details(document)
                                   +self._new_symbols(document))
            else:
                for e in self.added+self.added_labels:
                    msp.add_entity(e)
            self._group_lines(document)
            if self.has_walls and WALL_LAYER in document.doc.layers:
                document.doc.layers.get(WALL_LAYER).off()
            from .architectural import OPENING_LAYER
            if getattr(self,'opening_records',None) and OPENING_LAYER in document.doc.layers:
                document.doc.layers.get(OPENING_LAYER).off()
            self.removed_handles=[e.dxf.handle for e in self.removed]
            self.new_count=len(self.added)
            document.dirty=True
        except Exception:
            # A failed derived update must not leave the model invisible
            # nor half-synchronised.
            self._revert(document)
            if first:
                self.removed=None
            raise
    def _revert(self,document):
        from .architectural import WALL_LAYER
        from . import sync as SY
        msp=self.space(document)
        SY.delete_groups(document.doc)
        for e in self.added+self.added_labels:
            if e.is_alive and e.dxf.owner is not None:
                msp.unlink_entity(e)
        for e in (self.removed or [])+getattr(self,'removed_labels',[]):
            if e.is_alive and e.dxf.owner is None:
                msp.add_entity(e)
        self._apply_spaces(document,'old')
        self._apply_openings(document,'old')
        for e in self.orphans:
            if e.is_alive and e.dxf.owner is None:
                msp.add_entity(e)
        from .architectural import OPENING_LAYER
        if OPENING_LAYER in document.doc.layers and self.old_opening_layer_off is not None:
            layer=document.doc.layers.get(OPENING_LAYER)
            layer.off() if self.old_opening_layer_off else layer.on()
        db=document.doc.entitydb
        for name,handles,desc in self.old_groups or []:
            SY.create_group(document.doc,name,[db.get(h) for h in handles],desc)
        if WALL_LAYER in document.doc.layers and self.old_layer_off is not None:
            layer=document.doc.layers.get(WALL_LAYER)
            layer.off() if self.old_layer_off else layer.on()
        if self.sync:
            self._write_meta(document,'old')
        self.removed_handles=[e.dxf.handle for e in self.added if e.is_alive]
        document.dirty=True
    def undo(self,document):
        self._revert(document)

def P_key(q, nd=7):
    return (round(float(q[0]), nd), round(float(q[1]), nd))


def _MIDDLE_CENTER():
    from ezdxf.enums import TextEntityAlignment
    return TextEntityAlignment.MIDDLE_CENTER


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


def sync_report(cmd):
    """Human summary of what UNIONESARQ repaired before regenerating."""
    copies=sum(1 for _e,o,n in (cmd.sync or []) if (o or {}).get('id')!=n.get('id'))
    moved=len(cmd.sync or [])-copies
    return copies, moved, len(getattr(cmd,'groups',[]) or [])

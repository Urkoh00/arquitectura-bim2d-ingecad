# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: LA REGENERACIÓN: tras cada cambio rehace contornos de muros, recintos, rótulos, símbolos y
#   grupos de selección (y UNIONESARQ).
#   (Guía del código: docs/GUIA_DEL_CODIGO.md)
"""Regeneration of the derived plan drawing (UNIONESARQ and every
architectural change): wall outlines from geom.junctions, room outlines,
labels, opening symbols and selection groups, in one undoable step.

The DXF wall entities remain authoritative; outlines are regenerated, never
treated as new BIM objects. (v1.28: the old polygon helpers that predated
geom.junctions were removed; nothing used them.)
"""
from __future__ import annotations
from core.commands import Command

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
        self.layer_routes=None
    def _current(self,msp,kind='junction_edge'):
        from .architectural import metadata
        return [e for e in msp if (metadata(e) or {}).get('kind')==kind]
    def _plan_spaces(self,document,result):
        """Space outlines/areas from their seeds (first do only)."""
        import copy
        from .architectural import metadata
        from . import space_envelope as SE
        limits=SE.boundaries(document.doc)
        from . import cabinets as C
        cabinet_items=C.placed(document.doc)
        seen={}
        for e in self._current(document.doc.modelspace(),'space'):
            m=metadata(e)
            label=m.get('name') or 'Recinto'
            room,why=SE.outline(m,result,e)
            if room is None:
                self.issues.append(f'Recinto {label}: '+('su punto interior queda dentro de un muro o pilar'
                                   if why=='muro' else 'no está cerrado (falta un muro o una separación)')
                                   +'; se conserva su contorno anterior')
                continue
            key=(round(float(m.get('base',0)),7),tuple(P_key(q) for q in room['outer']))
            if key in seen:
                self.issues.append(f'Recintos {seen[key]} y {label} ocupan la misma estancia')
            seen.setdefault(key,label)
            from . import superficies as SU
            room_u=SE.outline(m,self.useful,e)[0] if getattr(self,'useful',None) is not None else None
            envelope=SE.resolve(m,room,limits)
            from . import cabinets as C
            # el espacio llega a los muros (criterio de CYPE); los armarios
            # solo cuentan en la superficie útil, según el proyecto
            obstacles=C.obstacles(document.doc,SE.effective(m,envelope),room,cabinet_items)
            from .parameters_arq import general_options
            room_u=C.useful_by_criterion(room_u or room,obstacles,
                                         general_options(document.doc).get('armarios_superficie_util','descuentan'))
            ev=SU.evaluate(SE.effective(m,envelope),room,room_u,by_use=getattr(self,'by_use',None))
            new=copy.deepcopy(m)
            if m.get('boundary_mode')=='polyline':
                from .geom import polygon as P
                new['boundary']=[list(q) for q in room['outer']]
                if not P.point_in_polygon(m['seed'],room['outer']):
                    piece=max(room['pieces'],key=P.area)
                    new['seed']=[sum(q[i] for q in piece)/len(piece) for i in (0,1)]
            new.update(upper_limit=envelope['upper_limit'],upper_limit_ids=envelope['upper_limit_ids'],
                       lower_limit_ids=envelope['lower_limit_ids'],free_height=envelope['height'],net_volume=envelope['volume'])
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
        for e,old,new,_fr in self.sync or []:
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
                if a.get('cabinet_mode')==b.get('cabinet_mode')=='adosado' and a.get('side')!=b.get('side'):continue
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
    def _new_lines(self,msp,segments,display_level_id=None):
        from .architectural import _xdata
        made=[]
        from .architectural import metadata
        from .wall_categories import category,LAYERS
        records={m['id']:m for e in msp if (m:=metadata(e)or{}).get('kind')=='wall'}
        for item in segments:
            ids=item[5] if item[0]=='arc' else item[3]
            layers=sorted({LAYERS[category(records.get(i,{}))] for i in ids}) or ['ARQ-MUROS']
            for layer in layers:
                if layer not in msp.doc.layers:msp.doc.layers.add(layer,color=8)
            layer=layers[0]
            if item[0]=='arc':
                _k,c,r,t0,t1,ids=item[:6]
                e=msp.add_arc(c,r,t0,t1,dxfattribs={'layer':layer})
            else:
                _k,a,b,ids=item
                e=msp.add_line(a,b,dxfattribs={'layer':layer})
            self.added.append(e)        # journalled at once: a failure further on removes it
            _xdata(msp,e,{'kind':'junction_edge','schema':3,'wall_ids':ids,**({'display_level_id':display_level_id}if display_level_id else{})})
            made.append(e)
        return made
    def _write_meta(self,document,which):
        from .architectural import _xdata
        msp=document.doc.modelspace()
        from .frame import FRAME_APPID
        items=self.sync if which=='new' else list(reversed(self.sync))
        for e,old,new,old_frame in items:
            if e.is_alive:
                _xdata(msp,e,new if which=='new' else old)
                if which!='new' and old_frame is not None:
                    # back to the frame IngeCAD's transformation left, so its
                    # own undo (it applies the inverse) finds it as it was
                    e.set_xdata(FRAME_APPID,old_frame)
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
        # what there was before, to leave it exactly so if anything fails (0006)
        baseline_handles={e.dxf.handle for e in msp}
        baseline_layers={layer.dxf.name for layer in document.doc.layers}
        if first:
            from . import sync as SY
            self.removed=self._current(msp)
            self.opening_edits=[];self.orphans=[]
            self.old_groups=SY.snapshot_groups(document.doc)
            self.old_layer_off=document.doc.layers.get(WALL_LAYER).is_off() if WALL_LAYER in document.doc.layers else False
            self.sync_notes=[]
            from .frame import FRAME_APPID
            def _frame(e):
                try:
                    return [(t.code,tuple(t.value)) for t in e.get_xdata(FRAME_APPID)] if e.has_xdata(FRAME_APPID) else None
                except Exception:
                    return None
            self.sync=[(e,copy.deepcopy(metadata(e)),new,_frame(e))
                       for e,new in SY.sync_changes(document.doc,notes=self.sync_notes)]
            self.removed_labels=(self._current(msp,'space_label')+self._current(msp,'column_detail')
                                 +self._current(msp,'opening_symbol'))
            from .architectural import OPENING_LAYER
            self.old_opening_layer_off=(document.doc.layers.get(OPENING_LAYER).is_off()
                                        if OPENING_LAYER in document.doc.layers else None)
        try:
            self._write_meta(document,'new')
            if first:
                # v1.6: one footprint per element from geom.junctions (the same
                # polygons go to IngeTrazo through exchange.py). CAD axes first.
                from .exchange import read_model
                from .geom import junctions as J
                records, columns, _ops, issues = read_model(document.doc, strict=False)
                specs = J.walls_from_records(records)
                from .geom.bands import solve_records
                from . import particiones_virtuales as VP
                result = solve_records(records, columns, VP.read(document.doc))   # by height bands
                from .superficies import useful_result
                self.useful = useful_result(specs, columns, records=records,
                                            partitions=result.virtual_partitions)
                from .parameters_arq import general_options
                self.by_use = general_options(document.doc)["usar_usos"]
                self.issues = issues + result.warnings + getattr(self,'sync_notes',[])
                self.result = result
                walls = [w for w in result.walls.values() if w["area"] > 0]
                self._plan_openings(document,records)
                segments = J.plan_items(result, self._opening_cuts())
                from .levels import load
                from .geom import spaces as SP
                data=load(document)
                self.level_segments=None
                if data.get('layer_managed'):
                    self.level_segments=[(lv['id'],J.plan_items(SP.network_at(result,lv['elevation']+1e-7),self._opening_cuts()))for lv in data['levels']]
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
                if self.level_segments is None:self.added=self._new_lines(msp,segments)
                else:
                    for ident,items in self.level_segments:self._new_lines(msp,items,ident)
                self.added_labels=(self._new_labels(document)+self._new_details(document)
                                   +self._new_symbols(document))
            else:
                for e in self.added+self.added_labels:
                    msp.add_entity(e)
            self._group_lines(document)
            from .level_layers import RouteLevels
            if self.layer_routes is None:self.layer_routes=RouteLevels()
            self.layer_routes.do(document)
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
            # nor half-synchronised: whatever was created before the failure
            # goes too (also what a helper made but did not hand back).
            for entity in list(msp):
                if (entity.dxf.handle not in baseline_handles and entity not in self.added
                        and entity not in self.added_labels):
                    self.added_labels.append(entity)
            self._revert(document)
            for layer in list(document.doc.layers):
                if layer.dxf.name not in baseline_layers:
                    try:
                        document.doc.layers.remove(layer.dxf.name)
                    except Exception:
                        pass
            if first:
                for entity in self.added+self.added_labels:
                    if entity.is_alive and entity.dxf.get('owner') is None:
                        document.doc.entitydb.delete_entity(entity)
                self.added=[];self.added_labels=[]
                self.removed=None
            raise
    def _revert(self,document):
        from .architectural import WALL_LAYER
        from . import sync as SY
        msp=self.space(document)
        if self.layer_routes is not None:self.layer_routes.undo(document)
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


def sync_report(cmd):
    """Human summary of what UNIONESARQ repaired before regenerating."""
    copies=sum(1 for _e,o,n,_f in (cmd.sync or []) if (o or {}).get('id')!=n.get('id'))
    moved=len(cmd.sync or [])-copies
    return copies, moved, len(getattr(cmd,'groups',[]) or [])

# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only classification/preview and explicit commit, using the existing reader.

No external recognizer is copied. INSERT contents are read virtually and never
hidden; ambiguous/unsupported categories remain visible for manual processing.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import copy
import math

ROLES = {'muros': 'Muros', 'medianeras': 'Medianeras', 'tabiques': 'Tabiques',
         'pilares': 'Pilares',
         'carpinteria': 'Carpintería (puerta o ventana según el dibujo)',
         'ventanas': 'Ventanas', 'puertas': 'Puertas',
         'vanos': 'Vanos', 'rejas': 'Rejas', 'barandillas': 'Barandillas',
         'escaleras': 'Escaleras'}
WALLS = {'muros', 'medianeras', 'tabiques'}
MANUAL = {'rejas', 'barandillas', 'escaleras'}
OPENINGS = {'carpinteria', 'puertas', 'ventanas', 'vanos'}
VOTES = {'puertas': 'door', 'ventanas': 'window', 'vanos': 'void'}   # «carpinteria» no vota
BLOCK_DEPTH = 4


@dataclass
class Classification:
    layers: dict = field(default_factory=dict)
    handles: dict = field(default_factory=dict)
    layers_confirmed: bool = False

    def role(self, entity):
        return self.handles.get(entity.dxf.handle, self.layers.get(entity.dxf.layer))

    def leaf_role(self, part, insert_layer, forced):
        """Role of an entity read inside a block: a graphical assignment of the
        block reference wins; otherwise the entity's OWN layer (layer «0» takes the
        reference's layer, as in DXF)."""
        if forced:
            return forced
        layer = part.dxf.layer
        return self.layers.get(insert_layer if layer == '0' else layer)

    def assign(self, handles, role):
        if role not in ROLES:
            raise ValueError('Categoría no válida')
        for h in handles:
            self.handles[str(h)] = role


@dataclass
class Plan:
    result: tuple
    sources: list
    warnings: list
    drawing: object
    fingerprint: str
    window: tuple
    height: float
    origin: str
    wall_roles: list = field(default_factory=list)
    curved_openings: list = field(default_factory=list)
    _preview_symbols: object = field(default=None,init=False,repr=False)

    @property
    def segments(self):
        from .geom.junctions import Wall
        lines = [(a, b) for a, b, _t in self.result[0]]
        for a,b,t,bulge in self.result[3]:
            spec=Wall('preview',a,b,t,'eje',bulge=bulge)
            points=spec.run(0.,a,b)
            lines.extend(zip(points,points[1:]))
        return lines + [s for group in self.opening_symbols().values() for s in group]

    def opening_symbols(self):
        """Native carpentry symbols, flattened only for tool feedback.

        No entities or annotation system are added to the drawing. An X
        identifies an unfilled opening. Works through preview_segments on
        both supported hosts without requiring custom overlay colours.
        """
        if self._preview_symbols is not None:return self._preview_symbols
        from .geom.junctions import Wall
        from . import openings as OP,convert_tools as C
        groups={'door':[],'window':[],'void':[]}
        walls=[Wall('preview',a,b,t,'eje') for a,b,t in self.result[0]]
        curves=[Wall('preview',a,b,t,'eje',bulge=bulge) for a,b,t,bulge in self.result[3]]
        for hosts,operations in ((walls,self.result[1]),(curves,self.curved_openings)):
            for k,pos,width,kind,hinge,side in operations:
                spec=hosts[k];s0,s1=pos-width/2,pos+width/2
                if kind=='void':
                    groups[kind].extend([(spec.point(s0,spec.lo),spec.point(s1,spec.hi)),
                                         (spec.point(s0,spec.hi),spec.point(s1,spec.lo))])
                    continue
                rec=OP.normalise({'type':kind,'offset':s0,'width':width,
                    'height':min(2.1,self.height),'sill':0.,'hinge':int(hinge>0),
                    'side':1 if side>=0 else -1,'chord':OP.chord_of(spec,width)})
                for glyph in OP.plan_symbol(spec,rec):
                    if glyph[0]=='line':groups[kind].append((glyph[1],glyph[2]))
                    elif glyph[0]=='poly':
                        points=glyph[1];groups[kind].extend(zip(points,points[1:]+(points[:1] if glyph[2] else [])))
                    elif glyph[0]=='arc':
                        center,r,a0,a1=glyph[1:]
                        a0,a1=math.radians(a0),math.radians(a1)
                        if a1<=a0:a1+=math.tau
                        groups[kind].extend(((s[0],s[1]),(s[2],s[3])) for s in C._flatten(center,r,a0,a1))
        self._preview_symbols=groups
        return groups


def layers_present(drawing):
    """Layers of the drawn entities, including those inside block references
    (a plan is often a block): the classification sheet lists them all."""
    found = set()

    def walk(entity, insert_layer, depth):
        layer = entity.dxf.layer
        if entity.dxftype() == 'INSERT':
            found.add(layer)
            if depth >= BLOCK_DEPTH:
                return
            try:
                for child in entity.virtual_entities():
                    walk(child, layer if layer != '0' else insert_layer, depth + 1)
            except Exception:
                pass
            return
        found.add(insert_layer if (layer == '0' and insert_layer) else layer)

    for e in drawing.modelspace():
        walk(e, None, 0)
    return sorted(found)


# Name hints, checked in this order (the first that matches wins). A carpentry
# layer goes to «carpinteria» (the drawing decides), not to doors or windows.
_GUESS = (('camara', None), ('cámara', None), ('aislam', None), ('cota', None),
          ('escal', 'escaleras'), ('barand', 'barandillas'), ('reja', 'rejas'),
          ('medianer', 'medianeras'), ('tabique', 'tabiques'),
          ('pilar', 'pilares'), ('soporte', 'pilares'),
          ('puert', 'puertas'), ('ventan', 'ventanas'), ('carp', 'carpinteria'),
          ('hueco', 'vanos'),
          ('pared', 'muros'), ('muro', 'muros'), ('cerramiento', 'muros'), ('fachada', 'muros'))


def guess_roles(layers):
    """{layer: role} proposed from the layer names; the operator confirms or
    changes them in the sheet. Layers with no hint are left out (not converted)."""
    out = {}
    for name in layers:
        n = str(name).lower()
        if n.startswith('arq-'):
            continue
        for hint, role in _GUESS:
            if hint in n:
                if role:
                    out[name] = role
                break
    return out


def fingerprint(drawing):
    """Conservative concurrency guard; includes source entity state, not file names."""
    import hashlib
    from ezdxf.lldxf.tagwriter import TagCollector
    digest = hashlib.sha256()
    for e in drawing.modelspace():
        digest.update(repr(TagCollector.dxftags(e)).encode())
    # INSERT references do not contain their definitions. Editing a nested
    # block after preview must invalidate the plan too, as must unit changes.
    for block in sorted(drawing.blocks, key=lambda b:b.name):
        digest.update(block.name.encode())
        digest.update(repr(TagCollector.dxftags(block.block)).encode())
        for e in block:
            digest.update(repr(TagCollector.dxftags(e)).encode())
    digest.update(repr(drawing.header.get('$INSUNITS',0)).encode())
    return digest.hexdigest()


def _outlines(entity):
    typ = entity.dxftype()
    if typ in ('SOLID', 'TRACE'):
        if any(abs(p.z)>1e-8 for p in entity.wcs_vertices()):
            raise ValueError('Relleno fuera del plano XY: revisión manual')
        return [[(float(p.x), float(p.y)) for p in entity.wcs_vertices()]]
    if typ == 'HATCH':
        # Reject holes/curved paths rather than filling them silently.
        paths = list(entity.paths)
        if len(paths) != 1:
            raise ValueError('Rayado con agujeros: revisión manual')
        if not hasattr(paths[0], 'vertices'):
            # A polygon made of native HATCH line edges needs no flattening.
            # Curved boundaries/holes stay manual rather than being filled.
            edges=list(paths[0].edges)
            if not edges or any(type(e).__name__!='LineEdge' for e in edges):
                raise ValueError('Rayado con aristas curvas: revisión manual')
            if any(math.dist(e.end,edges[(i+1)%len(edges)].start)>1e-8
                   for i,e in enumerate(edges)):
                raise ValueError('Contorno de rayado abierto: revisión manual')
            return [[tuple(e.start) for e in edges]]
        if any(abs(p[2]) > 1e-12 for p in paths[0].vertices):
            raise ValueError('Rayado curvo: revisión manual')
        return [[tuple(p[:2]) for p in paths[0].vertices]]
    return None


def hidden_layers(drawing):
    """Names of the layers switched off or frozen: what the operator has hidden
    is not converted (unless designated graphically)."""
    out = set()
    for layer in drawing.layers:
        try:
            if layer.is_off() or layer.is_frozen():
                out.add(layer.dxf.name)
        except Exception:
            pass
    return out


SWING_MIN = 0.35        # m: a door's swing (or a leaf) is never smaller than this


def scale_check(leaves):
    """ValueError when the plan is clearly not at full size in metres: the
    swings drawn in the carpentry are far too small for a door (a plan drawn at
    1:4, 1:5…, or in other units without $INSUNITS). Returns quietly otherwise."""
    radii = []
    for part, role in leaves:
        if role not in OPENINGS:
            continue
        try:
            if part.dxftype() == 'ARC' and part.dxf.end_angle != part.dxf.start_angle:
                radii.append(float(part.dxf.radius))
            elif part.dxftype() == 'LWPOLYLINE':
                pts = list(part.get_points('xyb'))
                for (x0, y0, b), (x1, y1, _b) in zip(pts, pts[1:]):
                    if abs(b) > 0.05:
                        chord = math.hypot(x1 - x0, y1 - y0)
                        radii.append(chord * (1 + b * b) / (4 * abs(b)))
        except Exception:
            continue
    if len(radii) < 2:
        return
    radii.sort()
    r = radii[len(radii) // 2]
    if r >= SWING_MIN or r <= 0:
        return
    k = max(2, round(0.8 / r))
    fmt = lambda v: f'{v:.3f}'.replace('.', ',')  # noqa: E731
    raise ValueError(
        f'el plano no parece estar a escala real en metros: los giros de las puertas miden '
        f'{fmt(r)} de radio y a escala real medirían en torno a 0,80. Probablemente está '
        f'dibujado a 1/{k}: escale el dibujo con ESCALA (factor {k}) desde un punto y repita '
        f'LINEASAMURO')


def analyse(drawing, lo, hi, classification, tmin=.07, tmax=.5, height=2.7,
            parallel=.005, origin='ocultar'):
    import ezdxf
    from . import convert_tools as C
    from .architectural import metadata
    if not (0 < tmin <= tmax and height > 0 and 0<=parallel<=.5 and all(map(math.isfinite, (tmin,tmax,height,parallel)))):
        raise ValueError('Dimensiones de conversión inválidas')
    if origin not in ('ocultar','conservar','borrar'):
        raise ValueError('Tratamiento de origen no válido')
    if int(drawing.header.get('$INSUNITS', 0)) not in (0, 6):
        raise ValueError('LINEASAMURO exige metros; convierta las unidades explícitamente')
    doc = ezdxf.new(); msp = doc.modelspace(); source_map = {}; warnings = []
    leaves = []          # (entity as read, role): votes and wall kinds, blocks included

    def category_of(role):
        if role not in ROLES:
            raise ValueError('Categoría no válida')
        return 'WALL' if role in WALLS else 'COLUMN' if role == 'pilares' else 'OPENING'

    hidden = hidden_layers(drawing)
    skipped = 0
    for e in drawing.modelspace():
        if metadata(e):
            continue
        if e.dxf.layer in hidden and e.dxf.handle not in classification.handles:
            skipped += 1
            continue
        role = classification.role(e)
        if e.dxftype() == 'INSERT':
            # a plan inside a block: each entity by its own layer, unless the
            # reference itself was designated graphically
            forced = classification.handles.get(e.dxf.handle)
            if forced is not None and forced not in ROLES:
                raise ValueError('Categoría no válida')
            if forced in MANUAL:
                warnings.append(f'{ROLES[forced]}: geometría original conservada; autoría BIM pendiente')
                continue
        elif not role:
            continue
        else:
            category_of(role)
            if role in MANUAL:
                warnings.append(f'{ROLES[role]}: geometría original conservada; autoría BIM pendiente')
                continue

        def emit(part, source, insert_layer, forced, depth=0):
            if part.dxftype()=='INSERT':
                if depth >= BLOCK_DEPTH:
                    warnings.append('Bloque anidado demasiado profundo; conservado')
                    return
                here = part.dxf.layer if part.dxf.layer != '0' else insert_layer
                try:
                    for child in part.virtual_entities():
                        emit(child, source, here, forced, depth+1)
                except Exception as exc:
                    warnings.append('Bloque no legible: '+type(exc).__name__)
                return
            if depth and not forced and part.dxf.layer in hidden:
                return
            leaf = classification.leaf_role(part, insert_layer, forced) if depth else role
            if not leaf:
                return
            if leaf in MANUAL:
                warnings.append(f'{ROLES[leaf]}: geometría original conservada; autoría BIM pendiente')
                return
            inherited = category_of(leaf)
            if inherited not in doc.layers:
                doc.layers.new(inherited)
            leaves.append((part, leaf))
            try:
                typ = part.dxftype()
                normal = part.dxf.get('extrusion', (0.,0.,1.))
                if any(abs(float(a)-b)>1e-8 for a,b in zip(normal,(0.,0.,1.))):
                    raise ValueError('Entidad fuera del plano XY: revisión manual')
                z = []
                if typ == 'LINE':z=[part.dxf.start.z,part.dxf.end.z]
                elif typ in ('ARC','CIRCLE'):z=[part.dxf.center.z]
                elif typ == 'LWPOLYLINE':z=[float(part.dxf.get('elevation',0.))]
                elif typ == 'HATCH':z=[part.dxf.elevation.z]
                if any(abs(float(v))>1e-8 for v in z):
                    raise ValueError('Entidad con elevación: revisión manual')
                outlines = _outlines(part)
            except ValueError as exc:
                warnings.append(str(exc));return
            entities = []
            if outlines:
                entities = [msp.add_lwpolyline(p, close=True, dxfattribs={'layer': inherited}) for p in outlines]
            elif part.dxftype() in ('LINE','ARC','LWPOLYLINE','CIRCLE'):
                v=part.copy();v.dxf.layer=inherited;msp.add_entity(v);entities=[v]
            for v in entities:
                source_map[v.dxf.handle] = source
        if e.dxftype() == 'INSERT':
            emit(e, e, e.dxf.layer, classification.handles.get(e.dxf.handle))
        else:
            emit(e, e, None, None)
    if skipped:
        warnings.append(f'{skipped} objetos en capas apagadas o inutilizadas no se han leído')
    scale_check(leaves)
    result = C.detect_all(doc, lo, hi, tmin, tmax, {'WALL'}, {'COLUMN'}, {'OPENING'}, parallel)
    from .conversion_curves import recover
    x0,x1=sorted((lo[0],hi[0]));y0,y1=sorted((lo[1],hi[1]))
    inside_leaves=[]
    for entity,role in leaves:
        segments=C._segments(entity)
        if segments and all(x0-1e-9<=x<=x1+1e-9 and y0-1e-9<=y<=y1+1e-9
                            for seg in segments for x,y in (seg[:2],seg[2:])):
            inside_leaves.append((entity,role))
    curved, curved_ops, curve_warnings = recover(result[3], inside_leaves)
    warnings.extend(curve_warnings)
    result=(*result[:3],curved,*result[4:])
    used = [];unpaired=result[5]
    from .geom.junctions import Wall
    curve_specs=[Wall('source-check',a,b,t,'eje',bulge=bulge) for a,b,t,bulge in curved]
    source_specs=[Wall('source-check',a,b,t,'eje') for a,b,t in result[0]]+curve_specs
    def represented_line(segment):
        if C._on_a_wall(segment,result[0]):return True
        for w in source_specs:
            sa,oa=w.local(segment[:2]);sb,ob=w.local(segment[2:4])
            if min(sa,sb)<-.02 or max(sa,sb)>w.length+.02:continue
            cap=(abs(sa-sb)<.02 and abs(min(oa,ob)-w.lo)<.02
                 and abs(max(oa,ob)-w.hi)<.02)
            face=(w.curved and max(abs(abs(o)-w.thickness/2) for o in (oa,ob))<.002)
            if cap or face:return True
        return False
    def represented_arc(arc):
        center,radius,a0,a1=arc
        for step in range(9):
            angle=a0+(a1-a0)*step/8
            pt=(center[0]+radius*math.cos(angle),center[1]+radius*math.sin(angle))
            if not any(math.dist(w.c,center)<1e-5 and
                       abs(abs(radius-w.r)-w.thickness/2)<1e-5 and
                       -1e-6<=w.local(pt)[0]<=w.length+1e-6 for w in curve_specs):
                return False
        return True
    for v in result[2]:
        source = source_map.get(v.dxf.handle)
        # Partially read blocks must remain visible; never alter definitions.
        if source is None or source.dxftype()=='INSERT':
            continue
        segs,arcs=C._pieces(v)
        if v.dxf.layer=='WALL' and not all(represented_line(s) for s in segs):
            continue  # even a very short unrecognised source must not disappear
        if arcs and not all(represented_arc(arc) for arc in arcs):
            continue  # a source containing an unpaired arc must stay visible
        doubtful=any(math.dist(f[:2],f[2:4])>tmax+.05 and
                     any(all(abs(a-b)<1e-6 for a,b in zip(f[:4],s)) for s in segs) for f in unpaired)
        if v.dxf.layer == 'OPENING' and not result[1]:
            continue
        if not doubtful and source not in used:
            used.append(source)
    # Explicit classifications override geometric heuristics only on existing
    # gaps with unambiguous nearby glyphs. No opening is guessed in a solid wall.
    ops=[]
    from ezdxf import bbox
    for op in result[1]:
        k,pos,width,kind,hinge,face=op;a,b,_t=result[0][k];length=math.dist(a,b)
        center=(a[0]+(b[0]-a[0])*pos/length,a[1]+(b[1]-a[1])*pos/length)
        votes=set()
        for e,role in leaves:
            if role not in VOTES:continue
            try:
                box=bbox.extents([e]);p=box.center
                if box.has_data and math.dist((p.x,p.y),center)<max(width,.5):
                    votes.add(VOTES[role])
            except Exception:continue
        if len(votes)==1:kind=votes.pop()
        elif len(votes)>1:warnings.append('Hueco con clasificaciones contradictorias; conserva lectura geométrica')
        ops.append((k,pos,width,kind,hinge,face))
    wall_roles=[]
    for a,b,_t in result[0]:
        center=((a[0]+b[0])/2,(a[1]+b[1])/2);nearest=None
        for e,role in leaves:
            if role not in WALLS:continue
            try:
                box=bbox.extents([e])
                if not box.has_data:continue
                score=math.dist((box.center.x,box.center.y),center)
                if nearest is None or score<nearest[0]:nearest=(score,role)
            except Exception:continue
        wall_roles.append(nearest[1] if nearest else 'muros')
    result=(result[0],ops,*result[2:])
    return Plan(result,used,list(dict.fromkeys(warnings)),drawing,fingerprint(drawing),(lo,hi),height,origin,wall_roles,curved_ops)


def commit(ctx, plan):
    from .compat import require_document
    from .architectural_v10 import create_wall, create_opening
    from .columns import column_command
    from .convert_tools import column_values, MoveToLayerCommand, _LayerOff, ORIGIN_LAYER
    from .transactions import SafeArchitecturalCommand, apply_architectural_change
    from core.commands import DeferredCommand
    from core.actions import EraseCommand
    from core.layers import NewLayerCommand
    doc=require_document(ctx)
    if doc.doc is not plan.drawing or fingerprint(doc.doc)!=plan.fingerprint:
        raise ValueError('El dibujo cambió después de la previsualización; vuelva a analizar')
    walls,ops,_src,curved,cols,_loose,_blocks=plan.result
    if not walls and not curved and not cols:return False
    commands=[create_wall(a,b,float(t),plan.height,0.,'eje',name=ROLES[plan.wall_roles[k]],
                          type_name=ROLES[plan.wall_roles[k]]) for k,(a,b,t) in enumerate(walls)]
    curved_commands=[create_wall(a,b,float(t),plan.height,0.,'eje',bulge=bulge,name='Muro') for a,b,t,bulge in curved]
    steps=list(commands)+curved_commands
    # DeferredCommand rebuilds against newly recreated wall entities on redo.
    # Allocate source identities outside its factory, never afresh on redo.
    import uuid
    opening_ids=[uuid.uuid4().hex for _ in range(len(ops)+len(plan.curved_openings))]
    def openings(_doc):
        out=[]
        for number,(k,pos,w,kind,hinge,face) in enumerate(ops):
            sill=.9 if kind=='window' else 0.
            h=min(1.2 if kind=='window' else 2.1,plan.height-sill)
            if h<=0:raise ValueError('Altura insuficiente para ventana')
            out.append(create_opening(commands[k].entity,pos-w/2,w,sill,h,
                       kind='gap' if kind=='void' else kind,existing=opening_ids[number],
                       hinge=int(hinge>0),side=1 if face>=0 else -1))
        for number,(k,pos,w,kind,hinge,face) in enumerate(plan.curved_openings,start=len(ops)):
            sill=.9 if kind=='window' else 0.
            h=min(1.2 if kind=='window' else 2.1,plan.height-sill)
            if h<=0:raise ValueError('Altura insuficiente para ventana')
            out.append(create_opening(curved_commands[k].entity,pos-w/2,w,sill,h,
                       kind='gap' if kind=='void' else kind,existing=opening_ids[number],
                       hinge=int(hinge>0),side=1 if face>=0 else -1))
        return SafeArchitecturalCommand('Huecos reconocidos',out)
    steps.append(DeferredCommand('Huecos reconocidos',openings))
    steps += [column_command(*column_values(p,plan.height)) for p in cols]
    if plan.origin=='ocultar' and plan.sources:
        if ORIGIN_LAYER not in doc.doc.layers:steps.insert(0,NewLayerCommand(ORIGIN_LAYER,color=8))
        steps += [MoveToLayerCommand(plan.sources,ORIGIN_LAYER),_LayerOff(ORIGIN_LAYER)]
    elif plan.origin=='borrar':steps.append(EraseCommand(plan.sources))
    apply_architectural_change(ctx,SafeArchitecturalCommand('Conversión confirmada',steps),kind='opening')
    return True

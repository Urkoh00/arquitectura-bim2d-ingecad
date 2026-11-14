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

    @property
    def segments(self):
        return [(a, b) for a, b, _t in self.result[0]] + [(a, b) for a,b,_t,_bulge in self.result[3]]


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
        if len(paths) != 1 or not hasattr(paths[0], 'vertices'):
            raise ValueError('Rayado con agujeros o contornos de aristas: revisión manual')
        if any(abs(p[2]) > 1e-12 for p in paths[0].vertices):
            raise ValueError('Rayado curvo: revisión manual')
        return [[tuple(p[:2]) for p in paths[0].vertices]]
    return None


def analyse(drawing, lo, hi, classification, tmin=.07, tmax=.5, height=2.7,
            parallel=.005, origin='ocultar'):
    import ezdxf
    from . import convert_tools as C
    from .architectural import metadata
    if not (0 < tmin <= tmax and height > 0 and all(map(math.isfinite, (tmin,tmax,height,parallel)))):
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

    for e in drawing.modelspace():
        if metadata(e):
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
    result = C.detect_all(doc, lo, hi, tmin, tmax, {'WALL'}, {'COLUMN'}, {'OPENING'}, parallel)
    used = [];unpaired=result[5]
    for v in result[2]:
        source = source_map.get(v.dxf.handle)
        # Partially read blocks must remain visible; never alter definitions.
        if source is None or source.dxftype()=='INSERT':
            continue
        segs=C._pieces(v)[0]
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
    return Plan(result,used,list(dict.fromkeys(warnings)),drawing,fingerprint(drawing),(lo,hi),height,origin,wall_roles)


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
    steps=list(commands)+[create_wall(a,b,float(t),plan.height,0.,'eje',bulge=bulge,name='Muro') for a,b,t,bulge in curved]
    def openings(_doc):
        out=[]
        for k,pos,w,kind,hinge,face in ops:
            sill=.9 if kind=='window' else 0.
            h=min(1.2 if kind=='window' else 2.1,plan.height-sill)
            if h<=0:raise ValueError('Altura insuficiente para ventana')
            out.append(create_opening(commands[k].entity,pos-w/2,w,sill,h,
                       kind='gap' if kind=='void' else kind,hinge=int(hinge>0),side=1 if face>=0 else -1))
        return SafeArchitecturalCommand('Huecos reconocidos',out)
    steps.append(DeferredCommand('Huecos reconocidos',openings))
    steps += [column_command(*column_values(p,plan.height)) for p in cols]
    if plan.origin=='ocultar' and plan.sources:
        if ORIGIN_LAYER not in doc.doc.layers:steps.insert(0,NewLayerCommand(ORIGIN_LAYER,color=8))
        steps += [MoveToLayerCommand(plan.sources,ORIGIN_LAYER),_LayerOff(ORIGIN_LAYER)]
    elif plan.origin=='borrar':steps.append(EraseCommand(plan.sources))
    apply_architectural_change(ctx,SafeArchitecturalCommand('Conversión confirmada',steps),kind='opening')
    return True

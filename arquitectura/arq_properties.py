# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: PROPIEDADESARQ: designar un elemento BIM por su dibujo en planta y abrir su ficha.
#   (Guía del código: docs/GUIA_DEL_CODIGO.md)
"""Select architectural objects through their 2D representation.

The official IngeCAD plugin API (2026-11) has no property-panel providers.
This tool therefore uses the same native BIM dialogs as creation and does
not monkey-patch IngeCAD's PropertiesPanel.
"""
from __future__ import annotations
from tools.base import Tool
from .architectural import metadata
from .compat import require_document


def resolve_arch_entity(doc, picked):
    """Return (entity, reason). Junction boundaries retain source wall ids."""
    if picked is None:
        return None, 'No se ha seleccionado una entidad.'
    data=metadata(picked) or {}
    if data.get('kind') in ('wall','column','opening','space','slab'):
        return picked, ''
    if data.get('kind') in ('opening_symbol','opening_mark','column_detail','space_label'):
        key,want={'opening_symbol':('opening_id','opening'),'opening_mark':('opening_id','opening'),'column_detail':('column_id','column'),
                  'space_label':('space_id','space')}[data['kind']]
        for entity in doc.doc.modelspace():
            info=metadata(entity) or {}
            if info.get('kind')==want and info.get('id')==data.get(key):
                return entity, ''
        return None, 'No se encuentra el elemento BIM original.'
    if data.get('kind') != 'junction_edge':
        return None, 'La entidad seleccionada no pertenece al plugin Arquitectura.'
    identifiers=list(data.get('wall_ids') or [])
    if not identifiers:
        return None, 'Segmento sin origen BIM: ejecute UNIONESARQ para regenerarlo.'
    if len(identifiers) != 1:
        return None, 'Contorno compartido por varios muros; seleccione otro segmento para evitar ambigüedades.'
    for entity in doc.doc.modelspace():
        info=metadata(entity) or {}
        if info.get('kind')=='wall' and info.get('id')==identifiers[0]:
            return entity, ''
    return None, 'No se encuentra el muro BIM original.'


def opening_change(entity, values):
    """The undoable edit of a carpentry from the values of its sheet: same
    identity; its model, size and position change (on a curved wall the
    width given is the planar one, the chord)."""
    from . import openings as OP
    from .architectural_v10 import edit_opening
    from .geom import junctions as J
    d=metadata(entity)
    wall=next((e for e in entity.doc.modelspace() if (metadata(e) or {}).get('id')==d.get('wall_id')
               and (metadata(e) or {}).get('kind')=='wall'),None)
    if wall is None:
        raise ValueError('No se encuentra el muro de la carpintería')
    w=metadata(wall)
    spec=J.walls_from_records([(w['id'],w)])[0]
    v=dict(values)
    real=float(v.pop('width'))
    width=OP.span_of(spec,real,v,int(v.get('side',d.get('side',1))))
    offset=float(v.pop('offset',d['offset']))
    if 'offset' not in values:          # keep its centre
        offset=float(d['offset'])+float(d['width'])/2-width/2
    keys=('name','type_name','material','operation')
    return edit_opening(entity,offset=offset,width=width,sill=v.pop('sill'),height=v.pop('height'),
                        **{k:v.pop(k) for k in keys if k in v},
                        **{k:val for k,val in v.items() if k in OP.V3_KEYS or k=='type'})


def space_change(entity, values):
    """The undoable edit of a space's record (its outline follows the walls)."""
    import copy
    from .architectural_v10 import EditArchitecturalCommand
    d=copy.deepcopy(metadata(entity))
    for k in ('name','number','use','enclosure','height','ceiling','level','height_mode'):
        # el número y el uso se pueden vaciar; el resto, vacío, no cambia
        if k in values and (values[k] not in (None,'') or (k in ('number','use') and values[k]=='')):
            d[k]=values[k]
    if 'cte' in values:                  # an empty classification is a valid choice
        from .cte_usos import validate
        d['cte']=validate(values['cte'])
    if values.get('name')=='':
        d['name']=d.get('name') or 'Recinto'
    import math
    if not math.isfinite(float(d['height'])) or float(d['height'])<=0:
        raise ValueError('La altura del recinto debe ser positiva')
    cmd=EditArchitecturalCommand(entity,d)
    cmd.name='ARQ RECINTO'
    return cmd


def cambio_propiedades(ctx, entity, values):
    """Una única selección de operación para las fichas y sus variantes de texto."""
    kind = metadata(entity)['kind']
    if kind == 'wall':
        from .architectural_v10 import edit_wall
        keys = ('thickness', 'height', 'base', 'reference', 'name', 'type_name',
                'material', 'level', 'layers', 'wall_category', 'height_constraint',
                'top_level_id', 'top_offset', 'base_offset', 'level_id',
                'defense_type', 'void_ratio')
        return edit_wall(entity, **{key: values[key] for key in keys if key in values})
    if kind == 'column':
        from .columns import EditColumnCommand
        return EditColumnCommand(entity, values)
    if kind == 'opening':
        return opening_change(entity, values)
    if kind == 'space':
        return space_change(entity, values)
    from .slab_tools import edit_change
    return edit_change(ctx, entity, values)


class ArqPropiedadesTool(Tool):
    name='PROPIEDADESARQ'
    entity_picker=True

    def start(self):
        self.name='PROPIEDADESARQ'
        self.prompt('Seleccione un muro, pilar, carpintería o recinto para editar sus propiedades BIM:')

    def on_point(self, point):
        try:
            services=getattr(self.ctx,'services',None)
            picked=services.pick_entity(point) if services else None
            entity, error=resolve_arch_entity(require_document(self.ctx), picked)
            if entity is None:
                self.ctx.echo('PROPIEDADESARQ: '+error)
                return
            data=metadata(entity)
            from . import bim_dialogs
            if not bim_dialogs.available(self.ctx):
                self.ctx.echo('Ficha BIM no disponible en este entorno; entidad '+str(data.get('id')))
                return
            if data['kind']=='slab':
                from .slabs import read as slab_read
                from .slab_tools import form
                data=slab_read(entity);dlg,read=form(self.ctx,data)
                values=read() if dlg.exec()==1 else None
            elif data['kind']=='wall':
                values=bim_dialogs.wall_properties(self.ctx,data)

            elif data['kind']=='column':
                values=bim_dialogs.column_properties(self.ctx,data)

            elif data['kind']=='opening':
                from . import openings as OP
                from .geom.junctions import walls_from_records
                host=next((metadata(e) for e in entity.doc.modelspace() if (metadata(e)or{}).get('id')==data.get('wall_id')),None)
                if host:
                    spec=walls_from_records([(host['id'],host)])[0]
                    data={**data,'_wall_spec':spec,'_wall_thickness':spec.thickness,
                          '_display_width':OP.measure_of(spec,data['width'],data,int(data.get('side',1)))}
                if data.get('cabinet'):
                    from .cabinets import form
                    dlg,read=form(self.ctx,data)
                    values=read()if dlg.exec()==1 else None
                else:values=bim_dialogs.carpentry_properties(self.ctx,data,editing=True)

            else:
                values=bim_dialogs.space_properties(self.ctx,data)

            command=cambio_propiedades(self.ctx,entity,values) if values is not None else None
            if command is not None:
                from .transactions import apply_architectural_change
                apply_architectural_change(self.ctx, command, kind=data['kind'])
                self.ctx.echo('Elemento BIM editado. Identificador conservado: '+str(data.get('id')))
            self.ctx.finish()
        except Exception as exc:
            self.ctx.echo(f'PROPIEDADESARQ: error ({type(exc).__name__}: {exc})')

    def on_enter(self):
        self.ctx.finish()

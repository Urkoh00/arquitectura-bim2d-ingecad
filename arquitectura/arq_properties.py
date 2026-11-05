# SPDX-License-Identifier: GPL-3.0-or-later
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
    if data.get('kind') in ('wall','column','opening'):
        return picked, ''
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


class ArqPropiedadesTool(Tool):
    name='PROPIEDADESARQ'
    entity_picker=True

    def start(self):
        self.name='PROPIEDADESARQ'
        self.prompt('Seleccione un muro, pilar o contorno ARQ para editar sus propiedades:')

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
            if data['kind']=='wall':
                from .architectural_v10 import edit_wall
                values=bim_dialogs.wall_properties(self.ctx,data)
                command=(edit_wall(entity, **{k:v for k,v in values.items() if k!='ifc_class'})
                         if values is not None else None)
            elif data['kind']=='column':
                from .columns import EditColumnCommand
                values=bim_dialogs.column_properties(self.ctx,data)
                command=EditColumnCommand(entity,values) if values is not None else None
            else:
                self.ctx.echo('La edición de carpinterías continuará en una revisión posterior.')
                self.ctx.finish()
                return
            if command is not None:
                from .transactions import apply_architectural_change
                apply_architectural_change(self.ctx, command, kind=data['kind'])
                self.ctx.echo('Elemento BIM editado. Identificador conservado: '+str(data.get('id')))
            self.ctx.finish()
        except Exception as exc:
            self.ctx.echo(f'PROPIEDADESARQ: error ({type(exc).__name__}: {exc})')

    def on_enter(self):
        self.ctx.finish()

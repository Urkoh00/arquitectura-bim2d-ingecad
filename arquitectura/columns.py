# SPDX-License-Identifier: GPL-3.0-or-later
"""BIM column footprints for IngeCAD, persisted in DXF XDATA."""
from __future__ import annotations
import math,uuid
from tools.base import Tool
from .architectural import _xdata
from .tools3d import ensure_arch_layers

PILLAR_LAYER='ARQ-PILAres'

from .sections import column_points

def column_command(center,values):
    from core.actions import AddEntityCommand
    from .architectural import APPID
    points=column_points(center,values)
    props={k:v for k,v in values.items() if k in ('shape','width','depth','radius','rotation','height','base','name','type_name','material','level')}
    rec={'kind':'column','schema':2,'id':uuid.uuid4().hex,'ifc_class':'IfcColumn',
         'center':list(map(float,center[:2])),**props}
    def factory(msp):
        return _xdata(msp,msp.add_lwpolyline(points,close=True),rec)
    return AddEntityCommand('ARQ PILAR',factory,layer=PILLAR_LAYER)

class PilarBimTool(Tool):
    name='PILAR'
    def start(self):
        self.name='PILAR'
        from .parameters_arq import load_defaults
        from .compat import require_document
        self.values=load_defaults(require_document(self.ctx))['column']
        self.prompt('PILAR: configurando sección y propiedades BIM...')
        try:
            from . import bim_dialogs
            if bim_dialogs.available(self.ctx):
                values=bim_dialogs.column_properties(self.ctx,self.values)
                if values is None:self.ctx.finish();return
                self.values.update(values)
        except Exception as exc:
            self.ctx.echo(f'PILAR: ficha no disponible ({type(exc).__name__}: {exc}); se utiliza sección rectangular 0,30 × 0,30 m.')
        self.prompt('PILAR: indique centro o [Fin]:')
    def on_point(self,p):
        try:
            from .transactions import apply_architectural_change
            apply_architectural_change(self.ctx, column_command(p,self.values), kind='column')
            self.ctx.echo('Pilar BIM insertado y encuentro con muros actualizado.')
            self.prompt('PILAR: siguiente centro o [Fin]:')
        except Exception as exc:
            self.ctx.echo(f'PILAR: error ({type(exc).__name__}: {exc})')
    def preview_segments(self,cursor):
        try:
            poly=column_points(cursor,self.values)
            return list(zip(poly,poly[1:]+poly[:1]))
        except ValueError:return []
    def on_option(self,text):
        if str(text).strip().lower() in ('fin','f'):
            self.ctx.finish();return True
        return False
    def on_enter(self):self.ctx.finish()


class EditColumnCommand:
    """One exact undo/redo transaction for a BIM pillar, same entity handle."""
    name = 'ARQ EDITAR PILAR'

    def __init__(self, entity, values):
        import copy
        from .architectural import metadata
        original = metadata(entity)
        if not original or original.get('kind') != 'column':
            raise ValueError('La entidad no es un pilar arquitectónico')
        self.handle = entity.dxf.handle
        self.before = copy.deepcopy(original)
        self.after = copy.deepcopy(original)
        self.after.update({k: v for k,v in values.items() if k in (
            'shape','width','depth','radius','rotation','height','base','name',
            'type_name','material','level')})
        # Preserve its stable BIM id and world placement.
        self.after['id'] = original['id']
        self.after['center'] = original['center']
        self.before_points = [tuple(p[:2]) for p in entity.get_points('xy')]
        self.after_points = column_points(original['center'], self.after)
        for k in ('height',):
            if not math.isfinite(float(self.after[k])) or float(self.after[k]) <= 0:
                raise ValueError('Altura de pilar inválida')
        if not math.isfinite(float(self.after['base'])):
            raise ValueError('Cota base de pilar inválida')

    def _apply(self, document, rec, points):
        entity = document.doc.entitydb.get(self.handle)
        if entity is None:
            raise RuntimeError('No se encuentra el pilar original')
        entity.set_points(points, format='xy')
        _xdata(document.doc.modelspace(), entity, rec)
        document.dirty = True

    def do(self, document):
        self._apply(document, self.after, self.after_points)

    def undo(self, document):
        self._apply(document, self.before, self.before_points)

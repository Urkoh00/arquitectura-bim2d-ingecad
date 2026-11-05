# SPDX-License-Identifier: GPL-3.0-or-later
"""Drawing-scoped architectural defaults, in native DXF root dictionary.

No global JSON or machine-specific path: the drawing carries its defaults.
The XRECORD is written in reversible IngeCAD history commands.
"""
from __future__ import annotations
import copy
import json
import math
from core.commands import Command

KEY = 'ARQUITECTURA_PARAMETROS'
DEFAULTS = {
    'schema': 1,
    'wall': {'thickness': 0.30, 'height': 2.70, 'base': 0.0,
             'reference': 'eje', 'name': 'Muro', 'type_name': 'Muro genérico',
             'material': 'Sin definir', 'level': 'Planta baja'},
    'column': {'shape': 'rect', 'width': 0.30, 'depth': 0.30, 'radius': 0.15, 'rotation': 0.0,
               'height': 2.70, 'base': 0.0, 'name': 'Pilar',
               'type_name': 'Pilar genérico', 'material': 'Hormigón armado',
               'level': 'Planta baja'},
    'door': {'width': 0.90, 'height': 2.10, 'sill': 0.0},
    'window': {'width': 1.20, 'height': 1.20, 'sill': 1.00},
}

def _drawing(document):
    drawing = getattr(document, 'doc', document)
    if drawing is None or not hasattr(drawing, 'rootdict'):
        raise ValueError('No hay un documento DXF activo')
    return drawing

def _raw(drawing):
    rec = drawing.rootdict.get(KEY)
    if rec is None:
        return None
    return ''.join(str(t.value) for t in rec.tags if t.code in (1, 3))

def load_defaults(document):
    saved = _raw(_drawing(document))
    result = copy.deepcopy(DEFAULTS)
    if saved:
        payload = json.loads(saved)
        if not isinstance(payload, dict):
            raise ValueError('Configuración ARQ mal formada')
        for key in ('wall','column','door','window'):
            data = payload.get(key, {})
            if isinstance(data,dict):
                result[key].update({k:v for k,v in data.items() if k in result[key]})
    validate_defaults(result)
    return result

def validate_defaults(values):
    for kind in ('wall','column','door','window'):
        d = values[kind]
        for key in ('thickness','height','width','depth','radius'):
            if key in d and (not isinstance(d[key],(int,float)) or not math.isfinite(d[key]) or d[key]<=0):
                raise ValueError(f'{kind}.{key}: debe ser mayor que cero')
        for key in ('base','sill','rotation'):
            if key in d and (not isinstance(d[key],(int,float)) or not math.isfinite(d[key])):
                raise ValueError(f'{kind}.{key}: cota inválida')
        if d.get('reference','eje') not in ('eje','izquierda','derecha'):
            raise ValueError('Referencia de muro no válida')
        if d.get('shape','rect') not in ('rect','circ','hex','oct'):
            raise ValueError('Sección de pilar no válida')
    return values

def _store(drawing, payload):
    root = drawing.rootdict
    rec = root.get(KEY)
    if payload is None:
        if rec is not None:
            root.discard(KEY)
            drawing.entitydb.delete_entity(rec)
        return
    text = json.dumps(payload, ensure_ascii=False, separators=(',',':'), sort_keys=True)
    chunks=[(1,text[i:i+240]) for i in range(0,len(text),240)]
    if rec is None:
        rec = root.add_xrecord(KEY)
    rec.reset(chunks)

class SetArchitecturalDefaults(Command):
    name='PARAMETROSARQ'
    def __init__(self, values):
        self.values=copy.deepcopy(validate_defaults(values))
        self.before=None
        self.first=True
    def do(self, document):
        drawing=_drawing(document)
        if self.first:
            self.before=_raw(drawing)
            self.first=False
        _store(drawing,self.values)
        document.dirty=True
    def undo(self,document):
        drawing=_drawing(document)
        if self.before is None:
            _store(drawing,None)
        else:
            # Restore exactly the previously serialized record.
            rec=drawing.rootdict.get(KEY)
            if rec is None: rec=drawing.rootdict.add_xrecord(KEY)
            rec.reset([(1,self.before[i:i+240]) for i in range(0,len(self.before),240)])
        document.dirty=True

def parametros_arq(ctx,*args):
    try:
        current=load_defaults(ctx.document)
        from .bim_dialogs import architectural_defaults_dialog
        new=architectural_defaults_dialog(ctx,current)
        if new is None:
            ctx.echo('PARAMETROSARQ: sin cambios.')
            return
        ctx.execute(SetArchitecturalDefaults(new))
        ctx.echo('PARAMETROSARQ: parámetros guardados en este DXF. Los elementos existentes no se modifican.')
    except Exception as exc:
        ctx.echo(f'PARAMETROSARQ: {type(exc).__name__}: {exc}')

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
    # Named wall types (IfcWallType): chosen in MURO with option T. Usual
    # Spanish names; the thicknesses are editable per drawing (TIPOSMURO).
    'wall_types': [
        {'name': 'Tabique', 'thickness': 0.07, 'material': ''},
        {'name': 'Tabicón', 'thickness': 0.10, 'material': ''},
        {'name': 'Medio pie', 'thickness': 0.12, 'material': ''},
        {'name': 'Un pie', 'thickness': 0.25, 'material': ''},
        {'name': 'Pie y medio', 'thickness': 0.38, 'material': ''},
        {'name': 'Dos pies', 'thickness': 0.51, 'material': ''},
    ],
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
        types = payload.get('wall_types')
        if isinstance(types, list):
            result['wall_types'] = [{'name': str(t.get('name', '')).strip(),
                                     'thickness': t.get('thickness'),
                                     'material': str(t.get('material', '') or '')}
                                    for t in types if isinstance(t, dict)]
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
    names = set()
    for t in values.get('wall_types', []):
        th = t.get('thickness')
        if not t.get('name') or not isinstance(th, (int, float)) or not math.isfinite(th) or th <= 0:
            raise ValueError(f"Tipo de muro no válido: {t}")
        if t['name'].lower() in names:
            raise ValueError(f"Tipo de muro repetido: {t['name']}")
        names.add(t['name'].lower())
    return values


def find_wall_type(types, text):
    """A wall type by its number (1-based) or by the start of its name."""
    txt = str(text).strip().lower()
    if txt.isdigit() and 1 <= int(txt) <= len(types):
        return types[int(txt) - 1]
    hits = [t for t in types if t['name'].lower() == txt] or \
        [t for t in types if t['name'].lower().startswith(txt)] if txt else []
    return hits[0] if len(hits) == 1 else None


def wall_types_text(types):
    return '  '.join(f"{i}) {t['name']} {t['thickness']:g}".replace('.', ',')
                     for i, t in enumerate(types, 1))

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


def tipos_muro(ctx, *args):
    """TIPOSMURO: list the drawing's wall types; with arguments,
    ``TIPOSMURO Nombre 0,12 [material]`` adds or updates one and
    ``TIPOSMURO -Nombre`` removes it. Stored in this DXF, undoable."""
    try:
        current = load_defaults(ctx.document)
        types = current['wall_types']
        if not args:
            ctx.echo('TIPOSMURO: ' + (wall_types_text(types) or '(ninguno)'))
            ctx.echo('  Añadir o cambiar: TIPOSMURO Nombre 0,12 [material] · Quitar: TIPOSMURO -Nombre')
            return
        words = [str(a) for a in args]
        if words[0].startswith('-'):
            name = ' '.join(words)[1:].strip().lower()
            new = [t for t in types if t['name'].lower() != name]
            if len(new) == len(types):
                ctx.echo(f'TIPOSMURO: no existe el tipo {name}.')
                return
        else:
            num = next((i for i, w in enumerate(words) if _is_number(w)), None)
            if num is None or num == 0:
                ctx.echo('TIPOSMURO: indique nombre y espesor, p. ej. TIPOSMURO Tabicón 0,10')
                return
            name = ' '.join(words[:num]).strip()
            entry = {'name': name, 'thickness': float(words[num].replace(',', '.')),
                     'material': ' '.join(words[num + 1:]).strip()}
            new = [t for t in types if t['name'].lower() != name.lower()]
            idx = next((i for i, t in enumerate(types) if t['name'].lower() == name.lower()), len(new))
            new.insert(idx, entry)
        current['wall_types'] = new
        ctx.execute(SetArchitecturalDefaults(current))
        ctx.echo('TIPOSMURO: ' + wall_types_text(new))
    except Exception as exc:  # noqa: BLE001
        ctx.echo(f'TIPOSMURO: {type(exc).__name__}: {exc}')


def _is_number(text):
    try:
        v = float(str(text).replace(',', '.'))
        return math.isfinite(v)
    except ValueError:
        return False

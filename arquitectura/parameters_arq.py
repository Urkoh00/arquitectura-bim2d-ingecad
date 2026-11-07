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
TIPOS_EDIFICIO_CEE = ('ViviendaUnifamiliar', 'BloqueDeViviendaCompleto', 'ViviendaIndividualEnBloque',
                      'EdificioUsoTerciario', 'LocalUsoTerciario')
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
    # Three classifications that must not be mixed (user's notes 07/11/2026):
    #   tipo_edificio_cee: <TipoDeEdificio> of the energy certificate XML
    #     (ViviendaUnifamiliar, BloqueDeViviendaCompleto, ViviendaIndividualEnBloque,
    #     EdificioUsoTerciario, LocalUsoTerciario; v2.1/v2.2, to check against v3.0);
    #   uso_dbhe: «residencial privado» or «otros usos» (DB-HE, Anejo D), the
    #     latter with load (baja/media/alta) and hours (8/12/16/24);
    #   uso_dbsi: DB-SI use (Residencial Vivienda, Administrativo, Docente, ...),
    #     never deduced from the other two.
    'usos': {'tipo_edificio_cee': 'ViviendaUnifamiliar', 'uso_dbhe': 'residencial privado',
             'carga_dbhe': '', 'horario_dbhe': '', 'uso_dbsi': 'Residencial Vivienda'},
    'window': {'width': 1.20, 'height': 1.20, 'sill': 1.00},
    # Wall types (IfcWallType). Each one is a list of layers, from the
    # DRAWN face (the reference line) toward the body of the wall; its
    # thickness is the sum of the layers. MURO asks for the TOTAL thickness
    # first and offers the types that have it. Editable per drawing with
    # TIPOSMURO (also from a CSV file). Sources of the defaults:
    #   Termoarcilla: blocks 30 x 19 cm, 14/19/24/29 cm thick (Hispalyt).
    #   Plasterboard partitions: designation total/stud, 1x15 or 2x12.5
    #   boards per face (Placo, guía de tabiques 2022).
    'wall_types': [
        {'name': 'PYL 78/48', 'layers': [[0.015, 'Placa de yeso laminado'], [0.048, 'Montante 48 + lana mineral'], [0.015, 'Placa de yeso laminado']]},
        {'name': 'PYL 98/48', 'layers': [[0.025, 'Placa de yeso laminado 2x12,5'], [0.048, 'Montante 48 + lana mineral'], [0.025, 'Placa de yeso laminado 2x12,5']]},
        {'name': 'PYL 100/70', 'layers': [[0.015, 'Placa de yeso laminado'], [0.070, 'Montante 70 + lana mineral'], [0.015, 'Placa de yeso laminado']]},
        {'name': 'PYL 120/70', 'layers': [[0.025, 'Placa de yeso laminado 2x12,5'], [0.070, 'Montante 70 + lana mineral'], [0.025, 'Placa de yeso laminado 2x12,5']]},
        {'name': 'PYL 120/90', 'layers': [[0.015, 'Placa de yeso laminado'], [0.090, 'Montante 90 + lana mineral'], [0.015, 'Placa de yeso laminado']]},
        {'name': 'PYL 140/90', 'layers': [[0.025, 'Placa de yeso laminado 2x12,5'], [0.090, 'Montante 90 + lana mineral'], [0.025, 'Placa de yeso laminado 2x12,5']]},
        {'name': 'Tabique LHD 7 guarnecido', 'layers': [[0.015, 'Guarnecido de yeso'], [0.070, 'Ladrillo hueco doble'], [0.015, 'Guarnecido de yeso']]},
        {'name': 'Termoarcilla 14', 'layers': [[0.14, 'Bloque Termoarcilla']]},
        {'name': 'Termoarcilla 19', 'layers': [[0.19, 'Bloque Termoarcilla']]},
        {'name': 'Termoarcilla 24', 'layers': [[0.24, 'Bloque Termoarcilla']]},
        {'name': 'Termoarcilla 29', 'layers': [[0.29, 'Bloque Termoarcilla']]},
        {'name': 'Fachada caravista + aislamiento + LHD (ejemplo)', 'layers': [
            [0.115, 'Ladrillo cara vista'], [0.010, 'Enfoscado de mortero'], [0.050, 'Lana mineral'],
            [0.070, 'Ladrillo hueco doble'], [0.015, 'Guarnecido de yeso']]},
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
        for key in ('wall','column','door','window','usos'):
            data = payload.get(key, {})
            if isinstance(data,dict):
                result[key].update({k:v for k,v in data.items() if k in result[key]})
        types = payload.get('wall_types')
        if isinstance(types, list):
            result['wall_types'] = [t for t in types if isinstance(t, dict)]
    result['wall_types'] = [normalise_type(t) for t in result['wall_types']]
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
    u = values.get('usos')
    if u and u.get('tipo_edificio_cee') not in TIPOS_EDIFICIO_CEE:
        raise ValueError('Tipo de edificio del certificado no válido: ' + str(u.get('tipo_edificio_cee')))
    if u and u.get('uso_dbhe') not in ('residencial privado', 'otros usos'):
        raise ValueError('Uso DB-HE: «residencial privado» u «otros usos»')
    if u and u.get('uso_dbhe') == 'otros usos':
        if u.get('carga_dbhe') not in ('baja', 'media', 'alta') or str(u.get('horario_dbhe')) not in ('8', '12', '16', '24'):
            raise ValueError('Otros usos DB-HE: carga baja/media/alta y horario 8/12/16/24 h')
    names = set()
    for t in values.get('wall_types', []):
        t = normalise_type(t)
        if not t['name'] or not t['layers']:
            raise ValueError(f"Tipo de muro no válido: {t}")
        for th, _mat in t['layers']:
            if not isinstance(th, (int, float)) or not math.isfinite(th) or th <= 0:
                raise ValueError(f"Capa no válida en el tipo {t['name']}")
        if t['name'].lower() in names:
            raise ValueError(f"Tipo de muro repetido: {t['name']}")
        names.add(t['name'].lower())
    return values


def normalise_type(t):
    """{'name', 'layers': [[thickness, material], ...], 'thickness', 'material'}.
    Accepts the v1.8.0 form {'name', 'thickness', 'material'} (one layer)."""
    name = str(t.get('name', '')).strip()
    layers = t.get('layers')
    if not layers:
        th = t.get('thickness')
        layers = [[th, str(t.get('material') or '')]] if th is not None else []
    layers = [[float(th), str(mat or '').strip()] for th, mat in layers]
    total = round(sum(th for th, _m in layers), 6)
    main = max(layers, key=lambda lm: lm[0])[1] if layers else ''
    return {'name': name, 'layers': layers, 'thickness': total, 'material': main}


def _num(v):
    return f"{v:.3f}".rstrip('0').rstrip('.').replace('.', ',')


def types_with_thickness(types, thickness, tol=5e-4):
    return [t for t in types if abs(t['thickness'] - float(thickness)) <= tol]


def find_wall_type(types, text):
    """A wall type by its number (1-based, in the listing order) or by the
    start of its name."""
    txt = str(text).strip().lower()
    ordered = sort_types(types)
    if txt.isdigit() and 1 <= int(txt) <= len(ordered):
        return ordered[int(txt) - 1]
    if not txt:
        return None
    hits = [t for t in ordered if t['name'].lower() == txt] or \
        [t for t in ordered if t['name'].lower().startswith(txt)]
    return hits[0] if len(hits) == 1 else None


def sort_types(types):
    return sorted(types, key=lambda t: (t['thickness'], t['name'].lower()))


def wall_types_text(types):
    """Numbered listing grouped by total thickness."""
    out, last = [], None
    for i, t in enumerate(sort_types(types), 1):
        head = f"[{_num(t['thickness'])}] " if t['thickness'] != last else ''
        last = t['thickness']
        out.append(f"{head}{i}) {t['name']}")
    return '  '.join(out)


def layers_text(t):
    return ' + '.join(f"{_num(th)} {mat}".strip() for th, mat in t['layers'])


def parse_type(text):
    """'Nombre = 0,015 Yeso + 0,07 LHD' or 'Nombre 0,12 [material]'."""
    text = str(text).strip()
    if '=' in text:
        name, rest = text.split('=', 1)
        layers = []
        for part in rest.split('+'):
            words = part.strip().split()
            if not words or not _is_number(words[0]):
                raise ValueError(f"Capa no válida: «{part.strip()}» (use «0,05 Material»)")
            layers.append([float(words[0].replace(',', '.')), ' '.join(words[1:])])
        return normalise_type({'name': name.strip(), 'layers': layers})
    words = text.split()
    # the thickness is the LAST decimal value («Termoarcilla 30 ECO 0,30»):
    # whole numbers may be part of the name
    decimals = [i for i, w in enumerate(words) if _is_number(w) and (',' in w or '.' in w)]
    num = decimals[-1] if decimals else next((i for i, w in enumerate(words) if _is_number(w)), None)
    if not num:
        raise ValueError('Indique nombre y espesor, p. ej. «Termoarcilla 24 0,24» o capas con «=»')
    return normalise_type({'name': ' '.join(words[:num]),
                           'thickness': float(words[num].replace(',', '.')),
                           'material': ' '.join(words[num + 1:])})


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
    """TIPOSMURO, wall types of this drawing (undoable):
      TIPOSMURO                                   lista, agrupada por espesor total
      TIPOSMURO 0,24                              tipos con ese espesor total, con sus capas
      TIPOSMURO Nombre 0,12 [material]            tipo de una capa (añade o cambia)
      TIPOSMURO Nombre = 0,015 Yeso + 0,07 LHD    tipo multicapa, desde la cara dibujada
      TIPOSMURO -Nombre                           quita un tipo
      TIPOSMURO importar ruta.csv                 «Nombre;capas» o «Nombre;espesor;material»
      TIPOSMURO exportar ruta.csv"""
    try:
        current = load_defaults(ctx.document)
        types = current['wall_types']
        text = ' '.join(str(a) for a in args).strip()
        low = text.lower()
        if not text:
            ctx.echo('TIPOSMURO: ' + (wall_types_text(types) or '(ninguno)'))
            ctx.echo('  Ver capas: TIPOSMURO 0,24 · Añadir: TIPOSMURO Nombre = 0,015 Yeso + 0,07 LHD'
                     ' · Quitar: TIPOSMURO -Nombre · TIPOSMURO importar/exportar ruta.csv')
            return
        if _is_number(text):
            hits = types_with_thickness(types, float(text.replace(',', '.')))
            if not hits:
                ctx.echo(f'TIPOSMURO: ningún tipo de {text} m.')
            for t in hits:
                ctx.echo(f"TIPOSMURO: {t['name']}: {layers_text(t)}")
            return
        if low.startswith('exportar '):
            path = text.split(' ', 1)[1].strip().strip('"')
            with open(path, 'w', encoding='utf-8-sig', newline='') as f:
                for t in sort_types(types):
                    f.write(f"{t['name']};{layers_text(t)}\n")
            ctx.echo(f'TIPOSMURO: {len(types)} tipos exportados a {path}')
            return
        if low.startswith('importar '):
            path = text.split(' ', 1)[1].strip().strip('"')
            new = {t['name'].lower(): t for t in types}
            count = 0
            with open(path, encoding='utf-8-sig') as f:
                for n, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    cols = [c.strip() for c in line.split(';')]
                    if len(cols) >= 3 and _is_number(cols[1]):
                        t = normalise_type({'name': cols[0], 'material': cols[2],
                                            'thickness': float(cols[1].replace(',', '.'))})
                    elif len(cols) >= 2:
                        t = parse_type(f"{cols[0]} = {cols[1]}")
                    else:
                        raise ValueError(f'línea {n}: «{line}»')
                    new[t['name'].lower()] = t
                    count += 1
            current['wall_types'] = list(new.values())
            ctx.execute(SetArchitecturalDefaults(current))
            ctx.echo(f'TIPOSMURO: {count} tipos importados; {len(new)} en total.')
            return
        if text.startswith('-'):
            name = text[1:].strip().lower()
            new = [t for t in types if t['name'].lower() != name]
            if len(new) == len(types):
                ctx.echo(f'TIPOSMURO: no existe el tipo {name}.')
                return
        else:
            entry = parse_type(text)
            new = [t for t in types if t['name'].lower() != entry['name'].lower()] + [entry]
            ctx.echo(f"TIPOSMURO: {entry['name']}: {layers_text(entry)} = {_num(entry['thickness'])} m")
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


def usos_arq(ctx, *args):
    """USOSARQ: classification of the building (one undo step):
      USOSARQ                                  shows it
      USOSARQ edificio ViviendaUnifamiliar     <TipoDeEdificio> of the energy certificate
      USOSARQ dbhe residencial                 DB-HE: residencial privado
      USOSARQ dbhe otros media 12              DB-HE: otros usos, load and hours
      USOSARQ dbsi Docente                     DB-SI / DB-SUA use (free text)"""
    try:
        current = load_defaults(ctx.document)
        u = current['usos']
        words = ' '.join(str(a) for a in args).split()
        if not words:
            ctx.echo('USOSARQ — clasificaciones independientes del edificio:')
            ctx.echo(f"  Certificado energético <TipoDeEdificio>: {u['tipo_edificio_cee']}")
            dbhe = u['uso_dbhe'] + (f", carga {u['carga_dbhe']}, {u['horario_dbhe']} h" if u['uso_dbhe'] == 'otros usos' else '')
            ctx.echo(f'  DB-HE: {dbhe}')
            ctx.echo(f"  DB-SI / DB-SUA: {u['uso_dbsi']}")
            ctx.echo('  Cambiar: USOSARQ edificio <' + '|'.join(TIPOS_EDIFICIO_CEE) + '>, '
                     'USOSARQ dbhe residencial | otros <baja|media|alta> <8|12|16|24>, USOSARQ dbsi <uso>')
            return u
        key, rest = words[0].lower(), words[1:]
        new = copy.deepcopy(current)
        nu = new['usos']
        if key == 'edificio' and rest:
            match = [t for t in TIPOS_EDIFICIO_CEE if t.lower() == rest[0].lower()]
            if not match:
                raise ValueError('valores admitidos: ' + ', '.join(TIPOS_EDIFICIO_CEE))
            nu['tipo_edificio_cee'] = match[0]
        elif key == 'dbhe' and rest:
            if rest[0].lower().startswith('res'):
                nu.update(uso_dbhe='residencial privado', carga_dbhe='', horario_dbhe='')
            else:
                if len(rest) < 3:
                    raise ValueError('otros usos: indique carga (baja/media/alta) y horario (8/12/16/24)')
                nu.update(uso_dbhe='otros usos', carga_dbhe=rest[1].lower(), horario_dbhe=rest[2])
        elif key == 'dbsi' and rest:
            nu['uso_dbsi'] = ' '.join(rest)
        else:
            raise ValueError('use USOSARQ edificio|dbhe|dbsi ...')
        ctx.execute(SetArchitecturalDefaults(new))
        ctx.echo('USOSARQ: clasificación guardada en este DXF; se exporta con el modelo BIM.')
        return nu
    except Exception as exc:
        ctx.echo(f'USOSARQ: {type(exc).__name__}: {exc}')

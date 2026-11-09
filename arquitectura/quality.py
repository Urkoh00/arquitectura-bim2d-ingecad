# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only CAD/BIM integrity audit; no geometric edits, no new dependencies."""
from __future__ import annotations
import math
from collections import Counter
from .architectural import metadata, WALL_LAYER, APPID


def audit_architecture(document):
    """Return a structured report of the actual drawing without altering it."""
    drawing = getattr(document, 'doc', document)
    msp = drawing.modelspace()
    records = [(e, metadata(e)) for e in msp]
    sources = [(e, d) for e, d in records if d and d.get('kind') == 'wall']
    columns = [(e, d) for e, d in records if d and d.get('kind') == 'column']
    outlines = [(e, d) for e, d in records if d and d.get('kind') == 'junction_edge']
    openings = [(e, d) for e, d in records if d and d.get('kind') == 'opening']
    issues = []
    # Los grupos 1000 tienen un límite de 255 bytes; informar también cuando
    # el JSON legado está truncado y ya no se reconoce como dato arquitectónico.
    for entity, _ in records:
        try:
            tags = entity.get_xdata(APPID)
        except (ValueError, KeyError):
            continue
        chunks = [t.value for t in tags if t.code == 1000]
        if any(len(str(v).encode('utf-8')) > 255 for v in chunks):
            issues.append(f'XDATA >255 bytes en entidad {entity.dxf.handle}: es necesario regrabar los atributos')
    # Auditoría informativa: no cambiar ids ni reconstruir geometría por sorpresa.
    geometry_tolerance = 1e-5
    def distant(a, b):
        return math.dist(tuple(map(float,a[:2])), tuple(map(float,b[:2]))) > geometry_tolerance
    # identities, unreadable data, orphan and misfit openings: the same
    # check EXPORTARBIM runs before exporting (integrity.audit)
    from .integrity import audit
    wall_ids = {d.get('id') for _, d in sources}
    issues += [p['text'] for p in audit(drawing)]
    for ent, d in sources:
        try:
            a, b = d['a'], d['b']
            if not all(math.isfinite(float(n)) for n in (*a, *b)):
                raise ValueError('coordenada no finita')
            if math.dist(a,b) <= 1e-5 or float(d['thickness']) <= 0 or float(d['height']) <= 0:
                raise ValueError('dimensión no positiva')
            if ent.dxftype() not in ('LWPOLYLINE', 'POINT'):
                raise ValueError('registro BIM de muro inesperado')
            if ent.dxftype() == 'LWPOLYLINE' and not ent.closed and len(ent) == 2:
                vertices = list(ent.get_points('xy'))
                if distant(vertices[0], a) or distant(vertices[1], b):
                    issues.append(f'Muro {d.get("id", "sin ID")}: eje CAD diferente de a/b en XDATA (posible MOVE/ROTATE/MIRROR)')
        except (ValueError, TypeError, KeyError) as exc:
            issues.append(f'Muro {d.get("id", "sin ID")}: parámetros incorrectos ({exc})')
    for ent, d in columns:
        if ent.dxftype() != 'LWPOLYLINE':
            issues.append(f'Pilar {d.get("id", "sin ID")}: sección no poligonal')
        else:
            try:
                # Secciones regulares del plugin: la media de vértices es el centro.
                vertices = list(ent.get_points('xy'))
                if vertices:
                    center = (sum(v[0] for v in vertices)/len(vertices),
                              sum(v[1] for v in vertices)/len(vertices))
                    if distant(center, d['center']):
                        issues.append(f'Pilar {d.get("id", "sin ID")}: centro CAD diferente de XDATA (posible MOVE/ROTATE/MIRROR)')
            except (KeyError, ValueError, TypeError, ZeroDivisionError):
                issues.append(f'Pilar {d.get("id", "sin ID")}: centro BIM no válido')
    for _, d in outlines:
        owners = d.get('wall_ids') or []
        if not owners:
            issues.append('Contorno sin origen BIM')
        for ident in owners:
            if ident not in wall_ids:
                issues.append(f'Contorno referido a muro inexistente: {ident}')
    issues += _outline_issues(drawing, sources, outlines)
    issues += _space_issues(drawing)
    if any(e.dxftype()=='LWPOLYLINE' and e.closed for e,_ in sources):
        issues.append('Hay muros de versiones antiguas con geometría duplicada; ejecutar ARQMIGRAR')
    if sources and not outlines:
        issues.append('Hay muros BIM, pero no existe contorno regenerado visible')
    if sources and WALL_LAYER in drawing.layers and drawing.layers.get(WALL_LAYER).is_off() and not outlines:
        issues.append('ALERTA: capa de muros fuente apagada sin contorno regenerado')
    if drawing.header.get('$INSUNITS', 0) not in (0, 6):
        issues.append('Unidades DXF distintas de metros: falta normalizar antes de exportar IGZ')
    if drawing.header.get('$INSUNITS', 0) == 0:
        issues.append('Unidades DXF sin declarar: el modelo arquitectónico presupone metros')
    return {'muros': len(sources), 'pilares': len(columns), 'huecos': len(openings),
            'segmentos': len(outlines), 'incidencias': sorted(set(issues))}


def validar_arq(ctx, *args):
    report = audit_architecture(ctx.document)
    ctx.echo('ARQVALIDAR — lectura del DXF sin modificar el dibujo')
    ctx.echo('Muros: {muros}; pilares: {pilares}; huecos: {huecos}; segmentos: {segmentos}'.format(**report))
    if report['incidencias']:
        for issue in report['incidencias']:
            ctx.echo('  AVISO: ' + issue)
    else:
        ctx.echo('No se detectaron incidencias en las comprobaciones implementadas.')
    ctx.echo('La ausencia de avisos no acredita geometría 3D ni IFC válido.')
    return report


def _segment_key(a, b, nd=6):
    a = (round(float(a[0]), nd), round(float(a[1]), nd))
    b = (round(float(b[0]), nd), round(float(b[1]), nd))
    return (a, b) if a <= b else (b, a)


def _arc_key(cx, cy, r, t0, t1, nd=5):
    """An arc by its circle and three of its points (two half circles of
    one round wall share their ends: the middle tells them apart)."""
    import math
    sweep = (t1 - t0) % 360.0
    pts = [(cx + r * math.cos(math.radians(t)), cy + r * math.sin(math.radians(t)))
           for t in (t0, t0 + sweep / 2, t1)]
    rnd = [(round(x, nd) + 0.0, round(y, nd) + 0.0) for x, y in pts]
    return ('arc', round(cx, nd) + 0.0, round(cy, nd) + 0.0, round(r, nd), rnd[1]) + _segment_key(rnd[0], rnd[2], nd)


def _item_key(it, nd=5):
    if it[0] == 'arc':
        _k, c, r, t0, t1 = it[:5]
        return _arc_key(c[0], c[1], r, t0, t1, nd)
    return _segment_key(it[1], it[2])


def _entity_key(e, nd=5):
    if e.dxftype() == 'ARC':
        c = e.dxf.center
        return _arc_key(c.x, c.y, float(e.dxf.radius), float(e.dxf.start_angle), float(e.dxf.end_angle), nd)
    return _segment_key((e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y))


def _outline_issues(drawing, sources, outlines):
    """Compare the plan lines in the drawing with the outline the current
    walls produce. Lines left over are what a COPY/MOVE of the visible lines
    alone leaves behind (a "phantom room": drawn, but no BIM wall)."""
    if not sources or not outlines:
        return []
    from .exchange import read_model
    from .geom import junctions as J
    from . import sync as SY
    try:
        from .openings import opening_cuts
        records, columns, ops, _issues = read_model(drawing, strict=False)
        specs = J.walls_from_records(records)
        result = J.solve(specs, [(cid, m['polygon']) for cid, m in columns])
        cuts = opening_cuts({w.id: w for w in specs}, ops)
        expected = {_item_key(it) for it in J.plan_items(result, cuts)}
    except Exception as exc:  # noqa: BLE001
        return [f'No se pudo comprobar el contorno ({type(exc).__name__}: {exc})']
    present = {}
    for e, _d in outlines:
        k = _entity_key(e)
        present[k] = present.get(k, 0) + 1
    extra = sum(n for k, n in present.items() if k not in expected) + \
        sum(n - 1 for k, n in present.items() if k in expected and n > 1)
    missing = len(expected - set(present))
    out = []
    if extra:
        out.append(f'Contorno con {extra} línea(s) sin muro BIM (copiadas o desplazadas sin su muro): '
                   'ejecute UNIONESARQ para eliminarlas')
    if missing:
        out.append(f'Contorno desactualizado: faltan {missing} línea(s): ejecute UNIONESARQ')
    grouped = set()
    for _name, g in SY.arq_groups(drawing):
        grouped |= {e.dxf.handle for e in g if e.is_alive}
    loose = sum(1 for e, _d in sources if e.dxf.handle not in grouped)
    if loose:
        out.append(f'{loose} muro(s) sin grupo de selección (al pinchar su contorno no se selecciona el muro): '
                   'ejecute UNIONESARQ')
    return out


def _space_issues(drawing):
    """Spaces whose seed no longer lies in a closed room, or whose outline is
    out of date with the walls (UNIONESARQ recomputes them)."""
    spaces = [(e, d) for e in drawing.modelspace()
              if (d := metadata(e)) and d.get('kind') == 'space']
    if not spaces:
        return []
    from .exchange import read_model
    from .geom import junctions as J
    from .geom import spaces as SP
    try:
        records, columns, _ops, _issues = read_model(drawing, strict=False)
        result = J.solve(J.walls_from_records(records),
                         [(cid, m['polygon']) for cid, m in columns])
        comps = SP.components(result)
    except Exception as exc:  # noqa: BLE001
        return [f'No se pudieron comprobar los recintos ({type(exc).__name__}: {exc})']
    out, seen = [], {}
    for e, d in spaces:
        name = d.get('name') or 'Recinto'
        room, why = SP.space_at(result, d.get('seed') or (0, 0), comps)
        if room is None:
            out.append(f'Recinto {name}: ' + ('su punto interior queda dentro de un muro o pilar'
                       if why == 'muro' else 'no está cerrado (falta un muro o una separación)'))
            continue
        key = tuple(_segment_key(q, q)[0] for q in room['outer'])
        if key in seen:
            out.append(f'Recintos {seen[key]} y {name} ocupan la misma estancia')
        seen.setdefault(key, name)
        now = [(round(float(q[0]), 6), round(float(q[1]), 6)) for q in e.get_points('xy')]
        want = [(round(float(q[0]), 6), round(float(q[1]), 6)) for q in room['outer']]
        if now != want or abs(float(d.get('area', 0)) - room['area']) > 1e-6:
            out.append(f'Recinto {name}: contorno o superficie desactualizados: ejecute UNIONESARQ')
    return out

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
        if chunks and metadata(entity) is None:
            issues.append(f'XDATA ARQ ilegible en entidad {entity.dxf.handle}: revisar o restaurar datos')
    # Auditoría informativa: no cambiar ids ni reconstruir geometría por sorpresa.
    geometry_tolerance = 1e-5
    def distant(a, b):
        return math.dist(tuple(map(float,a[:2])), tuple(map(float,b[:2]))) > geometry_tolerance
    ids = [d.get('id') for _, d in sources + columns + openings]
    for ident, count in Counter(ids).items():
        if not ident:
            issues.append('Objeto arquitectónico sin identificador BIM')
        elif count > 1:
            issues.append(f'Identificador BIM duplicado: {ident} ({count} objetos)')
    wall_ids = {d.get('id') for _, d in sources}
    for _, d in openings:
        if d.get('wall_id') not in wall_ids:
            issues.append(f'Hueco sin muro anfitrión: {d.get("id", "sin ID")}')
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

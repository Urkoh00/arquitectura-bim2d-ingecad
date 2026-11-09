# SPDX-License-Identifier: GPL-3.0-or-later
"""EXPORTARBIM: write the ``.arqbim`` contract for IngeTrazo.

Replaces the IGZ bridge for end users: no IngeTrazo sources, no external
Python. The file is opened in IngeTrazo by the ``arquitectura_bim``
extension (double-click, Open, or Extensions menu), which builds the model
with IngeTrazo's own classes; IngeTrazo then saves IGZ and exports IFC.
"""
from __future__ import annotations

from pathlib import Path


def _choose_path(ctx):
    from .compat import dialog_parent
    window = dialog_parent(ctx)
    try:
        from PySide6.QtWidgets import QFileDialog
        suggested = 'arquitectura.arqbim'
        doc_path = getattr(getattr(ctx, 'document', None), 'path', None)
        if doc_path:
            suggested = str(Path(doc_path).with_suffix('.arqbim'))
        name, _f = QFileDialog.getSaveFileName(window, 'Exportar modelo BIM para IngeTrazo',
                                               suggested, 'Arquitectura BIM (*.arqbim)')
        return Path(name).expanduser().resolve() if name else None
    except (ImportError, RuntimeError, TypeError) as exc:
        ctx.echo('No se puede abrir el selector de archivos: ' + str(exc))
        return None


def exportar_bim(ctx, *args):
    from .exchange import write
    document = ctx.document
    if document is None:
        ctx.echo('No hay un dibujo activo.')
        return None
    units = int(document.doc.header.get('$INSUNITS', 0))
    if units not in (0, 6):
        ctx.echo(f'EXPORTARBIM: el dibujo está en unidades $INSUNITS={units}; '
                 'el contrato exige metros (6). No se convierte nada en silencio.')
        return None
    dest = Path(' '.join(map(str, args))).expanduser().resolve() if args else _choose_path(ctx)
    if dest is None:
        ctx.echo('EXPORTARBIM cancelado.')
        return None
    if dest.suffix.lower() != '.arqbim':
        dest = dest.with_suffix('.arqbim')
    from . import integrity as IG
    problems = IG.audit(document.doc)
    if problems:
        # never blocked, never silent: the operator sees them and decides
        from . import bim_dialogs as BD
        if BD.available(ctx):
            if not BD.problems_dialog(ctx, problems):
                IG.highlight(ctx, [h for p in problems for h in p['handles']])
                ctx.echo(f'EXPORTARBIM cancelado: {len(problems)} problemas por corregir '
                         f'({IG.summary(problems)}); quedan seleccionados en el dibujo.')
                return None
        else:
            ctx.echo(f'EXPORTARBIM: {len(problems)} problemas ({IG.summary(problems)}); '
                     'se exporta sin los elementos afectados:')
            for p in problems:
                ctx.echo('  · ' + p['text'])
    try:
        tmp = dest.with_suffix('.arqbim.tmp')
        name = Path(getattr(document, 'path', '') or 'Proyecto').stem
        data = write(document.doc, tmp, project=name, problems=problems)
        if not data['elements']:
            tmp.unlink(missing_ok=True)
            ctx.echo('No hay muros ni pilares BIM que exportar.')
            return None
        tmp.replace(dest)                       # never leave a half-written file
    except ValueError as exc:
        ctx.echo(f'EXPORTARBIM: {exc}')
        return None
    walls = sum(1 for e in data['elements'] if e['ifc_class'] == 'IfcWall')
    cols = sum(1 for e in data['elements'] if e['ifc_class'] == 'IfcColumn')
    spaces = sum(1 for e in data['elements'] if e['ifc_class'] == 'IfcSpace')
    doors = sum(1 for e in data['elements'] if e['ifc_class'] == 'IfcDoor')
    windows = sum(1 for e in data['elements'] if e['ifc_class'] == 'IfcWindow')
    gaps = sum(1 for e in data['elements'] for o in e.get('openings', []) if o.get('kind') == 'gap')
    vol = sum(e['volume'] for e in data['elements'] if e['ifc_class'] in ('IfcWall', 'IfcColumn'))
    rec = f', {spaces} recintos' if spaces else ''
    rec += f', {doors} puertas, {windows} ventanas y {gaps} huecos' if doors or windows or gaps else ''
    ctx.echo(f'EXPORTARBIM: {dest.name} — {walls} muros, {cols} pilares{rec}, '
             f'volumen construido {vol:.3f} m³. Ábralo en IngeTrazo (extensión arquitectura_bim).')
    if spaces:
        ctx.echo('  Nota: el exportador IFC actual de IngeTrazo coloca los recintos (IfcSpace) dentro de '
                 'la planta en lugar de agregarlos a ella; IfcOpenShell lo marca como error de reglas '
                 'IFC4. La corrección está preparada para proponerla a su desarrollador.')
    shown = {p['text'] for p in problems}
    for issue in data['issues']:
        if issue not in shown:
            ctx.echo('  Aviso: ' + issue)
    if problems:
        ctx.echo(f'  Omitidos {len(IG.omitted_handles(problems))} elementos con problemas (ver arriba).')
    return data

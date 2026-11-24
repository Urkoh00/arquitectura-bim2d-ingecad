# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: Doble clic sobre un elemento BIM (IngeCAD 0.8): abre su ficha o retoma su orden.
#   (Guía del código: docs/GUIA_DEL_CODIGO.md)
"""Double-click on a BIM element (IngeCAD 0.8: ``PluginSpec.on_double_click``,
asked for by this plugin): the drawing order starts with its properties,
the way the reference program's «menú virtual» does.

* a wall (any line of its outline) -> MURO with its thickness, height,
  base, face, type, layers and material;
* a door, window or gap (its symbol) -> CARPINTERIA with its model;
* a column -> PILAR with its section;
* a room (its outline or its label) -> its sheet, to edit it.

Anything else is left to IngeCAD's own double-click.  On an IngeCAD without
the hook, MURO's G option and PROPIEDADESARQ do the same."""
from __future__ import annotations

_PRESETS = {}


def preset(tool_name):
    """The properties a double-click left for ``tool_name`` (taken once)."""
    return _PRESETS.pop(tool_name, None)


def on_double_click(ctx, entity):
    from .architectural import metadata
    from .arq_properties import resolve_arch_entity
    doc = getattr(ctx, "document", None)
    if doc is None or entity is None:
        return False
    target, _reason = resolve_arch_entity(doc, entity)
    if target is None:
        return False
    m = dict(metadata(target) or {})
    kind = m.get("kind")
    if kind == "slab":
        from .arq_properties import editar_propiedades
        return editar_propiedades(ctx, target)
    tool = {"wall": "MURO", "opening": "CARPINTERIA", "column": "PILAR"}.get(kind)
    if kind == "wall" and m.get("wall_category") == "defensa":
        tool = "DEFENSA"                 # una defensa abre DEFENSA, no MURO
    if tool:
        _PRESETS[tool] = m
        ctx.start_tool(tool)
        return True
    if kind == "space":
        from . import bim_dialogs
        from .arq_properties import space_change
        if not bim_dialogs.available(ctx):
            return False
        values = bim_dialogs.space_properties(ctx, m)
        if values is not None:
            from .transactions import apply_architectural_change
            try:
                # como PROPIEDADESARQ: regenera etiqueta y envolvente
                apply_architectural_change(ctx, space_change(target, values), kind="space")
            except ValueError as exc:
                ctx.echo(f"Recinto: {exc}")
        return True
    return False

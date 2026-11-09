# SPDX-License-Identifier: GPL-3.0-or-later
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
    tool = {"wall": "MURO", "opening": "CARPINTERIA", "column": "PILAR"}.get(kind)
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
            from .transactions import SafeArchitecturalCommand
            ctx.execute(SafeArchitecturalCommand("ARQ RECINTO", [space_change(target, values)]))
        return True
    return False

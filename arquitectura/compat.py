# SPDX-License-Identifier: GPL-3.0-or-later
"""Contexto IngeCAD: PluginContext y ToolContext son tipos distintos.

Los comandos reciben PluginContext.document. Las herramientas reciben
ToolContext(services=ToolController), cuyo documento vive en services.window.
No se asignan atributos dinámicos al dataclass del núcleo.
"""

def document_of(ctx):
    doc = getattr(ctx, "document", None)
    if doc is None:
        services = getattr(ctx, "services", None)
        window = getattr(services, "window", None)
        doc = getattr(window, "document", None)
    return doc

def require_document(ctx):
    document = document_of(ctx)
    if document is None:
        raise RuntimeError("No hay dibujo activo en IngeCAD")
    return document


def dialog_parent(ctx):
    """The QWidget to parent a dialog on, or None.

    A command handler's ``ctx.host`` IS the main window; ``host.window`` is
    then Qt's ``QWidget.window`` METHOD, not a widget (EXPORTARBIM failed on
    Windows with "called with wrong argument types"). A tool's context keeps
    the window in ``ctx.services.window``. Only real widgets are returned."""
    try:
        from PySide6.QtWidgets import QWidget
    except ImportError:
        return None
    for cand in (getattr(ctx, "host", None),
                 getattr(getattr(ctx, "services", None), "window", None),
                 getattr(getattr(ctx, "host", None), "window", None)):
        if isinstance(cand, QWidget):
            return cand
    return None

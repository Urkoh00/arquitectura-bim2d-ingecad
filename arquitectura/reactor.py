# SPDX-License-Identifier: GPL-3.0-or-later
"""Keeps BIM data true after edits made with IngeCAD's own commands.

IngeCAD 0.8 runs plugin reactors (``PluginSpec.reactors``, the
generalisation of its associative-dimension reactor, proposed by this
plugin) after every recorded command, in the same undo step.  After a
MOVE, ROTATE, SCALE, MIRROR, COPY, STRETCH or grip edit that touched a BIM
element, the plan is regenerated: the regeneration reads each element's
frame (frame.py) and brings its data into line, gives copies their own
identity and redraws the outline.  One undo restores everything.

On an IngeCAD without reactors this module is not used: the same happens
at the next plugin order or UNIONESARQ.
"""
from __future__ import annotations

from core.commands import Command

from .architectural import APPID, metadata
from .frame import FRAME_APPID

KINDS = ("wall", "column", "space", "opening")


def _fingerprint(e):
    try:
        pts = tuple(tuple(round(c, 9) for c in p) for p in e.get_points("xyb")) + (e.closed,)
    except Exception:  # noqa: BLE001
        return None
    try:
        frame = tuple(tuple(t.value) if hasattr(t.value, "__len__") else t.value
                      for t in e.get_xdata(FRAME_APPID)) if e.has_xdata(FRAME_APPID) else None
    except Exception:  # noqa: BLE001
        frame = None
    return pts, frame


def _snapshot(drawing):
    out = {}
    for e in drawing.modelspace():
        if e.dxftype() != "LWPOLYLINE":
            continue
        try:
            if not e.has_xdata(APPID):
                continue
        except Exception:  # noqa: BLE001
            continue
        m = metadata(e)
        if m and m.get("kind") in KINDS:
            out[e.dxf.handle] = (m.get("id"), _fingerprint(e))
    return out


class ArquitecturaReactor:
    name = "arquitectura"

    def before(self, document):
        if getattr(document, "_arq_reacting", False):
            return None
        snap = _snapshot(document.doc)
        return snap or None

    def react(self, document, state):
        if getattr(document, "_arq_reacting", False):
            return None
        if _snapshot(document.doc) == state:
            return None
        return SyncCommand()


class SyncCommand(Command):
    """The plan regenerated after a generic edit, as a follow-up of it."""
    name = "ARQ SINCRONIZAR BIM"
    needs_regen = True

    def __init__(self):
        self._regen = None

    def do(self, document):
        from .wall_network import RegenerateContoursCommand
        document._arq_reacting = True
        try:
            if self._regen is None:
                self._regen = RegenerateContoursCommand()
            self._regen.do(document)
        finally:
            document._arq_reacting = False

    def undo(self, document):
        if self._regen is not None:
            document._arq_reacting = True
            try:
                self._regen.undo(document)
            finally:
                document._arq_reacting = False

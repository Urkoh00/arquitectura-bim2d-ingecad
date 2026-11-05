# SPDX-License-Identifier: GPL-3.0-or-later
"""Keeps BIM data true after edits made with IngeCAD's own commands.

Uses the follow-up hook proposed upstream (``PluginSpec.reactors`` ->
``core.commands.REACTORS``, the generalisation of the associative-dimension
reactor). After any recorded command:

* an architectural entity that appeared carrying an ID that already exists
  (COPY, MIRROR keeping the source, ARRAY, paste) gets a NEW identity — the
  original keeps its own;
* a wall whose CAD axis moved (MOVE, ROTATE, MIRROR, STRETCH, grips) gets its
  XDATA ``a``/``b`` rewritten from the axis; a column its ``center``;
* if the plan outline exists, it is regenerated.

Everything happens in ONE follow-up command joined to the user's command:
one undo restores geometry, identities, XDATA and outline together.
Without the upstream hook this module is inert (ARQVALIDAR still reports).
"""
from __future__ import annotations

import math
import uuid

from core.commands import Command

from .architectural import _xdata, metadata

KINDS = ("wall", "column")


def _fingerprint(e):
    try:
        return tuple(tuple(round(c, 9) for c in p) for p in e.get_points("xy")) + (e.closed,)
    except Exception:  # noqa: BLE001
        return None


def _snapshot(drawing):
    out = {}
    for e in drawing.modelspace():
        if e.dxftype() != "LWPOLYLINE":
            continue
        m = metadata(e)
        if m and m.get("kind") in KINDS:
            out[e.dxf.handle] = (m.get("id"), _fingerprint(e))
    return out


class ArquitecturaReactor:
    name = "arquitectura"

    def before(self, document):
        snap = _snapshot(document.doc)
        return snap or None

    def react(self, document, state):
        if getattr(document, "_arq_reacting", False):
            return None
        now = _snapshot(document.doc)
        ids_before = {v[0] for v in state.values()}
        changes = []                    # (entity, new_metadata)
        db = document.doc.entitydb
        seen_ids = {}
        for handle, (ident, fp) in now.items():
            e = db.get(handle)
            old = state.get(handle)
            m = dict(metadata(e))
            changed = False
            if old is None and ident in ids_before:
                m["id"] = uuid.uuid4().hex             # a copy: new identity
                m["copied_from"] = ident
                changed = True
            elif ident in seen_ids:                     # duplicate created otherwise
                m["id"] = uuid.uuid4().hex
                changed = True
            seen_ids[m["id"]] = handle
            if old is None or old[1] != fp or changed:
                pts = [tuple(map(float, p)) for p in e.get_points("xy")]
                if m["kind"] == "wall" and not e.closed and len(pts) == 2:
                    if math.dist(pts[0], m["a"]) > 1e-9 or math.dist(pts[1], m["b"]) > 1e-9:
                        m["a"], m["b"] = list(pts[0]), list(pts[1])
                        changed = True
                elif m["kind"] == "column" and pts:
                    cx = sum(p[0] for p in pts) / len(pts)
                    cy = sum(p[1] for p in pts) / len(pts)
                    if math.dist((cx, cy), m.get("center", (cx, cy))) > 1e-9:
                        m["center"] = [cx, cy]
                        changed = True
            if changed:
                changes.append((e, m))
        geometry_moved = any(state.get(h, (None, None))[1] != v[1] for h, v in now.items()) \
            or set(now) != set(state)
        if not changes and not geometry_moved:
            return None
        return SyncCommand(changes, regenerate=geometry_moved and _has_outline(document))


def _has_outline(document):
    for e in document.doc.modelspace():
        if e.dxftype() == "LINE" and (metadata(e) or {}).get("kind") == "junction_edge":
            return True
    return False


class SyncCommand(Command):
    name = "ARQ SINCRONIZAR BIM"
    needs_regen = True

    def __init__(self, changes, regenerate):
        self.changes = changes
        self.regenerate = regenerate
        self._old = []
        self._regen = None

    @property
    def entities(self):
        return [e for e, _m in self.changes]

    def do(self, document):
        msp = document.doc.modelspace()
        self._old = []
        for e, m in self.changes:
            self._old.append((e, metadata(e)))
            _xdata(msp, e, m)
        if self.regenerate:
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
            self._regen.undo(document)
        msp = document.doc.modelspace()
        for e, m in reversed(self._old):
            _xdata(msp, e, m)

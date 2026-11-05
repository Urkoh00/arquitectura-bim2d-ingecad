# SPDX-License-Identifier: GPL-3.0-or-later
"""Keep BIM data and plan representation together without host hooks.

Two pieces, both used by ``UNIONESARQ`` (RegenerateContoursCommand) inside
one undoable command, and by the optional follow-up reactor:

* ``sync_changes``: what a generic CAD edit left behind. A copy carries the
  identity of its original (COPY, MIRROR keeping the source, ARRAY, paste):
  the OLDEST entity (lowest DXF handle: handles only grow) keeps the ID and
  every later one gets a new identity with ``copied_from``. A wall whose
  visible axis was moved/rotated/stretched gets ``a``/``b`` rewritten from
  the axis; a column its ``center``. The CAD geometry is the authority.

* Selection groups: one native IngeCAD/AutoCAD GROUP per wall, "ARQ_<axis
  handle>", holding the hidden axis and the plan lines derived from it.
  IngeCAD's selection expands a pick to the whole selectable group (the
  axis on its switched-off layer included), so picking any visible line of
  a wall takes the wall: COPY/MOVE/ERASE/MIRROR act on the BIM object and
  its drawing together, never on the derived lines alone.
"""
from __future__ import annotations

import copy
import math
import uuid

from .architectural import metadata

GROUP_PREFIX = "ARQ_"
KINDS = ("wall", "column", "opening")


def _handle_key(entity):
    try:
        return int(entity.dxf.handle, 16)
    except (TypeError, ValueError):
        return 0


def _points(entity):
    return [tuple(map(float, p)) for p in entity.get_points("xy")]


def sync_changes(drawing, tol=1e-9):
    """[(entity, new_metadata)] needed to make XDATA true to the drawing.
    Read-only: nothing is written here."""
    tagged = []
    for e in drawing.modelspace():
        m = metadata(e)
        if m and m.get("kind") in KINDS and m.get("id"):
            tagged.append((e, m))
    tagged.sort(key=lambda em: _handle_key(em[0]))
    seen = set()
    changes = []
    for e, m in tagged:
        new = copy.deepcopy(m)
        changed = False
        if m["id"] in seen:
            new["id"] = uuid.uuid4().hex
            new["copied_from"] = m["id"]
            changed = True
        seen.add(new["id"])
        if e.dxftype() == "LWPOLYLINE":
            pts = _points(e)
            if m["kind"] == "wall" and not e.closed and len(pts) == 2 and "a" in m and "b" in m:
                if math.dist(pts[0], m["a"][:2]) > tol or math.dist(pts[1], m["b"][:2]) > tol:
                    new["a"], new["b"] = list(pts[0]), list(pts[1])
                    changed = True
            elif m["kind"] == "column" and pts:
                c = [sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)]
                old = m.get("center") or c
                if math.dist(c, old[:2]) > tol:
                    new["center"] = c
                    changed = True
        if changed:
            changes.append((e, new))
    return changes


# --- selection groups --------------------------------------------------------

def arq_groups(drawing):
    """[(name, group)] of the plugin's selection groups."""
    try:
        return [(n, g) for n, g in drawing.groups if str(n).startswith(GROUP_PREFIX)]
    except Exception:  # noqa: BLE001
        return []


def snapshot_groups(drawing):
    """[(name, [member handles], description)] to restore on undo."""
    out = []
    for name, g in arq_groups(drawing):
        out.append((name, [e.dxf.handle for e in g if e.is_alive],
                    str(g.dxf.get("description", "") or "")))
    return out


def delete_groups(drawing):
    for name, _g in arq_groups(drawing):
        try:
            drawing.groups.delete(name)
        except Exception:  # noqa: BLE001
            pass


def create_group(drawing, name, entities, description=""):
    entities = [e for e in entities if e is not None and e.is_alive]
    if not entities:
        return None
    if name in drawing.groups:
        drawing.groups.delete(name)
    g = drawing.groups.new(name)
    g.set_data(entities)
    g.dxf.selectable = 1
    if description:
        g.dxf.description = description[:64]
    return g


def wall_axes(drawing):
    """{wall id: axis entity} for the current (already synchronised) walls."""
    out = {}
    for e in drawing.modelspace():
        m = metadata(e) or {}
        if m.get("kind") == "wall" and m.get("id") and e.dxftype() == "LWPOLYLINE":
            out.setdefault(m["id"], e)
    return out


def build_wall_groups(drawing, lines_by_wall):
    """One selectable group per wall: its axis + its derived plan lines."""
    axes = wall_axes(drawing)
    names = []
    for ident, axis in axes.items():
        name = GROUP_PREFIX + str(axis.dxf.handle).upper()
        m = metadata(axis) or {}
        label = m.get("name") or "Muro"
        create_group(drawing, name, [axis, *lines_by_wall.get(ident, [])],
                     f"{label} BIM {ident[:8]} (Arquitectura)")
        names.append(name)
    return names

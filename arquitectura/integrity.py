# SPDX-License-Identifier: GPL-3.0-or-later
"""Integrity of the BIM data before exporting: report, never block.

Before an export the whole drawing is checked and every problem is listed
with the entities it concerns, so the operator can see them highlighted in
the drawing and decide: export without those elements, or go back and fix
them.  Nothing here edits the drawing.

Problems found (the IDs are those of the independent audit of v1.15):
* ``ilegible``  - an entity carries plugin data that cannot be read (0024):
  before, it simply vanished from the export.
* ``sin_id``    - a BIM object without identity.
* ``duplicado`` - two objects with one identity, usually a generic COPY
  (0013, now also for spaces): the newest copy is left out; UNIONESARQ
  gives it an identity of its own.
* ``huerfano``  - a door, window or gap whose host wall does not exist
  (0001): before, it was dropped without a word.
* ``hueco``     - an opening that does not fit in its wall, overlaps
  another one or has impossible measures (0005).
* ``datos``     - a wall, column or space with missing or impossible measures.
"""
from __future__ import annotations

import math

from .architectural import APPID, metadata

KINDS = ("wall", "column", "opening", "space")
NAMES = {"wall": "Muro", "column": "Pilar", "opening": "Carpintería", "space": "Recinto"}
TOL = 1e-6


def _num(value):
    if isinstance(value, bool):
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _label(m):
    kind = m.get("kind")
    name = m.get("name") or m.get("type_name") or ""
    if kind == "opening":
        kind_name = {"door": "Puerta", "window": "Ventana", "gap": "Hueco"}.get(m.get("type"), "Carpintería")
    else:
        kind_name = NAMES.get(kind, "Elemento")
    return f"{kind_name} {name}".strip() if name else f"{kind_name} {str(m.get('id', ''))[:8]}"


def _problem(code, text, entities, ids=()):
    return {"code": code, "text": text,
            "handles": [e.dxf.handle for e in entities],
            "ids": [i for i in ids if i]}


def audit(drawing):
    """[problem] of the drawing's BIM data; each problem is a dict with
    ``code``, ``text``, ``handles`` (entities to highlight / omit) and ``ids``."""
    problems = []
    tagged = []
    for e in drawing.modelspace():
        try:
            has = e.has_xdata(APPID)
        except Exception:
            has = False
        if not has:
            continue
        m = metadata(e)
        if m is None:
            problems.append(_problem(
                "ilegible", f"Datos BIM ilegibles en la entidad {e.dxf.handle} ({e.dxftype()}, capa "
                f"{e.dxf.layer}): no se puede exportar; restáurelos o vuelva a crear el elemento.", [e]))
            continue
        if m.get("kind") in KINDS:
            tagged.append((e, m))

    # identities: the oldest entity keeps it, newer ones are copies
    def handle_key(em):
        try:
            return int(em[0].dxf.handle, 16)
        except (TypeError, ValueError):
            return 0
    tagged.sort(key=handle_key)
    seen, valid = {}, []
    for e, m in tagged:
        ident = m.get("id")
        if not ident or not isinstance(ident, str):
            problems.append(_problem("sin_id", f"{_label(m)} sin identificador BIM (entidad {e.dxf.handle}).", [e]))
            continue
        if ident in seen:
            first = seen[ident]
            problems.append(_problem(
                "duplicado", f"{_label(m)}: identificador BIM duplicado con la entidad {first.dxf.handle}; "
                "suele ser una COPIA. Se omite la copia; UNIONESARQ le da identidad propia.", [e], [ident]))
            continue
        seen[ident] = e
        valid.append((e, m))

    # measures of every element
    walls = {}
    for e, m in valid:
        kind = m["kind"]
        bad = []
        if kind in ("wall", "column", "space"):
            h = _num(m.get("height"))
            if h is None or h <= 0:
                bad.append("altura")
            if _num(m.get("base", 0)) is None:
                bad.append("cota")
        if kind == "wall":
            t = _num(m.get("thickness"))
            if t is None or t <= 0:
                bad.append("espesor")
            try:
                a, b = (tuple(map(float, m[k][:2])) for k in ("a", "b"))
                if not all(map(math.isfinite, a + b)) or math.dist(a, b) < 1e-5:
                    bad.append("eje")
            except (KeyError, TypeError, ValueError, IndexError):
                bad.append("eje")
        if kind == "space":
            seed = m.get("seed")
            if not (isinstance(seed, (list, tuple)) and len(seed) >= 2 and all(_num(v) is not None for v in seed[:2])):
                bad.append("punto interior")
        if bad:
            problems.append(_problem("datos", f"{_label(m)}: datos no válidos ({', '.join(bad)}).", [e], [m["id"]]))
            continue
        if kind == "wall":
            walls[m["id"]] = (e, m)

    # openings against their host
    from .geom.junctions import walls_from_records
    try:
        specs = {w.id: w for w in walls_from_records([(i, m) for i, (_e, m) in walls.items()])}
    except Exception:
        specs = {}
    by_host = {}
    for e, m in valid:
        if m["kind"] != "opening":
            continue
        host = m.get("wall_id")
        if host not in walls:
            problems.append(_problem(
                "huerfano", f"{_label(m)} sin muro anfitrión (el muro {str(host)[:8]} no existe): "
                "no se puede exportar; bórrela o vuelva a colocarla en un muro.", [e], [m["id"]]))
            continue
        s, w, z, h = (_num(m.get(k)) for k in ("offset", "width", "sill", "height"))
        wall_e, wall_m = walls[host]
        why = None
        if None in (s, w, z, h) or w <= 0 or h <= 0:
            why = "medidas no válidas"
        elif s < -TOL or (host in specs and s + w > specs[host].length + 1e-6):
            why = "no cabe en la longitud del muro"
        elif z < -TOL or z + h > float(wall_m["height"]) + 1e-6:
            why = "no cabe en la altura del muro"
        if why:
            problems.append(_problem("hueco", f"{_label(m)}: {why}.", [e, wall_e], [m["id"], host]))
            continue
        for other_e, o in by_host.get(host, []):
            ds = min(s + w, float(o["offset"]) + float(o["width"])) - max(s, float(o["offset"]))
            dz = min(z + h, float(o["sill"]) + float(o["height"])) - max(z, float(o["sill"]))
            if ds > 1e-6 and dz > 1e-6:
                problems.append(_problem("hueco", f"{_label(m)} se solapa con {_label(o)} en el mismo muro.",
                                         [e, other_e], [m["id"], o["id"]]))
                break
        else:
            by_host.setdefault(host, []).append((e, m))
    return problems


def omitted_handles(problems):
    """Handles of the entities the export leaves out (the walls that are
    only mentioned as hosts are not left out)."""
    out = set()
    for p in problems:
        if p["handles"]:
            out.add(p["handles"][0])
    return out


def summary(problems):
    from collections import Counter
    c = Counter(p["code"] for p in problems)
    names = {"ilegible": "datos ilegibles", "sin_id": "sin identificador", "duplicado": "copias sin identidad",
             "huerfano": "carpinterías sin muro", "hueco": "huecos que no caben o se solapan",
             "datos": "datos no válidos"}
    return ", ".join(f"{n} {names.get(k, k)}" for k, n in c.items())


def highlight(ctx, handles):
    """Select (and frame) the entities in IngeCAD, when its window offers it.
    Uses only what the official IngeCAD already has; without it, nothing."""
    services = getattr(ctx, "services", None)
    document = getattr(ctx, "document", None)
    if services is None or document is None:
        return False
    handles = [h for h in handles if h]
    try:
        if hasattr(services, "selection"):
            services.selection = set(handles)
            for attr in ("_highlight_cache", "_grips_cache"):
                if hasattr(services, attr):
                    setattr(services, attr, None)
            changed = getattr(services, "changed", None)
            if changed is not None and hasattr(changed, "emit"):
                changed.emit()
        window = getattr(services, "window", None)
        if window is not None and hasattr(window, "zoom_to_entity") and handles:
            from ezdxf import bbox
            ents = [document.doc.entitydb.get(h) for h in handles]
            ents = [e for e in ents if e is not None]
            if ents:
                box = bbox.extents(ents, fast=True)
                if box.has_data:
                    pad = max(box.size.x, box.size.y, 1.0) * 0.6
                    window.viewport.view.zoom_extents(box.extmin.x - pad, box.extmin.y - pad,
                                                      box.extmax.x + pad, box.extmax.y + pad)
                    window.viewport.update()
        return True
    except Exception:
        return False

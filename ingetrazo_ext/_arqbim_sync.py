# SPDX-License-Identifier: GPL-3.0-or-later
"""Auxiliary proposal: source-owned groups, one native undo command.

Loaded next to arquitectura_bim.py; never modifies the host. Legacy imports
without an ownership marker require an explicit migration, not guessing by name.
"""
from __future__ import annotations
import copy
import hashlib
import json
from core.history import Command

KEY = 'arquitectura_import'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False,
                                     separators=(',', ':')).encode()).hexdigest()


def marker(group):
    return (getattr(group, 'ext', None) or {}).get(KEY, {})


def prepare(scene, incoming, data, model_key, definition):
    """Build the complete change before History.execute; None is a true no-op.

    model_key is explicit, never an absolute workstation path. Cross-source
    identity collisions and old unowned imports are rejected conservatively.
    """
    if not isinstance(model_key, str) or not model_key.strip():
        raise ValueError('Clave de modelo vacía')
    if getattr(scene, 'edit_group', None):
        raise ValueError('Cierre el grupo en edición antes de reimportar')
    ids = [e['id'] for e in data['elements']]
    guids = [e['guid'] for e in data['elements']]
    if len(set(ids)) != len(ids) or len(set(guids)) != len(guids):
        raise ValueError('Identidades repetidas en el modelo')
    owners = [g for g in scene.groups if marker(g).get('model_key') == model_key]
    if len(owners) > 1:
        raise ValueError('Varios contenedores con la misma clave')
    root = owners[0] if owners else None
    def walk(groups):
        for g in groups:
            yield g
            yield from walk(getattr(g, 'children', ()) or ())
    own = set(walk([root])) if root else set()
    for g in walk(scene.groups):
        if g in own:
            continue
        rec = (getattr(g, 'ext', None) or {}).get('arquitectura') or {}
        if rec.get('source_id') in ids or (getattr(g, 'ifc', None) or {}).get('guid') in guids:
            raise ValueError('Identidad ya presente fuera del modelo; migración explícita necesaria')
    signature = digest(data)
    if root and marker(root).get('signature') == signature:
        return None
    old = {((g.ext or {}).get('arquitectura') or {}).get('source_id'): g
           for g in (root.children or [])} if root else {}
    items = {e['id']: e for e in data['elements']}
    children = []
    updates = []
    for g in incoming.groups:
        rec = g.ext['arquitectura']; ident = rec['source_id']; sig = digest(items[ident])
        previous = old.get(ident)
        if previous and marker(previous).get('signature') == sig:
            children.append(previous)
        else:
            # Preserve foreign namespaces, but the source owns architecture/IFC.
            if previous:
                g.ext = {**copy.deepcopy(previous.ext or {}), **g.ext}
            g.ext[KEY] = {'signature': sig}
            if previous:
                updates.append((previous,g))
                children.append(previous)
            else:
                children.append(g)
    # Non-source children remain user-owned.
    children += [g for g in (root.children or []) if not (g.ext or {}).get('arquitectura')] if root else []
    value = copy.deepcopy(scene.plugin_data.get('arquitectura') or {})
    models = dict(value.get('models') or {})
    models[model_key] = definition
    value['models'] = models
    offset = ((incoming.plugin_data or {}).get('arquitectura') or {}).get('survey_offset')
    if offset:
        value['survey_offset'] = offset
    return SyncCommand(root, children, incoming, model_key, signature, value, updates)


class SyncCommand(Command):
    def __init__(self, root, children, incoming, key, signature, value, updates):
        from core.group import Group
        self.root = root or Group(name=key)
        self.children = children
        self.incoming = incoming
        self.ext = {**copy.deepcopy(self.root.ext or {}), KEY: {'model_key': key, 'signature': signature}}
        self.value = value
        self.updates = updates
        self.before = None

    def do(self, scene):
        self.before = (list(scene.groups), list(self.root.children or []),
                       self.root.ext, self.root.xform, copy.deepcopy(scene.plugin_data),
                       list(scene.layers), dict(scene.materials), set(scene.selection),
                       [(g,g.mesh,g.ext,g.ifc,g.layer) for g,_new in self.updates])
        try:
            for group,new in self.updates:
                group.mesh,group.ext,group.ifc,group.layer = new.mesh,new.ext,new.ifc,new.layer
            self.root.adopt(self.children)
            self.root.ext = self.ext
            if self.root not in scene.groups:
                scene.groups.append(self.root)
            names = {x.name for x in scene.layers}
            scene.layers.extend(x for x in self.incoming.layers if x.name not in names)
            for name, mat in self.incoming.materials.items():
                if name in scene.materials and scene.materials[name] != mat:
                    raise ValueError('Conflicto de material: ' + name)
                scene.materials[name] = mat
            scene.plugin_data['arquitectura'] = copy.deepcopy(self.value)
            scene.selection.clear()
            scene.version += 1
        except Exception:
            self.undo(scene)
            raise

    def undo(self, scene):
        groups, kids, ext, pose, pdata, layers, mats, selection, states = self.before
        for g,mesh,gext,ifc,layer in states:
            g.mesh,g.ext,g.ifc,g.layer=mesh,gext,ifc,layer
        scene.groups[:] = groups
        self.root.children = kids
        self.root.ext, self.root.xform = ext, pose
        scene.plugin_data = copy.deepcopy(pdata)
        scene.layers[:] = layers
        scene.materials = dict(mats)
        scene.selection = set(selection)
        scene.version += 1

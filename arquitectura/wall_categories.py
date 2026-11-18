# SPDX-License-Identifier: GPL-3.0-or-later
"""Categorías de muro: un único vocabulario para órdenes, tipos, conversión y
exportación.

Cada categoría tiene su capa. La categoría decide además cómo se exporta el
muro (exchange.build): fachada, medianera y sótano son exteriores; el tabique
es PARTITIONING; la defensa (v1.29) es una barandilla o un antepecho, con
sus datos propios en defensas.py.
"""
CATEGORIES = (('Fachada (exterior)', 'fachada'), ('Tabique', 'tabique'),
              ('Medianera', 'medianera'), ('Muro de sótano', 'sotano'),
              ('Defensa (barandilla o antepecho)', 'defensa'))
LAYERS = {'fachada':'ARQ-MUROS', 'tabique':'ARQ-TABIQUES',
          'medianera':'ARQ-MEDIANERAS', 'sotano':'ARQ-SOTANO',
          'defensa':'ARQ-DEFENSAS'}
ROLES = {'muros':'fachada', 'tabiques':'tabique', 'medianeras':'medianera'}


def category(record, external=None):
    value = record.get('wall_category')
    if value is not None:
        if value not in LAYERS: raise ValueError('Categoría de muro no válida')
        return value
    if record.get('wall_role') in ROLES: return ROLES[record['wall_role']]
    return 'tabique' if external is False else 'fachada'


def migrate_steps(document):
    from .architectural import metadata
    from .architectural_v10 import edit_wall
    from .exchange import read_model
    from .geom.bands import solve_records
    from .geom.spaces import external_walls
    records, columns, _, _ = read_model(document.doc, strict=False)
    result = solve_records(records, columns)
    external = set().union(*(external_walls(part) for _, part in result.vertical_networks))
    changes = []
    for e in document.doc.modelspace():
        m = metadata(e) or {}
        if m.get('kind') != 'wall' or m.get('wall_category'): continue
        old_layer = e.dxf.layer.split('@')[0]
        value = next((k for k,v in LAYERS.items() if v==old_layer), None)
        value = value or category(m, m['id'] in external)
        changes.append(edit_wall(e, wall_category=value))
    return changes

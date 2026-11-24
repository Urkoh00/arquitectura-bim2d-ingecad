# SPDX-License-Identifier: GPL-3.0-or-later
"""Categorías de muro: un único vocabulario para órdenes, tipos, conversión y
exportación.

Cada categoría tiene su capa. La categoría decide además cómo se exporta el
muro (exchange.build): fachada, medianera y sótano son exteriores
(IsExternal); su tipo IFC lo da ``ifc_type``; la defensa (v1.29) es una
barandilla o un antepecho, con sus datos propios en defensas.py.
"""
CATEGORIES = (('Fachada (exterior)', 'fachada'), ('Partición', 'particion'),
              ('Medianera', 'medianera'), ('Muro de sótano', 'sotano'),
              ('Defensa (barandilla o antepecho)', 'defensa'))
LAYERS = {'fachada':'ARQ-MUROS', 'particion':'ARQ-PARTICIONES',
          'medianera':'ARQ-MEDIANERAS', 'sotano':'ARQ-SOTANO',
          'defensa':'ARQ-DEFENSAS'}
ROLES = {'muros':'fachada', 'particiones':'particion', 'tabiques':'particion',
         'medianeras':'medianera'}
# v1.48.1: «Tabique» pasa a llamarse «Partición», como en el catálogo de
# elementos constructivos. Los dibujos anteriores guardan «tabique» y tienen
# la capa ARQ-TABIQUES: se leen igual y conservan su capa hasta ARQMIGRAR.
ALIASES = {'tabique': 'particion'}
LEGACY_LAYERS = {'particion': 'ARQ-TABIQUES'}

# Tipo IFC de cada categoría: (PredefinedType, ObjectType o None).
# Son los valores que escribe un modelador IFC de referencia (v1.33, prueba
# del propietario) y los que piden los generadores de modelo analítico para
# el cálculo energético: la medianera y el muro de sótano no tienen valor
# propio en IfcWallTypeEnum y van como USERDEFINED con su ObjectType.
IFC_TYPES = {'fachada':('USERDEFINED', 'EXTERNALWALL'),
             'particion':('PARTITIONING', None),
             'medianera':('USERDEFINED', 'PARTYWALL'),
             'sotano':('USERDEFINED', 'BASEMENTWALL')}


def category(record, external=None):
    value = record.get('wall_category')
    if value is not None:
        value = ALIASES.get(value, value)
        if value not in LAYERS: raise ValueError('Categoría de muro no válida')
        return value
    if record.get('wall_role') in ROLES: return ROLES[record['wall_role']]
    return 'particion' if external is False else 'fachada'


def layer_name(cat, layers=None):
    """Capa de la categoría ``cat``. Si se da la tabla de capas del dibujo y
    solo existe la capa anterior (ARQ-TABIQUES), se usa esa: un dibujo sin
    migrar no reparte sus particiones entre dos capas."""
    cat = ALIASES.get(cat, cat)
    name = LAYERS[cat]
    old = LEGACY_LAYERS.get(cat)
    if layers is not None and old and name not in layers and old in layers:
        return old
    return name


def category_of_layer(layer):
    """Categoría de una capa ARQ (con o sin sufijo de nivel), o None."""
    base = str(layer).split('@')[0]
    for cat, name in LAYERS.items():
        if base == name or base == LEGACY_LAYERS.get(cat):
            return cat
    return None


def ifc_type(cat):
    """(PredefinedType, ObjectType o None) del muro de categoría ``cat``."""
    return IFC_TYPES.get(ALIASES.get(cat, cat), ('STANDARD', None))


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
        value = category_of_layer(e.dxf.layer)
        value = value or category(m, m['id'] in external)
        changes.append(edit_wall(e, wall_category=value))
    return changes

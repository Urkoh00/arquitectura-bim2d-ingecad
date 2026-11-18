# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: Altura de un muro de nivel a nivel (restricción superior); todos reciben el mismo registro
#   resuelto.
#   (Guía del código: docs/GUIA_DEL_CODIGO.md)
"""Wall vertical constraints; every consumer receives the same resolved record."""
import math

KEYS = ('height_constraint','top_level_id','top_offset','base_offset','level_id')


def resolve(record, catalog):
    mode=record.get('height_constraint','fixed')
    if mode=='fixed': return dict(record)
    if mode!='level': raise ValueError('Restricción de altura del muro no válida')
    levels={lv['id']:lv for lv in catalog['levels']}
    low=levels.get(record.get('level_id'));high=levels.get(record.get('top_level_id'))
    if low is None or high is None:raise ValueError('El muro referencia un nivel base o superior inexistente')
    bottom=float(record.get('base_offset',0));top=float(record.get('top_offset',0))
    if not all(math.isfinite(v)for v in (bottom,top)):raise ValueError('Desfases de muro no finitos')
    base=low['elevation']+bottom;height=high['elevation']+top-base
    if height<=1e-8 or not math.isfinite(height):raise ValueError('La restricción superior no deja una altura positiva')
    return {**record,'base':base,'height':height,'level':low['name'],'level_offset':bottom}


def openings_by_wall(drawing):
    """{wall_id: [opening records]} in one pass over the drawing: a loop
    over every wall must not scan the whole drawing once per wall."""
    from .architectural import metadata
    out={}
    for e in drawing.modelspace():
        m=metadata(e)or{}
        if m.get('kind')=='opening':out.setdefault(m.get('wall_id'),[]).append(m)
    return out


def validate_openings(drawing, record, index=None):
    from .architectural import validate_wall
    if index is None:index=openings_by_wall(drawing)
    holes=index.get(record['id'],[])
    validate_wall({**record,'openings':sorted(holes,key=lambda o:o['offset'])})

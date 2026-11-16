# SPDX-License-Identifier: GPL-3.0-or-later
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


def validate_openings(drawing, record):
    from .architectural import metadata,validate_wall
    holes=[m for e in drawing.modelspace() if (m:=metadata(e)or{}).get('kind')=='opening' and m.get('wall_id')==record['id']]
    validate_wall({**record,'openings':sorted(holes,key=lambda o:o['offset'])})

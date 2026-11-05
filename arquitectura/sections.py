# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure, shared plan profiles for the DXF column and IngeTrazo export."""
from __future__ import annotations
import math

SHAPES = {'rect', 'circ', 'hex', 'oct'}

def column_points(center, values):
    x,y = float(center[0]),float(center[1])
    shape = values.get('shape','rect')
    if shape == 'rect':
        w,d = float(values['width']),float(values['depth'])
        if not all(map(math.isfinite,(x,y,w,d))) or min(w,d)<=0:
            raise ValueError('Sección rectangular inválida')
        return [(x-w/2,y-d/2),(x+w/2,y-d/2),(x+w/2,y+d/2),(x-w/2,y+d/2)]
    if shape not in ('circ','hex','oct'):
        raise ValueError('Forma de pilar desconocida: '+str(shape))
    r = float(values['radius'])
    angle = math.radians(float(values.get('rotation',0)))
    if not all(map(math.isfinite,(x,y,r,angle))) or r<=0:
        raise ValueError('Radio u orientación de pilar inválidos')
    n = {'circ':48,'hex':6,'oct':8}[shape]
    return [(x+r*math.cos(angle+2*math.pi*i/n),
             y+r*math.sin(angle+2*math.pi*i/n)) for i in range(n)]

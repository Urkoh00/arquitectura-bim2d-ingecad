# SPDX-License-Identifier: GPL-3.0-or-later
"""Standalone converter: run with IngeTrazo's Python interpreter.

Usage: cd /path/to/ingetrazo && python /path/to/igz_bridge.py spec.json file.igz
Only IngeTrazo's ORIGINAL Scene/Group/Mesh/save_scene are used.
"""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path

# Separate interpreter and repository root prevent IngeCAD/IngeTrazo core collision.
sys.path.insert(0, str(Path.cwd().resolve()))

def build_scene(data):
    from PySide6.QtGui import QVector3D as V
    from core.scene import Scene
    from core.mesh import Mesh
    from core.group import Group
    from core.layers import Layer
    from architectural import partition_solids

    if data.get('schema') != 1 or data.get('units') != 'm':
        raise ValueError('Especificación arquitectónica incompatible')
    scene=Scene()
    scene.layers.append(Layer('ARQ-MUROS3D',color=(0.7,0.7,0.7)))
    scene.layers.append(Layer('ARQ-PILARES',color=(0.55,0.65,0.7)))
    for wall in data['walls']:
        mesh=Mesh()
        ax,ay=wall['a'];bx,by=wall['b'];length=math.dist((ax,ay),(bx,by))
        ux,uy=(bx-ax)/length,(by-ay)/length
        nx,ny=-uy,ux
        def P(s,t,z):return V(ax+ux*s+nx*t,ay+uy*s+ny*t,wall['base']+z)
        ref=wall.get('reference','eje')
        if ref == 'izquierda': left,right=0.,wall['thickness']
        elif ref == 'derecha': left,right=-wall['thickness'],0.
        else: left,right=-wall['thickness']/2,wall['thickness']/2
        for s0,s1,z0,z1 in partition_solids(wall):
            v=[P(s0,left,z0),P(s1,left,z0),P(s1,right,z0),P(s0,right,z0),
               P(s0,left,z1),P(s1,left,z1),P(s1,right,z1),P(s0,right,z1)]
            for ids in [(3,2,1,0),(4,5,6,7),(0,1,5,4),
                        (2,3,7,6),(3,0,4,7),(1,2,6,5)]:
                mesh.add_face([v[i] for i in ids])
        if not list(partition_solids(wall)):
            raise ValueError('Muro sin geometría: '+wall['id'])
        g=Group(mesh,name=wall.get('name') or 'Muro '+wall['id'][:8])
        g.layer='ARQ-MUROS3D'
        g.ifc={'class':'IfcWall','name':g.name}
        # IGZ extension metadata is preserved, but the current IFC writer does
        # NOT automatically export these fields as IFC property sets.
        g.ext={'arquitectura':{
            'schema':2,'source_id':wall['id'],'class':'IfcWall',
            'type_name':wall.get('type_name',''),'material':wall.get('material',''),
            'level':wall.get('level',''),'thickness':wall['thickness'],
            'height':wall['height'],'base':wall['base'],
            'reference':wall.get('reference','eje'),
            'openings':wall.get('openings',[])}}
        scene.groups.append(g)
    # Column geometry and metadata: independent IFC-tagged groups.
    # Same coordinate system as the walls, with base/height preserved.
    for column in data.get('columns',[]):
        x,y=column['center'];base=float(column.get('base',0.0))
        height=float(column['height'])
        if height<=0:raise ValueError('Altura de pilar no positiva')
        from sections import column_points
        poly = column_points((x,y), column)
        mesh=Mesh()
        v0=[V(px,py,base) for px,py in poly]
        v1=[V(px,py,base+height) for px,py in poly]
        mesh.add_face(list(reversed(v0)))
        mesh.add_face(v1)
        for i in range(len(poly)):
            j=(i+1)%len(poly)
            mesh.add_face([v0[i],v0[j],v1[j],v1[i]])
        group=Group(mesh,name=column.get('name') or 'Pilar '+column['id'][:8])
        group.layer='ARQ-PILARES'
        group.ifc={'class':'IfcColumn','name':group.name}
        group.ext={'arquitectura':{'schema':2,'source_id':column['id'],
              'class':'IfcColumn',**{k:column.get(k) for k in
              ('shape','width','depth','radius','rotation','height','base','type_name','material','level')}}}
        scene.groups.append(group)
    if len(scene.groups) != len(data['walls']) + len(data.get('columns',[])):
        raise RuntimeError('IGZ: número de objetos BIM incorrecto')
    return scene


def main(argv=None):
    args=list(sys.argv[1:] if argv is None else argv)
    if len(args)!=2:raise SystemExit('Uso: igz_bridge.py especificacion.json salida.igz')
    spec=Path(args[0]).resolve(); dest=Path(args[1]).resolve()
    with spec.open(encoding='utf-8') as f:data=json.load(f)
    scene=build_scene(data)
    from formats.igz import save_scene, load_into
    save_scene(scene,dest)
    # Validate with the REAL official reader, not only with json.loads. This
    # catches schema and mesh incompatibilities before IngeCAD publishes IGZ.
    loaded = type(scene)()
    load_into(loaded, dest)
    want = {g.ext['arquitectura']['source_id']:g.ifc['class'] for g in scene.groups}
    got = {}
    for g in loaded.groups:
        info = (g.ext or {}).get('arquitectura') or {}
        uid = info.get('source_id')
        if uid in got:
            raise RuntimeError('IGZ duplicó un identificador BIM al reabrirse')
        got[uid] = (g.ifc or {}).get('class')
        if not g.mesh.faces:
            raise RuntimeError('IGZ: geometría ausente al reabrir '+str(uid))
    if got != want:
        raise RuntimeError('IGZ no conserva objetos IFC y sus identificadores BIM')
    print(f'IGZ creado y releído con IngeTrazo: {dest} | muros: {len(data["walls"])} | pilares: {len(data.get("columns", []))}')

if __name__=='__main__':main()

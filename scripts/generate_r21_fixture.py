# SPDX-License-Identifier: GPL-3.0-or-later
import json,sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core.document import Document
from core.commands import History
from arquitectura import architectural_v10 as A,transactions as T,exchange as E,cabinets as C
D=Document.new();H=History(D);ctx=SimpleNamespace(document=D,execute=H.execute)
walls=[]
for a,b in [((0,0),(6,0)),((6,0),(6,5)),((6,5),(0,5)),((0,5),(0,0))]:
 c=A.create_wall(a,b,.3,3);T.apply_architectural_change(ctx,c);walls.append(c.entity)
o=A.create_opening(walls[0],1,1.2,.9,1.1,kind='window',type_name='VENTANA ABATIBLE',operation='SIDEHUNG');T.apply_architectural_change(ctx,o,kind='opening')
c=C.create(walls[1],1,1.2,.6,2.1,mode='adosado');T.apply_architectural_change(ctx,c,kind='opening')
from arquitectura.wall_tools import RecintoTool
from tools.base import ToolContext
class Services:
 window=SimpleNamespace(document=D)
t=RecintoTool(ToolContext(execute=H.execute,prompt=lambda *_:None,echo=lambda *_:None,finish=lambda:None,services=Services()));t.start();t.on_point((3,2.5))
out=Path(sys.argv[1]);out.mkdir(exist_ok=True,parents=True);D.save_as(out/'origin.dxf');E.write(D.doc,out/'origin.arqbim')
print(json.dumps({'elements':len(E.build(D.doc)['elements'])}))

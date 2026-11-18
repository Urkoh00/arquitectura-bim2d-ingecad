# SPDX-License-Identifier: GPL-3.0-or-later
"""Accept a real IngeTrazo .arqcambios, undo/redo, and export again."""
import json,sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core.document import Document
from core.commands import History
from arquitectura import exchange as E,roundtrip as R
source=Path(sys.argv[1]);changes=Path(sys.argv[2]);out=Path(sys.argv[3]);out.mkdir(exist_ok=True,parents=True)
d=Document.load(source);h=History(d);ctx=SimpleNamespace(document=d,execute=h.execute);before=E.build(d.doc)
data=json.loads(changes.read_text());assert not R.conflicts(d.doc,data)
R.accept(ctx,data);assert len(h._undo)==1;after=E.build(d.doc);h.undo();assert E.build(d.doc)==before;h.redo();assert E.build(d.doc)==after
E.write(d.doc,out/'confirmed.arqbim');d.save_as(out/'confirmed.dxf')
print(json.dumps({'single_undo_redo':True,'changes':len(data['changes']),'rooms_before':{e['id']:e['volume']for e in before['elements']if e['ifc_class']=='IfcSpace'},'rooms_after':{e['id']:e['volume']for e in after['elements']if e['ifc_class']=='IfcSpace'}},indent=2))

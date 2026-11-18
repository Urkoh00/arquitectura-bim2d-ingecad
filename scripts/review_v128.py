# SPDX-License-Identifier: GPL-3.0-or-later
"""Independent probes on the unchanged uploaded v1.28; synthetic only."""
import json,sys
from pathlib import Path
from types import SimpleNamespace
from PySide6.QtWidgets import QApplication
from core.document import Document
from core.commands import History
from arquitectura import architectural_v10 as A,architectural as AR,exchange as E,bim_dialogs as BD,integrity as IG
from ingetrazo_ext import arquitectura_bim as X
app=QApplication.instance()or QApplication([])
d=Document.new();h=History(d)
for name in ['ARQ-MUROS','ARQ-MUROS3D','ARQ-HUECOS3D']:d.doc.layers.add(name)
w=A.create_wall((0,0),(6,0),.3,3);h.execute(w)
o=A.create_opening(w.entity,1,1.2,.9,1.1,kind='window',frame_width=-.05);h.execute(o)
r=AR.metadata(o.entity);dlg,read=BD.carpentry_form(SimpleNamespace(),r);values=read();problems=dlg._arq['problems'](values)
contract=E.build(d.doc);X.validate_contract(contract)
result={'negative_frame_width':{'stored':r['frame_width'],'dialog':values['frame_width'],'dialog_problems':problems,'audit':IG.audit(d.doc),'contract_accepts':True},'version':'1.28.0-dev'}
Path(sys.argv[1]).write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2))

# SPDX-License-Identifier: GPL-3.0-or-later
"""Complete confirmed source -> idempotent IngeTrazo -> official IFC."""
import json,sys,copy
from pathlib import Path
from types import SimpleNamespace
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'ingetrazo_ext'))
import arquitectura_bim as X,_arqbim_sync as SY,_arq_edit as ED
from core.scene import Scene
from core.history import History
from formats.igz import load_into,save_scene
from formats.ifc import save_ifc
import ifcopenshell,ifcopenshell.validate
pending=Path(sys.argv[1]);confirmed=Path(sys.argv[2]);out=Path(sys.argv[3]);out.mkdir(parents=True,exist_ok=True)
scene=Scene();load_into(scene,pending);rootgroup=scene.groups[0]
old={g.ext['arquitectura']['source_id']:g for g in rootgroup.children}
data=X.read_contract(confirmed);incoming=X.build_scene(data)
cmd=SY.prepare(scene,incoming,data,'synthetic.arqbim',X.definition(data));assert cmd is not None
h=History(scene);h.execute(cmd);assert not h.last_error
assert all(g is old[g.ext['arquitectura']['source_id']]for g in rootgroup.children)
assert not scene.plugin_data['arquitectura']['models']['synthetic.arqbim']['editing']['pending']
assert SY.prepare(scene,X.build_scene(data),data,'synthetic.arqbim',X.definition(data))is None
assert not ED.shared().changes(data['roundtrip'],data['roundtrip'])['changes']
# Compare each updated owned mesh and record with a fresh import of source.
expected={g.ext['arquitectura']['source_id']:g for g in incoming.groups}
for g in rootgroup.children:
 ident=g.ext['arquitectura']['source_id'];assert g.ext['arquitectura']==expected[ident].ext['arquitectura']
 assert abs(X._volume64(g)-X._volume64(expected[ident]))<1e-8
save_scene(scene,out/'confirmed.igz');n=save_ifc(scene,out/'confirmed.ifc',project_name='R21 sintético')
f=ifcopenshell.open(str(out/'confirmed.ifc'));logger=ifcopenshell.validate.json_logger();ifcopenshell.validate.validate(f,logger,express_rules=True)
result={'elements':len(data['elements']),'ifc_written':n,'same_group_objects':True,'second_import_noop':True,'pending_cleared':True,'ifc_counts':{c:len(f.by_type(c))for c in ['IfcWall','IfcWindow','IfcDoor','IfcSpace','IfcBuildingElementProxy','IfcBuildingStorey','IfcRelDefinesByType','IfcPropertySet']},'express_errors':len(logger.statements),'express_rules':[s.get('attribute') for s in logger.statements]}
(out/'report.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))

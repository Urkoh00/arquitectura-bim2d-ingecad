# SPDX-License-Identifier: GPL-3.0-or-later
import math
import pytest
from arquitectura import openings as O
from arquitectura.geom.junctions import Wall
from tests.test_ingecad_integration import plugin
from tests.test_wall_tools import Session,draw


@pytest.mark.parametrize('kind',['door','window'])
@pytest.mark.parametrize('face',['interior','centrada','exterior','distancia'])
@pytest.mark.parametrize('side',[1,-1])
def test_four_positions_share_the_same_band(kind,face,side):
    spec=Wall('wall',(0,0),(6,0),.3,'eje')
    rec=O.normalise({'type':kind,'offset':1.,'width':.9,'sill':0.,'height':2.,'face':face,'side':side,
                     'frame_depth':.05,'setback':.05,'setback_from':'exterior','angle':0.,'sill_kind':'ventanal'})
    lo,hi=O.frame_band(spec,rec);assert hi-lo==pytest.approx(.05)
    if face=='distancia':assert (lo,hi)==pytest.approx((-.10,-.05) if side==1 else (.05,.10))
    parts=O.carpentry_parts(spec,rec,0);frame=next(p for p in parts if p['role']=='frame')
    assert frame['prism'][2:]==pytest.approx((lo,hi))
    symbol=O.plan_symbol(spec,rec);assert symbol


@pytest.mark.parametrize('side',[1,-1])
def test_curved_positions_use_effective_chord_band(side):
    spec=Wall('curved',(0,0),(6,0),.4,'eje',bulge=math.tan(math.pi/16))
    for face in O.FACES:
        rec=O.normalise({'type':'window','offset':1.,'width':.8,'sill':.8,'height':1.2,'side':side,
                        'face':face,'setback':.02,'setback_from':'exterior','frame_depth':.04})
        pw,rr=O.proxy(spec,rec);lo,hi=O.frame_band(pw,rr)
        assert lo>=pw.lo-1e-9 and hi<=pw.hi+1e-9 and O.carpentry_parts(spec,rec,0)


def test_legacy_migration_keeps_geometry():
    from arquitectura.migration import migrate_opening_position
    spec=Wall('wall',(0,0),(5,0),.3,'eje');old={'type':'door','offset':1.,'width':.9,'sill':0.,'height':2.1,'face':'exterior','side':-1}
    before=O.frame_band(spec,O.normalise(old));new=migrate_opening_position(old)
    assert O.frame_band(spec,new)==before and new['face']==old['face'] and 'setback' not in old


@pytest.mark.parametrize('change',[{'setback':.29},{'setback':-.01},{'setback':float('nan')},{'frame_depth':.4}])
def test_impossible_recess_rejected(change):
    spec=Wall('wall',(0,0),(5,0),.3,'eje');rec=O.normalise({'type':'window','width':1.,'height':1.,'sill':.8,'face':'distancia','frame_depth':.05,**change})
    with pytest.raises(ValueError):O.frame_band(spec,rec)


def test_record_export_and_undo_preserve_identity(plugin,tmp_path):
    s=Session(plugin);t=s.tool('MURO');t.thickness=.3;draw(t,(0,0),(5,0));c=s.tool('CARPINTERIA')
    c.v.update(face='distancia',setback=.05,setback_from='exterior',frame_depth=.05)
    c.on_point((1,.15));c.on_point((2,1));ops=[e for e in s.document.doc.modelspace() if (s.meta(e)or{}).get('kind')=='opening'];assert len(ops)==1
    identity=s.meta(ops[0])['id'];data=s.export(tmp_path);el=next(e for e in data['elements'] if e['ifc_class']=='IfcDoor')
    assert el['params']['setback']==.05 and el['psets']['ARQ_IngeCAD']['FrameReferenceIsGeographic'] is False
    import importlib
    A=importlib.import_module(c.__module__.rsplit('.',1)[0]+'.architectural_v10');T=importlib.import_module(c.__module__.rsplit('.',1)[0]+'.transactions')
    T.apply_architectural_change(c.ctx,A.edit_opening(ops[0],setback=.08),kind='opening');assert s.meta(ops[0])['id']==identity
    s.history.undo();assert s.meta(ops[0])['setback']==.05;s.history.redo();assert s.meta(ops[0])['setback']==.08

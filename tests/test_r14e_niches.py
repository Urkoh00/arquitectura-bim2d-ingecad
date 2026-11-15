# SPDX-License-Identifier: GPL-3.0-or-later
import math
import pytest
from tests.test_ingecad_integration import plugin
from tests.test_wall_tools import Session
from tests.test_r12_conversion import module


@pytest.mark.parametrize('angle',[0,37,90])
@pytest.mark.parametrize('side',[-1,1])
@pytest.mark.parametrize('leaves',[1,2,3,4])
@pytest.mark.parametrize('operation',['SWINGING','SLIDING'])
def test_niche_residual_plan_solid_exchange_and_undo(plugin,angle,side,leaves,operation,tmp_path):
    s=Session(plugin);A=module(s,'architectural_v10');C=module(s,'cabinets');T=module(s,'transactions')
    angle=math.radians(angle);end=(4*math.cos(angle),4*math.sin(angle))
    cmd=A.create_wall((0,0),end,.5,3);T.apply_architectural_change(s.tool('MURO').ctx,cmd)
    wall=cmd.entity
    change=C.create(wall,1,1.2,.3,2.1,leaves,operation,side)
    T.apply_architectural_change(s.tool('MURO').ctx,change,kind='opening')
    records=[s.meta(e)for e in s.document.doc.modelspace()if(s.meta(e)or{}).get('kind')=='opening']
    assert len(records)==1 and records[0]['leaves']==leaves;rec=records[0];ident=rec['id']
    J=module(s,'geom.junctions');O=module(s,'openings');S=module(s,'geom.solids')
    spec=J.walls_from_records([(s.meta(wall)['id'],s.meta(wall))])[0]
    from shapely.geometry import Polygon
    cut=Polygon(O.cut_polygon(spec,rec,0));assert cut.area==pytest.approx(1.2*.3)
    # Residual .20 m at every point along the niche, not just its bounds.
    lo,hi=O.cut_band(spec,rec);assert hi-lo==pytest.approx(.3)
    assert Polygon(spec.strip()).difference(cut).area==pytest.approx(4*.5-1.2*.3)
    data=s.export(tmp_path);w=next(e for e in data['elements']if e['ifc_class']=='IfcWall')
    assert w['volume']==pytest.approx(4*.5*3-1.2*.3*2.1,abs=1e-7)
    faces=[([tuple(v)for v in f['outer']],[[tuple(v)for v in h]for h in f['holes']])for f in w['faces']]
    assert abs(S.face_volume(faces))==pytest.approx(w['volume'],abs=1e-7)
    door=next(e for e in data['elements']if e['ifc_class']=='IfcDoor')
    assert door['enums']['PredefinedType']=='USERDEFINED'and door['attributes']['ObjectType']=='ARMARIO'
    assert door['params']['niche_depth']==pytest.approx(.3)and len([p for p in door['parts']if p['role']=='leaf'])==leaves
    assert w['openings'][0]['params']['niche_depth']==pytest.approx(.3)
    assert len([g for g in O.plan_symbol(spec,rec)if g[0]=='arc'])==(leaves if operation=='SWINGING'else 0)
    s.history.undo();assert not any((s.meta(e)or{}).get('kind')=='opening'for e in s.document.doc.modelspace())
    assert s.export(tmp_path)['elements'][0]['volume']==pytest.approx(6)
    s.history.redo();assert next(s.meta(e)for e in s.document.doc.modelspace()if(s.meta(e)or{}).get('kind')=='opening')['id']==ident


@pytest.mark.parametrize('depth',[0,-.1,.5,.495,float('nan'),float('inf')])
def test_invalid_niche_rejected_before_history_changes(plugin,depth):
    s=Session(plugin);A=module(s,'architectural_v10');C=module(s,'cabinets');P=module(s,'conversion_plan')
    cmd=A.create_wall((0,0),(4,0),.5,3);s.history.execute(cmd);before=P.fingerprint(s.document.doc)
    with pytest.raises(ValueError):C.create(cmd.entity,1,1.2,depth,2.1)
    assert P.fingerprint(s.document.doc)==before


def test_niche_save_reopen_edit_and_corrupt_record_warning(plugin,tmp_path):
    from core.document import Document
    s=Session(plugin);A=module(s,'architectural_v10');C=module(s,'cabinets');T=module(s,'transactions')
    wall=A.create_wall((0,0),(4,0),.5,3);T.apply_architectural_change(s.tool('MURO').ctx,wall)
    niche=C.create(wall.entity,1,1.2,.3,2.1,4);T.apply_architectural_change(s.tool('MURO').ctx,niche,kind='opening')
    ident=s.meta(niche.entity)['id'];path=tmp_path/'sintetico.dxf';s.document.doc.saveas(path)
    reopened=Document.load(path);E=module(s,'exchange');out=E.build(reopened.doc)
    rec=next(e for e in out['elements']if e['ifc_class']=='IfcDoor')
    assert rec['id']==ident and rec['params']['niche_depth']==pytest.approx(.3)and rec['params']['leaves']==4
    assert 'ItinerarioAccesibleSUA'not in rec['psets']['ARQ_IngeCAD']
    change=A.edit_opening(niche.entity,niche_depth=.2,leaves=3)
    T.apply_architectural_change(s.tool('MURO').ctx,change,kind='opening')
    assert s.meta(niche.entity)['id']==ident and s.meta(niche.entity)['niche_depth']==pytest.approx(.2)
    assert next(e for e in s.export(tmp_path)['elements']if e['ifc_class']=='IfcWall')['volume']==pytest.approx(6-1.2*.2*2.1)
    s.history.undo();assert s.meta(niche.entity)['niche_depth']==pytest.approx(.3)
    # Invalid saved depth is surfaced by the same integrity checker as holes.
    arch=module(s,'architectural');rec=s.meta(niche.entity);rec['niche_depth']=.6;arch._xdata(s.document.doc.modelspace(),niche.entity,rec)
    issues=module(s,'integrity').audit(s.document.doc)
    assert any(i['code']=='hueco'and'nicho'in i['text']for i in issues)


def test_userdefined_cabinet_attributes_match_ifc4_schema():
    ifcopenshell=pytest.importorskip('ifcopenshell')
    import ifcopenshell.validate
    model=ifcopenshell.file(schema='IFC4')
    model.create_entity('IfcDoor',GlobalId=ifcopenshell.guid.new(),Name='Armario sintetico',
        PredefinedType='USERDEFINED',ObjectType='ARMARIO',OperationType='USERDEFINED',
        UserDefinedOperationType='4_HOJAS_SLIDING')
    logger=ifcopenshell.validate.json_logger();ifcopenshell.validate.validate(model,logger,express_rules=True)
    assert not logger.statements


def test_host_thickness_edit_cannot_silently_turn_a_niche_into_through_cut(plugin):
    s=Session(plugin);A=module(s,'architectural_v10');C=module(s,'cabinets');T=module(s,'transactions');P=module(s,'conversion_plan')
    wall=A.create_wall((0,0),(4,0),.5,3);T.apply_architectural_change(s.tool('MURO').ctx,wall)
    T.apply_architectural_change(s.tool('MURO').ctx,C.create(wall.entity,1,1.2,.3,2.1),kind='opening')
    before=P.fingerprint(s.document.doc)
    with pytest.raises(ValueError):T.apply_architectural_change(s.tool('MURO').ctx,A.edit_wall(wall.entity,thickness=.25))
    assert P.fingerprint(s.document.doc)==before

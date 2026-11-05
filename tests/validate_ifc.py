"""Independent IFC check with IfcOpenShell (not used by IngeCAD/IngeTrazo)."""
import sys, json
import ifcopenshell, ifcopenshell.validate, ifcopenshell.util.element as U
import ifcopenshell.geom, ifcopenshell.util.shape as SH

def report(path, contract=None):
    f = ifcopenshell.open(path)
    log = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate(f, log)
    errs = [m for m in log.statements if m.get('level', 'error') in ('error',)]
    out = {'archivo': path.split('/')[-1], 'errores_esquema': len(log.statements)}
    for cls in ('IfcWall', 'IfcColumn', 'IfcOpeningElement', 'IfcBuildingStorey', 'IfcMaterial',
                'IfcRelVoidsElement', 'IfcPropertySet', 'IfcWallType'):
        out[cls] = len(f.by_type(cls))
    walls = f.by_type('IfcWall') + f.by_type('IfcColumn')
    out['con_planta'] = sum(1 for w in walls if U.get_container(w) is not None)
    out['con_material'] = sum(1 for w in walls if U.get_material(w) is not None)
    out['con_Pset_comun'] = sum(1 for w in walls if any(k.startswith('Pset_') for k in U.get_psets(w)))
    s = ifcopenshell.geom.settings()
    vols = {}
    for w in walls:
        sh = ifcopenshell.geom.create_shape(s, w)
        vols[w.GlobalId] = SH.get_volume(sh.geometry)
    if contract:
        c = json.load(open(contract))
        want = {e['guid']: e['volume'] for e in c['elements']}
        out['guid_conservados'] = sum(1 for g in vols if g in want)
        out['max_err_volumen_m3'] = max((abs(vols[g] - want[g]) for g in vols if g in want), default=None)
    out['volumen_total_ifc_m3'] = round(sum(vols.values()), 6)
    if log.statements:
        out['primer_error'] = str(log.statements[0])[:300]
    return out

if __name__ == '__main__':
    print(json.dumps(report(*sys.argv[1:]), ensure_ascii=False, indent=1))

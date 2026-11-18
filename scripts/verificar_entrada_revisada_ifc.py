# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: verifica el modelo sintético de entrada revisada en IGZ e IFC
# con las clases y el exportador oficiales de IngeTrazo 0.6.2.1.
"""No aplica correcciones al motor anfitrión ni presupone conformidad general."""
import json
import math
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "ingetrazo_ext"))
import arquitectura_bim as extension
from core.scene import Scene
from formats.igz import load_into, save_scene
from formats.ifc import save_ifc
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.shape
import ifcopenshell.validate


def verificar(destino):
    datos = extension.read_contract(destino / "resultado.arqbim")
    escena = extension.build_scene(datos)
    extension.check_scene(escena, datos)
    save_scene(escena, destino / "resultado.igz")
    recuperada = Scene()
    load_into(recuperada, destino / "resultado.igz")
    assert recuperada.plugin_data == escena.plugin_data
    extension.check_scene(recuperada, datos)
    cantidad = save_ifc(recuperada, destino / "resultado.ifc", project_name="Entrada revisada sintética")
    modelo = ifcopenshell.open(str(destino / "resultado.ifc"))
    muros = modelo.by_type("IfcWall")
    assert cantidad == 1 and len(muros) == 1
    forma = ifcopenshell.geom.create_shape(ifcopenshell.geom.settings(), muros[0])
    volumen = ifcopenshell.util.shape.get_volume(forma.geometry)
    esperado = 6. * .2 * 2.7
    assert math.isclose(volumen, esperado, abs_tol=1e-7)
    registro = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate(modelo, registro, express_rules=True)
    assert not registro.statements
    informe = {
        "ingetrazo": "0.6.2.1",
        "elementos_ifc": cantidad,
        "volumen_analitico_m3": esperado,
        "volumen_ifc_m3": volumen,
        "errores_express_este_caso": len(registro.statements),
        "propiedades_ifc": len(modelo.by_type("IfcPropertySet")),
        "tipos_ifc": len(modelo.by_type("IfcRelDefinesByType")),
        "limite": "Un solo muro; este resultado no acredita conformidad IFC general ni soluciona pérdidas semánticas del exportador oficial.",
    }
    (destino / "informe_ingetrazo_ifc.json").write_text(json.dumps(informe, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(informe, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    verificar(Path(sys.argv[1]).resolve())

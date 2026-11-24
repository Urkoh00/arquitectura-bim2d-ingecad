# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: CATALOGOEC importa los IFC del catálogo de elementos constructivos a
#   una biblioteca del usuario, corrige sus defectos, la contrasta con la
#   biblioteca térmica del Ministerio (que prevalece) y crea tipos de muro.
"""Catálogo de elementos constructivos del usuario (v1.48.1).

El catálogo real no se distribuye: estas pruebas usan IFC sintéticos con los
mismos defectos que los ficheros exportados por su aplicación. Si se define
``ARQ_CEC_PRUEBA`` con una carpeta de IFC reales, se prueba también su lectura.
"""
import io
import json
import os
import zipfile
from importlib import import_module
from pathlib import Path

import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401  (fixture)
from tests.test_recintos import _cmd_ctx
from tests.test_wall_tools import Session

CABECERA = """ISO-10303-21;
HEADER;
FILE_DESCRIPTION (('ViewDefinition [CoordinationView_V2.0]'), '2;1');
FILE_NAME ('', '2026-11-22T15:36:35' , (''), (''), 'Catalogo de prueba v.04.00', 'Catalogo de prueba v.04.00', '');
FILE_SCHEMA (('IFC4'));
ENDSEC;
DATA;
#2=IFCOWNERHISTORY($,$,$,.ADDED.,$,$,$,0);
"""

FACHADA = """
#10=IFCPROPERTYSINGLEVALUE('MasaSuperficial',$,IFCLABEL('207,00'),$);
#11=IFCPROPERTYSINGLEVALUE('IndiceGlobalReduccionAcustica',$,IFCREAL(53.),$);
/*#12=IFCPROPERTYSINGLEVALUE('Durabilidad',$,IFCREAL(10),$);*/
#13=IFCPROPERTYSET('a7d5cefb-968c-44b2-8d2b-6f2a2d266a62',#2,'IVE_Prestaciones',$,(#10,#11));
#14=IFCPROPERTYSINGLEVALUE('FireRating',$,IFCLABEL('EI60 Sil\\S\\mceo'),$);
#15=IFCPROPERTYSINGLEVALUE('ThermalTransmitance',$,IFCTHERMALTRANSMITTANCEMEASURE({u}),$);
#16=IFCPROPERTYSET('81b1be72-e96a-491c-8248-464a6c08ce80',#2,'Pset_WallCommon',$,(#14,#15));
#20=IFCWALLTYPE('ab8de682-86df-4e11-aed7-025dc2506305',#2,'Fachada FC01b01M32050',$,$,(#13,#16) ,$,$,$,.STANDARD.);
#30=IFCMATERIAL('F\\S\\abrica de prueba',$,'F\\S\\abricas');
#31=IFCMATERIALLAYER(#30,0.115,$,$,'Hoja 1',$,80);
#32=IFCPROPERTYSINGLEVALUE('Espesor',$,IFCREAL(115,00),$);
#33=IFCPROPERTYSINGLEVALUE('Masa',$,IFCREAL(249),$);
#34=IFCMATERIALPROPERTIES('Pset_Material',$,(#32,#33),#30);
#35=IFCPROPERTYSINGLEVALUE('ThermalConductivity',$,IFCREAL({lam}),$);
#36=IFCPROPERTYSINGLEVALUE('MassDensity',$,IFCREAL(2170),$);
#37=IFCMATERIALPROPERTIES('Pset_MaterialThermal',$,(#35,#36),#30);
#40=IFCMATERIAL('Aislante  de prueba',$,'Aislantes t\\S\\imicos');
#41=IFCMATERIALLAYER(#40,0.05,$,$,'Hoja 1',$,60);
#42=IFCPROPERTYSINGLEVALUE('ThermalConductivity',$,IFCREAL(0.04),$);
#43=IFCPROPERTYSINGLEVALUE('MassDensity',$,IFCREAL(0),$);
#44=IFCMATERIALPROPERTIES('Pset_MaterialThermal',$,(#42,#43),#40);
#50=IFCMATERIALLAYERSET((#31,#41),'Fachada FC01b01M32050');
#51=IFCMATERIALLAYERSETUSAGE(#50,.AXIS2.,.POSITIVE.,-140.);
#52=IFCWALLSTANDARDCASE('c23c33cc-c483-4518-b807-028da63afb45',#2,'Fachada FC01b01M32050',$,$,$,$,$,$);
#53=IFCRELASSOCIATESMATERIAL('b70f9ffb-3955-4b0b-8c48-32bbe7c628fe',#2,$,$,(#52),#51);
#54=IFCRELASSOCIATESMATERIAL('252d2eaf-f429-4a2b-bbea-22daf184b042',#2,$,$,(#20),#50);
#55=IFCRELDEFINESBYTYPE('6e36aba5-152d-46d8-b330-b0b675e62324',#2,$,$,(#52),#20);
"""

PARTICION = """
#60=IFCWALLTYPE('68bc16a7-dc0b-4e26-8021-02e58c5ac7d3',#2,'Partici\\S\\sn PT05_P5.1_40',$,$,$,$,$,$,.STANDARD.);
#61=IFCMATERIAL('Entramado de prueba CEC P5.1 40 mm',$,'Entramados');
#62=IFCMATERIALLAYER(#61,0.086,$,$,'Hoja 1',$,80);
#63=IFCMATERIALLAYERSET((#62),'PT05');
#64=IFCRELASSOCIATESMATERIAL('252d2eaf-f429-4a2b-bbea-22daf184b042',#2,$,$,(#60),#63);
#65=IFCPROPERTYSINGLEVALUE('ThermalTransmitance',$,IFCTHERMALTRANSMITTANCEMEASURE(0),$);
#66=IFCPROPERTYSET('81b1be72-e96a-491c-8248-464a6c08ce80',#2,'Pset_WallCommon',$,(#65));
#67=IFCRELDEFINESBYPROPERTIES('eaf1be77-a49b-40da-8271-5d75c67d0906',#2,$,$,(#60),#66);
#70=IFCSLABTYPE('7367afde-560e-49f8-97ce-24c6022e1f25',#2,'Forjado FJ0125HO1T0E',$,$,$,$,$,$,$);
#71=IFCMATERIAL('Hormig\\S\\sn de prueba',$,$);
#72=IFCMATERIALLAYER(#71,0.25,$,$,$,$,$);
#73=IFCMATERIALLAYERSET((#72),'FJ');
#74=IFCRELASSOCIATESMATERIAL('x',#2,$,$,(#70),#73);
"""

PIE = "ENDSEC;\nEND-ISO-10303-21;\n"


def ifc(*partes, u="0.46", lam="0.5"):
    return CABECERA + "".join(p.replace("{u}", u).replace("{lam}", lam) for p in partes) + PIE


def _escribir(ruta, texto):
    ruta.write_bytes(texto.encode("utf-8"))
    return ruta


@pytest.fixture
def C(plugin, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setenv("ARQ_CATALOGO_CONSTRUCTIVO", str(tmp_path / "usuario" / "cec.json"))
    monkeypatch.setenv("ARQ_BIBLIOTECA_TERMICA", str(tmp_path / "usuario" / "bib.json"))
    return import_module(plugin.commands["CATALOGOEC"].__module__)


def _termica(capas_lam=None):
    """Biblioteca térmica del Ministerio, mínima, con los nombres dados."""
    materiales = {nombre: {"grupo": "", "tipo": "PROPERTIES", "conductividad": lam,
                           "densidad": None, "calor_especifico": None, "difusion_vapor": None}
                  for nombre, lam in (capas_lam or {}).items()}
    return {"formato": "arquitectura-biblioteca-termica", "version": 1,
            "origen": {"fichero": "prueba", "sha256": "0" * 64}, "materiales": materiales,
            "composiciones": {}, "vidrios": {}, "marcos": {}, "huecos": {}, "avisos": []}


# ------------------------------------------------------------------- lectura

def test_lee_las_soluciones_y_corrige_los_defectos_del_catalogo(C, tmp_path):
    bib = C.importar(_escribir(tmp_path / "f.ifc", ifc(FACHADA, PARTICION)))
    assert sorted(bib["soluciones"]) == ["FC01b01M32050", "FJ0125HO1T0E", "PT05_P5.1_40"]
    fc = bib["soluciones"]["FC01b01M32050"]
    assert fc["familia"] == "FC" and fc["clase_ifc"] == "IfcWall"
    assert fc["denominacion"] == "Fachada"
    assert [(c["material"], c["espesor"]) for c in fc["capas"]] == [
        ("Fábrica de prueba", 0.115), ("Aislante de prueba", 0.05)]
    assert fc["espesor"] == pytest.approx(0.165)
    # «207,00» (texto) e IFCREAL(115,00) (coma que parte el número) son números
    assert fc["prestaciones"]["MasaSuperficial"] == 207.0
    assert fc["capas"][0]["propiedades"]["Espesor"] == 115.0
    # el 0 de una densidad es «sin dato»; el comentario /* */ no se lee
    assert fc["capas"][1]["propiedades"]["MassDensity"] is None
    assert "Durabilidad" not in fc["prestaciones"]
    assert fc["comunes"] == {"FireRating": "EI60 Silíceo", "ThermalTransmitance": 0.46}
    # el desplazamiento de -140 m y los GlobalId no se guardan
    texto = json.dumps(bib, ensure_ascii=False)
    assert "-140" not in texto and "ab8de682" not in texto
    assert any("coma decimal" in a for a in bib["avisos"])
    assert bib["soluciones"]["FJ0125HO1T0E"]["clase_ifc"] == "IfcSlab"


def test_las_referencias_al_catalogo_estatal_solo_si_se_declaran(C, tmp_path):
    bib = C.importar(_escribir(tmp_path / "f.ifc", ifc(FACHADA, PARTICION)))
    assert bib["soluciones"]["FC01b01M32050"]["referencias_cte"] == []
    refs = bib["soluciones"]["PT05_P5.1_40"]["referencias_cte"]
    assert [r["codigo"] for r in refs] == ["P5.1"]
    assert refs[0]["origen"].startswith("declarada")
    # la U = 0 de la partición es «sin dato», no una transmitancia nula
    assert bib["soluciones"]["PT05_P5.1_40"]["comunes"]["ThermalTransmitance"] is None


def test_varios_ficheros_se_acumulan_por_codigo(C, tmp_path):
    a = _escribir(tmp_path / "a.ifc", ifc(FACHADA))
    b = _escribir(tmp_path / "b.ifc", ifc(FACHADA, PARTICION))   # mismos GlobalId que a
    bib = C.importar([a, b])
    assert len(bib["soluciones"]) == 3 and len(bib["origenes"]) == 2
    assert not [x for x in bib["avisos"] if "datos distintos" in x]
    distinta = _escribir(tmp_path / "c.ifc", ifc(FACHADA, u="0.52"))
    bib = C.importar(distinta, bib)
    assert any("FC01b01M32050" in x and "datos distintos" in x for x in bib["avisos"])
    assert bib["soluciones"]["FC01b01M32050"]["comunes"]["ThermalTransmitance"] == 0.52


def test_lee_un_zip_y_una_carpeta(C, tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("Fachadas.ifc", ifc(FACHADA))
    zipeado = tmp_path / "exportados.zip"
    zipeado.write_bytes(buffer.getvalue())
    assert list(C.importar(zipeado)["soluciones"]) == ["FC01b01M32050"]
    carpeta = tmp_path / "carpeta"
    carpeta.mkdir()
    _escribir(carpeta / "p.ifc", ifc(PARTICION))
    assert sorted(C.importar(carpeta)["soluciones"]) == ["FJ0125HO1T0E", "PT05_P5.1_40"]


def test_un_fichero_sin_soluciones_se_rechaza(C, tmp_path):
    with pytest.raises(ValueError):
        C.importar(_escribir(tmp_path / "vacio.ifc", ifc()))
    with pytest.raises(ValueError):
        C.importar(_escribir(tmp_path / "otro.ifc", "nada que ver"))


# --------------------------------------------- rango: prevalece el Ministerio

def test_sin_biblioteca_del_ministerio_no_hay_contraste(C, tmp_path):
    sol = C.importar(_escribir(tmp_path / "f.ifc", ifc(FACHADA)))["soluciones"]["FC01b01M32050"]
    c = C.contrastar(sol, None)
    assert c["u_ministerio"] is None and "BIBLIOTECAHE" in c["avisos"][0]


def test_solo_se_contrasta_un_material_de_nombre_identico(C, tmp_path):
    sol = C.importar(_escribir(tmp_path / "f.ifc", ifc(FACHADA)))["soluciones"]["FC01b01M32050"]
    # «Fábrica de prueba» no es «Fábrica de prueba maciza»: no se presupone
    c = C.contrastar(sol, _termica({"Fábrica de prueba maciza": 0.5, "Aislante de prueba": 0.04}))
    assert [f["ministerio"] for f in c["capas"]] == [None, "Aislante de prueba"]
    assert c["u_ministerio"] is None


def test_si_los_valores_difieren_prevalece_el_ministerio(C, tmp_path):
    sol = C.importar(_escribir(tmp_path / "f.ifc", ifc(FACHADA, lam="0.5")))["soluciones"][
        "FC01b01M32050"]
    # mismo nombre (sin tildes ni mayúsculas), otra conductividad
    termica = _termica({"FABRICA de prueba": 0.6, "Aislante de prueba": 0.04})
    c = C.contrastar(sol, termica)
    assert c["capas"][0]["ministerio"] == "FABRICA de prueba"
    assert any("λ 0.5 (catálogo) ≠ 0.6 (Ministerio)" in a and "prevalece el Ministerio" in a
               for a in c["avisos"])
    from importlib import import_module as im
    termica_mod = im(C.__name__.rsplit(".", 1)[0] + ".biblioteca_termica")
    esperada = termica_mod.u_opaco(termica, [("FABRICA de prueba", 0.115),
                                             ("Aislante de prueba", 0.05)])
    assert c["u_ministerio"] == pytest.approx(esperada)
    assert any("prevalece la del Ministerio" in a for a in c["avisos"])   # 0,46 declarada


def test_el_tipo_de_muro_lleva_solo_nombres_y_espesores(C, tmp_path):
    bib = C.importar(_escribir(tmp_path / "f.ifc", ifc(FACHADA, PARTICION)))
    fc = C.tipo_de_muro(bib["soluciones"]["FC01b01M32050"])
    assert fc["wall_category"] == "fachada" and fc["name"] == "FC01b01M32050"
    assert fc["layers"] == [[0.115, "Fábrica de prueba"], [0.05, "Aislante de prueba"]]
    assert fc["catalogo"]["codigo"] == "FC01b01M32050"
    assert "0.5" not in json.dumps(fc)          # ninguna conductividad del catálogo
    pt = C.tipo_de_muro(bib["soluciones"]["PT05_P5.1_40"], "Entramado")
    assert pt["wall_category"] == "particion" and pt["name"] == "Entramado"
    with pytest.raises(ValueError):
        C.tipo_de_muro(bib["soluciones"]["FJ0125HO1T0E"])


# ------------------------------------------------------------------- orden

def test_la_orden_importa_fuera_del_dibujo_crea_un_tipo_y_se_deshace(C, plugin, tmp_path):  # noqa: F811
    s = Session(plugin)
    ctx = _cmd_ctx(s)
    orden = plugin.commands["CATALOGOEC"]
    assert orden(ctx) is None and "no hay catálogo" in s.out[-1]
    ruta = _escribir(tmp_path / "f.ifc", ifc(FACHADA, PARTICION))
    bib = orden(ctx, "importar", str(ruta))
    guardado = Path(os.environ["ARQ_CATALOGO_CONSTRUCTIVO"])
    assert json.loads(guardado.read_text(encoding="utf-8"))["soluciones"] == bib["soluciones"]
    assert not guardado.with_suffix(".tmp").exists()
    assert orden(ctx, "buscar", "aislante") == ["FC01b01M32050"]
    vista = orden(ctx, "ver", "fc01b01m32050")
    assert vista["solucion"]["codigo"] == "FC01b01M32050"
    assert any("informativo" in x for x in s.out)
    pa = import_module(plugin.commands["PARAMETROSARQ"].__module__)
    antes = pa.load_defaults(s.document)["wall_types"]
    tipo = orden(ctx, "tipo", "PT05_P5.1_40", "Entramado", "CEC")
    assert tipo["name"] == "Entramado CEC" and tipo["wall_category"] == "particion"
    tipos = pa.load_defaults(s.document)["wall_types"]
    nuevo = next(t for t in tipos if t["name"] == "Entramado CEC")
    assert nuevo["catalogo"]["codigo"] == "PT05_P5.1_40"
    s.history.undo()
    assert pa.load_defaults(s.document)["wall_types"] == antes
    assert orden(ctx, "tipo", "FJ0125HO1T0E") is None and "solo las fachadas" in s.out[-1]
    assert orden(ctx, "ver", "NOEXISTE") is None
    orden(ctx, "vaciar")
    assert not guardado.exists()


def test_la_orden_esta_registrada_con_su_icono_y_su_ayuda():
    raiz = Path(__file__).parents[1]
    fuente = (raiz / "arquitectura" / "__init__.py").read_text(encoding="utf-8")
    assert '"CATALOGOEC": catalogo_ec' in fuente
    assert (raiz / "arquitectura" / "icons" / "catalogoec.svg").is_file()
    assert '(("CATALOGOEC",)' in (raiz / "arquitectura" / "ayuda.py").read_text(encoding="utf-8")


@pytest.mark.skipif(not os.environ.get("ARQ_CEC_PRUEBA"),
                    reason="sin IFC reales del catálogo (ARQ_CEC_PRUEBA)")
def test_ifc_reales_del_catalogo(C):
    bib = C.importar(os.environ["ARQ_CEC_PRUEBA"])
    assert bib["soluciones"]
    for sol in bib["soluciones"].values():
        assert sol["capas"] and sol["espesor"] > 0
        assert all(c["espesor"] > 0 for c in sol["capas"])

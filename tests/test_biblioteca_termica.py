# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: BIBLIOTECAHE importa un catálogo BDL (.bdc, .gz o .zip) a la
#   biblioteca térmica del usuario y calcula la U de una composición.
"""Biblioteca térmica importada del catálogo de la Herramienta Unificada.

El catálogo real no se distribuye: estas pruebas usan un BDL sintético con
la misma sintaxis. Si se define ``ARQ_BDC_PRUEBA`` con la ruta de un
``BDCatalogo.bdc`` instalado, se prueba además la importación completa.
"""
import gzip
import importlib.util
import io
import json
import os
import zipfile
from pathlib import Path

import pytest

RAIZ = Path(__file__).parents[1]

BDL = '''$ catálogo sintético de prueba
"Ladrillo de prueba" = MATERIAL
     TYPE          = PROPERTIES
     GROUP         = "Fábricas"
     CONDUCTIVITY  =  0.5
     DENSITY       =  1000
     SPECIFIC-HEAT =  1000
     VAPOUR-DIFFUSIVITY-FACTOR =  10
     ..
"Aislante de prueba" = MATERIAL
     TYPE          = PROPERTIES
     GROUP         = "Aislantes"
     CONDUCTIVITY  =  0.04
     DENSITY       =  30
     SPECIFIC-HEAT =  1000
     VAPOUR-DIFFUSIVITY-FACTOR =  1
     ..
"Cámara de aire de prueba" = MATERIAL
     TYPE          = RESISTANCE
     GROUP         = "Cámaras"
     RESISTANCE    =  0.18
     ..
"Fachada de prueba" = LAYERS
     GROUP         = "Fachadas"
     MATERIAL      = ("Ladrillo de prueba","Aislante de prueba","Cámara de aire de prueba")
     THICKNESS     = (0.115,0.04,0.0)
     ..
"Rota" = LAYERS
     MATERIAL      = ("Ladrillo de prueba","No existe")
     THICKNESS     = (0.1,0.05)
     ..
"Vidrio de prueba" = GLASS-TYPE
     GROUP             ="Dobles"
     TYPE              = SHADING-COEF
     SHADING-COEF      =  0.5
     GLASS-CONDUCTANCE =  2.7
     ..
 "Marco de prueba" = NAME-FRAME
      GROUP         = "Metálicos"
      FRAME-WIDTH   =  0.1
      FRAME-CONDUCT =  3.2
      FRAME-ABS     =  0.7
..
"Hueco de prueba" = GAP
     GROUP          = "Huecos"
     GLASS-TYPE          = "Vidrio de prueba"
     NAME-FRAME        = "Marco de prueba"
     PORCENTAGE        = 25.000000
     INF-COEF          = 27.000000
     ..
"Sin interés" = FORJADO
     CANTO = 0.3
     ..
'''


def _modulo():
    spec = importlib.util.spec_from_file_location(
        "biblioteca_termica_prueba", RAIZ / "arquitectura" / "biblioteca_termica.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class Ctx:
    def __init__(self):
        self.lineas = []

    def echo(self, texto):
        self.lineas.append(texto)


@pytest.fixture
def B(tmp_path, monkeypatch):
    monkeypatch.setenv("ARQ_BIBLIOTECA_TERMICA", str(tmp_path / "usuario" / "bib.json"))
    return _modulo()


@pytest.mark.parametrize("forma", ["iso", "utf8", "gz", "zip"])
def test_lee_el_catalogo_en_todas_sus_formas(B, tmp_path, forma):
    datos = {"iso": BDL.replace("\n", "\r\n").encode("iso-8859-1"),
             "utf8": BDL.encode("utf-8"),
             "gz": gzip.compress(BDL.encode("utf-8"))}.get(forma)
    if forma == "zip":
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as z:
            z.writestr("BDCatalogo.bdc", BDL.encode("iso-8859-1"))
        datos = buffer.getvalue()
    ruta = tmp_path / f"catalogo.{forma}"
    ruta.write_bytes(datos)
    bib = B.importar(ruta)
    assert set(bib["materiales"]) == {"Ladrillo de prueba", "Aislante de prueba",
                                      "Cámara de aire de prueba"}
    assert bib["materiales"]["Ladrillo de prueba"]["conductividad"] == 0.5
    assert bib["materiales"]["Cámara de aire de prueba"] == {
        "grupo": "Cámaras", "tipo": "RESISTANCE", "resistencia": 0.18}
    assert bib["composiciones"]["Fachada de prueba"]["capas"][0] == ["Ladrillo de prueba", 0.115]
    assert bib["vidrios"]["Vidrio de prueba"] == {"grupo": "Dobles", "u": 2.7, "g": 0.43}
    assert bib["marcos"]["Marco de prueba"]["u"] == 3.2
    assert bib["huecos"]["Hueco de prueba"]["fraccion_marco"] == 0.25
    assert bib["huecos"]["Hueco de prueba"]["vidrio"] == "Vidrio de prueba"
    assert any("No existe" in a for a in bib["avisos"])
    assert len(bib["origen"]["sha256"]) == 64


def test_los_espacios_repetidos_en_los_nombres_no_rompen_las_referencias(B, tmp_path):
    texto = BDL.replace('"Ladrillo de prueba" = MATERIAL', '"Ladrillo  de prueba" = MATERIAL')
    ruta = tmp_path / "c.bdc"
    ruta.write_text(texto, encoding="utf-8")
    bib = B.importar(ruta)
    assert "Ladrillo de prueba" in bib["materiales"]
    assert not [a for a in bib["avisos"] if "Ladrillo" in a]


def test_un_fichero_que_no_es_catalogo_se_rechaza(B, tmp_path):
    ruta = tmp_path / "otro.bdc"
    ruta.write_text("nada que ver", encoding="utf-8")
    with pytest.raises(ValueError):
        B.importar(ruta)


def test_u_de_una_composicion_con_las_resistencias_del_da_db_he_1(B, tmp_path):
    ruta = tmp_path / "c.bdc"
    ruta.write_text(BDL, encoding="utf-8")
    bib = B.importar(ruta)
    capas = bib["composiciones"]["Fachada de prueba"]["capas"]
    r = 0.115 / 0.5 + 0.04 / 0.04 + 0.18
    assert B.u_opaco(bib, capas) == pytest.approx(1 / (0.13 + r + 0.04))
    assert B.u_opaco(bib, capas, "ascendente") == pytest.approx(1 / (0.10 + r + 0.04))
    assert B.u_opaco(bib, capas, "descendente") == pytest.approx(1 / (0.17 + r + 0.04))
    with pytest.raises(KeyError):
        B.u_opaco(bib, [["No existe", 0.1]])


def test_la_busqueda_no_distingue_tildes_ni_mayusculas(B, tmp_path):
    ruta = tmp_path / "c.bdc"
    ruta.write_text(BDL, encoding="utf-8")
    bib = B.importar(ruta)
    assert B.buscar(bib, "camara") == ["Cámara de aire de prueba"]
    assert B.buscar(bib, "PRUEBA aisl") == ["Aislante de prueba"]


def test_la_orden_importa_guarda_fuera_del_dibujo_y_consulta(B, tmp_path):
    ruta = tmp_path / "c.bdc"
    ruta.write_text(BDL, encoding="utf-8")
    ctx = Ctx()
    assert B.biblioteca_he(ctx) is None
    assert "no hay biblioteca" in ctx.lineas[-1]
    bib = B.biblioteca_he(ctx, "importar", str(ruta))
    guardada = Path(os.environ["ARQ_BIBLIOTECA_TERMICA"])
    assert json.loads(guardada.read_text(encoding="utf-8"))["materiales"] == bib["materiales"]
    assert not guardada.with_suffix(".tmp").exists()
    assert B.biblioteca_he(ctx, "buscar", "ladrillo") == ["Ladrillo de prueba"]
    u = B.biblioteca_he(ctx, "u", "Fachada de prueba", "/", "techo")
    assert u == pytest.approx(B.u_opaco(bib, bib["composiciones"]["Fachada de prueba"]["capas"],
                                        "ascendente"))
    assert B.biblioteca_he(ctx, "u", "Fachada") is None
    assert "Parecidas: Fachada de prueba" in ctx.lineas[-1]
    assert B.biblioteca_he(ctx)["formato"] == B.FORMATO


def test_la_orden_esta_registrada_con_su_icono():
    fuente = (RAIZ / "arquitectura" / "__init__.py").read_text(encoding="utf-8")
    assert '"BIBLIOTECAHE": biblioteca_he' in fuente
    assert (RAIZ / "arquitectura" / "icons" / "bibliotecahe.svg").is_file()


@pytest.mark.skipif(not os.environ.get("ARQ_BDC_PRUEBA"),
                    reason="sin catálogo instalado (ARQ_BDC_PRUEBA)")
def test_catalogo_real_instalado(B):
    bib = B.importar(os.environ["ARQ_BDC_PRUEBA"])
    assert len(bib["materiales"]) > 500 and len(bib["composiciones"]) > 300
    assert len(bib["vidrios"]) > 100 and bib["marcos"] and bib["huecos"]
    for comp in list(bib["composiciones"].values())[:50]:
        if all(m in bib["materiales"] for m, _e in comp["capas"]):
            assert 0.05 < B.u_opaco(bib, comp["capas"]) < 6

# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: ambas manos oscilobatientes se agrupan y viajan desde dos plantas sin perder identidad.
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.escenario_r28 import modelo_carpinterias
from tests.escenarios_r27 import modulo
from tests.verificacion_r27 import datos_bim


def test_modelo_dos_plantas_con_oscilobatientes_y_familias_reales(plugin, tmp_path):
    from core.document import Document
    from ingetrazo_ext.arquitectura_bim import validate_contract

    sesion = modelo_carpinterias(plugin)
    piezas = [
        sesion.meta(e)
        for e in sesion.document.doc.modelspace()
        if (sesion.meta(e) or {}).get("kind") == "opening"
    ]
    recintos = [
        sesion.meta(e)
        for e in sesion.document.doc.modelspace()
        if (sesion.meta(e) or {}).get("kind") == "space"
    ]
    assert len(recintos) == 4
    assert any("Salón" in r["name"] for r in recintos)
    ventanas = [r for r in piezas if r["type"] == "window"]
    oscilobatientes = [r for r in ventanas if r["operation"] == "TILTANDTURN"]
    assert len(ventanas) == 5
    assert len(oscilobatientes) == 2
    assert {r["hinge"] for r in oscilobatientes} == {0, 1}
    assert len([r for r in piezas if r["type"] == "door" and not r.get("cabinet")]) == 9
    assert any(r.get("cabinet") for r in piezas)
    assert any(r["type"] == "gap" for r in piezas)
    assert any(r["curve_mode"] == "curva" for r in piezas)
    memoria = modulo(plugin, "memoria_modelo")
    grupos, cambio = memoria.preparar(sesion.document.doc)
    grupos_dobles = [g for g in grupos if g["definicion"]["operation"] == "TILTANDTURN"]
    assert len(grupos_dobles) == 1 and len(grupos_dobles[0]["piezas"]) == 2
    assert {p["mano"] for p in grupos_dobles[0]["piezas"]} == {"izquierda", "derecha"}
    assert len({p["nivel_id"] for p in grupos_dobles[0]["piezas"]}) == 2
    antes = datos_bim(plugin, sesion.document)
    sesion.history.execute(cambio)
    despues = datos_bim(plugin, sesion.document)
    sesion.history.undo()
    assert datos_bim(plugin, sesion.document) == antes
    sesion.history.redo()
    assert datos_bim(plugin, sesion.document) == despues
    ruta = tmp_path / "carpinterias.dxf"
    sesion.document.save_as(ruta)
    documento = Document.load(ruta)
    assert datos_bim(plugin, documento) == despues
    contrato = modulo(plugin, "exchange").build(documento.doc)
    validate_contract(contrato)
    identidades = {r["id"] for r in oscilobatientes}
    exportadas = [e for e in contrato["elements"] if e["id"] in identidades]
    assert len(exportadas) == 2
    assert {e["params"]["hinge"] for e in exportadas} == {0, 1}
    assert all(e["params"]["operation"] == "TILTANDTURN" for e in exportadas)
    assert not sesion.issues()

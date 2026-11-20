# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: las marcas y el catálogo se guardan juntos y recuperan su estado al deshacer.
import importlib
from copy import deepcopy
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session


def modelo(plugin):
    sesion = Session(plugin)
    muro = sesion.tool("MURO")
    muro.on_point((0.0, 0.0))
    muro.on_point((12.0, 0.0))
    muro.on_enter()
    paquete = plugin.tools["MURO"].__module__.rsplit(".", 1)[0]
    arquitectura = importlib.import_module(paquete + ".architectural_v10")
    transacciones = importlib.import_module(paquete + ".transactions")
    anfitrion = next(iter(sesion.walls().values()))
    for distancia in (1.0, 4.0):
        transacciones.apply_architectural_change(
            muro.ctx,
            arquitectura.create_opening(anfitrion, distancia, 0.885, 0.0, 2.1, kind="door"),
            kind="opening",
        )
    return sesion, importlib.import_module(paquete + ".memoria_modelo"), arquitectura


def registros(sesion):
    return [deepcopy(sesion.meta(e)) for e in sesion.document.doc.modelspace() if sesion.meta(e)]


def test_marcas_persisten_en_fuentes_catalogo_y_deshacer(plugin, tmp_path):
    from core.document import Document

    sesion, memoria, _ = modelo(plugin)
    antes = registros(sesion)
    grupos, cambio = memoria.preparar(sesion.document.doc)
    sesion.history.execute(cambio)
    assert grupos[0]["marca"] == "P1"
    assert {r["mark"] for r in registros(sesion) if r["kind"] == "opening"} == {"P1"}
    despues = registros(sesion)
    sesion.history.undo()
    assert registros(sesion) == antes
    sesion.history.redo()
    assert registros(sesion) == despues
    ruta = tmp_path / "marcas.dxf"
    sesion.document.save_as(ruta)
    documento = Document.load(ruta)
    assert memoria.catalogo(documento.doc)[1] == memoria.catalogo(sesion.document.doc)[1]
    assert {
        r["mark"]
        for e in documento.doc.modelspace()
        if (r := sesion.meta(e)) and r["kind"] == "opening"
    } == {"P1"}


def test_marca_manual_renombra_grupo_completo_y_conserva_identidades(plugin):
    sesion, memoria, arquitectura = modelo(plugin)
    _, cambio = memoria.preparar(sesion.document.doc)
    sesion.history.execute(cambio)
    entidades = [
        e
        for e in sesion.document.doc.modelspace()
        if (sesion.meta(e) or {}).get("kind") == "opening"
    ]
    identidades = [sesion.meta(e)["id"] for e in entidades]
    sesion.history.execute(arquitectura.edit_opening(entidades[0], mark="P8"))
    grupos, cambio = memoria.preparar(sesion.document.doc)
    sesion.history.execute(cambio)
    assert len(grupos) == 1 and grupos[0]["marca"] == "P8"
    assert [sesion.meta(e)["mark"] for e in entidades] == ["P8", "P8"]
    assert [sesion.meta(e)["id"] for e in entidades] == identidades

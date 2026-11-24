# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: una sola manilla en la hoja activa, con material y altura compartidos por 2D y 3D.
import pytest
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_fichas_tipos_usos import qapp  # noqa: F401
from tests.test_wall_tools import Session
from tests.escenarios_r27 import modulo
from tests.test_r27_creacion_texto import responder
from tests.test_r28_oscilobatiente import ventana


@pytest.mark.parametrize(
    "tipo,operacion",
    [("door", "SWINGING"), ("door", "SLIDING"), ("window", "TILTANDTURN"), ("window", "SLIDING")],
)
@pytest.mark.parametrize("principal", ["left", "right"])
@pytest.mark.parametrize("lado", [1, -1])
def test_manilla_unica_en_la_hoja_principal_con_material_y_altura_reales(
    plugin, tipo, operacion, principal, lado
):
    aberturas = modulo(plugin, "openings")
    muro = modulo(plugin, "geom.junctions").Wall("muro", (0, 0), (8, 0), 0.3, "eje")
    registro = ventana(
        type=tipo,
        operation=operacion,
        leaves=2,
        main_leaf=principal,
        side=lado,
        sill=0 if tipo == "door" else 0.9,
        height=2.1 if tipo == "door" else 1.2,
        handle_material="Acero sintético",
    )
    piezas = aberturas.carpentry_parts(muro, registro, 3.2)
    manillas = [p for p in piezas if p["role"] == "handle"]
    assert len(manillas) == 1
    manilla = manillas[0]
    assert manilla["material"] == "Acero sintético"
    a, b, p, q, z0, z1 = manilla["box"]
    assert a < b and p < q and z0 < z1
    assert (z0 + z1) / 2 == pytest.approx(3.2 + (1.05 if tipo == "door" else 1.5))
    centro = (a + b) / 2
    nombre = "Hoja 1" if (principal == "left") == (lado > 0) else "Hoja 2"
    hoja = [p["box"] for p in piezas if p["role"] == "leaf" and p["name"] == nombre]
    assert min(c[0] for c in hoja) < centro < max(c[1] for c in hoja)


def test_fija_y_vano_no_tienen_manilla_y_altura_invalida_se_informa(plugin):
    aberturas = modulo(plugin, "openings")
    muro = modulo(plugin, "geom.junctions").Wall("muro", (0, 0), (8, 0), 0.3, "eje")
    for tipo, operacion in (("window", "FIXED"), ("gap", "")):
        assert not any(
            p["role"] == "handle"
            for p in aberturas.carpentry_parts(muro, ventana(type=tipo, operation=operacion), 0)
        )
    assert aberturas.dimension_problems(ventana(handle_height=-1))
    assert aberturas.dimension_problems(ventana(handle_height=5))


def test_la_manilla_es_parte_del_elemento_en_el_contrato_y_su_alzado(plugin):
    from ingetrazo_ext.arquitectura_bim import validate_contract
    from tests.test_r28a_plano import generar

    sesion = Session(plugin)
    muro = sesion.tool("MURO")
    muro.on_point((0, 0))
    muro.on_point((8, 0))
    muro.on_enter()
    anfitrion = next(iter(sesion.walls().values()))
    sesion.history.execute(
        modulo(plugin, "architectural_v10").create_opening(
            anfitrion,
            1,
            1.2,
            0.9,
            1.2,
            kind="window",
            operation="TILTANDTURN",
            leaves=2,
            main_leaf="right",
            handle_height=1.4,
            handle_material="Acero",
        )
    )
    contrato = modulo(plugin, "exchange").build(sesion.document.doc)
    validate_contract(contrato)
    ventanas = [e for e in contrato["elements"] if e["ifc_class"] == "IfcWindow"]
    assert len(ventanas) == 1
    assert len([p for p in ventanas[0]["parts"] if p["role"] == "handle"]) == 1
    assert not any(e["ifc_class"] == "IfcBuildingElementPart" for e in contrato["elements"])
    generar(sesion, plugin)
    manilla = next(
        e
        for e in sesion.document.doc.modelspace()
        if (sesion.meta(e) or {}).get("role") == "handle"
    )
    assert manilla.dxftype() == "LWPOLYLINE"


def test_altura_y_material_de_manilla_coinciden_en_ficha_y_guion(plugin, qapp):
    sesion = Session(plugin)
    herramienta = sesion.tool("VENTANAARQ")
    ficha, leer = modulo(plugin, "bim_dialogs").carpentry_form(
        herramienta.ctx, {**herramienta.v, **herramienta.bim}
    )
    ficha._arq["handle_height"].setValue(1.35)
    ficha._arq["handle_material"].setCurrentText("Acero")
    datos = leer()
    variante = sesion.tool("-VENTANAARQ")
    responder(variante, {"handle_height": "1,35", "handle_material": "Acero"})
    assert datos["handle_height"] == variante.v["handle_height"] == 1.35
    assert datos["handle_material"] == variante.v["handle_material"] == "Acero"
    ficha.close()


def test_auto_y_altura_explicita_igual_no_separan_tipos_pero_otro_material_si(plugin):
    memoria = modulo(plugin, "memoria_carpinteria")
    muro = modulo(plugin, "geom.junctions").Wall("muro", (0, 0), (8, 0), 0.3, "eje")
    auto = memoria.definir(muro, ventana(handle_height=0))
    explicita = memoria.definir(muro, ventana(handle_height=1.5))
    assert memoria.iguales(auto, explicita)
    assert not memoria.iguales(auto, memoria.definir(muro, ventana(handle_material="Otro metal")))


def test_la_vista_previa_conserva_la_cara_del_elemento_editado(plugin, qapp):
    vista = modulo(plugin, "bim_dialogs").carpentry_preview(lambda: ventana(leaves=2, side=-1, main_leaf="left"))
    assert vista.sample()[1]["side"] == -1
    vista.resize(360, 480)
    assert not vista.grab().isNull()
    assert not vista.error
    vista.close()


def test_una_manilla_dentro_del_hueco_pero_sobre_el_marco_se_rechaza(plugin, qapp):
    aberturas = modulo(plugin, "openings")
    datos = ventana(handle_height=0.92)
    assert aberturas.dimension_problems(datos)
    sesion = Session(plugin)
    herramienta = sesion.tool("VENTANAARQ")
    ficha, leer = modulo(plugin, "bim_dialogs").carpentry_form(herramienta.ctx, {**herramienta.v, **herramienta.bim})
    control = ficha._arq["handle_height"]
    control.setValue(0.92)
    assert ficha._arq["problems"](leer())
    ficha.close()


def test_la_manilla_curva_llega_como_solido_cerrado_y_la_edicion_se_deshace(plugin, tmp_path):
    from core.document import Document
    from ingetrazo_ext.arquitectura_bim import validate_contract
    from tests.verificacion_r27 import estado

    sesion = Session(plugin)
    arquitectura = modulo(plugin, "architectural_v10")
    contexto = sesion.tool("MURO").ctx
    aplicar = modulo(plugin, "transactions").apply_architectural_change
    aplicar(contexto, arquitectura.create_wall((0, 0), (8, 0), 0.3, 3.0, bulge=0.3), kind="wall")
    muro = next(iter(sesion.walls().values()))
    aplicar(
        contexto,
        arquitectura.create_opening(
            muro,
            2,
            1.2,
            0,
            2.1,
            kind="door",
            operation="SLIDING",
            curve_mode="curva",
            width_reference="eje",
        ),
        kind="opening",
    )
    puerta = next(
        e
        for e in sesion.document.doc.modelspace()
        if (sesion.meta(e) or {}).get("kind") == "opening"
    )
    antes = estado(plugin, sesion.document)
    aplicar(
        contexto,
        arquitectura.edit_opening(puerta, handle_height=1.2, handle_material="Acero"),
        kind="opening",
    )
    despues = estado(plugin, sesion.document)
    sesion.history.undo()
    assert estado(plugin, sesion.document) == antes
    sesion.history.redo()
    assert estado(plugin, sesion.document) == despues
    ruta = tmp_path / "curva.dxf"
    sesion.document.save_as(ruta)
    contrato = modulo(plugin, "exchange").build(Document.load(ruta).doc)
    validate_contract(contrato)
    puerta_exportada = next(e for e in contrato["elements"] if e["ifc_class"] == "IfcDoor")
    assert any(p["role"] == "handle" and p["volume"] > 0 for p in puerta_exportada["parts"])

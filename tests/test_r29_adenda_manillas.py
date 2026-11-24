# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: manillas enfrentadas en puertas y una o dos manillas interiores en ventanas.
import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session
from tests.escenarios_r27 import modulo
from tests.test_r28_oscilobatiente import ventana


def piezas(plugin, **cambios):
    aberturas = modulo(plugin, "openings")
    muro = modulo(plugin, "geom.junctions").Wall("muro", (0, 0), (8, 0), 0.3)
    registro = ventana(**cambios)
    return aberturas, registro, aberturas.carpentry_parts(muro, registro, 3.2)


@pytest.mark.parametrize("hojas,modo,cantidad", [(1, "activa", 2), (2, "activa", 2), (2, "ambas", 4)])
@pytest.mark.parametrize("lado", [1, -1])
@pytest.mark.parametrize("principal", ["left", "right"])
def test_puertas_abatibles_tienen_parejas_enfrentadas(plugin, hojas, modo, cantidad, lado, principal):
    _, registro, partes = piezas(
        plugin, type="door", operation="SWINGING", sill=0, height=2.1,
        leaves=hojas, handles_mode=modo, side=lado, main_leaf=principal,
    )
    manillas = [parte["box"] for parte in partes if parte["role"] == "handle"]
    assert len(manillas) == cantidad
    posiciones = {}
    for caja in manillas:
        posiciones.setdefault(caja[:2], []).append(caja)
        assert (caja[4] + caja[5]) / 2 == pytest.approx(4.25)
    assert len(posiciones) == cantidad // 2
    for grupo in posiciones.values():
        assert len(grupo) == 2
        assert grupo[0][4:] == grupo[1][4:]
        assert grupo[0][3] < grupo[1][2] or grupo[1][3] < grupo[0][2]


@pytest.mark.parametrize("cantidad", [1, 2])
@pytest.mark.parametrize("lado", [1, -1])
def test_manillas_de_ventana_se_reparten_dentro_de_la_hoja_y_solo_por_dentro(plugin, cantidad, lado):
    aberturas, registro, partes = piezas(plugin, handles=cantidad, side=lado, leaves=2)
    manillas = [parte["box"] for parte in partes if parte["role"] == "handle"]
    assert len(manillas) == cantidad
    inferior, superior = aberturas.limites_verticales_hoja(registro, 3.2)
    for caja in manillas:
        assert inferior < caja[4] < caja[5] < superior
    if cantidad == 2:
        assert manillas[0][5] < manillas[1][4]
        assert manillas[0][2:4] == manillas[1][2:4]


def test_dos_manillas_no_caben_en_una_hoja_demasiado_baja(plugin):
    aberturas = modulo(plugin, "openings")
    datos = ventana(handles=2, height=0.03, frame_width=0, sill=0.9)
    assert any("manillas" in texto for texto in aberturas.dimension_problems(datos))
    with pytest.raises(ValueError, match="manillas"):
        piezas(plugin, **datos)


@pytest.mark.parametrize("tipo", ["door", "window"])
def test_corredera_conserva_un_tirador_aunque_cambien_los_campos_inactivos(plugin, tipo):
    _, _, partes = piezas(plugin, type=tipo, operation="SLIDING", handles=2, handles_mode="ambas")
    assert len([parte for parte in partes if parte["role"] == "handle"]) == 1


def test_los_datos_anteriores_se_leen_como_activa_y_una_manilla(plugin):
    aberturas = modulo(plugin, "openings")
    datos = ventana()
    datos.pop("handles", None)
    datos.pop("handles_mode", None)
    leidos = aberturas.normalise(datos)
    assert leidos["handles"] == 1
    assert leidos["handles_mode"] == "activa"


def test_dxf_sin_los_datos_nuevos_exporta_los_valores_por_defecto_sin_reescribirlo(plugin, tmp_path):
    from core.document import Document

    sesion = Session(plugin)
    herramienta = sesion.tool("MURO")
    herramienta.on_point((0, 0))
    herramienta.on_point((8, 0))
    herramienta.on_enter()
    muro = next(iter(sesion.walls().values()))
    cambio = modulo(plugin, "architectural_v10").create_opening(muro, 1, 1, 0, 2.1, kind="door")
    sesion.history.execute(cambio)
    anteriores = sesion.meta(cambio.entity)
    for campo in ("handles", "handles_mode", "main_leaf", "handle_height", "handle_material"):
        anteriores.pop(campo, None)
    modulo(plugin, "architectural")._xdata(sesion.document.doc.modelspace(), cambio.entity, anteriores)
    ruta = tmp_path / "registro_anterior.dxf"
    sesion.document.save_as(ruta)
    documento = Document.load(ruta)
    contrato = modulo(plugin, "exchange").build(documento.doc)
    puerta = next(elemento for elemento in contrato["elements"] if elemento["ifc_class"] == "IfcDoor")
    assert puerta["params"]["handles_mode"] == "activa"
    assert puerta["params"]["handles"] == 1
    assert len([parte for parte in puerta["parts"] if parte["role"] == "handle"]) == 2
    entidad = documento.doc.entitydb[cambio.entity.dxf.handle]
    assert sesion.meta(entidad) == anteriores


def test_las_manillas_separan_tipos_y_el_plano_pasa_a_version_tres(plugin):
    memoria = modulo(plugin, "memoria_carpinteria")
    muro = modulo(plugin, "geom.junctions").Wall("muro", (0, 0), (8, 0), 0.3)
    simple = memoria.definir(muro, ventana(handles=1))
    doble = memoria.definir(muro, ventana(handles=2))
    assert not memoria.iguales(simple, doble)
    puerta = ventana(type="door", operation="SWINGING", sill=0, height=2.1, leaves=2)
    activa = memoria.definir(muro, {**puerta, "handles_mode": "activa"})
    ambas = memoria.definir(muro, {**puerta, "handles_mode": "ambas"})
    assert not memoria.iguales(activa, ambas)
    assert modulo(plugin, "memoria_plano").VERSION == 3


@pytest.mark.parametrize("campo,valor", [("handles", 0), ("handles", 3), ("handles", True), ("handles_mode", "otra")])
def test_valores_invalidos_se_informan_en_la_validacion_comun(plugin, campo, valor):
    assert modulo(plugin, "openings").dimension_problems(ventana(**{campo: valor}))


def test_ficha_y_texto_comparten_los_nuevos_datos(plugin):
    from PySide6.QtWidgets import QApplication
    from tests.test_r27_creacion_texto import responder

    aplicacion = QApplication.instance() or QApplication([])
    sesion = Session(plugin)
    herramienta = sesion.tool("VENTANAARQ")
    ficha, leer = modulo(plugin, "bim_dialogs").carpentry_form(
        herramienta.ctx, {**herramienta.v, **herramienta.bim}
    )
    try:
        ficha._arq["handles"].setValue(2)
        variante = sesion.tool("-VENTANAARQ")
        responder(variante, {"handles": "2"})
        assert leer()["handles"] == variante.v["handles"] == 2
    finally:
        ficha.close()


@pytest.mark.parametrize("tipo,modo,cantidad,esperadas", [
    ("door", "activa", 1, 2), ("door", "ambas", 1, 4), ("window", "activa", 2, 2),
])
def test_contrato_persistencia_y_edicion_conservan_piezas_y_volumen(
    plugin, tmp_path, tipo, modo, cantidad, esperadas
):
    from core.document import Document
    from ingetrazo_ext.arquitectura_bim import validate_contract
    from tests.verificacion_r27 import estado

    sesion = Session(plugin)
    herramienta = sesion.tool("MURO")
    herramienta.on_point((0, 0))
    herramienta.on_point((8, 0))
    herramienta.on_enter()
    muro = next(iter(sesion.walls().values()))
    arquitectura = modulo(plugin, "architectural_v10")
    aplicar = modulo(plugin, "transactions").apply_architectural_change
    cambio = arquitectura.create_opening(
        muro, 1, 1.2, 0 if tipo == "door" else 0.9, 2.1 if tipo == "door" else 1.2,
        kind=tipo, operation="SWINGING" if tipo == "door" else "TILTANDTURN", leaves=2,
        handles=cantidad, handles_mode=modo,
    )
    aplicar(herramienta.ctx, cambio, kind="opening")
    identificador = sesion.meta(cambio.entity)["id"]
    ruta = tmp_path / "manillas.dxf"
    sesion.document.save_as(ruta)
    contrato = modulo(plugin, "exchange").build(Document.load(ruta).doc)
    validate_contract(contrato)
    elemento = next(elemento for elemento in contrato["elements"] if elemento["id"] == identificador)
    assert len([parte for parte in elemento["parts"] if parte["role"] == "handle"]) == esperadas
    assert elemento["volume"] == pytest.approx(sum(parte["volume"] for parte in elemento["parts"]))
    assert elemento["params"]["handles"] == cantidad
    assert elemento["params"]["handles_mode"] == modo
    assert sum(e["ifc_class"] == ("IfcDoor" if tipo == "door" else "IfcWindow") for e in contrato["elements"]) == 1
    antes = estado(plugin, sesion.document)
    aplicar(herramienta.ctx, arquitectura.edit_opening(cambio.entity, handle_height=1.3), kind="opening")
    despues = estado(plugin, sesion.document)
    sesion.history.undo()
    assert estado(plugin, sesion.document) == antes
    sesion.history.redo()
    assert estado(plugin, sesion.document) == despues

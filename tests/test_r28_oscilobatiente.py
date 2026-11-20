# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: la operación oscilobatiente conserva ambas manos y comparte símbolos y datos entre ficha y texto.
from copy import deepcopy
import importlib
import math
import pytest
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_fichas_tipos_usos import qapp  # noqa: F401
from tests.test_r27_creacion_texto import responder
from tests.test_wall_tools import Session


def modulo(plugin, nombre):
    paquete = plugin.tools["MURO"].__module__.rsplit(".", 1)[0]
    return importlib.import_module(paquete + "." + nombre)


def ventana(**cambios):
    return {
        "type": "window",
        "operation": "TILTANDTURN",
        "width": 1.2,
        "height": 1.2,
        "sill": 0.9,
        "offset": 1.0,
        "leaves": 1,
        "side": 1,
        "hinge": 0,
        **cambios,
    }


@pytest.mark.parametrize("bisagra", [0, 1])
@pytest.mark.parametrize("lado", [1, -1])
def test_operacion_y_simbolo_de_planta_con_bisagra_real(plugin, bisagra, lado):
    aberturas = modulo(plugin, "openings")
    muro = modulo(plugin, "geom.junctions").Wall("muro", (0.0, 0.0), (8.0, 0.0), 0.3, "eje")
    datos = aberturas.normalise(ventana(hinge=bisagra, side=lado))
    assert datos["operation"] == "TILTANDTURN"
    simbolo = aberturas.plan_symbol(muro, datos)
    arcos = [g for g in simbolo if g[0] == "arc"]
    assert len(arcos) == 1
    centro = arcos[0][1]
    esperado = 1.05 if bisagra == 0 else 2.15
    assert centro[0] == pytest.approx(esperado)
    assert arcos[0][2] == pytest.approx(1.1)
    abatible = aberturas.plan_symbol(muro, {**datos, "operation": "SIDEHUNG"})
    assert simbolo != abatible
    for dato in arcos[0][1:]:
        if isinstance(dato, (int, float)):
            assert math.isfinite(dato)


@pytest.mark.parametrize("bisagra", [0, 1])
def test_alzado_compone_apertura_lateral_y_basculante(plugin, bisagra):
    aberturas = modulo(plugin, "openings")
    datos = aberturas.normalise(ventana(hinge=bisagra))
    trazos = aberturas.simbolos_apertura_alzado(datos)
    assert len(trazos) == 2
    lateral, basculante = trazos
    assert lateral[1][0] == pytest.approx(1.05 if bisagra == 0 else 2.15)
    assert lateral[1][1] == pytest.approx(1.5)
    assert basculante[1] == pytest.approx((1.6, 0.95))
    assert basculante[0][1] == pytest.approx(2.05)
    assert basculante[2][1] == pytest.approx(2.05)


def test_solido_cerrado_y_medidas_no_cambian_con_el_simbolo(plugin):
    aberturas = modulo(plugin, "openings")
    muro = modulo(plugin, "geom.junctions").Wall("muro", (0.0, 0.0), (8.0, 0.0), 0.3, "eje")
    primera = aberturas.carpentry_parts(muro, ventana(), 0.0)
    segunda = aberturas.carpentry_parts(muro, ventana(operation="SIDEHUNG"), 0.0)
    assert primera == segunda
    assert aberturas.filling_box(muro, ventana(), 0.0) == aberturas.filling_box(
        muro, ventana(hinge=1), 0.0
    )


def test_oscilobatiente_solo_en_ventanas_y_en_modelo_plano(plugin):
    aberturas = modulo(plugin, "openings")
    with pytest.raises(ValueError):
        aberturas.normalise(ventana(type="door"))
    with pytest.raises(ValueError):
        aberturas.normalise(ventana(curve_mode="curva", width_reference="eje"))


@pytest.mark.parametrize("bisagra", [0, 1])
def test_ficha_y_ventana_por_texto_producen_la_misma_operacion_y_mano(plugin, qapp, bisagra):
    sesion = Session(plugin)
    normal = sesion.tool("VENTANAARQ")
    ficha, leer = modulo(plugin, "bim_dialogs").carpentry_form(
        normal.ctx, {**normal.v, **normal.bim}
    )
    controles = ficha._arq
    controles["operation"].setCurrentIndex(controles["operation"].findData("TILTANDTURN"))
    controles["hinge"].setCurrentIndex(controles["hinge"].findData(bisagra))
    valores = leer()
    assert valores["operation"] == "TILTANDTURN"
    assert valores["hinge"] == bisagra
    assert controles["hinge"].isHidden() is False
    texto = sesion.tool("-VENTANAARQ")
    responder(texto, {"operation": "TILTANDTURN", "hinge": "Inicial" if bisagra == 0 else "Final"})
    normal.apply_sheet(valores)
    salida = {**texto.v, **texto.bim}
    ficha_aplicada = {**normal.v, **normal.bim}
    # La orden textual normaliza antes la clase y la versión que fija la creación.
    for clave in ("schema", "ifc_class"):
        salida.pop(clave, None)
        ficha_aplicada.pop(clave, None)
    assert set(salida) == set(ficha_aplicada)
    for clave, esperado in ficha_aplicada.items():
        if isinstance(esperado, float):
            assert salida[clave] == pytest.approx(esperado)
        else:
            assert salida[clave] == esperado
    ficha.close()


@pytest.mark.parametrize("bisagra", [0, 1])
@pytest.mark.parametrize("sentido", [1, -1])
def test_colocacion_por_texto_exportacion_y_deshacer_conservan_operacion_y_mano(
    plugin, bisagra, tmp_path, sentido
):
    sesion = Session(plugin)
    muro = sesion.tool("MURO")
    muro.on_point((0.0, 0.0))
    muro.on_point((8.0, 0.0))
    muro.on_enter()
    herramienta = sesion.tool("-VENTANAARQ")
    responder(
        herramienta,
        {
            "operation": "TILTANDTURN",
            "hinge": "Inicial" if bisagra == 0 else "Final",
            "leaves": "1",
        },
    )
    herramienta.on_point((2.0, 0.15))
    herramienta.on_point((2.0 + 2.0 * sentido, 0.15))
    herramienta.on_enter()
    entidad = next(
        e
        for e in sesion.document.doc.modelspace()
        if (sesion.meta(e) or {}).get("kind") == "opening"
    )
    antes = deepcopy(sesion.meta(entidad))
    assert antes["operation"] == "TILTANDTURN" and antes["hinge"] == bisagra
    contrato = sesion.export(tmp_path)
    elemento = next(e for e in contrato["elements"] if e["id"] == antes["id"])
    assert elemento["params"]["operation"] == "TILTANDTURN"
    assert elemento["params"]["hinge"] == bisagra
    sesion.history.undo()
    assert not any(
        (sesion.meta(e) or {}).get("kind") == "opening" for e in sesion.document.doc.modelspace()
    )
    sesion.history.redo()
    recuperada = next(
        e
        for e in sesion.document.doc.modelspace()
        if (sesion.meta(e) or {}).get("id") == antes["id"]
    )
    assert sesion.meta(recuperada) == antes

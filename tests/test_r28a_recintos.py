# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: la localización incluye toda la longitud del vano, también junto a un recinto estrecho.
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session
from tests.escenarios_r27 import modulo


def test_un_recinto_que_solo_toca_un_extremo_del_vano_tambien_se_incluye(plugin):
    sesion = Session(plugin)
    herramienta = sesion.tool("MURO")
    herramienta.thickness = 0.30
    herramienta.on_point((0, 0))
    herramienta.on_point((8, 0))
    herramienta.on_enter()
    muro = next(iter(sesion.walls().values()))
    sesion.history.execute(
        modulo(plugin, "architectural_v10").create_opening(muro, 1.0, 1.2, 0.0, 2.1, kind="door")
    )
    puntos = [(1.02, 0.15), (1.12, 0.15), (1.12, 2.0), (1.02, 2.0)]
    habitacion = {"outer": puntos, "holes": [], "area": 0.185, "perimeter": 3.9}
    cambio, _ = modulo(plugin, "wall_tools").create_space(
        (1.05, 1.0),
        habitacion,
        name="Paso estrecho",
        number=1,
        height=2.7,
        boundary_mode="polyline",
    )
    sesion.history.execute(cambio)
    piezas = modulo(plugin, "memoria_modelo").leer(sesion.document.doc)
    assert piezas[0]["recintos"] == ["Paso estrecho"]


def test_el_frente_de_armario_solo_se_asocia_al_recinto_hacia_el_que_abre(plugin):
    sesion = Session(plugin)
    herramienta = sesion.tool("MURO")
    herramienta.thickness = 0.30
    herramienta.on_point((0, 0))
    herramienta.on_point((8, 0))
    herramienta.on_enter()
    muro = next(iter(sesion.walls().values()))
    sesion.history.execute(
        modulo(plugin, "cabinets").create(muro, 1, 1.2, 0.6, 2.3, mode="adosado", side=1)
    )
    for numero, (nombre, puntos) in enumerate(
        (
            ("Interior", [(0.5, 0.15), (3, 0.15), (3, 2), (0.5, 2)]),
            ("Trasdós", [(0.5, -2), (3, -2), (3, -0.15), (0.5, -0.15)]),
        )
    ):
        area = abs(modulo(plugin, "geom.polygon").area(puntos))
        habitacion = {"outer": puntos, "holes": [], "area": area, "perimeter": 8.7}
        cambio, _ = modulo(plugin, "wall_tools").create_space(
            puntos[0],
            habitacion,
            name=nombre,
            number=numero + 1,
            height=2.7,
            boundary_mode="polyline",
        )
        sesion.history.execute(cambio)
    piezas = modulo(plugin, "memoria_modelo").leer(sesion.document.doc)
    assert len(piezas) == 2
    assert all(pieza["recintos"] == ["Interior"] for pieza in piezas)

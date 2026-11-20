# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: construye un modelo propio de dos plantas para contrastar las familias de carpintería.
from tests.test_wall_tools import Session
from tests.escenarios_r27 import modulo


def modelo_carpinterias(plugin):
    sesion = Session(plugin)
    contexto = sesion.tool("MURO").ctx
    arquitectura = modulo(plugin, "architectural_v10")
    niveles = modulo(plugin, "levels")
    transacciones = modulo(plugin, "transactions")
    catalogo = niveles.load(sesion.document)
    baja = catalogo["levels"][0]
    alta = {"id": "r28-planta-alta", "name": "Planta primera", "elevation": 3.2}
    catalogo["levels"].append(alta)
    niveles.apply(contexto, catalogo)

    def aplicar(cambio):
        transacciones.apply_architectural_change(contexto, cambio)

    def crear_muro(inicio, final, nivel, **valores):
        cambio = arquitectura.create_wall(
            inicio,
            final,
            thickness=0.3,
            height=3.0,
            base=nivel["elevation"],
            level_id=nivel["id"],
            level=nivel["name"],
            **valores,
        )
        anteriores = set(sesion.walls())
        aplicar(cambio)
        return next(e for clave, e in sesion.walls().items() if clave not in anteriores)

    for indice, nivel in enumerate((baja, alta)):
        # Ambas plantas comparten coordenadas XY; la elevación pertenece al nivel.
        puertas = crear_muro((0.0, 0.0), (20.0, 0.0), nivel)
        ventanas = crear_muro((0.0, 6.0), (20.0, 6.0), nivel)
        for numero, (distancia, hojas, operacion, bisagra) in enumerate(
            (
                (1.0, 1, "SWINGING", 0),
                (4.0, 1, "SWINGING", 1),
                (7.0, 2, "SWINGING", 0),
                (10.0, 1, "SLIDING", 1),
            )
        ):
            aplicar(
                arquitectura.create_opening(
                    puertas,
                    distancia,
                    1.4 if hojas == 2 else 0.925,
                    0.0,
                    2.1,
                    kind="door",
                    leaves=hojas,
                    operation=operacion,
                    hinge=bisagra,
                    name=f"Puerta {indice + 1}.{numero + 1}",
                )
            )
        operaciones = (
            ("FIXED", "SIDEHUNG", "TILTANDTURN") if indice == 0 else ("SLIDING", "TILTANDTURN")
        )
        for numero, operacion in enumerate(operaciones):
            aplicar(
                arquitectura.create_opening(
                    ventanas,
                    1.0 + numero * 3.0,
                    1.2,
                    0.9,
                    1.2,
                    kind="window",
                    operation=operacion,
                    leaves=1,
                    hinge=indice,
                    name=f"Ventana {indice + 1}.{numero + 1}",
                )
            )
        if indice == 0:
            aplicar(
                modulo(plugin, "cabinets").create(
                    puertas,
                    14.0,
                    2.4,
                    0.6,
                    2.3,
                    leaves=3,
                    mode="adosado",
                )
            )
            aplicar(arquitectura.create_opening(ventanas, 14.0, 1.0, 0.0, 2.1, kind="gap"))
            curva = crear_muro((24.0, 0.0), (24.0, 6.0), nivel, bulge=0.3)
            aplicar(
                arquitectura.create_opening(
                    curva,
                    2.0,
                    1.2,
                    0.0,
                    2.1,
                    kind="door",
                    operation="SLIDING",
                    curve_mode="curva",
                    width_reference="eje",
                    leaves=1,
                )
            )
    return sesion

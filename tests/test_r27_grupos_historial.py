# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: las referencias DXF de selección sobreviven a editar, Deshacer y Rehacer sin cambiar manejador.
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_wall_tools import Session
from tests.test_r27_configuracion_texto import modulo


def test_editar_y_regenerar_conserva_las_referencias_de_grupo(plugin):
    sesion = Session(plugin)
    herramienta = sesion.tool('MURO')
    herramienta.on_point((0., 0.))
    herramienta.on_point((5., 0.))
    herramienta.on_enter()
    conversion = modulo(plugin, 'conversion_plan')
    sincronizacion = modulo(plugin, 'sync')
    antes = conversion.fingerprint(sesion.document.doc)
    grupos_antes = {n: g.dxf.handle for n, g in sincronizacion.arq_groups(sesion.document.doc)}
    muro = next(iter(sesion.walls().values()))
    cambio = modulo(plugin, 'architectural_v10').edit_wall(muro, height=3.5)
    modulo(plugin, 'transactions').apply_architectural_change(herramienta.ctx, cambio)
    despues = conversion.fingerprint(sesion.document.doc)
    assert {n: g.dxf.handle for n, g in sincronizacion.arq_groups(sesion.document.doc)} == grupos_antes
    for _ in range(2):
        sesion.history.undo()
        assert conversion.fingerprint(sesion.document.doc) == antes
        sesion.history.redo()
        assert conversion.fingerprint(sesion.document.doc) == despues

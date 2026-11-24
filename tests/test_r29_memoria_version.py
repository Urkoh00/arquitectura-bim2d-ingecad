# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: un plano anterior sin hoja principal ni manillas requiere Actualizar sin moverlo.
from copy import deepcopy
from tests.test_ingecad_integration import plugin  # noqa: F401
from tests.test_r28_marcas_dibujo import modelo
from tests.test_r28a_plano import generar
from tests.escenarios_r27 import modulo


def test_arqvalidar_avisa_del_plano_anterior_a_la_nueva_representacion(plugin):
    sesion, _, _ = modelo(plugin)
    plano = generar(sesion, plugin)
    entidad, datos = plano.planos(sesion.document.doc)[0]
    antiguo = deepcopy(datos)
    antiguo["version"] = plano.VERSION - 1
    modulo(plugin, "architectural")._xdata(sesion.document.doc.modelspace(), entidad, antiguo)
    antes = deepcopy(sesion.meta(entidad))
    assert any("desactualizada" in texto for texto in plano.avisos(sesion.document.doc))
    assert sesion.meta(entidad) == antes
    plano.actualizar(sesion.tool("MURO").ctx)
    _, actualizado = plano.planos(sesion.document.doc)[0]
    assert actualizado["id"] == datos["id"] and actualizado["insert"] == datos["insert"]
    assert actualizado["version"] == plano.VERSION
    assert not plano.avisos(sesion.document.doc)

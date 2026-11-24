# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: dos listas más de una revisión externa (24-11): deshacer de un plano que falló pronto y escala uniforme
#   con tolerancia relativa (fallan sin la corrección); la carpintería huérfana
#   en MEMORIACARP ya se omitía (se fija).
from tests.test_ingecad_integration import plugin  # noqa: F401  (fixture)
from tests.test_wall_tools import Session, draw
from tests.test_wall_tools_2 import _door


def test_memoria_ignora_una_carpinteria_sin_muro(plugin):  # noqa: F811
    from arquitectura import memoria_modelo as MM
    s = Session(plugin)
    t = s.tool('MURO')
    draw(t, (0, 0), (4, 0))
    _door(s, list(s.walls().values())[0], 1.0)
    muro = list(s.walls().values())[0]
    s.document.doc.modelspace().unlink_entity(muro)       # muro borrado sin regenerar
    MM.leer(s.document.doc)          # read_model(strict) ya la omite: aviso falso, se fija


def test_deshacer_un_plano_que_no_llego_a_hacerse():
    from arquitectura.memoria_plano import PlanoMemoria
    orden = PlanoMemoria({"escala": 50}, (0, 0))
    assert orden.capas_creadas == [] and orden.crea_discontinua is False and orden.anteriores == []


def test_escala_pequena_y_desigual_no_es_uniforme():
    from arquitectura.frame import Affine
    a = Affine(((0, 0, 0), (1e-6, 0, 0), (0, 2e-6, 0), (0, 0, 1)))
    assert not a.uniform
    b = Affine(((0, 0, 0), (1e-6, 0, 0), (0, 1e-6, 0), (0, 0, 1)))
    assert b.uniform

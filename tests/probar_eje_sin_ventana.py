# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: reproducción en proceso sin QApplication de las opciones de ficha de EDITAREJE.
import os
from pathlib import Path
import sys

sys.path[:0] = [os.environ['INGECAD_SRC'], str(Path(__file__).resolve().parents[1])]
from arquitectura import plugin_spec
from tests.test_wall_tools import Session

sesion = Session(plugin_spec())
rejilla = sesion.tool('EJES')
rejilla.on_point((0., 0.))
herramienta = sesion.tool('EDITAREJE')
herramienta.on_point((0., 2.))
assert herramienta.entity is not None
assert herramienta.on_option(sys.argv[1]) is True
print('SIN CIERRE')

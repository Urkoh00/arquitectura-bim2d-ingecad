# SPDX-License-Identifier: GPL-3.0-or-later
"""Script de test_f5_ventana.py: MainWindow REAL de IngeCAD, MURO activo,
F5 pulsado con QTest. Se ejecuta en un proceso aparte (una ventana Qt por
proceso). Imprime una línea RESULTADO con lo observado."""
import faulthandler
import importlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

faulthandler.dump_traceback_later(60, exit=True)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, os.environ["INGECAD_SRC"])

from PySide6.QtCore import Qt                    # noqa: E402
from PySide6.QtTest import QTest                 # noqa: E402
from PySide6.QtWidgets import QApplication       # noqa: E402

app = QApplication.instance() or QApplication([])
from core.plugins import load_plugin             # noqa: E402

d = Path(tempfile.mkdtemp()) / "arquitectura"
shutil.copytree(ROOT / "arquitectura", d)
spec = load_plugin(d, bundled=False).spec
pkg = spec.tools["MURO"].__module__.rsplit(".", 1)[0]
importlib.import_module(pkg + ".bim_dialogs").available = lambda ctx: False   # sin diálogo modal
from views.tool_controller import register_tool_classes   # noqa: E402
register_tool_classes({k: spec.tools[k] for k in ("MURO", "MUROCURVO")}, owner="arquitectura")
from views.main_window import MainWindow         # noqa: E402

win = MainWindow()
win.new_document("m")
win.show()
QTest.qWaitForWindowExposed(win, 5000)
out = {}
win.tools.start_tool("MURO")
tool = win.tools.tool
tool.reference = "izquierda"
win.viewport.setFocus()
QTest.keyClick(win.viewport, Qt.Key_F5)
app.processEvents()
out["lienzo"] = tool.reference
win.command_line.setFocus()
QTest.keyClick(win.command_line, Qt.Key_F5)
app.processEvents()
out["linea_ordenes"] = tool.reference
win.tools.cancel()
app.processEvents()
QTest.keyClick(win.viewport, Qt.Key_F5)
app.processEvents()
out["tras_cancelar"] = tool.reference
out["atajo_retirado"] = type(tool)._shortcut is None
# MUROCURVO con ORTO: el punto de paso no se fuerza (prueba del 10-11)
win.tools.ortho_on = True
win.tools.start_tool("MUROCURVO")
curvo = win.tools.tool
curvo.on_point((0.0, 0.0))
curvo.on_point((4.0, 0.0))
paso = win.tools.resolved_point(2.0, 1.0)
out["orto_paso"] = [round(v, 6) for v in paso]
curvo.on_point(paso)
out["curvos"] = sum(1 for e in win.document.doc.modelspace()
                    if e.has_xdata("ARQINGECAD") and abs(float(
                        json.loads("".join(v for _c, v in e.get_xdata("ARQINGECAD"))).get("bulge") or 0)) > 0.1)
out["orto_extremo"] = [round(v, 6) for v in win.tools.resolved_point(13.0, 1.0)]   # el siguiente extremo, sí
win.tools.cancel()
win.document.dirty = False
win.close()
print("RESULTADO " + json.dumps(out))

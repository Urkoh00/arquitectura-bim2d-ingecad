# SPDX-License-Identifier: GPL-3.0-or-later
"""Script de test_tab_ventana.py: MainWindow REAL de IngeCAD, MURO activo;
se escribe en la línea de órdenes y se pulsa Tab con QTest. Proceso aparte
(una ventana Qt por proceso). Imprime una línea RESULTADO."""
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
register_tool_classes({k: spec.tools[k] for k in ("MURO",)}, owner="arquitectura")
from views.main_window import MainWindow         # noqa: E402

win = MainWindow()
win.new_document("t")
win.show()
QTest.qWaitForWindowExposed(win, 5000)
line = win.command_line.input
out = {}


def teclear(texto, tecla=None):
    line.setFocus()
    QTest.keyClicks(line, texto)
    if tecla is not None:
        QTest.keyClick(line, tecla)
    app.processEvents()


win.tools.start_tool("MURO")
tool = win.tools.tool
teclear("0,0", Qt.Key_Return)                    # primer punto
out["inicio"] = list(tool.startpoint) if tool.startpoint else None
teclear("5", Qt.Key_Tab)                         # longitud 5 fijada; activa el ángulo
out["fijadas"] = dict(tool.tab_locks)
out["activa"] = tool.tab_field
out["linea_vacia"] = line.text() == ""
out["foco_en_linea"] = line.hasFocus()
teclear("90", Qt.Key_Return)                     # ángulo 90 + Intro: coloca
walls = [json.loads("".join(v for _c, v in e.get_xdata("ARQINGECAD")))
         for e in win.document.doc.modelspace() if e.has_xdata("ARQINGECAD")]
walls = [w for w in walls if w.get("kind") == "wall"]
out["muros"] = len({w["id"] for w in walls})
out["extremo"] = [round(float(v), 6) for v in walls[-1]["b"]] if walls else None
win.tools.cancel()
app.processEvents()
win.viewport.setFocus()
QTest.keyClick(win.viewport, Qt.Key_Tab)         # sin orden: Tab hace lo de siempre
app.processEvents()
out["sin_orden"] = "ok"
win.document.dirty = False
win.close()
print("RESULTADO " + json.dumps(out))

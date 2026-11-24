# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: lista de posibles errores de una revisión externa (24-11). Un armario
#   con más hojas de las que caben (registro editado a mano o importado) hacía
#   fallar la regeneración de todo el dibujo; ahora se avisa y ARQVALIDAR lo
#   señala. El botón Aceptar de la ficha de carpintería sí se desactiva.
from tests.test_ingecad_integration import plugin  # noqa: F401  (fixture)
from tests.test_wall_tools import Session
from tests.escenarios_r27 import modulo


def _armario_imposible(plugin):  # noqa: F811
    s = Session(plugin)
    ctx = s.tool("MURO").ctx
    A = modulo(plugin, "architectural_v10")
    T = modulo(plugin, "transactions")
    T.apply_architectural_change(ctx, A.create_wall((0, 0), (6, 0), thickness=0.3, height=3.0))
    muro = [e for e in s.document.doc.modelspace() if (s.meta(e) or {}).get("kind") == "wall"][0]
    T.apply_architectural_change(ctx, modulo(plugin, "cabinets").create(
        muro, 1.0, 1.0, 0.6, 2.3, leaves=8, mode="adosado"))
    from arquitectura.architectural import _xdata
    hueco = [e for e in s.document.doc.modelspace() if (s.meta(e) or {}).get("kind") == "opening"][0]
    m = dict(s.meta(hueco))
    m["leaves"] = 20            # 0,96 m / 20 = 0,048 m por hoja: no caben
    _xdata(s.document.doc.modelspace(), hueco, m)
    return s


def test_un_armario_imposible_no_impide_regenerar(plugin):  # noqa: F811
    from arquitectura.wall_network import RegenerateContoursCommand
    s = _armario_imposible(plugin)
    orden = RegenerateContoursCommand()
    orden.do(s.document)                         # antes: ValueError y nada se regeneraba
    assert any("sin símbolo en planta" in i for i in orden.issues)


def test_arqvalidar_senala_el_armario_imposible(plugin):  # noqa: F811
    from arquitectura import integrity as IG
    s = _armario_imposible(plugin)
    problemas = IG.audit(s.document.doc)
    assert any("Ancho insuficiente" in p["text"] for p in problemas)


def test_aceptar_se_desactiva_con_un_boton_de_instancia():
    """El aviso decía que ``buttons.StandardButton`` no existe en la instancia:
    sí existe en PySide6, y el botón se obtiene."""
    from PySide6.QtWidgets import QApplication, QDialogButtonBox
    QApplication.instance() or QApplication([])
    b = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    assert hasattr(b, "StandardButton") and b.button(b.StandardButton.Ok) is not None

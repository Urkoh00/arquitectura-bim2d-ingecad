# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: la ayuda cubre exactamente las órdenes registradas y se abre como
#   cuadro ordenado; PARAMETROSARQ abre su ficha (fallaba con NameError).
"""AYUDAARQ en cuadro de diálogo y apertura de PARAMETROSARQ (v1.42)."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401  (fixture)

RAIZ = Path(__file__).parents[1]
NOMBRES_COMERCIALES = ("cype", "dibac", "vectordraw", "revit", "archicad", "allplan",
                       "bimserver", "sketchup")


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_la_ayuda_tiene_todas_las_ordenes_registradas_y_ninguna_mas(plugin):
    from arquitectura import PLUGIN
    from arquitectura.ayuda import ordenes
    registradas = set(PLUGIN.tools) | set(PLUGIN.commands)
    assert ordenes() == registradas, (sorted(registradas - ordenes()),
                                      sorted(ordenes() - registradas))


def test_el_texto_de_ayuda_va_ordenado_por_secciones(plugin):
    from arquitectura.ayuda import SECCIONES, texto
    lineas = texto("9.9")
    secciones = [l for l in lineas if l.startswith("--- ")]
    assert secciones == [f"--- {titulo} ---" for titulo, _ in SECCIONES]
    assert sum(1 for l in lineas if l.startswith("PILAR ")) == 1      # sin duplicados
    assert all(len(l) <= 160 for l in lineas)


def test_sin_ventana_la_ayuda_sale_en_la_linea_de_ordenes(plugin):
    from arquitectura.ayuda import mostrar_ayuda
    eco = []
    mostrar_ayuda(SimpleNamespace(echo=eco.append), "9.9")
    assert eco[0].startswith("=== Plugin Arquitectura 9.9")
    assert any(l.startswith("BIBLIOTECAHE") for l in eco)


def test_el_cuadro_de_ayuda_filtra_y_muestra_el_detalle(plugin, qapp):
    from arquitectura.ayuda import SECCIONES, dialogo
    dlg = dialogo(SimpleNamespace(echo=print), "9.9")
    assert dlg.arbol.topLevelItemCount() == len(SECCIONES)
    dlg.buscador.setText("curvo")
    visibles = [dlg.arbol.topLevelItem(i).child(j).text(0)
                for i in range(dlg.arbol.topLevelItemCount())
                for j in range(dlg.arbol.topLevelItem(i).childCount())
                if not dlg.arbol.topLevelItem(i).child(j).isHidden()]
    assert "MUROCURVO" in visibles and "CURVAMURO" in visibles and "PILAR" not in visibles
    muros = dlg.arbol.topLevelItem(0)
    dlg.arbol.setCurrentItem(muros.child(0))
    assert "ESPESOR TOTAL" in dlg.detalle.toPlainText()
    dlg.deleteLater()


def test_parametrosarq_abre_su_ficha(plugin, qapp, monkeypatch):
    from PySide6.QtWidgets import QDialog
    from arquitectura import bim_dialogs, parameters_arq
    from core.document import Document
    vistos = {}

    def sin_mostrar(dlg):
        combo = dlg._arq[("general", "armarios_superficie_util")]
        vistos["armarios"] = (type(combo).__name__, combo.currentData())
        return QDialog.Rejected

    monkeypatch.setattr(QDialog, "exec", sin_mostrar)
    actuales = parameters_arq.load_defaults(Document.new())
    assert bim_dialogs.architectural_defaults_dialog(SimpleNamespace(host=None), actuales) is None
    assert vistos["armarios"] == ("QComboBox", "computan")


def test_sin_nombres_comerciales_en_el_codigo_del_plugin():
    for carpeta in ("arquitectura", "ingetrazo_ext", "scripts"):
        for fichero in (RAIZ / carpeta).rglob("*.py"):
            if "arq_shared" in fichero.parts:
                continue                           # copia generada de arquitectura/
            texto = fichero.read_text(encoding="utf-8").casefold()
            for nombre in NOMBRES_COMERCIALES:
                assert nombre not in texto, (fichero, nombre)

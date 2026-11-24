# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: el complemento cumple lo que comprueba el robot del catálogo de
#   complementos de IngeCAD: PLUGIN = PluginSpec(id=..., name=...) literal en
#   arquitectura/__init__.py, con el id igual al nombre de la carpeta.
import ast
from pathlib import Path

RAIZ = Path(__file__).parents[1] / "arquitectura"


def _spec():
    arbol = ast.parse((RAIZ / "__init__.py").read_text(encoding="utf-8"))
    for nodo in arbol.body:
        if isinstance(nodo, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "PLUGIN" for t in nodo.targets):
            llamada = nodo.value
            if isinstance(llamada, ast.Call) and getattr(llamada.func, "id", "") == "PluginSpec":
                return {k.arg: k.value for k in llamada.keywords if k.arg}
    return None


def test_plugin_literal_con_id_igual_a_la_carpeta_y_nombre():
    datos = _spec()
    assert datos is not None, "falta PLUGIN = PluginSpec(...) en el nivel superior"
    assert isinstance(datos["id"], ast.Constant) and datos["id"].value == RAIZ.name
    assert "name" in datos


def test_sin_ficheros_compilados_ni_enlaces_en_la_carpeta_publicada():
    # el ZIP del catálogo es la carpeta sin __pycache__; aquí, nada que no se lea
    raros = [p for p in RAIZ.rglob("*")
             if p.is_symlink() or p.suffix in (".so", ".dll", ".pyd", ".exe")]
    assert raros == []

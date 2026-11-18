# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: genera una entrada sintética revisada, comprueba Deshacer/Rehacer
# y exporta el único muro autorizado para ensayar la cadena BIM oficial.
"""Ejecutar con IngeCAD 0.8.0 en PYTHONPATH; no emplea planos de usuario."""
import hashlib
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication
from core.commands import History
from core.document import Document

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from arquitectura import conversion_dialog, conversion_plan, entrada_revisada, exchange


def verificar(destino):
    destino.mkdir(parents=True, exist_ok=True)
    aplicacion = QApplication.instance() or QApplication([])
    documento = Document.new()
    dibujo = documento.doc
    espacio = dibujo.modelspace()
    for nombre in ["REV-MURO-CARA", "REV-MURO-EJE", "REV-HUECO-CANDIDATO"]:
        dibujo.layers.add(nombre)
    for altura in [0., .2, 2., 2.2]:
        espacio.add_line((0., altura), (6., altura), dxfattribs={"layer": "REV-MURO-CARA"})
    caras = list(espacio.query('LINE[layer=="REV-MURO-CARA"]'))
    eje = espacio.add_line((0., .1), (6., .1), dxfattribs={"layer": "REV-MURO-EJE"})
    candidato = espacio.add_line((2., .05), (3., .05), dxfattribs={"layer": "REV-HUECO-CANDIDATO"})
    fuente = destino / "entrada_sintetica.dxf"
    documento.save_as(fuente)
    datos = {
        "schema": entrada_revisada.ESQUEMA,
        "dxf": {"name": fuente.name, "sha256": entrada_revisada.hash_archivo(fuente)},
        "source": {"name": "croquis_sintetico_informativo.pdf", "sha256": hashlib.sha256(b"Origen sintetico, solo informativo").hexdigest()},
        "units": "m",
        "scale_checked": True,
        "review": {"state": "revisado", "date": "2026-11-18"},
        "layers": {
            "REV-MURO-CARA": {"role": "muro-cara", "state": "confirmado"},
            "REV-MURO-EJE": {"role": "muro-eje", "state": "confirmado"},
            "REV-HUECO-CANDIDATO": {"role": "hueco", "state": "candidato"},
        },
        "entities": {cara.dxf.handle: {"state": "pendiente"} for cara in caras[2:]},
    }
    procedencia = Path(str(fuente) + ".procedencia.json")
    procedencia.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    revision = entrada_revisada.cargar_procedencia(procedencia, dibujo)
    clasificacion = conversion_plan.Classification(reviewed_source=revision)
    huella_inicial = conversion_plan.fingerprint(dibujo)
    plan = conversion_plan.analyse(dibujo, (-1., -1.), (7., 3.), clasificacion)
    assert len(plan.result[0]) == 1
    assert not plan.result[1]
    assert set(plan.sources) == set(caras[:2])
    contexto = SimpleNamespace(document=documento)
    dialogo, leer = conversion_dialog.classification_form(contexto, dibujo, clasificacion)
    dialogo.show()
    aplicacion.processEvents()
    dialogo.grab().save(str(destino / "clasificacion_revisada.png"))
    assert leer().role(eje) is None
    assert leer().role(candidato) is None
    dialogo.close()
    historial = History(documento)
    contexto.execute = historial.execute
    conversion_plan.commit(contexto, plan)
    contrato = exchange.build(dibujo, project="Entrada revisada sintética")
    assert len(historial._undo) == 1
    assert len(contrato["elements"]) == 1
    esperado = 6. * .2 * 2.7
    assert math.isclose(contrato["elements"][0]["volume"], esperado, abs_tol=1e-9)
    historial.undo()
    assert conversion_plan.fingerprint(dibujo) == huella_inicial
    historial.redo()
    assert exchange.build(dibujo, project="Entrada revisada sintética") == contrato
    exchange.write(dibujo, destino / "resultado.arqbim", project="Entrada revisada sintética")
    documento.save_as(destino / "resultado.dxf")
    informe = {
        "schema": entrada_revisada.ESQUEMA,
        "muros": 1,
        "huecos": 0,
        "caras_confirmadas": 2,
        "caras_pendientes": 2,
        "eje_excluido": True,
        "candidato_excluido": True,
        "un_deshacer_y_rehacer": True,
        "volumen_analitico_m3": esperado,
        "volumen_contrato_m3": contrato["elements"][0]["volume"],
    }
    (destino / "informe_ingecad.json").write_text(json.dumps(informe, indent=2), encoding="utf-8")
    print(json.dumps(informe, indent=2))


if __name__ == "__main__":
    verificar(Path(sys.argv[1]).resolve())

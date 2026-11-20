# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: dibujo sintético y respuestas reproducibles para el repaso de órdenes.
from importlib import import_module


def modulo(spec, nombre):
    return import_module(spec.tools["MURO"].__module__.rsplit(".", 1)[0] + "." + nombre)


def preparar(spec):
    from tests.test_wall_tools import Session

    sesion = Session(spec)
    herramienta = sesion.tool("MURO")
    herramienta.thickness = 0.3
    for punto in [(0.0, 0.0), (10.0, 0.0), (10.0, 8.0), (0.0, 8.0), (0.0, 0.0)]:
        herramienta.on_point(punto)
    herramienta.on_enter()
    pilar = sesion.tool("PILAR")
    pilar.on_point((20.0, 20.0))
    pilar.on_enter()
    forjado = sesion.tool("FORJADO")
    for punto in [(30.0, 0.0), (36.0, 0.0), (36.0, 5.0), (30.0, 5.0)]:
        forjado.on_point(punto)
    forjado.on_enter()
    forjado.on_enter()
    ejes = sesion.tool("EJES")
    ejes.on_option("x 1x3")
    ejes.on_option("y 1x4")
    ejes.on_point((50.0, 0.0))
    puerta = sesion.tool("PUERTAARQ")
    puerta.on_point((2.0, 0.15))
    puerta.on_point((4.0, 0.15))
    puerta.on_enter()
    dibujo = sesion.document.doc
    dibujo.layers.new("Muros origen")
    for y in (0.0, 0.2):
        dibujo.modelspace().add_line((100.0, y), (105.0, y), dxfattribs={"layer": "Muros origen"})
    return sesion


RESPUESTAS = {
    "ARMARIO": ["70,20", "72,21"],
    "ARMARIOBIM": ["6,0.15", ""],
    "BLOQUE": ["1", "70,20"],
    "BORRATRAMO": ["8,0.15", ""],
    "CAMARA": ["70,20", "75,20", ""],
    "CAPASARQ": [],
    "CAPASAUTO": [],
    "CARPINTERIA": ["5,0.15", "7,0.15", ""],
    "COTAMUROS": ["-1,4", "11,4", ""],
    "CURVAMURO": ["5,0.15", "1", ""],
    "CURVAS3D": ["", "", "70,20", "75,20", "", "fin"],
    "DEFENSA": ["70,20", "75,20", ""],
    "DIVIDEMURO": ["longitud", "2", "0,8", "10,8", ""],
    "EDITARARQ": ["8,0.15"],
    "EDITAREJE": ["50,2", "ficha"],
    "EJES": ["70,20"],
    "ELEMENTOS": ["1"],
    "ESCALERA": ["70,20"],
    "ESTIRAMURO": ["9.9,0.15", "12,0", ""],
    "FORJADO": ["70,20", "75,20", "75,24", "70,24", "", ""],
    "HIPERVINCULO": ["referencia.pdf", "70,20"],
    "HUECOARQ": ["5,0.15", "7,0.15", ""],
    "HUECOFORJADO": ["33,2", "31,1", "32,1", "32,2", "31,2", ""],
    "LINEASAMURO": ["99,-1", "106,1", "confirmar", ""],
    "LISTATEXTOS": ["coord", "70,20"],
    "MEMORIACARP": ["tabla"],
    "MOVERCARP": ["2.5,0.15", "3.5,0.15", ""],
    "MURO": ["70,20", "75,20", ""],
    "MUROCURVO": ["70,20", "75,20", "1", ""],
    "MUROPARALELO": ["8,0.15", "2", "8,3", "8,4", ""],
    "PARTEMURO": ["8,0.15", "7,0.15", "8,0.15", ""],
    "PARTICIONVIRTUAL": ["0,4", "10,4", "", ""],
    "PILAR": ["70,20", ""],
    "PILARESENEJES": ["todos"],
    "PIVOTAMURO": ["9.9,0.15", "12,1", ""],
    "PROPIEDADESARQ": ["8,0.15"],
    "PUERTA": ["70,20"],
    "PUERTAARQ": ["5,0.15", "7,0.15", ""],
    "RECINTO": ["5,4", ""],
    "REJILLA": ["70,20"],
    "SELATRIB": ["elementos", "3"],
    "SUPERFICIE": ["70,20", "75,20", "75,24", "70,24", ""],
    "SUPERFICIES": ["actualizar", ""],
    "TRAMA": ["2", "1", "70,20", "75,20", "75,24", "70,24", ""],
    "UNIRMURO": ["8,0.15", "10,4", ""],
    "URL": ["referencia.pdf", "70,20"],
    "VENTANA": ["70,20"],
    "VENTANAARQ": ["5,0.15", "7,0.15", ""],
    "VERTICES": ["70,20", "75,20", "75,24", "", "80,20"],
    "VERTPOLY": ["70,20", "75,20", "75,24", "", "80,20"],
}

# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: ejecuta una orden por teclado en MainWindow real, en un proceso independiente.
import faulthandler
import importlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import traceback

faulthandler.dump_traceback_later(180, exit=True)
RAIZ = Path(__file__).resolve().parents[1]
sys.path[:0] = [os.environ["INGECAD_SRC"], str(RAIZ)]
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QFileDialog, QLineEdit, QMessageBox
from core.plugins import load_plugin
from views.main_window import MainWindow

orden = sys.argv[1]
destino = Path(sys.argv[2])
destino.mkdir(parents=True, exist_ok=True)
fallos = []


def registrar_excepcion(tipo, error, traza):
    mensaje = "".join(traceback.format_exception(tipo, error, traza))
    fallos.append(mensaje)
    with (destino / "EXCEPCIONES.log").open("a", encoding="utf-8") as registro:
        registro.write(mensaje)
    sys.stderr.write(mensaje)


sys.excepthook = registrar_excepcion
QApplication.setAttribute(Qt.AA_DontUseNativeDialogs, True)
app = QApplication([])
ventana = MainWindow()
carpeta_temporal = Path(tempfile.mkdtemp(prefix="r27_"))
carpeta_plugin = carpeta_temporal / "arquitectura"
shutil.copytree(RAIZ / "arquitectura", carpeta_plugin)
cargado = load_plugin(carpeta_plugin, bundled=False)
assert cargado.available, cargado.reason
ventana.plugins.loaded[cargado.spec.id] = cargado
assert ventana.plugins.activate(cargado.spec.id)
ventana.new_document("Ensayo sintético R27")
from core.document import Document

semilla = Path(os.environ.get("R27_SEMILLA", "/workspace/work/r27-evidence/semilla"))
ventana.document = Document.load(semilla / "modelo.dxf")
ventana.tools.attach_document(ventana.document)
ventana.plugins.document_opened(ventana.document)
from tests.escenarios_r27 import RESPUESTAS, modulo

arquitectura = modulo(cargado.spec, "architectural")
if orden.lstrip("-") == "NIVELASIGNAR":
    fuente = next(
        e
        for e in ventana.document.doc.modelspace()
        if (arquitectura.metadata(e) or {}).get("kind") == "wall"
    )
    ventana.tools.selection = {fuente.dxf.handle}

ventana.show()
QTest.qWaitForWindowExposed(ventana, 5000)
linea = ventana.command_line.input
respuestas = []
cuadros = []
titulos_cuadros = []
cuadros_preparados = set()
modo = os.environ.get("R27_DIALOGOS", "aceptar")


def contestar_cuadro():
    # Un selector puede abrir inmediatamente otro cuadro dentro de su señal.
    # Un temporizador de un solo disparo atiende también ese bucle anidado.
    QTimer.singleShot(25, contestar_cuadro)
    cuadro = app.activeModalWidget()
    if cuadro is None:
        return
    if cuadro not in cuadros:
        cuadros.append(cuadro)
        titulos_cuadros.append(cuadro.windowTitle())
        print("CUADRO", type(cuadro).__name__, cuadro.windowTitle(), flush=True)
    if isinstance(cuadro, QFileDialog) and modo == "cancelar":
        QTest.keyClick(cuadro, Qt.Key_Escape)
        return
    if isinstance(cuadro, QFileDialog) and id(cuadro) not in cuadros_preparados:
        cuadros_preparados.add(id(cuadro))
        ruta = (
            semilla / "propuesta.arqcambios"
            if orden.lstrip("-") == "SINCRONIZARARQ"
            else destino / "exportado.arqbim"
        )
        cuadro.setDirectory(str(ruta.parent))
        entrada = cuadro.findChild(QLineEdit, "fileNameEdit")
        if entrada is not None:
            entrada.setFocus()
            entrada.selectAll()
            QTest.keyClicks(entrada, ruta.name)
            print("ARCHIVO", cuadro.selectedFiles(), flush=True)
            cuadro.grab().save(str(destino / "selector_archivo.png"))
            QTest.keyClick(entrada, Qt.Key_Return)
            return
    if isinstance(cuadro, QMessageBox):
        botones = cuadro.buttons()
        if botones:
            QTest.mouseClick(botones[-1], Qt.LeftButton)
        return
    botones = cuadro.findChildren(QDialogButtonBox)
    for caja in botones:
        aceptar = [
            b
            for b in caja.buttons()
            if caja.buttonRole(b) in (QDialogButtonBox.AcceptRole, QDialogButtonBox.YesRole)
        ]
        cerrar = [
            b
            for b in caja.buttons()
            if caja.buttonRole(b) in (QDialogButtonBox.RejectRole, QDialogButtonBox.NoRole)
        ]
        candidatos = (cerrar or aceptar) if modo == "cancelar" else (aceptar or cerrar)
        if candidatos:
            QTest.mouseClick(candidatos[0], Qt.LeftButton)
            return


QTimer.singleShot(25, contestar_cuadro)


def esperar_regeneracion():
    limite = time.monotonic() + 15.0
    while time.monotonic() < limite:
        app.processEvents()
        trabajador = getattr(ventana, "_regen_worker", None)
        temporizador_regeneracion = getattr(ventana.tools, "_regen_timer", None)
        pendiente = temporizador_regeneracion is not None and temporizador_regeneracion.isActive()
        if trabajador is None and not pendiente:
            QTest.qWait(30)
            if getattr(ventana, "_regen_worker", None) is None:
                return
        QTest.qWait(15)
    raise AssertionError("La regeneración de la ventana no terminó")


def escribir(texto):
    linea.setFocus()
    QTest.keyClicks(linea, str(texto))
    QTest.keyClick(linea, Qt.Key_Return)
    app.processEvents()
    esperar_regeneracion()
    respuestas.append(str(texto))


def contestar_ficha():
    for _ in range(150):
        herramienta = ventana.tools.tool
        if herramienta is None or getattr(herramienta, "_campos_texto", None) is None:
            return
        campo = herramienta._campos_texto[herramienta._indice_texto]
        if campo.clave == "ruta":
            ruta = (
                semilla / "propuesta.arqcambios"
                if orden == "-SINCRONIZARARQ"
                else destino / "exportado.arqbim"
            )
            escribir(str(ruta))
        else:
            escribir("")
    raise AssertionError("La ficha de texto no termina")


from tests.verificacion_r27 import estado, datos_bim, persistencia

antes_orden = estado(cargado.spec, ventana.document)
incidencias_antes = modulo(cargado.spec, "quality").audit_architecture(ventana.document)[
    "incidencias"
]
escribir(orden)
contestar_ficha()
guion_respuestas = (
    json.loads(os.environ["R27_RESPUESTAS"])
    if "R27_RESPUESTAS" in os.environ
    else RESPUESTAS.get(orden.lstrip("-"), [])
)
for respuesta in guion_respuestas:
    if ventana.tools.tool is None:
        break
    escribir(respuesta)
    contestar_ficha()
# Esc se envía por teclado también en las órdenes de inserción continua.
linea.setFocus()
QTest.keyClick(linea, Qt.Key_Escape)
QTest.qWait(40)
verificaciones = {}
if os.environ.get("R27_VERIFICAR") == "1":
    despues_orden = estado(cargado.spec, ventana.document)
    pasos = ventana.history.depth
    for _ in range(pasos):
        ventana._cmd_undo()
    verificaciones["deshacer_exacto"] = estado(cargado.spec, ventana.document) == antes_orden
    for _ in range(pasos):
        ventana._cmd_redo()
    verificaciones["rehacer_exacto"] = estado(cargado.spec, ventana.document) == despues_orden
    verificaciones["pasos_deshacer"] = pasos
    incidencias = modulo(cargado.spec, "quality").audit_architecture(ventana.document)[
        "incidencias"
    ]
    verificaciones["incidencias_antes"] = incidencias_antes
    verificaciones["incidencias_despues"] = incidencias
    antes_regenerar = datos_bim(cargado.spec, ventana.document)
    escribir("UNIONESARQ")
    verificaciones["uniones_idempotente"] = (
        datos_bim(cargado.spec, ventana.document) == antes_regenerar
    )
    verificaciones["persistencia"] = persistencia(cargado.spec, ventana.document, destino)
esperar_regeneracion()
app.processEvents()
modulo_arq = importlib.import_module(
    cargado.spec.tools["MURO"].__module__.rsplit(".", 1)[0] + ".architectural"
)
registros = [
    modulo_arq.metadata(e) for e in ventana.document.doc.modelspace() if modulo_arq.metadata(e)
]
if orden.startswith("-"):
    assert not titulos_cuadros, "La variante abrió cuadros: " + str(titulos_cuadros)
resultado = {
    "orden": orden,
    "plataforma": app.platformName(),
    "respuestas": respuestas,
    "cuadros": titulos_cuadros,
    "excepciones": fallos,
    "registros": registros,
    "verificaciones": verificaciones,
    "profundidad": ventana.history.depth,
    "modo_cuadros": modo,
    "historial": ventana.command_line.history.toPlainText(),
}
ventana.grab().save(str(destino / "ventana.png"))
(destino / "resultado.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + "\n")
ventana.tools.cancel()
esperar_regeneracion()
ventana.document.dirty = False
ventana.close()
shutil.rmtree(carpeta_temporal)
assert not fallos, fallos
print(
    "RESULTADO "
    + json.dumps(
        {
            "orden": orden,
            "plataforma": app.platformName(),
            "cuadros": len(cuadros),
            "registros": len(registros),
            "excepciones": len(fallos),
        },
        ensure_ascii=False,
    )
)

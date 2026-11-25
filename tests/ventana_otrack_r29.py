# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: toma una referencia con pausa real y registra el punto entregado por el controlador nativo.
import faulthandler
import json
import os
from pathlib import Path
import sys
import time
import traceback

faulthandler.dump_traceback_later(120, exit=True)
RAIZ = Path(__file__).resolve().parents[1]
sys.path[:0] = [os.environ['INGECAD_SRC'], str(RAIZ)]
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialogButtonBox
from core.plugins import load_plugin
from views.main_window import MainWindow
from tests.test_wall_tools import Session
from tests.escenarios_r27 import modulo
from tests.verificacion_r27 import estado

orden = sys.argv[1]
destino = Path(sys.argv[2])
referencia = sys.argv[3] if len(sys.argv) > 3 else 'cara'
destino.mkdir(parents=True, exist_ok=True)
app = QApplication([])
fallos = []


def registrar_excepcion(tipo, error, traza):
    texto = ''.join(traceback.format_exception(tipo, error, traza))
    fallos.append(texto)
    sys.stderr.write(texto)


sys.excepthook = registrar_excepcion
cargado = load_plugin(RAIZ / 'arquitectura', bundled=False)
assert cargado.available, cargado.reason
# La semilla usa órdenes reales sin interfaz; todos los datos son propios.
sesion = Session(cargado.spec)
niveles = modulo(cargado.spec, 'levels')
sesion.history.execute(niveles.StoreCatalog(niveles.load(sesion.document)))
puntos = [(0, 0), (6, 0), (6, 4), (0, 4)]
for inicio, final in zip(puntos, puntos[1:] + puntos[:1]):
    cambio = modulo(cargado.spec, 'architectural_v10').create_wall(inicio, final, 0.3)
    modulo(cargado.spec, 'transactions').apply_architectural_change(sesion.tool('MURO').ctx, cambio)
if orden in ('RECINTO', 'FORJADO'):
    cambio = modulo(cargado.spec, 'architectural_v10').create_wall(
        (1, 2), (2, 2), 0.1, wall_category='particion')
    modulo(cargado.spec, 'transactions').apply_architectural_change(sesion.tool('MURO').ctx, cambio)
if orden == 'MOVERCARP':
    puerta = sesion.tool('PUERTAARQ')
    puerta.on_point((1.5, 0.15))
    puerta.on_point((2.5, 0.15))
    puerta.on_enter()
sesion.document.doc.header['$INSUNITS'] = 6
ventana = MainWindow()
ventana.plugins.loaded[cargado.spec.id] = cargado
assert ventana.plugins.activate(cargado.spec.id)
ventana.new_document('Modelo sintético R29: rastreo')
ventana.document = sesion.document
ventana.tools.attach_document(ventana.document)
ventana.plugins.document_opened(ventana.document)
ventana.show()
QTest.qWaitForWindowExposed(ventana, 5000)
cuadros = []


def aceptar_ficha():
    cuadro = app.activeModalWidget()
    if cuadro is None:
        return
    if cuadro.windowTitle() not in cuadros:
        cuadros.append(cuadro.windowTitle())
    botones = cuadro.findChild(QDialogButtonBox)
    if botones is not None:
        boton = botones.button(QDialogButtonBox.Ok)
        if boton is not None:
            boton.click()


def esperar_regeneracion():
    limite = time.monotonic() + 15
    while time.monotonic() < limite:
        app.processEvents()
        temporizador = getattr(ventana.tools, '_regen_timer', None)
        pendiente = temporizador is not None and temporizador.isActive()
        if getattr(ventana, '_regen_worker', None) is None and not pendiente:
            QTest.qWait(40)
            if not ventana.tools.caches_warming():
                return
        QTest.qWait(15)
    raise AssertionError('No termina la regeneración nativa')


def escribir(texto):
    linea = ventana.command_line.input
    linea.setFocus()
    QTest.keyClicks(linea, texto)
    QTest.keyClick(linea, Qt.Key_Return)
    esperar_regeneracion()


def mover_cursor(punto):
    x, y = ventana.viewport.view.world_to_screen(*punto)
    posicion = QPoint(int(x), int(y))
    ventana.viewport.setFocus()
    QTest.mouseMove(ventana.viewport, posicion)
    app.processEvents()
    return posicion


temporizador_fichas = QTimer()
temporizador_fichas.timeout.connect(aceptar_ficha)
temporizador_fichas.start(50)
ventana.viewport.view.zoom_extents(-1, -1, 9, 5)
ventana.regen_in_memory()
esperar_regeneracion()
escribir(orden)
herramienta = ventana.tools.tool
assert herramienta is not None, orden
seleccion_inicial = herramienta.entity_picker
if orden == 'MUROPARALELO':
    # Se toma la fachada norte: las referencias del sur quedan a un lado,
    # en vez de pedir un lado mediante un punto situado en la propia base.
    escribir('3,3.85')
    assert herramienta.stage == 'side'
elif orden in ('ESTIRAMURO', 'PIVOTAMURO'):
    escribir('5.8,0.15')
    assert herramienta.wall is not None
elif orden == 'CARPINTERIA':
    escribir('3,0.15')
    assert herramienta.first is not None
elif orden == 'MOVERCARP':
    # La hoja libre se puede designar sin coincidir con el contorno del muro.
    arquitectura = modulo(cargado.spec, 'architectural')
    segmentos_hoja = []
    for entidad in ventana.document.doc.modelspace():
        if entidad.dxftype() != 'LWPOLYLINE':
            continue
        if (arquitectura.metadata(entidad) or {}).get('kind') != 'opening_symbol':
            continue
        vertices = list(entidad.get_points('xy'))
        if entidad.closed:
            vertices.append(vertices[0])
        segmentos_hoja.extend(zip(vertices, vertices[1:]))
    inicio, final = max(segmentos_hoja, key=lambda segmento:
                        sum((a - b) ** 2 for a, b in zip(*segmento)))
    centro_hoja = [(a + b) / 2 for a, b in zip(inicio, final)]
    escribir(f'{centro_hoja[0]},{centro_hoja[1]}')
    assert herramienta.entity is not None
antes = estado(cargado.spec, ventana.document)
profundidad_antes = ventana.history.depth
ventana.tools.osnap_on = True
ventana.tools.osnap_modes = {'END'}
ventana.tools.ortho_on = False
ventana.tools.polar_on = False
ventana.tools.snap_on = False
ventana.tools.otrack_on = False
ventana.activateWindow()
app.processEvents()
ventana.viewport.setFocus()
QTest.qWait(40)
QTest.keyClick(ventana.viewport, Qt.Key_F11)
assert ventana.tools.otrack_on
# El primer movimiento arranca las cachés nativas; esperar evita confundir
# su construcción al abrir el dibujo con la ausencia de una referencia.
mover_cursor((8, 4))
QTest.qWait(300)
esperar_regeneracion()
origen = (6, 0) if referencia == 'eje' else (-0.15, -0.15)
if orden in ('RECINTO', 'FORJADO'):
    origen = (2, 2) if referencia == 'eje' else (2, 1.95)
elif orden == 'PIVOTAMURO' and referencia == 'eje':
    origen = (6, 4)
objetivo = (4, origen[1] + 0.02)
if orden == 'ESTIRAMURO':
    objetivo = (8, origen[1] + 0.02)
mover_cursor(origen)
QTest.qWait(ventana.tools.TRACK_DWELL_MS + 160)
adquiridos = list(ventana.tools.track_points())
posicion = mover_cursor(objetivo)
QTest.qWait(80)
entrada_cursor = ventana.viewport.view.screen_to_world(posicion.x(), posicion.y())
resuelto = ventana.tools.resolved_point(*entrada_cursor)
guia = ventana.tools.track_hint
seleccion_al_colocar = herramienta.entity_picker
ventana.viewport.update()
QTest.qWait(80)
captura = ventana.screen().grabWindow(ventana.winId())
captura_pantalla = not captura.isNull()
if captura_pantalla:
    posicion_vista = ventana.viewport.mapTo(ventana, QPoint(0, 0))
    pixmap = ventana.screen().grabWindow(
        ventana.winId(), posicion_vista.x(), posicion_vista.y(),
        ventana.viewport.width(), ventana.viewport.height())
else:
    # Qt offscreen no tiene pantalla ni contexto GL: la prueba gráfica se hace en X11.
    captura = ventana.grab()
    pixmap = ventana.viewport.grab()
captura.save(str(destino / 'rastreo.png'))
imagen = pixmap.toImage()
trazos_naranjas = 0
huecos_trazo = 0
if guia is not None:
    inicio_pantalla = ventana.viewport.view.world_to_screen(*guia[0])
    final_pantalla = ventana.viewport.view.world_to_screen(*guia[1])
    escala_pixel = pixmap.devicePixelRatio()
    izquierda = int(min(inicio_pantalla[0], final_pantalla[0]) * escala_pixel) + 20
    derecha = int(max(inicio_pantalla[0], final_pantalla[0]) * escala_pixel) - 20
    fila = int(inicio_pantalla[1] * escala_pixel)
    for columna in range(max(0, izquierda), min(imagen.width(), derecha)):
        muestra_naranja = False
        for desplazamiento in range(-2, 3):
            color = imagen.pixelColor(columna, fila + desplazamiento)
            if color.red() > 200 and 100 < color.green() < 210 and color.blue() < 90:
                muestra_naranja = True
        if muestra_naranja:
            trazos_naranjas += 1
        else:
            huecos_trazo += 1
# El observador no cambia el punto ni sustituye la operación de la herramienta.
puntos_entregados = []
accion_original = herramienta.on_point


def observar_punto(punto):
    puntos_entregados.append(tuple(punto))
    return accion_original(punto)


herramienta.on_point = observar_punto
QTest.mouseClick(ventana.viewport, Qt.LeftButton, pos=posicion)
esperar_regeneracion()
herramienta.on_point = accion_original
if orden == 'MUROPARALELO':
    escribir('4,-2')
elif orden == 'MURO':
    escribir('5,-0.15')
elif orden == 'MUROCURVO':
    escribir('5,-0.15')
    escribir('1')
elif orden == 'FORJADO':
    for respuesta in ('5,1.95', '5,3', '4,3', '', ''):
        escribir(respuesta)
ventana.tools.cancel()
esperar_regeneracion()
despues = estado(cargado.spec, ventana.document)
pasos_deshacer = ventana.history.depth - profundidad_antes
escribir('UNDO')
escribir('1')
deshacer_exacto = estado(cargado.spec, ventana.document) == antes
escribir('REDO')
rehacer_exacto = estado(cargado.spec, ventana.document) == despues
fuentes = ('wall', 'opening', 'column', 'space', 'slab')
identidades_antes = {registro['id'] for registro in antes['bim']['registros']
                     if registro.get('kind') in fuentes}
identidades_despues = {registro['id'] for registro in despues['bim']['registros']
                       if registro.get('kind') in fuentes}
origenes_antes = {registro['id']: registro for registro in antes['bim']['registros']
                  if registro.get('kind') in fuentes}
origenes_despues = {registro['id']: registro for registro in despues['bim']['registros']
                    if registro.get('kind') in fuentes}
referencias = ('wall_id', 'level_id', 'level', 'level_offset')
referencias_conservadas = all(
    origenes_despues[identificador].get(campo) == registro.get(campo)
    for identificador, registro in origenes_antes.items()
    if identificador in origenes_despues
    for campo in referencias
)
resultado = {
    'orden': orden, 'referencia': referencia,
    'plataforma': app.platformName(), 'cuadros': cuadros,
    'seleccion_inicial': seleccion_inicial, 'seleccion_al_colocar': seleccion_al_colocar,
    'origen': origen, 'cursor': entrada_cursor, 'resuelto': resuelto,
    'adquiridos': adquiridos, 'guia': guia, 'entregados': puntos_entregados,
    'pixeles_trazo': trazos_naranjas, 'pixeles_hueco_trazo': huecos_trazo,
    'captura_pantalla': captura_pantalla,
    'pasos_deshacer': pasos_deshacer,
    'deshacer_exacto': deshacer_exacto, 'rehacer_exacto': rehacer_exacto,
    'identidades_conservadas': identidades_antes <= identidades_despues,
    'referencias_conservadas': referencias_conservadas,
    'mismos_elementos': identidades_antes == identidades_despues,
    'excepciones': fallos,
}
ventana.document.save_as(destino / 'modelo.dxf')
ventana.tools.cancel()
ventana.document.dirty = False
ventana.close()
(destino / 'RESULTADO.json').write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + '\n')
print('RESULTADO ' + json.dumps(resultado, ensure_ascii=False))

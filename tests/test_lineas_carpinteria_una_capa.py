# SPDX-License-Identifier: GPL-3.0-or-later
"""LINEASAMURO con la carpintería en UNA capa (puertas y ventanas juntas, líneas y
polilíneas), como la dibujan muchas aplicaciones LISP: la puerta se distingue por su
giro (arco) y la ventana por sus líneas de vidrio. Planos sintéticos."""
import pytest
from tests.test_ingecad_integration import plugin
from tests.test_wall_tools import Session
from tests.test_r12_conversion import module


def planta(target, layer_walls='Gpared', layer_carp='Fcarp'):
    """Muro de 6 m y 0,20 con una puerta (1,00-1,90) y una ventana (3,50-4,70)."""
    for y in (0, .2):
        for x0, x1 in ((0, 1), (1.9, 3.5), (4.7, 6)):
            target.add_line((x0, y), (x1, y), dxfattribs={'layer': layer_walls})
    # puerta: giro como polilínea con bulto (cuarto de círculo) y hoja como línea
    target.add_lwpolyline([(1.9, .2, 0, 0, 0.41421356), (1.0, 1.1)],
                          format='xyseb', dxfattribs={'layer': layer_carp})
    target.add_line((1.0, .2), (1.0, 1.1), dxfattribs={'layer': layer_carp})
    # ventana: marco y vidrio, tres líneas dentro del espesor (una de ellas polilínea)
    target.add_line((3.5, .05), (4.7, .05), dxfattribs={'layer': layer_carp})
    target.add_lwpolyline([(3.5, .10), (4.7, .10)], dxfattribs={'layer': layer_carp})
    target.add_line((3.5, .15), (4.7, .15), dxfattribs={'layer': layer_carp})


def capas(d):
    for n in ('Gpared', 'Fcarp'):
        if n not in d.layers:
            d.layers.new(n)


def kinds(plan):
    return sorted(o[3] for o in plan.result[1])


def test_una_capa_de_carpinteria_se_distingue_por_el_dibujo(plugin):
    s = Session(plugin); d = s.document.doc; capas(d); planta(d.modelspace())
    P = module(s, 'conversion_plan')
    plan = P.analyse(d, (-1, -1), (7, 3), P.Classification({'Gpared': 'muros', 'Fcarp': 'carpinteria'}))
    assert len(plan.result[0]) == 1
    assert kinds(plan) == ['door', 'window']


def test_capa_forzada_a_puertas_lo_convierte_todo_en_puertas(plugin):
    """Asignar la capa a «Puertas» es una orden explícita: prevalece sobre el dibujo."""
    s = Session(plugin); d = s.document.doc; capas(d); planta(d.modelspace())
    P = module(s, 'conversion_plan')
    plan = P.analyse(d, (-1, -1), (7, 3), P.Classification({'Gpared': 'muros', 'Fcarp': 'puertas'}))
    assert kinds(plan) == ['door', 'door']


def test_excepcion_designada_prevalece_sobre_el_dibujo(plugin):
    """Una puerta corredera (sin arco) se lee como ventana; designada como puerta, es puerta."""
    s = Session(plugin); d = s.document.doc; capas(d); planta(d.modelspace())
    P = module(s, 'conversion_plan')
    c = P.Classification({'Gpared': 'muros', 'Fcarp': 'carpinteria'})
    ventana = [e.dxf.handle for e in d.modelspace() if e.dxf.layer == 'Fcarp'
               and e.dxftype() in ('LINE', 'LWPOLYLINE') and min(p[0] for p in _pts(e)) >= 3.4]
    c.assign(ventana, 'puertas')
    assert kinds(P.analyse(d, (-1, -1), (7, 3), c)) == ['door', 'door']


def test_planta_dentro_de_un_bloque_se_clasifica_por_sus_capas(plugin):
    """La planta suele venir dentro de un bloque: cada línea va según SU capa."""
    s = Session(plugin); d = s.document.doc; capas(d)
    b = d.blocks.new('PLANTA_BAJA'); planta(b)
    insert = d.modelspace().add_blockref('PLANTA_BAJA', (0, 0))
    P = module(s, 'conversion_plan')
    assert {'Gpared', 'Fcarp'} <= set(P.layers_present(d))
    plan = P.analyse(d, (-1, -1), (7, 3), P.Classification({'Gpared': 'muros', 'Fcarp': 'carpinteria'}))
    assert len(plan.result[0]) == 1 and kinds(plan) == ['door', 'window']
    assert insert not in plan.sources          # el bloque no se toca


def _pts(e):
    if e.dxftype() == 'LINE':
        return [tuple(e.dxf.start), tuple(e.dxf.end)]
    return [tuple(p[:2]) for p in e.get_points()]


def test_propuesta_de_categorias_por_nombre_de_capa(plugin):
    s = Session(plugin); P = module(s, 'conversion_plan')
    g = P.guess_roles(['Gpared', 'Fcamara', 'Fcarp', 'Mpilar', 'Fescalera', 'Frejas',
                       'Fejes', 'Freferencia', 'Puertas', 'Ventanas', 'ARQ-MUROS', 'Cotas'])
    assert g == {'Gpared': 'muros', 'Fcarp': 'carpinteria', 'Mpilar': 'pilares',
                 'Fescalera': 'escaleras', 'Frejas': 'rejas', 'Puertas': 'puertas',
                 'Ventanas': 'ventanas'}


def test_cuadro_propone_y_lista_capas_del_bloque(plugin):
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])       # al ejecutar este fichero solo
    s = Session(plugin); d = s.document.doc; capas(d)
    b = d.blocks.new('PLANTA'); planta(b); d.modelspace().add_blockref('PLANTA', (0, 0))
    P = module(s, 'conversion_plan'); D = module(s, 'conversion_dialog')
    t = s.tool('LINEASAMURO')
    dlg, read = D.classification_form(None, d, P.Classification())
    c = read()
    assert c.layers.get('Gpared') == 'muros' and c.layers.get('Fcarp') == 'carpinteria'
    dlg.deleteLater()


def test_plano_a_escala_reducida_se_detecta_y_propone_factor(plugin):
    """Un plano dibujado a 1/4 (giros de puerta de 0,225) no se convierte en
    disparates: se avisa y se propone el factor de escala."""
    from ezdxf.math import Matrix44
    s = Session(plugin); d = s.document.doc; capas(d); m = d.modelspace(); planta(m)
    d.modelspace().add_arc((4.0, 2.0), 0.9, 0, 90, dxfattribs={'layer': 'Fcarp'})   # otra puerta
    for e in list(m):
        e.transform(Matrix44.scale(0.25, 0.25, 1))
    P = module(s, 'conversion_plan')
    with pytest.raises(ValueError, match='factor 4'):
        P.analyse(d, (-1, -1), (3, 2), P.Classification({'Gpared': 'muros', 'Fcarp': 'carpinteria'}))


def test_capas_apagadas_no_se_leen(plugin):
    s = Session(plugin); d = s.document.doc; capas(d); planta(d.modelspace())
    d.layers.get('Fcarp').off()
    P = module(s, 'conversion_plan')
    plan = P.analyse(d, (-1, -1), (7, 3), P.Classification({'Gpared': 'muros', 'Fcarp': 'carpinteria'}))
    assert kinds(plan) == ['void', 'void']           # sin carpintería visible, vanos
    assert any('apagadas' in w for w in plan.warnings)
    d.layers.get('Gpared').freeze()
    plan = P.analyse(d, (-1, -1), (7, 3), P.Classification({'Gpared': 'muros', 'Fcarp': 'carpinteria'}))
    assert not plan.result[0]


def test_designar_con_ventana_y_con_captura(plugin):
    s = Session(plugin); d = s.document.doc; capas(d); planta(d.modelspace())
    C = module(s, 'convert_tools')
    dentro = C.entities_in_rect(d, (-0.5, -0.5), (3.6, 0.5))            # izquierda → derecha
    toca = C.entities_in_rect(d, (3.6, 0.5), (-0.5, -0.5), crossing=True)
    assert dentro and set(dentro) < set(toca)
    lineas = {e.dxf.handle for e in d.modelspace() if e.dxftype() == 'LINE' and e.dxf.layer == 'Gpared'}
    assert {h for h in dentro if h in lineas} == {e.dxf.handle for e in d.modelspace()
            if e.dxftype() == 'LINE' and e.dxf.layer == 'Gpared' and max(e.dxf.start.x, e.dxf.end.x) <= 3.6}
    d.layers.get('Gpared').off()
    assert not set(C.entities_in_rect(d, (-0.5, -0.5), (7, 0.5))) & lineas


def test_herramienta_designa_por_ventana(plugin):
    s = Session(plugin); d = s.document.doc; capas(d); planta(d.modelspace())
    P = module(s, 'conversion_plan'); t = s.tool('LINEASAMURO')
    t.classification = P.Classification(); t.pick_role = 'muros'
    t.ctx.services.pick_entity = lambda p: None            # pulsar en vacío
    t.on_point((-0.5, -0.5)); assert t.preview_segments((7, 0.5))
    t.on_point((7, 0.5))
    assert sum(1 for r in t.classification.handles.values() if r == 'muros') >= 6

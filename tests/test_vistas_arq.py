# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: SECCIONARQ y ALZADOARQ en la sesión real de IngeCAD: una casa con
#   puerta, ventana y forjado; corte, vistas, niveles, marca, Actualizar y
#   Deshacer/Rehacer en una sola transacción.
import math

import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401  (fixture)
from tests.test_wall_tools import Session
from tests.escenarios_r27 import modulo


def casa(plugin):  # noqa: F811
    s = Session(plugin)
    t = s.tool('MURO')
    t.thickness, t.reference = 0.30, 'eje'
    for p in [(0, 0), (6, 0), (6, 4), (0, 4), (0, 0)]:
        t.on_point(p)
    t.on_enter()
    v10 = modulo(plugin, 'architectural_v10')
    sur = next(w for w in s.walls().values()
               if abs(s.meta(w)['a'][1]) < 1e-9 and abs(s.meta(w)['b'][1]) < 1e-9)
    s.history.execute(v10.create_opening(sur, 1.0, 0.9, 0.0, 2.1, kind='door'))
    s.history.execute(v10.create_opening(sur, 3.5, 1.2, 0.9, 1.2, kind='window'))
    sl = modulo(plugin, 'slabs')
    cambio = sl.create([(-0.15, -0.15), (6.15, -0.15), (6.15, 4.15), (-0.15, 4.15)],
                       thickness=0.3, top=3.3)
    s.history.execute(cambio[0] if isinstance(cambio, tuple) else cambio)
    return s


def _detalles(s, vista_id=None, papel=None):
    arch = modulo(s.plugin, 'architectural')
    out = []
    for e in s.document.doc.modelspace():
        m = arch.metadata(e) or {}
        if m.get('kind') == 'arq_view_detail' and (vista_id is None or m['view_id'] == vista_id) \
                and (papel is None or m['role'] == papel):
            out.append(e)
    return out


def _anclas(s):
    return modulo(s.plugin, 'vistas_arq').vistas(s.document.doc)


def _seccion(s, p, q, lado, insercion, opciones=()):
    t = s.tool('SECCIONARQ')
    for o in opciones:
        t.on_option(o)
    for punto in (p, q, lado, insercion):
        t.on_point(punto)
    return t


def test_seccion_transversal_por_la_puerta(plugin):  # noqa: F811
    s = casa(plugin)
    # corte por x = 1,45 (en el hueco de la puerta), mirando hacia +x
    _seccion(s, (1.45, -2), (1.45, 6), (3, 0), (20, 0))
    (ancla, datos), = _anclas(s)
    assert datos['tipo'] == 'seccion' and datos['nombre'] == 'A'
    rellenos = _detalles(s, datos['id'], 'relleno')
    # cortados: muro norte, forjado y el cerco de la puerta (el muro sur no:
    # el corte pasa por su hueco)
    assert len(rellenos) >= 3
    cortes = _detalles(s, datos['id'], 'corte')
    zs = [p[1] for e in cortes for p in e.get_points('xy')]
    assert min(zs) == pytest.approx(0.0) and max(zs) == pytest.approx(3.3)
    assert _detalles(s, datos['id'], 'visto')
    marcas = _detalles(s, datos['id'], 'marca')
    assert {e.dxf.text for e in marcas if e.dxftype() == 'TEXT'} == {"A", "A'"}
    assert all(e.dxf.layer.startswith('ARQ-VISTA-') for e in _detalles(s))
    assert any('cortados' in x for x in s.out)


def test_el_alzado_sur_dibuja_la_puerta_y_la_ventana_sin_cortar(plugin):  # noqa: F811
    s = casa(plugin)
    t = s.tool('ALZADOARQ')
    for punto in ((-1, -3), (7, -3), (3, 0), (0, -20)):
        t.on_point(punto)
    (ancla, datos), = _anclas(s)
    assert datos['tipo'] == 'alzado' and datos['nombre'] == '1'
    assert _detalles(s, datos['id'], 'relleno') == []
    lineas = _detalles(s, datos['id'], 'visto')
    # el contorno del hueco de la ventana: líneas verticales en s = 1 + 3,5 y
    # 1 + 4,7 (la línea empieza en x = −1) entre 0,9 y 2,1 de altura
    y0 = -20.0
    verticales = {e.dxf.start.x for e in lineas
                  if abs(e.dxf.start.x - e.dxf.end.x) < 1e-9
                  and min(e.dxf.start.y, e.dxf.end.y) >= y0 + 0.9 - 1e-6
                  and max(e.dxf.start.y, e.dxf.end.y) <= y0 + 2.1 + 1e-6}
    assert any(abs(v - 4.5) < 0.05 for v in verticales)
    assert any(abs(v - 5.7) < 0.05 for v in verticales)


def test_actualizar_regenera_desde_el_modelo_y_se_deshace(plugin):  # noqa: F811
    s = casa(plugin)
    _seccion(s, (3, -2), (3, 6), (4, 0), (20, 0))
    (ancla, datos), = _anclas(s)
    antes = {e.dxf.handle for e in _detalles(s, datos['id'])}
    # se sube el forjado: la sección vieja no lo sabe hasta Actualizar
    arch = modulo(plugin, 'architectural')
    forjado = next(e for e in s.document.doc.modelspace()
                   if (arch.metadata(e) or {}).get('kind') == 'slab')
    m = arch.metadata(forjado)
    sl = modulo(plugin, 'slabs')
    s.history.execute(sl.EditSlab(forjado, dict(m, base=m['base'] + 0.5)))
    t = s.tool('SECCIONARQ')
    t.on_option('Actualizar')
    despues = _detalles(s, datos['id'])
    assert antes.isdisjoint({e.dxf.handle for e in despues})
    zs = [p[1] for e in _detalles(s, datos['id'], 'corte') for p in e.get_points('xy')]
    assert max(zs) == pytest.approx(3.8)
    s.history.undo()
    assert {e.dxf.handle for e in _detalles(s, datos['id'])} == antes
    s.history.redo()
    assert {e.dxf.handle for e in _detalles(s, datos['id'])} == {e.dxf.handle for e in despues}


def test_crear_una_vista_se_deshace_entera(plugin):  # noqa: F811
    s = casa(plugin)
    capas_antes = {c.dxf.name for c in s.document.doc.layers}
    _seccion(s, (3, -2), (3, 6), (4, 0), (20, 0), opciones=('Nombre', 'B', 'Profundidad', '2'))
    (ancla, datos), = _anclas(s)
    assert datos['nombre'] == 'B' and datos['profundidad'] == 2
    s.history.undo()
    assert _anclas(s) == [] and _detalles(s) == []
    assert {c.dxf.name for c in s.document.doc.layers} == capas_antes
    s.history.redo()
    assert len(_anclas(s)) == 1 and _detalles(s)


def test_una_linea_sin_edificio_no_rompe_nada(plugin):  # noqa: F811
    s = casa(plugin)
    _seccion(s, (50, 50), (60, 50), (55, 60), (80, 0))
    (ancla, datos), = _anclas(s)
    assert _detalles(s, datos['id'], 'relleno') == [] and _detalles(s, datos['id'], 'visto') == []
    assert _detalles(s, datos['id'], 'titulo')


def test_las_ordenes_estan_registradas_con_su_icono(plugin):  # noqa: F811
    from pathlib import Path
    raiz = Path(__file__).parents[1] / 'arquitectura'
    assert 'SECCIONARQ' in plugin.tools and 'ALZADOARQ' in plugin.tools
    assert (raiz / 'icons' / 'seccionarq.svg').is_file()
    assert (raiz / 'icons' / 'alzadoarq.svg').is_file()


def test_dibujo_de_prueba(plugin, tmp_path):  # noqa: F811
    """Guarda un DXF con una sección y un alzado para revisarlo a ojo
    (ARQ_VISTAS_DXF = ruta)."""
    import os
    destino = os.environ.get('ARQ_VISTAS_DXF')
    if not destino:
        pytest.skip('sin ARQ_VISTAS_DXF')
    s = _con_peto(plugin)
    _seccion(s, (1.45, -2), (1.45, 6), (3, 0), (10, 0))
    t = s.tool('ALZADOARQ')
    for punto in ((-1, -3), (7, -3), (3, 0), (0, -8)):
        t.on_point(punto)
    _seccion(s, (-1, 2), (7, 2), (3, 0), (10, -8), opciones=('Nombre', 'B'))
    s.document.doc.saveas(destino)


def _con_peto(plugin):  # noqa: F811
    """La casa con un antepecho de 1 m sobre el forjado de cubierta."""
    s = casa(plugin)
    v10 = modulo(plugin, 'architectural_v10')
    for a, b in (((-0.075, -0.075), (6.075, -0.075)), ((6.075, -0.075), (6.075, 4.075)),
                 ((6.075, 4.075), (-0.075, 4.075)), ((-0.075, 4.075), (-0.075, -0.075))):
        s.history.execute(v10.create_wall(a, b, thickness=0.15, height=1.0, base=3.3,
                                          wall_category='defensa', defense_type='antepecho'))
    return s


def test_el_peto_de_la_cubierta_aparece_en_la_seccion_y_el_alzado(plugin):  # noqa: F811
    s = _con_peto(plugin)
    _seccion(s, (3, -2), (3, 6), (4, 0), (20, 0))
    t = s.tool('ALZADOARQ')
    for punto in ((-1, -3), (7, -3), (3, 0), (0, -20)):
        t.on_point(punto)
    (_a, seccion), (_b, alzado) = sorted(_anclas(s), key=lambda x: x[1]['tipo'], reverse=True)
    zs = [p[1] for e in _detalles(s, seccion['id'], 'corte') for p in e.get_points('xy')]
    assert max(zs) == pytest.approx(4.3)                   # el peto, cortado, hasta 3,3 + 1
    lineas = _detalles(s, alzado['id'], 'visto')
    assert max(max(e.dxf.start.y, e.dxf.end.y) for e in lineas) == pytest.approx(-20 + 4.3)


def test_opciones_de_relleno_y_grosores(plugin):  # noqa: F811
    s = casa(plugin)
    pa = modulo(plugin, 'parameters_arq')
    valores = pa.load_defaults(s.document)
    assert valores['general']['vista_relleno'] == 'color' and valores['general']['vista_color'] == 9
    valores['general'].update(vista_relleno='diagonal', grosor_corte=0.70, grosor_visto=0.13)
    s.history.execute(pa.SetArchitecturalDefaults(valores))
    capas = s.document.doc.layers
    capas.new('ARQ-VISTA-CORTE', dxfattribs={'color': 3})      # una capa ya existente
    _seccion(s, (3, -2), (3, 6), (4, 0), (20, 0))
    (_a, datos), = _anclas(s)
    relleno = _detalles(s, datos['id'], 'relleno')[0]
    assert relleno.dxf.solid_fill == 0 and relleno.dxf.pattern_name == 'ANSI31'
    assert capas.get('ARQ-VISTA-CORTE').dxf.lineweight == 70
    assert capas.get('ARQ-VISTA-CORTE').dxf.color == 7
    assert capas.get('ARQ-VISTA-VISTO').dxf.lineweight == 13
    assert capas.get('ARQ-VISTA-TIERRA').dxf.lineweight == 70
    assert capas.get('ARQ-VISTA-RELLENO').dxf.color == 9
    tierra = _detalles(s, datos['id'], 'tierra')
    assert len(tierra) == 1 and tierra[0].dxf.start.y == pytest.approx(0.0)
    s.history.undo()
    assert capas.get('ARQ-VISTA-CORTE').dxf.color == 3      # la capa vuelve a como estaba
    with pytest.raises(ValueError):
        valores['general']['vista_color'] = 1
        pa.validate_defaults(valores)


def test_un_fallo_al_actualizar_antes_de_retirar_la_vista_no_la_duplica(plugin, monkeypatch):  # noqa: F811
    s = casa(plugin)
    _seccion(s, (3, -2), (3, 6), (4, 0), (20, 0))
    espacio = s.document.doc.modelspace()
    antes = sorted(e.dxf.handle for e in espacio)
    va = modulo(plugin, 'vistas_arq')

    def fallar(self, dibujo, opciones):
        raise ValueError('Fallo de prueba en capas')

    monkeypatch.setattr(va.VistaArq, '_capas', fallar)
    t = s.tool('SECCIONARQ')
    try:
        t.on_option('Actualizar')
    except ValueError:
        pass
    despues = [e.dxf.handle for e in espacio]
    assert len(despues) == len(set(despues)), 'entidades duplicadas en el espacio'
    assert sorted(despues) == antes

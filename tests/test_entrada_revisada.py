# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: entradas revisadas: procedencia, exclusiones, fuente y Deshacer.
import json
from pathlib import Path

import pytest

from tests.test_ingecad_integration import plugin
from tests.test_fichas import qt
from tests.test_r12_conversion import module
from tests.test_wall_tools import Session


def crear_entrada(plugin, tmp_path, con_hueco=False):
    sesion = Session(plugin)
    dibujo = sesion.document.doc
    for nombre in ["REV-MURO-CARA", "REV-MURO-EJE", "REV-HUECO-CANDIDATO", "REV-PUERTA"]:
        dibujo.layers.add(nombre)
    espacio = dibujo.modelspace()
    caras = []
    intervalos = [(0, 2), (3, 6)] if con_hueco else [(0, 6)]
    for altura in [0, .2]:
        for inicio, fin in intervalos:
            caras.append(espacio.add_line((inicio, altura), (fin, altura), dxfattribs={"layer": "REV-MURO-CARA"}))
    eje = espacio.add_line((0, .1), (6, .1), dxfattribs={"layer": "REV-MURO-EJE"})
    candidato = espacio.add_line((2, .05), (3, .05), dxfattribs={"layer": "REV-HUECO-CANDIDATO"})
    fuente = tmp_path / "entrada.dxf"
    sesion.document.save_as(fuente)
    entrada = module(sesion, "entrada_revisada")
    datos = {
        "schema": "arq.entrada-revisada/v1",
        "dxf": {"name": fuente.name, "sha256": entrada.hash_archivo(fuente)},
        "source": {"name": "croquis-no-disponible.pdf", "sha256": "a" * 64},
        "units": "m",
        "scale_checked": True,
        "review": {"state": "revisado", "date": "2026-11-18"},
        "layers": {
            "REV-MURO-CARA": {"role": "muro-cara", "state": "confirmado"},
            "REV-MURO-EJE": {"role": "muro-eje", "state": "confirmado"},
            "REV-HUECO-CANDIDATO": {"role": "hueco", "state": "candidato"},
            "REV-PUERTA": {"role": "puerta", "state": "pendiente"},
        },
    }
    ruta = tmp_path / "entrada.dxf.procedencia.json"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    return sesion, ruta, datos, caras, eje, candidato


def analizar(sesion, ruta):
    entrada = module(sesion, "entrada_revisada")
    planes = module(sesion, "conversion_plan")
    procedencia = entrada.cargar_procedencia(ruta, sesion.document.doc)
    clasificacion = planes.Classification(reviewed_source=procedencia)
    return planes, clasificacion, planes.analyse(sesion.document.doc, (-1, -1), (7, 2), clasificacion)


def test_dos_caras_y_eje_auxiliar_dan_un_muro_y_un_deshacer(plugin, tmp_path):
    sesion, ruta, datos, caras, eje, candidato = crear_entrada(plugin, tmp_path)
    planes, clasificacion, plan = analizar(sesion, ruta)
    assert len(plan.result[0]) == 1
    assert not plan.result[1]
    assert clasificacion.role(eje) is None
    assert clasificacion.role(candidato) is None
    assert set(plan.sources) == set(caras)
    huella = planes.fingerprint(sesion.document.doc)
    herramienta = sesion.tool("LINEASAMURO")
    assert planes.commit(herramienta.ctx, plan)
    assert len(sesion.walls()) == 1
    assert eje.dxf.layer == "REV-MURO-EJE"
    assert candidato.dxf.layer == "REV-HUECO-CANDIDATO"
    sesion.history.undo()
    assert not sesion.walls()
    assert planes.fingerprint(sesion.document.doc) == huella
    sesion.history.redo()
    assert len(sesion.walls()) == 1


def test_sin_procedencia_no_convierte_ni_por_capa_ni_por_objeto(plugin, tmp_path):
    sesion, ruta, datos, caras, eje, candidato = crear_entrada(plugin, tmp_path)
    ruta.unlink()
    planes = module(sesion, "conversion_plan")
    lector = module(sesion, "convert_tools")
    nombres = planes.layers_present(sesion.document.doc)
    assert not planes.guess_roles(nombres)
    clasificacion = planes.Classification({nombre: "muros" for nombre in nombres})
    clasificacion.assign([cara.dxf.handle for cara in caras], "muros")
    plan = planes.analyse(sesion.document.doc, (-1, -1), (7, 2), clasificacion)
    assert not plan.result[0]
    assert not lector.collect(sesion.document.doc, (-1, -1), (7, 2))[0]
    herramienta = sesion.tool("LINEASAMURO")
    herramienta._convert((-1, -1), (7, 2))
    assert not sesion.walls()


@pytest.mark.parametrize("estado", ["pendiente", "rechazado", "candidato"])
def test_estado_no_confirmado_prevalece_sobre_asignaciones(plugin, tmp_path, estado):
    sesion, ruta, datos, caras, eje, candidato = crear_entrada(plugin, tmp_path)
    datos["layers"]["REV-MURO-CARA"]["state"] = estado
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    planes, clasificacion, plan = analizar(sesion, ruta)
    clasificacion.assign([cara.dxf.handle for cara in caras], "muros")
    assert all(clasificacion.role(cara) is None for cara in caras)
    assert not plan.result[0]


@pytest.mark.parametrize("cambio", ["fuente", "procedencia", "dibujo"])
def test_cambiar_la_fuente_o_revision_invalida_la_confirmacion(plugin, tmp_path, cambio):
    sesion, ruta, datos, caras, eje, candidato = crear_entrada(plugin, tmp_path)
    planes, clasificacion, plan = analizar(sesion, ruta)
    if cambio == "fuente":
        fuente = ruta.parent / datos["dxf"]["name"]
        fuente.write_bytes(fuente.read_bytes() + b"\n")
    elif cambio == "procedencia":
        datos["layers"]["REV-MURO-CARA"]["state"] = "pendiente"
        ruta.write_text(json.dumps(datos), encoding="utf-8")
    else:
        caras[0].dxf.end = (7, 0)
    herramienta = sesion.tool("LINEASAMURO")
    with pytest.raises(ValueError, match="cambi|dibujo"):
        planes.commit(herramienta.ctx, plan)
    assert not sesion.walls()



def test_cuadro_muestra_revision_por_entidad_y_bloquea_ejes(plugin, tmp_path, qt):
    sesion, ruta, datos, caras, eje, candidato = crear_entrada(plugin, tmp_path)
    planes, clasificacion, plan = analizar(sesion, ruta)
    cuadros = module(sesion, "conversion_dialog")
    dialogo, leer = cuadros.classification_form(None, sesion.document.doc, clasificacion)
    tabla = dialogo._arq["table"]
    for numero in range(tabla.rowCount()):
        selector = tabla.cellWidget(numero, 1)
        assert not selector.isEnabled()
        if tabla.item(numero, 0).text() == "REV-MURO-EJE":
            assert selector.currentText() == "No convertir"
    assert leer().reviewed_source is clasificacion.reviewed_source
    assert not dialogo._arq["pick"].isEnabled()
    dialogo.close()


def test_rangos_no_duplican_caras_confirmadas(plugin, tmp_path):
    sesion, ruta, datos, caras, eje, candidato = crear_entrada(plugin, tmp_path)
    planes, clasificacion, plan = analizar(sesion, ruta)
    clasificacion.thickness_ranges = {"muros": (.1, .3), "tabiques": (.05, .15)}
    plan = planes.analyse(sesion.document.doc, (-1, -1), (7, 2), clasificacion)
    assert len(plan.result[0]) == 1
    assert plan.reviewed_source is clasificacion.reviewed_source


def test_un_hueco_candidato_no_autoriza_vano_ni_cerrar_su_interrupcion(plugin, tmp_path):
    sesion, ruta, datos, caras, eje, candidato = crear_entrada(plugin, tmp_path, con_hueco=True)
    planes, clasificacion, plan = analizar(sesion, ruta)
    assert not plan.result[1]
    assert not plan.curved_openings
    assert candidato not in plan.sources
    assert not plan.result[0]
    assert not plan.sources


def test_puerta_confirmada_se_propone_como_puerta(plugin, tmp_path):
    sesion, ruta, datos, caras, eje, candidato = crear_entrada(plugin, tmp_path, con_hueco=True)
    espacio = sesion.document.doc.modelspace()
    giro = espacio.add_arc((2, .2), 1., 0, 90, dxfattribs={"layer": "REV-PUERTA"})
    hoja = espacio.add_line((2, .2), (2, 1.2), dxfattribs={"layer": "REV-PUERTA"})
    sesion.document.save_as(ruta.parent / datos["dxf"]["name"])
    entrada = module(sesion, "entrada_revisada")
    datos["dxf"]["sha256"] = entrada.hash_archivo(ruta.parent / datos["dxf"]["name"])
    datos["layers"]["REV-PUERTA"]["state"] = "confirmado"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    planes, clasificacion, plan = analizar(sesion, ruta)
    assert len(plan.result[0]) == 1
    assert len(plan.result[1]) == 1
    assert plan.result[1][0][3] == "door"


RECHAZOS = [
    "esquema_ausente", "esquema_desconocido", "unidades_distintas", "escala_sin_comprobar",
    "escala_ausente", "escala_como_texto", "escala_como_numero", "revision_ausente",
    "revision_no_terminada", "fecha_ausente", "fecha_formato_incorrecto", "fecha_imposible",
    "revisor_invalido", "original_ausente", "nombre_original_vacio", "hash_original_invalido",
    "dxf_ausente", "nombre_dxf_invalido", "hash_dxf_invalido", "hash_dxf_distinto",
    "extension_dxf_incorrecta", "ruta_dxf_no_permitida", "nombre_procedencia_incorrecto",
    "capas_ausentes", "capas_como_lista", "capa_rev_sin_describir", "capa_no_rev",
    "capa_inexistente", "capa_como_texto", "papel_desconocido", "estado_capa_desconocido",
    "papel_no_textual", "capa_duplicada_sin_distinguir_mayusculas", "entidades_como_lista",
    "handle_inexistente", "estado_entidad_desconocido", "excepcion_con_papel", "json_duplicado",
    "json_invalido", "json_demasiado_grande", "plan_externo", "dxf_borrado", "dxf_modificado",
    "dibujo_distinto", "unidades_dxf_incompatibles", "otro_dxf_con_igual_geometria",
]


@pytest.mark.parametrize("motivo", RECHAZOS)
def test_cada_rechazo_impide_activar_el_modo(plugin, tmp_path, motivo):
    sesion, ruta, datos, caras, eje, candidato = crear_entrada(plugin, tmp_path)
    fuente = ruta.parent / datos["dxf"]["name"]
    entrada = module(sesion, "entrada_revisada")
    match motivo:
        case "esquema_ausente":
            del datos["schema"]
        case "esquema_desconocido":
            datos["schema"] = "otro/v1"
        case "unidades_distintas":
            datos["units"] = "mm"
        case "escala_sin_comprobar":
            datos["scale_checked"] = False
        case "escala_ausente":
            del datos["scale_checked"]
        case "escala_como_texto":
            datos["scale_checked"] = "sí"
        case "escala_como_numero":
            datos["scale_checked"] = 1
        case "revision_ausente":
            del datos["review"]
        case "revision_no_terminada":
            datos["review"]["state"] = "pendiente"
        case "fecha_ausente":
            del datos["review"]["date"]
        case "fecha_formato_incorrecto":
            datos["review"]["date"] = "18-11-2026"
        case "fecha_imposible":
            datos["review"]["date"] = "2026-02-30"
        case "revisor_invalido":
            datos["review"]["reviewer"] = []
        case "original_ausente":
            del datos["source"]
        case "nombre_original_vacio":
            datos["source"]["name"] = ""
        case "hash_original_invalido":
            datos["source"]["sha256"] = "sin hash"
        case "dxf_ausente":
            del datos["dxf"]
        case "nombre_dxf_invalido":
            datos["dxf"]["name"] = ""
        case "hash_dxf_invalido":
            datos["dxf"]["sha256"] = "sin hash"
        case "hash_dxf_distinto":
            datos["dxf"]["sha256"] = "0" * 64
        case "extension_dxf_incorrecta":
            datos["dxf"]["name"] = "entrada.pdf"
        case "ruta_dxf_no_permitida":
            datos["dxf"]["name"] = "../entrada.dxf"
        case "nombre_procedencia_incorrecto":
            ruta = ruta.with_name("otro.procedencia.json")
        case "capas_ausentes":
            del datos["layers"]
        case "capas_como_lista":
            datos["layers"] = []
        case "capa_rev_sin_describir":
            del datos["layers"]["REV-MURO-EJE"]
        case "capa_no_rev":
            datos["layers"]["Muros"] = {"role": "muro-cara", "state": "confirmado"}
        case "capa_inexistente":
            datos["layers"]["REV-OTRA"] = {"role": "muro-cara", "state": "confirmado"}
        case "capa_como_texto":
            datos["layers"]["REV-MURO-CARA"] = "confirmado"
        case "papel_desconocido":
            datos["layers"]["REV-MURO-CARA"]["role"] = "eje"
        case "estado_capa_desconocido":
            datos["layers"]["REV-MURO-CARA"]["state"] = "aceptado"
        case "papel_no_textual":
            datos["layers"]["REV-MURO-CARA"]["role"] = []
        case "capa_duplicada_sin_distinguir_mayusculas":
            datos["layers"]["rev-muro-cara"] = datos["layers"]["REV-MURO-CARA"]
        case "entidades_como_lista":
            datos["entities"] = []
        case "handle_inexistente":
            datos["entities"] = {"FFFF": {"state": "confirmado"}}
        case "estado_entidad_desconocido":
            datos["entities"] = {caras[0].dxf.handle: {"state": "aceptado"}}
        case "excepcion_con_papel":
            datos["entities"] = {eje.dxf.handle: {"state": "confirmado", "role": "muro-cara"}}
        case "plan_externo":
            datos["plan"] = {"walls": [[0, 0, 100, 100]]}
        case "dxf_borrado":
            fuente.unlink()
        case "dxf_modificado":
            fuente.write_bytes(fuente.read_bytes() + b"\n")
        case "dibujo_distinto":
            caras[0].dxf.end = (7, 0)
        case "otro_dxf_con_igual_geometria":
            sesion.document.doc.filename = str(tmp_path / "otro.dxf")
        case "unidades_dxf_incompatibles":
            sesion.document.doc.header["$INSUNITS"] = 4
            sesion.document.save_as(fuente)
            datos["dxf"]["sha256"] = entrada.hash_archivo(fuente)
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    if motivo == "json_duplicado":
        ruta.write_text('{"schema":"arq.entrada-revisada/v1","schema":"otro"}', encoding="utf-8")
    elif motivo == "json_invalido":
        ruta.write_text("{sin cerrar", encoding="utf-8")
    elif motivo == "json_demasiado_grande":
        ruta.write_bytes(b" " * (4 * 1024 * 1024 + 1))
    with pytest.raises(ValueError):
        entrada.cargar_procedencia(ruta, sesion.document.doc)
    assert not sesion.walls()


@pytest.mark.parametrize("estado", ["pendiente", "rechazado", "candidato"])
def test_estado_por_entidad_prevalece_sobre_capa_confirmada(plugin, tmp_path, estado):
    sesion, ruta, datos, caras, eje, candidato = crear_entrada(plugin, tmp_path)
    datos["entities"] = {cara.dxf.handle: {"state": estado} for cara in caras}
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    planes, clasificacion, plan = analizar(sesion, ruta)
    assert not plan.result[0]
    assert all(clasificacion.role(cara) is None for cara in caras)


def test_entidades_confirmadas_prevalecen_sobre_capa_pendiente(plugin, tmp_path):
    sesion, ruta, datos, caras, eje, candidato = crear_entrada(plugin, tmp_path)
    datos["layers"]["REV-MURO-CARA"]["state"] = "pendiente"
    datos["entities"] = {cara.dxf.handle: {"state": "confirmado"} for cara in caras}
    datos["entities"][eje.dxf.handle] = {"state": "confirmado"}
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    planes, clasificacion, plan = analizar(sesion, ruta)
    assert len(plan.result[0]) == 1
    assert clasificacion.role(eje) is None


@pytest.mark.parametrize("esquema", [None, "desconocido"])
def test_procedencia_invalida_mantiene_conversion_normal_y_excluye_rev(plugin, tmp_path, esquema):
    sesion, ruta, datos, caras, eje, candidato = crear_entrada(plugin, tmp_path)
    dibujo = sesion.document.doc
    dibujo.layers.add("Muros normales")
    for altura in [3, 3.2]:
        dibujo.modelspace().add_line((0, altura), (6, altura), dxfattribs={"layer": "Muros normales"})
    sesion.document.save_as(ruta.parent / datos["dxf"]["name"])
    if esquema is None:
        del datos["schema"]
    else:
        datos["schema"] = esquema
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    herramienta = sesion.tool("LINEASAMURO")
    assert herramienta.classification is None
    herramienta._convert((-1, -1), (7, 4))
    assert len(sesion.walls()) == 1
    registro = sesion.meta(next(iter(sesion.walls().values())))
    assert registro["a"][1] == pytest.approx(3.1)
    assert all(cara.dxf.layer == "REV-MURO-CARA" for cara in caras)


def test_una_sola_cara_pendiente_no_se_empareja_con_el_eje(plugin, tmp_path):
    sesion, ruta, datos, caras, eje, candidato = crear_entrada(plugin, tmp_path)
    datos["entities"] = {caras[0].dxf.handle: {"state": "pendiente"}}
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    planes, clasificacion, plan = analizar(sesion, ruta)
    assert not plan.result[0]
    assert clasificacion.role(caras[1]) == "muros"
    assert clasificacion.role(eje) is None


def test_hueco_generico_confirmado_no_se_convierte_en_puerta_o_ventana(plugin, tmp_path):
    sesion, ruta, datos, caras, eje, candidato = crear_entrada(plugin, tmp_path)
    datos["layers"]["REV-HUECO-CANDIDATO"]["state"] = "confirmado"
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    planes, clasificacion, plan = analizar(sesion, ruta)
    assert clasificacion.role(candidato) is None
    assert not plan.result[1]


def test_ventana_confirmada_se_propone_y_crea_como_ventana(plugin, tmp_path):
    sesion, ruta, datos, caras, eje, candidato = crear_entrada(plugin, tmp_path, con_hueco=True)
    dibujo = sesion.document.doc
    dibujo.layers.add("REV-VENTANA")
    for altura in [.04, .08, .12]:
        dibujo.modelspace().add_line((2, altura), (3, altura), dxfattribs={"layer": "REV-VENTANA"})
    for posicion in [2, 3]:
        dibujo.modelspace().add_line((posicion, .04), (posicion, .12), dxfattribs={"layer": "REV-VENTANA"})
    datos["layers"]["REV-VENTANA"] = {"role": "ventana", "state": "confirmado"}
    fuente = ruta.parent / datos["dxf"]["name"]
    sesion.document.save_as(fuente)
    datos["dxf"]["sha256"] = module(sesion, "entrada_revisada").hash_archivo(fuente)
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    planes, clasificacion, plan = analizar(sesion, ruta)
    assert len(plan.result[0]) == 1
    assert len(plan.result[1]) == 1
    assert plan.result[1][0][3] == "window"
    planes.commit(sesion.tool("LINEASAMURO").ctx, plan)
    carpinterias = [sesion.meta(entidad) for entidad in dibujo.modelspace() if (sesion.meta(entidad) or {}).get("kind") == "opening"]
    assert len(carpinterias) == 1
    assert carpinterias[0]["type"] == "window"


def test_dxf_del_laboratorio_reabierto_por_ingecad_conserva_su_revision(plugin, tmp_path):
    import hashlib
    import ezdxf
    from core.document import Document
    sesion = Session(plugin)
    dibujo = ezdxf.new()
    dibujo.layers.add("REV-CARAS")
    for altura in [0, .2]:
        dibujo.modelspace().add_line((0, altura), (6, altura), dxfattribs={"layer": "REV-CARAS"})
    fuente = tmp_path / "laboratorio.dxf"
    dibujo.saveas(fuente)
    datos = {
        "schema": "arq.entrada-revisada/v1",
        "dxf": {"name": fuente.name, "sha256": hashlib.sha256(fuente.read_bytes()).hexdigest()},
        "source": {"name": "croquis-no-presente.pdf", "sha256": "a" * 64},
        "units": "m",
        "scale_checked": True,
        "review": {"state": "revisado", "date": "2026-11-18"},
        "layers": {"REV-CARAS": {"role": "muro-cara", "state": "confirmado"}},
    }
    ruta = Path(str(fuente) + ".procedencia.json")
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    documento = Document.load(fuente)
    entrada = module(sesion, "entrada_revisada")
    planes = module(sesion, "conversion_plan")
    revision = entrada.cargar_procedencia(ruta, documento.doc)
    plan = planes.analyse(documento.doc, (-1, -1), (7, 2), planes.Classification(reviewed_source=revision))
    assert len(plan.result[0]) == 1


def test_fuente_original_es_informativa_incluso_si_hay_un_archivo_distinto(plugin, tmp_path):
    sesion, ruta, datos, caras, eje, candidato = crear_entrada(plugin, tmp_path)
    original = ruta.parent / datos["source"]["name"]
    original.write_bytes(b"Contenido local distinto: no se debe verificar ni importar")
    planes, clasificacion, plan = analizar(sesion, ruta)
    assert len(plan.result[0]) == 1


def test_bloque_no_permite_colar_capas_rev_sin_procedencia(plugin):
    sesion = Session(plugin)
    dibujo = sesion.document.doc
    dibujo.layers.add("REV-MURO-CARA")
    bloque = dibujo.blocks.new("GEOMETRIA_SINTETICA")
    for altura in [0, .2]:
        bloque.add_line((0, altura), (6, altura), dxfattribs={"layer": "REV-MURO-CARA"})
    referencia = dibujo.modelspace().add_blockref("GEOMETRIA_SINTETICA", (0, 0))
    planes = module(sesion, "conversion_plan")
    lector = module(sesion, "convert_tools")
    clasificacion = planes.Classification(handles={referencia.dxf.handle: "muros"})
    plan = planes.analyse(dibujo, (-1, -1), (7, 2), clasificacion)
    assert not plan.result[0]
    assert not lector.collect(dibujo, (-1, -1), (7, 2))[0]


def test_contorno_confirmado_solo_se_oculta_si_esta_representado(plugin, tmp_path):
    sesion, ruta, datos, caras, eje, candidato = crear_entrada(plugin, tmp_path)
    dibujo = sesion.document.doc
    contorno = dibujo.modelspace().add_hatch(dxfattribs={"layer": "REV-MURO-CARA"})
    contorno.paths.add_polyline_path([(8, 1), (12, 1), (12, 1.2), (8, 1.2)], is_closed=True)
    fuente = ruta.parent / datos["dxf"]["name"]
    sesion.document.save_as(fuente)
    entrada = module(sesion, "entrada_revisada")
    datos["dxf"]["sha256"] = entrada.hash_archivo(fuente)
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    revision = entrada.cargar_procedencia(ruta, dibujo)
    planes = module(sesion, "conversion_plan")
    plan = planes.analyse(dibujo, (-1, -1), (13, 2), planes.Classification(reviewed_source=revision))
    assert len(plan.result[0]) == 2
    assert contorno in plan.sources
    planes.commit(sesion.tool("LINEASAMURO").ctx, plan)
    assert len(sesion.walls()) == 2
    assert contorno.dxf.layer == "ARQ-PLANO-ORIGEN"
    sesion.history.undo()
    assert contorno.dxf.layer == "REV-MURO-CARA"

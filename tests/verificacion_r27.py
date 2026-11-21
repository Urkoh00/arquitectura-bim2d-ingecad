# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: compara datos BIM, geometría y persistencia real durante el repaso de órdenes.
import json
from pathlib import Path


def datos_bim(spec, documento):
    from tests.escenarios_r27 import modulo

    arquitectura = modulo(spec, "architectural")
    parametros = modulo(spec, "parameters_arq")
    niveles = modulo(spec, "levels")
    registros = [
        arquitectura.metadata(e) for e in documento.doc.modelspace() if arquitectura.metadata(e)
    ]
    return {
        "registros": sorted(registros, key=lambda r: json.dumps(r, sort_keys=True)),
        "parametros": parametros.load_defaults(documento),
        "niveles": niveles.load(documento),
    }


def estado(spec, documento):
    from ezdxf.lldxf.tagwriter import TagCollector

    entidades = []
    for entidad in documento.doc.modelspace():
        # Los manejadores son enlaces DXF internos; la identidad BIM se comprueba
        # por separado y no se sustituye por el manejador de una copia regenerada.
        etiquetas = []
        for tag in TagCollector.dxftags(entidad):
            if tag.code in (5, 330):
                continue
            if tag.code == 60 and tag.value == 0:
                # DXF permite omitir el valor por defecto de visibilidad.
                continue
            valor = str(tag.value)
            if entidad.dxftype() == "DIMENSION" and tag.code == 2 and valor.startswith("*D"):
                # Rehacer puede asignar otro nombre al bloque gráfico anónimo.
                # Se compara su contenido, no se omite la representación de la cota.
                bloque = documento.doc.blocks[valor]
                contenido = []
                for pieza in bloque:
                    contenido.append(
                        [
                            (dato.code, str(dato.value))
                            for dato in TagCollector.dxftags(pieza)
                            if dato.code not in (5, 330)
                            and not (dato.code == 60 and dato.value == 0)
                        ]
                    )
                valor = json.dumps(contenido)
            etiquetas.append((tag.code, valor))
        entidades.append(json.dumps(etiquetas))
    return {"bim": datos_bim(spec, documento), "entidades": sorted(entidades)}


def contenido_memoria(spec, documento):
    from tests.escenarios_r27 import modulo
    import unicodedata

    arquitectura = modulo(spec, "architectural")
    textos = []
    cotas = []
    for entidad in documento.doc.modelspace():
        datos = arquitectura.metadata(entidad) or {}
        if datos.get("kind") != "carpentry_schedule_detail":
            continue
        if entidad.dxftype() in ("TEXT", "MTEXT"):
            textos.append(unicodedata.normalize("NFC", entidad.plain_text()).replace("\r\n", "\n"))
        elif entidad.dxftype() == "DIMENSION":
            cotas.append(float(entidad.get_measurement()))
    return sorted(textos), sorted(cotas)


def persistencia(spec, documento, destino):
    from core.document import Document
    from formats.dwg_bridge import load_dwg
    from ingetrazo_ext.arquitectura_bim import validate_contract
    from tests.escenarios_r27 import modulo

    esperado = datos_bim(spec, documento)
    textos, cotas = contenido_memoria(spec, documento)
    resultados = []
    for extension in ("dxf", "dwg"):
        ruta = Path(destino) / ("modelo." + extension)
        motor, avisos = documento.save_as(ruta)
        recuperado = load_dwg(ruta) if extension == "dwg" else Document.load(ruta)
        iguales = datos_bim(spec, recuperado) == esperado
        contrato = modulo(spec, "exchange").build(recuperado.doc)
        validate_contract(contrato)
        textos_reabiertos, cotas_reabiertas = contenido_memoria(spec, recuperado)
        pruebas_memoria = {}
        if textos:
            pruebas_memoria = {
                "memoria_textos_iguales": textos_reabiertos == textos,
                "memoria_cotas_iguales": len(cotas_reabiertas) == len(cotas)
                and all(abs(a - b) <= 1e-7 for a, b in zip(cotas, cotas_reabiertas)),
            }
        resultados.append(
            {
                "formato": extension,
                "motor": motor,
                "avisos": avisos,
                "datos_bim_iguales": iguales,
                "contrato_valido": True,
                **pruebas_memoria,
            }
        )
    return resultados

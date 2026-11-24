# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: mide las carpinterías con openings y asigna marcas estables por igualdad física.
from copy import deepcopy
import math
import re

from . import openings
from .geom.soldadura import TOLERANCIA

PREFIJOS = {"door": "P", "window": "V", "gap": "H"}


def iguales(primera, segunda, tolerancia=TOLERANCIA):
    """La tolerancia compara medidas; nunca se redondean claves geométricas."""
    if isinstance(primera, dict) and isinstance(segunda, dict):
        return primera.keys() == segunda.keys() and all(
            iguales(primera[clave], segunda[clave], tolerancia) for clave in primera
        )
    if isinstance(primera, (list, tuple)) and isinstance(segunda, (list, tuple)):
        return len(primera) == len(segunda) and all(
            iguales(a, b, tolerancia) for a, b in zip(primera, segunda)
        )
    if isinstance(primera, bool) or isinstance(segunda, bool):
        return primera == segunda
    if isinstance(primera, (int, float)) and isinstance(segunda, (int, float)):
        return (
            math.isfinite(primera)
            and math.isfinite(segunda)
            and abs(primera - segunda) <= tolerancia
        )
    return primera == segunda


def prefijo(registro):
    return "A" if registro.get("cabinet") else PREFIJOS[registro["type"]]


def validar_marca(marca, letra):
    marca = str(marca).strip().upper()
    if marca and not re.fullmatch(letra + r"[1-9][0-9]*", marca):
        raise ValueError(f"La marca debe ser {letra} y un número entero positivo")
    return marca


def medir(muro, registro):
    """Medidas y plantillas del mismo generador utilizado por las piezas 3D."""
    registro = openings.normalise(registro)
    partes = openings.carpentry_parts(muro, registro, 0.0)
    plantillas = [deepcopy(parte.get("unrolled", parte)) for parte in partes]
    plano, trasladado = openings.proxy(muro, registro)
    fondo_inicial, fondo_final = openings.frame_band(plano, trasladado)
    ancho = openings.measure_of(muro, registro["width"], registro, registro["side"])
    if registro.get("curve_mode") != "curva":
        inicio, final, _, _, base, coronacion = openings.filling_box(muro, registro, 0.0)
        ancho = final - inicio
    else:
        base = float(registro["sill"])
        coronacion = base + float(registro["height"])
    limites_hojas = {}
    for parte in plantillas:
        if parte["role"] != "leaf":
            continue
        if "box" in parte:
            inicio, final = parte["box"][:2]
        else:
            contorno = parte["prism"][0]
            inicio = min(p[0] for p in contorno)
            final = max(p[0] for p in contorno)
        anterior = limites_hojas.get(parte["name"], (inicio, final))
        limites_hojas[parte["name"]] = (min(inicio, anterior[0]), max(final, anterior[1]))
    factor = ancho / float(registro["width"]) if registro.get("curve_mode") == "curva" else 1.0
    return {
        "origen_s": float(trasladado["offset"]),
        "factor_s": factor,
        "ancho": ancho,
        "alto": coronacion - base,
        "hojas": [(final - inicio) * factor for inicio, final in limites_hojas.values()],
        "limites_hojas": [
            [
                (inicio - float(trasladado["offset"])) * factor,
                (final - float(trasladado["offset"])) * factor,
            ]
            for inicio, final in limites_hojas.values()
        ],
        "antepecho": base,
        "fondo_cerco": 0.0 if registro["type"] == "gap" else fondo_final - fondo_inicial,
        "plantillas": plantillas,
        "registro": registro,
    }


def definir(muro, registro):
    medidas = medir(muro, registro)
    registro = medidas["registro"]
    campos = (
        "type",
        "type_name",
        "material",
        "leaves",
        "leaf",
        "leaf2",
        "operation",
        "frame_width",
        "leaf_thickness",
        "sill_kind",
        "curve_mode",
    )
    definicion = {clave: registro.get(clave, "") for clave in campos}
    definicion.update(
        {
            "prefijo": prefijo(registro),
            "ancho": medidas["ancho"],
            "alto": medidas["alto"],
            "antepecho": medidas["antepecho"],
            "fondo_cerco": medidas["fondo_cerco"],
            "hojas_reales": medidas["hojas"],
            "materiales": {
                papel: openings.part_material(registro, papel)
                for papel in ("frame", "leaf", "glass", "sill")
            },
        }
    )
    if registro["leaves"] == 2:
        definicion["main_leaf"] = registro["main_leaf"]
    if registro["curve_mode"] == "curva":
        # Dos arcos de igual desarrollo y distinto radio no son la misma pieza.
        definicion["radio"] = muro.r
        definicion["referencia_ancho"] = registro["width_reference"]
    return definicion


def unidades(muro, registro):
    """Un armario aporta frentes reales; su cuerpo no se cuenta como una puerta."""
    if registro.get("cabinet"):
        from .cabinets import fronts

        for indice, frente in enumerate(fronts(muro, openings.normalise(registro))):
            yield {
                "origen": registro["id"],
                "indice": indice,
                "prefijo": "A",
                "definicion": {**definir(muro, frente), "prefijo": "A"},
                "medidas": medir(muro, frente),
                "registro": frente,
                "marca_solicitada": registro.get("mark", ""),
                "solicitud_manual": registro.get("mark_manual", False),
            }
    else:
        yield {
            "origen": registro["id"],
            "indice": 0,
            "prefijo": prefijo(registro),
            "definicion": definir(muro, registro),
            "medidas": medir(muro, registro),
            "registro": openings.normalise(registro),
            "marca_solicitada": registro.get("mark", ""),
            "solicitud_manual": registro.get("mark_manual", False),
        }


def coincide_tipo_anterior(anterior, actual):
    # En v1.47 no se distinguía la hoja activa: la primera de las nuevas
    # agrupaciones conserva la marca, y las demás reciben números nuevos.
    if "main_leaf" not in anterior and "main_leaf" in actual:
        actual = {clave: valor for clave, valor in actual.items() if clave != "main_leaf"}
    return iguales(anterior, actual)


def asignar_marcas(piezas, catalogo=None):
    """Devuelve grupos y catálogo sin modificar la entrada ni reutilizar marcas retiradas."""
    catalogo = deepcopy(catalogo or {"version": 1, "tipos": [], "siguientes": {}})
    anteriores = catalogo["tipos"]
    siguientes = {letra: int(catalogo.get("siguientes", {}).get(letra, 1)) for letra in "PVHA"}
    for tipo in anteriores:
        letra = tipo["definicion"]["prefijo"]
        marca = validar_marca(tipo["marca"], letra)
        siguientes[letra] = max(siguientes[letra], int(marca[1:]) + 1)
    grupos = []
    for pieza in sorted(piezas, key=lambda p: (p["origen"], p["indice"])):
        candidato = next(
            (
                grupo
                for grupo in grupos
                if all(
                    iguales(miembro["definicion"], pieza["definicion"])
                    for miembro in grupo["piezas"]
                )
            ),
            None,
        )
        if candidato is None:
            candidato = {"definicion": deepcopy(pieza["definicion"]), "piezas": []}
            grupos.append(candidato)
        candidato["piezas"].append(pieza)
    usadas = set()
    for grupo in grupos:
        solicitudes = {
            validar_marca(p["marca_solicitada"], p["prefijo"])
            for p in grupo["piezas"]
            if p.get("solicitud_manual") and p.get("marca_solicitada")
        }
        if len(solicitudes) > 1:
            raise ValueError("Hay marcas manuales distintas para piezas iguales")
        if solicitudes:
            marca = solicitudes.pop()
            antiguo = next((t for t in anteriores if t["marca"] == marca), None)
            if marca in usadas or (
                antiguo is not None and not coincide_tipo_anterior(antiguo["definicion"], grupo["definicion"])
            ):
                raise ValueError("La marca solicitada ya identifica otra pieza")
            grupo["marca"] = marca
            usadas.add(marca)
            letra = marca[0]
            siguientes[letra] = max(siguientes[letra], int(marca[1:]) + 1)
    for grupo in grupos:
        if "marca" in grupo:
            continue
        anterior = next(
            (
                tipo
                for tipo in anteriores
                if tipo["marca"] not in usadas
                and all(
                    coincide_tipo_anterior(tipo["definicion"], pieza["definicion"]) for pieza in grupo["piezas"]
                )
            ),
            None,
        )
        if anterior is not None:
            grupo["marca"] = anterior["marca"]
            usadas.add(grupo["marca"])
    for grupo in grupos:
        if "marca" not in grupo:
            letra = grupo["definicion"]["prefijo"]
            grupo["marca"] = letra + str(siguientes[letra])
            siguientes[letra] += 1
        grupo["piezas"] = deepcopy(grupo["piezas"])
    tipos = [{"marca": g["marca"], "definicion": deepcopy(g["definicion"])} for g in grupos]
    return grupos, {"version": 1, "tipos": tipos, "siguientes": siguientes}


def renombrar(catalogo, marca, nueva):
    catalogo = deepcopy(catalogo)
    tipo = next((tipo for tipo in catalogo["tipos"] if tipo["marca"] == marca), None)
    if tipo is None:
        raise ValueError("Marca inexistente en el catálogo de carpinterías")
    nueva = validar_marca(nueva, tipo["definicion"]["prefijo"])
    if not nueva:
        raise ValueError("Una marca asignada no puede quedar vacía")
    if any(t["marca"] == nueva and t is not tipo for t in catalogo["tipos"]):
        raise ValueError("Esa marca ya identifica otra pieza")
    tipo["marca"] = nueva
    letra = nueva[0]
    catalogo["siguientes"][letra] = max(catalogo["siguientes"].get(letra, 1), int(nueva[1:]) + 1)
    return catalogo

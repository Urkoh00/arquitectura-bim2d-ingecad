# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: campos de las fichas de creación para responderlos por la línea de órdenes.
from copy import deepcopy

from .linea_campos import Campo

CREACION = {
    "MURO": "muro",
    "PILAR": "pilar",
    "PILARESENEJES": "pilar",
    "CARPINTERIA": "carpinteria",
    "PUERTAARQ": "carpinteria",
    "VENTANAARQ": "carpinteria",
    "HUECOARQ": "carpinteria",
    "ARMARIOBIM": "armario",
    "FORJADO": "forjado",
    "RECINTO": "recinto",
    "EJES": "rejilla",
    "REJILLA": "rejilla",
}


def medida(clave, titulo, minimo=0.001, maximo=100000.0, cuando=None):
    return Campo(clave, titulo, "numero", minimo=minimo, maximo=maximo, cuando=cuando)


def opcion(clave, titulo, valores, cuando=None):
    opciones = valores if callable(valores) else tuple(valores)
    return Campo(clave, titulo, "opcion", opciones, cuando=cuando)


def texto(clave, titulo, cuando=None):
    return Campo(clave, titulo, cuando=cuando)


def identidad():
    return [texto("name", "Nombre"), texto("type_name", "Tipo BIM"), texto("material", "Material")]


def campos_muro(ctx, datos):
    from .parameters_arq import load_defaults, find_wall_type
    from .compat import require_document
    from .levels import load
    from .wall_categories import CATEGORIES

    tipos = load_defaults(require_document(ctx))["wall_types"]
    catalogo = load(require_document(ctx))
    niveles = [(nivel["name"], nivel["id"]) for nivel in catalogo["levels"]]
    actual = next((tipo for tipo in tipos if tipo["name"] == datos.get("type_name")), None)
    datos["_tipo_elegido"] = actual["name"] if actual else None
    datos.setdefault("cara_exterior", "auto")
    datos.setdefault("height_constraint", "fixed")
    datos.setdefault("level_id", catalogo["active"])
    superiores = [
        nivel for nivel in catalogo["levels"] if nivel["elevation"] > datos.get("base", 0)
    ]
    datos.setdefault("top_level_id", superiores[0]["id"] if superiores else catalogo["active"])
    datos.setdefault("base_offset", datos.get("level_offset", 0.0))
    datos.setdefault("top_offset", 0.0)
    datos.setdefault(
        "_espesor_manual", bool(actual and abs(actual["thickness"] - datos["thickness"]) > 5e-7)
    )
    datos.setdefault("_resolucion", "restore")
    fija = lambda valores: valores["height_constraint"] == "fixed"
    ligada = lambda valores: not fija(valores)
    con_tipo = lambda valores: valores.get("_tipo_elegido") is not None
    manual = lambda valores: con_tipo(valores) and valores["_espesor_manual"]
    campos = [
        opcion(
            "_tipo_elegido",
            "Tipo del catálogo",
            [("Genérico", None)] + [(t["name"], t["name"]) for t in tipos],
        ),
        opcion("wall_category", "Categoría", CATEGORIES),
        Campo("_espesor_manual", "Modificar espesor del tipo", "logico", cuando=con_tipo),
        medida("thickness", "Espesor total (m)", cuando=lambda v: not con_tipo(v) or manual(v)),
        opcion(
            "_resolucion",
            "Resolver discrepancia con el tipo",
            [("Restaurar", "restore"), ("Variante local", "variant"), ("Desvincular", "detach")],
            manual,
        ),
        opcion("height_constraint", "Altura", [("Fija", "fixed"), ("Entre niveles", "level")]),
        medida("height", "Altura fija (m)", cuando=fija),
        medida("base", "Cota base (m)", -100000.0, cuando=fija),
        opcion("level_id", "Nivel base", niveles, ligada),
        medida("base_offset", "Desfase de base (m)", -100000.0, cuando=ligada),
        opcion("top_level_id", "Nivel superior", niveles, ligada),
        medida("top_offset", "Desfase superior (m)", -100000.0, cuando=ligada),
        opcion(
            "reference",
            "Referencia de dibujo",
            [("Eje", "eje"), ("Izquierda", "izquierda"), ("Derecha", "derecha")],
        ),
        opcion("cara_exterior", "Cara exterior", [
            ("Automática", "auto"), ("Izquierda", "izquierda"), ("Derecha", "derecha")
        ]),
        texto("name", "Nombre"),
        texto("material", "Material principal"),
    ]

    def cambiar(clave, valor, valores):
        if clave == "_espesor_manual" and not valor and valores.get("_tipo_elegido"):
            valores["thickness"] = find_wall_type(tipos, valores["_tipo_elegido"])["thickness"]
        if clave != "_tipo_elegido" or valor is None:
            return
        tipo = find_wall_type(tipos, valor)
        valores["thickness"] = tipo["thickness"]
        valores["wall_category"] = tipo["wall_category"]
        valores["_espesor_manual"] = False
        if tipo.get("material"):
            valores["material"] = tipo["material"]
        if valores.get("name") in ("", "Muro") or any(
            t["name"] == valores.get("name") for t in tipos
        ):
            valores["name"] = tipo["name"]

    return campos, cambiar


def normalizar_muro(ctx, datos, tipos=None, catalogo=None):
    from .parameters_arq import load_defaults, normalise_type, _num
    from .compat import require_document
    from .wall_constraints import resolve
    from .levels import load
    from .wall_categories import category

    if tipos is None:
        tipos = load_defaults(require_document(ctx))["wall_types"]
    tipo = next((t for t in tipos if t["name"] == datos.get("_tipo_elegido")), None)
    salida = {clave: deepcopy(valor) for clave, valor in datos.items() if not clave.startswith("_")}
    salida["wall_category"] = category(salida)
    if salida.get("height_constraint") == "level":
        if catalogo is None:
            catalogo = load(require_document(ctx))
        salida = resolve(salida, catalogo)
    else:
        for clave in ("level_id", "top_level_id", "top_offset", "base_offset"):
            salida.pop(clave, None)
    if tipo:
        if "orden_capas" in tipo:
            salida["orden_capas"] = tipo["orden_capas"]
        else:
            salida.pop("orden_capas", None)
        diferente = abs(salida["thickness"] - tipo["thickness"]) > 5e-7
        if diferente and datos["_resolucion"] == "detach":
            salida.update(type_name=f"Muro {_num(salida['thickness'])}", layers=[])
        elif diferente and datos["_resolucion"] == "variant":
            factor = salida["thickness"] / tipo["thickness"]
            variante = normalise_type(
                {
                    "name": tipo["name"] + " (" + _num(salida["thickness"]) + " m, variante local)",
                    "layers": [
                        [espesor * factor, material] for espesor, material in tipo["layers"]
                    ],
                }
            )
            salida.update(
                thickness=variante["thickness"],
                type_name=variante["name"],
                layers=variante["layers"],
            )
        else:
            salida.update(
                thickness=tipo["thickness"], type_name=tipo["name"], layers=deepcopy(tipo["layers"])
            )
    else:
        actual = salida.get("type_name")
        conservar = actual and not any(t["name"] == actual for t in tipos)
        salida.update(
            type_name=str(actual) if conservar else f"Muro {_num(salida['thickness'])}",
            layers=deepcopy(salida.get("layers") or []) if conservar else [],
        )
    from .capas_envolvente import validar_orden_y_cara
    validar_orden_y_cara(salida)
    salida["name"] = str(salida.get("name") or "").strip() or "Muro"
    if salida["height"] <= 0 or salida["thickness"] <= 0:
        raise ValueError("Altura y espesor deben ser positivos")
    return salida


def campos_pilar(datos, enganche=True):
    datos.setdefault("profile", "HEB 160")
    datos.setdefault("cover", 0.0)
    datos.setdefault("anchor", 5)
    es = lambda clase: lambda valores: valores["shape"] == clase
    campos = [
        opcion(
            "shape",
            "Sección",
            [
                ("Rectangular", "rect"),
                ("Circular", "circ"),
                ("Hexagonal", "hex"),
                ("Octogonal", "oct"),
                ("Metálica", "steel"),
            ],
        ),
        medida("width", "Anchura (m)", cuando=es("rect")),
        medida("depth", "Fondo (m)", cuando=es("rect")),
        medida(
            "radius",
            "Radio circunscrito (m)",
            cuando=lambda v: v["shape"] in ("circ", "hex", "oct"),
        ),
        texto("profile", "Perfil metálico", es("steel")),
        medida("cover", "Recubrimiento (m)", 0.0, 1.0),
        Campo("rotation", "Rotación (grados)", "angulo", minimo=-360.0, maximo=360.0),
        medida("height", "Altura (m)"),
        medida("base", "Cota base (m)", -100000.0),
        *identidad(),
        texto("level", "Nivel descriptivo"),
    ]
    if enganche:
        campos.append(Campo("anchor", "Enganche (1–9)", "entero", minimo=1, maximo=9))
    return campos


def normalizar_pilar(datos):
    salida = deepcopy(datos)
    salida["name"] = str(salida.get("name") or "").strip() or "Pilar"
    salida["type_name"] = str(salida.get("type_name") or "").strip() or "Pilar genérico"
    if salida["shape"] == "steel":
        from .sections import parse_section

        perfil = parse_section(salida["profile"])
        if perfil.get("shape") != "steel":
            raise ValueError("Indique un perfil metálico válido")
        salida["profile"] = perfil["profile"]
        if salida.get("material") in ("", "Hormigón armado"):
            salida["material"] = perfil.get("material", "Acero")
    else:
        salida.pop("profile", None)
    from .sections import local_footprint

    local_footprint(salida)
    return salida


def campos_carpinteria(ctx, datos, editar=False):
    from . import openings as OP
    from .parameters_arq import load_defaults
    from .compat import require_document

    catalogo = [
        t for t in load_defaults(require_document(ctx))["opening_types"] if not t.get("cabinet")
    ]
    datos.update(OP.normalise(datos))
    datos.setdefault("_tipo_catalogo", None)
    datos.setdefault("leaf", 0.825)
    datos.setdefault("leaf2", 0.0)
    datos.setdefault("facet_sagitta", 0.005)
    datos.setdefault("setback", 0.0)
    datos.setdefault("setback_from", "exterior")
    datos.setdefault("curve_mode", "plana")
    datos.setdefault("width_reference", "cuerda")
    datos.setdefault("sill_kind", "alfeizar")
    for clave in ("name", "type_name", "material"):
        datos.setdefault(clave, "")
    for clave, papel in [
        ("frame_material", "frame"),
        ("leaf_material", "leaf"),
        ("glass_material", "glass"),
        ("sill_material", "sill"),
    ]:
        datos.setdefault(clave, OP.part_material(datos, papel))
    puerta = lambda v: v["type"] == "door"
    ventana = lambda v: v["type"] == "window"
    con_marco = lambda v: v["type"] != "gap"
    campos = [
        opcion(
            "_tipo_catalogo",
            "Tipo del dibujo",
            [("Parámetros actuales", None)] + [(t["name"], t["name"]) for t in catalogo],
        ),
        opcion("type", "Elemento", [("Puerta", "door"), ("Ventana", "window"), ("Vano", "gap")]),
        opcion("curve_mode", "Geometría", [("Plana", "plana"), ("Curva", "curva")]),
        opcion(
            "width_reference",
            "Referencia del ancho",
            [
                ("Cuerda", "cuerda"),
                ("Eje", "eje"),
                ("Interior", "interior"),
                ("Exterior", "exterior"),
            ],
        ),
        medida(
            "facet_sagitta", "Precisión de la curva (flecha máxima, m)", 0.0001, 0.02,
            cuando=lambda valores: valores["curve_mode"] == "curva",
        ),
        opcion(
            "operation",
            "Apertura",
            lambda v: [(OP.OPERATION_NAMES[k], k) for k in OP.OPERATIONS[v["type"]]],
            con_marco,
        ),
        opcion(
            "hinge",
            "Bisagra",
            [("Inicial", 0), ("Final", 1)],
            lambda v: not editar and ventana(v) and v["operation"] == "TILTANDTURN",
        ),
        Campo("leaves", "Número de hojas", "entero", minimo=1, maximo=6, cuando=con_marco),
        opcion("main_leaf", "Hoja principal vista desde el exterior", [("Izquierda", "left"), ("Derecha", "right")],
               lambda v: con_marco(v) and v["leaves"] == 2),
        medida("leaf", "Primera hoja desde el inicio del muro (m)", cuando=puerta),
        medida(
            "leaf2",
            "Segunda hoja, 0 = igual (m)",
            0.0,
            cuando=lambda v: puerta(v) and v["leaves"] == 2,
        ),
        medida(
            "width",
            "Ancho del hueco (m)",
            cuando=lambda v: not puerta(v) or v["curve_mode"] == "curva",
        ),
        medida("height", "Altura (m)"),
        medida("sill", "Antepecho (m)", 0.0),
        medida("handle_height", "Altura de manilla desde suelo, 0 = automática (m)", 0.0, 1000.0,
               lambda v: con_marco(v) and v["operation"] != "FIXED"),
        opcion(
            "handles_mode", "Hojas de puerta con manillas por las dos caras",
            [("Activa", "activa"), ("Ambas", "ambas")],
            lambda v: puerta(v) and v["operation"] == "SWINGING" and v["leaves"] == 2,
        ),
        Campo(
            "handles", "Manillas interiores en la hoja principal", "entero", minimo=1, maximo=2,
            cuando=lambda v: ventana(v) and v["operation"] not in ("FIXED", "SLIDING"),
        ),
        texto("handle_material", "Material de manilla", lambda v: con_marco(v) and v["operation"] != "FIXED"),
        opcion(
            "face",
            "Ajuste del cerco",
            [
                ("Interior", "interior"),
                ("Centrado", "centrada"),
                ("Exterior", "exterior"),
                ("Distancia", "distancia"),
            ],
            con_marco,
        ),
        medida("setback", "Distancia del cerco a la cara (m)", 0.0, 1000.0, con_marco),
        opcion(
            "setback_from",
            "Cara de referencia del cerco",
            [("Interior", "interior"), ("Exterior", "exterior")],
            con_marco,
        ),
        medida("frame_width", "Anchura del cerco (m)", 0.0, cuando=con_marco),
        medida("frame_depth", "Fondo del cerco, 0 = automático (m)", 0.0, cuando=con_marco),
        opcion(
            "sill_kind",
            "Remate",
            [("Alféizar", "alfeizar"), ("Vierteaguas", "vierteaguas"), ("Ventanal", "ventanal")],
            ventana,
        ),
        texto("frame_material", "Material del cerco", con_marco),
        texto("leaf_material", "Material de la hoja", con_marco),
        texto("glass_material", "Material del vidrio", ventana),
        texto("sill_material", "Material del remate", ventana),
        texto("mark", "Marca de memoria"),
        *identidad(),
    ]
    if editar:
        campos.extend(
            [
                medida("offset", "Desplazamiento sobre el muro (m)", 0.0),
                opcion("side", "Cara de apertura", [("Primera", 1), ("Opuesta", -1)]),
                opcion("hinge", "Bisagra", [("Inicial", 0), ("Final", 1)]),
            ]
        )

    def cambiar(clave, valor, valores):
        if clave == "_tipo_catalogo" and valor:
            elegido = next(t for t in catalogo if t["name"] == valor)
            copiables = (
                "height",
                "sill",
                "leaves",
                "main_leaf",
                "handle_height",
                "handle_material",
                "handles_mode",
                "handles",
                "leaf",
                "leaf2",
                "width",
                "frame_width",
                "frame_depth",
                "setback",
                "operation",
                "face",
                "sill_kind",
                "setback_from",
                "curve_mode",
                "width_reference",
                "frame_material",
                "leaf_material",
                "glass_material",
                "sill_material",
            )
            valores.update({k: deepcopy(v) for k, v in elegido["values"].items() if k in copiables})
            valores.update(type=elegido["type"], type_name=elegido["name"])
            valores["material"] = elegido["values"].get("material", "")
        if clave == "type" and valor != valores["type"]:
            valores["operation"] = OP.OPERATIONS[valor][0]
            valores["leaves"] = 1 if valor != "gap" else 0
        if clave == "leaves" and valores["type"] == "door" and valor not in (1, 2):
            raise ValueError("Una puerta admite una o dos hojas")

    return campos, cambiar


def normalizar_carpinteria(datos, validar=True):
    from . import openings as OP
    from .memoria_carpinteria import validar_marca, PREFIJOS

    salida = {k: deepcopy(v) for k, v in datos.items() if not k.startswith("_")}
    tipo = salida["type"]
    salida["mark"] = validar_marca(salida.get("mark", ""), PREFIJOS[tipo])
    if tipo == "door":
        if validar and salida["leaves"] not in (1, 2):
            raise ValueError("Una puerta admite una o dos hojas")
        salida["leaf2"] = salida.get("leaf2", 0.0) if salida["leaves"] == 2 else 0.0
        ancho = OP.door_width(
            salida["leaf"], salida["leaves"], salida["leaf2"], salida["frame_width"]
        )
        if salida.get("curve_mode") != "curva":
            salida["width"] = ancho
        salida["leaf2"] = salida["leaf2"] or (salida["leaf"] if salida["leaves"] == 2 else 0.0)
        for clave in ("sill_kind", "glass_material", "sill_material"):
            salida.pop(clave, None)
    else:
        salida.pop("leaf", None)
        salida.pop("leaf2", None)
    if tipo == "gap":
        salida.update(leaves=0, face="centrada", frame_width=0.0, frame_depth=0.0, operation="")
        for clave in (
            "sill_kind",
            "frame_material",
            "leaf_material",
            "glass_material",
            "sill_material",
        ):
            salida.pop(clave, None)
    problemas = OP.dimension_problems(salida) if validar else []
    if problemas:
        raise ValueError("; ".join(problemas))
    return salida


def campos_armario(datos):
    return [
        texto("mark", "Marca de los frentes"),
        opcion("cabinet_mode", "Modo", [("Adosado", "adosado"), ("Nicho", "nicho")]),
        texto("body_material", "Material del cuerpo"),
        medida("width", "Ancho (m)", maximo=1000.0),
        medida("niche_depth", "Fondo (m)", maximo=1000.0),
        medida("height", "Altura (m)", maximo=1000.0),
        medida("sill", "Base sobre el muro (m)", 0.0, 1000.0),
        Campo("leaves", "Hojas", "entero", minimo=1, maximo=128),
        opcion("operation", "Apertura", [("Corredera", "SLIDING"), ("Abatible", "SWINGING")]),
    ]


def normalizar_forjado(datos):
    salida = deepcopy(datos)
    salida["name"] = str(salida.get("name") or "").strip() or "Forjado"
    return salida


def campos_forjado(datos):
    from .slabs import KINDS

    datos.setdefault("clear_holes", False)
    return [
        texto("name", "Nombre"),
        texto("material", "Material"),
        opcion(
            "slab_kind", "Clase de forjado", [(valor[0], clave) for clave, valor in KINDS.items()]
        ),
        medida("thickness", "Canto (m)", maximo=100.0),
        medida("top_offset", "Desfase de la cara superior (m)", -1e6, 1e6),
        Campo("clear_holes", "Quitar los huecos existentes", "logico"),
    ]


def campos_recinto(ctx, datos):
    from .parameters_arq import general_options
    from .compat import require_document
    from . import cte_usos as CU

    por_uso = general_options(require_document(ctx))["usar_usos"]
    datos.setdefault("number", "")
    datos.setdefault("cte", {})
    campos = [
        texto("name", "Nombre"),
        texto("number", "Número"),
        texto("use", "Uso", lambda _: por_uso),
        opcion(
            "enclosure",
            "Situación",
            [("Interior", "interior"), ("Exterior cubierto", "exterior_cubierto"),
             ("Patio descubierto", "exterior_descubierto")],
        ),
        opcion("height_mode", "Altura", [("Automática", "auto"), ("Manual", "manual")]),
        medida("height", "Altura de reserva (m)"),
        Campo("ceiling", "Falso techo", "logico"),
        texto("level", "Nivel descriptivo"),
    ]
    if por_uso:
        datos["_proponer_cte"] = False
        campos.append(
            Campo("_proponer_cte", "Proponer clasificación según el uso (vivienda)", "logico")
        )
        for clave, titulo, etiquetas in CU.CONJUNTOS:
            datos["cte." + clave] = datos["cte"].get(clave, "")
            campos.append(
                opcion("cte." + clave, titulo, [("Sin asignar", "")] + [(e, e) for e in etiquetas])
            )

    def cambiar(clave, valor, valores):
        if clave == "_proponer_cte" and valor:
            valores.update({"cte." + k: v for k, v in CU.propose(valores.get("use", "")).items()})

    return campos, cambiar


def campos_rejilla(datos):
    valores = dict(
        x="3x5",
        y="2x4",
        first_number="1",
        first_letter="A",
        prefix="",
        suffix="",
        angle=0.0,
        extension=1.0,
        scale=100.0,
        text_mm=2.5,
        dim_text_mm=3.5,
        radius_mm=4.0,
        bubble="circle",
        start=True,
        end=True,
        dimensions=True,
        interactive_angle=False,
    )
    for clave, valor in valores.items():
        datos.setdefault(clave, valor)
    return [
        Campo("x", "Intervalos X (; o n x medida)", "intervalos"),
        Campo("y", "Intervalos Y", "intervalos"),
        Campo("first_number", "Primer número", "entero", minimo=1),
        texto("first_letter", "Primera letra"),
        texto("prefix", "Prefijo"),
        texto("suffix", "Sufijo"),
        Campo("angle", "Ángulo (grados)", "angulo", minimo=-360.0, maximo=100000.0, decimales=3),
        Campo(
            "extension", "Prolongación (m)", "numero", minimo=0.001, maximo=100000.0, decimales=3
        ),
        *[
            Campo(
                clave,
                titulo,
                "real" if clave == "scale" else "papel",
                minimo=0.001,
                maximo=100000.0,
                decimales=3,
            )
            for clave, titulo in [
                ("scale", "Escala 1:"),
                ("text_mm", "Texto de burbuja (mm papel)"),
                ("dim_text_mm", "Texto de cotas (mm papel)"),
                ("radius_mm", "Radio de burbuja (mm papel)"),
            ]
        ],
        opcion("bubble", "Burbuja", [("Círculo", "circle"), ("Hexágono", "hexagon")]),
        Campo("start", "Burbuja inicial", "logico"),
        Campo("end", "Burbuja final", "logico"),
        Campo("dimensions", "Cotas en cadena y total", "logico"),
        Campo("interactive_angle", "Giro con cursor después del origen", "logico"),
    ]


def campos_memoria(ctx, datos):
    from .levels import load
    from .compat import require_document

    niveles = load(require_document(ctx))["levels"]
    generar = lambda valores: valores["accion"] == "generar"
    return [
        opcion("accion", "Acción", [("Generar", "generar"), ("Actualizar", "actualizar")]),
        opcion("modo", "Contenido", [("Todo", "todo"), ("Tabla", "tabla"), ("Fichas", "fichas")], generar),
        opcion("planta", "Planta", [("Todas", "all"), *[(nivel["name"], nivel["id"]) for nivel in niveles]], generar),
        opcion("agrupar", "Agrupar", [("Marca", "marca"), ("Planta", "planta")], generar),
        opcion("escala", "Escala", [("1:20", 20), ("1:25", 25), ("1:50", 50)], generar),
        Campo("huecos", "Incluir huecos", "logico", cuando=generar),
        Campo("rotulos", "Rótulos en planta", "logico", cuando=generar),
        Campo("seccion", "Sección horizontal", "logico", cuando=generar),
    ]


def normalizar_memoria(ctx, datos):
    from .levels import load
    from .compat import require_document

    valores = dict(datos)
    if valores.get("accion") not in ("generar", "actualizar"):
        raise ValueError("Acción de memoria no válida")
    if valores["accion"] == "actualizar":
        return {"accion": "actualizar"}
    if valores.get("modo") not in ("todo", "tabla", "fichas"):
        raise ValueError("Contenido: Todo, Tabla o Fichas")
    if valores.get("agrupar") not in ("marca", "planta"):
        raise ValueError("Agrupar por marca o por planta")
    permitidos = {nivel["id"] for nivel in load(require_document(ctx))["levels"]}
    if valores.get("planta") != "all" and valores.get("planta") not in permitidos:
        raise ValueError("La planta de la memoria ya no existe")
    if type(valores.get("escala")) is not int or valores["escala"] not in (20, 25, 50):
        raise ValueError("Escala: 1:20, 1:25 o 1:50")
    for clave in ("huecos", "rotulos", "seccion"):
        if type(valores.get(clave)) is not bool:
            raise ValueError(clave + ": Sí o No")
    return {clave: valores[clave] for clave in ("accion", "modo", "planta", "agrupar", "escala", "huecos", "rotulos", "seccion")}

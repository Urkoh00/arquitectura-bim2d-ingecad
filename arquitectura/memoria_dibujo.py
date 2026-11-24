# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: dibuja fichas, cotas y tabla desde las medidas y piezas comunes de openings.
from .architectural import _xdata
from . import openings

CAPA_PLANO = "ARQ-CARPINTERIA-MEMORIA"
CAPA_COTAS = "ARQ-CARPINTERIA-COTAS"
DISCONTINUA = "ARQ-MEMORIA-DISCONTINUA"


def numero(valor):
    return f"{valor:.2f}".replace(".", ",")


def manos(fila):
    if set(fila["manos"]) == {"sin mano"}:
        return "—"
    return ", ".join(f"{cantidad} {mano}" for mano, cantidad in sorted(fila["manos"].items()))


def localizacion(fila):
    return " | ".join(
        dato["planta"] + " / " + ("; ".join(dato["recintos"]) or "sin recinto")
        for dato in fila["localizacion"]
    )


def principal(fila):
    registro = fila["medidas"]["registro"]
    if registro["leaves"] != 2:
        return "—"
    return "izquierda" if registro["main_leaf"] == "left" else "derecha"


class Dibujante:
    def __init__(self, documento, identificador, escala):
        self.documento = documento
        self.espacio = documento.doc.modelspace()
        self.identificador = identificador
        self.altura = 0.0025 * escala
        self.escala = escala
        self.marca = ""
        self.seccion = False            # dibujar() lo fija con la configuración

    def longitud(self, valor):
        from .presentacion import longitud

        return longitud(valor, self.documento)

    def etiquetar(self, entidad, papel, **datos):
        _xdata(
            self.espacio,
            entidad,
            {
                "kind": "carpentry_schedule_detail",
                "schema": 1,
                "schedule_id": self.identificador,
                "role": papel,
                "mark": self.marca,
                **datos,
            },
        )
        return entidad

    def linea(self, inicio, final, papel="elevation", discontinua=False):
        atributos = {"layer": CAPA_PLANO}
        if discontinua:
            atributos["linetype"] = DISCONTINUA
        return self.etiquetar(self.espacio.add_line(inicio, final, dxfattribs=atributos), papel)

    def contorno(self, puntos, cerrado=True, papel="elevation"):
        return self.etiquetar(
            self.espacio.add_lwpolyline(puntos, close=cerrado, dxfattribs={"layer": CAPA_PLANO}),
            papel,
        )

    def texto(self, insercion, texto, ancho, papel="caption"):
        return self.etiquetar(
            self.espacio.add_mtext(
                texto.replace("\n", "\\P"),
                dxfattribs={
                    "layer": CAPA_PLANO,
                    "insert": insercion,
                    "width": ancho,
                    "char_height": self.altura,
                    "style": self.espacio.doc.header.get("$TEXTSTYLE", "Standard"),
                },
            ),
            papel,
        )

    def cota(self, primero, segundo, base, angulo, papel):
        if abs(primero[0] - segundo[0]) + abs(primero[1] - segundo[1]) <= 1e-7:
            return
        dibujo = self.espacio.doc
        estilo = dibujo.header.get("$DIMSTYLE", "Standard")
        if estilo not in dibujo.dimstyles:
            estilo = "Standard"
        datos_estilo = dibujo.dimstyles.get(estilo).dxf
        tamano = float(datos_estilo.get("dimtxt", 2.5))
        conversion = 0.0025 / (tamano if tamano > 0 else 2.5)
        # La escala es el denominador de la ficha; los tamaños gráficos se
        # expresan en metros de papel y conservan las proporciones del estilo.
        anulaciones = {"dimscale": self.escala, "dimtxt": 0.0025}
        from .presentacion import anulaciones_cota

        anulaciones.update(anulaciones_cota(self.documento))
        for clave, defecto in (
            ("dimasz", 2.5),
            ("dimtsz", 0.0),
            ("dimgap", 0.625),
            ("dimexo", 0.625),
            ("dimexe", 1.25),
            ("dimdle", 0.0),
        ):
            anulaciones[clave] = float(datos_estilo.get(clave, defecto)) * conversion
        dimension = self.espacio.add_linear_dim(
            base=base,
            p1=primero,
            p2=segundo,
            angle=angulo,
            dimstyle=estilo,
            override=anulaciones,
            dxfattribs={"layer": CAPA_COTAS},
        )
        if papel in ("ancho", "hoja"):
            dimension.dimension.dxf.text = ("hueco" if papel == "ancho" else "hoja") + " <>"
        self.etiquetar(dimension.dimension, "dimension", dimension_kind=papel)
        dimension.render()
        bloque = dibujo.blocks.get(dimension.dimension.dxf.geometry)
        for pieza in bloque:
            pieza.dxf.layer = CAPA_COTAS

    def ficha(self, fila, x, techo, ancho_tarjeta, alto_tarjeta):
        previas = {entidad.dxf.handle for entidad in self.espacio}
        self.marca = fila["marca"]
        medidas = fila["medidas"]
        registro = medidas["registro"]
        ancho = medidas["ancho"]
        alto = medidas["alto"]
        antepecho = medidas["antepecho"]
        margen = max(0.5, 4 * self.altura)
        suelo = (
            techo
            - margen * 2
            - alto
            - antepecho
            - max(0.5, len(medidas["hojas"]) * self.altura * 2)
        )
        origen_x = x + margen

        def vista(punto):
            estacion, altura = punto
            local = (estacion - medidas["origen_s"]) * medidas["factor_s"]
            # Desde la cara exterior se mira hacia el interior: el eje horizontal es side*u.
            if registro["side"] < 0:
                local = ancho - local
            return (origen_x + local, suelo + altura)

        marco_tarjeta = self.contorno(
            [
                (x, techo),
                (x + ancho_tarjeta, techo),
                (x + ancho_tarjeta, techo - alto_tarjeta),
                (x, techo - alto_tarjeta),
            ],
            papel="frame_card",
        )
        tipo = fila["definicion"].get("type_name") or (
            "Frente de armario"
            if fila["definicion"]["prefijo"] == "A"
            else openings.NAMES[registro["type"]]
        )
        desarrollo = " · desarrollo" if registro.get("curve_mode") == "curva" else ""
        plantas = " / ".join(fila["plantas"])
        self.texto(
            (x + self.altura, techo - self.altura),
            f"{fila['marca']} · {tipo}{desarrollo}\n{fila['unidades']} ud · {plantas}",
            ancho_tarjeta - 2 * self.altura,
        )
        for parte in medidas["plantillas"]:
            if "box" in parte:
                inicio, final, _, _, inferior, superior = parte["box"]
                puntos = [
                    (inicio, inferior),
                    (final, inferior),
                    (final, superior),
                    (inicio, superior),
                ]
                self.contorno([vista(punto) for punto in puntos], papel=parte["role"])
            else:
                exterior, patios, _, _ = parte["prism"]
                for anillo in [exterior, *patios]:
                    self.contorno([vista(punto) for punto in anillo], papel=parte["role"])
        if registro["type"] == "gap":
            self.contorno(
                [
                    (origen_x, suelo),
                    (origen_x + ancho, suelo),
                    (origen_x + ancho, suelo + alto),
                    (origen_x, suelo + alto),
                ]
            )
        simbolo = dict(registro)
        # Una carpintería plana sobre muro curvo utiliza el marco local de su cuerda.
        simbolo.update(
            offset=medidas["origen_s"], width=ancho / medidas["factor_s"], curve_mode="plana"
        )
        for trazo in openings.simbolos_apertura_alzado(simbolo):
            self.contorno([vista(punto) for punto in trazo], cerrado=False, papel="operation")
        self.linea(
            (origen_x - self.altura, suelo), (origen_x + ancho + self.altura, suelo), papel="floor"
        )
        if antepecho > 0:
            for borde in (origen_x, origen_x + ancho):
                self.linea(
                    (borde, suelo),
                    (borde, suelo + antepecho),
                    papel="sill_projection",
                    discontinua=True,
                )
        desplazamiento = max(0.25, 3 * self.altura)
        self.cota(
            (origen_x, suelo + antepecho),
            (origen_x + ancho, suelo + antepecho),
            (origen_x, suelo - desplazamiento),
            0,
            "ancho",
        )
        self.cota(
            (origen_x + ancho, suelo + antepecho),
            (origen_x + ancho, suelo + antepecho + alto),
            (origen_x + ancho + desplazamiento, suelo),
            90,
            "alto",
        )
        if antepecho > 0:
            self.cota(
                (origen_x, suelo),
                (origen_x, suelo + antepecho),
                (origen_x - desplazamiento, suelo),
                90,
                "antepecho",
            )
        for indice, (inicio, final) in enumerate(medidas["limites_hojas"]):
            if registro["side"] < 0:
                inicio, final = ancho - final, ancho - inicio
            altura = suelo + antepecho + alto
            self.cota(
                (origen_x + inicio, altura),
                (origen_x + final, altura),
                (origen_x, altura + desplazamiento + indice * 2 * self.altura),
                0,
                "hoja",
            )
        siguiente = suelo - desplazamiento - 4 * self.altura
        if self.seccion:
            siguiente = self.seccion_horizontal(
                fila, origen_x, siguiente, ancho_tarjeta - margen - self.altura
            )
        materiales = fila["definicion"]["materiales"]
        u = "sin datos" if fila["u"] is None else numero(fila["u"]) + " W/m²K (sin ψ)"
        textos = [
            "Exterior · " + manos(fila),
            f"{self.longitud(ancho)} × {self.longitud(alto)} m · antepecho {self.longitud(antepecho)} m",
            "Cerco: " + materiales["frame"] + " · hoja: " + materiales["leaf"],
            "Vidrio: " + (materiales["glass"] if registro["type"] == "window" else "sin vidrio"),
            f"Hueco: {numero(fila['area_unitaria'])} m² · U: {u}",
            "Ubicación: " + localizacion(fila),
        ]
        if registro["type"] == "gap":
            textos[2:4] = ["Sin cerco, hojas ni vidrio"]
        if registro["leaves"] == 2:
            textos.insert(1, "Hoja principal: " + principal(fila))
        manilla = next((p for p in medidas["plantillas"] if p["role"] == "handle"), None)
        if manilla:
            altura_manilla = (manilla["box"][4] + manilla["box"][5]) / 2
            textos.append("Manilla: " + materiales["handle"] + " · altura " + self.longitud(altura_manilla) + " m")
        cuerpo = self.texto(
            (x + self.altura, siguiente), "\n".join(textos), ancho_tarjeta - 2 * self.altura
        )
        from ezdxf import bbox

        contenido = [
            entidad
            for entidad in self.espacio
            if entidad.dxf.handle not in previas and entidad is not marco_tarjeta
        ]
        limites = bbox.extents(contenido)
        alto_real = techo - limites.extmin.y + 2 * self.altura
        marco_tarjeta.set_points(
            [
                (x, techo),
                (x + ancho_tarjeta, techo),
                (x + ancho_tarjeta, techo - alto_real),
                (x, techo - alto_real),
            ]
        )
        return alto_real

    def seccion_horizontal(self, fila, x, y, ancho_texto):
        from .geom.junctions import Wall
        from ezdxf import bbox

        previas = {entidad.dxf.handle for entidad in self.espacio}

        medidas = fila["medidas"]
        ancho = medidas["ancho"]
        registro = {
            **medidas["registro"],
            "width": ancho,
            "offset": 0.3,
            "curve_mode": "plana",
            "cabinet": False,
        }
        espesor = fila["espesor_muro"]
        muro = Wall("memoria", (0.0, 0.0), (ancho + 0.6, 0.0), espesor, "eje")
        registro = openings.normalise(registro)
        items = openings.plan_symbol(muro, registro)
        alturas = [espesor / 2]
        for item in items:
            if item[0] == "line":
                alturas.extend(punto[1] for punto in item[1:3])
            elif item[0] == "poly":
                alturas.extend(punto[1] for punto in item[1])
            else:
                alturas.append(item[1][1] + item[2])
        origen_y = y - max(alturas)

        def transformar(punto):
            estacion = punto[0] - 0.3
            if registro["side"] < 0:
                estacion = ancho - estacion
            return (x + estacion, origen_y + punto[1])

        for inicio, final in ((0, 0.3), (ancho + 0.3, ancho + 0.6)):
            self.contorno(
                [
                    transformar(punto)
                    for punto in (
                        (inicio, -espesor / 2),
                        (final, -espesor / 2),
                        (final, espesor / 2),
                        (inicio, espesor / 2),
                    )
                ],
                papel="section",
            )
        for item in items:
            if item[0] == "line":
                self.linea(transformar(item[1]), transformar(item[2]), papel="section")
            elif item[0] == "poly":
                self.contorno([transformar(punto) for punto in item[1]], item[2], papel="section")
            else:
                import math

                centro, radio, primero, ultimo = item[1:5]
                barrido = (ultimo - primero) % 360
                puntos = [
                    (
                        centro[0] + radio * math.cos(math.radians(primero + barrido * paso / 36)),
                        centro[1] + radio * math.sin(math.radians(primero + barrido * paso / 36)),
                    )
                    for paso in range(37)
                ]
                self.contorno([transformar(punto) for punto in puntos], False, papel="section")
        trazos = [entidad for entidad in self.espacio if entidad.dxf.handle not in previas]
        # La hoja puede abrir hacia abajo: el espesor no delimita el símbolo.
        borde_inferior = bbox.extents(trazos).extmin.y
        leyenda = self.texto(
            (x, borde_inferior - self.altura),
            "Sección · muro " + self.longitud(espesor) + " m (más frecuente)",
            ancho_texto,
            papel="section_caption",
        )
        return bbox.extents([leyenda]).extmin.y - 2 * self.altura

    def tabla(self, filas, insercion):
        from core.tables import insert_table
        from .architectural import metadata

        cabeceras = [
            "Marca",
            "Ud",
            "Tipo",
            "Ancho × alto (m)",
            "Hojas (nº · m)",
            "Apertura",
            "Mano",
            "Principal",
            "Materiales",
            "m²/ud",
            "m² total",
            "Planta / recintos",
        ]
        datos = []
        for fila in filas:
            definicion = fila["definicion"]
            materiales = definicion["materiales"]
            datos.append(
                [
                    fila["marca"],
                    str(fila["unidades"]),
                    (
                        "Frente de armario"
                        if definicion["prefijo"] == "A"
                        else openings.NAMES[definicion["type"]]
                    ),
                    self.longitud(fila["medidas"]["ancho"])
                    + " × "
                    + self.longitud(fila["medidas"]["alto"]),
                    (
                        (
                            str(len(fila["medidas"]["hojas"]))
                            + " · "
                            + " / ".join(self.longitud(valor) for valor in fila["medidas"]["hojas"])
                        )
                        if fila["medidas"]["hojas"]
                        else "—"
                    ),
                    openings.OPERATION_NAMES.get(definicion["operation"]) or "sin carpintería",
                    manos(fila),
                    principal(fila),
                    (
                        "sin carpintería"
                        if definicion["type"] == "gap"
                        else "C: "
                        + materiales["frame"]
                        + "; H: "
                        + materiales["leaf"]
                        + ("; M: " + materiales["handle"] if "handle" in materiales else "")
                        + ("; V: " + materiales["glass"] if definicion["type"] == "window" else "")
                    ),
                    numero(fila["area_unitaria"]),
                    numero(fila["area_total"]),
                    localizacion(fila),
                ]
            )
        anchuras = [
            max(len(str(fila[columna])) for fila in [cabeceras, *datos]) * self.altura * 0.7
            + 3 * self.altura
            for columna in range(len(cabeceras))
        ]
        previas = {entidad.dxf.handle for entidad in self.espacio}
        comando = insert_table(
            insercion,
            len(cabeceras),
            1.0,
            len(datos),
            4 * self.altura,
            self.altura,
            title="MEMORIA DE CARPINTERÍA",
            headers=cabeceras,
            data=datos,
            col_widths=anchuras,
        )
        # TABLE ya genera líneas y textos estables; su API no crea ACAD_TABLE.
        for miembro in comando.commands:
            miembro.layer = CAPA_PLANO
            miembro.do(self.documento)
        for entidad in self.espacio:
            if entidad.dxf.handle not in previas and not metadata(entidad):
                self.etiquetar(entidad, "table")


def dibujar(documento, filas, insercion, configuracion, identificador):
    dibujante = Dibujante(documento, identificador, configuracion["escala"])
    dibujante.seccion = configuracion["seccion"]
    x, y = insercion
    if not filas:
        dibujante.texto(
            (x, y), "MEMORIA DE CARPINTERÍA — sin carpinterías en el ámbito guardado", 10.0
        )
        y -= 6 * dibujante.altura
    if filas and configuracion["modo"] in ("todo", "fichas"):
        ancho = max(3.2, max(fila["medidas"]["ancho"] for fila in filas) + 2.0)
        columnas = min(4, len(filas))
        techo_fila = y
        alto_fila = 0.0
        marcos_fila = []
        for indice, fila in enumerate(filas):
            previas = {entidad.dxf.handle for entidad in dibujante.espacio}
            alto_real = dibujante.ficha(
                fila, x + (indice % columnas) * (ancho + 0.4), techo_fila, ancho, 0.0
            )
            from .architectural import metadata

            marcos_fila.extend(
                entidad
                for entidad in dibujante.espacio
                if entidad.dxf.handle not in previas
                and (metadata(entidad) or {}).get("role") == "frame_card"
            )
            alto_fila = max(alto_fila, alto_real)
            if (indice + 1) % columnas == 0 or indice == len(filas) - 1:
                # Se ajusta la fila completa para conservar la cuadrícula,
                # también si una ficha tiene materiales o recintos más largos.
                for marco in marcos_fila:
                    puntos = list(marco.get_points("xy"))
                    marco.set_points(
                        [
                            puntos[0],
                            puntos[1],
                            (puntos[2][0], techo_fila - alto_fila),
                            (puntos[3][0], techo_fila - alto_fila),
                        ]
                    )
                techo_fila -= alto_fila + 0.4
                alto_fila = 0.0
                marcos_fila = []
        y = techo_fila - 0.5
    if configuracion["modo"] in ("todo", "tabla"):
        dibujante.marca = ""
        dibujante.tabla(filas, (x, y))

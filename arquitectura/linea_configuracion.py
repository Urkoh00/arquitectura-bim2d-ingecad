# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: configuración, catálogo y niveles por texto; los cambios usan las órdenes existentes.
from copy import deepcopy
from pathlib import Path
import uuid

from tools.base import Tool
from .linea_campos import Campo, ContextoLinea, PreguntasTexto
from .linea_fichas import medida, opcion, texto
from .compat import require_document

NOMBRES_CONFIGURACION = ("PARAMETROSARQ", "USOSARQ", "TIPOSMURO", "NIVELES", "NIVELASIGNAR")


def campos_parametros(valores):
    etiquetas = {
        "thickness": "Espesor",
        "height": "Altura",
        "base": "Cota base",
        "reference": "Referencia",
        "name": "Nombre",
        "type_name": "Tipo BIM",
        "material": "Material",
        "level": "Nivel",
        "shape": "Sección",
        "width": "Anchura",
        "depth": "Fondo",
        "radius": "Radio",
        "rotation": "Giro",
        "sill": "Antepecho",
        "wall_category": "Categoría",
    }
    campos = []
    planos = {}
    for grupo, titulo in [
        ("wall", "Muros"),
        ("column", "Pilares"),
        ("door", "Puertas"),
        ("window", "Ventanas"),
    ]:
        for clave, valor in valores[grupo].items():
            ruta = grupo + "." + clave
            planos[ruta] = valor
            etiqueta = titulo + ": " + etiquetas.get(clave, clave)
            if clave in ("thickness", "height", "width", "depth", "radius", "base", "sill"):
                campos.append(
                    medida(ruta, etiqueta + " (m)", -1e6 if clave in ("base", "sill") else 0.001)
                )
            elif clave == "rotation":
                campos.append(
                    Campo(ruta, etiqueta + " (grados)", "angulo", minimo=-360.0, maximo=360.0)
                )
            elif clave == "reference":
                campos.append(
                    opcion(
                        ruta,
                        etiqueta,
                        [("Eje", "eje"), ("Izquierda", "izquierda"), ("Derecha", "derecha")],
                    )
                )
            elif clave == "shape":
                campos.append(
                    opcion(
                        ruta,
                        etiqueta,
                        [
                            ("Rectangular", "rect"),
                            ("Circular", "circ"),
                            ("Hexagonal", "hex"),
                            ("Octogonal", "oct"),
                        ],
                    )
                )
            else:
                campos.append(texto(ruta, etiqueta))
    general = valores["general"]
    from .vistas_arq import RELLENOS, GAMA, GROSORES
    for clave in ("escala", "precision_medidas", "usar_usos", "cota_minima", "norte", "armarios_superficie_util",
                  "vista_relleno", "vista_color", "grosor_corte", "grosor_tierra", "grosor_visto"):
        planos["general." + clave] = general[clave]
    campos.extend(
        [
            opcion("general.escala", "Escala de documentación", [("1:20", 20), ("1:25", 25), ("1:50", 50)]),
            opcion("general.precision_medidas", "Precisión de las medidas", [("Centímetros", "cm"), ("Milímetros", "mm")]),
            Campo("general.usar_usos", "Trabajar con usos de recinto", "logico"),
            medida("general.cota_minima", "Cota mínima (m)", 0.0, 10.0),
            Campo(
                "general.norte",
                "Norte (grados, horario desde +Y)",
                "angulo",
                minimo=-360.0,
                maximo=360.0,
            ),
            opcion(
                "general.armarios_superficie_util",
                "Armarios en superficie útil",
                [("Computan", "computan"), ("Descuentan", "descuentan")],
            ),
            opcion("general.vista_relleno", "Relleno de lo cortado en secciones",
                   [(n, v) for v, n in RELLENOS.items()]),
            opcion("general.vista_color", "Gris del relleno", list(GAMA)),
            opcion("general.grosor_corte", "Grosor de lo cortado (mm)",
                   [(f"{x:g}".replace(".", ","), x) for x in GROSORES]),
            opcion("general.grosor_tierra", "Grosor de la línea de tierra (mm)",
                   [(f"{x:g}".replace(".", ","), x) for x in GROSORES]),
            opcion("general.grosor_visto", "Grosor de lo visto (mm)",
                   [(f"{x:g}".replace(".", ","), x) for x in GROSORES]),
        ]
    )
    return campos, planos


class ConfiguracionTexto(PreguntasTexto, Tool):
    def start(self):
        from .parameters_arq import load_defaults

        self.name = type(self).name
        self._campos_texto = None
        self.ctx = ContextoLinea(self.ctx)
        self._configuracion = load_defaults(require_document(self.ctx))
        if self.orden_original == "PARAMETROSARQ":
            campos, valores = campos_parametros(self._configuracion)
            self.preguntar(campos, valores, self._guardar_parametros)
        elif self.orden_original == "USOSARQ":
            self._preguntar_usos()
        elif self.orden_original == "TIPOSMURO":
            self._preguntar_tipos()
        elif self.orden_original == "NIVELES":
            self._preguntar_niveles()
        else:
            self.prompt("-NIVELASIGNAR: seleccione fuentes BIM y confirme con Intro:")

    def _guardar_parametros(self, valores):
        from .parameters_arq import guardar_parametros

        nuevo = deepcopy(self._configuracion)
        for ruta, valor in valores.items():
            grupo, clave = ruta.split(".", 1)
            nuevo[grupo][clave] = valor
        guardar_parametros(self.ctx, nuevo)
        self.ctx.finish()

    def _preguntar_usos(self):
        from .parameters_arq import TIPOS_EDIFICIO_CEE
        from .bim_dialogs import CEE_NAMES

        valores = deepcopy(self._configuracion["usos"])
        valores["carga_dbhe"] = valores.get("carga_dbhe") or "media"
        valores["horario_dbhe"] = str(valores.get("horario_dbhe") or "12")
        otros = lambda v: v["uso_dbhe"] == "otros usos"
        campos = [
            opcion(
                "tipo_edificio_cee",
                "Tipo de edificio del certificado",
                [(CEE_NAMES.get(t, t), t) for t in TIPOS_EDIFICIO_CEE],
            ),
            opcion(
                "uso_dbhe",
                "Uso DB-HE",
                [("Residencial privado", "residencial privado"), ("Otros usos", "otros usos")],
            ),
            opcion(
                "carga_dbhe",
                "Carga interna",
                [("Baja", "baja"), ("Media", "media"), ("Alta", "alta")],
                otros,
            ),
            opcion(
                "horario_dbhe", "Horario", [(n + " h", n) for n in ("8", "12", "16", "24")], otros
            ),
            texto("uso_dbsi", "Uso DB-SI / DB-SUA"),
        ]
        self.preguntar(campos, valores, self._guardar_usos)

    def _guardar_usos(self, valores):
        from .parameters_arq import guardar_usos

        if valores["uso_dbhe"] == "residencial privado":
            valores.update(carga_dbhe="", horario_dbhe="")
        guardar_usos(self.ctx, valores)
        self.ctx.finish()

    def _preguntar_tipos(self):
        from .parameters_arq import layers_text, nuevo_tipo
        from .wall_categories import CATEGORIES

        tipos = self._configuracion["wall_types"]
        primero = tipos[0] if tipos else nuevo_tipo(tipos)
        valores = {
            "accion": "editar" if tipos else "crear",
            "anterior": tipos[0]["name"] if tipos else None,
            "nombre": primero["name"],
            "capas": layers_text(primero),
            "categoria": primero["wall_category"],
            "ruta": str(Path.cwd() / "tipos_muro.csv"),
        }
        editar = lambda v: v["accion"] in ("crear", "editar", "duplicar")
        elegir = lambda v: v["accion"] in ("editar", "eliminar", "duplicar")
        archivo = lambda v: v["accion"] in ("importar", "exportar")
        campos = [
            opcion(
                "accion",
                "Catálogo de muros",
                [
                    (t.capitalize(), t)
                    for t in ("listar", "crear", "editar", "duplicar", "eliminar", "importar", "exportar")
                ],
            ),
            opcion("anterior", "Tipo existente", [(t["name"], t["name"]) for t in tipos], elegir),
            texto("nombre", "Nombre del tipo", editar),
            texto("capas", "Capas desde la cara dibujada (espesor material + ...)", editar),
            opcion("categoria", "Categoría", CATEGORIES, editar),
            texto("ruta", "Ruta del CSV", archivo),
        ]

        def cambiar(clave, valor, datos):
            if clave == "accion" and valor == "crear":
                tipo = nuevo_tipo(tipos)
                datos.update(nombre=tipo["name"], capas=layers_text(tipo), categoria=tipo["wall_category"])
            if clave == "anterior":
                tipo = next((t for t in tipos if t["name"] == valor), None)
                if tipo is None:
                    raise ValueError("Seleccione un tipo existente")
                if datos["accion"] == "duplicar":
                    tipo = nuevo_tipo(tipos, tipo)
                datos.update(
                    nombre=tipo["name"], capas=layers_text(tipo), categoria=tipo["wall_category"]
                )

        self.preguntar(campos, valores, self._guardar_tipos, cambiar)

    def _guardar_tipos(self, valores):
        from . import parameters_arq as P

        accion = valores["accion"]
        if accion in ("listar", "importar", "exportar"):
            if accion == "listar":
                P.tipos_muro(self.ctx)
            else:
                P.tipos_muro(self.ctx, accion, valores["ruta"])
            self.ctx.finish()
            return
        tipos = deepcopy(self._configuracion["wall_types"])
        anterior = next((t for t in tipos if t["name"] == valores["anterior"]), None)
        if accion in ("editar", "eliminar", "duplicar") and anterior is None:
            raise ValueError("Seleccione un tipo existente")
        if accion == "eliminar":
            tipos.remove(anterior)
        else:
            tipo = P.parse_type(valores["nombre"] + " = " + valores["capas"])
            tipo = P.normalise_type({**tipo, "wall_category": valores["categoria"]})
            if accion == "editar":
                tipos[tipos.index(anterior)] = tipo
            else:
                tipos.append(tipo)
        P.guardar_tipos(self.ctx, tipos)
        self.ctx.finish()

    def _preguntar_niveles(self):
        from .levels import load

        self._catalogo = load(require_document(self.ctx))
        niveles = self._catalogo["levels"]
        activo = next(n for n in niveles if n["id"] == self._catalogo["active"])
        datos = {
            "accion": "editar",
            "nivel": activo["id"],
            "nombre": activo["name"],
            "cota": activo["elevation"],
            "activar": False,
            "estado": "on",
            "valor": True,
        }
        elegir = lambda v: v["accion"] != "crear"
        editar = lambda v: v["accion"] in ("crear", "editar")
        estado = lambda v: v["accion"] == "estado"
        campos = [
            opcion(
                "accion",
                "Niveles",
                [
                    (t.capitalize(), t)
                    for t in ("listar", "crear", "editar", "eliminar", "activo", "estado")
                ],
            ),
            opcion("nivel", "Nivel existente", [(n["name"], n["id"]) for n in niveles], elegir),
            texto("nombre", "Nombre del nivel", editar),
            medida("cota", "Cota nominal (m)", -1e6, 1e6, cuando=editar),
            Campo("activar", "Dejar este nivel activo", "logico", cuando=editar),
            opcion(
                "estado",
                "Estado de sus capas",
                [("Encendido", "on"), ("Inutilizado", "frozen"), ("Bloqueado", "locked")],
                estado,
            ),
            Campo("valor", "Activar ese estado", "logico", cuando=estado),
        ]

        def cambiar(clave, valor, valores):
            if clave == "accion" and valor == "crear":
                valores.update(
                    nombre=f"Nivel {len(niveles)}", cota=max(n["elevation"] for n in niveles) + 3.0
                )
            if clave == "nivel":
                nivel = next(n for n in niveles if n["id"] == valor)
                valores.update(nombre=nivel["name"], cota=nivel["elevation"])

        self.preguntar(campos, datos, self._guardar_niveles, cambiar)

    def _guardar_niveles(self, valores):
        from .levels import apply
        from .level_layers import set_state

        accion = valores["accion"]
        if accion == "listar":
            for nivel in self._catalogo["levels"]:
                self.ctx.echo(f"{nivel['name']}: {nivel['elevation']:g} m")
        elif accion == "estado":
            set_state(self.ctx, valores["nivel"], valores["estado"], valores["valor"])
        else:
            datos = deepcopy(self._catalogo)
            nivel = next((n for n in datos["levels"] if n["id"] == valores["nivel"]), None)
            if accion == "crear":
                nivel = {
                    "id": uuid.uuid4().hex,
                    "name": valores["nombre"],
                    "elevation": valores["cota"],
                }
                datos["levels"].append(nivel)
            elif accion == "editar":
                nivel.update(name=valores["nombre"], elevation=valores["cota"])
            elif accion == "eliminar":
                datos["levels"].remove(nivel)
                if datos["active"] == nivel["id"]:
                    datos["active"] = datos["levels"][0]["id"] if datos["levels"] else None
            if accion == "activo" or (accion in ("crear", "editar") and valores["activar"]):
                datos["active"] = nivel["id"]
            apply(self.ctx, datos)
        self.ctx.finish()

    def on_selection(self, entidades):
        from .levels import load

        self._seleccion = list(entidades)
        datos = load(require_document(self.ctx))
        campos = [
            opcion("nivel", "Nivel de destino", [(n["name"], n["id"]) for n in datos["levels"]]),
            Campo("conservar", "Conservar cota absoluta", "logico"),
        ]
        self.preguntar(campos, {"nivel": datos["active"], "conservar": True}, self._asignar_nivel)

    def _asignar_nivel(self, valores):
        from .levels import assign

        assign(self.ctx, self._seleccion, valores["nivel"], valores["conservar"])
        self.ctx.finish()


def crear_variantes_configuracion():
    return {
        "-"
        + nombre: type(
            nombre.title() + "PorLinea",
            (ConfiguracionTexto,),
            {
                "name": "-" + nombre,
                "orden_original": nombre,
                "wants_selection": nombre == "NIVELASIGNAR",
                "__module__": __name__,
            },
        )
        for nombre in NOMBRES_CONFIGURACION
    }

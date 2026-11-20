# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: edición BIM y de ejes por texto, conservando las operaciones de las fichas.
from copy import deepcopy

from tools.base import Tool
from .architectural import metadata
from .compat import require_document
from .linea_campos import Campo, ContextoLinea, PreguntasTexto
from . import linea_fichas as F

NOMBRES_EDICION = ("PROPIEDADESARQ", "EDITARARQ", "EDITAREJE")


class PropiedadesTexto(PreguntasTexto, Tool):
    entity_picker = True

    def start(self):
        self.name = type(self).name
        self.ctx = ContextoLinea(self.ctx)
        self._campos_texto = None
        self.prompt(self.name + ": designe un elemento BIM:")

    def on_point(self, punto):
        if self._campos_texto is not None:
            return PreguntasTexto.on_point(self, punto)
        from .arq_properties import resolve_arch_entity

        entidad, error = resolve_arch_entity(
            require_document(self.ctx), self.ctx.services.pick_entity(punto)
        )
        if entidad is None:
            self.ctx.echo(self.name + ": " + error)
            return
        self.entity = entidad
        datos = deepcopy(metadata(entidad))
        self._kind = datos["kind"]
        if self.orden_original == "EDITARARQ" and self._kind not in ("wall", "opening", "space"):
            self.ctx.echo("No se seleccionó una entidad ARQ editable.")
            return
        cambiar = None
        if self._kind == "wall":
            campos, cambiar = F.campos_muro(self.ctx, datos)
        elif self._kind == "column":
            campos = F.campos_pilar(datos, False)
        elif self._kind == "space":
            campos, cambiar = F.campos_recinto(self.ctx, datos)
        elif self._kind == "slab":
            from . import slabs
            from .levels import load

            datos = deepcopy(slabs.read(entidad))
            catalogo = load(require_document(self.ctx))
            nivel = next(n for n in catalogo["levels"] if n["id"] == datos["level_id"])
            datos["top_offset"] = datos["base"] + datos["thickness"] - nivel["elevation"]
            campos = F.campos_forjado(datos)
        elif datos.get("cabinet"):
            campos = F.campos_armario(datos)
        else:
            from . import openings
            from .geom.junctions import walls_from_records

            anfitrion = next(
                metadata(e)
                for e in entidad.doc.modelspace()
                if (metadata(e) or {}).get("id") == datos["wall_id"]
            )
            muro = walls_from_records([(anfitrion["id"], anfitrion)])[0]
            datos["width"] = openings.measure_of(
                muro, datos["width"], datos, int(datos.get("side", 1))
            )
            campos, cambiar = F.campos_carpinteria(self.ctx, datos, editar=True)
        self.preguntar(campos, datos, self._guardar, cambiar)

    def _guardar(self, datos):
        from .arq_properties import cambio_propiedades
        from .transactions import apply_architectural_change

        if self._kind == "wall":
            valores = F.normalizar_muro(self.ctx, datos)
        elif self._kind == "column":
            valores = F.normalizar_pilar(datos)
        elif self._kind == "opening" and not datos.get("cabinet"):
            valores = F.normalizar_carpinteria(datos)
        elif self._kind == "space":
            from .cte_usos import validate

            valores = deepcopy(datos)
            valores["cte"].update({k[4:]: v for k, v in datos.items() if k.startswith("cte.")})
            valores["cte"] = validate(valores["cte"])
        else:
            valores = datos
        cambio = cambio_propiedades(self.ctx, self.entity, valores)
        apply_architectural_change(self.ctx, cambio, kind=self._kind)
        if self.orden_original == "PROPIEDADESARQ":
            self.ctx.echo(
                "Elemento BIM editado. Identificador conservado: "
                + str(metadata(self.entity)["id"])
            )
        elif self._kind == "wall":
            self.ctx.echo("Propiedades BIM y encuentros actualizados en una operación.")
        else:
            self.ctx.echo("Propiedades BIM actualizadas en una operación.")
        self.ctx.finish()

    def on_enter(self):
        if self._campos_texto is not None:
            return PreguntasTexto.on_enter(self)
        self.ctx.finish()


from .grid_tools import GridEditTool


class EjeTexto(PreguntasTexto, GridEditTool):
    name = "-EDITAREJE"

    def start(self):
        self._campos_texto = None
        self.ctx = ContextoLinea(self.ctx)
        super().start()

    def on_option(self, texto):
        if self._campos_texto is not None or self.entity is None:
            return super().on_option(texto)
        orden = str(texto).casefold().strip()
        if orden not in ("ficha", "separaciones", "tabla"):
            return super().on_option(texto)
        from . import grids

        if orden in ("separaciones", "tabla"):
            datos, *_ = grids.spacing_values(
                require_document(self.ctx).doc, metadata(self.entity)["grid_id"]
            )
            campos = [
                Campo("x", "Intervalos X", "intervalos"),
                Campo("y", "Intervalos Y", "intervalos"),
            ]
            self.preguntar(campos, datos, self._espaciado)
        else:
            datos = deepcopy(metadata(self.entity))
            puntos = grids.endpoints(self.entity)
            escala = float(datos.get("scale", 100.0))
            campos = [F.texto("label", "Marca")]
            for indice, punto in enumerate(puntos):
                for eje, valor in zip(("x", "y"), punto):
                    clave = f"p{indice}.{eje}"
                    datos[clave] = valor
                    campos.append(
                        F.medida(
                            clave,
                            ("Inicio" if indice == 0 else "Final") + " " + eje.upper(),
                            -1e9,
                            1e9,
                        )
                    )
            for clave, titulo in [
                ("text_height", "Texto"),
                ("radius", "Radio"),
                ("dim_text_height", "Texto de cotas"),
            ]:
                datos[clave] = datos.get(clave, datos["text_height"]) * 1000 / escala
                campos.append(
                    Campo(clave, titulo + " (mm papel)", "papel", minimo=0.1, maximo=100.0)
                )
            campos.append(
                F.opcion("bubble", "Burbuja", [("Círculo", "circle"), ("Hexágono", "hexagon")])
            )
            for indice in range(2):
                datos[f"extremo{indice}"] = datos["ends"][indice]
                campos.append(Campo(f"extremo{indice}", f"Burbuja {indice + 1}", "logico"))
            self.preguntar(campos, datos, self._ficha)
        return True

    def _espaciado(self, datos):
        self.apply_spacing(datos)
        self.ctx.finish()

    def _ficha(self, datos):
        escala = float(datos.get("scale", 100.0))
        valores = {k: datos[k] for k in ("label", "bubble")}
        valores.update(
            {k: datos[k] * escala / 1000 for k in ("text_height", "radius", "dim_text_height")}
        )
        valores["ends"] = [datos[f"extremo{i}"] for i in range(2)]
        puntos = [[datos[f"p{i}.{eje}"] for eje in ("x", "y")] for i in range(2)]
        self.apply_axis(valores, puntos)
        self.ctx.finish()


def crear_variantes_edicion():
    variantes = {EjeTexto.name: EjeTexto}
    for nombre in NOMBRES_EDICION[:-1]:
        variantes["-" + nombre] = type(
            nombre.title() + "PorLinea",
            (PropiedadesTexto,),
            {"name": "-" + nombre, "orden_original": nombre, "__module__": __name__},
        )
    return variantes

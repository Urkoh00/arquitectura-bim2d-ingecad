# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: variantes -ORDEN; las preguntas de texto reutilizan los comandos geométricos nativos.
from copy import deepcopy

from .linea_campos import ContextoLinea, PreguntasTexto
from . import linea_fichas as F


class CreacionTexto(PreguntasTexto):
    """La misma instancia conserva referencias, cotas temporales y los handlers del original."""

    def start(self):
        self._campos_texto = None
        self.ctx = ContextoLinea(self.ctx)
        super().start()
        self.name = type(self).name
        self._configurar_texto()

    def _configurar_texto(self):
        familia = F.CREACION[self.orden_original]
        cambiar = None
        if familia == "muro":
            datos = {
                **self.bim,
                **{k: getattr(self, k) for k in ("thickness", "height", "base", "reference")},
            }
            campos, cambiar = F.campos_muro(self.ctx, datos)
        elif familia == "pilar":
            datos = deepcopy(self.values)
            datos["anchor"] = getattr(self, "anchor", 5)
            campos = F.campos_pilar(datos, self.orden_original == "PILAR")
        elif familia == "carpinteria":
            datos = deepcopy({**self.v, **self.bim})
            campos, cambiar = F.campos_carpinteria(self.ctx, datos)
        elif familia == "recinto":
            datos = dict(
                name=self.next_name or "",
                number=self.number or "",
                use=self.use,
                enclosure=self.enclosure,
                height=self.height,
                height_mode=self.height_mode,
                ceiling=self.ceiling,
                level=self.level,
                cte=deepcopy(self.cte),
            )
            campos = F.campos_recinto(self.ctx, datos)
        else:
            datos = deepcopy(self.values)
            campos = {
                "forjado": F.campos_forjado,
                "armario": F.campos_armario,
                "rejilla": F.campos_rejilla,
            }[familia](datos)
        self.preguntar(campos, datos, self._aplicar_texto, cambiar)

    def _aplicar_texto(self, datos):
        familia = F.CREACION[self.orden_original]
        if familia == "muro":
            valores = F.normalizar_muro(self.ctx, datos)
            for clave in ("thickness", "height", "base", "reference"):
                setattr(self, clave, valores.pop(clave))
            if not valores.get("layers"):
                valores.pop("layers", None)
                self.bim.pop("layers", None)
            self.bim.update(valores)
            self.ctx.echo(f"Altura resultante: {self.height:g} m")
            self._reprompt()
        elif familia == "pilar":
            valores = F.normalizar_pilar(datos)
            anclaje = valores.pop("anchor", 5)
            if self.orden_original == "PILAR":
                self.anchor = anclaje
            self.values.update(valores)
            if self.orden_original == "PILAR":
                self._prompt()
            else:
                self.prompt("PILARESENEJES: primera esquina de zona o [Todos]:")
        elif familia == "carpinteria":
            self.apply_sheet(F.normalizar_carpinteria(datos))
            self._prompt()
        elif familia == "recinto":
            from . import cte_usos as CU

            valores = deepcopy(datos)
            valores["cte"].update({k[4:]: v for k, v in valores.items() if k.startswith("cte.")})
            valores["cte"] = CU.validate(valores["cte"])
            self.apply_sheet(valores)
            self._prompt()
        else:
            if familia == "rejilla":
                from . import grids

                grids.grid_geometry((0.0, 0.0), datos)
                grids.letter_index(datos["first_letter"])
            valores = deepcopy(datos)
            valores.pop("clear_holes", None)
            self.values = valores
            if familia == "rejilla":
                self.prompt(
                    "EJES: origen de rejilla o [X intervalos/Y intervalos/Angulo grados/Suelto/Fin]:"
                )
            else:
                self._prompt()

    def on_option(self, texto):
        if self._campos_texto is None and str(texto).casefold() in (
            "d",
            "ficha",
            "dialogo",
            "diálogo",
        ):
            self._configurar_texto()
            return True
        return super().on_option(texto)


def crear_variantes(herramientas, comandos):
    variantes = {}
    for nombre in F.CREACION:
        original = herramientas[nombre]
        variante = type(
            original.__name__ + "PorLinea",
            (CreacionTexto, original),
            {"name": "-" + nombre, "orden_original": nombre, "__module__": __name__},
        )
        variantes[variante.name] = variante
    from .linea_configuracion import crear_variantes_configuracion

    variantes.update(crear_variantes_configuracion())
    return variantes

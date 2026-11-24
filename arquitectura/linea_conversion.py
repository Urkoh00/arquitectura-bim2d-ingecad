# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: clasificación por texto de LINEASAMURO, con la vista previa y la conversión existentes.
from copy import deepcopy

from .convert_tools import LineasAMuroTool
from .compat import require_document
from .entrada_revisada import es_capa_revisada, cargar_procedencia
from .linea_campos import Campo, ContextoLinea, PreguntasTexto
from .linea_fichas import medida, opcion, texto

NOMBRES_CONVERSION = ("LINEASAMURO",)


class ConversionTexto(PreguntasTexto, LineasAMuroTool):
    name = "-LINEASAMURO"

    def start(self):
        self._campos_texto = None
        self.ctx = ContextoLinea(self.ctx)
        super().start()
        self._classification_dialog()

    def _classification_available(self):
        return False

    def _classification_dialog(self):
        from .conversion_plan import Classification, ROLES, guess_roles, layers_present

        actual = self.classification or Classification()
        capas = layers_present(require_document(self.ctx).doc)
        asignaciones = (
            actual.layers if actual.layers_confirmed or actual.layers else guess_roles(capas)
        )
        datos = {
            "altura": self.height,
            "minimo": self.tmin,
            "maximo": self.tmax,
            "paralelismo": self.lineas["paralelismo"],
            "origen": self.origin,
            "procedencia": "",
            "rangos": bool(actual.thickness_ranges),
            "designar": None,
        }
        campos = [
            medida("altura", "Altura de muros (m)"),
            medida("minimo", "Espesor mínimo (m)"),
            medida("maximo", "Espesor máximo (m)"),
            medida("paralelismo", "Desviación de paralelismo (m)", 0.0, 0.5),
            opcion(
                "origen",
                "Líneas originales",
                [(t.capitalize(), t) for t in ("ocultar", "borrar", "conservar")],
            ),
            texto(
                "procedencia", "Ruta de procedencia (vacía conserva la actual; Ninguna la retira)"
            ),
        ]
        for capa in capas:
            clave = "capa." + capa
            datos[clave] = None if es_capa_revisada(capa) else asignaciones.get(capa)
            if es_capa_revisada(capa):
                self.ctx.echo(capa + ": solo puede convertirse mediante procedencia válida.")
            elif actual.reviewed_source is None:
                campos.append(
                    opcion(
                        clave,
                        "Papel de la capa " + capa,
                        [("No convertir", None)] + [(v, k) for k, v in ROLES.items()],
                    )
                )
        campos.append(Campo("rangos", "Usar rangos independientes por categoría", "logico"))
        for categoria, inicial in [
            ("muros", (0.07, 0.50)),
            ("medianeras", (0.07, 0.50)),
            ("particiones", (0.05, 0.15)),
        ]:
            for extremo, valor in zip(
                ("minimo", "maximo"), actual.thickness_ranges.get(categoria, inicial)
            ):
                clave = categoria + "." + extremo
                datos[clave] = valor
                campos.append(
                    medida(
                        clave,
                        categoria.capitalize() + ": espesor " + extremo + " (m)",
                        0.001,
                        5.0,
                        lambda v: v["rangos"],
                    )
                )
        if actual.reviewed_source is None:
            campos.append(
                opcion(
                    "designar",
                    "Asignar objetos gráficamente antes de convertir",
                    [("Continuar", None)] + [(v, k) for k, v in ROLES.items()],
                )
            )
        self.preguntar(campos, datos, self._clasificar)
        return True

    def _clasificar(self, datos):
        from .conversion_plan import Classification

        actual = self.classification or Classification()
        revision = actual.reviewed_source
        ruta = datos["procedencia"].strip()
        if ruta.casefold() == "ninguna":
            revision = None
        elif ruta:
            revision = cargar_procedencia(ruta, require_document(self.ctx).doc)
        if revision is not None:
            revision.comprobar(require_document(self.ctx).doc)
        if datos["minimo"] > datos["maximo"]:
            raise ValueError("El espesor mínimo supera al máximo")
        rangos = {}
        if datos["rangos"]:
            for categoria in ("muros", "medianeras", "particiones"):
                limites = datos[categoria + ".minimo"], datos[categoria + ".maximo"]
                if limites[0] > limites[1]:
                    raise ValueError(categoria + ": el mínimo supera al máximo")
                rangos[categoria] = limites
        self.classification = Classification(
            {k[5:]: v for k, v in datos.items() if k.startswith("capa.") and v is not None},
            deepcopy(actual.handles),
            layers_confirmed=True,
            thickness_ranges=rangos,
            reviewed_source=revision,
        )
        self.height = datos["altura"]
        self.tmin = datos["minimo"]
        self.tmax = datos["maximo"]
        self.origin = datos["origen"]
        self.lineas["paralelismo"] = datos["paralelismo"]
        self.conversion_preview = None
        self.first = None
        self.pick_role = datos["designar"] if revision is None else None
        self.entity_picker = bool(self.pick_role)
        self._prompt()


def crear_variantes_conversion():
    return {ConversionTexto.name: ConversionTexto}

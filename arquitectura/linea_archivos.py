# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: rutas y conflictos por texto para exportar, sincronizar, importar y consultar la ayuda.
import json
from pathlib import Path

from tools.base import Tool
from .compat import require_document
from .linea_campos import Campo, ContextoLinea, PreguntasTexto
from .linea_fichas import opcion, texto

NOMBRES_ARCHIVOS = ("EXPORTARBIM", "SINCRONIZARARQ", "BIBLIOTECAHE", "AYUDAARQ")


class ArchivoTexto(PreguntasTexto, Tool):
    def start(self):
        self.name = type(self).name
        self.ctx = ContextoLinea(self.ctx)
        self._campos_texto = None
        if self.orden_original == "AYUDAARQ":
            from .ayuda import mostrar_ayuda
            from . import _VERSION

            mostrar_ayuda(self.ctx, _VERSION)
            self.ctx.finish()
        elif self.orden_original == "EXPORTARBIM":
            documento = require_document(self.ctx)
            ruta = Path(getattr(documento, "path", "") or "arquitectura.dxf").with_suffix(".arqbim")
            from .integrity import audit

            self._problemas = audit(documento.doc)
            campos = [texto("ruta", "Archivo de destino .arqbim")]
            if self._problemas:
                for problema in self._problemas:
                    self.ctx.echo(problema["text"])
                campos.append(
                    Campo("continuar", "Exportar omitiendo los elementos con problemas", "logico")
                )
            self.preguntar(campos, {"ruta": str(ruta), "continuar": False}, self._exportar)
        elif self.orden_original == "SINCRONIZARARQ":
            self.preguntar([texto("ruta", "Archivo .arqcambios")], {"ruta": ""}, self._leer_cambios)
        else:
            campos = [
                opcion(
                    "accion",
                    "Biblioteca térmica",
                    [(t.capitalize(), t) for t in ("estado", "importar", "buscar", "u")],
                ),
                texto("ruta", "Ruta del catálogo", lambda v: v["accion"] == "importar"),
                texto("consulta", "Texto o composición", lambda v: v["accion"] in ("buscar", "u")),
                opcion(
                    "posicion",
                    "Posición de la composición",
                    [("Vertical", ""), ("Techo", "techo"), ("Suelo", "suelo")],
                    lambda v: v["accion"] == "u",
                ),
            ]
            self.preguntar(
                campos,
                {"accion": "estado", "ruta": "", "consulta": "", "posicion": ""},
                self._biblioteca,
            )

    def _exportar(self, valores):
        from .bim_export import exportar_bim
        from .integrity import highlight

        if self._problemas and not valores["continuar"]:
            highlight(self.ctx, [h for problema in self._problemas for h in problema["handles"]])
            self.ctx.echo(
                "EXPORTARBIM cancelado: quedan seleccionados los elementos con problemas."
            )
            self.ctx.finish()
            return
        if not valores["ruta"].strip():
            raise ValueError("Indique un archivo de destino")
        try:
            exportar_bim(self.ctx, valores["ruta"])
        except OSError as error:
            self.ctx.echo("EXPORTARBIM: " + str(error))
            return self.start()
        self.ctx.finish()

    def _biblioteca(self, valores):
        from .biblioteca_termica import biblioteca_he

        accion = valores["accion"]
        if accion == "importar":
            if not valores["ruta"].strip():
                raise ValueError("Indique la ruta del catálogo")
            biblioteca_he(self.ctx, accion, valores["ruta"])
        elif accion in ("buscar", "u"):
            consulta = valores["consulta"]
            if accion == "u" and valores["posicion"]:
                consulta += " / " + valores["posicion"]
            biblioteca_he(self.ctx, accion, consulta)
        else:
            biblioteca_he(self.ctx)
        self.ctx.finish()

    def _leer_cambios(self, valores):
        from .roundtrip import leer_cambios, snapshot

        if not valores["ruta"].strip():
            raise ValueError("Indique un archivo de cambios")
        try:
            self._cambios, conflictos = leer_cambios(
                valores["ruta"], require_document(self.ctx).doc
            )
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise ValueError(str(error)) from error
        actual = snapshot(require_document(self.ctx).doc)
        campos = []
        decisiones = {}
        por_identidad = {c["id"]: c for c in self._cambios["changes"]}
        for identidad, motivo in conflictos.items():
            self.ctx.echo(identidad + ": " + motivo)
            if identidad in por_identidad:
                cambio = por_identidad[identidad]
                registro = actual["records"].get(identidad, {})
                for clave, pareja in cambio["fields"].items():
                    self.ctx.echo(
                        clave
                        + ": "
                        + json.dumps(
                            [pareja["old"], registro.get(clave), pareja["new"]], ensure_ascii=False
                        )
                    )
            else:
                self.ctx.echo(json.dumps(self._cambios["catalog"], ensure_ascii=False))
            opciones = [("Conservar IngeCAD", "keep")]
            if identidad == "catalog" or identidad in actual["records"]:
                opciones.append(("Aplicar IngeTrazo", "apply"))
            campos.append(opcion(identidad, "Decisión para " + identidad, opciones))
            decisiones[identidad] = "keep"
        self.preguntar(campos, decisiones, self._sincronizar)

    def _sincronizar(self, decisiones):
        from .roundtrip import terminar_sincronizacion

        terminar_sincronizacion(self.ctx, self._cambios, decisiones)
        self.ctx.finish()


def crear_variantes_archivos():
    return {
        "-"
        + nombre: type(
            nombre.title() + "PorLinea",
            (ArchivoTexto,),
            {"name": "-" + nombre, "orden_original": nombre, "__module__": __name__},
        )
        for nombre in NOMBRES_ARCHIVOS
    }

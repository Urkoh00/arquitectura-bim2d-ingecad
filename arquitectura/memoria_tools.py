# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: MEMORIACARP y su variante textual comparten campos, validación y transacciones.
from tools.base import Tool
from .linea_campos import PreguntasTexto, ContextoLinea
from .linea_fichas import campos_memoria, normalizar_memoria
from .compat import require_document
from . import memoria_plano


def formulario(ctx, datos):
    from PySide6.QtWidgets import QComboBox, QCheckBox, QFormLayout
    from .bim_dialogs import _dialog

    cuadro, disposicion, botones = _dialog(
        ctx,
        "Arquitectura — Memoria de carpintería",
        "Fichas y tabla desde las carpinterías BIM. Actualizar conserva posición y opciones de cada plano.",
    )
    campos = campos_memoria(ctx, datos)
    controles = {}
    forma = QFormLayout()
    disposicion.addLayout(forma)
    for campo in campos:
        if campo.tipo == "logico":
            control = QCheckBox()
            control.setChecked(datos[campo.clave])
        else:
            control = QComboBox()
            for etiqueta, valor in campo.opciones_de(datos):
                control.addItem(etiqueta, valor)
            control.setCurrentIndex(control.findData(datos[campo.clave]))
        controles[campo.clave] = control
        forma.addRow(campo.titulo, control)
    disposicion.addWidget(botones)

    def leer():
        valores = {
            campo.clave: (
                controles[campo.clave].isChecked()
                if campo.tipo == "logico"
                else controles[campo.clave].currentData()
            )
            for campo in campos
        }
        return normalizar_memoria(ctx, valores)

    def mostrar():
        valores = {
            campo.clave: (
                controles[campo.clave].isChecked()
                if campo.tipo == "logico"
                else controles[campo.clave].currentData()
            )
            for campo in campos
        }
        for campo in campos:
            controles[campo.clave].setVisible(campo.visible(valores))
            forma.labelForField(controles[campo.clave]).setVisible(campo.visible(valores))

    controles["accion"].currentIndexChanged.connect(mostrar)
    mostrar()
    cuadro._arq = controles
    return cuadro, leer


class MemoriaCarpTool(PreguntasTexto, Tool):
    name = "MEMORIACARP"
    solo_texto = False

    def start(self):
        self.name = type(self).name
        self._campos_texto = None
        self.configuracion = memoria_plano.configuracion_inicial(require_document(self.ctx))
        self.preparado = False
        if self.solo_texto:
            self.ctx = ContextoLinea(self.ctx)
            self._texto()
        else:
            self.prompt("MEMORIACARP [Ficha/Todo/Tabla/Fichas/Actualizar] <Ficha>:")

    def _texto(self):
        self.preguntar(
            campos_memoria(self.ctx, self.configuracion), self.configuracion, self._aceptar
        )

    def _ficha(self):
        from .bim_dialogs import available

        if not available(self.ctx):
            self._texto()
            return
        from PySide6.QtWidgets import QDialog

        cuadro, leer = formulario(self.ctx, self.configuracion)
        if cuadro.exec() != QDialog.Accepted:
            self.ctx.finish()
            return
        self._aceptar(leer())

    def _aceptar(self, valores):
        self.configuracion = normalizar_memoria(self.ctx, valores)
        if self.configuracion["accion"] == "actualizar":
            memoria_plano.actualizar(self.ctx)
            self.ctx.finish()
            return
        self.preparado = True
        self.prompt(self.name + ": punto de inserción del plano:")

    def on_enter(self):
        if self._campos_texto is not None:
            return super().on_enter()
        if not self.preparado:
            self._ficha()
        else:
            self.ctx.finish()

    def on_option(self, texto):
        if self._campos_texto is not None:
            return super().on_option(texto)
        palabra = str(texto).strip().casefold()
        if palabra == "actualizar":
            try:
                memoria_plano.actualizar(self.ctx)
            except (ValueError, RuntimeError) as error:
                self.ctx.echo(str(error))
            self.ctx.finish()
        elif palabra in ("todo", "tabla", "fichas", "ficha"):
            if palabra != "ficha":
                self.configuracion["modo"] = palabra
            if self.solo_texto:
                self._texto()
            else:
                self._ficha()
        else:
            # IngeCAD ofrece el texto a on_option antes de interpretarlo como punto.
            return False
        return True

    def on_point(self, punto):
        if self._campos_texto is not None:
            self.ctx.echo("Termine las opciones antes de indicar la inserción")
            return
        try:
            memoria_plano.generar(self.ctx, self.configuracion, punto)
        except (ValueError, RuntimeError) as error:
            self.ctx.echo("MEMORIACARP: " + str(error))
            return
        self.ctx.echo("Plano de carpintería generado. Actualizar conserva su posición.")
        self.ctx.finish()


class MemoriaCarpTexto(MemoriaCarpTool):
    name = "-MEMORIACARP"
    solo_texto = True

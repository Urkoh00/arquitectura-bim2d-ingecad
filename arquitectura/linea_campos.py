# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: preguntas de texto sin ventanas, con valores por defecto y entrada validada.
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import math
import re

_MEDIDA = re.compile(r"([+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:[eE][+-]?\d+)?)\s*(mm|cm|m|°)?", re.I)


def numero(texto, unidades=True, angular=False):
    """Las medidas de la orden se expresan en metros; los ángulos no llevan cm/mm."""
    coincidencia = _MEDIDA.fullmatch(str(texto).strip())
    if coincidencia is None:
        raise ValueError("Indique un número finito, con coma o punto")
    valor = float(coincidencia[1].replace(",", "."))
    unidad = (coincidencia[2] or "").lower()
    if unidad == "°" and not angular:
        raise ValueError("Este campo no es un ángulo")
    if unidad in ("mm", "cm", "m"):
        if not unidades:
            raise ValueError("Este campo no es una longitud")
        valor *= {"mm": 0.001, "cm": 0.01, "m": 1.0}[unidad]
    if not math.isfinite(valor):
        raise ValueError("Indique un número finito")
    return valor


def intervalos(texto):
    from .grids import distances

    partes = re.split(r"[;\s]+", str(texto).strip())
    resultado = []
    for parte in partes:
        factores = parte.lower().split("x")
        if len(factores) == 2:
            cantidad = numero(factores[0], unidades=False)
            if not cantidad.is_integer():
                raise ValueError("El número de intervalos debe ser entero")
            resultado.append(f"{int(cantidad)}x{numero(factores[1]):g}")
        elif len(factores) == 1:
            resultado.append(f"{numero(parte):g}")
        else:
            raise ValueError("Use separaciones con ; o n x distancia")
    salida = ";".join(resultado)
    distances(salida)
    return salida


@dataclass(frozen=True)
class Campo:
    clave: str
    titulo: str
    tipo: str = "texto"
    opciones: tuple = ()
    minimo: float | None = None
    maximo: float | None = None
    cuando: object = None

    def visible(self, valores):
        return self.cuando is None or self.cuando(valores)

    def opciones_de(self, valores):
        return self.opciones(valores) if callable(self.opciones) else self.opciones

    def leer(self, texto, valores=None):
        if self.tipo == "opcion":
            opciones = self.opciones_de(valores or {})
            entrada = str(texto).strip().casefold()
            if re.fullmatch(r"#\d+", entrada):
                indice = int(entrada[1:]) - 1
                if 0 <= indice < len(opciones):
                    return opciones[indice][1]
            coincidencias = [
                valor
                for etiqueta, valor in opciones
                if entrada in (str(etiqueta).casefold(), str(valor).casefold())
            ]
            if coincidencias:
                if any(valor != coincidencias[0] for valor in coincidencias):
                    raise ValueError("Nombre ambiguo: indique # y el número de la opción")
                return coincidencias[0]
            raise ValueError("Elija " + " / ".join(str(etiqueta) for etiqueta, _ in opciones))
        if self.tipo == "logico":
            if str(texto).casefold() in ("si", "sí", "s", "1", "true"):
                return True
            if str(texto).casefold() in ("no", "n", "0", "false"):
                return False
            raise ValueError("Indique Sí o No")
        if self.tipo == "intervalos":
            return intervalos(texto)
        if self.tipo in ("numero", "angulo", "entero", "real", "papel"):
            valor = numero(
                texto, unidades=self.tipo in ("numero", "papel"), angular=self.tipo == "angulo"
            )
            if self.tipo == "papel" and _MEDIDA.fullmatch(str(texto).strip())[2]:
                valor *= 1000.0
            if self.tipo == "entero":
                if not valor.is_integer():
                    raise ValueError("Indique un número entero")
                valor = int(valor)
            if self.minimo is not None and valor < self.minimo:
                raise ValueError(f"El valor mínimo es {self.minimo:g}")
            if self.maximo is not None and valor > self.maximo:
                raise ValueError(f"El valor máximo es {self.maximo:g}")
            return valor
        valor = str(texto).strip()
        return (
            valor[1:-1]
            if len(valor) >= 2 and valor.startswith('"') and valor.endswith('"')
            else valor
        )

    def mostrar(self, valor, valores=None):
        if self.tipo == "opcion":
            return next(
                (
                    str(etiqueta)
                    for etiqueta, dato in self.opciones_de(valores or {})
                    if dato == valor
                ),
                str(valor or ""),
            )
        if self.tipo == "logico":
            return "Sí" if valor else "No"
        if isinstance(valor, float):
            return f"{valor:g}".replace(".", ",")
        return "" if valor is None else str(valor)


class ContextoLinea:
    """Mantiene el contrato del contexto y desactiva las fichas solo en esta orden."""

    sin_dialogos = True

    def __init__(self, contexto):
        self._contexto = contexto

    def __getattr__(self, nombre):
        return getattr(self._contexto, nombre)

    @property
    def document(self):
        from .compat import document_of

        return document_of(self._contexto)

    @property
    def host(self):
        anfitrion = getattr(self._contexto, "host", None)
        if anfitrion is not None:
            return anfitrion
        return getattr(getattr(self._contexto, "services", None), "window", None)


class PreguntasTexto:
    """Mezcla de Tool: conserva los handlers nativos al terminar la ficha de texto."""

    @property
    def entity_picker(self):
        if getattr(self, "_campos_texto", None) is not None:
            return True
        if "_selector_solicitado" in self.__dict__:
            return self._selector_solicitado
        return super().entity_picker

    @entity_picker.setter
    def entity_picker(self, valor):
        self._selector_solicitado = bool(valor)

    def preguntar(self, campos, valores, aceptar, cambiar=None):
        self._campos_texto = list(campos)
        self._lista_campos_anterior = list(campos)
        self._valores_texto = deepcopy(valores)
        self._aceptar_texto = aceptar
        self._cambiar_texto = cambiar
        self._indice_texto = 0
        # Durante una pregunta literal, un nombre como «Centro» no es un osnap.
        self._avanzar_texto()

    def _avanzar_texto(self):
        while self._indice_texto < len(self._campos_texto):
            campo = self._campos_texto[self._indice_texto]
            if campo.visible(self._valores_texto):
                opciones = ""
                if campo.tipo == "opcion":
                    opciones = (
                        " ["
                        + "/".join(
                            f"#{i} {e}"
                            for i, (e, _) in enumerate(campo.opciones_de(self._valores_texto), 1)
                        )
                        + "]"
                    )
                defecto = campo.mostrar(self._valores_texto.get(campo.clave), self._valores_texto)
                self.prompt(f"{type(self).name}: {campo.titulo}{opciones} <{defecto}>:")
                return
            self._indice_texto += 1
        valores = deepcopy(self._valores_texto)
        aceptar = self._aceptar_texto
        self._campos_texto = None
        try:
            aceptar(valores)
        except (ValueError, TypeError) as error:
            self.ctx.echo(f"{type(self).name}: {error}")
            self._campos_texto = list(self._lista_campos_anterior)
            self._indice_texto = 0
            self._avanzar_texto()

    def on_option(self, texto):
        if getattr(self, "_campos_texto", None) is not None:
            if str(texto).casefold() == "anterior":
                self._indice_texto = max(0, self._indice_texto - 1)
                while self._indice_texto and not self._campos_texto[self._indice_texto].visible(
                    self._valores_texto
                ):
                    self._indice_texto -= 1
                self._avanzar_texto()
                return True
            return self._aceptar_campo(texto)
        return super().on_option(texto)

    def _aceptar_campo(self, texto):
        campo = self._campos_texto[self._indice_texto]
        try:
            valor = campo.leer(texto, self._valores_texto)
            self._guardar_valor(campo, valor)
        except (ValueError, TypeError) as error:
            self.ctx.echo(f"{type(self).name}: {error}")
            self._avanzar_texto()
            return True
        self._lista_campos_anterior = self._campos_texto
        self._indice_texto += 1
        self._avanzar_texto()
        return True

    def _guardar_valor(self, campo, valor):
        if self._cambiar_texto is not None:
            self._cambiar_texto(campo.clave, valor, self._valores_texto)
        self._valores_texto[campo.clave] = valor

    def on_enter(self):
        if getattr(self, "_campos_texto", None) is not None:
            campo = self._campos_texto[self._indice_texto]
            valor = self._valores_texto.get(campo.clave)
            try:
                # No se vuelve a interpretar una etiqueta: puede coincidir con otra
                # opción, contener comillas literales o perder precisión al mostrarse.
                if campo.tipo == "opcion":
                    if not any(valor == dato for _, dato in campo.opciones_de(self._valores_texto)):
                        raise ValueError("El valor por defecto no pertenece a las opciones")
                elif campo.tipo != "texto" and valor is not None:
                    valor = campo.leer(str(valor), self._valores_texto)
                self._guardar_valor(campo, valor)
            except (ValueError, TypeError) as error:
                self.ctx.echo(f"{type(self).name}: {error}")
                self._avanzar_texto()
                return True
            self._lista_campos_anterior = self._campos_texto
            self._indice_texto += 1
            self._avanzar_texto()
            return True
        return super().on_enter()

    def on_point(self, punto):
        if getattr(self, "_campos_texto", None) is not None:
            self.ctx.echo("Responda por texto o pulse Intro para aceptar el valor por defecto.")
            self._avanzar_texto()
            return
        return super().on_point(punto)

    def wants_raw_text(self):
        if getattr(self, "_campos_texto", None) is not None:
            return True
        return super().wants_raw_text()

    def tab_ready(self):
        if getattr(self, "_campos_texto", None) is not None:
            return False
        preparar = getattr(super(), "tab_ready", None)
        return preparar() if callable(preparar) else False

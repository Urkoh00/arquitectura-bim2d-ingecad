# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: formatea medidas para el dibujo sin alterar los valores geométricos.
import math

# Holgura, en fracciones de la última cifra, para que una medida que vale la
# mitad exacta (0,885 a centímetros) se escriba siempre por exceso, aunque los
# cálculos la hayan dejado en 0,88499999… Solo afecta al texto, nunca a la geometría.
_HOLGURA = 1e-6


def decimales(documento=None):
    from .parameters_arq import general_options

    return 3 if general_options(documento).get("precision_medidas", "cm") == "mm" else 2


def longitud(valor, documento=None):
    cifras = decimales(documento)
    valor = float(valor)
    unidades = math.floor(abs(valor) * 10**cifras + 0.5 + _HOLGURA)
    signo = "-" if valor < 0 and unidades else ""
    entero, fraccion = divmod(unidades, 10**cifras)
    return f"{signo}{entero},{fraccion:0{cifras}d}"


def anulaciones_cota(documento):
    return {"dimdec": decimales(documento), "dimdsep": ord(","), "dimzin": 0, "dimlfac": 1.0}

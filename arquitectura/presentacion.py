# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: formatea medidas para el dibujo sin alterar los valores geométricos.


def decimales(documento=None):
    from .parameters_arq import general_options

    return 3 if general_options(documento).get("precision_medidas", "cm") == "mm" else 2


def longitud(valor, documento=None):
    return f"{float(valor):.{decimales(documento)}f}".replace(".", ",")


def anulaciones_cota(documento):
    return {"dimdec": decimales(documento), "dimdsep": ord(","), "dimzin": 0, "dimlfac": 1.0}

# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: perfiles de trabajo (Planos 2D, Modelo BIM, Modelo Térmico). Deciden qué
#   órdenes se ofrecen, qué campos muestran las fichas y qué avisa ARQVALIDAR; nunca
#   cambian lo que se guarda: un muro es el mismo objeto BIM en los tres perfiles.
"""Perfiles de trabajo del plugin (decisión del propietario, 25-11-2026).

* **Planos 2D** (``planos``, por defecto): planta acotada, superficies, secciones,
  alzados y plano de carpintería. Sin exportación ni datos térmicos.
* **Modelo BIM** (``bim``): añade la exportación a IngeTrazo e IFC y la
  sincronización de cambios.
* **Modelo Térmico** (``termico``): añade los catálogos térmicos y constructivos,
  los usos del edificio, la clasificación normativa de los recintos y la cara
  exterior y el orden de capas de los muros.

Los perfiles son acumulativos. Los elementos se crean igual en todos: subir de
perfil no obliga a redibujar, y ARQVALIDAR dice qué falta para el nuevo.

La versión 1.0 publica solo **Planos 2D** (``PUBLICADOS``). La variable de entorno
``ARQ_PERFIL`` fuerza otro perfil para el desarrollo y las pruebas.

El perfil se lee al cargar el plugin: los menús y la barra de IngeCAD 0.8.0 son
fijos una vez cargado (no hay forma pública de ocultar una entrada después).
"""
import os

PLANOS, BIM, TERMICO = "planos", "bim", "termico"
ORDEN = (PLANOS, BIM, TERMICO)
NOMBRES = {PLANOS: "Planos 2D", BIM: "Modelo BIM", TERMICO: "Modelo Térmico"}
POR_DEFECTO = PLANOS

#: Perfiles que ofrece esta versión publicada.
PUBLICADOS = (PLANOS,)

#: Perfil mínimo de cada orden que no es de Planos 2D. Sus variantes con guion
#: («-EXPORTARBIM») siguen a la orden.
MINIMO = {
    "EXPORTARBIM": BIM,
    "SINCRONIZARARQ": BIM,
    "USOSARQ": TERMICO,
    "BIBLIOTECAHE": TERMICO,
    "CATALOGOEC": TERMICO,
}


def perfil_activo():
    """``ARQ_PERFIL`` si es un perfil válido; si no, el perfil por defecto."""
    valor = str(os.environ.get("ARQ_PERFIL", "")).strip().lower()
    valor = {"térmico": TERMICO, "planos2d": PLANOS}.get(valor, valor)
    return valor if valor in ORDEN else POR_DEFECTO


def incluye(perfil, necesario):
    """¿El perfil ``perfil`` contiene lo del perfil ``necesario``?"""
    return ORDEN.index(perfil) >= ORDEN.index(necesario)


def minimo_de(orden):
    return MINIMO.get(str(orden).lstrip("-").upper(), PLANOS)


def disponible(orden, perfil=None):
    return incluye(perfil or perfil_activo(), minimo_de(orden))


def mensaje_no_disponible(orden, perfil=None):
    perfil = perfil or perfil_activo()
    necesario = minimo_de(orden)
    nombre = str(orden).upper()
    if necesario not in PUBLICADOS:
        return (f"{nombre}: forma parte del perfil {NOMBRES[necesario]}, que llegará en una "
                f"versión posterior. Esta versión trabaja con el perfil {NOMBRES[perfil]}.")
    return (f"{nombre}: forma parte del perfil {NOMBRES[necesario]}; el perfil activo es "
            f"{NOMBRES[perfil]}.")


def orden_no_disponible(nombre):
    """Orden que sustituye a otra fuera del perfil: lo explica y no hace nada."""
    def orden(ctx, *args):
        ctx.echo(mensaje_no_disponible(nombre))
    orden.__name__ = "no_disponible_" + nombre.lstrip("-").lower()
    return orden


def filtrar_menu(entradas, perfil=None):
    """Quita del menú las órdenes fuera del perfil y los submenús que quedan
    vacíos; conserva separadores sin dejar dos seguidos ni uno al final."""
    from core.plugins import SEPARATOR, Submenu
    perfil = perfil or perfil_activo()
    salida = []
    for entrada in entradas:
        if entrada == SEPARATOR:
            if salida and salida[-1] != SEPARATOR:
                salida.append(entrada)
            continue
        if isinstance(entrada, Submenu):
            hijos = filtrar_menu(entrada.items, perfil)
            if any(h != SEPARATOR for h in hijos):
                salida.append(Submenu(entrada.label, tuple(hijos)))
            continue
        if disponible(entrada.command, perfil):
            salida.append(entrada)
    while salida and salida[-1] == SEPARATOR:
        salida.pop()
    return tuple(salida)


def filtrar_barra(entradas, perfil=None):
    perfil = perfil or perfil_activo()
    return tuple(e for e in entradas if disponible(e.command, perfil))


def filtrar_ordenes(herramientas, comandos, perfil=None):
    """Las órdenes fuera del perfil se sustituyen por una que lo explica: quien
    la escriba sabe por qué no se ejecuta, en vez de «orden desconocida»."""
    perfil = perfil or perfil_activo()
    fuera = [n for n in herramientas if not disponible(n, perfil)]
    herramientas = {n: t for n, t in herramientas.items() if disponible(n, perfil)}
    comandos = {n: (c if disponible(n, perfil) else orden_no_disponible(n))
                for n, c in comandos.items()}
    for nombre in fuera:                     # p. ej. la variante «-EXPORTARBIM»
        comandos[nombre] = orden_no_disponible(nombre)
    return herramientas, comandos

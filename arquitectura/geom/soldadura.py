# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: une los vértices que están a menos de una tolerancia, sin las
#   fronteras de redondeo de round(); lo usan el generador de sólidos y el
#   validador de contratos de la extensión.
#   (Guía del código: docs/GUIA_DEL_CODIGO.md)
"""Soldadura de vértices con tolerancia.

Redondear las coordenadas no sirve para decidir si dos puntos son el mismo:
dos valores separados por 1e-10 m quedan a ambos lados de una frontera de
redondeo (…,xxxxxxx5) y dan claves distintas. Lejos del origen y con muros
girados ocurre de verdad: 700006,93538245 y 700006,9353824501 son el mismo
vértice calculado por dos caminos, y round(·, 7) los separa, de modo que un
sólido cerrado parecía abierto.

La soldadura compara con tolerancia: divide el espacio en celdas del tamaño
de la tolerancia y busca el representante en la celda del punto y en sus 26
vecinas, así que dos puntos más cerca que la tolerancia se unen siempre,
estén donde estén. El primer punto de cada grupo es el representante, de
modo que el resultado es determinista para un mismo orden de entrada.
"""
from __future__ import annotations

import math

#: tolerancia por defecto, en metros (una décima de micra)
TOLERANCIA = 1e-7


class Soldador:
    """Asigna a cada punto el representante de su grupo.

    ``punto(v)`` devuelve el primer punto registrado a menos de
    ``tolerancia`` en cada coordenada, o registra ``v`` como nuevo
    representante. ``indice(v)`` devuelve el número del representante, útil
    como clave de vértice."""

    def __init__(self, tolerancia: float = TOLERANCIA):
        if not (tolerancia > 0 and math.isfinite(tolerancia)):
            raise ValueError("La tolerancia de soldadura debe ser positiva")
        self.tolerancia = tolerancia
        self._celdas: dict = {}
        self.representantes: list = []

    def _celda(self, v):
        t = self.tolerancia
        return tuple(math.floor(c / t) for c in v)

    def indice(self, v) -> int:
        v = tuple(v)
        cx, cy, cz = self._celda(v)
        t = self.tolerancia
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for i in self._celdas.get((cx + dx, cy + dy, cz + dz), ()):
                        r = self.representantes[i]
                        if all(abs(a - b) <= t for a, b in zip(v, r)):
                            return i
        i = len(self.representantes)
        self.representantes.append(v)
        self._celdas.setdefault((cx, cy, cz), []).append(i)
        return i

    def punto(self, v):
        return self.representantes[self.indice(v)]

# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: clasificación constructiva explícita, guardada en el dibujo y compartible sin CAD.
"""La clase no se deduce del nombre ni de propiedades térmicas."""
from .capas_envolvente import CLASES_MATERIAL


ETIQUETAS = (("Sin clasificar", ""), ("Aislante", "aislante"),
             ("Fábrica", "fabrica"), ("Hoja", "hoja"),
             ("Revestimiento", "revestimiento"), ("Trasdosado", "trasdosado"),
             ("Cámara", "camara"))


def validar(clases):
    if not isinstance(clases, dict):
        raise ValueError('La clasificación de materiales debe ser un catálogo')
    vistos = set()
    salida = {}
    for nombre, clase in clases.items():
        if not isinstance(nombre, str) or not nombre.strip():
            raise ValueError('Material sin nombre')
        nombre = nombre.strip()
        clave = nombre.casefold()
        if clave in vistos:
            raise ValueError('Material duplicado en la clasificación constructiva: ' + nombre)
        vistos.add(clave)
        if clase not in CLASES_MATERIAL:
            raise ValueError('Clase constructiva no válida: ' + str(clase))
        salida[nombre] = clase
    return salida


def nombres(valores):
    materiales = set(valores.get('general', {}).get('materiales_constructivos', {}))
    for tipo in valores.get('wall_types', []):
        materiales.update(str(material) for _espesor, material in tipo.get('layers', []))
    return sorted(materiales, key=str.casefold)


def catalogo(clases):
    return {'materiales': {nombre: {'clase_constructiva': clase}
                           for nombre, clase in validar(clases).items()}}

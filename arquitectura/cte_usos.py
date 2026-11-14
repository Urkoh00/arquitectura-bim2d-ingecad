# SPDX-License-Identifier: GPL-3.0-or-later
"""Normative classification of a space (IfcSpace) under the Spanish building code
(CTE) and the low-voltage regulation (ITC-BT-25).

Each set («conjunto») is one document of the code; a space takes at most ONE
label of each set, chosen by the operator. The labels are the categories the
documents themselves use (their tables of uses, protected / habitable rooms,
lighting zones…). They classify; they do not check compliance: no value here
says that a space meets the code.

``propose(use)`` suggests labels from the room's ordinary use (Dormitorio,
Cocina…) for a dwelling; the operator confirms or changes them in the sheet.
"""
from __future__ import annotations

#: (key, title, labels) in the order of the sheet
CONJUNTOS = (
    ("SI", "CTE DB SI. Seguridad en caso de incendio (uso y ocupación)", (
        "Cualquiera (Zonas de ocupación ocasional)",
        "Cualquiera (Aseos de planta)",
        "Residencial vivienda (Plantas de vivienda)",
        "Residencial público (Zonas de alojamiento)",
        "Residencial público (Salones de uso múltiple)",
        "Residencial público (Uso público: sótano, planta baja y entreplanta)",
        "Aparcamiento (Actividad sujeta a horarios)",
        "Aparcamiento (En otros casos)",
        "Administrativo (Plantas o zonas de oficinas)",
        "Administrativo (Vestíbulos generales y zonas de uso público)",
        "Docente (Conjunto de la planta o del edificio)",
        "Docente (Locales diferentes de aulas)",
        "Docente (Aulas)",
        "Docente (Aulas de escuelas infantiles)",
        "Docente (Aulas de enseñanza primaria)",
        "Docente (Aulas de enseñanza secundaria)",
        "Docente (Salas de lectura de bibliotecas)",
        "Hospitalario (Salas de espera)",
        "Hospitalario (Zonas de hospitalización)",
        "Hospitalario (Servicios ambulatorios y de diagnóstico)",
        "Hospitalario (Tratamiento a pacientes internados)",
        "Comercial (Áreas de ventas: sótano, planta baja y entreplanta)",
        "Comercial (Áreas de venta: otras plantas)",
        "Comercial (Zonas comunes de centros comerciales)",
        "Comercial (Centros comerciales: plantas con acceso exterior)",
        "Comercial (Centros comerciales: otras plantas)",
        "Comercial (Áreas con poco público)",
        "Pública concurrencia (Zonas de espectadores, con asientos definidos)",
        "Pública concurrencia (Zonas de espectadores, sin asientos definidos)",
        "Pública concurrencia (Zonas de espectadores de pie)",
        "Pública concurrencia (Zonas de público en discotecas)",
        "Pública concurrencia (Zonas de público de pie, en bares, cafetería, etc.)",
        "Pública concurrencia (Zonas de público en gimnasio con aparatos)",
        "Pública concurrencia (Zonas de público en gimnasio sin aparatos)",
        "Pública concurrencia (Piscinas, zonas de baño)",
        "Pública concurrencia (Piscinas descubiertas, zonas de estancia)",
        "Pública concurrencia (Piscinas públicas, vestuarios)",
        "Pública concurrencia (Salones de uso múltiple)",
        "Pública concurrencia (Restaurantes de «comida rápida»)",
        "Pública concurrencia (Bares, cafeterías, restaurantes, etc.)",
        "Pública concurrencia (Salas de espera, salas de lectura, etc.)",
        "Pública concurrencia (Uso público: sótano, planta baja y entreplanta)",
        "Pública concurrencia (Vestíbulos, vestuarios, etc.)",
        "Pública concurrencia (Zonas de público en terminales de transporte)",
        "Pública concurrencia (Zonas de servicio de bares, restaurantes, cafeterías, etc.)",
        "Archivos, almacenes",
    )),
    ("SUA4", "CTE DB SUA 4. Seguridad frente al riesgo causado por iluminación inadecuada", (
        "Alumbrado normal (Zonas de circulación interiores)",
        "Alumbrado normal (Zonas de circulación exteriores)",
        "Alumbrado normal (Aparcamientos interiores)",
        "Alumbrado de emergencia (Aparcamientos)",
        "Alumbrado de emergencia (Locales de riesgo especial, según CTE DB-SI 1)",
        "Alumbrado de emergencia (Recintos cuya ocupación es mayor a 100 personas)",
        "Alumbrado de emergencia (Aseos generales de planta en edificios de uso público)",
    )),
    ("SUA9_RECINTO", "CTE DB SUA 9. Accesibilidad. Uso del recinto", (
        "Vestíbulo", "Pasillo", "Salón", "Dormitorio", "Cocina", "Aseo", "Terraza", "Vestuario",
    )),
    ("SUA9_UNIDAD", "CTE DB SUA 9. Accesibilidad. Unidad de uso", (
        "Vivienda accesible", "Alojamiento accesible", "Servicio higiénico accesible",
    )),
    ("HE", "CTE DB HE. Ahorro de energía", (
        "Habitable (Zona acondicionada)", "Habitable (Zona no acondicionada)", "No habitable",
    )),
    ("HE3", "CTE DB HE 3. Condiciones de las instalaciones de iluminación", (
        "Administrativo en general",
        "Andenes de estaciones de transporte",
        "Pabellones de exposición o ferias",
        "Salas de diagnóstico",
        "Aulas y laboratorios",
        "Habitaciones de hospital",
        "Otros recintos interiores",
        "Zonas comunes",
        "Almacenes, archivos, salas técnicas y cocinas",
        "Aparcamientos",
        "Espacios deportivos",
        "Estaciones de transporte",
        "Supermercados, hipermercados y grandes almacenes",
        "Bibliotecas, museos y galerías de arte",
        "Zonas comunes en edificios no residenciales",
        "Centros comerciales",
        "Hostelería y restauración",
        "Religioso en general",
        "Salones de actos, auditorios, salas de usos múltiples y convenciones, de ocio o "
        "espectáculo, de reuniones y de conferencias",
        "Tiendas y pequeño comercio",
        "Habitaciones de hoteles, hostales…",
        "Locales con nivel de iluminación superior a 600 lux",
    )),
    ("HR", "CTE DB HR. Protección frente al ruido", (
        "Protegido (Dormitorio)", "Protegido (Aula)", "Protegido (Sala de conferencias)",
        "Protegido (Restaurante)", "Protegido (Oficina)", "Protegido (Despacho)",
        "Protegido (Estancia)", "Habitable", "Habitable (Zona común)", "Habitable (Escalera)",
        "De actividad", "Garaje", "De instalaciones", "Hueco de ascensor",
    )),
    ("HS2", "CTE DB HS 2. Recogida y evacuación de residuos", (
        "Almacén de contenedores",
    )),
    ("HS3", "CTE DB HS 3. Calidad del aire interior", (
        "Salas de estar y comedores", "Dormitorio principal", "Resto de dormitorios",
        "Locales húmedos", "Trasteros y sus zonas comunes", "Aparcamientos y garajes",
        "Almacenes de residuos",
    )),
    ("HS6", "CTE DB HS 6. Protección frente a la exposición al radón", (
        "Habitable", "No habitable",
    )),
    ("ITC_BT_25", "ITC-BT-25. Instalaciones interiores en viviendas. Puntos de utilización", (
        "Acceso", "Vestíbulo", "Sala de estar o Salón", "Dormitorios", "Baños",
        "Pasillos o distribuidores", "Cocina", "Terrazas y Vestidores",
        "Garajes unifamiliares y Otros",
    )),
)

KEYS = tuple(k for k, _t, _l in CONJUNTOS)
TITLES = {k: t for k, t, _l in CONJUNTOS}
LABELS = {k: l for k, _t, l in CONJUNTOS}

# Suggestions for a DWELLING from the room's ordinary use (bim_dialogs.ROOM_USES).
# Only what follows unambiguously from the use; the rest is left to the operator.
_VIVIENDA = {
    "estar": {"SUA9_RECINTO": "Salón", "HR": "Protegido (Estancia)",
              "HS3": "Salas de estar y comedores", "ITC_BT_25": "Sala de estar o Salón"},
    "comedor": {"SUA9_RECINTO": "Salón", "HR": "Protegido (Estancia)",
                "HS3": "Salas de estar y comedores", "ITC_BT_25": "Sala de estar o Salón"},
    "estar-comedor": {"SUA9_RECINTO": "Salón", "HR": "Protegido (Estancia)",
                      "HS3": "Salas de estar y comedores", "ITC_BT_25": "Sala de estar o Salón"},
    "dormitorio": {"SUA9_RECINTO": "Dormitorio", "HR": "Protegido (Dormitorio)",
                   "HS3": "Resto de dormitorios", "ITC_BT_25": "Dormitorios"},
    "dormitorio principal": {"SUA9_RECINTO": "Dormitorio", "HR": "Protegido (Dormitorio)",
                             "HS3": "Dormitorio principal", "ITC_BT_25": "Dormitorios"},
    "cocina": {"SUA9_RECINTO": "Cocina", "HR": "Habitable", "HS3": "Locales húmedos",
               "ITC_BT_25": "Cocina"},
    "baño": {"SUA9_RECINTO": "Aseo", "HR": "Habitable", "HS3": "Locales húmedos",
             "ITC_BT_25": "Baños"},
    "aseo": {"SUA9_RECINTO": "Aseo", "HR": "Habitable", "HS3": "Locales húmedos",
             "ITC_BT_25": "Baños"},
    "lavadero": {"HR": "Habitable", "HS3": "Locales húmedos", "ITC_BT_25": "Garajes unifamiliares y Otros"},
    "vestíbulo": {"SUA9_RECINTO": "Vestíbulo", "HR": "Habitable", "ITC_BT_25": "Vestíbulo"},
    "pasillo": {"SUA9_RECINTO": "Pasillo", "HR": "Habitable", "ITC_BT_25": "Pasillos o distribuidores"},
    "distribuidor": {"SUA9_RECINTO": "Pasillo", "HR": "Habitable",
                     "ITC_BT_25": "Pasillos o distribuidores"},
    "despacho": {"HR": "Protegido (Despacho)", "ITC_BT_25": "Garajes unifamiliares y Otros"},
    "trastero": {"HE": "No habitable", "HS3": "Trasteros y sus zonas comunes", "HS6": "No habitable",
                 "ITC_BT_25": "Garajes unifamiliares y Otros"},
    "despensa": {"HE": "No habitable", "HS6": "No habitable"},
    "garaje": {"SI": "Aparcamiento (En otros casos)", "HE": "No habitable", "HR": "Garaje",
               "HS3": "Aparcamientos y garajes", "HS6": "No habitable",
               "ITC_BT_25": "Garajes unifamiliares y Otros"},
    "terraza": {"SUA9_RECINTO": "Terraza", "ITC_BT_25": "Terrazas y Vestidores"},
    "tendedero": {"ITC_BT_25": "Terrazas y Vestidores"},
    "porche": {"ITC_BT_25": "Terrazas y Vestidores"},
    "escalera": {"HR": "Habitable (Escalera)"},
}
_HABITABLE = {"estar", "comedor", "estar-comedor", "dormitorio", "dormitorio principal", "cocina",
              "baño", "aseo", "vestíbulo", "pasillo", "distribuidor", "despacho", "escalera"}


def propose(use, residential=True):
    """{set: label} suggested for a room of that use. Only for dwellings
    (``residential``); elsewhere the operator chooses (the code's tables depend
    on the activity, not on the room's name)."""
    key = str(use or "").strip().lower()
    if not residential or key not in _VIVIENDA:
        return {}
    out = {"SI": "Residencial vivienda (Plantas de vivienda)"} if key not in ("garaje",) else {}
    if key in _HABITABLE:
        out.update(HE="Habitable (Zona acondicionada)", HS6="Habitable")
    out.update(_VIVIENDA[key])
    return validate(out)


def validate(labels):
    """The labels kept: known sets and labels only, empty ones dropped.
    ValueError on an unknown set or a label that is not of its set."""
    out = {}
    for k, v in dict(labels or {}).items():
        if v in (None, ""):
            continue
        if k not in LABELS:
            raise ValueError(f"conjunto normativo desconocido: {k}")
        if v not in LABELS[k]:
            raise ValueError(f"«{v}» no es una etiqueta de {TITLES[k]}")
        out[k] = v
    return out


def pset(labels):
    """Property set for the IFC export: one property per set, in sheet order."""
    v = validate(labels)
    return {k: v[k] for k in KEYS if k in v}

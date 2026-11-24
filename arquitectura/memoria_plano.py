# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: conserva y actualiza el plano derivado de carpintería como una transacción deshacible.
from copy import deepcopy
import hashlib
import json
import uuid

from core.commands import Command
from .architectural import metadata, _xdata, reenlazar
from . import memoria_modelo
from .memoria_dibujo import CAPA_PLANO, CAPA_COTAS, DISCONTINUA

CAPA_ROTULOS = "ARQ-CARPINTERIA-MARCAS"
VERSION = 1


def planos(dibujo):
    return [
        (entidad, datos)
        for entidad in dibujo.modelspace()
        if (datos := metadata(entidad) or {}).get("kind") == "carpentry_schedule"
    ]


def insercion_actual(entidad, datos):
    """Posición del plano para Actualizar: la del punto ancla, que acompaña al
    dibujo cuando el usuario lo desplaza; la guardada solo si falta."""
    try:
        punto = entidad.dxf.location
        return (float(punto.x), float(punto.y))
    except AttributeError:
        return tuple(map(float, datos["insert"][:2]))


def configuracion_inicial(documento):
    from .parameters_arq import general_options

    return {
        "accion": "generar",
        "modo": "todo",
        "planta": "all",
        "agrupar": "marca",
        "escala": general_options(documento)["escala"],
        "huecos": True,
        "rotulos": True,
        "seccion": True,
    }


def biblioteca():
    from .biblioteca_termica import cargar

    try:
        return cargar()
    except (OSError, ValueError):
        return None


def huella_termica(datos):
    fuente = {clave: (datos or {}).get(clave, {}) for clave in ("vidrios", "marcos")}
    texto = json.dumps(fuente, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(texto.encode()).hexdigest()


def avisos(dibujo):
    existentes = planos(dibujo)
    if not existentes:
        return []
    fuente = memoria_modelo.estado_fuentes(dibujo)
    termica = huella_termica(biblioteca())
    resultado = []
    entidades = list(dibujo.modelspace())
    for _, datos in existentes:
        identificador = datos["id"]
        cantidad = sum(
            (metadata(entidad) or {}).get("schedule_id") == identificador for entidad in entidades
        )
        if datos.get("source_hash") != fuente or datos.get("thermal_hash") != termica:
            resultado.append(
                "Memoria de carpintería desactualizada: ejecute MEMORIACARP Actualizar"
            )
        if cantidad != datos.get("detail_count"):
            resultado.append("Memoria de carpintería incompleta: ejecute MEMORIACARP Actualizar")
    return sorted(set(resultado))


def resumen_filas(filas):
    return [
        {
            clave: deepcopy(valor)
            for clave, valor in fila.items()
            if clave not in ("piezas", "medidas", "definicion")
        }
        | {
            "ancho": fila["medidas"]["ancho"],
            "alto": fila["medidas"]["alto"],
            "hojas": fila["medidas"]["hojas"],
            "apertura": fila["definicion"]["operation"],
            "materiales": fila["definicion"]["materiales"],
        }
        for fila in filas
    ]


class PlanoMemoria(Command):
    name = "ARQ PLANO DE CARPINTERÍA"
    needs_regen = True

    def __init__(self, configuracion, insercion, entidad=None):
        self.configuracion = deepcopy(configuracion)
        self.insercion = tuple(map(float, insercion[:2]))
        self.entidad = entidad
        self.identificador = metadata(entidad)["id"] if entidad is not None else uuid.uuid4().hex
        self.nombre_grupo = "ARQMEM_" + self.identificador
        self.nuevos = None
        self.bloques = {}
        self.aplicado = False

    def _capas(self, dibujo):
        for nombre, color in ((CAPA_PLANO, 7), (CAPA_COTAS, 2), (CAPA_ROTULOS, 6)):
            if nombre not in dibujo.layers:
                capa = dibujo.layers.new(nombre, dxfattribs={"color": color})
                if nombre != CAPA_ROTULOS:
                    capa.lock()
                self.capas_creadas.append(nombre)
        if DISCONTINUA not in dibujo.linetypes:
            dibujo.linetypes.new(
                DISCONTINUA,
                dxfattribs={
                    "description": "Proyección del antepecho",
                    "pattern": [0.12, 0.08, -0.04],
                },
            )
            self.crea_discontinua = True

    def _grupo(self, dibujo, entidades):
        if self.nombre_grupo not in dibujo.groups:
            dibujo.groups.new(self.nombre_grupo)
        dibujo.groups.get(self.nombre_grupo).set_data(entidades)

    def do(self, documento):
        from .memoria_dibujo import dibujar
        from .memoria_carpinteria import asignar_marcas

        dibujo = documento.doc
        espacio = dibujo.modelspace()
        self.capas_creadas = []
        self.crea_discontinua = False
        inicial = self.nuevos is None
        if inicial:
            self.anteriores = [
                entidad
                for entidad in espacio
                if (metadata(entidad) or {}).get("schedule_id") == self.identificador
            ]
            self.datos_anteriores = (
                deepcopy(metadata(self.entidad)) if self.entidad is not None else None
            )
            self.grupo_anterior = self.nombre_grupo in dibujo.groups
            self.nuevos = []
        originales = {entidad.dxf.handle for entidad in espacio}
        nombres_bloques = set(dibujo.blocks.block_names())
        try:
            self._capas(dibujo)
            if self.nombre_grupo in dibujo.groups:
                dibujo.groups.get(self.nombre_grupo).clear()
            for entidad in self.anteriores:
                if entidad.is_alive and entidad.dxf.owner is not None:
                    espacio.unlink_entity(entidad)
            if inicial:
                _, catalogo = memoria_modelo.catalogo(dibujo)
                grupos, _ = asignar_marcas(memoria_modelo.leer(dibujo), catalogo)
                termica = biblioteca()
                filas = memoria_modelo.filas(grupos, self.configuracion, termica)
                if not filas and self.datos_anteriores is None:
                    raise ValueError("No hay carpinterías en el ámbito elegido")
                dibujar(documento, filas, self.insercion, self.configuracion, self.identificador)
                self.nuevos = [
                    entidad for entidad in espacio if entidad.dxf.handle not in originales
                ]
                self.datos_nuevos = {
                    "kind": "carpentry_schedule",
                    "schema": 1,
                    "version": VERSION,
                    "id": self.identificador,
                    "config": self.configuracion,
                    "insert": list(self.insercion),
                    "source_hash": memoria_modelo.estado_fuentes(dibujo),
                    "thermal_hash": huella_termica(termica),
                    "detail_count": len(self.nuevos),
                    "rows": resumen_filas(filas),
                }
                if self.entidad is None:
                    self.entidad = espacio.add_point(
                        (*self.insercion, 0.0), dxfattribs={"layer": CAPA_PLANO, "invisible": 1}
                    )
                self.bloques = {
                    nombre: [pieza.copy() for pieza in dibujo.blocks.get(nombre)]
                    for nombre in set(dibujo.blocks.block_names()) - nombres_bloques
                }
            else:
                for nombre, piezas in self.bloques.items():
                    if nombre not in dibujo.blocks:
                        bloque = dibujo.blocks.new(nombre)
                        for pieza in piezas:
                            bloque.add_entity(pieza.copy())
                for entidad in self.nuevos:
                    reenlazar(espacio, entidad)
                if self.datos_anteriores is None:
                    reenlazar(espacio, self.entidad)
            _xdata(espacio, self.entidad, self.datos_nuevos)
            self._grupo(dibujo, [self.entidad, *self.nuevos])
            self.aplicado = True
            documento.dirty = True
        except Exception:
            # También se recogen entidades creadas por un render que haya fallado a medias.
            self.nuevos = [
                entidad
                for entidad in espacio
                if entidad.dxf.handle not in originales and entidad is not self.entidad
            ]
            self.bloques = {
                nombre: [] for nombre in set(dibujo.blocks.block_names()) - nombres_bloques
            }
            self.aplicado = True
            self.undo(documento)
            self.nuevos = None
            raise

    def undo(self, documento):
        if not self.aplicado:
            return
        dibujo = documento.doc
        espacio = dibujo.modelspace()
        if self.nombre_grupo in dibujo.groups:
            dibujo.groups.get(self.nombre_grupo).clear()
            if not self.grupo_anterior:
                dibujo.groups.delete(self.nombre_grupo)
        for entidad in self.nuevos:
            if entidad.is_alive and entidad.dxf.owner is not None:
                espacio.unlink_entity(entidad)
        if self.datos_anteriores is None:
            if self.entidad is not None and self.entidad.dxf.owner is not None:
                espacio.unlink_entity(self.entidad)
        else:
            _xdata(espacio, self.entidad, self.datos_anteriores)
        for entidad in self.anteriores:
            reenlazar(espacio, entidad)
        if self.grupo_anterior:
            self._grupo(dibujo, [self.entidad, *self.anteriores])
        for nombre in self.bloques:
            if nombre in dibujo.blocks:
                dibujo.blocks.delete_block(nombre, safe=False)
        if self.crea_discontinua and DISCONTINUA in dibujo.linetypes:
            dibujo.linetypes.remove(DISCONTINUA)
        for nombre in reversed(self.capas_creadas):
            dibujo.layers.remove(nombre)
        self.removed_handles = [entidad.dxf.handle for entidad in self.nuevos]
        self.aplicado = False
        documento.dirty = True


def generar(ctx, configuracion, insercion):
    from .compat import require_document
    from .transactions import SafeArchitecturalCommand, apply_architectural_change

    documento = require_document(ctx)
    _, marcas = memoria_modelo.preparar(documento.doc)
    plano = PlanoMemoria(configuracion, insercion)
    apply_architectural_change(
        ctx, SafeArchitecturalCommand("MEMORIACARP", [marcas, plano]), kind="opening"
    )
    return plano


def actualizar(ctx):
    from .compat import require_document
    from .transactions import SafeArchitecturalCommand, apply_architectural_change

    documento = require_document(ctx)
    existentes = planos(documento.doc)
    if not existentes:
        ctx.echo("No hay un plano de carpintería que actualizar")
        return None
    _, marcas = memoria_modelo.preparar(documento.doc)
    cambios = [
        PlanoMemoria(datos["config"], insercion_actual(entidad, datos), entidad)
        for entidad, datos in existentes
    ]
    apply_architectural_change(
        ctx, SafeArchitecturalCommand("MEMORIACARP Actualizar", [marcas, *cambios]), kind="opening"
    )
    return cambios


def crear_rotulos(documento):
    dibujo = documento.doc
    configuraciones = [
        datos["config"] for _, datos in planos(dibujo) if datos["config"].get("rotulos")
    ]
    if not configuraciones:
        return []
    from .memoria_carpinteria import asignar_marcas

    _, catalogo = memoria_modelo.catalogo(dibujo)
    grupos, _ = asignar_marcas(memoria_modelo.leer(dibujo), catalogo)
    por_origen = {}
    for configuracion in configuraciones:
        for fila in memoria_modelo.filas(grupos, configuracion):
            for pieza in fila["piezas"]:
                por_origen.setdefault(
                    pieza["origen"], (pieza, fila["marca"], configuracion["escala"])
                )
    hechos = []
    if CAPA_ROTULOS not in dibujo.layers:
        dibujo.layers.new(CAPA_ROTULOS, dxfattribs={"color": 6})
    for identificador, (pieza, marca, escala) in por_origen.items():
        entidad = dibujo.modelspace().add_text(
            marca, dxfattribs={"layer": CAPA_ROTULOS, "height": 0.0025 * escala}
        )
        entidad.dxf.insert = (*pieza["posicion"], 0.0)
        _xdata(
            dibujo.modelspace(),
            entidad,
            {"kind": "opening_mark", "schema": 1, "opening_id": identificador},
        )
        hechos.append(entidad)
    return hechos

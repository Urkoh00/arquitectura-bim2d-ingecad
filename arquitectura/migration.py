# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: ARQMIGRAR: migración explícita y deshacible de muros de versiones antiguas.
#   (Guía del código: docs/GUIA_DEL_CODIGO.md)
"""Explicit, reversible legacy wall migration to an authoritative open axis.

Old closed footprint polylines and v1.2.4 POINT records remain valid without
migration. This command converts only tagged BIM wall sources, never ordinary
CAD entities. Run on a copy and inspect the result before saving over originals.
"""
from __future__ import annotations
from core.commands import Command
from .architectural import metadata, _xdata, WALL_LAYER

class MigrateLegacyWalls(Command):
    name='ARQ MIGRAR MUROS A EJES'
    needs_regen=True
    def __init__(self):
        self.before=None
        self.new_handles=[]
        self.count=0
    def do(self, document):
        msp=document.doc.modelspace()
        legacy=[e for e in msp if (metadata(e) or {}).get('kind')=='wall' and
                (e.dxftype()=='POINT' or (e.dxftype()=='LWPOLYLINE' and e.closed))]
        # Las entidades originales se retiran del espacio (no se borran) y el
        # Deshacer las devuelve tal cual: mismo identificador, curvas (bulge),
        # capa, color y demás atributos. Antes se recreaban con sus puntos
        # (x, y) y un contorno curvo volvía recto (revisión del 24-11).
        self.before=legacy
        from .architectural_v10 import axis_points
        self.new_handles=[]
        for e in legacy:
            rec=metadata(e)
            # el eje conserva la curva del muro (su bulge), como al dibujarlo
            axis=msp.add_lwpolyline(axis_points(rec),format='xyb',dxfattribs={'layer':WALL_LAYER})
            _xdata(msp,axis,rec)
            self.new_handles.append(axis.dxf.handle)
            msp.unlink_entity(e)
        self.count=len(legacy)
        document.dirty=True
    def undo(self,document):
        msp=document.doc.modelspace()
        for h in self.new_handles:
            e=document.doc.entitydb.get(h)
            if e is not None and e.is_alive:msp.delete_entity(e)
        for e in self.before or []:
            msp.add_entity(e)
        document.dirty=True


class CanonicalPillarLayer(Command):
    """Native case-only layer rename, reversible without changing BIM IDs."""
    name='ARQ NORMALIZAR CAPA DE PILARES'
    needs_regen=True
    def __init__(self):self.inner=None;self.count=0
    def do(self,document):
        if self.inner is None:
            from core.layers import RenameLayerCommand
            from .transactions import SafeArchitecturalCommand
            commands=[]
            if 'ARQ-PILARES' in document.doc.layers:
                old=document.doc.layers.get('ARQ-PILARES').dxf.name
                if old!='ARQ-PILARES':
                    self.count=sum(e.dxf.layer.lower()==old.lower() for e in document.doc.modelspace())
                    temp='ARQ-PILARES-CAMBIO'
                    while temp in document.doc.layers:temp+='-'
                    commands=[RenameLayerCommand(old,temp),RenameLayerCommand(temp,'ARQ-PILARES')]
            self.inner=SafeArchitecturalCommand(self.name,commands)
        self.inner.do(document)
    def undo(self,document):
        if self.inner:self.inner.undo(document)
        document.dirty=True

class PartitionLayers(Command):
    """v1.48.1: las capas ARQ-TABIQUES (con o sin sufijo de nivel) pasan a
    ARQ-PARTICIONES. Se renombran en el dibujo, así que sus entidades las
    siguen sin cambiar de identificador; si la capa nueva ya existe, se deja
    como está y se avisa."""
    name='ARQ CAPAS DE PARTICIONES'
    needs_regen=True
    def __init__(self):self.inner=None;self.count=0;self.skipped=[]
    def do(self,document):
        if self.inner is None:
            from core.layers import RenameLayerCommand
            from .transactions import SafeArchitecturalCommand
            from .wall_categories import LAYERS,LEGACY_LAYERS
            commands=[]
            for cat,old in LEGACY_LAYERS.items():
                for layer in list(document.doc.layers):
                    name=layer.dxf.name
                    if name.split('@')[0].upper()!=old:continue
                    new=LAYERS[cat]+name[len(old):]
                    if new in document.doc.layers:self.skipped.append(name);continue
                    commands.append(RenameLayerCommand(name,new));self.count+=1
            self.inner=SafeArchitecturalCommand(self.name,commands)
        self.inner.do(document)
    def undo(self,document):
        if self.inner:self.inner.undo(document)
        document.dirty=True

def migrar_arq(ctx,*args):
    try:
        from .transactions import SafeArchitecturalCommand
        from .wall_network import RegenerateContoursCommand
        from core.commands import DeferredCommand
        from .wall_categories import migrate_steps,LAYERS
        from core.layers import NewLayerCommand
        cmd=MigrateLegacyWalls();layers=CanonicalPillarLayer();particiones=PartitionLayers()
        ctx.execute(SafeArchitecturalCommand('ARQ migrar ejes y regenerar',[
            particiones,DeferredCommand('ARQ capas nuevas',lambda doc:SafeArchitecturalCommand('Capas',[NewLayerCommand(n,color=8)for n in LAYERS.values()if n not in doc.doc.layers])),
            layers,cmd,DeferredCommand('ARQ categorías',lambda doc:SafeArchitecturalCommand('Categorías explícitas',migrate_steps(doc))),
            DeferredCommand('ARQ contorno',lambda _:RegenerateContoursCommand())]))
        ctx.echo('Categorías de muros deducidas y confirmadas; revise las medianeras y los contactos con el terreno.')
        ctx.echo(f'ARQMIGRAR: {cmd.count} registros anteriores convertidos a ejes BIM. Se puede deshacer.')
        if particiones.count:ctx.echo(f'ARQ-PARTICIONES: {particiones.count} capas ARQ-TABIQUES renombradas; mismo Deshacer.')
        if particiones.skipped:ctx.echo('ARQ-PARTICIONES ya existe: revise '+', '.join(particiones.skipped))
        if layers.count:ctx.echo(f'ARQ-PILARES: {layers.count} entidades conservadas en la capa normalizada; mismo Deshacer.')
    except Exception as exc:
        ctx.echo(f'ARQMIGRAR: error ({type(exc).__name__}: {exc})')


def migrate_opening_position(record):
    """Add optional offset fields; old face/side semantics stay unchanged.

    No geographic facade is inferred, and no drawing mutation occurs here.
    """
    from .openings import normalise
    return normalise(dict(record))

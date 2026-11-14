# SPDX-License-Identifier: GPL-3.0-or-later
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
        # Store DXF geometry and metadata for exact architectural restoration.
        self.before=[{'type':e.dxftype(),'closed':bool(e.closed) if e.dxftype()=='LWPOLYLINE' else False,
                      'points':list(e.get_points('xy')) if e.dxftype()=='LWPOLYLINE' else None,
                      'position':tuple(e.dxf.location) if e.dxftype()=='POINT' else None,
                      'layer':e.dxf.layer,'metadata':metadata(e)} for e in legacy]
        self.new_handles=[]
        for e in legacy:
            rec=metadata(e)
            axis=msp.add_lwpolyline([rec['a'],rec['b']],dxfattribs={'layer':WALL_LAYER})
            _xdata(msp,axis,rec)
            self.new_handles.append(axis.dxf.handle)
            msp.delete_entity(e)
        self.count=len(legacy)
        document.dirty=True
    def undo(self,document):
        msp=document.doc.modelspace()
        for h in self.new_handles:
            e=document.doc.entitydb.get(h)
            if e is not None and e.is_alive:msp.delete_entity(e)
        for rec in self.before or []:
            if rec['type']=='POINT':
                e=msp.add_point(rec['position'],dxfattribs={'layer':rec['layer']})
            else:
                e=msp.add_lwpolyline(rec['points'],close=rec['closed'],dxfattribs={'layer':rec['layer']})
            _xdata(msp,e,rec['metadata'])
        document.dirty=True

def migrar_arq(ctx,*args):
    try:
        from .transactions import SafeArchitecturalCommand
        from .wall_network import RegenerateContoursCommand
        from core.commands import DeferredCommand
        cmd=MigrateLegacyWalls()
        ctx.execute(SafeArchitecturalCommand('ARQ migrar ejes y regenerar',[
            cmd,DeferredCommand('ARQ contorno',lambda _:RegenerateContoursCommand())]))
        ctx.echo(f'ARQMIGRAR: {cmd.count} registros anteriores convertidos a ejes BIM. Se puede deshacer.')
    except Exception as exc:
        ctx.echo(f'ARQMIGRAR: error ({type(exc).__name__}: {exc})')


def migrate_opening_position(record):
    """Add optional offset fields; old face/side semantics stay unchanged.

    No geographic facade is inferred, and no drawing mutation occurs here.
    """
    from .openings import normalise
    return normalise(dict(record))

# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: Una acción arquitectónica = un solo paso de Deshacer: la orden más la regeneración de la
#   planta.
#   (Guía del código: docs/GUIA_DEL_CODIGO.md)
"""Atomic architectural actions: the native IngeCAD history records one step.

Unlike CompositeCommand.do, this variant rolls already-applied member commands
back if a later member fails. No private History calls or host patches.
"""
from __future__ import annotations
from core.commands import CompositeCommand, Command
from core.layers import NewLayerCommand
from .compat import require_document
from .wall_network import RegenerateContoursCommand
from .architectural import WALL_LAYER


class ArchitecturalRegeneration(Command):
    """One derived command per history entry: redo reuses its entities."""
    name = 'ARQ encuentros derivados'
    needs_regen = True
    def __init__(self):
        self.inner = RegenerateContoursCommand()

    def do(self, document):
        self.inner.do(document)
    def undo(self, document):
        self.inner.undo(document)
        self.removed_handles = self.inner.removed_handles


class SafeArchitecturalCommand(CompositeCommand):
    """Roll back successful subcommands on a failure before History.record()."""
    needs_regen = True

    def do(self, document):
        from .level_layers import locked_snapshot,check_locked,require_new,preflight
        from .architectural import metadata
        from .levels import load as _levels
        for command in self.commands:preflight(document,command)
        locked=locked_snapshot(document)
        managed=bool(_levels(document.doc).get('layer_managed'))
        existing={m.get('id')for e in document.doc.modelspace() if(m:=metadata(e)or{}).get('kind')in('wall','column','space','opening','slab')} if managed else set()
        applied = []
        try:
            for command in self.commands:
                command.do(document)
                applied.append(command)
                followup = getattr(command, 'dimassoc_followup', None)
                if followup is not None:
                    followup.do(document)
            check_locked(document,locked)
            for e in (document.doc.modelspace() if managed else ()):
                m=metadata(e)or{}
                if m.get('kind')in('wall','column','space','opening','slab')and m.get('id')not in existing:require_new(document.doc,m)
        except Exception as original:
            failures = []
            for command in reversed(applied):
                try:
                    followup = getattr(command, 'dimassoc_followup', None)
                    if followup is not None:
                        followup.undo(document)
                    command.undo(document)
                except Exception as exc:
                    failures.append(f'{getattr(command,"name",type(command).__name__)}: {exc}')
            if failures:
                raise RuntimeError('Fallo al restaurar operación arquitectónica: '
                                   + '; '.join(failures)) from original
            raise


def apply_architectural_change(ctx, change, *, kind='wall'):
    """Create/edit source and derived contour as ONE undoable history entry."""
    doc = require_document(ctx)
    from .wall_categories import layers_to_create
    needed = [(WALL_LAYER, 8), *[(name,8) for name in layers_to_create(doc.doc.layers)]]
    if kind == 'column':
        from .columns import PILLAR_LAYER
        needed.insert(0, (PILLAR_LAYER, 4))
    if kind == 'column' or 'ARQ-PILARES' in doc.doc.layers:
        needed.append(('ARQ-AISLAMIENTOS', 3))
    if kind == 'space':
        needed.append(('ARQ-RECINTOS', 3))
    if kind == 'virtual_partition':
        from .particiones_virtuales import LAYER, LAYER_COLOR
        needed.append((LAYER, LAYER_COLOR))
    if kind == 'opening':
        from .architectural import OPENING_LAYER
        from .openings import SYMBOL_LAYER
        needed += [(OPENING_LAYER, 3), (SYMBOL_LAYER, 6)]
    commands = [NewLayerCommand(name, color=color)
                for name, color in needed if name not in doc.doc.layers]
    commands += [change, ArchitecturalRegeneration()]
    ctx.execute(SafeArchitecturalCommand('ARQ elemento + encuentros', commands))
    return change

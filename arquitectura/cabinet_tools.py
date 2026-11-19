# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: ARMARIOBIM: la interacción de la orden, separada de la geometría (cabinets.py) para que esta
#   pueda viajar a IngeTrazo sin cargar IngeCAD.
#   (Guía del código: docs/GUIA_DEL_CODIGO.md)
"""CAD interaction separated from the shared cabinet geometry."""
from .cabinets import create, form
from .opening_tools import CarpinteriaTool


class CabinetTool(CarpinteriaTool):
    name='ARMARIOBIM'
    def start(self):
        self.name=type(self).name;self._cache=None;self.active=True
        self.values={'cabinet_mode':'adosado','body_material':'Madera','width':1.2,'niche_depth':.6,'height':2.1,'sill':0.,'leaves':2,'operation':'SLIDING'}
        from .bim_dialogs import available
        if available(self.ctx):
            dlg,read=form(self.ctx,self.values)
            if dlg.exec()!=1:self.active=False;self.ctx.finish();return
            self.values=read()
        self._prompt()
    def _prompt(self):self.prompt('ARMARIOBIM: cara de acceso y jamba del armario, o Intro para terminar:')
    def on_point(self,p):
        if not self.active:return
        from .transactions import apply_architectural_change
        try:
            wall,spec=self._wall_at(tuple(p[:2]))
            if wall is None:raise ValueError('Designe una cara de muro BIM')
            offset,across=spec.local(tuple(p[:2]));v=self.values
            change=create(wall,offset,v['width'],v['niche_depth'],v['height'],v['leaves'],v['operation'],
                          1 if across>=(spec.lo+spec.hi)/2 else -1,v['sill'],mode=v['cabinet_mode'],body_material=v['body_material'])
            apply_architectural_change(self.ctx,change,kind='opening');self._cache=None
            from .architectural import metadata
            from .cabinets import niche_warning
            aviso=niche_warning(metadata(wall) or {},v['cabinet_mode'])
            if aviso:self.ctx.echo('ARMARIOBIM: aviso: '+aviso)
        except ValueError as exc:self.ctx.echo('ARMARIOBIM: '+str(exc))
        self._prompt()
    def on_enter(self):self.active=False;self.ctx.finish()
    def on_cancel(self):self.active=False;self.ctx.finish()
    def on_option(self,text):return False

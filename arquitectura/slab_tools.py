# SPDX-License-Identifier: GPL-3.0-or-later
"""Slab drafting through native point input, picking and history."""
from tools.base import Tool
from . import slabs as S
from .architectural import metadata


def form(ctx,record=None):
    from PySide6.QtWidgets import QFormLayout,QLineEdit,QDoubleSpinBox,QCheckBox,QLabel
    from .bim_dialogs import _dialog
    from .compat import require_document
    from .levels import load
    data=load(require_document(ctx));rec=record or{}
    lv=next(v for v in data['levels']if v['id']==rec.get('level_id',data['active']))
    dlg,layout,buttons=_dialog(ctx,'Arquitectura — Forjado horizontal',
        'El contorno y los huecos se dibujan en planta. La cara superior se mide respecto del nivel; el espesor crece hacia abajo.')
    fields=QFormLayout();name=QLineEdit(rec.get('name','Forjado'));material=QLineEdit(rec.get('material','Sin definir'));fields.addRow('Nombre',name);fields.addRow('Material',material)
    thick=QDoubleSpinBox();thick.setDecimals(4);thick.setRange(.001,100);thick.setValue(rec.get('thickness',.2));fields.addRow('Espesor (m)',thick)
    top=QDoubleSpinBox();top.setDecimals(4);top.setRange(-1e6,1e6);top.setValue(rec.get('base',lv['elevation']-.2)+rec.get('thickness',.2)-lv['elevation']);fields.addRow('Cara superior / nivel (m)',top)
    fields.addRow('Nivel',QLabel(lv['name']));layout.insertLayout(1,fields)
    clear=QCheckBox('Quitar todos los huecos (se puede deshacer)');clear.setVisible(bool(record));layout.addWidget(clear);layout.addWidget(buttons)
    def read():return {'name':name.text().strip()or'Forjado','material':material.text(),'thickness':thick.value(),'top_offset':top.value(),'clear_holes':clear.isChecked()}
    dlg._arq={'name':name,'material':material,'thickness':thick,'top':top,'clear_holes':clear}
    return dlg,read


def edit_change(ctx,entity,values):
    from .levels import load
    from .compat import require_document
    m=S.read(entity);data=load(require_document(ctx));lv=next(v for v in data['levels']if v['id']==m.get('level_id',data['active']))
    out={**m,'name':values['name'],'material':values['material'],'thickness':values['thickness'],
         'base':lv['elevation']+values['top_offset']-values['thickness']}
    if values.get('clear_holes'):out['holes']=[]
    return S.EditSlab(entity,out)


class SlabTool(Tool):
    name='FORJADO'
    def start(self):
        self.name=type(self).name;self.outer=None;self.holes=[];self.points=[];self.phase='outer';self.finished=False
        self.values={'thickness':.2,'top_offset':0.,'name':'Forjado','material':'Sin definir'}
        from .bim_dialogs import available
        if available(self.ctx):
            dlg,read=form(self.ctx)
            if dlg.exec()!=1:self.on_cancel();return
            self.values=read();self.values.pop('clear_holes',None)
        self._prompt()
    def _prompt(self):
        self.prompt('FORJADO: '+('puntos del contorno; Intro para cerrar'if self.phase=='outer'else 'puntos del hueco; Intro para cerrar'if self.phase=='hole'else 'Intro para confirmar, Hueco para otro contorno o Esc para cancelar'))
    def on_point(self,p):
        if self.finished:return
        if self.phase=='confirm':self.ctx.echo('Use Hueco para añadir un hueco o Intro para confirmar');return
        self.points.append(tuple(map(float,p[:2])));self.last_point=self.points[-1];self._prompt()
    def on_option(self,text):
        if str(text).lower()in('u','retroceder')and self.points:
            self.points.pop();self.last_point=self.points[-1]if self.points else None;self._prompt();return True
        if self.phase=='confirm'and str(text).lower()in('h','hueco'):
            self.phase='hole';self.points=[];self.last_point=None;self._prompt();return True
        return False
    def on_enter(self):
        if self.finished:return
        try:
            if self.phase=='outer':self.outer=S.ring(self.points);self.points=[];self.phase='confirm'
            elif self.phase=='hole':
                h=S.ring(self.points);S.region(self.outer,self.holes+[h]);self.holes.append(h);self.points=[];self.phase='confirm'
            else:S.apply_new(self.ctx,self.outer,self.holes,**self.values);self.finished=True;self.ctx.finish();return
        except ValueError as exc:self.ctx.echo('FORJADO: '+str(exc))
        self._prompt()
    def preview_segments(self,cursor):
        if self.finished:return []
        loops=([self.outer]if self.outer else[])+self.holes
        lines=[(a,b)for loop in loops for a,b in zip(loop,loop[1:]+loop[:1])]
        pts=self.points+([tuple(cursor[:2])]if self.points and cursor is not None else[])
        if pts:lines.extend(zip(pts,pts[1:]+pts[:1]))
        return lines
    def on_cancel(self):self.finished=True;self.points=[];self.ctx.finish()


class SlabHoleTool(Tool):
    name='HUECOFORJADO';entity_picker=True
    def start(self):self.name=type(self).name;self.entity=None;self.points=[];self.finished=False;self.entity_picker=True;self.prompt('HUECOFORJADO: seleccione el forjado:')
    def on_point(self,p):
        if self.finished:return
        if self.entity is None:
            e=self.ctx.services.pick_entity(p)
            if e is not None and(metadata(e)or{}).get('kind')=='slab':self.entity=e;self.entity_picker=False;self.last_point=None;self.prompt('Hueco: puntos del perímetro; Intro para confirmar')
            else:self.ctx.echo('Seleccione el HATCH fuente del forjado')
        else:self.points.append(tuple(map(float,p[:2])));self.last_point=self.points[-1]
    def on_enter(self):
        if self.entity is None or self.finished:return
        from .transactions import apply_architectural_change
        try:
            m=S.read(self.entity);m['holes'].append(S.ring(self.points));cmd=S.EditSlab(self.entity,m)
            apply_architectural_change(self.ctx,cmd);self.finished=True;self.ctx.finish()
        except ValueError as exc:self.ctx.echo('HUECOFORJADO: '+str(exc))
    def preview_segments(self,cursor):
        if self.finished or not self.points:return []
        pts=self.points+([tuple(cursor[:2])]if cursor is not None else[]);return list(zip(pts,pts[1:]+pts[:1]))
    def on_cancel(self):self.finished=True;self.points=[];self.ctx.finish()

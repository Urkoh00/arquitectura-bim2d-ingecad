# SPDX-License-Identifier: GPL-3.0-or-later
"""Partial wall niches using the existing opening and door pipeline."""
from . import openings as OP


def fronts(spec,rec):
    OP.cut_band(spec,rec)
    n=int(rec['leaves']);fw=float(rec['frame_width']);step=(rec['width']-2*fw)/n
    if step<=.06:raise ValueError('Ancho insuficiente para las hojas del armario')
    for i in range(n):
        yield {**rec,'cabinet':False,'offset':rec['offset']+fw+i*step+.002,'width':step-.004,
               'leaves':1,'hinge':i%2,'face':'distancia','setback_from':'interior',
               'setback':0.,'frame_depth':min(.05,rec['niche_depth']),
               'frame_width':0.,'leaf':step-.004,'leaf2':0.,
               '_track':rec['side']*.03*(i%2)if rec['operation']=='SLIDING'else 0.}


def symbols(spec,rec):
    result=[];fw=float(rec['frame_width'])
    full={**rec,'cabinet':False,'leaves':1,'face':'interior','frame_depth':min(.05,rec['niche_depth'])}
    lo,hi=OP.frame_band(spec,full);h=hi if rec['side']>0 else lo
    if fw:result.extend(OP._jambs(spec.point,rec['offset'],rec['offset']+rec['width'],fw,lo,hi,h,float(rec.get('leaf_thickness')or OP.LEAF_THICKNESS)))
    for front in fronts(spec,rec):
        shift=front['_track']
        def pt(p):return(p[0]+spec.n[0]*shift,p[1]+spec.n[1]*shift)
        for g in OP.plan_symbol(spec,front):
            if g[0]=='poly':result.append(('poly',[pt(p)for p in g[1]],g[2]))
            elif g[0]=='line':result.append(('line',pt(g[1]),pt(g[2])))
            else:result.append(('arc',pt(g[1]),*g[2:]))
    return result


def parts(spec,rec,base):
    full={**rec,'cabinet':False,'leaves':1,'face':'interior','frame_depth':min(.05,rec['niche_depth'])}
    result=[p for p in OP.carpentry_parts(spec,full,base)if p['role']=='frame']
    for i,front in enumerate(fronts(spec,rec)):
        for piece in OP.carpentry_parts(spec,front,base):
            piece=dict(piece);a,b,lo,hi,z0,z1=piece['box'];shift=front['_track']
            piece['box']=(a,b,lo+shift,hi+shift,z0,z1);piece['name']=f'Hoja {i+1}'
            result.append(piece)
    return result


def create(wall,offset,width,depth,height,leaves=2,operation='SLIDING',side=1,base=0.):
    from .architectural_v10 import create_opening
    return create_opening(wall,offset,width,base,height,kind='door',cabinet=True,
        niche_depth=depth,leaves=leaves,operation=operation,side=side,
        name='Armario',type_name='ARMARIO',frame_width=.02,frame_depth=min(.05,depth))


def form(ctx,record=None):
    from PySide6.QtWidgets import QFormLayout,QDoubleSpinBox,QSpinBox,QComboBox,QMessageBox
    from .bim_dialogs import _dialog
    rec=record or {};dlg,layout,buttons=_dialog(ctx,'Arquitectura — Armario BIM',
        'Nicho parcial: conserve al menos 0,01 m de muro. Designe la cara de acceso y la jamba. No se deduce el fondo del dibujo.')
    rows=QFormLayout();edit={}
    for key,label,value in [('width','Ancho (m)',1.2),('niche_depth','Fondo del nicho (m)',.3),('height','Altura (m)',2.1),('sill','Base sobre el muro (m)',0.)]:
        w=QDoubleSpinBox();w.setDecimals(4);w.setRange(0 if key=='sill'else .001,1000);w.setValue(rec.get(key,value));rows.addRow(label,w);edit[key]=w
    leaves=QSpinBox();leaves.setRange(1,4);leaves.setValue(rec.get('leaves',2));rows.addRow('Hojas',leaves)
    operation=QComboBox();operation.addItem('Corredera','SLIDING');operation.addItem('Abatible','SWINGING');operation.setCurrentIndex(max(0,operation.findData(rec.get('operation','SLIDING'))));rows.addRow('Apertura',operation)
    layout.insertLayout(1,rows);layout.addWidget(buttons)
    def read():return {**{k:w.value()for k,w in edit.items()},'leaves':leaves.value(),'operation':operation.currentData()}
    dlg._arq={**edit,'leaves':leaves,'operation':operation}
    return dlg,read


from .opening_tools import CarpinteriaTool


class CabinetTool(CarpinteriaTool):
    name='ARMARIOBIM'
    def start(self):
        self.name=type(self).name;self._cache=None;self.active=True
        self.values={'width':1.2,'niche_depth':.3,'height':2.1,'sill':0.,'leaves':2,'operation':'SLIDING'}
        from .bim_dialogs import available
        if available(self.ctx):
            dlg,read=form(self.ctx,self.values)
            if dlg.exec()!=1:self.active=False;self.ctx.finish();return
            self.values=read()
        self._prompt()
    def _prompt(self):self.prompt('ARMARIOBIM: cara de acceso y jamba del nicho, o Intro para terminar:')
    def on_point(self,p):
        if not self.active:return
        from .transactions import apply_architectural_change
        try:
            wall,spec=self._wall_at(tuple(p[:2]))
            if wall is None:raise ValueError('Designe una cara de muro BIM')
            offset,across=spec.local(tuple(p[:2]));v=self.values
            change=create(wall,offset,v['width'],v['niche_depth'],v['height'],v['leaves'],v['operation'],
                          1 if across>=(spec.lo+spec.hi)/2 else -1,v['sill'])
            apply_architectural_change(self.ctx,change,kind='opening');self._cache=None
        except ValueError as exc:self.ctx.echo('ARMARIOBIM: '+str(exc))
        self._prompt()
    def on_enter(self):self.active=False;self.ctx.finish()
    def on_cancel(self):self.active=False;self.ctx.finish()
    def on_option(self,text):return False

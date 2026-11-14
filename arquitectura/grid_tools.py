# SPDX-License-Identifier: GPL-3.0-or-later
"""Grid tools using the host's point input, property widgets and history."""
from tools.base import Tool
from . import grids as G
from .compat import require_document
from .transactions import apply_architectural_change,SafeArchitecturalCommand

def grid_form(ctx,values):
    from PySide6.QtWidgets import QLineEdit,QFormLayout,QDoubleSpinBox,QCheckBox,QComboBox
    from .bim_dialogs import _dialog
    dlg,layout,buttons=_dialog(ctx,'Arquitectura — Rejilla estructural',
        'Separaciones en metros: 3x5,40 4,20. Números en U y letras en V; se omiten I, O y Ñ. '
        'Ejes vinculados a pilares. IFC de rejillas pendiente; referencias conservadas como datos.')
    form=QFormLayout();edit={}
    for key,label,default in [('x','Intervalos X','3x5'),('y','Intervalos Y','2x4'),
            ('first_number','Primer número','1'),('first_letter','Primera letra','A'),
            ('prefix','Prefijo',''),('suffix','Sufijo','')]:
        w=QLineEdit(str(values.get(key,default)));edit[key]=w;form.addRow(label,w)
    for key,label,default in [('angle','Ángulo (°)',0),('extension','Prolongación (m)',1),
             ('scale','Escala 1:',100),('text_mm','Texto (mm papel)',2.5),('radius_mm','Radio burbuja (mm papel)',4)]:
        w=QDoubleSpinBox();w.setRange(-360 if key=='angle' else .001,100000);w.setDecimals(3);w.setValue(float(values.get(key,default)));edit[key]=w;form.addRow(label,w)
    bubble=QComboBox();bubble.addItem('Círculo','circle');bubble.addItem('Hexágono','hexagon');edit['bubble']=bubble;form.addRow('Burbuja',bubble)
    for key,label in [('start','Burbuja inicial'),('end','Burbuja final'),('dimensions','Cotas en cadena y total')]:
        w=QCheckBox(label);w.setChecked(bool(values.get(key,True)));edit[key]=w;form.addRow(w)
    layout.insertLayout(1,form);dlg._arq=edit
    def read():
        data={}
        for key,w in edit.items():
            if isinstance(w,QLineEdit):data[key]=w.text().strip()
            elif isinstance(w,QCheckBox):data[key]=w.isChecked()
            elif isinstance(w,QComboBox):data[key]=w.currentData()
            else:data[key]=w.value()
        G.distances(data['x']);G.distances(data['y']);G.letter_index(data['first_letter']);int(data['first_number'])
        return data
    return dlg,read

class GridTool(Tool):
    name='EJES'
    def start(self):
        self.values={};self.mode='grid';self.first=None
        from .bim_dialogs import available
        if available(self.ctx):
            dlg,read=grid_form(self.ctx,self.values)
            if dlg.exec()!=1:self.ctx.finish();return
            self.values=read()
        self.prompt('EJES: origen de rejilla o [X intervalos/Y intervalos/Angulo grados/Suelto/Fin]:')
    def on_option(self,text):
        parts=str(text).strip().split(maxsplit=1);key=parts[0].lower() if parts else ''
        if key in ('x','y','angulo','ángulo') and len(parts)==2:
            if key in ('x','y'):G.distances(parts[1]);self.values[key]=parts[1]
            else:self.values['angle']=float(parts[1].replace(',','.'))
            return True
        if key=='suelto':self.mode='single';self.first=None;self.prompt('Eje suelto: primer extremo:');return True
        if key in ('f','fin'):self.ctx.finish();return True
        return False
    def on_point(self,p):
        if self.mode=='single':
            if self.first is None:self.first=p;self.prompt('Segundo extremo:');return
            from core.actions import AddEntityCommand
            from core.layers import NewLayerCommand
            from core.linetypes import LoadLinetypesCommand
            import uuid
            rec={'kind':'grid_axis','id':uuid.uuid4().hex,'grid_id':uuid.uuid4().hex,'family':'S','index':0,
                 'label':'1','text_height':.25,'radius':.4,'ends':[True,True],'bubble':'circle','dimensions':False}
            a,b=self.first,p
            if __import__('math').dist(a,b)<1e-6:raise ValueError('Eje de longitud nula')
            def factory(msp):return G._xdata(msp,msp.add_lwpolyline([a,b],dxfattribs={
                'linetype':'DASHDOT','ltscale':G.linetype_scale(msp.doc,100.),'color':8,'lineweight':13}),rec)
            change=SafeArchitecturalCommand('ARQ EJE SUELTO',[LoadLinetypesCommand(['DASHDOT']),NewLayerCommand(G.LAYER,color=8),AddEntityCommand('ARQ EJE',factory,layer=G.LAYER),G.RegenerateGrid()])
        else:change=G.create_grid(tuple(p[:2]),self.values)
        apply_architectural_change(self.ctx,change,kind='column');self.ctx.finish()
    def on_enter(self):self.ctx.finish()
    def preview_segments(self,cursor):
        if cursor is None:return []
        if self.mode=='single':return [(self.first,cursor)] if self.first is not None else []
        import math
        xs=G.distances(self.values.get('x','3x5'));ys=G.distances(self.values.get('y','2x4'))
        angle=math.radians(float(self.values.get('angle',0)));c,s=math.cos(angle),math.sin(angle)
        ext=float(self.values.get('extension',1.))
        def p(x,y):return (cursor[0]+c*x-s*y,cursor[1]+s*x+c*y)
        return [(p(x,-ext),p(x,ys[-1]+ext)) for x in xs]+[(p(-ext,y),p(xs[-1]+ext,y)) for y in ys]

class RejillaTool(GridTool):name='REJILLA'

class GridEditTool(Tool):
    name='EDITAREJE';entity_picker=True
    def start(self):self.entity=None;self.prompt('EDITAREJE: designe un eje; después nuevo punto medio o [Ficha/Renumerar valor]:')
    def on_point(self,p):
        if self.entity is None:
            e=self.ctx.services.pick_entity(p)
            if e is not None and (G.metadata(e)or{}).get('kind')=='grid_axis':
                self.entity=e;self.prompt('Nuevo punto medio del eje o [Renumerar valor]:')
            else:self.ctx.echo('Designe la línea de un eje, no su burbuja.')
            return
        a,b=G.endpoints(self.entity);dx,dy=p[0]-(a[0]+b[0])/2,p[1]-(a[1]+b[1])/2
        before=G.snapshot(require_document(self.ctx).doc)
        change=SafeArchitecturalCommand('ARQ MOVER EJE',[G.SetAxis(self.entity,[(a[0]+dx,a[1]+dy),(b[0]+dx,b[1]+dy)]),G.RegenerateGrid(before)])
        apply_architectural_change(self.ctx,change,kind='column');self.ctx.finish()
    def on_option(self,text):
        if self.entity is not None and str(text).strip().lower()=='ficha':
            dlg,read=axis_form(self.ctx,self.entity)
            if dlg.exec()==1:
                values,points=read();before=G.snapshot(require_document(self.ctx).doc)
                apply_architectural_change(self.ctx,SafeArchitecturalCommand('ARQ FICHA EJE',[G.SetAxis(self.entity,points,**values),G.RegenerateGrid(before)]),kind='column')
            self.ctx.finish();return True
        parts=str(text).strip().split(maxsplit=1)
        if self.entity is None or len(parts)!=2 or parts[0].lower()!='renumerar':return False
        m=G.metadata(self.entity);first=int(parts[1]) if m['family']=='U' else G.letter_index(parts[1])
        if first<1:raise ValueError('Numeración positiva')
        members=sorted([(e,n) for e,n in G.axes(require_document(self.ctx).doc) if n['grid_id']==m['grid_id'] and n['family']==m['family'] and n['index']>=m['index']],key=lambda x:x[1]['index'])
        commands=[G.SetAxis(e,label=n.get('prefix','')+(str(first+i) if m['family']=='U' else G.letter(first+i))+n.get('suffix','')) for i,(e,n) in enumerate(members)]
        apply_architectural_change(self.ctx,SafeArchitecturalCommand('ARQ RENUMERAR',[*commands,G.RegenerateGrid()]),kind='column');self.ctx.finish();return True
    def on_enter(self):self.ctx.finish()

class GridColumnsTool(Tool):
    name='PILARESENEJES'
    def start(self):
        from .parameters_arq import load_defaults
        self.values=dict(load_defaults(require_document(self.ctx))['column']);self.first=None
        from .bim_dialogs import available,column_properties
        if available(self.ctx):
            v=column_properties(self.ctx,self.values)
            if v is None:self.ctx.finish();return
            self.values.update(v)
        self.prompt('PILARESENEJES: primera esquina de zona o [Todos]:')
    def on_option(self,text):
        if str(text).strip().lower()=='todos':G.place_columns(self.ctx,self.values);self.ctx.finish();return True
        return False
    def on_point(self,p):
        if self.first is None:self.first=p;self.prompt('Esquina opuesta:');return
        points=G.intersections(require_document(self.ctx).doc);a=self.first;b=p
        chosen={i for i,(q,link) in enumerate(points) if min(a[0],b[0])<=q[0]<=max(a[0],b[0]) and min(a[1],b[1])<=q[1]<=max(a[1],b[1])}
        G.place_columns(self.ctx,self.values,chosen);self.ctx.finish()
    def on_enter(self):self.ctx.finish()

def axis_form(ctx,entity):
    from PySide6.QtWidgets import QLineEdit,QFormLayout,QDoubleSpinBox,QCheckBox,QComboBox
    from .bim_dialogs import _dialog
    m=G.metadata(entity);points=G.endpoints(entity);scale=float(m.get('scale',100.))
    dlg,layout,buttons=_dialog(ctx,'Arquitectura — Eje estructural',
        'Editar extremos, marca y representación. Los pilares vinculados y las cotas se actualizan en un Deshacer.')
    form=QFormLayout();label=QLineEdit(m['label']);form.addRow('Marca',label);coords=[]
    for i,p in enumerate(points):
        row=[]
        for j,value in enumerate(p):
            w=QDoubleSpinBox();w.setDecimals(6);w.setRange(-1e9,1e9);w.setValue(value)
            form.addRow(('Inicio' if i==0 else 'Final')+' '+('X' if j==0 else 'Y'),w);row.append(w)
        coords.append(row)
    sizes=[]
    for key,title in [('text_height','Texto (mm papel)'),('radius','Radio (mm papel)')]:
        w=QDoubleSpinBox();w.setRange(.1,100.);w.setValue(m[key]*1000/scale);form.addRow(title,w);sizes.append(w)
    bubble=QComboBox();bubble.addItem('Círculo','circle');bubble.addItem('Hexágono','hexagon');bubble.setCurrentIndex(max(0,bubble.findData(m['bubble'])));form.addRow('Burbuja',bubble)
    ends=[]
    for i in range(2):
        w=QCheckBox('Burbuja '+('inicial' if i==0 else 'final'));w.setChecked(m['ends'][i]);form.addRow(w);ends.append(w)
    layout.insertLayout(1,form)
    def read():
        return {'label':label.text().strip(),'text_height':sizes[0].value()*scale/1000,
                'radius':sizes[1].value()*scale/1000,'bubble':bubble.currentData(),
                'ends':[w.isChecked() for w in ends]},[[w.value() for w in row] for row in coords]
    dlg._arq={'label':label,'coordinates':coords,'sizes':sizes,'ends':ends,'bubble':bubble}
    return dlg,read

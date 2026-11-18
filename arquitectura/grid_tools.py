# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: EJES, EDITAREJE, REJILLA y PILARESENEJES: órdenes de las rejillas de ejes estructurales.
#   (Guía del código: docs/GUIA_DEL_CODIGO.md)
"""Grid tools using the host's point input, property widgets and history."""
from tools.base import Tool
from . import grids as G
from .compat import require_document
from .transactions import apply_architectural_change,SafeArchitecturalCommand

def interval_editor(text,label):
    from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QSpinBox,QDoubleSpinBox,QLabel,QPushButton,QTableWidget,QTableWidgetItem,QHeaderView
    from PySide6.QtCore import Qt
    w=QWidget();layout=QVBoxLayout(w);top=QHBoxLayout();layout.addLayout(top)
    count=QSpinBox();count.setRange(2,101);top.addWidget(QLabel('Número de ejes '+label));top.addWidget(count)
    table=QTableWidget(0,2);table.setHorizontalHeaderLabels(['Vano','Separación (m)']);table.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch);table.setMinimumHeight(120);layout.addWidget(table)
    bottom=QHBoxLayout();layout.addLayout(bottom);equal=QDoubleSpinBox();equal.setDecimals(6);equal.setRange(.000001,1e9);equal.setValue(5.);bottom.addWidget(equal);fill=QPushButton('Todas iguales');bottom.addWidget(fill)
    total=QLabel();layout.addWidget(total)
    initial=G.distances(text);initial=[b-a for a,b in zip(initial,initial[1:])];busy=False
    def read():
        import math
        values=[float(table.item(i,1).text().strip().replace(',','.')) for i in range(table.rowCount())]
        if not values or not all(math.isfinite(v) and v>0 for v in values):raise ValueError('Todas las separaciones deben ser positivas y finitas')
        if len(values)==len(initial) and all(abs(a-b)<1e-9 for a,b in zip(values,initial)):return str(text)
        return ' '.join(f'{v:.6f}' for v in values)
    def update(*_):
        if busy:return
        try:total.setText('Total '+label+': '+f'{G.distances(read())[-1]:.6f}'.rstrip('0').rstrip('.')+' m')
        except (ValueError,AttributeError):total.setText('Revise las separaciones de '+label)
    def resize(n):
        nonlocal busy
        old=[table.item(i,1).text() for i in range(table.rowCount()) if table.item(i,1) is not None]
        busy=True;table.setRowCount(n-1)
        for i in range(n-1):
            name=QTableWidgetItem(f'{i+1} — {i+2}');name.setFlags(name.flags()&~Qt.ItemIsEditable);table.setItem(i,0,name)
            value=old[i] if i<len(old) else (old[-1] if old else f'{equal.value():.6f}')
            table.setItem(i,1,QTableWidgetItem(value))
        busy=False;update()
    count.valueChanged.connect(resize);table.itemChanged.connect(update)
    count.setValue(len(initial)+1);resize(len(initial)+1)
    for i,v in enumerate(initial):table.item(i,1).setText(f'{v:.6f}')
    def fill_all():
        for i in range(table.rowCount()):table.item(i,1).setText(f'{equal.value():.6f}')
    fill.clicked.connect(fill_all);update()
    w._arq={'count':count,'table':table,'equal':equal,'fill':fill,'total':total,'read':read}
    return w,read


def _validated(dlg,buttons,read):
    from PySide6.QtWidgets import QMessageBox
    buttons.accepted.disconnect()
    def accept():
        try:read()
        except (ValueError,OverflowError) as exc:QMessageBox.warning(dlg,'Rejilla',str(exc));return
        dlg.accept()
    buttons.accepted.connect(accept)


def grid_form(ctx,values):
    from PySide6.QtWidgets import QLineEdit,QFormLayout,QDoubleSpinBox,QCheckBox,QComboBox,QHBoxLayout,QTabWidget,QWidget
    from .bim_dialogs import _dialog
    dlg,layout,buttons=_dialog(ctx,'Arquitectura — Rejilla estructural',
        'Fije el número de ejes y las separaciones. Al aceptar se pide el punto de inserción en el dibujo.')
    tabs=QTabWidget();layout.addWidget(tabs);spacing=QWidget();tables=QHBoxLayout(spacing);tabs.addTab(spacing,'Número de ejes y separaciones');edit={};readers={}
    for key,label,default in [('x','X','3x5'),('y','Y','2x4')]:
        widget,read=interval_editor(values.get(key,default),label);tables.addWidget(widget);edit[key]=widget;readers[key]=read
    appearance=QWidget();form=QFormLayout(appearance);tabs.addTab(appearance,'Orientación y representación')
    for key,label,default in [('first_number','Primer número','1'),('first_letter','Primera letra','A'),('prefix','Prefijo',''),('suffix','Sufijo','')]:
        w=QLineEdit(str(values.get(key,default)));edit[key]=w;form.addRow(label,w)
    for key,label,default in [('angle','Ángulo (°)',0),('extension','Prolongación (m)',1),('scale','Escala 1:',100),('text_mm','Texto burbuja (mm papel)',2.5),('dim_text_mm','Texto cotas (mm papel)',3.5),('radius_mm','Radio burbuja (mm papel)',4)]:
        w=QDoubleSpinBox();w.setRange(-360 if key=='angle' else .001,100000);w.setDecimals(3);w.setValue(float(values.get(key,default)));edit[key]=w;form.addRow(label,w)
    bubble=QComboBox();bubble.addItem('Círculo','circle');bubble.addItem('Hexágono','hexagon');bubble.setCurrentIndex(max(0,bubble.findData(values.get('bubble','circle'))));edit['bubble']=bubble;form.addRow('Burbuja',bubble)
    for key,label,default in [('start','Burbuja inicial',True),('end','Burbuja final',True),('dimensions','Cotas en cadena y total',True),('interactive_angle','Indicar giro con el cursor después del origen',False)]:
        w=QCheckBox(label);w.setChecked(bool(values.get(key,default)));edit[key]=w;form.addRow(w)
    layout.addWidget(buttons);dlg._arq=edit;dlg._buttons=buttons;dlg.resize(800,520)
    def read():
        data={key:fn() for key,fn in readers.items()}
        for key,w in edit.items():
            if key in readers:continue
            if isinstance(w,QLineEdit):data[key]=w.text().strip()
            elif isinstance(w,QCheckBox):data[key]=w.isChecked()
            elif isinstance(w,QComboBox):data[key]=w.currentData()
            else:data[key]=w.value()
        G.grid_geometry((0,0),data);G.letter_index(data['first_letter'])
        if int(data['first_number'])<1:raise ValueError('Numeración positiva')
        return data
    _validated(dlg,buttons,read)
    return dlg,read


def spacing_form(ctx,values):
    from PySide6.QtWidgets import QHBoxLayout
    from .bim_dialogs import _dialog
    dlg,layout,buttons=_dialog(ctx,'Arquitectura — Separaciones de rejilla',
        'Cambiar un vano desplaza los ejes siguientes y sus pilares. Se conservan identificadores y marcas; un Deshacer restaura todo.')
    row=QHBoxLayout();layout.addLayout(row);parts={};readers={}
    for key,label in [('x','X'),('y','Y')]:
        w,read=interval_editor(values[key],label);w._arq['count'].setEnabled(False);row.addWidget(w);parts[key]=w;readers[key]=read
    layout.addWidget(buttons);dlg._arq=parts;dlg._buttons=buttons;dlg.resize(760,430)
    def read():return {key:fn() for key,fn in readers.items()}
    _validated(dlg,buttons,read);return dlg,read

class GridTool(Tool):
    name='EJES'
    def start(self):
        self.name=type(self).name
        self.values={};self.mode='grid';self.first=None;self.origin=None;self.phase='origin';self.last_point=None
        from .bim_dialogs import available
        if available(self.ctx):
            dlg,read=grid_form(self.ctx,self.values)
            if dlg.exec()!=1:self.phase='finished';self.ctx.finish();return
            self.values=read()
        self.prompt('EJES: origen de rejilla o [X intervalos/Y intervalos/Angulo grados/Suelto/Fin]:')
    def on_option(self,text):
        parts=str(text).strip().split(maxsplit=1);key=parts[0].lower() if parts else ''
        if key in ('x','y','angulo','ángulo') and len(parts)==2:
            if key in ('x','y'):G.distances(parts[1]);self.values[key]=parts[1]
            else:
                self.values['angle']=float(parts[1].replace(',','.'))
                if self.phase=='angle':self._insert(self.origin);return True
            return True
        if key=='suelto':self.mode='single';self.first=None;self.prompt('Eje suelto: primer extremo:');return True
        if key in ('f','fin'):self.ctx.finish();return True
        return False
    def _insert(self,p):
        apply_architectural_change(self.ctx,G.create_grid(tuple(p[:2]),self.values),kind='column');self.phase='finished';self.ctx.finish()
    def on_point(self,p):
        if self.phase=='finished':return
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
        else:
            if self.phase=='angle':
                import math
                if math.dist(self.origin,p)<1e-6:raise ValueError('Indique una dirección distinta del origen')
                self.values['angle']=math.degrees(math.atan2(p[1]-self.origin[1],p[0]-self.origin[0]))
                self._insert(self.origin);return
            if self.values.get('interactive_angle'):
                self.origin=tuple(p[:2]);self.last_point=self.origin;self.phase='angle'
                self.prompt('EJES: dirección del eje X o [Angulo grados]; Intro conserva el ángulo:');return
            self._insert(p);return
        apply_architectural_change(self.ctx,change,kind='column');self.phase='finished';self.ctx.finish()
    def on_enter(self):
        if self.phase=='angle':self._insert(self.origin)
        else:self.phase='finished';self.ctx.finish()
    def preview_segments(self,cursor):
        if cursor is None:return []
        if self.mode=='single':return [(self.first,cursor)] if self.first is not None else []
        if self.phase=='finished':return []
        values=dict(self.values);origin=cursor
        if self.phase=='angle':
            import math
            origin=self.origin
            if math.dist(origin,cursor)>1e-6:values['angle']=math.degrees(math.atan2(cursor[1]-origin[1],cursor[0]-origin[0]))
        return G.grid_geometry(origin,values)

class RejillaTool(GridTool):name='REJILLA'

class GridEditTool(Tool):
    name='EDITAREJE';entity_picker=True
    def start(self):self.entity=None;self.prompt('EDITAREJE: designe un eje; después nuevo punto medio o [Separaciones/Ficha/Renumerar valor]:')
    def on_point(self,p):
        if self.entity is None:
            e=self.ctx.services.pick_entity(p)
            if e is not None and (G.metadata(e)or{}).get('kind')=='grid_axis':
                self.entity=e;self.prompt('Nuevo punto medio del eje o [Separaciones/Ficha/Renumerar valor]:')
            else:self.ctx.echo('Designe la línea de un eje, no su burbuja.')
            return
        a,b=G.endpoints(self.entity);dx,dy=p[0]-(a[0]+b[0])/2,p[1]-(a[1]+b[1])/2
        before=G.snapshot(require_document(self.ctx).doc)
        change=SafeArchitecturalCommand('ARQ MOVER EJE',[G.SetAxis(self.entity,[(a[0]+dx,a[1]+dy),(b[0]+dx,b[1]+dy)]),G.RegenerateGrid(before)])
        apply_architectural_change(self.ctx,change,kind='column');self.ctx.finish()
    def apply_spacing(self,values):
        drawing=require_document(self.ctx).doc
        change=G.resize_grid(drawing,G.metadata(self.entity)['grid_id'],values)
        apply_architectural_change(self.ctx,change,kind='column')

    def on_option(self,text):
        if self.entity is not None and str(text).strip().lower() in ('separaciones','tabla'):
            values,*_=G.spacing_values(require_document(self.ctx).doc,G.metadata(self.entity)['grid_id'])
            dlg,read=spacing_form(self.ctx,values)
            if dlg.exec()==1:self.apply_spacing(read())
            self.ctx.finish();return True
        if self.entity is not None and str(text).strip().lower()=='ficha':
            dlg,read=axis_form(self.ctx,self.entity)
            if dlg.exec()==1:
                values,points=read();before=G.snapshot(require_document(self.ctx).doc)
                grid_id=G.metadata(self.entity)['grid_id']
                style=[G.SetAxis(e,dim_text_height=values['dim_text_height'])
                       for e,m in G.axes(require_document(self.ctx).doc)
                       if e is not self.entity and m['grid_id']==grid_id]
                apply_architectural_change(self.ctx,SafeArchitecturalCommand('ARQ FICHA EJE',[G.SetAxis(self.entity,points,**values),*style,G.RegenerateGrid(before)]),kind='column')
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
    for key,title in [('text_height','Texto (mm papel)'),('radius','Radio (mm papel)'),('dim_text_height','Texto cotas de rejilla (mm papel)')]:
        w=QDoubleSpinBox();w.setRange(.1,100.);w.setValue(m.get(key,m['text_height'])*1000/scale);form.addRow(title,w);sizes.append(w)
    bubble=QComboBox();bubble.addItem('Círculo','circle');bubble.addItem('Hexágono','hexagon');bubble.setCurrentIndex(max(0,bubble.findData(m['bubble'])));form.addRow('Burbuja',bubble)
    ends=[]
    for i in range(2):
        w=QCheckBox('Burbuja '+('inicial' if i==0 else 'final'));w.setChecked(m['ends'][i]);form.addRow(w);ends.append(w)
    layout.insertLayout(1,form);layout.addWidget(buttons)
    def read():
        return {'label':label.text().strip(),'text_height':sizes[0].value()*scale/1000,
                'radius':sizes[1].value()*scale/1000,'dim_text_height':sizes[2].value()*scale/1000,'bubble':bubble.currentData(),
                'ends':[w.isChecked() for w in ends]},[[w.value() for w in row] for row in coords]
    dlg._arq={'label':label,'coordinates':coords,'sizes':sizes,'ends':ends,'bubble':bubble}
    return dlg,read

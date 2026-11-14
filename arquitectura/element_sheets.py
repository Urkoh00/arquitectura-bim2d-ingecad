# SPDX-License-Identifier: GPL-3.0-or-later
"""Auxiliary coherent sheets; beam/railing records are NOT authoring commands.

Walls and columns reuse the existing forms. Other sheets return validated
parameters for review/integration; they neither insert BIM nor invent exports.
"""
from __future__ import annotations
import math

TITLES={'wall':'Muro','column':'Pilar','beam':'Viga','handrail':'Tipo de pasamanos',
        'railing':'Barandilla','grille':'Reja'}
FIELDS={
 'beam': [('width','Anchura',.25),('depth','Canto',.4),('length','Longitud',3.),('base','Cota base',2.7)],
 'handrail':[('width','Anchura / diámetro',.045),('depth','Canto',.045),('height','Altura de colocación',1.)],
 'railing':[('length','Longitud',3.),('height','Altura',1.1),('spacing','Separación entre ejes de barrotes',.12),('bar_width','Anchura de barrote',.02)],
 'grille':[('width','Anchura',1.2),('height','Altura',1.4),('spacing','Separación entre ejes de barrotes',.12),('bar_width','Anchura de barrote',.02)]}


def validate(kind, record):
    if kind not in TITLES:raise ValueError('Elemento no reconocido')
    fields=FIELDS.get(kind, [('thickness','Espesor',.15),('height','Altura',2.7)] if kind=='wall'
                      else [('width','Anchura',.3),('depth','Fondo',.3),('height','Altura',2.7)])
    for key,label,default in fields:
        v=float(record.get(key,default))
        if not math.isfinite(v) or (key!='base' and v<=0):raise ValueError(label+': medida inválida')
    if kind in ('railing','grille') and record['spacing']<=record['bar_width']:
        raise ValueError('La separación debe ser mayor que la anchura del barrote')
    return record


def _preview(kind, read):
    from PySide6.QtCore import QRectF, Qt, QPointF
    from PySide6.QtGui import QPainter,QPen,QColor,QPolygonF
    from PySide6.QtWidgets import QWidget
    class Preview(QWidget):
        def __init__(self):super().__init__();self.setMinimumSize(300,230)
        def paintEvent(self,event):
            p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.fillRect(self.rect(),QColor('#fafafa'))
            try:
                v=read();validate(kind,v)
                width=float(v.get('length',v.get('width',v.get('thickness',.3))))
                height=float(v.get('height',v.get('depth',.4)))
                if kind=='beam':height=v['depth']
                points=None
                if kind=='column':
                    from .sections import column_points
                    points=column_points((0.,0.),v)
                    minx=min(q[0] for q in points);miny=min(q[1] for q in points)
                    width=max(q[0] for q in points)-minx; height=max(q[1] for q in points)-miny
                if kind=='handrail':height=v['depth'];width=v['width']
                scale=min((self.width()-50)/width,(self.height()-70)/height)
                w,h=width*scale,height*scale;x,y=(self.width()-w)/2,(self.height()-h)/2
                p.setPen(QPen(QColor('#37506a'),2))
                if points is not None:
                    p.drawPolygon(QPolygonF([QPointF(x+(a-minx)*scale,y+h-(b-miny)*scale) for a,b in points]))
                elif kind=='handrail' and v.get('section')=='Circular':
                    p.drawEllipse(QRectF(x,y,w,h))
                else:
                    p.drawRect(QRectF(x,y,w,h))
                if kind in ('railing','grille'):
                    n=min(200,int(width/v['spacing']))
                    for k in range(1,n+1):
                        xx=x+k*v['spacing']*scale;p.drawLine(int(xx),int(y),int(xx),int(y+h))
                p.drawText(12,self.height()-30,f'{width:g} × {height:g} m')
                p.drawText(12,self.height()-12,'Esquema de parámetros; no es una validación 3D')
            except (ValueError,TypeError,KeyError) as exc:
                p.drawText(self.rect(),Qt.AlignCenter,str(exc))
            finally:p.end()
    return Preview()


def element_form(ctx,kind,record=None):
    from . import bim_dialogs as B
    from PySide6.QtWidgets import (QFormLayout,QGroupBox,QLineEdit,QLabel,QHBoxLayout,
                                   QWidget,QVBoxLayout,QComboBox,QDoubleSpinBox,QDialogButtonBox)
    if kind not in TITLES:raise ValueError('Elemento no reconocido')
    data=dict(record or {})
    if kind in ('wall','column'):
        dlg,read=B.wall_form(ctx,data) if kind=='wall' else B.column_form(ctx,data,anchor=data.get('anchor',5))
        from PySide6.QtWidgets import QScrollArea
        preview=_preview(kind,read);layout=dlg.layout()
        items=[]
        while layout.count():items.append(layout.takeAt(0))
        help_widget=items[0].widget();button_widget=items[-1].widget()
        fields=QWidget();fields_layout=QVBoxLayout(fields)
        for item in items[1:-1]:
            if item.widget():fields_layout.addWidget(item.widget())
            elif item.layout():fields_layout.addLayout(item.layout())
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(fields)
        body=QHBoxLayout();body.addWidget(scroll,3);body.addWidget(preview,2)
        layout.addWidget(help_widget);layout.addLayout(body);layout.addWidget(button_widget)
        dlg.resize(1000,650)
        for w in dlg.findChildren(QDoubleSpinBox):w.valueChanged.connect(lambda *_: preview.update())
        for w in dlg.findChildren(QComboBox):w.currentIndexChanged.connect(lambda *_: preview.update())
        dlg._element_preview=preview
        return dlg,read
    dlg,layout,buttons=B._dialog(ctx,'Arquitectura — '+TITLES[kind],
        'Defina parámetros, material e identificación. Ficha auxiliar: no inserta ni exporta elementos BIM.')
    body=QHBoxLayout();left=QWidget();stack=QVBoxLayout(left)
    geometry=QGroupBox('Geometría y colocación');form=QFormLayout(geometry);stack.addWidget(geometry);editors={}
    profile=QComboBox();profile.addItems(['Rectangular','Circular','Perfil metálico'])
    profile.setCurrentText(data.get('section','Rectangular'));form.addRow('Sección:',profile)
    for key,label,default in FIELDS[kind]:
        spin=B._spin(data.get(key,default),positive=key!='base');spin.setSuffix(' m');editors[key]=spin;form.addRow(label+':',spin)
    identity=QGroupBox('Identificación y material');props=QFormLayout(identity);stack.addWidget(identity)
    for key,label,default in [('name','Nombre',TITLES[kind]),('type_name','Tipo','Genérico'),('material','Material','Acero'),('level','Nivel','Planta baja')]:
        w=QLineEdit(str(data.get(key,default)));editors[key]=w;props.addRow(label+':',w)
    status=QLabel('');status.setWordWrap(True)
    def read():
        v={**data,**{k:w.value() if isinstance(w,QDoubleSpinBox) else w.text().strip() for k,w in editors.items()}}
        v['section']=profile.currentText();return validate(kind,v)
    preview=_preview(kind,read);body.addWidget(left,3);body.addWidget(preview,2);layout.addLayout(body)
    layout.addWidget(status);layout.removeWidget(buttons);layout.addWidget(buttons)
    def refresh(*_):
        try:read();message='Parámetros válidos. Compruebe normativa y anclajes por separado.';valid=True
        except ValueError as exc:message=str(exc);valid=False
        status.setText(message);buttons.button(QDialogButtonBox.Ok).setEnabled(valid);preview.update()
    for w in editors.values():
        (w.valueChanged if isinstance(w,QDoubleSpinBox) else w.textChanged).connect(refresh)
    profile.currentIndexChanged.connect(refresh);refresh();dlg._arq={'editors':editors,'preview':preview,'status':status,'section':profile}
    dlg.resize(900,600)
    return dlg,read

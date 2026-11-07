# SPDX-License-Identifier: GPL-3.0-or-later
"""IngeCAD interactive drawing tools: 2D in modelspace, architectural data in XDATA."""
from __future__ import annotations
import math
from tools.base import Tool
from .architectural import metadata
from .architectural_v10 import (create_wall,create_opening,edit_wall,edit_opening,
                               WALL_LAYER,OPENING_LAYER)
from .tools3d import ensure_arch_layers

class MuroTool(Tool):
    name='MURO'
    def start(self):
        self.name=type(self).name
        self.startpoint=None;self.last_wall=None
        self.last_point=None  # IngeCAD ToolController: anchor for ORTHO/POLAR/tracking
        from .parameters_arq import load_defaults
        from .compat import require_document
        defaults=load_defaults(require_document(self.ctx))['wall']
        self.thickness=defaults['thickness'];self.height=defaults['height'];self.base=defaults['base'];self.reference=defaults['reference'];self.pending=None
        self.bim={k:defaults[k] for k in ('name','type_name','material','level')}
        # Prompt FIRST. No drawing mutation while ToolController.start_tool is
        # still activating this tool (some IngeCAD versions reset tools on edits).
        self.prompt('MURO: configurando propiedades arquitectónicas...')
        try:
            from . import bim_dialogs
            if bim_dialogs.available(self.ctx):
                values=bim_dialogs.wall_properties(self.ctx,{**defaults})
                if values is None:
                    self.ctx.echo('MURO: cancelado por el usuario.')
                    self.ctx.finish()
                    return
                for key in ('thickness','height','base','reference'):
                    setattr(self,key,values[key])
                self.bim={k:values[k] for k in self.bim}
            else:
                self.ctx.echo('MURO: ficha BIM no disponible; utilizando parámetros por defecto. Use E/A/C/R para cambiarlos.')
        except Exception as exc:
            # Never let a broken Qt dialog silently kill the CAD command.
            self.ctx.echo(f'MURO: error al abrir la ficha BIM ({type(exc).__name__}: {exc}). Se continúa por comandos.')
        self.prompt('MURO: primer punto o [Espesor/Altura/Cota/Referencia/Fin]:')
    def on_point(self,p):
        if self.pending:
            self.ctx.echo('Termine primero la opción numérica.');return
        if self.startpoint is None:
            self.startpoint=p
            self.last_point=p
            self.prompt('MURO: siguiente punto (Enter: nuevo tramo; [E/A/C/R/P/V/Fin]):')
            return
        if math.dist(self.startpoint,p)<1e-6:
            self.ctx.echo('Seleccione un punto distinto al origen.');return
        try:
            cmd=create_wall(self.startpoint,p,self.thickness,self.height,self.base,self.reference,**self.bim)
            from .transactions import apply_architectural_change
            apply_architectural_change(self.ctx, cmd, kind='wall')
        except Exception as exc:
            self.ctx.echo(f'MURO: no se pudo crear el tramo ({type(exc).__name__}: {exc}).')
            self.prompt('Seleccione segundo punto o corrija el error:')
            return
        self.last_wall=cmd.entity
        self.startpoint=p
        self.last_point=p
        self.prompt('MURO trazado. Siguiente punto o [E/A/C/R/Fin]:')
    def preview_segments(self, cursor):
        """Temporary four-edge wall footprint, same native preview hook as LINE."""
        if self.startpoint is None or self.pending is not None:
            return []
        try:
            from .architectural_v10 import wall_corners
            corners = wall_corners(self.startpoint, cursor, self.thickness, self.reference)
            return list(zip(corners, corners[1:] + corners[:1]))
        except ValueError:
            return []

    def on_option(self,text):
        txt=str(text).strip().lower()
        if self.pending:
            key=self.pending;self.pending=None
            if key=='reference':
                refs={'e':'eje','eje':'eje','i':'izquierda','izquierda':'izquierda',
                      'd':'derecha','derecha':'derecha'}
                if txt not in refs:self.ctx.echo('Referencia no válida: eje/izquierda/derecha');return True
                self.reference=refs[txt]
            else:
                try:v=float(txt.replace(',','.'))
                except ValueError:self.ctx.echo('Debe introducir un número.');return True
                if not math.isfinite(v) or (key!='base' and v<=0):
                    self.ctx.echo('Valor numérico no válido');return True
                setattr(self,key,v)
            self.ctx.echo(f'Parámetros: espesor {self.thickness:g}, altura {self.height:g}, cota {self.base:g}, referencia {self.reference}')
            self.prompt('Indique punto del muro:');return True
        if txt in ('e','espesor','a','altura','c','cota','r','referencia'):
            self.pending={'e':'thickness','espesor':'thickness','a':'height','altura':'height',
                          'c':'base','cota':'base','r':'reference','referencia':'reference'}[txt]
            self.prompt('Referencia [Eje/Izquierda/Derecha]:' if self.pending=='reference' else 'Valor (m):')
            return True
        if txt in ('p','puerta','v','ventana'):
            if self.last_wall is None:
                self.ctx.echo('Primero debe dibujar un tramo de muro.');return True
            self.ctx.echo('Use PUERTAARQ o VENTANAARQ para especificar el hueco sobre un muro.');return True
        if txt in ('f','fin'):self.ctx.finish();return True
        return False
    def on_enter(self):
        if self.pending:
            self.ctx.echo('Opción cancelada.');self.pending=None;return
        if self.startpoint is not None:
            self.startpoint=None
            self.last_point=None
            self.prompt('Nuevo tramo: indique primer punto o [Fin]:')
        else:self.ctx.finish()

class CarpinteriaTool(Tool):
    name='PUERTAARQ';kind='puerta'
    def start(self):
        self.name=type(self).name
        self.wall=None;self.data=[]
        self.prompt(f'{self.kind.upper()}: seleccione un muro ARQ con el ratón:')
    def on_point(self,p):
        if self.wall is not None:return
        services=getattr(self.ctx,'services',None)
        ent=services.pick_entity(p) if services else None
        if not ent or (metadata(ent) or {}).get('kind')!='wall':
            self.ctx.echo('No se seleccionó un muro ARQ.');return
        self.wall=ent
        from . import bim_dialogs
        if bim_dialogs.available(self.ctx):
            m=metadata(ent)
            values=bim_dialogs.opening_properties(self.ctx,self.kind,
                       wall_length=math.dist(m['a'],m['b']),wall_height=m['height'])
            if values is None:self.ctx.finish();return
            try:
                cmd=create_opening(self.wall,values['offset'],values['width'],
                    values['sill'],values['height'],kind=self.kind,
                    **{k:values[k] for k in ('name','type_name','material','operation')})
                self.ctx.execute(cmd);self.ctx.echo('Carpintería BIM vinculada al muro.')
            except ValueError as ex:self.ctx.echo(str(ex))
            self.ctx.finish();return
        self.prompt('Distancia desde el inicio del muro (m):')
    def on_option(self,text):
        if self.wall is None:return False
        try:value=float(str(text).replace(',','.'))
        except ValueError:self.ctx.echo('Introduzca una medida numérica válida.');return True
        if not math.isfinite(value):self.ctx.echo('Medida no finita.');return True
        self.data.append(value)
        labels=('Anchura (m):','Antepecho (m):','Altura del hueco (m):')
        if len(self.data)<4:self.prompt(labels[len(self.data)-1]);return True
        try:
            cmd=create_opening(self.wall,*self.data,kind=self.kind)
            self.ctx.execute(cmd)
            self.ctx.echo(self.kind.capitalize()+' vinculada al muro; hueco guardado en DXF.')
            self.ctx.finish()
        except ValueError as exc:
            self.ctx.echo('No se pudo crear: '+str(exc))
            self.data=[];self.prompt('Distancia desde el inicio del muro (m):')
        return True

class VentanaArqTool(CarpinteriaTool):
    name='VENTANAARQ';kind='ventana'

class EditarArqTool(Tool):
    name='EDITARARQ'
    def start(self):
        self.name=type(self).name
        self.entity=None;self.field=None
        self.prompt('Seleccione un muro o un hueco ARQ:')
    def on_point(self,p):
        services=getattr(self.ctx,'services',None)
        ent=services.pick_entity(p) if services else None
        dat=metadata(ent) if ent is not None else None
        from .arq_properties import resolve_arch_entity
        from .compat import require_document
        ent,_why=resolve_arch_entity(require_document(self.ctx),ent)
        dat=metadata(ent) if ent is not None else None
        if not dat or dat.get('kind') not in ('wall','opening','space'):
            self.ctx.echo('No se seleccionó una entidad ARQ editable.');return
        self.entity=ent
        from . import bim_dialogs
        if bim_dialogs.available(self.ctx) and dat['kind'] in ('opening','space'):
            from .arq_properties import opening_change, space_change
            values=(bim_dialogs.carpentry_properties(self.ctx,dat,editing=True) if dat['kind']=='opening'
                    else bim_dialogs.space_properties(self.ctx,dat))
            if values is not None:
                try:
                    from .transactions import apply_architectural_change
                    cmd=opening_change(ent,values) if dat['kind']=='opening' else space_change(ent,values)
                    apply_architectural_change(self.ctx, cmd, kind=dat['kind'])
                    self.ctx.echo('Propiedades BIM actualizadas en una operación.')
                except ValueError as ex:self.ctx.echo('No se pudo editar: '+str(ex))
            self.ctx.finish();return
        if bim_dialogs.available(self.ctx):
            if dat['kind']=='wall':
                values=bim_dialogs.wall_properties(self.ctx,dat)
                if values is not None:cmd=edit_wall(ent,**{k:v for k,v in values.items() if k!='ifc_class'})
            else:
                wall=next((e for e in ent.doc.modelspace() if (metadata(e) or {}).get('id')==dat['wall_id']),None)
                if wall is None:self.ctx.echo('Muro anfitrión no encontrado.');self.ctx.finish();return
                host=metadata(wall)
                values=bim_dialogs.opening_properties(self.ctx,dat['type'],dat,
                    math.dist(host['a'],host['b']),host['height'])
                if values is not None:cmd=edit_opening(ent,**{k:v for k,v in values.items() if k!='ifc_class'})
            if values is not None:
                try:
                    from .transactions import apply_architectural_change
                    apply_architectural_change(self.ctx, cmd, kind=dat['kind'])
                    self.ctx.echo('Propiedades BIM y encuentros actualizados en una operación.')
                except ValueError as ex:self.ctx.echo('No se pudo editar: '+str(ex))
            self.ctx.finish();return
        if dat['kind']=='wall':
            self.prompt('Propiedad [Espesor/Altura/Cota/Referencia]:')
        else:self.prompt('Propiedad [Desplazamiento/Anchura/Antepecho/Altura]:')
    def on_option(self,text):
        if self.entity is None:return False
        d=metadata(self.entity)
        if self.field is None:
            choices=({'espesor':'thickness','altura':'height','cota':'base','referencia':'reference'}
                     if d['kind']=='wall' else
                     {'desplazamiento':'offset','anchura':'width','antepecho':'sill','altura':'height'})
            k=str(text).strip().lower()
            if k not in choices:
                self.ctx.echo('Propiedad desconocida.');return True
            self.field=choices[k];self.prompt('Nuevo valor (m o eje/izquierda/derecha):');return True
        raw=str(text).strip().lower()
        try:
            val=raw if self.field=='reference' else float(raw.replace(',','.'))
            cmd=(edit_wall(self.entity,**{self.field:val}) if d['kind']=='wall'
                 else edit_opening(self.entity,**{self.field:val}))
            from .transactions import apply_architectural_change
            apply_architectural_change(self.ctx, cmd, kind=d['kind'])
            self.ctx.echo('Propiedad y contornos modificados; deshacer disponible en un paso.')
            self.ctx.finish()
        except ValueError as exc:self.ctx.echo(str(exc));self.prompt('Nuevo valor:')
        return True

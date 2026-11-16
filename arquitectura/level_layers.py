# SPDX-License-Identifier: GPL-3.0-or-later
"""Level controls backed exclusively by native DXF layer states."""
import hashlib
import json

from core.commands import Command
from .architectural import metadata
from .levels import load


def suffix(ident):
    return '@'+hashlib.sha256(ident.encode()).hexdigest()[:12]


def names(document, ident):
    return [ly.dxf.name for ly in document.doc.layers if ly.dxf.name.endswith(suffix(ident))]


def state(document, ident):
    layers=[document.doc.layers.get(n) for n in names(document,ident)]
    if not layers:return {'on':True,'frozen':False,'locked':False}
    def common(values):return values[0] if all(v==values[0]for v in values) else None
    return {key:common([getattr(ly,method)() for ly in layers]) for key,method in
            (('on','is_on'),('frozen','is_frozen'),('locked','is_locked'))}


def require_new(drawing, record):
    from .levels import bind
    if not load(drawing).get('layer_managed'):return
    record=bind(drawing,record)
    ident=record.get('level_id')
    if record.get('kind')=='opening' and record.get('wall_id'):
        wall=next((metadata(e) for e in drawing.modelspace() if (metadata(e)or{}).get('id')==record['wall_id']),{})
        ident=opening_level(drawing,record,wall)['id']
    if ident:
        doc=type('Drawing',(),{'doc':drawing})()
        st=state(doc,ident)
        if st['locked'] is not False or st['frozen'] is not False or st['on'] is not True:
            raise ValueError('El nivel de destino está apagado, inutilizado, bloqueado o tiene estados mixtos')


def _any_locked(document):
    """Fast exit: with no locked layer nothing can be protected."""
    return any(ly.is_locked() for ly in document.doc.layers)


def require_unlocked(document, entity):
    if not _any_locked(document):return
    if (entity.dxf.layer in document.doc.layers and document.doc.layers.get(entity.dxf.layer).is_locked())or entity.dxf.handle in locked_snapshot(document):
        raise ValueError('El elemento pertenece a una capa o nivel bloqueado')


def locked_snapshot(document):
    if not _any_locked(document):return {}
    rows=[(e,metadata(e)or{})for e in document.doc.modelspace()]
    ids=set()
    for e,m in rows:
        if e.dxf.layer not in document.doc.layers or not document.doc.layers.get(e.dxf.layer).is_locked():continue
        if m.get('id'):ids.add(m['id'])
        ids.update(m.get('wall_ids')or[])
        ids.update(m[k]for k in ('opening_id','space_id','column_id')if m.get(k))
    return {e.dxf.handle:fingerprint(e) for e,m in rows
            if m.get('kind')in('wall','column','opening','space','slab') and
            (m.get('id')in ids or m.get('wall_id')in ids)}


def fingerprint(entity):
    points=list(entity.get_points()) if entity.dxftype()=='LWPOLYLINE' else None
    return json.dumps([entity.dxf.all_existing_dxf_attribs(),points,metadata(entity)],sort_keys=True,default=str)


def check_locked(document, before):
    for handle,old in before.items():
        entity=document.doc.entitydb.get(handle)
        if entity is None or not entity.is_alive or entity.dxf.owner is None or fingerprint(entity)!=old:
            raise ValueError('La operación modificaría elementos de una capa o nivel bloqueado')


class RouteLevels(Command):
    """Assign native layers to sources and their representations; exact undo."""
    name='ARQ capas de nivel'
    needs_regen=True
    def __init__(self):self.before=[];self.created=[];self.descriptions={}
    def do(self,document):
        data=load(document)
        if not data.get('layer_managed'):return
        catalog={lv['id']:lv for lv in data['levels']}
        oldstates={i:state(document,i) for i in catalog}
        existing_levels={i:bool(names(document,i))for i in catalog}
        sources={m['id']:(e,m) for e in document.doc.modelspace() if (m:=metadata(e)or{}).get('id')}
        def ensure(prefix,ident):
            target=prefix+suffix(ident)
            if target not in document.doc.layers:
                base=document.doc.layers.get(prefix)if prefix in document.doc.layers else None
                attrs={'color':abs(base.dxf.color),'linetype':base.dxf.linetype,'lineweight':base.dxf.get('lineweight',-3),'plot':base.dxf.get('plot',1)}if base else {'color':8}
                layer=document.doc.layers.new(target,dxfattribs=attrs)
                layer.description='Nivel: '+catalog[ident]['name']
                st=oldstates[ident]if existing_levels[ident]or base is None else {'on':base.is_on(),'frozen':base.is_frozen(),'locked':base.is_locked()}
                if st['on'] is False:layer.off()
                if st['frozen'] is True:layer.freeze()
                if st['locked'] is True:layer.lock()
                self.created.append(target)
            layer=document.doc.layers.get(target)
            description='Nivel: '+catalog[ident]['name']
            if layer.description!=description:
                self.descriptions.setdefault(target,layer.description);layer.description=description
            return target
        self.before=[];self.created=[];self.descriptions={}
        for ident in catalog:ensure('ARQ-MUROS',ident)
        try:
            for e in document.doc.modelspace():
                m=metadata(e)or{};source=m;opening_ident=None
                if m.get('kind')=='junction_edge':
                    ids=m.get('wall_ids')or[]
                    source=next((sources[i][1] for i in ids if i in sources),{})
                else:
                    key=next((m[k]for k in ('opening_id','space_id','column_id') if m.get(k)),None)
                    if key in sources:source=sources[key][1]
                if source.get('kind')=='opening':
                    opening=source
                    source=sources.get(source.get('wall_id'),(None,{}))[1]
                    opening_ident=opening_level(document.doc,opening,source)['id']
                    prefix='ARQ-CARPINTERIA'
                elif source.get('kind')=='wall':
                    from .wall_categories import category,LAYERS
                    prefix=LAYERS[category(source)]
                else:prefix={'column':'ARQ-PILARES','space':'ARQ-RECINTOS','slab':'ARQ-FORJADOS'}.get(source.get('kind'))
                ident=m.get('display_level_id')or opening_ident or source.get('level_id')
                if not prefix or ident not in catalog:continue
                target=ensure(prefix,ident)
                invisible=e.dxf.get('invisible') if e.dxf.hasattr('invisible')else None
                self.before.append((e,e.dxf.layer,invisible))
                e.dxf.layer=target
                if m.get('kind')in('wall','opening'):e.dxf.invisible=1
            document.dirty=True
        except Exception:
            self.undo(document);raise
    def undo(self,document):
        for e,layer,invisible in self.before:
            if e.is_alive:
                e.dxf.layer=layer
                if invisible is None:e.dxf.discard('invisible')
                else:e.dxf.invisible=invisible
        for name,value in self.descriptions.items():
            if name in document.doc.layers:document.doc.layers.get(name).description=value
        for name in reversed(self.created):
            if name in document.doc.layers and not any(e.dxf.layer==name for e in document.doc.modelspace()):document.doc.layers.remove(name)
        document.dirty=True


def set_state(ctx, ident, prop, value):
    from .compat import require_document
    from .levels import catalog_steps
    from .transactions import SafeArchitecturalCommand
    from core.commands import DeferredCommand
    from core.layers import LayerPropertyCommand
    doc=require_document(ctx);data=load(doc)
    if ident not in {lv['id']for lv in data['levels']}:raise ValueError('Nivel inexistente')
    if prop not in ('on','frozen','locked') or type(value)is not bool:raise ValueError('Estado de nivel no válido')
    data['layer_managed']=True
    def native(_):return SafeArchitecturalCommand('Estado de capas',[
        LayerPropertyCommand(n,prop,value)for n in names(doc,ident)])
    ctx.execute(SafeArchitecturalCommand('ARQ estado de nivel',[
        *catalog_steps(doc,data),RouteLevels(),DeferredCommand('Capas nativas',native)]))


def install_toolbar(ctx, *_):
    """Public 0.8 toolbar handle; on 0.7 the commands remain available."""
    getter=getattr(ctx,'toolbar',None)
    if not callable(getter):return
    _monitor_toolbar(ctx)
    try:bar=getter('arquitectura')
    except (AttributeError,TypeError):return
    if bar is None or bar.property('arq_levels_installed'):return
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QWidget,QHBoxLayout,QLabel,QComboBox,QToolButton
    widget=QWidget(bar);row=QHBoxLayout(widget);row.setContentsMargins(4,0,4,0)
    current_layer=QLabel();row.addWidget(current_layer)
    row.addWidget(QLabel('Nivel:'));combo=QComboBox();combo.setMinimumContentsLength(14);row.addWidget(combo)
    controls={}
    for prop,label in (('on','Encendido'),('frozen','Inutilizado'),('locked','Bloqueado')):
        button=QToolButton();button.setCheckable(True);button.setText(label);row.addWidget(button);controls[prop]=button
        def toggle(value,key=prop):
            try:set_state(ctx,combo.currentData(),key,value)
            except ValueError as exc:ctx.echo(str(exc))
            refresh()
        button.clicked.connect(toggle)
    def refresh():
        doc=ctx.document
        if doc is None:widget.setEnabled(False);return
        widget.setEnabled(True);data=load(doc)
        from core.layers import current_layer_name
        current_layer.setText('Capa: '+current_layer_name(doc))
        wanted=[(lv['name'],lv['id'])for lv in data['levels']]
        if [(combo.itemText(i),combo.itemData(i))for i in range(combo.count())]!=wanted:
            combo.blockSignals(True);combo.clear()
            for text,ident in wanted:combo.addItem(text,ident)
            combo.blockSignals(False)
        if combo.currentData()!=data['active']:
            combo.blockSignals(True);combo.setCurrentIndex(max(0,combo.findData(data['active'])));combo.blockSignals(False)
        for prop,value in state(doc,data['active']).items():
            controls[prop].setChecked(value is True)
            words={'on':('Apagado','Encendido'),'frozen':('Utilizable','Inutilizado'),'locked':('Desbloqueado','Bloqueado')}
            controls[prop].setText(words[prop][value is True]+(' (mixto)' if value is None else ''))
            controls[prop].setToolTip('Estado nativo de capas'+(' (mixto)' if value is None else ''))
    def active(_):
        from .levels import apply
        data=load(ctx.document);data['active']=combo.currentData()
        try:apply(ctx,data)
        except ValueError as exc:ctx.echo(str(exc))
        refresh()
    combo.currentIndexChanged.connect(active)
    bar.addWidget(widget);bar.setProperty('arq_levels_installed',True)
    bar._arq_level_controls={'widget':widget,'active':combo,'current_layer':current_layer,**controls,'refresh':refresh}
    timer=QTimer(widget);timer.timeout.connect(refresh);timer.start(500)
    widget._timer=timer
    refresh()


def tagged(command,record):
    command.arq_record=record
    return command


def preflight(document,command):
    """Reject known locked edits before a derived command can touch groups."""
    if hasattr(command,'arq_record'):require_new(document.doc,command.arq_record)
    entity=getattr(command,'entity',None)
    if entity is not None and getattr(entity,'is_alive',False):
        require_unlocked(document,entity)
        before=getattr(command,'old_record',getattr(command,'before',{}))
        after=getattr(command,'new_record',getattr(command,'after',{}))
        if isinstance(before,dict)and isinstance(after,dict)and(before.get('level_id')!=after.get('level_id')or before.get('wall_category')!=after.get('wall_category')):
            require_new(document.doc,after)
    for entity in getattr(command,'entities',[]):
        if getattr(entity,'is_alive',False):require_unlocked(document,entity)
    for child in getattr(command,'commands',[]):preflight(document,child)


def target_available(drawing,record):
    """Geometric picking fallbacks must respect the native layer view too."""
    data=load(drawing)
    if not data.get('layer_managed'):return True
    lv=next(v for v in data['levels']if v['id']==data['active'])
    base=float(record.get('base',0));height=float(record.get('height',0))
    if not base-1e-8<=lv['elevation']<base+height-1e-8:return False
    from .wall_categories import category,LAYERS
    prefix=LAYERS[category(record)] if record.get('kind')=='wall' else 'ARQ-PILARES'
    name=prefix+suffix(lv['id'])
    if name not in drawing.layers:return False
    layer=drawing.layers.get(name)
    return layer.is_on()and not layer.is_frozen()and not layer.is_locked()


def before_command(ctx, event):
    # The public veto hook covers save/undo/close; it never vetoes them.
    install_toolbar(ctx)
    return None


_MONITOR_OWNER=object()


def _monitor_toolbar(ctx):
    """Discover a toolbar enabled later, through its public handle only.

    Timers are owned by Qt and hold weak host references; reload replaces the
    old monitor. This watches view availability, never stores layer state.
    """
    import weakref
    from PySide6.QtCore import QObject,QTimer
    from PySide6.QtWidgets import QApplication
    if not isinstance(ctx.host,QObject):return
    app=QApplication.instance()
    if app is None:return
    registry=getattr(app,'arquitectura_level_monitors',None)
    if registry is None:registry=app.arquitectura_level_monitors={}
    key=id(ctx.host);old=registry.get(key)
    if old is not None and old.arq_owner is _MONITOR_OWNER:return
    if old is not None:old.stop();old.deleteLater()
    host_ref=weakref.ref(ctx.host);context_type=type(ctx);owner=_MONITOR_OWNER
    try:echo_ref=weakref.WeakMethod(ctx.echo)
    except TypeError:echo_ref=lambda:None
    timer=QTimer(app);timer.arq_owner=_MONITOR_OWNER;registry[key]=timer
    def tick():
        import sys
        host=host_ref();alive=host is not None
        if alive:
            try:host.objectName()
            except (RuntimeError,ReferenceError):alive=False
        if not alive or getattr(sys.modules.get(__name__),'_MONITOR_OWNER',None)is not owner:
            timer.stop()
            if registry.get(key)is timer:registry.pop(key,None)
            timer.deleteLater();return
        try:
            fresh=context_type(host=host,echo=echo_ref()or(lambda _:None))
            install_toolbar(fresh)
        except Exception:  # noqa: BLE001 - a host change must not raise every tick
            timer.stop()
            if registry.get(key)is timer:registry.pop(key,None)
            timer.deleteLater()
    timer.timeout.connect(tick);timer.start(500)


def opening_level(drawing,record,wall):
    """A hosted opening belongs to the floor at its actual elevation."""
    from .levels import KEY
    if KEY not in drawing.rootdict:
        return {'id':wall.get('level_id'),'name':wall.get('level')or'Planta baja','elevation':float(wall.get('base',0))}
    from .wall_constraints import resolve
    data=load(drawing);wall=resolve(wall,data)
    z=float(wall.get('base',0))+float(record.get('sill',0))
    below=[lv for lv in data['levels']if lv['elevation']<=z+1e-8]
    return max(below,key=lambda lv:lv['elevation'])if below else min(data['levels'],key=lambda lv:lv['elevation'])

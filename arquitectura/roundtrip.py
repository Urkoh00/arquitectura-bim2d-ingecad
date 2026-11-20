# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: SINCRONIZARARQ: lee un .arqcambios de IngeTrazo, detecta conflictos con el dibujo actual, lo
#   comprueba todo en una copia y lo aplica con las órdenes de edición del plugin en un solo Deshacer.
#   También genera la «instantánea» del dibujo que viaja en el contrato (export_snapshot).
#   (Guía del código: docs/GUIA_DEL_CODIGO.md)
"""IngeCAD source snapshots and atomic acceptance of extension proposals."""
from __future__ import annotations
import copy,json,io
from . import roundtrip_model as M


def snapshot(drawing):
    from .architectural import metadata
    from .frame import reconcile
    from .parameters_arq import load_defaults
    from .levels import load
    records={}
    for e in drawing.modelspace():
        r=metadata(e)or{}
        if r.get('kind')in ('wall','opening','column','space','slab'):
            r=reconcile(e,r)
            if r is None:raise ValueError('Registro copiado o sin reconciliar')
            if r['id']in records:raise ValueError('Identidad duplicada en el origen')
            records[r['id']]=r
    defaults=load_defaults(drawing)
    catalog={'wall':defaults['wall_types'],'opening':defaults.get('opening_types',[])}
    known={t['name']for t in catalog['opening']}
    for r in records.values():
        name=r.get('type_name')
        if r['kind']=='opening' and name and name not in known:
            catalog['opening'].append({'name':name,'type':r['type'],'cabinet':bool(r.get('cabinet')),
              'values':{k:r[k]for k in M.OPEN_FIELDS if k in r}});known.add(name)
    return {'schema':1,'source_id':str(drawing.header.get('$FINGERPRINTGUID','')),
            'levels':load(drawing),'records':records,'catalog':catalog}


def conflicts(drawing,data):
    M.validate_changes(data);now=snapshot(drawing)
    if data['source_id']!=now['source_id']:raise ValueError('El dibujo no es el origen de los cambios')
    revision=M.digest(now)!=data['fingerprint'];out={}
    for change in data['changes']:
        ident=change['id'];r=now['records'].get(ident)
        if r is None:out[ident]='Elemento eliminado'
        elif revision or r!=change['before']:out[ident]='La revisión de IngeCAD ha cambiado'
    if data['catalog']['new']!=data['catalog']['old'] and (revision or now['catalog']!=data['catalog']['old']):out['catalog']='El catálogo o la revisión han cambiado'
    return out


def _steps(document,data,decisions):
    from .architectural import metadata
    from .architectural_v10 import edit_wall,edit_opening
    from .parameters_arq import load_defaults,SetArchitecturalDefaults
    index={r['id']:e for e in document.doc.modelspace() if(r:=metadata(e)or{}).get('id')}
    edits=[]
    for change in sorted(data['changes'],key=lambda c:c['before']['kind']!='wall'):
        ident=change['id']
        if decisions.get(ident)=='keep':continue
        entity=index.get(ident)
        if entity is None:raise ValueError('No se puede aplicar un cambio a un elemento eliminado: '+ident)
        values={k:p['new']for k,p in change['fields'].items()}
        command=(edit_wall if change['before']['kind']=='wall'else edit_opening)(entity,**values)
        # Validate later dependent edits against the accepted preceding changes.
        command.do(document);edits.append(command)
    if decisions.get('catalog')!='keep' and data['catalog']['new']!=data['catalog']['old']:
        values=load_defaults(document.doc);cat=data['catalog']['new']
        values['wall_types']=cat['wall'];values['opening_types']=cat['opening']
        command=SetArchitecturalDefaults(values);command.do(document);edits.append(command)
    return edits


def accept(ctx,data,decisions=None):
    """All planning/validation on a clone; one safe command on the live drawing."""
    from .compat import require_document
    from .transactions import SafeArchitecturalCommand,ArchitecturalRegeneration
    from .architectural import metadata
    from .level_layers import require_unlocked
    import ezdxf
    document=require_document(ctx);decisions=decisions or {};issues=conflicts(document.doc,data)
    if any(decisions.get(i)not in ('keep','apply')for i in issues):raise ValueError('Conflictos sin resolver: '+', '.join(issues))
    if any(v not in ('keep','apply')for v in decisions.values()):raise ValueError('Decisión no válida')
    buf=io.StringIO();document.doc.write(buf);buf.seek(0)
    from core.document import Document
    clone=Document(ezdxf.read(buf))
    # Shared validator also checks free spans and positive sizes.
    state=snapshot(document.doc)
    for change in sorted(data['changes'],key=lambda c:c['before']['kind']!='wall'):
        if decisions.get(change['id'])=='keep':continue
        state,_=M.propose(state,change['id'],{k:p['new']for k,p in change['fields'].items()})
    staged=_steps(clone,data,decisions)
    if not staged:return None
    regen=ArchitecturalRegeneration();regen.do(clone)
    index={r['id']:e for e in document.doc.modelspace() if(r:=metadata(e)or{}).get('id')}
    commands=[]
    from core.layers import NewLayerCommand
    from .wall_categories import LAYERS,category
    needed={LAYERS[category(command.new_record)]for command in staged if getattr(command,'new_record',{}).get('kind')=='wall'}
    commands.extend(NewLayerCommand(name,color=8)for name in sorted(needed)if name not in document.doc.layers)
    from .architectural_v10 import edit_wall,edit_opening
    # Commands are planned in the same order on a scratch drawing, then their
    # source entities rebound to live handles; old states remain exact copies.
    for command in staged:
        entity=getattr(command,'entity',None)
        if entity is not None:
            ident=metadata(entity)['id'];live=index[ident];require_unlocked(document,live)
            command.entity=live
        commands.append(command)
    result=SafeArchitecturalCommand('SINCRONIZARARQ',commands+[ArchitecturalRegeneration()])
    ctx.execute(result)
    return result


def leer_cambios(path,drawing):
    """La ficha y la orden textual leen y comprueban exactamente el mismo archivo."""
    from pathlib import Path
    if Path(path).stat().st_size>32*1024*1024:
        raise ValueError('Archivo de cambios demasiado grande')
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    return data,conflicts(drawing,data)


def terminar_sincronizacion(ctx,data,decisions):
    result=accept(ctx,data,decisions)
    ctx.echo('SINCRONIZARARQ: '+('cambios aplicados; exporte de nuevo a IngeTrazo.'if result else 'sin cambios.'))
    return result


def sincronizar_arq(ctx,*args):
    from pathlib import Path
    from .compat import require_document,dialog_parent
    from PySide6.QtWidgets import QFileDialog,QMessageBox,QDialog,QVBoxLayout,QTableWidget,QTableWidgetItem,QComboBox,QDialogButtonBox
    path=' '.join(map(str,args)) if args else QFileDialog.getOpenFileName(dialog_parent(ctx),'Sincronizar cambios de Arquitectura','','Cambios (*.arqcambios)')[0]
    if not path:return None
    try:
        data,issues=leer_cambios(path,require_document(ctx).doc);decisions={}
        if issues:
            dlg=QDialog(dialog_parent(ctx));dlg.setWindowTitle('Conflictos de Arquitectura');layout=QVBoxLayout(dlg)
            table=QTableWidget(len(issues),4);table.setHorizontalHeaderLabels(['Elemento','Conflicto','Valores: origen / IngeCAD / propuesta','Decisión']);layout.addWidget(table)
            current=snapshot(require_document(ctx).doc);byid={c['id']:c for c in data['changes']};dlg.resize(1100,500)
            for row,(ident,reason)in enumerate(issues.items()):
                table.setItem(row,0,QTableWidgetItem(ident));table.setItem(row,1,QTableWidgetItem(reason))
                values=[]
                if ident in byid:
                    change=byid[ident];record=current['records'].get(ident,{})
                    values=[k+': '+json.dumps([pair['old'],record.get(k),pair['new']],ensure_ascii=False)for k,pair in change['fields'].items()]
                else:values=[json.dumps(data['catalog'],ensure_ascii=False)]
                table.setItem(row,2,QTableWidgetItem('\n'.join(values)))
                combo=QComboBox();combo.addItem('Conservar IngeCAD','keep')
                if ident=='catalog' or ident in current['records']:combo.addItem('Aplicar IngeTrazo','apply')
                table.setCellWidget(row,3,combo)
            buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.accepted.connect(dlg.accept);buttons.rejected.connect(dlg.reject);layout.addWidget(buttons)
            if dlg.exec()!=QDialog.Accepted:return None
            decisions={ident:table.cellWidget(row,3).currentData()for row,ident in enumerate(issues)}
        return terminar_sincronizacion(ctx,data,decisions)
    except (ValueError,KeyError,TypeError,OSError)as exc:
        ctx.echo('SINCRONIZARARQ: '+str(exc));QMessageBox.warning(dialog_parent(ctx),'Sincronizar Arquitectura',str(exc));return None


def export_snapshot(drawing):
    """Invalid source models remain exportable as omissions, never editable."""
    try:
        value=snapshot(drawing);M.finite_tree(value);M.digest(value);return value
    except (ValueError,KeyError,TypeError):return None

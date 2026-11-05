# SPDX-License-Identifier: GPL-3.0-or-later
"""Interactive tools for experimental architectural entities."""
from __future__ import annotations
import os
import subprocess
import tempfile
from pathlib import Path

from tools.base import Tool
from .compat import require_document
from .architectural import (WALL_LAYER, OPENING_LAYER, wall_command,
                            opening_command, collect, export_spec)

def ensure_arch_layers(ctx):
    from core.layers import NewLayerCommand
    doc = require_document(ctx)
    for name, color in ((WALL_LAYER,8),(OPENING_LAYER,3)):
        if name not in doc.doc.layers:
            ctx.execute(NewLayerCommand(name,color=color))

class Muro3DTool(Tool):
    name='MURO3D'
    def start(self):
        ensure_arch_layers(self.ctx)
        self.a=None;self.thickness=0.25;self.height=2.7;self.base=0.0;self.waiting=None
        self.prompt('Primer punto del eje del muro o [Espesor/Altura/Cota]:')
    def on_point(self,p):
        if self.waiting:return
        if self.a is None:
            self.a=p;self.prompt('Siguiente punto del eje (Enter para terminar):');return
        try:
            self.ctx.execute(wall_command(self.a,p,self.thickness,self.height,self.base))
            self.a=p
            self.prompt('Siguiente punto del eje (Enter para terminar):')
        except ValueError as ex:self.ctx.echo(str(ex))
    def on_option(self,text):
        if self.waiting:
            try:
                from .architectural import finite
                v=finite(text,positive=self.waiting!='base')
            except (TypeError,ValueError):self.ctx.echo('Medida numérica no válida');return True
            setattr(self,self.waiting,v);self.waiting=None
            self.prompt('Indique punto del eje:');return True
        k=str(text).lower().strip()
        mapping={'espesor':'thickness','e':'thickness','altura':'height','a':'height','cota':'base','c':'base'}
        if k in mapping:
            self.waiting=mapping[k];self.prompt('Introduzca la medida en metros:');return True
        return False
    def on_enter(self):
        self.ctx.finish()

class Hueco3DTool(Tool):
    name='HUECO3D'
    def start(self):
        ensure_arch_layers(self.ctx)
        self.wall=None;self.values=[]
        self.prompt('Seleccione un muro MURO3D por un punto:')
    def on_point(self,p):
        if self.wall is not None:return
        services=getattr(self.ctx,'services',None)
        ent=services.pick_entity(p) if services else None
        from .architectural import metadata
        if not ent or (metadata(ent) or {}).get('kind')!='wall':
            self.ctx.echo('No se ha seleccionado un muro MURO3D.');return
        self.wall=ent
        self.prompt('Distancia desde el origen del muro (m):')
    def on_option(self,text):
        if self.wall is None:return False
        try:
            from .architectural import finite
            value=finite(text,positive=len(self.values) in (1,3))
            self.values.append(value)
            if len(self.values)<4:
                self.prompt(('Anchura del hueco (m):','Altura de antepecho (m):','Altura del hueco (m):')[len(self.values)-1]);return True
            self.ctx.execute(opening_command(self.wall,*self.values))
            self.ctx.echo('Hueco vinculado al muro; exportable a IGZ.')
            self.ctx.finish()
        except ValueError as ex:
            self.ctx.echo(str(ex))
            if len(self.values)>=4:self.ctx.finish()
        return True


def _choose_igz_path(ctx):
    """Native Qt dialog, with headless callers still able to supply a path."""
    from .compat import dialog_parent
    window = dialog_parent(ctx)
    try:
        from PySide6.QtWidgets import QFileDialog
        suggested = 'arquitectura.igz'
        if getattr(ctx, 'document', None) is not None:
            doc_path = getattr(ctx.document, 'path', None)
            if doc_path:
                suggested = str(Path(doc_path).with_suffix('.igz'))
        filename, _filter = QFileDialog.getSaveFileName(
            window, 'Exportar muros y pilares a IngeTrazo', suggested,
            'Modelo IngeTrazo (*.igz)')
        return Path(filename).expanduser().resolve() if filename else None
    except (ImportError, RuntimeError, TypeError) as exc:
        ctx.echo('No se puede abrir el selector de archivos: '+str(exc))
        return None


def _igz_paths():
    root = os.environ.get('INGETRAZO_ROOT', '').strip()
    interpreter = os.environ.get('INGETRAZO_PYTHON', '').strip()
    try:
        from PySide6.QtCore import QSettings
        prefs = QSettings('IngeCAD', 'Arquitectura')
        root = root or str(prefs.value('ingetrazo/source_root', '') or '')
        interpreter = interpreter or str(prefs.value('ingetrazo/python', '') or '')
    except ImportError:
        pass
    return root, interpreter


def configurar_igz(ctx, *args):
    """Local integration settings; neither copied into DXF nor IGZ."""
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout,
        QHBoxLayout, QLineEdit, QPushButton, QFileDialog, QVBoxLayout, QLabel, QWidget)
    root, interpreter = _igz_paths()
    host = getattr(ctx, 'host', None)
    dlg = QDialog(host)
    dlg.setWindowTitle('Arquitectura — Conexión con IngeTrazo')
    dlg.setMinimumWidth(570)
    layout = QVBoxLayout(dlg)
    layout.addWidget(QLabel('Se utiliza el escritor IGZ oficial de IngeTrazo.\n'
                            'Seleccione su código fuente y el intérprete Python que dispone de PySide6.'))
    form = QFormLayout()
    def path_row(initial, is_dir):
        container = QWidget(dlg); area = QHBoxLayout(container); area.setContentsMargins(0,0,0,0); edit = QLineEdit(initial, dlg)
        choose = QPushButton('Examinar…', dlg)
        def pick():
            if is_dir:
                result = QFileDialog.getExistingDirectory(dlg, 'Código fuente de IngeTrazo', edit.text())
            else:
                result, _ = QFileDialog.getOpenFileName(dlg, 'Intérprete Python', edit.text(), 'Ejecutables (*.exe);;Todos (*)')
            if result: edit.setText(result)
        choose.clicked.connect(pick)
        area.addWidget(edit); area.addWidget(choose)
        return container,edit
    rrow,re = path_row(root, True)
    prow,pe = path_row(interpreter, False)
    form.addRow('Carpeta IngeTrazo:', rrow)
    form.addRow('Python IngeTrazo:', prow)
    layout.addLayout(form)
    buttons = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel, dlg)
    buttons.accepted.connect(dlg.accept);buttons.rejected.connect(dlg.reject)
    layout.addWidget(buttons)
    if not dlg.exec():
        ctx.echo('CONFIGIGZ cancelado.');return
    root, interpreter = re.text().strip(), pe.text().strip()
    if not Path(root, 'formats', 'igz.py').is_file():
        ctx.echo('CONFIGIGZ: la carpeta no contiene formats/igz.py.');return
    if not Path(interpreter).is_file():
        ctx.echo('CONFIGIGZ: intérprete Python no encontrado.');return
    prefs = QSettings('IngeCAD', 'Arquitectura')
    prefs.setValue('ingetrazo/source_root', root)
    prefs.setValue('ingetrazo/python', interpreter)
    ctx.echo('CONFIGIGZ: conexión guardada. Ejecute EXPORTARIGZ.')


def _source_units(document):
    drawing = getattr(document, 'doc', document)
    return int(drawing.header.get('$INSUNITS', 0))


def _run_export(ctx,*args):
    """Export only semantic wall/column records, never regenerated 2D edges."""
    import json
    dest = Path(' '.join(map(str,args))).expanduser().resolve() if args else _choose_igz_path(ctx)
    if dest is None:
        ctx.echo('EXPORTARIGZ cancelado.'); return
    if dest.suffix.lower() != '.igz':
        ctx.echo('La salida debe tener extensión .igz'); return
    document = ctx.document
    if document is None:
        ctx.echo('No hay un dibujo activo.'); return
    insunits = _source_units(document)
    if insunits not in (0, 6):
        ctx.echo('EXPORTARIGZ: unidades DXF incompatibles ($INSUNITS=' + str(insunits) +
                 '). El prototipo exige metros (6); no convierte unidades silenciosamente.'); return
    if insunits == 0:
        ctx.echo('Aviso: el dibujo no declara unidades ($INSUNITS=0). Se interpretan como metros.');
    root, python = _igz_paths()
    if not root or not Path(root, 'formats', 'igz.py').is_file():
        ctx.echo('Configure INGETRAZO_ROOT con el directorio de código fuente de IngeTrazo.'); return
    if not python or not Path(python).is_file():
        ctx.echo('Configure INGETRAZO_PYTHON con el intérprete que ejecuta IngeTrazo (PySide6 instalado).'); return
    try:
        data = collect(document)
        n_walls, n_cols = len(data['walls']), len(data.get('columns', []))
        if not (n_walls or n_cols):
            ctx.echo('No hay muros ni pilares BIM para exportar.');return
        # Avoid exposing a partial output if the external writer fails.
        with tempfile.TemporaryDirectory(prefix='arq_igz_') as d:
            spec = Path(d, 'arquitectura.json')
            spec.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            interim = Path(d, 'modelo.igz')
            bridge = Path(__file__).with_name('igz_bridge.py')
            proc = subprocess.run([python, str(bridge), str(spec), str(interim)],
                                  cwd=root, capture_output=True, text=True, timeout=180)
            if proc.returncode:
                raise RuntimeError((proc.stderr or proc.stdout)[-1600:])
            if not interim.is_file() or interim.stat().st_size == 0:
                raise RuntimeError('IngeTrazo no produjo un archivo IGZ válido.')
            # The official serializer writes JSON for small untextured scenes;
            # large scenes may be ZIP. Verify JSON semantics when available.
            if interim.read_bytes()[:1] == b'{':
                import json as _json
                payload = _json.loads(interim.read_text(encoding='utf-8'))
                groups = payload.get('scene', {}).get('groups', [])
                if len(groups) != n_walls + n_cols:
                    raise RuntimeError('Recuento BIM incorrecto en el IGZ.')
                classes = sorted(g.get('ifc', {}).get('class') for g in groups)
                if classes != sorted(['IfcWall']*n_walls + ['IfcColumn']*n_cols):
                    raise RuntimeError('Clases IFC incorrectas en el IGZ.')
            dest.parent.mkdir(parents=True, exist_ok=True)
            # Atomic replacement even when Windows TEMP and destination are on
            # different volumes; os.replace(temp_file, D:) can fail EXDEV.
            import shutil
            from uuid import uuid4
            staged = dest.parent / (dest.name + '.tmp-' + uuid4().hex)
            try:
                shutil.copyfile(interim, staged)
                os.replace(staged, dest)
            finally:
                if staged.exists():
                    staged.unlink()
        ctx.echo(f'IGZ generado: {dest} | muros: {n_walls} | pilares: {n_cols}')
        ctx.echo('Metadatos conservados en IGZ (group.ext); su exportación a PropertySets IFC requiere adaptación de IngeTrazo.')
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.TimeoutExpired) as exc:
        ctx.echo('EXPORTARIGZ falló: '+str(exc))

exportar_igz = _run_export

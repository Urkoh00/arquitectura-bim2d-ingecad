# SPDX-License-Identifier: GPL-3.0-or-later
import pytest
from tests.test_ingecad_integration import plugin
from tests.test_wall_tools import Session


@pytest.fixture(scope='module')
def app():
    from PySide6.QtWidgets import QApplication
    q=QApplication.instance() or QApplication([]);yield q


@pytest.mark.parametrize('kind',['wall','column','beam','handrail','railing','grille'])
def test_sheets_offscreen(plugin,app,kind):
    import importlib
    S=importlib.import_module(plugin.tools['MURO'].__module__.rsplit('.',1)[0]+'.element_sheets')
    dlg,read=S.element_form(None,kind);data=read();assert data
    dlg.show();app.processEvents();image=dlg.grab();assert not image.isNull();dlg.close()


def test_bar_spacing_validation(plugin,app):
    import importlib
    S=importlib.import_module(plugin.tools['MURO'].__module__.rsplit('.',1)[0]+'.element_sheets')
    dlg,read=S.element_form(None,'railing');editors=dlg._arq['editors'];editors['bar_width'].setValue(.2);editors['spacing'].setValue(.1)
    with pytest.raises(ValueError,match='separación'):read()
    assert 'separación' in dlg._arq['status'].text().lower();dlg.close()


def test_conversion_dialog_has_all_roles(plugin,app):
    import importlib
    s=Session(plugin);P=importlib.import_module(plugin.tools['MURO'].__module__.rsplit('.',1)[0]+'.conversion_plan');D=importlib.import_module(plugin.tools['MURO'].__module__.rsplit('.',1)[0]+'.conversion_dialog')
    dlg,read=D.classification_form(None,s.document.doc,P.Classification());assert dlg._arq['role'].count()==11
    assert read().layers=={};dlg.close()


def test_column_preview_uses_native_shape(plugin,app):
    import importlib,hashlib
    S=importlib.import_module(plugin.tools['MURO'].__module__.rsplit('.',1)[0]+'.element_sheets')
    dlg,read=S.element_form(None,'column');dlg.show();app.processEvents();preview=dlg._element_preview
    def pixels():
        image=preview.grab().toImage();return hashlib.sha256(bytes(image.bits())).hexdigest()
    before=pixels();box=dlg._arq['shape'];box.setCurrentIndex(box.findData('circ'));app.processEvents()
    assert pixels()!=before and read()['shape']=='circ';dlg.close()

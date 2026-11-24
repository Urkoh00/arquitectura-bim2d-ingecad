# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: cuarto lote de la revisión automática del 24-11. Paramento de
#   longitud nula en PILAR, cota de nivel no numérica, bloqueo de capas
#   comprobado con una sola lectura del dibujo, reactor en un dibujo aún sin
#   elementos BIM y Tab que no borra lo escrito si la orden lo rechaza.
import pytest

from tests.test_ingecad_integration import plugin  # noqa: F401  (fixture)


def test_un_paramento_de_longitud_nula_es_un_valueerror():
    # antes ZeroDivisionError, que PILAR no atendía al confirmar la esquina
    from arquitectura import column_tools as CT
    with pytest.raises(ValueError, match="longitud nula"):
        CT._line_dir(((1.0, 2.0), (1.0, 2.0)))
    assert CT._line_dir(((0.0, 0.0), (0.0, 3.0))) == pytest.approx((0.0, 1.0))


@pytest.mark.parametrize("cota", [None, [1], {"z": 1}, "abc"])
def test_una_cota_de_nivel_no_numerica_es_un_valueerror(cota):
    from arquitectura import levels as LV
    data = {"schema": 1, "active": "a", "levels": [{"id": "a", "name": "PB", "elevation": cota}]}
    with pytest.raises(ValueError):
        LV.validate(data)


def test_el_bloqueo_se_comprueba_con_una_sola_lectura(monkeypatch):
    """Una orden con muchas entidades leía el dibujo entero una vez por
    entidad cuando había alguna capa bloqueada."""
    from arquitectura import level_layers as LL

    class Ent:
        is_alive = True

        def __init__(self, h):
            self.dxf = type("D", (), {"layer": "0", "handle": h})()

    class Capas:
        def __contains__(self, name):
            return False

    class Doc:
        layers = Capas()

    class Documento:
        doc = Doc()

    class Orden:
        entities = [Ent(str(i)) for i in range(50)]
        commands = []

    lecturas = []
    monkeypatch.setattr(LL, "_any_locked", lambda d: True)
    monkeypatch.setattr(LL, "locked_snapshot", lambda d: lecturas.append(1) or {})
    LL.preflight(Documento(), Orden())
    assert len(lecturas) == 1


def test_el_reactor_vigila_un_dibujo_aun_sin_elementos_bim():
    """Sin elementos BIM, ``before`` devolvía None e IngeCAD no llamaba a
    ``react``: lo que trajera la orden (pegar) quedaba sin sincronizar."""
    import ezdxf
    from arquitectura import reactor as R

    class Documento:
        doc = ezdxf.new()

    d = Documento()
    estado = R.ArquitecturaReactor().before(d)
    assert estado == {} and estado is not None
    assert R.ArquitecturaReactor().react(d, estado) is None      # nada cambió


def test_tab_rechazado_conserva_lo_escrito(plugin, monkeypatch):  # noqa: F811
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication, QLineEdit, QWidget
    from arquitectura import tabulador

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(tabulador, "host_offers_tab", lambda: False)

    class Line:
        def __init__(self):
            self.input = QLineEdit()
            self.out = []

        def echo(self, text):
            self.out.append(text)

    class Tool:
        def tab_ready(self):
            return True

        def on_tab(self, text, backwards=False):
            raise ValueError("valor no válido")

    class Services:
        pass

    services = Services()
    services.window = QWidget()
    services.window.command_line = Line()
    services.tool = Tool()

    class Ctx:
        pass

    ctx = Ctx()
    ctx.services = services
    assert tabulador.install(ctx)
    edit = services.window.command_line.input
    edit.setText("2,5x")
    app.sendEvent(edit, QKeyEvent(QEvent.KeyPress, Qt.Key_Tab, Qt.NoModifier))
    assert edit.text() == "2,5x"
    assert any("valor no válido" in t for t in services.window.command_line.out)

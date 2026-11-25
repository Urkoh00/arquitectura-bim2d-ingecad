# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: perfiles de trabajo (Planos 2D, Modelo BIM, Modelo Térmico). El perfil decide
#   las órdenes ofrecidas, los avisos de ARQVALIDAR y los campos térmicos; la 1.0
#   publica solo Planos 2D, que es el perfil por defecto.
import pytest

from arquitectura import perfiles as PF


def _entradas(menu):
    from core.plugins import Submenu
    for e in menu:
        if isinstance(e, Submenu):
            yield from _entradas(e.items)
        elif hasattr(e, "command"):
            yield e.command


def _spec(monkeypatch, perfil):
    if perfil is None:
        monkeypatch.delenv("ARQ_PERFIL", raising=False)
    else:
        monkeypatch.setenv("ARQ_PERFIL", perfil)
    import arquitectura
    return arquitectura._spec_kwargs()


def test_por_defecto_planos_2d_y_es_el_unico_publicado(monkeypatch):
    monkeypatch.delenv("ARQ_PERFIL", raising=False)
    assert PF.perfil_activo() == "planos"
    assert PF.PUBLICADOS == ("planos",)
    monkeypatch.setenv("ARQ_PERFIL", "desconocido")
    assert PF.perfil_activo() == "planos"


def test_planos_2d_no_ofrece_exportacion_ni_datos_termicos(monkeypatch):
    spec = _spec(monkeypatch, None)
    menu = set(_entradas(spec["menu"]))
    barra = {e.command for e in spec["toolbar"]}
    fuera = {"EXPORTARBIM", "SINCRONIZARARQ", "USOSARQ", "BIBLIOTECAHE", "CATALOGOEC"}
    assert not (menu | barra) & fuera
    assert {"MURO", "CARPINTERIA", "SECCIONARQ", "ALZADOARQ", "SUPERFICIES", "ARQVALIDAR"} <= menu
    assert "Intercambio BIM" not in [getattr(e, "label", "") for e in spec["menu"]]
    # escritas, explican por qué no se ejecutan (también la variante con guion)
    for nombre in ("EXPORTARBIM", "-EXPORTARBIM", "BIBLIOTECAHE"):
        assert nombre in spec["commands"] and nombre not in spec["tools"]

        class Ctx:
            dichos = []

            def echo(self, texto):
                self.dichos.append(texto)

        ctx = Ctx()
        spec["commands"][nombre](ctx)
        assert "versión posterior" in ctx.dichos[0] and "Planos 2D" in ctx.dichos[0]


@pytest.mark.parametrize("perfil,dentro,fuera", [
    ("bim", {"EXPORTARBIM", "SINCRONIZARARQ"}, {"BIBLIOTECAHE", "USOSARQ", "CATALOGOEC"}),
    ("termico", {"EXPORTARBIM", "BIBLIOTECAHE", "USOSARQ", "CATALOGOEC"}, set()),
])
def test_los_perfiles_son_acumulativos(monkeypatch, perfil, dentro, fuera):
    spec = _spec(monkeypatch, perfil)
    menu = set(_entradas(spec["menu"]))
    assert dentro <= menu and not (menu & fuera)
    assert {"MURO", "SECCIONARQ"} <= menu


def test_arqvalidar_solo_avisa_de_capas_en_el_perfil_termico(monkeypatch):
    import ezdxf
    from arquitectura import quality as Q

    class Documento:
        doc = ezdxf.new()

    monkeypatch.setattr(Q, "_avisos_capas", lambda *_a: ["AVISO-TERMICO"])
    monkeypatch.delenv("ARQ_PERFIL", raising=False)
    assert "AVISO-TERMICO" not in Q.audit_architecture(Documento())["incidencias"]
    monkeypatch.setenv("ARQ_PERFIL", "termico")
    assert "AVISO-TERMICO" in Q.audit_architecture(Documento())["incidencias"]


def test_menu_sin_separadores_sobrantes(monkeypatch):
    from core.plugins import SEPARATOR
    menu = _spec(monkeypatch, None)["menu"]
    assert menu[-1] != SEPARATOR
    assert all(not (a == SEPARATOR and b == SEPARATOR) for a, b in zip(menu, menu[1:]))

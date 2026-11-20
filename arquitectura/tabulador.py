# SPDX-License-Identifier: GPL-3.0-or-later
# Resumen: La tecla Tab recorre las cotas temporales y fija su valor (muros y carpinterías).
#   (Guía del código: docs/GUIA_DEL_CODIGO.md)
"""Tab through the temporary dimensions.

While MURO or a carpentry command runs, Tab moves to the next temporary
dimension or angle (Shift+Tab to the previous one). If a value is typed
before pressing Tab, that dimension is fixed to it (shown in green, between
brackets) and the next one becomes active; the rest keep following the
cursor. Enter, or a click, places the element with the fixed values.

IngeCAD 0.8 hands only F4–F6 to the running tool (``Tool.on_key``); Tab
moves the keyboard focus. Until the host offers Tab to the tool, a small
event filter does it: it acts only when the running tool has ``on_tab`` and
says it is ready (``tab_ready``); otherwise Tab does what it always did.
"""
from __future__ import annotations

_FILTER = None


def press(tool, text="", backwards=False):
    """Give Tab to ``tool`` with the text typed so far. True if used.
    (What the event filter calls; tests call it directly.)"""
    fn = getattr(tool, "on_tab", None)
    ready = getattr(tool, "tab_ready", None)
    if not callable(fn) or (callable(ready) and not ready()):
        return False
    fn(str(text or ""), backwards=backwards)
    return True


def _typed(edit):
    """What the user typed in the command line, without the inline
    suggestion the completer adds after it."""
    fn = getattr(edit, "_typed_text", None)
    try:
        return fn() if callable(fn) else edit.text()
    except Exception:  # noqa: BLE001
        return ""


def install(ctx):
    """Install the filter once (with Qt); it follows the latest window."""
    global _FILTER
    services = getattr(ctx, "services", None)
    window = getattr(services, "window", None)
    if services is None or window is None:
        return False
    try:
        from PySide6.QtCore import QEvent, QObject, Qt
        from PySide6.QtWidgets import QApplication
    except Exception:  # noqa: BLE001
        return False
    app = QApplication.instance()
    if app is None:
        return False
    if _FILTER is not None:
        _FILTER.services = services
        return True

    class _TabFilter(QObject):
        def eventFilter(self, obj, event):  # noqa: N802 (Qt)
            try:
                if event.type() != QEvent.KeyPress or event.key() not in (Qt.Key_Tab,
                                                                           Qt.Key_Backtab):
                    return False
                if event.modifiers() & (Qt.ControlModifier | Qt.AltModifier):
                    return False
                services = self.services
                tool = getattr(services, "tool", None)
                if not callable(getattr(tool, "on_tab", None)):
                    return False
                ready = getattr(tool, "tab_ready", None)
                if callable(ready) and not ready():
                    return False
                line = getattr(getattr(services, "window", None), "command_line", None)
                edit = getattr(line, "input", None)
                text = _typed(edit) if edit is not None else ""
                backwards = (event.key() == Qt.Key_Backtab
                             or bool(event.modifiers() & Qt.ShiftModifier))
                try:
                    press(tool, text, backwards)
                except Exception as exc:  # noqa: BLE001
                    if line is not None:
                        line.echo(f"Tab: {type(exc).__name__}: {exc}")
                if edit is not None:
                    edit.clear()
                for name in ("_preview_now",):
                    fn = getattr(services, name, None)
                    if callable(fn):
                        fn()
                changed = getattr(services, "changed", None)
                if changed is not None:
                    changed.emit()
                return True
            except Exception:  # noqa: BLE001  never break the keyboard
                return False

    _FILTER = _TabFilter()
    _FILTER.services = services
    app.installEventFilter(_FILTER)
    return True

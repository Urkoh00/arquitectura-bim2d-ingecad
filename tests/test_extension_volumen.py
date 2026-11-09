# SPDX-License-Identifier: GPL-3.0-or-later
"""The IngeTrazo extension's check measures volume in double precision.

Found by the user on 9-11-2026: a plan drawn 35 m from the origin could not
be imported in IngeTrazo 0.6.1; the check compared IngeTrazo's float32
takeoff (REGISTRO_UPSTREAM T-01) and refused a door that was exact."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _ext():
    spec = importlib.util.spec_from_file_location("arquitectura_bim", ROOT / "ingetrazo_ext" / "arquitectura_bim.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Face:
    def __init__(self, tris):
        self.tris = tris

    def triangulate(self):
        return self.tris


def _box(x0, y0, dx, dy, h):
    from PySide6.QtGui import QVector3D as V
    p = [V(x0, y0, 0), V(x0 + dx, y0, 0), V(x0 + dx, y0 + dy, 0), V(x0, y0 + dy, 0)]
    q = [V(v.x(), v.y(), h) for v in p]
    quads = [(p[3], p[2], p[1], p[0]), (q[0], q[1], q[2], q[3])] + \
        [(p[i], p[(i + 1) % 4], q[(i + 1) % 4], q[i]) for i in range(4)]
    return [_Face([(a, b, c), (a, c, d)]) for a, b, c, d in quads]


def test_volumen_en_doble_precision_lejos_del_origen():
    from PySide6.QtGui import QVector3D
    m = _ext()
    faces = _box(-28.05, 22.746802079171985, 0.15, 0.885, 2.1)
    naive = abs(sum(QVector3D.dotProduct(t[0], QVector3D.crossProduct(t[1], t[2])) / 6.0
                    for f in faces for t in f.triangulate()))
    exact = 0.15 * 0.885 * 2.1
    group = type("G", (), {"mesh": type("M", (), {"faces": faces})()})()
    assert abs(naive - exact) > 1e-5                        # what IngeTrazo's takeoff gives
    assert m._volume64(group) == pytest.approx(exact, abs=1e-6)

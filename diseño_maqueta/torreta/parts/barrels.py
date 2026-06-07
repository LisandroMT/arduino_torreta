"""Cañón gatling (fijo a la cuna; bascula con el tilt).

Reescrito hacia la referencia: cañones LARGOS y FINOS expuestos, montados en una
recámara compacta y sujetos por un par de abrazaderas cerca de la base y un anillo
de boca en la punta. Nada de camisa gruesa.

Marco de cabezal: origen = eje de elevación, +X = dirección de tiro.
"""
from __future__ import annotations

import math

from build123d import Cylinder, Pos, Rot

from ..config import Config


def _x(radius, length):
    """Cilindro de eje X (build123d lo crea en Z; se rota 90° sobre Y)."""
    return Rot(0, 90, 0) * Cylinder(radius=radius, height=length)


def build(cfg: Config):
    b = cfg.barrels
    r_bc = b.bolt_circle_dia_mm / 2
    r_cl = r_bc + b.tube_dia_mm / 2           # radio exterior del racimo

    body = None        # recámara, abrazaderas, anillo de boca (oscuro)
    tubes = None       # los cañones (claro)

    def add_body(s):
        nonlocal body
        body = s if body is None else body + s

    def add_tube(s):
        nonlocal tubes
        tubes = s if tubes is None else tubes + s

    # --- Recámara compacta (rear, solapa la cuna) -----------------------------
    bl = b.breech_length_mm
    x_breech0 = -4.0
    add_body(Pos(x_breech0 + bl / 2, 0, 0) * _x(b.breech_dia_mm / 2, bl))

    # --- Cañones finos y largos -----------------------------------------------
    x_tube0 = x_breech0 + 2
    x_tube_c = x_tube0 + b.length_mm / 2
    for i in range(b.n_tubes):
        ang = 2 * math.pi * i / b.n_tubes
        y, z = r_bc * math.cos(ang), r_bc * math.sin(ang)
        add_tube(Pos(x_tube_c, y, z) * _x(b.tube_dia_mm / 2, b.length_mm))

    # --- Abrazaderas oscuras cerca de la recámara -----------------------------
    for k in range(b.clamp_count):
        cx = x_breech0 + bl + 4 + k * (b.clamp_width_mm + 6)
        ring = _x(r_cl + b.clamp_extra_r_mm, b.clamp_width_mm) - _x(r_bc - 0.6,
                                                                   b.clamp_width_mm + 2)
        add_body(Pos(cx, 0, 0) * ring)

    # --- Anillo de boca que une las puntas ------------------------------------
    x_muzzle = x_tube0 + b.length_mm - b.muzzle_ring_mm / 2
    muzzle = _x(r_cl + 0.8, b.muzzle_ring_mm) - _x(r_bc - 0.4, b.muzzle_ring_mm + 2)
    add_body(Pos(x_muzzle, 0, 0) * muzzle)

    # --- Eje central hueco (futuro láser) -------------------------------------
    if b.hollow_axis:
        x_mid = x_tube0 + b.length_mm / 2
        bore = Pos(x_mid, 0, 0) * _x(b.central_axis_dia_mm / 2, b.length_mm + 12)
        if body is not None:
            body -= bore
        if tubes is not None:
            tubes -= bore

    # --- Spin cosmético del racimo --------------------------------------------
    if cfg.pose.spin_deg:
        body = Rot(cfg.pose.spin_deg, 0, 0) * body
        tubes = Rot(cfg.pose.spin_deg, 0, 0) * tubes

    return [(body, "body"), (tubes, "tube")]


if __name__ == "__main__":
    from ..render import render_roleparts
    cfg = Config.load()
    print("render ->", render_roleparts(build(cfg), cfg, "outputs/_wip_barrels.png",
                                        title="Cañón fino", hero=True))

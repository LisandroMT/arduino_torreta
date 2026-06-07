"""Pedestal giratorio (pan).

Tambor cilíndrico corto que, en la torreta real, se acopla al horn del servo de
paneo y constituye la base del cuerpo blindado. Lleva un par de panel lines
(ranuras horizontales) decorativas.
"""
from __future__ import annotations

from build123d import Cylinder, Pos

from ..config import Config


def z_base(cfg: Config) -> float:
    """Altura (Z) a la que apoya el pedestal: encima del collar de la base."""
    return cfg.base.collar_height_mm


def z_top(cfg: Config) -> float:
    """Altura (Z) de la cara superior del pedestal (donde apoya el cuerpo)."""
    return z_base(cfg) + cfg.pedestal.height_mm


def build(cfg: Config):
    p = cfg.pedestal
    z0 = z_base(cfg)
    r = p.diameter_mm / 2

    # Se extiende 2 mm hacia abajo dentro del collar para que la fusión sea sólida.
    ov = 2.0
    drum = Pos(0, 0, (z0 - ov) + (p.height_mm + ov) / 2) * Cylinder(
        radius=r, height=p.height_mm + ov)

    # Panel lines: ranuras horizontales (anillos rebajados poco profundos).
    for i in range(p.panel_line_count):
        frac = (i + 1) / (p.panel_line_count + 1)
        zc = z0 + frac * p.height_mm
        groove = Cylinder(radius=r + 0.5, height=1.0) - Cylinder(
            radius=r - p.panel_line_depth_mm, height=1.0)
        drum -= Pos(0, 0, zc) * groove

    return [(drum, "body")]


if __name__ == "__main__":
    from ..render import render_roleparts
    from . import base
    cfg = Config.load()
    parts = base.build(cfg) + build(cfg)
    print("render ->", render_roleparts(parts, cfg, "outputs/_wip_pedestal.png",
                                        title="Base + pedestal"))

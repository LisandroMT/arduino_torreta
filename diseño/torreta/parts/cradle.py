"""Cuna / yugo (bascula en tilt).

Bloque que entra entre las orejas del muñón del cuerpo y sostiene el cañón. Pivota
sobre el pasador del tilt (eje Y a través del origen del marco de cabezal). Al
imprimir, la cuna y el cañón se fusionan en una sola pieza ('gun').

Marco de cabezal: origen = eje de elevación (pasador del tilt), +X = tiro.
"""
from __future__ import annotations

from build123d import Axis, Box, Cylinder, Pos, Rot, chamfer, fillet

from ..config import Config


def build(cfg: Config):
    c = cfg.cradle
    pin_r = cfg.body.trunnion_pin_dia_mm / 2 + cfg.glb.clearance_mm

    # Bloque principal, ligeramente adelantado para abrazar la recámara del cañón.
    block = Box(c.depth_mm, c.width_mm, c.height_mm)
    block = Pos(2.0, 0, 0) * block
    try:
        block = chamfer(block.edges(), c.chamfer_mm)
    except Exception:
        pass

    # Mejillas laterales redondeadas hacia el eje del pasador (look de yugo).
    cheek = Rot(90, 0, 0) * Cylinder(radius=c.height_mm * 0.42, height=c.width_mm)
    block += cheek                                      # centrado en el pivote

    # Orificio del pasador del tilt (eje Y).
    block -= Rot(90, 0, 0) * Cylinder(radius=pin_r, height=c.width_mm + 6)

    return [(block, "body")]


if __name__ == "__main__":
    from ..render import render_roleparts
    from . import barrels
    cfg = Config.load()
    print("render ->", render_roleparts(build(cfg) + barrels.build(cfg), cfg,
                                        "outputs/_wip_gun.png",
                                        title="Cuna + cañón", hero=True))

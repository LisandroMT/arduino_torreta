"""Base (estática).

Plataforma hexagonal baja con 3 patas (trípode) tipo paleta con textura de pisada
en grilla y chevrones amarillos en las facetas. En el centro lleva el socket de la
junta de pan donde gira el eje del cuerpo, con paso para el tornillo de retención.

Marco global, pose neutra. +X = frente.
"""
from __future__ import annotations

import math

from build123d import Axis, Box, Cylinder, Polygon, Pos, Rot, chamfer, extrude, fillet

from ..config import Config
from ..geom import circumradius_from_across_flats, reg_prism


def _leg(cfg: Config):
    """Una pata tipo paleta hacia +X, con punta redondeada y textura de pisada."""
    b = cfg.base
    x0 = b.hex_across_flats_mm * 0.30
    x1 = x0 + b.leg_length_mm
    rw, tw, th = b.leg_root_width_mm, b.leg_tip_width_mm, b.leg_thickness_mm

    plan = Polygon((x0, -rw / 2), (x0, rw / 2), (x1, tw / 2), (x1, -tw / 2), align=None)
    leg = extrude(plan, amount=th)
    try:
        leg = fillet(leg.edges().filter_by(Axis.Z).group_by(Axis.X)[-1], min(7, tw / 2 - 1))
    except Exception:
        pass

    # Textura de pisada: grilla de rebajes rectangulares en la cara superior.
    rows, cols = max(1, b.tread_rows), max(1, b.tread_cols)
    gx0, gx1 = x0 + b.leg_length_mm * 0.28, x1 - 9
    depth = min(1.8, th * 0.3)
    for r in range(rows):
        tx = gx0 + (gx1 - gx0) * (r + 0.5) / rows
        for c in range(cols):
            ty = (-tw * 0.32) + (tw * 0.64) * (c + 0.5) / cols
            leg -= Pos(tx, ty, th - depth / 2) * Box((gx1 - gx0) / rows * 0.55,
                                                     tw * 0.64 / cols * 0.6, depth)
    leg -= Pos(x1 - 9, 0, th / 2) * Cylinder(radius=2.0, height=th + 2)
    return leg


def _chevron(width, depth, z):
    """Chevron (>) amarillo formado por dos barras finas en V, sobre el plano XY a z."""
    bar = Box(depth, width * 0.62, 2.0)
    a = Rot(0, 0, 28) * Pos(0, -width * 0.28, 0) * bar
    b = Rot(0, 0, -28) * Pos(0, width * 0.28, 0) * bar
    return Pos(0, 0, z) * (a + b)


def build(cfg: Config):
    b = cfg.base
    af = b.hex_across_flats_mm
    parts = []

    # --- Plataforma hexagonal con bisel superior ------------------------------
    plat = reg_prism(af, 6, b.height_mm, rotation=0)
    try:
        plat = chamfer(plat.edges().group_by(Axis.Z)[-1], b.top_chamfer_mm)
    except Exception:
        pass

    # --- Socket de pan + paso del tornillo ------------------------------------
    plat -= Pos(0, 0, b.height_mm - b.pan_socket_depth_mm / 2 + 0.01) * Cylinder(
        radius=b.pan_socket_dia_mm / 2, height=b.pan_socket_depth_mm)
    plat -= Pos(0, 0, b.height_mm / 2) * Cylinder(radius=b.pan_screw_dia_mm / 2 + 0.3,
                                                  height=b.height_mm + 2)
    plat -= Pos(0, 0, 1.5) * Cylinder(radius=3.2, height=3)   # avellanado de la cabeza

    # --- Patas (trípode) ------------------------------------------------------
    structure = plat
    for i in range(b.n_legs):
        ang = b.leg_orient_deg + i * 360.0 / b.n_legs
        structure += Rot(0, 0, ang) * _leg(cfg)
    parts.append((structure, "body"))

    # --- Chevrones amarillos en las facetas (frente y laterales libres) -------
    if b.chevron_accents:
        r_face = af / 2 - 1                       # sobre la faceta, cerca del borde
        chev_z = b.height_mm - b.top_chamfer_mm * 0.4
        leg_angs = {(b.leg_orient_deg + i * 360.0 / b.n_legs) % 360 for i in range(b.n_legs)}
        for k in range(6):                        # 6 facetas del hexágono
            ang = 60 * k
            if any(abs(((ang - la + 180) % 360) - 180) < 25 for la in leg_angs):
                continue                          # saltar facetas tapadas por patas
            chev = _chevron(20, 4, chev_z)
            chev = Rot(0, 0, ang) * Pos(r_face, 0, 0) * Rot(0, 0, 90) * chev
            parts.append((chev, "accent"))

    return parts


if __name__ == "__main__":
    from ..render import render_roleparts
    cfg = Config.load()
    print("render ->", render_roleparts(build(cfg), cfg, "outputs/_wip_base.png",
                                        title="Base hexagonal", hero=True))

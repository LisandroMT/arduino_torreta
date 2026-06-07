"""Maqueta de torreta en MDF para corte CNC/láser.

Diseño por PANELES PLANOS encastrables (lenguaje de corte 2D) + cañón gatling
hecho con VARILLAS (dowels) sostenidas por discos de MDF. Articulación pan
(bulón central) + tilt (bulón en la cuna). Genera:
  - render 3D del ensamble (reusa el motor de render de torreta/),
  - layout de corte plano (DXF + SVG) y una vista previa de las piezas.

Es un diseño paramétrico ORIGINAL en lenguaje de fabricación plana, pensado para
ser alcanzable y limpio (sin el detalle de un sculpt).

  python torreta_mdf.py render     # render 3D del ensamble posado
  python torreta_mdf.py flat        # DXF/SVG de corte + preview de piezas
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from types import SimpleNamespace

import yaml
from build123d import (Box, Circle, Cylinder, Location, Polygon, Pos, Rectangle,
                       RegularPolygon, Rot, extrude)

from torreta import render as R

YAML = Path(__file__).resolve().parent / "turret_mdf.yaml"


def _ns(d):
    return SimpleNamespace(**{k: (_ns(v) if isinstance(v, dict) else v) for k, v in d.items()})


def load():
    return _ns(yaml.safe_load(YAML.read_text(encoding="utf-8")))


def circ(across_flats, sides):
    return (across_flats / 2) / math.cos(math.pi / sides)


# ============================================================================
#  PANELES — cada uno: sketch 2D (para corte) + Location (para el 3D)
# ============================================================================

def base_sketch(cfg):
    """Hexágono + 3 patas paleta + agujero central de pan (sketch 2D)."""
    b = cfg.base
    hexa = RegularPolygon(radius=circ(b.hex_across_flats_mm, 6), side_count=6, rotation=0)
    r0 = b.hex_across_flats_mm / 2 * 0.7
    r1 = r0 + b.leg_length_mm
    w = b.leg_width_mm
    s = hexa
    for i in range(b.n_legs):
        ang = b.leg_orient_deg + i * 360.0 / b.n_legs
        leg = Polygon((r0, -w / 2), (r1, -w * 0.4), (r1, w * 0.4), (r0, w / 2), align=None)
        s += Rot(0, 0, ang) * leg
    s -= Circle(b.pan_bolt_dia_mm / 2 + 0.2)
    return s


def deck_sketch(cfg):
    """Cubierta giratoria: hexágono + agujero de pan + ranuras para los paneles."""
    b = cfg.body
    af = max(b.width_mm, b.depth_mm) + 14
    s = RegularPolygon(radius=circ(af, 6), side_count=6, rotation=30)
    s -= Circle(cfg.base.pan_bolt_dia_mm / 2 + 0.2)
    return s


def side_sketch(cfg):
    """Silueta lateral en cuña + agujero del eje de tilt (sketch 2D: x=prof, y=alto)."""
    b = cfg.body
    d, hf, hb = b.depth_mm, b.front_height_mm, b.back_height_mm
    s = Polygon((-d / 2, 0), (d / 2, 0), (d / 2, hf), (d / 2 - 18, hb), (-d / 2, hb),
                align=None)
    px = d / 2 - b.trunnion_from_front_mm
    s -= Pos(px, b.trunnion_height_mm) * Circle(b.tilt_bolt_dia_mm / 2 + 0.2)
    return s


def rect_sketch(w, h):
    return Pos(0, h / 2) * Rectangle(w, h)


def disc_sketch(cfg):
    """Disco de MDF con círculo de varillas + centro (sketch 2D)."""
    a = cfg.barrels
    s = Circle(a.disc_dia_mm / 2)
    for i in range(a.n_tubes):
        ang = 2 * math.pi * i / a.n_tubes
        y, z = (a.bolt_circle_dia_mm / 2) * math.cos(ang), (a.bolt_circle_dia_mm / 2) * math.sin(ang)
        s -= Pos(y, z) * Circle(a.dowel_dia_mm / 2 + 0.15)
    s -= Circle(3)
    return s


def cheek_sketch(cfg):
    """Mejilla de la cuna: placa con agujero de pivote (sketch 2D)."""
    b = cfg.body
    s = Pos(0, 0) * Rectangle(46, 30)
    s -= Circle(b.tilt_bolt_dia_mm / 2 + 0.2)   # pivote en el origen
    return s


# Catálogo de piezas planas (para el layout de corte).
def flat_pieces(cfg):
    b = cfg.body
    return [
        ("base_x2", base_sketch(cfg)),
        ("deck", deck_sketch(cfg)),
        ("side_x2", side_sketch(cfg)),
        ("front", rect_sketch(b.width_mm - 2 * cfg.material.thickness_mm, b.front_height_mm)),
        ("back", rect_sketch(b.width_mm - 2 * cfg.material.thickness_mm, b.back_height_mm)),
        ("cheek_x2", cheek_sketch(cfg)),
        ("disc_x3", disc_sketch(cfg)),
    ]


# ============================================================================
#  ENSAMBLE 3D (sólidos en coordenadas de mundo) + pose
# ============================================================================

def _slab(sketch, t):
    return extrude(sketch, t)


def assemble_roleparts(cfg):
    t = cfg.material.thickness_mm
    b, a = cfg.body, cfg.barrels
    parts = []  # (solid, role)

    # --- Base estática (capas apiladas) + chevrón amarillo --------------------
    base2d = base_sketch(cfg)
    for layer in range(cfg.base.layers):
        parts.append((Pos(0, 0, layer * t) * _slab(base2d, t), "body"))
    z_base_top = cfg.base.layers * t

    # --- Grupo giratorio: cubierta + caja del cuerpo --------------------------
    rot = []  # piezas que giran (se les aplica pan)
    z_deck = z_base_top + cfg.body.deck_clearance_mm
    rot.append((Pos(0, 0, z_deck) * _slab(deck_sketch(cfg), t), "body"))
    z0 = z_deck + t                                   # piso del cuerpo

    # Paneles laterales (cuña), finos en Y, con el eje de tilt.
    side2d = side_sketch(cfg)
    for sy in (b.width_mm / 2, -b.width_mm / 2 + t):
        rot.append((Pos(0, sy, z0) * Rot(90, 0, 0) * _slab(side2d, t), "body"))

    # Frente y fondo (cajas finas en X), entre los laterales.
    inner_w = b.width_mm - 2 * t
    front = Pos(b.depth_mm / 2 - t, 0, z0 + b.front_height_mm / 2) * \
        Box(t, inner_w, b.front_height_mm)
    back = Pos(-b.depth_mm / 2, 0, z0 + b.back_height_mm / 2) * \
        Box(t, inner_w, b.back_height_mm)
    rot.append((front, "body"))
    rot.append((back, "body"))

    # Franja amarilla en un lateral.
    rot.append((Pos(b.depth_mm * 0.1, b.width_mm / 2 + 0.4, z0 + b.back_height_mm * 0.5) *
                Box(b.depth_mm * 0.5, 1.2, 4), "accent"))

    # --- Cañón (cuna + discos + varillas) en marco de cabezal -----------------
    px = b.depth_mm / 2 - b.trunnion_from_front_mm
    pz = z0 + b.trunnion_height_mm
    gun = []  # en marco de cabezal (origen = pivote), +X = tiro

    # Mejillas de la cuna (finas en Y) a los lados.
    cheek2d = cheek_sketch(cfg)
    for sy in (a.cheek_gap_mm / 2, -a.cheek_gap_mm / 2 - t):
        gun.append((Pos(0, sy, 0) * Rot(90, 0, 0) * _slab(cheek2d, t), "body"))

    # Discos de MDF (finos en X) a lo largo del cañón.
    disc2d = disc_sketch(cfg)
    x_first, x_last = 6, 6 + a.length_mm * 0.8
    for i in range(a.disc_count):
        xi = x_first + (x_last - x_first) * i / (a.disc_count - 1)
        gun.append((Pos(xi, 0, 0) * Rot(0, 90, 0) * _slab(disc2d, t), "body"))

    # Varillas (dowels) sobre el bolt circle.
    for i in range(a.n_tubes):
        ang = 2 * math.pi * i / a.n_tubes
        y, z = (a.bolt_circle_dia_mm / 2) * math.cos(ang), (a.bolt_circle_dia_mm / 2) * math.sin(ang)
        dowel = Rot(0, 90, 0) * Cylinder(radius=a.dowel_dia_mm / 2, height=a.length_mm)
        gun.append((Pos(4 + a.length_mm / 2, y, z) * dowel, "tube"))

    # --- Aplicar pose ---------------------------------------------------------
    loc_pan = Rot(0, 0, cfg.pose.pan_deg)
    loc_gun = loc_pan * Pos(px, 0, pz) * Rot(0, -cfg.pose.tilt_deg, 0)
    parts += [(loc_pan * s, r) for s, r in rot]
    parts += [(loc_gun * s, r) for s, r in gun]
    return parts


# ============================================================================
#  RENDER 3D
# ============================================================================

def render(cfg, out="outputs/mdf_hero.png", hero=True):
    R._ROLE_RENDER_COLOR.update({"body": cfg.style.mdf_color,
                                 "tube": cfg.style.dowel_color,
                                 "accent": cfg.style.accent_color})
    rp = assemble_roleparts(cfg)
    rm = [(R.to_mesh(s, 0.12), role) for s, role in rp]
    Path("outputs").mkdir(exist_ok=True)
    if hero:
        return R.render_hero(rm, out, background=cfg.style.background)
    return R.render_views(None, out, background=cfg.style.background, role_meshes=rm)


# ============================================================================
#  LAYOUT DE CORTE PLANO (DXF + SVG + preview)
# ============================================================================

def flat(cfg, dxf="outputs/mdf_corte.dxf", svg="outputs/mdf_corte.svg",
         preview="outputs/mdf_corte_preview.png"):
    pieces = flat_pieces(cfg)
    # Nesting simple en filas.
    placed = []
    x, y, row_h, margin = 0, 0, 0, 12
    sheet_w = 380
    for name, sk in pieces:
        bb = sk.bounding_box()
        w, h = bb.size.X, bb.size.Y
        if x + w > sheet_w:
            x, y = 0, y - (row_h + margin)
            row_h = 0
        loc = Pos(x - bb.min.X, y - bb.min.Y)
        placed.append((name, loc * sk))
        x += w + margin
        row_h = max(row_h, h)

    # DXF / SVG.
    written = {}
    try:
        from build123d import ExportDXF, Unit
        ex = ExportDXF(unit=Unit.MM)
        for name, sk in placed:
            ex.add_shape(sk, layer="corte")
        ex.write(dxf)
        written["dxf"] = dxf
    except Exception as e:
        written["dxf_error"] = str(e)
    try:
        from build123d import ExportSVG
        ex = ExportSVG(unit=__import__("build123d").Unit.MM)
        for name, sk in placed:
            ex.add_shape(sk)
        ex.write(svg)
        written["svg"] = svg
    except Exception as e:
        written["svg_error"] = str(e)

    # Preview: piezas extruidas finas, vista cenital.
    R._ROLE_RENDER_COLOR.update({"body": cfg.style.mdf_color})
    rm = [(R.to_mesh(extrude(sk, 1.5), 0.2), "body") for _, sk in placed]
    R.render_views  # noqa
    import numpy as np
    import pyvista as pv
    _, _, center, radius = R._bounds_of(rm)
    pl = pv.Plotter(off_screen=True, window_size=(1300, 900), border=False)
    pl.set_background(cfg.style.background)
    for light in R._studio_lights(center, radius):
        pl.add_light(light)
    for mesh, _ in rm:
        pl.add_mesh(mesh, color=cfg.style.mdf_color, ambient=0.3, diffuse=0.8,
                    smooth_shading=False)
    pl.camera_position = [(center[0], center[1], radius * 3), tuple(center), (0, 1, 0)]
    pl.enable_anti_aliasing("msaa", multi_samples=8)
    pl.screenshot(preview)
    pl.close()
    written["preview"] = preview
    return written


if __name__ == "__main__":
    cfg = load()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "render"
    if cmd == "render":
        print("render ->", render(cfg))
    elif cmd == "flat":
        for k, v in flat(cfg).items():
            print(f"{k:12s}: {v}")
    else:
        print("uso: render | flat")

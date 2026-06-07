"""Cuerpo blindado + cuello (gira en pan).

Bloque facetado (biselado, no redondo) montado sobre un tambor giratorio con un eje
inferior que entra en el socket de la base (junta de pan). Al frente lleva dos
orejas de muñón con orificios coaxiales para el pasador del tilt. Detalles: franjas
amarillas laterales, caja de munición amarilla con triángulo, ventana hundida y
sensores arriba. Todo esto es UNA pieza imprimible que gira sobre la base.

Marco global, pose neutra. +X = frente.
"""
from __future__ import annotations

from build123d import (Axis, Box, Cylinder, Plane, Polygon, Pos, Rot, chamfer,
                       extrude)

from ..config import Config
from ..geom import circumradius_from_across_flats
from ..layout import base_top_z, drum_top_z, trunnion_pivot


def _safe_chamfer(solid, edges, r):
    for radius in (r, r * 0.6, r * 0.3):
        try:
            return chamfer(edges, radius)
        except Exception:
            continue
    return solid


def build(cfg: Config):
    b, n = cfg.body, cfg.neck
    z0 = drum_top_z(cfg)                      # base del cuerpo (tope del tambor)
    w, d = b.width_mm, b.depth_mm
    clr = cfg.glb.clearance_mm
    parts = []

    # --- Cuña facetada --------------------------------------------------------
    prof = Plane.XZ * Polygon(
        (-d / 2, z0 - 2), (d / 2, z0 - 2),
        (d / 2, z0 + b.front_height_mm), (-d / 2, z0 + b.back_height_mm),
        align=None)
    body = Pos(0, w / 2, 0) * extrude(prof, amount=w)
    body = _safe_chamfer(body, body.edges().filter_by(Axis.Z), b.facet_chamfer_mm)
    body = _safe_chamfer(body, body.edges().filter_by(Axis.Y), b.facet_chamfer_mm * 0.6)

    # --- Tambor del cuello + eje de pan ---------------------------------------
    drum = Pos(0, 0, base_top_z(cfg) + n.drum_height_mm / 2) * Cylinder(
        radius=n.drum_dia_mm / 2, height=n.drum_height_mm + 2)   # solapa el cuerpo
    body += drum
    for i in range(n.panel_lines):
        zc = base_top_z(cfg) + (i + 1) / (n.panel_lines + 1) * n.drum_height_mm
        body -= Pos(0, 0, zc) * (Cylinder(radius=n.drum_dia_mm / 2 + 0.5, height=1.0)
                                 - Cylinder(radius=n.drum_dia_mm / 2 - 0.8, height=1.0))

    shaft_dia = cfg.base.pan_socket_dia_mm - 2 * clr
    shaft = Pos(0, 0, base_top_z(cfg) - n.shaft_height_mm / 2 + 0.5) * Cylinder(
        radius=shaft_dia / 2, height=n.shaft_height_mm + 1)
    body += shaft
    # Pozo del tornillo de retención M3 en el eje (desde abajo).
    body -= Pos(0, 0, base_top_z(cfg) - n.shaft_height_mm + 4) * Cylinder(
        radius=cfg.base.pan_screw_dia_mm / 2 - 0.1, height=12)

    # --- Orejas del muñón (tilt) ----------------------------------------------
    px, _, pz = trunnion_pivot(cfg)
    ear_h = b.trunnion_z_mm * 1.5
    y_ear = b.ear_gap_mm / 2 + b.ear_thickness_mm / 2
    for sy in (-y_ear, y_ear):
        ear = Box(26, b.ear_thickness_mm, ear_h)
        ear = _safe_chamfer(ear, ear.edges().filter_by(Axis.Y), 3)
        ear = Pos(px - 6, sy, pz) * ear            # solapa el frente del cuerpo
        body += ear
    # Orificio coaxial del pasador del tilt (eje Y) atravesando orejas y hueco.
    body -= Pos(px, 0, pz) * (Rot(90, 0, 0) * Cylinder(
        radius=b.trunnion_pin_dia_mm / 2 + 0.05, height=w + 30))
    # Vaciar el hueco entre orejas para que entre la cuna.
    body -= Pos(px + 2, 0, pz) * Box(40, b.ear_gap_mm, ear_h + 10)

    # --- Ventana / panel hundido en un lateral (+Y) ---------------------------
    if b.side_window:
        body -= Pos(-d * 0.1, w / 2, z0 + b.back_height_mm * 0.55) * Box(
            d * 0.4, 3, b.back_height_mm * 0.3)

    # --- Antena / sensores arriba (solapando el techo) ------------------------
    if b.antenna:
        tl = z0 + b.back_height_mm
        body += Pos(-d * 0.28, 0, tl - 1.0) * Box(10, 12, 5)
        body += Pos(-d * 0.28, 5, tl + 8) * Cylinder(radius=1.0, height=18)  # base dentro del cap

    parts.append((body, "body"))

    # --- Franjas amarillas laterales ------------------------------------------
    if b.side_stripes:
        for zc in (z0 + b.back_height_mm * 0.4, z0 + b.back_height_mm * 0.6):
            strip = Box(d * 0.5, w + 1.0, 2.0)
            parts.append((Pos(-d * 0.05, 0, zc) * strip, "accent"))

    # --- Caja de munición amarilla con triángulo (abajo-adelante, +Y) ---------
    if b.ammo_box:
        bx = Pos(d * 0.28, w * 0.42, z0 + b.front_height_mm * 0.45) * Box(14, 10, 16)
        # Triángulo grabado en la cara externa (+Y).
        s = 7
        tri = Plane.XZ * Polygon((-s / 2, -s / 2), (s / 2, -s / 2), (0, s / 2), align=None)
        tri = extrude(tri, amount=2)
        tri = Pos(d * 0.28, w * 0.42 + 5.2, z0 + b.front_height_mm * 0.45) * Rot(90, 0, 0) * tri
        bx -= tri
        parts.append((bx, "accent"))

    return parts


if __name__ == "__main__":
    from ..render import render_roleparts
    from . import base
    cfg = Config.load()
    print("render ->", render_roleparts(base.build(cfg) + build(cfg), cfg,
                                        "outputs/_wip_body.png",
                                        title="Cuerpo facetado", hero=True))

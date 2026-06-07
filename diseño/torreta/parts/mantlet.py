"""Mantelete + cargador (conjunto de elevación / tilt).

Se construye en el "marco de cabezal": el origen es el eje de elevación (donde
pivota sobre el muñón del cuerpo) y +X es la dirección de tiro. El ensamble se
encarga de llevarlo a su posición y aplicar el ángulo de tilt.

  - Mantelete: bloque frontal que abraza el eje y porta el racimo de cañones.
  - Cargador: cuña amarilla que cuelga por debajo, con un triángulo de
    advertencia grabado en su cara frontal.
"""
from __future__ import annotations

from build123d import Box, Plane, Polygon, Pos, Rot, chamfer, extrude

from ..config import Config


def build(cfg: Config):
    m = cfg.mantlet
    parts = []

    # --- Mantelete: bloque centrado en el eje de elevación --------------------
    mant = Box(m.thickness_mm, m.width_mm, m.height_mm)  # X=espesor, Y=ancho, Z=alto
    mant = chamfer(mant.edges(), min(2.5, m.thickness_mm * 0.2))
    parts.append((mant, "body"))

    # --- Cargador amarillo: cuña que cuelga por debajo y hacia adelante -------
    if m.magazine_yellow:
        drop = m.magazine_drop_mm
        mag = Box(m.thickness_mm * 0.85, m.magazine_width_mm, drop)
        mag = chamfer(mag.edges(), 1.5)
        # Cuelga por debajo del mantelete, solapando 2 mm, e inclinado al frente.
        mag = Rot(0, -12, 0) * mag                        # cant hacia +X
        mag = Pos(2.0, 0, -m.height_mm / 2 - drop / 2 + 2.0) * mag

        # Triángulo de advertencia grabado en la cara frontal (+X) del cargador.
        if m.warning_triangle:
            s = m.magazine_width_mm * 0.4
            tri2d = Plane.YZ * Polygon((-s / 2, -s / 2), (s / 2, -s / 2), (0, s / 2),
                                       align=None)
            tri = extrude(tri2d, amount=1.2)
            # Ubicar en la cara frontal del cargador, a media altura de su caída.
            front_x = m.thickness_mm * 0.85 / 2 + 1.0
            tri = Pos(front_x, 0, -m.height_mm / 2 - drop * 0.45) * tri
            mag -= tri

        parts.append((mag, "accent"))

    return parts


if __name__ == "__main__":
    from ..render import render_roleparts
    cfg = Config.load()
    print("render ->", render_roleparts(build(cfg), cfg, "outputs/_wip_mantlet.png",
                                        title="Mantelete + cargador (marco de cabezal)"))

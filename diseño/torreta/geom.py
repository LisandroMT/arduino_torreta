"""Helpers geométricos compartidos entre las piezas.

Convenciones del modelo (todas las piezas las respetan):
  - Z es vertical (arriba); el origen está en el centro de la base, sobre el piso.
  - +X es "hacia el frente" (la dirección a la que apunta el cañón en pose neutra).
  - Las piezas se construyen en posición neutra de ensamble; el ensamble aplica la pose.
"""
from __future__ import annotations

import math

from build123d import Pos, RegularPolygon, Rot, extrude


def circumradius_from_across_flats(across_flats: float, sides: int) -> float:
    """Radio a los vértices de un polígono regular dado el ancho entre caras opuestas."""
    return (across_flats / 2.0) / math.cos(math.pi / sides)


def reg_prism(across_flats: float, sides: int, height: float, *, z0: float = 0.0,
              rotation: float = 0.0):
    """Prisma poligonal regular extruido en +Z desde z0.

    rotation orienta una cara hacia +X cuando vale 180/sides (octógono: 22.5°,
    hexágono: 30°).
    """
    r = circumradius_from_across_flats(across_flats, sides)
    poly = RegularPolygon(radius=r, side_count=sides, rotation=rotation)
    return Pos(0, 0, z0) * extrude(poly, amount=height)


def reg_ring(outer_af: float, inner_af: float, sides: int, height: float, *,
             z0: float = 0.0, rotation: float = 0.0):
    """Anillo poligonal (prisma exterior menos interior)."""
    return (reg_prism(outer_af, sides, height, z0=z0, rotation=rotation)
            - reg_prism(inner_af, sides, height, z0=z0, rotation=rotation))


# Compatibilidad: octógonos (usados por piezas previas).
def octagon_prism(across_flats: float, height: float, *, z0: float = 0.0,
                  rotation: float = 22.5):
    return reg_prism(across_flats, 8, height, z0=z0, rotation=rotation)


def octagon_ring(outer_across_flats: float, inner_across_flats: float, height: float,
                 *, z0: float = 0.0, rotation: float = 22.5):
    return reg_ring(outer_across_flats, inner_across_flats, 8, height, z0=z0,
                    rotation=rotation)

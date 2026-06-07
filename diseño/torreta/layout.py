"""Geometría de referencia compartida: alturas del apilado y eje de elevación.

Centraliza las cotas que varias piezas necesitan para encajar, evitando imports
circulares entre los módulos de parts/.
"""
from __future__ import annotations

from .config import Config


def base_top_z(cfg: Config) -> float:
    """Cara superior de la base estática (donde apoya el tambor del cuerpo)."""
    return cfg.base.height_mm


def drum_top_z(cfg: Config) -> float:
    """Cara superior del tambor del cuello (base del cuerpo blindado)."""
    return base_top_z(cfg) + cfg.neck.drum_height_mm


def trunnion_pivot(cfg: Config) -> tuple[float, float, float]:
    """Punto (x, y, z) del eje de elevación, global, en pose neutra."""
    return (cfg.body.trunnion_x_mm, 0.0, drum_top_z(cfg) + cfg.body.trunnion_z_mm)

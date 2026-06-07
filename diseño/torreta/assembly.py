"""Ensamble articulado de la torreta.

Tres piezas físicas independientes (cada una se imprime por separado y se unen con
pasadores/tornillos):
  - base : estática.
  - body : gira en pan sobre la base (eje vertical Z).
  - gun  : cuna + cañón; gira en pan y además bascula en tilt sobre el muñón (Y).

Expone:
  - build_roleparts(cfg): piezas POSADAS con su rol de color, para el render.
  - part_solids(cfg): dict {nombre: sólido fusionado} en orientación NEUTRA, para
    exportar cada pieza imprimible.
"""
from __future__ import annotations

from build123d import Pos, Rot, Solid

from .config import Config
from .layout import trunnion_pivot
from .parts import barrels, base, body, cradle


def _xform(loc, part):
    """Aplica una Location a un Part o a una colección de sólidos."""
    if hasattr(part, "tessellate"):
        return loc * part
    return [loc * s for s in part]


def _iter_solids(part):
    if hasattr(part, "solids"):
        ss = list(part.solids())
        if ss:
            return ss
    if hasattr(part, "tessellate"):
        return [part]
    out = []
    for s in part:
        out.extend(_iter_solids(s))
    return out


# --- Construcción de cada grupo en posición NEUTRA ---------------------------

def _base_parts(cfg):
    return base.build(cfg)


def _body_parts(cfg):
    return body.build(cfg)


def _gun_parts(cfg):
    """Cuna + cañón en el marco de cabezal (origen = pivote del tilt)."""
    return cradle.build(cfg) + barrels.build(cfg)


# --- Render: todo posado -----------------------------------------------------

def build_roleparts(cfg: Config):
    px, _, pz = trunnion_pivot(cfg)
    p = cfg.pose
    loc_pan = Rot(0, 0, p.pan_deg)
    loc_gun = loc_pan * Pos(px, 0, pz) * Rot(0, -p.tilt_deg, 0)

    out = []
    out += _base_parts(cfg)                                   # estática
    for part, role in _body_parts(cfg):                       # pan
        out.append((_xform(loc_pan, part), role))
    for part, role in _gun_parts(cfg):                        # pan + tilt
        out.append((_xform(loc_gun, part), role))
    return out


# --- Export: cada pieza física como un sólido neutro -------------------------

def _fuse(parts):
    solids = [s for part, _ in parts for s in _iter_solids(part)]
    fused = Solid.fuse(*solids) if len(solids) > 1 else solids[0]
    return fused


def part_solids(cfg: Config) -> dict:
    """Sólido fusionado de cada pieza imprimible, en orientación neutra."""
    out = {
        "base": _fuse(_base_parts(cfg)),
        "body": _fuse(_body_parts(cfg)),
        "gun": _fuse(_gun_parts(cfg)),
    }
    if cfg.glb.scale != 1.0:
        from build123d import scale
        out = {k: scale(v, by=cfg.glb.scale) for k, v in out.items()}
    return out


def build_exploded_roleparts(cfg: Config):
    """Piezas separadas en el eje vertical para mostrar el despiece/ensamble."""
    px, _, pz = trunnion_pivot(cfg)
    out = []
    out += _base_parts(cfg)
    for part, role in _body_parts(cfg):
        out.append((_xform(Pos(0, 0, 45), part), role))
    for part, role in _gun_parts(cfg):
        out.append((_xform(Pos(px + 50, 0, pz + 95), part), role))
    return out


if __name__ == "__main__":
    from .render import render_roleparts
    cfg = Config.load()
    print("render ->", render_roleparts(build_roleparts(cfg), cfg,
                                        "outputs/_wip_assembly.png",
                                        title="Torreta articulada", hero=True))

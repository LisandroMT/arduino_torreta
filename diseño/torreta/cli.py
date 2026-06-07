"""Interfaz de línea de comandos de la torreta articulada.

  python -m torreta.cli build     # valida cada pieza + exporta STL/STEP + GLB + renders
  python -m torreta.cli render     # render posado (hero por defecto, --grid para 2x2)
  python -m torreta.cli check      # gate de imprimibilidad por pieza
  python -m torreta.cli exploded   # vista explotada (despiece)
  python -m torreta.cli motion     # tira del rango de movimiento (pan/tilt)

Toda la geometría sale de turret.yaml; con --yaml se usa otro archivo.
"""
from __future__ import annotations

import argparse
import sys

from .config import Config


def _load(args) -> Config:
    return Config.load(args.yaml) if args.yaml else Config.load()


def cmd_render(args) -> int:
    from .assembly import build_roleparts
    from .render import render_roleparts
    cfg = _load(args)
    out = render_roleparts(build_roleparts(cfg), cfg, args.out,
                           title="Torreta Gatling — paramétrica", hero=not args.grid)
    print(f"render -> {out}")
    return 0


def cmd_exploded(args) -> int:
    from .assembly import build_exploded_roleparts
    from .render import render_roleparts
    cfg = _load(args)
    out = render_roleparts(build_exploded_roleparts(cfg), cfg,
                           "outputs/torreta_exploded.png", hero=True)
    print(f"render -> {out}")
    return 0


def cmd_check(args) -> int:
    from .assembly import part_solids
    from .validate import check_all
    cfg = _load(args)
    ok, report = check_all(part_solids(cfg), cfg)
    print(report)
    return 0 if ok else 1


def cmd_build(args) -> int:
    from .assembly import (build_exploded_roleparts, build_roleparts, part_solids)
    from .export import export_assembly_glb, export_parts
    from .render import render_roleparts
    from .validate import check_all
    cfg = _load(args)

    print("· construyendo piezas…")
    solids = part_solids(cfg)
    print("· validando imprimibilidad por pieza…")
    ok, report = check_all(solids, cfg)
    print(report)
    if not ok and not args.force:
        print("\nABORTADO: alguna pieza no pasó el gate (usá --force para exportar igual).")
        return 1

    print("· exportando piezas (STL/STEP)…")
    w1 = export_parts(solids, cfg)
    print("· exportando ensamble GLB con colores…")
    roleparts = build_roleparts(cfg)
    w2 = export_assembly_glb(roleparts, cfg)
    print("· renderizando…")
    render_roleparts(roleparts, cfg, "outputs/torreta_hero.png", hero=True)
    render_roleparts(roleparts, cfg, "outputs/torreta_views.png", title="Torreta")
    render_roleparts(build_exploded_roleparts(cfg), cfg, "outputs/torreta_exploded.png",
                     hero=True)

    print("\nEntregables:")
    for k, v in {**w1, **w2}.items():
        print(f"  {k:14s}: {v}")
    print("  renders        : outputs/torreta_hero.png, torreta_views.png, torreta_exploded.png")
    return 0


def cmd_motion(args) -> int:
    import copy
    from .assembly import build_roleparts
    from .render import role_color, to_mesh, _apply_palette
    import pyvista as pv
    cfg = _load(args)
    _apply_palette(cfg)

    poses = [(0, 0), (45, 0), (90, 0), (0, 25), (45, 25), (90, 25)]
    pl = pv.Plotter(off_screen=True, shape=(2, 3), window_size=(1500, 900), border=False)
    for idx, (pan, tilt) in enumerate(poses):
        c = copy.deepcopy(cfg)
        c.pose.pan_deg, c.pose.tilt_deg = pan, tilt
        pl.subplot(idx // 3, idx % 3)
        pl.set_background(cfg.style.background)
        from .render import _studio_lights, _bounds_of, _MATERIAL
        rm = [(to_mesh(p, cfg.glb.tessellation_mm), role) for p, role in build_roleparts(c)]
        _, _, center, radius = _bounds_of(rm)
        for light in _studio_lights(center, radius):
            pl.add_light(light)
        for mesh, role in rm:
            pl.add_mesh(mesh, color=role_color(cfg, role), smooth_shading=True,
                        **_MATERIAL.get(role, _MATERIAL["body"]))
        pl.add_text(f"pan {pan}  tilt {tilt}", font_size=9, color="white",
                    position="upper_left")
        pl.camera_position = [(190, -210, 150), (0, 0, 60), (0, 0, 1)]
        pl.camera.zoom(1.2)
    pl.enable_anti_aliasing("msaa", multi_samples=8)
    pl.screenshot("outputs/torreta_motion.png")
    pl.close()
    print("render -> outputs/torreta_motion.png")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="torreta", description=__doc__)
    p.add_argument("--yaml", help="ruta a un turret.yaml alternativo")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("render", help="render posado")
    pr.add_argument("--out", default="outputs/torreta_hero.png")
    pr.add_argument("--grid", action="store_true", help="grilla 2x2 en vez de hero")
    pr.set_defaults(func=cmd_render)

    pe = sub.add_parser("exploded", help="vista explotada")
    pe.set_defaults(func=cmd_exploded)

    pc = sub.add_parser("check", help="gate de imprimibilidad por pieza")
    pc.set_defaults(func=cmd_check)

    pb = sub.add_parser("build", help="validar + exportar + render")
    pb.add_argument("--force", action="store_true")
    pb.set_defaults(func=cmd_build)

    pm = sub.add_parser("motion", help="tira de rango de movimiento")
    pm.set_defaults(func=cmd_motion)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

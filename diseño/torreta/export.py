"""Exportación del modelo articulado.

  - Por pieza (base, body, gun): STEP (editable) + STL (slicer), en outputs/parts/.
  - Ensamble posado completo: GLB con colores por pieza, para visualizadores 3D.
"""
from __future__ import annotations

from pathlib import Path

from build123d import Compound, Color, export_step, export_stl

from .config import Config
from .render import role_color


def export_parts(part_solids: dict, cfg: Config, outdir="outputs/parts") -> dict:
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    written = {}
    for name, solid in part_solids.items():
        step = out / f"{name}.step"
        stl = out / f"{name}.stl"
        export_step(solid, str(step))
        export_stl(solid, str(stl), tolerance=cfg.glb.tessellation_mm,
                   angular_tolerance=0.2)
        written[f"{name}.step"] = step
        written[f"{name}.stl"] = stl
    return written


def export_assembly_glb(roleparts, cfg: Config, outdir="outputs") -> dict:
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    children = []
    for i, (part, role) in enumerate(roleparts):
        solids = part.solids() if hasattr(part, "solids") else list(part)
        comp = Compound(children=list(solids))
        comp.color = Color(role_color(cfg, role))
        comp.label = f"{role}_{i}"
        children.append(comp)
    scene = Compound(children=children)
    written = {}
    try:
        from build123d import export_gltf
        path = out / "torreta.glb"
        export_gltf(scene, str(path), binary=True)
        written["glb"] = path
    except Exception as e:  # pragma: no cover
        written["glb_error"] = str(e)
    return written

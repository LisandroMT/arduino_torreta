"""Ingesta y acondicionamiento de mallas externas (p. ej. de IA imagen→3D).

Flujo: cargar una malla (GLB/OBJ/STL/PLY) → diagnosticar → reparar (unir vértices,
normales, tapar huecos) → escalar a tamaño real → exportar STL listo para slicer.

No genera geometría de terceros: es una herramienta de saneamiento. La malla la
aporta el usuario; acá solo se la deja imprimible y a escala.

Uso:
  python -m torreta.meshtools entrada.glb --target-height 150 --out outputs/ingesta.stl
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import trimesh


def load_mesh(path: str | Path) -> trimesh.Trimesh:
    """Carga una malla; si el archivo es una escena (GLB), fusiona sus partes."""
    obj = trimesh.load(str(path), force="mesh")
    if isinstance(obj, trimesh.Scene):
        obj = trimesh.util.concatenate(tuple(obj.geometry.values()))
    return obj


def diagnose(m: trimesh.Trimesh) -> dict:
    return {
        "vertices": len(m.vertices),
        "faces": len(m.faces),
        "watertight": bool(m.is_watertight),
        "winding_consistent": bool(m.is_winding_consistent),
        "n_bodies": int(m.body_count),
        "volume_cm3": round(float(m.volume) / 1000, 2) if m.is_volume else None,
        "bbox_mm": [round(float(x), 1) for x in m.extents],
    }


def repair(m: trimesh.Trimesh) -> trimesh.Trimesh:
    """Saneo estándar para impresión: vértices, caras, normales y huecos."""
    m.merge_vertices()
    m.update_faces(m.unique_faces())
    m.update_faces(m.nondegenerate_faces())
    m.remove_unreferenced_vertices()
    trimesh.repair.fix_normals(m)
    trimesh.repair.fix_winding(m)
    trimesh.repair.fill_holes(m)
    return m


def scale_to_height(m: trimesh.Trimesh, target_height_mm: float) -> trimesh.Trimesh:
    """Escala uniformemente para que el alto (eje Z) sea target_height_mm."""
    h = float(m.extents[2]) or 1.0
    m.apply_scale(target_height_mm / h)
    return m


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input", help="malla de entrada (glb/obj/stl/ply)")
    p.add_argument("--target-height", type=float, default=None,
                   help="alto final en mm (escala uniforme)")
    p.add_argument("--out", default="outputs/ingesta.stl")
    args = p.parse_args(argv)

    m = load_mesh(args.input)
    print("ANTES :", diagnose(m))
    m = repair(m)
    if args.target_height:
        m = scale_to_height(m, args.target_height)
    print("DESPUÉS:", diagnose(m))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    m.export(str(out))
    print(f"exportado -> {out}  (watertight={m.is_watertight})")
    return 0 if m.is_watertight else 2


if __name__ == "__main__":
    raise SystemExit(main())

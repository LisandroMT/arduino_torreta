"""Render offscreen de calidad de presentación con PyVista (VTK).

Convierte sólidos build123d a mallas PyVista (vía teselado, sin tocar disco) y
arma un PNG multi-vista con sombreado y colores por pieza. Es a la vez el
entregable visual y el mecanismo de verificación de la metodología incremental:
después de cada hito miramos el PNG y comparamos con la referencia.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pyvista as pv

# Headless: forzar offscreen antes de crear cualquier Plotter.
pv.OFF_SCREEN = True
os.environ.setdefault("PYVISTA_OFF_SCREEN", "true")

# Cámaras de las 4 vistas canónicas (posición relativa, se escala al tamaño del modelo).
_VIEWS = {
    "3/4 frente": (1.0, -1.0, 0.6),
    "lateral":    (0.05, -1.0, 0.15),
    "frente":     (1.0, -0.05, 0.1),
    "picado":     (0.8, -0.8, 1.1),
}


def _tess_one(shape, tol: float) -> pv.PolyData:
    verts, faces = shape.tessellate(tolerance=tol)
    pts = np.array([(v.X, v.Y, v.Z) for v in verts], dtype=float)
    cells = np.empty((len(faces), 4), dtype=np.int64)
    cells[:, 0] = 3
    cells[:, 1:] = np.asarray(faces, dtype=np.int64)
    return pv.PolyData(pts, cells.ravel())


def to_mesh(part, tol: float) -> pv.PolyData:
    """build123d Part / Compound / ShapeList -> pv.PolyData (teselado, sin disco).

    Acepta colecciones de sólidos disjuntos (p. ej. los tubos del cañón), que
    build123d devuelve como ShapeList; se teselan por separado y se fusionan.
    """
    if hasattr(part, "tessellate"):
        mesh = _tess_one(part, tol)
    else:  # ShapeList u otro iterable de sólidos
        blocks = [_tess_one(s, tol) for s in part if hasattr(s, "tessellate")]
        mesh = blocks[0]
        for b in blocks[1:]:
            mesh = mesh.merge(b)
    return mesh.compute_normals(consistent_normals=True, auto_orient_normals=True)


# Material por rol: aspecto "gunmetal" mate, tubos metálicos claros, acentos que
# se leen como emisivos (alto ambient para que "brillen" sin importar la luz).
_MATERIAL = {
    "body":   dict(metallic=0.55, roughness=0.45, specular=0.35, specular_power=30,
                   ambient=0.18, diffuse=0.8),
    "tube":   dict(metallic=0.9, roughness=0.3, specular=0.7, specular_power=60,
                   ambient=0.2, diffuse=0.75),
    "accent": dict(metallic=0.0, roughness=1.0, specular=0.0, specular_power=1,
                   ambient=0.95, diffuse=0.35),   # casi emisivo
}


def _bounds_of(meshes):
    bounds = np.array([m.bounds for m, _ in meshes])
    lo = bounds[:, [0, 2, 4]].min(axis=0)
    hi = bounds[:, [1, 3, 5]].max(axis=0)
    return lo, hi, (lo + hi) / 2, float(np.linalg.norm(hi - lo)) / 2 or 1.0


def _studio_lights(center, radius):
    """Tres puntos de luz (key / fill / rim) estilo estudio."""
    cx, cy, cz = center
    r = radius
    key = pv.Light(position=(cx + 2 * r, cy - 2.5 * r, cz + 3 * r),
                   focal_point=center, color="white", intensity=0.95)
    fill = pv.Light(position=(cx - 2.5 * r, cy - 1.5 * r, cz + 1.2 * r),
                    focal_point=center, color=(0.8, 0.85, 1.0), intensity=0.45)
    rim = pv.Light(position=(cx - 0.5 * r, cy + 3 * r, cz + 2 * r),
                   focal_point=center, color="white", intensity=0.6)
    return [key, fill, rim]


# Color real por rol, fijado por render_* desde el YAML antes de poblar la escena.
_ROLE_RENDER_COLOR: dict[str, str] = {}


def _scene(pl, meshes, bg, *, with_ground=True):
    lo, hi, center, radius = _bounds_of(meshes)
    pl.set_background(bg)
    for light in _studio_lights(center, radius):
        pl.add_light(light)
    for mesh, role in meshes:
        mat = _MATERIAL.get(role, _MATERIAL["body"])
        pl.add_mesh(mesh, color=_ROLE_RENDER_COLOR.get(role, "#888888"),
                    smooth_shading=True, **mat)
    if with_ground:
        size = radius * 6
        ground = pv.Plane(center=(center[0], center[1], lo[2] - 0.2),
                          direction=(0, 0, 1), i_size=size, j_size=size)
        pl.add_mesh(ground, color="#333539", ambient=0.25, diffuse=0.6,
                    specular=0.05, smooth_shading=True)
    return center, radius


def render_views(named_parts, out_png, *, tol=0.12, background="#3A3A3A",
                 title=None, role_meshes=None) -> Path:
    """Grilla 2x2 de vistas con iluminación de estudio.

    Acepta `role_meshes` = lista (mesh, rol) ya teselada (preferido), o el dict
    `named_parts` {nombre: (Part, color)} por compatibilidad.
    """
    if role_meshes is None:
        role_meshes = [(to_mesh(p, tol), name.split("_")[0])
                       for name, (p, _c) in named_parts.items()]

    pl = pv.Plotter(off_screen=True, shape=(2, 2), window_size=(1200, 1100),
                    border=False)
    for idx, (vname, vdir) in enumerate(_VIEWS.items()):
        pl.subplot(idx // 2, idx % 2)
        center, radius = _scene(pl, role_meshes, background)
        d = np.array(vdir, dtype=float)
        d = d / np.linalg.norm(d)
        pos = center + d * radius * 3.0
        pl.camera_position = [tuple(pos), tuple(center), (0, 0, 1)]
        pl.camera.zoom(1.3)
        pl.add_text(vname, font_size=9, color="white", position="upper_left")
    try:
        pl.enable_shadows()
    except Exception:
        pass
    pl.enable_anti_aliasing("msaa", multi_samples=8)
    out = Path(out_png)
    out.parent.mkdir(parents=True, exist_ok=True)
    pl.screenshot(str(out))
    pl.close()
    return out


def render_hero(role_meshes, out_png, *, background="#3A3A3A",
                view=(1.0, -1.0, 0.55)) -> Path:
    """Render único grande, ángulo 3/4 frente, como la referencia."""
    pl = pv.Plotter(off_screen=True, window_size=(1300, 1000), border=False)
    center, radius = _scene(pl, role_meshes, background)
    d = np.array(view, dtype=float)
    d = d / np.linalg.norm(d)
    pos = center + d * radius * 2.7
    pl.camera_position = [tuple(pos), tuple(center), (0, 0, 1)]
    pl.camera.zoom(1.35)
    try:
        pl.enable_shadows()
    except Exception:
        pass
    pl.enable_anti_aliasing("msaa", multi_samples=8)
    out = Path(out_png)
    out.parent.mkdir(parents=True, exist_ok=True)
    pl.screenshot(str(out))
    pl.close()
    return out


# --- Mapeo rol -> color y conveniencia para listas (Part, rol) ---------------

def role_color(cfg, role: str) -> str:
    return {
        "body": cfg.style.body_color,
        "tube": cfg.style.tube_color,
        "accent": cfg.style.accent_color,
    }[role]


def _apply_palette(cfg) -> None:
    _ROLE_RENDER_COLOR.update({
        "body": cfg.style.body_color,
        "tube": cfg.style.tube_color,
        "accent": cfg.style.accent_color,
    })


def render_roleparts(roleparts, cfg, out_png, *, title: str | None = None,
                     hero: bool = False) -> Path:
    """Renderiza una lista de (Part, rol) usando la paleta del YAML.

    hero=True produce un render único grande (3/4 frente); si no, la grilla 2x2.
    """
    _apply_palette(cfg)
    role_meshes = [(to_mesh(part, cfg.glb.tessellation_mm), role)
                   for part, role in roleparts]
    if hero:
        return render_hero(role_meshes, out_png, background=cfg.style.background)
    return render_views(None, out_png, background=cfg.style.background,
                        title=title, role_meshes=role_meshes)

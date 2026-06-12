"""Torreta v2 — diseño "ultra" del prototipo final (open-frame, componentes reales).

Diseño NUEVO, independiente de la torreta gatling de Fase 1. Concepto: torreta de
seguimiento open-frame donde la electrónica visible se modela con sus MEDIDAS DE
DATASHEET y la estructura (imprimible en 3D) se diseña alrededor de ellas:

  - 28BYJ-48  : cuerpo Ø28×19, brida con agujeros a 35 mm, eje Ø5×9
  - SG90      : cuerpo 22.5×11.8×22.7, aletas a 32.2 mm, eje Ø4.6
  - HC-SR04   : PCB 45×20×1.6, transductores Ø16×12 (centros a 26 mm)
  - Cámara M12: PCB 32×32×1.6, holder 16×16, barril Ø13×16 (lente M12)
  - KY-008    : PCB 18.5×15×1.6, tubo láser de latón Ø6.5×10.5
  - GY-521    : PCB 21.2×16.4×1.6 (MPU6050 4×4 QFN)
  - ESP32 DevKit: PCB 54.4×27.9, módulo WROOM-32 18×25.5×3.1
  - LCD 1602  : PCB 80×36, bezel 71.2×26.5, integrado en consola frontal

Ejes: Z arriba, +Y = frente (boca del cañón). Unidades: mm.
Uso:  .venv/bin/python torreta_v2.py   (genera renders + GLB + STEP en outputs/)
"""
from __future__ import annotations

import math
import os
from pathlib import Path

import numpy as np
import pyvista as pv

pv.OFF_SCREEN = True
os.environ.setdefault("PYVISTA_OFF_SCREEN", "true")

from build123d import (  # noqa: E402
    Axis, Box, Color, Compound, Cylinder, Plane, Pos, Rot,
    chamfer, export_gltf, export_step, fillet, mirror,
)

from torreta.render import to_mesh  # teselador build123d -> pyvista  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE / "outputs"

# ============================== PALETA / MATERIALES =========================
COL = {
    "graphite":  "#2B3036",   # estructura impresa (PETG grafito)
    "panel":     "#21252A",   # paneles oscuros
    "alu":       "#B9C0C7",   # aluminio (separadores, ejes)
    "amber":     "#FFB547",   # acentos
    "pcb_blue":  "#1660A8",   # HC-SR04
    "pcb_green": "#1F6B34",   # cámara M12
    "pcb_red":   "#A4252B",   # KY-008
    "pcb_prpl":  "#5435A0",   # GY-521
    "pcb_dark":  "#15314F",   # ESP32 DevKit
    "silver":    "#CFD6DA",   # transductores, blindajes
    "mesh":      "#3C4146",   # malla de los transductores
    "brass":     "#C9A44A",   # tubo del láser
    "lens":      "#0E1216",   # ópticas
    "servo":     "#2A6FD6",   # SG90
    "cream":     "#E8E4D8",   # horn del servo
    "white":     "#EDEDED",   # conectores
    "lcd_glass": "#9AD65A",   # pantalla (emisiva)
    "chip":      "#16191D",   # encapsulados IC
}
MAT = {  # presets PBR para PyVista
    "metal":   dict(metallic=0.85, roughness=0.35, specular=0.6, specular_power=50, ambient=0.16, diffuse=0.8),
    "alu":     dict(metallic=0.75, roughness=0.42, specular=0.5, specular_power=40, ambient=0.18, diffuse=0.8),
    "plastic": dict(metallic=0.05, roughness=0.58, specular=0.25, specular_power=18, ambient=0.16, diffuse=0.85),
    "pcb":     dict(metallic=0.0,  roughness=0.85, specular=0.12, specular_power=8,  ambient=0.2,  diffuse=0.85),
    "glass":   dict(metallic=0.3,  roughness=0.12, specular=0.95, specular_power=90, ambient=0.12, diffuse=0.6),
    "emissive": dict(metallic=0.0, roughness=1.0,  specular=0.0,  specular_power=1,  ambient=0.95, diffuse=0.3),
    "brass":   dict(metallic=0.9,  roughness=0.32, specular=0.7,  specular_power=60, ambient=0.18, diffuse=0.78),
}

PARTS: list[dict] = []   # {solid, color, mat, name}


def add(solid, color: str, mat: str, name: str, loc=None):
    if loc is not None:
        solid = loc * solid
    PARTS.append(dict(solid=solid, color=color, mat=mat, name=name))
    return solid


def vfillet(part, r):
    """Fillet de aristas verticales; si OpenCASCADE falla, sigue sin fillet."""
    try:
        return fillet(part.edges().filter_by(Axis.Z), r)
    except Exception:
        return part


# ============================ COTAS GENERALES ===============================
PAN_DEG, TILT_DEG = 22, -12          # pose del render (tilt negativo = boca arriba)
Z_PLATE_TOP = 54                     # cara superior de la placa estatórica
Z_PLATFORM = 56                      # plataforma giratoria (cara inferior)
Z_TILT = 118                         # altura del eje de elevación

pan = Rot(Z=PAN_DEG)
tilt = Pos(0, 0, Z_TILT) * Rot(X=TILT_DEG) * Pos(0, 0, -Z_TILT)
pose_pan = pan                        # piezas que solo panean
pose_tilt = pan * tilt                # piezas que panean y basculan


# ============================ BASE OPEN-FRAME ===============================
# Placa inferior 130×130×6 con fillets generosos
bottom = vfillet(Box(130, 130, 6), 14)
add(Pos(0, 0, 3) * bottom, COL["graphite"], "plastic", "placa_inferior")

# Separadores de aluminio Ø8×42 en las 4 esquinas
for sx in (-1, 1):
    for sy in (-1, 1):
        add(Pos(48 * sx, 48 * sy, 27) * Cylinder(4, 42), COL["alu"], "alu", "separador")
        add(Pos(48 * sx, 48 * sy, 6.8) * Cylinder(5.5, 1.6), COL["alu"], "alu", "tuerca")

# Placa estatórica Ø100×6 (aloja el stepper por debajo)
estator = Cylinder(50, 6) - Cylinder(5.5, 8)
estator = chamfer(estator.edges().filter_by(Axis.Z, reverse=True).group_by(Axis.Z)[-1], 1.2) \
    if True else estator
add(Pos(0, 0, 51) * estator, COL["graphite"], "plastic", "placa_estator")

# ---- 28BYJ-48 colgado bajo la placa (medidas de datasheet) ----
add(Pos(0, 0, 37.5) * Cylinder(14, 19), COL["silver"], "metal", "28byj48_cuerpo")
flange = Box(35, 7, 1) + Pos(17.5, 0, 0) * Cylinder(3.5, 1) + Pos(-17.5, 0, 0) * Cylinder(3.5, 1)
flange = flange - Pos(17.5, 0, 0) * Cylinder(2.1, 3) - Pos(-17.5, 0, 0) * Cylinder(2.1, 3)
add(Pos(0, 0, 47.5) * flange, COL["silver"], "metal", "28byj48_brida")
add(Pos(0, 0, 49) * Cylinder(4.5, 2), COL["silver"], "metal", "28byj48_collar")
add(Pos(0, 0, 52.5) * Cylinder(2.5, 9), COL["alu"], "alu", "28byj48_eje")
add(Pos(0, 15.5, 38) * Box(14.6, 6, 16.5), COL["servo"], "plastic", "28byj48_caja_cables")
add(Pos(0, 19.5, 38) * Box(11, 3, 6), COL["white"], "plastic", "28byj48_jst")

# ---- ESP32 DevKit + ULN2003 a la vista sobre la placa inferior ----
esp_loc = Pos(-14, -22, 0) * Rot(Z=8)
add(Box(27.9, 54.4, 1.6), COL["pcb_dark"], "pcb", "esp32_pcb", esp_loc * Pos(0, 0, 7))
add(Box(18, 25.5, 3.1), COL["silver"], "metal", "esp32_wroom", esp_loc * Pos(0, -12, 9.3))
add(Box(8, 6, 3), COL["silver"], "metal", "esp32_usb", esp_loc * Pos(0, 24.5, 8.7))
for px in (-12.7, 12.7):
    add(Box(2.5, 48, 8.5), COL["chip"], "plastic", "esp32_header", esp_loc * Pos(px, 0, 7 - 4))

uln_loc = Pos(26, -14, 0) * Rot(Z=-14)
add(Box(32, 35, 1.6), COL["pcb_green"], "pcb", "uln2003_pcb", uln_loc * Pos(0, 0, 7))
add(Box(7, 19, 5), COL["chip"], "plastic", "uln2003_ic", uln_loc * Pos(-6, 0, 10))
add(Box(6, 14, 7), COL["white"], "plastic", "uln2003_conector", uln_loc * Pos(8, 6, 11))
for i in range(4):
    add(Box(2, 1.2, 0.8), COL["amber"], "emissive", "uln2003_led",
        uln_loc * Pos(8, -12 + i * 4, 8))

# ---- Consola LCD 1602 en el frente (medidas reales 80×36, bezel 71.2×26.5) ----
con_loc = Pos(0, 48, 0)
wedge = Pos(0, 0, 16) * Box(88, 28, 32)
wedge = wedge - (Pos(0, 8, 38) * Rot(X=-35) * Box(94, 70, 36))    # cara inclinada al frente
wedge = vfillet(wedge, 5)
add(wedge, COL["graphite"], "plastic", "consola", con_loc)
# LCD apoyado sobre la cara inclinada (normal hacia el frente-arriba)
lcd_tilt = con_loc * Pos(0, 1.5, 19) * Rot(X=-35)
add(Box(80, 36, 1.6), COL["pcb_green"], "pcb", "lcd_pcb", lcd_tilt)
add(Box(75, 30.5, 7), COL["chip"], "plastic", "lcd_bezel", lcd_tilt * Pos(0, 0, 4.3))
add(Box(66, 18, 1.2), COL["lcd_glass"], "emissive", "lcd_pantalla", lcd_tilt * Pos(0, 0, 8.0))

# ========================= PLATAFORMA GIRATORIA (PAN) =======================
add(Pos(0, 0, 55) * Cylinder(9, 4), COL["graphite"], "plastic", "cubo_eje", pose_pan)
platform = Cylinder(48, 8) - Cylinder(40, 2.5, align=None)
platform = vfillet(platform, 0)  # sin fillet vertical; bisel superior:
platform = chamfer(platform.edges().group_by(Axis.Z)[-1], 1.5)
add(Pos(0, 0, 60) * platform, COL["graphite"], "plastic", "plataforma", pose_pan)
ring = Cylinder(48.6, 2.6) - Cylinder(46.4, 4)
add(Pos(0, 0, 60.6) * ring, COL["amber"], "emissive", "anillo_acento", pose_pan)
# marcas de índice del sector ±180°
for adeg in (-150, -90, -30, 30, 90, 150):
    a = math.radians(adeg)
    add(Pos(42 * math.sin(a), 42 * math.cos(a), 64.2) * Box(2.2, 6, 0.6),
        COL["amber"], "emissive", "indice", pose_pan)

# ============================= HORQUILLA (YOKE) =============================
for sx in (-1, 1):
    arm = vfillet(Box(16, 30, 70), 5)
    add(Pos(34 * sx, 0, 99) * arm, COL["graphite"], "plastic", "brazo", pose_pan)
    stripe = Box(1.2, 16, 52)
    add(Pos((34 + 8.2) * sx, 0, 99) * stripe, COL["amber"], "emissive", "franja_brazo", pose_pan)
brace = vfillet(Box(52, 12, 16), 4)
add(Pos(0, -16, 78) * brace, COL["graphite"], "plastic", "puente", pose_pan)

# ---- SG90 real atravesando el brazo derecho (eje = eje de tilt) ----
# Construido en marco local (eje del servo = +Z local), luego rotado a -X mundo.
sg_parts = []
def sg(solid, color, mat, name):
    sg_parts.append((solid, color, mat, name))

sg(Pos(0.55, 0, 11.35) * Box(22.5, 11.8, 22.7), COL["servo"], "plastic", "sg90_cuerpo")
tabs = Pos(0.55, 0, 17.65) * Box(32.2, 11.8, 2.5)
tabs = tabs - Pos(14.8, 0, 17.65) * Cylinder(1, 4) - Pos(-13.7, 0, 17.65) * Cylinder(1, 4)
sg(tabs, COL["servo"], "plastic", "sg90_aletas")
sg(Pos(0, 0, 24.7) * Cylinder(5.9, 4), COL["servo"], "plastic", "sg90_tapa")
sg(Pos(-7.0, 0, 24.2) * Cylinder(2.8, 3), COL["servo"], "plastic", "sg90_lobulo")
sg(Pos(0, 0, 28.3) * Cylinder(2.3, 3.2), COL["cream"], "plastic", "sg90_eje")
sg(Pos(0, 0, 30.3) * Cylinder(3.5, 1.6), COL["cream"], "plastic", "sg90_horn_cubo")
sg(Pos(0, -8, 30.3) * Box(4.5, 17, 1.6), COL["cream"], "plastic", "sg90_horn_brazo")
# Aletas (z local 16.4) apoyadas en la cara exterior del brazo (x=42)
sg_loc = pose_pan * Pos(42 + 16.4, 0, Z_TILT) * Rot(Y=-90)
# (el horn queda en x=24, engranado con el muñón del pod; cuerpo dentro/fuera del brazo)
for s, c, m, n in sg_parts:
    add(s, c, m, n, sg_loc)

# pivote del lado izquierdo
add(Pos(-27, 0, Z_TILT) * Rot(Y=90) * Cylinder(8, 6), COL["alu"], "alu", "pivote_izq", pose_pan)
add(Pos(-23.5, 0, Z_TILT) * Rot(Y=90) * Cylinder(3.5, 4), COL["alu"], "alu", "pivote_perno", pose_pan)

# ====================== POD DE SENSORES (TILT) ==============================
pod = vfillet(Box(52, 60, 32), 6)
pod = chamfer(pod.edges().group_by(Axis.Z)[-1], 2)
add(Pos(0, 4, Z_TILT) * pod, COL["graphite"], "plastic", "pod", pose_tilt)
for sx in (-1, 1):  # muñones
    add(Pos(27.5 * sx, 0, Z_TILT) * Rot(Y=90) * Cylinder(11, 5), COL["panel"],
        "plastic", "munon", pose_tilt)

# paneles laterales con acento
for sx in (-1, 1):
    add(Pos(26.6 * sx, 6, Z_TILT) * Box(1.2, 34, 18), COL["panel"], "plastic",
        "panel_lateral", pose_tilt)

# ---- Cañón (porta-láser) ----
barrel = Rot(X=-90) * Cylinder(8, 56)            # eje +Y, de y=34 a y=90 aprox
add(Pos(0, 62, Z_TILT) * barrel, COL["panel"], "plastic", "canon", pose_tilt)
add(Pos(0, 38, Z_TILT) * Rot(X=-90) * Cylinder(10, 10), COL["graphite"], "plastic",
    "canon_raiz", pose_tilt)
muz = Rot(X=-90) * (Cylinder(9.5, 7) - Cylinder(5.2, 9))
add(Pos(0, 88, Z_TILT) * muz, COL["amber"], "emissive", "freno_boca", pose_tilt)
add(Pos(0, 91, Z_TILT) * Rot(X=-90) * Cylinder(4.0, 7), COL["brass"], "brass",
    "laser_salida", pose_tilt)
add(Pos(0, 94.7, Z_TILT) * Rot(X=-90) * Cylinder(2.4, 1.2), COL["lens"], "glass",
    "laser_emisor", pose_tilt)

# ---- KY-008 expuesto sobre el cañón (PCB 18.5×15, tubo Ø6.5×10.5) ----
ky = Pos(0, 24, Z_TILT + 17.2)
for px in (-6, 6):
    add(Cylinder(1.2, 4), COL["alu"], "alu", "ky_standoff", pose_tilt * ky * Pos(px, -2, -2.8))
add(Box(15, 18.5, 1.6), COL["pcb_red"], "pcb", "ky008_pcb", pose_tilt * ky)
add(Rot(X=-90) * Cylinder(3.25, 10.5), COL["brass"], "brass", "ky008_tubo",
    pose_tilt * ky * Pos(0, 12.5, 4.0))
add(Rot(X=-90) * Cylinder(1.8, 1), COL["lens"], "glass", "ky008_lente",
    pose_tilt * ky * Pos(0, 18.2, 4.0))
add(Box(8, 2.5, 2.5), COL["chip"], "plastic", "ky008_pines", pose_tilt * ky * Pos(0, -8.5, 2))

# ---- Cámara de placa M12 (PCB 32×32, barril Ø13×16) sobre el pod ----
cam = Pos(0, 12, Z_TILT + 35)            # centro del PCB de la cámara
add(Box(36, 3, 36), COL["graphite"], "plastic", "cam_soporte",
    pose_tilt * cam * Pos(0, -2.6, 0))
add(Box(6, 3, 12), COL["graphite"], "plastic", "cam_columna",
    pose_tilt * Pos(0, 8.5, Z_TILT + 18))
add(Box(32, 1.6, 32), COL["pcb_green"], "pcb", "cam_pcb", pose_tilt * cam)
for px in (-14, 14):
    for pz in (-14, 14):
        add(Rot(X=90) * Cylinder(1.1, 2.4), COL["alu"], "alu", "cam_tornillo",
            pose_tilt * cam * Pos(px, 0.5, pz))
add(Box(16, 6, 16), COL["chip"], "plastic", "cam_holder", pose_tilt * cam * Pos(0, 3.8, 0))
add(Rot(X=-90) * Cylinder(6.5, 16), COL["chip"], "plastic", "cam_barril",
    pose_tilt * cam * Pos(0, 14.8, 0))
add(Rot(X=-90) * (Cylinder(7.2, 3.2) - Cylinder(6.5, 4)), COL["panel"], "plastic",
    "cam_anillo_foco", pose_tilt * cam * Pos(0, 19.5, 0))
add(Rot(X=-90) * Cylinder(4.6, 1.4), COL["lens"], "glass", "cam_lente",
    pose_tilt * cam * Pos(0, 22.9, 0))
add(Box(1.8, 1.2, 1), COL["amber"], "emissive", "cam_led", pose_tilt * cam * Pos(12, 1.2, -14.8))

# ---- HC-SR04 real bajo el cañón (PCB 45×20, transductores Ø16×12 a 26 mm) ----
us = Pos(0, 31, Z_TILT - 22)             # centro del PCB (vertical, mira a +Y)
add(Box(48, 3, 24), COL["graphite"], "plastic", "us_soporte", pose_tilt * us * Pos(0, -2.4, 1))
add(Box(45, 1.6, 20), COL["pcb_blue"], "pcb", "hcsr04_pcb", pose_tilt * us)
for px in (-13, 13):
    add(Rot(X=-90) * Cylinder(8, 12), COL["silver"], "metal", "hcsr04_transductor",
        pose_tilt * us * Pos(px, 6.9, 0))
    add(Rot(X=-90) * Cylinder(6.9, 0.8), COL["mesh"], "plastic", "hcsr04_malla",
        pose_tilt * us * Pos(px, 13.2, 0))
add(Box(10, 3.4, 4), COL["silver"], "metal", "hcsr04_cristal", pose_tilt * us * Pos(0, 2.5, -6))
add(Box(10, 2.5, 2.5), COL["chip"], "plastic", "hcsr04_pines", pose_tilt * us * Pos(0, -1.8, -11))

# ---- GY-521 (MPU6050) plano sobre el pod, atrás ----
gy = Pos(0, -16, Z_TILT + 16.8)
add(Box(16.4, 21.2, 1.6), COL["pcb_prpl"], "pcb", "gy521_pcb", pose_tilt * gy)
add(Box(4, 4, 0.9), COL["chip"], "plastic", "gy521_mpu", pose_tilt * gy * Pos(0, 2, 1.2))
add(Box(2.5, 20.3, 2.5), COL["chip"], "plastic", "gy521_header", pose_tilt * gy * Pos(-6, 0, -2))

# ---- Disipador trasero + prensaestopas ----
for i in range(5):
    add(Pos(-16 + i * 8, -30, Z_TILT) * Box(2.4, 9, 22), COL["panel"], "plastic",
        "aleta", pose_tilt)
add(Pos(0, -36, Z_TILT - 6) * Rot(X=90) * Cylinder(4, 7), COL["panel"], "plastic",
    "prensaestopas", pose_tilt)
add(Pos(0, -39.2, Z_TILT - 6) * Rot(X=90) * Cylinder(4.6, 1.6), COL["amber"], "emissive",
    "anillo_cable", pose_tilt)


# ================================ SALIDAS ===================================
def render(parts, out_png, *, views=None, hero_dir=None, win=(1300, 1000), zoom=1.32,
           focus_center=None, focus_radius=None):
    meshes = [(to_mesh(p["solid"], 0.1), p["color"], MAT[p["mat"]]) for p in parts]
    bounds = np.array([m.bounds for m, _, _ in meshes])
    lo = bounds[:, [0, 2, 4]].min(axis=0); hi = bounds[:, [1, 3, 5]].max(axis=0)
    center = np.array(focus_center) if focus_center is not None else (lo + hi) / 2
    radius = focus_radius or float(np.linalg.norm(hi - lo)) / 2 or 1.0

    def scene(pl):
        pl.set_background("#3A3A3A")
        cx, cy, cz = center; r = radius
        pl.add_light(pv.Light(position=(cx + 2 * r, cy - 2.5 * r, cz + 3 * r),
                              focal_point=center, color="white", intensity=0.95))
        pl.add_light(pv.Light(position=(cx - 2.5 * r, cy - 1.5 * r, cz + 1.2 * r),
                              focal_point=center, color=(0.8, 0.85, 1.0), intensity=0.45))
        pl.add_light(pv.Light(position=(cx - 0.5 * r, cy + 3 * r, cz + 2 * r),
                              focal_point=center, color="white", intensity=0.6))
        for mesh, colr, mat in meshes:
            pl.add_mesh(mesh, color=colr, smooth_shading=True, **mat)
        ground = pv.Plane(center=(cx, cy, lo[2] - 0.2), direction=(0, 0, 1),
                          i_size=radius * 6, j_size=radius * 6)
        pl.add_mesh(ground, color="#333539", ambient=0.25, diffuse=0.6, specular=0.05)

    if views:  # grilla 2x2
        pl = pv.Plotter(off_screen=True, shape=(2, 2), window_size=(1900, 1750), border=False)
        for idx, (vname, vdir) in enumerate(views.items()):
            pl.subplot(idx // 2, idx % 2)
            scene(pl)
            d = np.array(vdir, float); d /= np.linalg.norm(d)
            pl.camera_position = [tuple(center + d * radius * 3.0), tuple(center), (0, 0, 1)]
            pl.camera.zoom(1.3)
            pl.add_text(vname, font_size=9, color="white", position="upper_left")
    else:
        pl = pv.Plotter(off_screen=True, window_size=win, border=False)
        scene(pl)
        d = np.array(hero_dir, float); d /= np.linalg.norm(d)
        pl.camera_position = [tuple(center + d * radius * 2.6), tuple(center), (0, 0, 1)]
        pl.camera.zoom(zoom)
    try:
        pl.enable_shadows()
    except Exception:
        pass
    pl.enable_anti_aliasing("msaa", multi_samples=8)
    OUT.mkdir(exist_ok=True)
    pl.screenshot(str(out_png))
    pl.close()
    return out_png


def main():
    print(f"piezas: {len(PARTS)}")
    # bbox global
    comp = Compound(children=[p["solid"] for p in PARTS])
    bb = comp.bounding_box()
    print(f"bbox: {bb.size.X:.1f} x {bb.size.Y:.1f} x {bb.size.Z:.1f} mm")

    render(PARTS, OUT / "v2_views.png",
           views={"3/4 frente": (1.0, 1.2, 0.6), "lateral": (1.0, 0.05, 0.15),
                  "frente": (0.05, 1.0, 0.12), "picado": (0.8, 0.8, 1.2)})
    render(PARTS, OUT / "v2_hero.png", hero_dir=(1.0, 1.35, 0.45), zoom=1.0)
    render(PARTS, OUT / "v2_detalle.png", hero_dir=(1.0, 1.15, 0.3), zoom=1.05,
           focus_center=(0, 28, 124), focus_radius=58)
    print("renders ok")

    # GLB con color por pieza
    children = []
    for i, p in enumerate(PARTS):
        solids = p["solid"].solids() if hasattr(p["solid"], "solids") else [p["solid"]]
        c = Compound(children=list(solids))
        c.color = Color(p["color"])
        c.label = f"{p['name']}_{i}"
        children.append(c)
    scene = Compound(children=children)
    export_gltf(scene, str(OUT / "torreta_v2.glb"), binary=True)
    export_step(scene, str(OUT / "torreta_v2.step"))
    print("export ok:", OUT / "torreta_v2.glb")


if __name__ == "__main__":
    main()

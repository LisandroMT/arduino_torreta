"""Torreta FASE 2 — la maqueta esculpida de Fase 1, ahuecada y motorizada.

Toma la geometría estética PROBADA del paquete `torreta/` (base hexagonal con
patas y chevrones, cuerpo facetado con franjas/ventana/antena, cuna con
mejillas) y le practica cirugía booleana para integrar TODOS los componentes
de DESCRIPCION_PROYECTO.md por dentro, con UN SOLO cañón hueco que lleva el
láser KY-008 en la punta.

Piezas imprimibles: base · tapa · cuerpo (pan) · cañón+cuna (tilt).
Las cotas estructurales salen de turret.yaml con overrides funcionales acá.

Uso:  .venv/bin/python torreta_fase2.py
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
    Box, Color, Compound, Cylinder, Pos, Rot, export_gltf, export_step,
    export_stl, extrude, RegularPolygon,
)

from torreta.config import Config            # noqa: E402
from torreta.render import to_mesh           # noqa: E402
from torreta.parts import base as p_base     # noqa: E402
from torreta.parts import body as p_body     # noqa: E402
from torreta.parts import cradle as p_cradle  # noqa: E402
from torreta.assembly import _iter_solids    # noqa: E402
from torreta.layout import trunnion_pivot    # noqa: E402


def _fuse(parts):
    """Agrupa los sólidos en un Compound operable con booleanas.

    (Solid.fuse / `+` pueden devolver ShapeList, sobre el que las restas
    no operan en silencio — el Compound sí se comporta.)
    """
    solids = [s for part, _ in parts for s in _iter_solids(part)]
    return Compound(children=solids)

HERE = Path(__file__).parent
OUT = HERE / "outputs"

# ===================== OVERRIDES FUNCIONALES (sobre el YAML) ================
cfg = Config.load()
cfg.base.hex_across_flats_mm = 150   # interior con lugar para la electrónica
cfg.base.height_mm = 42
cfg.base.top_chamfer_mm = 7
cfg.base.leg_length_mm = 42
cfg.base.leg_thickness_mm = 10
cfg.neck.drum_dia_mm = 60
cfg.neck.drum_height_mm = 22
cfg.body.width_mm = 72
cfg.body.depth_mm = 70
cfg.body.back_height_mm = 78
cfg.body.front_height_mm = 54
cfg.body.trunnion_z_mm = 38
cfg.body.trunnion_x_mm = 38
cfg.body.trunnion_pin_dia_mm = 5.2   # bulón M5
cfg.body.ear_thickness_mm = 7
cfg.body.ear_gap_mm = 56
cfg.cradle.width_mm = 54
cfg.cradle.height_mm = 38
cfg.cradle.depth_mm = 42

PX, _, PZ = trunnion_pivot(cfg)              # pivote del tilt (eje Y), +X = tiro
# pose NEUTRA para exportar: el visor HTML articula pan/tilt en vivo sobre
# los GLB por pieza (los renders también salen neutros)
cfg.pose.pan_deg, cfg.pose.tilt_deg = 0, 0
PAN, TILT = cfg.pose.pan_deg, cfg.pose.tilt_deg
loc_pan = Rot(0, 0, PAN)
loc_gun = loc_pan * Pos(PX, 0, PZ) * Rot(0, -TILT, 0)

HOLGURA, PILOTO = 0.4, 1.8

# ============================== PALETA ======================================
COL = {
    "cuerpo": cfg.style.body_color, "tubo": cfg.style.tube_color,
    "acento": cfg.style.accent_color, "panel": "#191C20",
    "alu": "#B9C0C7", "acero": "#C8CDD2", "laton": "#C9A44A",
    "lente": "#0E1216", "servo": "#2A6FD6", "crema": "#E8E4D8",
    "blanco": "#EDEDED", "chip": "#16191D", "malla": "#3C4146",
    "pcb_azul": "#1660A8", "pcb_verde": "#1F6B34", "pcb_rojo": "#A4252B",
    "pcb_viol": "#5435A0", "pcb_esp": "#15314F", "lcd": "#9AD65A",
    "dht": "#F5F5F0",
}
MAT = {
    "plastico": dict(metallic=0.05, roughness=0.55, specular=0.3, specular_power=20, ambient=0.16, diffuse=0.85),
    "metal":   dict(metallic=0.85, roughness=0.35, specular=0.6, specular_power=50, ambient=0.16, diffuse=0.8),
    "pcb":     dict(metallic=0.0,  roughness=0.8,  specular=0.15, specular_power=10, ambient=0.2, diffuse=0.85),
    "vidrio":  dict(metallic=0.3,  roughness=0.12, specular=0.95, specular_power=90, ambient=0.12, diffuse=0.6),
    "emisivo": dict(metallic=0.0,  roughness=1.0,  specular=0.0,  specular_power=1, ambient=0.95, diffuse=0.3),
}

PARTS: list[dict] = []
PIEZAS: dict[str, object] = {}


def add(solid, color, mat, name, *, loc=None, pieza=None):
    if not hasattr(solid, "moved"):
        solid = Compound(children=list(solid))
    if loc is not None:
        solid = solid.moved(loc)
    PARTS.append(dict(solid=solid, color=color, mat=mat, name=name, pieza=pieza))
    return solid


# Marco del LCD: cara inclinada 35° del pod-consola sobre la pared 270°.
# OJO: el hexágono tiene VÉRTICES en los múltiplos de 60° (a 240° hay una
# punta que atravesaba la pantalla); las caras planas están en 30°+60k.
# 270° es cara plana, libre de patas, y fuera del barrido de la mentonera.
LOC_LCD = Rot(0, 0, 270) * Pos(85, 0, 31.5) * Rot(0, 35, 0)


# ============================================================================
# PIEZA: BASE (esculpida de Fase 1 + cirugía funcional)
# ============================================================================
def construir_base():
    partes = p_base.build(cfg)                       # [(solid, rol)] esculpido
    estructura = _fuse([p for p in partes if p[1] == "body"])

    # cavidad interior (queda piso del socket de 2 mm en z 26..28)
    estructura -= Pos(0, 0, 14.5) * extrude(RegularPolygon(
        (140 - 6) / 2 / math.cos(math.pi / 6), 6), 23)
    # montaje del 28BYJ-48 bajo el techo de la cavidad
    estructura -= Pos(0, 0, 27) * Cylinder(radius=3.6, height=8)        # eje Ø7.2
    for sx in (-1, 1):
        estructura -= Pos(0, 17.5 * sx, 27) * Cylinder(radius=2.15, height=8)
    # ranura pasacables junto al muñón (el mazo baja del tambor)
    estructura -= Pos(-19, 0, 34) * Box(12, 16, 22)
    # pod-consola del LCD sobre la CARA PLANA de 270°, elevado sobre las
    # patas (z 12..36) y por debajo de la superficie biselada
    pod = Pos(81, 0, 24) * Box(32, 86, 24)              # r 65..97
    # cara inclinada descendiendo hacia afuera (estilo atril)
    pod -= Pos(93, 0, 43) * Rot(0, 35, 0) * Box(42, 84, 28)
    pod = Rot(0, 0, 270) * pod
    estructura += pod
    estructura -= LOC_LCD * Pos(0, 0, -4) * Box(38, 81, 10)    # marco del LCD
    estructura -= LOC_LCD * Pos(0, 0, -10) * Box(32, 76, 14)   # bolsillo del PCB
    estructura -= LOC_LCD * Pos(0, 0, -16) * Box(14, 30, 14)   # paso de cables
    # funda del joystick en la cara plana de 90°
    funda = Rot(0, 0, 90) * Pos(77, 0, 21) * Box(12, 40, 34)
    funda -= Rot(0, 0, 90) * Pos(78.5, 0, 23) * Box(12, 26.5 + HOLGURA, 34)
    estructura += funda
    # ventilación del DHT22 (cara plana de 330°)
    for i in range(5):
        estructura -= Rot(0, 0, 330) * Pos(74, -12 + i * 6, 20) * Box(8, 2.4, 14)
    # rejilla del buzzer (cara plana de 30°)
    for dy in (-5, 0, 5):
        estructura -= Rot(0, 0, 30) * Pos(74, dy, 22) * Box(8, 2.4, 2.4)
    # salida USB / alimentación (cara plana de 210°)
    estructura -= Rot(0, 0, 210) * Pos(74, 0, 16) * Box(8, 13, 9)

    PIEZAS["base"] = estructura
    add(estructura, COL["cuerpo"], "plastico", "Base esculpida (hueca)", pieza="base")
    for part, rol in partes:                          # chevrones amarillos
        if rol == "accent":
            # saltear el chevrón del sector 240°: ahí va el pod del LCD
            c = part.bounding_box().center()
            if abs(((math.degrees(math.atan2(c.Y, c.X)) - 240 + 180) % 360) - 180) < 25:
                continue
            add(part, COL["acento"], "emisivo", "chevron", pieza="base")


def construir_tapa():
    tapa = extrude(RegularPolygon(141 / 2 / math.cos(math.pi / 6), 6), 2.5)
    for cx, cy, dx, dy in ((-18, -14, 48, 23), (20, -20, 35, 27)):
        for sx in (-1, 1):
            for sy in (-1, 1):
                b = Pos(cx + sx * dx / 2, cy + sy * dy / 2, 4.75) * Cylinder(radius=3, height=4.5)
                b -= Pos(cx + sx * dx / 2, cy + sy * dy / 2, 5) * Cylinder(radius=PILOTO / 2, height=5)
                tapa += b
    PIEZAS["tapa"] = tapa
    add(tapa, COL["panel"], "plastico", "Tapa porta-electronica", pieza="tapa")


# ============================================================================
# PIEZA: CUERPO (esculpido de Fase 1 + D-hub + hueco + servo)
# ============================================================================
def construir_cuerpo():
    partes = p_body.build(cfg)
    cuerpo = _fuse([p for p in partes if p[1] == "body"])

    # eje impreso -> muñón-rodamiento: agujero en D para el eje del stepper
    d_hole = (Cylinder(radius=(5 + 0.15) / 2, height=14) &
              Box(7, 3 + 0.15, 14))
    cuerpo -= Pos(0, 0, 34) * d_hole

    # ahuecado: tambor hueco DEJANDO el piso que une el eje motriz (z 41..48)
    cuerpo -= Pos(0, 0, 57) * Cylinder(radius=23, height=18)
    # ranura pasacables a través del piso del tambor (alinea con la base en pan=0)
    cuerpo -= Pos(-19, 0, 50) * Box(12, 16, 20)
    from build123d import Plane, Polygon
    z0 = 42 + cfg.neck.drum_height_mm                                   # 64
    inner = Plane.XZ * Polygon((-31, z0 - 4), (29, z0 - 4), (29, z0 + 50),
                               (-31, z0 + 74), align=None)
    cuerpo -= Pos(0, 32, 0) * extrude(inner, amount=64)
    # (la extrusión de Plane.XZ va hacia -Y: queda centrada con el Pos previo)

    # zócalo de la antena: con el cuerpo agrandado, el techo inclinado queda
    # 2 mm por debajo de donde el builder original apoya la base de la antena
    cuerpo += Pos(-cfg.body.depth_mm * 0.28, 0, 136) * Box(10, 12, 7)

    # holgura de tilt: profundizar la boca entre orejas para que la cuna
    # (esquina trasera a r=27 del pivote) bascule -5°..+30° sin rozar
    cuerpo -= Pos(36, 0, PZ) * Box(46, cfg.body.ear_gap_mm, 78)

    # pad + pocket pasante del SG90 en la oreja derecha (+Y)
    y_ear = cfg.body.ear_gap_mm / 2 + cfg.body.ear_thickness_mm / 2     # 31.5
    cuerpo += Pos(PX + 12, y_ear, PZ) * Box(24, cfg.body.ear_thickness_mm, 28)
    cuerpo -= Pos(PX + 5.35, y_ear, PZ) * Box(23.1, 9, 12.4)
    for dx in (-13.9, 13.9):
        cuerpo -= Pos(PX + 5.35 + dx, y_ear + 2, PZ) * Rot(90, 0, 0) * \
            Cylinder(radius=PILOTO / 2, height=6)

    PIEZAS["cuerpo"] = cuerpo
    add(cuerpo, COL["cuerpo"], "plastico", "Cuerpo blindado (hueco)",
        loc=loc_pan, pieza="cuerpo")
    for part, rol in partes:
        if rol == "accent":
            add(part, COL["acento"], "emisivo", "acento_cuerpo",
                loc=loc_pan, pieza="cuerpo")


# ============================================================================
# PIEZA: CAÑÓN ÚNICO + CUNA (tilt) — el láser va DENTRO de la punta
# ============================================================================
def construir_canon():
    partes = p_cradle.build(cfg)
    arma = _fuse([p for p in partes if p[1] == "body"])

    # ---- cañón único esculpido (eje +X) ----
    eje = Rot(0, 90, 0)
    recamara = Pos(19, 0, 0) * eje * Cylinder(radius=13, height=22)
    tubo = Pos(74, 0, 0) * eje * Cylinder(radius=10, height=92)
    arma += recamara + tubo
    for xg in (52, 70, 88):                       # ranuras térmicas
        arma -= Pos(xg, 0, 0) * eje * (Cylinder(radius=10.6, height=2.2)
                                       - Cylinder(radius=9.2, height=2.4))
    freno = Pos(128, 0, 0) * eje * Cylinder(radius=12, height=18)
    for sy in (-1, 1):                            # venteos laterales del freno
        freno -= Pos(128, 9 * sy, 0) * Box(10, 6, 5)
    arma += freno
    # interior: conducto Ø17 hasta la boca, salida Ø7.4 (el KY-008 entra
    # por la cuna y queda alojado en la punta, con la lente asomando)
    arma -= Pos(75, 0, 0) * eje * Cylinder(radius=8.5, height=120)
    arma -= Pos(135.2, 0, 0) * eje * Cylinder(radius=3.7, height=6)

    # ---- cuna hueca (pocket de cables + GY-521) ----
    arma -= Pos(0, 0, -6) * Box(30, 40, 30)
    gy_boss = Pos(-6, 0, -19) * Box(24, 20, 4)
    for dy in (-7.6, 7.6):
        gy_boss -= Pos(-6, dy, -18.5) * Cylinder(radius=PILOTO / 2, height=5)
    arma += gy_boss

    # ---- mentonera del HC-SR04, colgada de la cuna por cartelas + espina ----
    menton = Pos(29, 0, -33) * Box(3, 52, 26)
    for sy in (-1, 1):
        menton -= Pos(29, 13 * sy, -35) * eje * Cylinder(radius=8.3, height=6)
        # cartelas: suben hasta solapar el bloque de la cuna (z -19..-12)
        menton += Pos(20.5, 24 * sy, -27) * Box(17, 2, 30)
    # espina central: une la placa con la recámara del cañón
    menton += Pos(25, 0, -16) * Box(8, 10, 12)
    arma += menton

    # ---- bandeja superior de la webcam, ELEVADA sobre columnas para pasar
    # POR ENCIMA de las orejas del muñón al bascular (bandeja 64 > hueco 56) ----
    bandeja = Pos(0, 0, 30.5) * Box(46, 64, 3)
    for sy in (-1, 1):
        for dx in (-12, 12):
            bandeja -= Pos(dx, 24 * sy, 30.5) * Box(5, 6, 5)
        bandeja += Pos(-2, 18 * sy, 24) * Box(14, 10, 12)    # columnas a la cuna
    bandeja += Pos(21, 0, 34) * Box(2.5, 64, 9)              # tope frontal
    arma += bandeja

    # ---- acople del horn del SG90 (cara derecha) + ranura ----
    arma -= Pos(5.35, 26, 0) * Box(5.2, 3, 18.5)

    PIEZAS["canon_cuna"] = arma
    add(arma, COL["cuerpo"], "plastico", "Cañón único + cuna", loc=loc_gun,
        pieza="canon_cuna")
    add(Pos(135.5, 0, 0) * Rot(0, 90, 0) * (Cylinder(radius=12.2, height=2)
        - Cylinder(radius=10.5, height=3)), COL["acento"], "emisivo",
        "anillo_boca", loc=loc_gun, pieza="canon_cuna")


# ============================================================================
# COMPONENTES (alojados; visibles en el corte y el despiece)
# ============================================================================
def componentes():
    eje = Rot(0, 90, 0)
    # --- base ---
    add(Pos(0, 0, 15.5) * Cylinder(radius=14, height=19), COL["acero"], "metal", "28BYJ-48")
    add(Pos(0, 0, 25.5) * Box(7, 35, 1), COL["acero"], "metal", "28BYJ-48 brida")
    add(Pos(0, 0, 30) * Cylinder(radius=2.5, height=10), COL["alu"], "metal", "28BYJ-48 eje")
    add(Pos(-15.5, 0, 16) * Box(6, 14.6, 16.5), COL["servo"], "plastico", "28BYJ-48 cables")
    esp = Pos(-18, -14, 8.6)
    add(esp * Box(27.9, 54.4, 1.6), COL["pcb_esp"], "pcb", "ESP32 DevKit")
    add(esp * Pos(0, -12, 2.3) * Box(18, 25.5, 3.1), COL["acero"], "metal", "WROOM-32")
    uln = Pos(20, -20, 8.6)
    add(uln * Box(35, 27, 1.6), COL["pcb_verde"], "pcb", "ULN2003")
    add(uln * Pos(-6, 0, 2.8) * Box(7, 19, 4), COL["chip"], "plastico", "ULN2003 IC")
    # LCD embutido
    add(LOC_LCD * Pos(0, 0, -7) * Box(36, 80, 1.6), COL["pcb_verde"], "pcb", "LCD 1602 PCB")
    add(LOC_LCD * Pos(0, 0, -4.5) * Box(30.5, 75, 5), COL["chip"], "plastico", "LCD bezel")
    add(LOC_LCD * Pos(0, 0, -1.6) * Box(16, 64.5, 1), COL["lcd"], "emisivo", "LCD pantalla")
    # DHT22 / buzzer / joystick
    add(Rot(0, 0, 330) * Pos(66, 0, 22) * Box(7.7, 15.1, 25.1), COL["dht"],
        "plastico", "DHT22")
    add(Rot(0, 0, 30) * Pos(66, 0, 22) * Rot(0, 90, 0) * Cylinder(radius=6, height=9.5),
        COL["chip"], "plastico", "Buzzer")
    joy = Rot(0, 0, 90) * Pos(79.5, 0, 19)
    add(joy * Box(7, 26, 32), COL["pcb_rojo"], "pcb", "Joystick PCB")
    add(joy * Pos(6, 0, 6) * Rot(0, 90, 0) * Cylinder(radius=9, height=6),
        COL["chip"], "plastico", "Joystick domo")
    add(joy * Pos(12, 0, 6) * Rot(0, 90, 0) * Cylinder(radius=1.8, height=8),
        COL["chip"], "plastico", "Joystick palanca")
    # --- cuerpo (pan) ---
    sg = loc_pan * Pos(PX + 5.35, cfg.body.ear_gap_mm / 2 + cfg.body.ear_thickness_mm + 2, PZ) * Rot(-90, 0, 0) * Rot(0, 0, 90)
    add(Pos(0.55, 0, 11.35) * Box(22.5, 11.8, 22.7), COL["servo"], "plastico", "SG90", loc=sg)
    add(Pos(0.55, 0, 17.65) * Box(32.2, 11.8, 2.5), COL["servo"], "plastico", "SG90 aletas", loc=sg)
    add(Pos(0, 0, 24.7) * Cylinder(radius=5.9, height=4), COL["servo"], "plastico", "SG90 tapa", loc=sg)
    add(loc_pan * Pos(PX, -(cfg.body.ear_gap_mm / 2 + cfg.body.ear_thickness_mm + 1.5), PZ) *
        Rot(90, 0, 0) * Cylinder(radius=4.5, height=3), COL["alu"], "metal", "M5 cabeza")
    # --- cañón / cuna (tilt) ---
    # PCB bajo del eje para que el tubo de latón quede centrado en la salida
    add(Pos(124, 0, -4) * Box(18.5, 15.2, 1.6), COL["pcb_rojo"], "pcb", "KY-008",
        loc=loc_gun)
    add(Pos(132, 0, 0) * eje * Cylinder(radius=3.25, height=10.5), COL["laton"],
        "metal", "KY-008 tubo", loc=loc_gun)
    add(Pos(135.9, 0, 0) * eje * Cylinder(radius=1.8, height=1.2), COL["lente"],
        "vidrio", "KY-008 lente", loc=loc_gun)
    add(Pos(-6, 0, -16) * Box(16.4, 21.2, 1.6), COL["pcb_viol"], "pcb", "GY-521",
        loc=loc_gun)
    us = Pos(26.5, 0, -35)
    add(us * Box(1.6, 45, 20), COL["pcb_azul"], "pcb", "HC-SR04 PCB", loc=loc_gun)
    for sy in (-1, 1):
        add(us * Pos(6.9, 13 * sy, 0) * eje * Cylinder(radius=8, height=12),
            COL["acero"], "metal", "HC-SR04 transductor", loc=loc_gun)
        add(us * Pos(13.2, 13 * sy, 0) * eje * Cylinder(radius=6.9, height=0.8),
            COL["malla"], "plastico", "HC-SR04 malla", loc=loc_gun)
    add(Pos(0, 0, 36.7) * Box(30, 60, 9.5), COL["chip"], "plastico",
        "Webcam (generica)", loc=loc_gun)
    add(Pos(16.5, 0, 36.7) * eje * Cylinder(radius=7, height=4), COL["panel"],
        "plastico", "Webcam barril", loc=loc_gun)
    add(Pos(19, 0, 36.7) * eje * Cylinder(radius=4.5, height=1.2), COL["lente"],
        "vidrio", "Webcam lente", loc=loc_gun)


# ================================ RENDER ====================================
def render(parts, out_png, *, views=None, hero_dir=None, zoom=1.05, clip=None,
           win=(1400, 1050)):
    meshes = []
    for p in parts:
        try:
            m = to_mesh(p["solid"], 0.12)
        except Exception as e:
            print(f"  [render] AVISO: '{p['name']}' no teselable ({e}); se omite")
            continue
        if clip is not None:
            m = m.clip(normal=clip[0], origin=clip[1], invert=True)
            if m.n_points == 0:
                continue
        meshes.append((m, p["color"], MAT[p["mat"]]))
    bounds = np.array([m.bounds for m, _, _ in meshes])
    lo = bounds[:, [0, 2, 4]].min(axis=0); hi = bounds[:, [1, 3, 5]].max(axis=0)
    center = (lo + hi) / 2
    radius = float(np.linalg.norm(hi - lo)) / 2 or 1.0

    def scene(pl):
        pl.set_background(cfg.style.background)
        cx, cy, cz = center; r = radius
        pl.add_light(pv.Light(position=(cx + 2 * r, cy - 2.5 * r, cz + 3 * r),
                              focal_point=center, color="white", intensity=0.95))
        pl.add_light(pv.Light(position=(cx - 2.5 * r, cy - 1.5 * r, cz + 1.2 * r),
                              focal_point=center, color=(0.8, 0.85, 1.0), intensity=0.45))
        pl.add_light(pv.Light(position=(cx - 0.5 * r, cy + 3 * r, cz + 2 * r),
                              focal_point=center, color="white", intensity=0.6))
        for mesh, colr, mat in meshes:
            pl.add_mesh(mesh, color=colr, smooth_shading=True, **mat)
        ground = pv.Plane(center=(cx, cy, lo[2] - 0.3), direction=(0, 0, 1),
                          i_size=radius * 6, j_size=radius * 6)
        pl.add_mesh(ground, color="#333539", ambient=0.25, diffuse=0.6, specular=0.05)

    if views:
        pl = pv.Plotter(off_screen=True, shape=(2, 2), window_size=(1900, 1750), border=False)
        for idx, (vname, vdir) in enumerate(views.items()):
            pl.subplot(idx // 2, idx % 2)
            scene(pl)
            d = np.array(vdir, float); d /= np.linalg.norm(d)
            pl.camera_position = [tuple(center + d * radius * 3.0), tuple(center), (0, 0, 1)]
            pl.camera.zoom(1.25)
            pl.add_text(vname, font_size=10, color="white", position="upper_left")
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


def render_explotado(out_png):
    offsets = {"tapa": (0, 0, -50), "base": (0, 0, 0), "cuerpo": (0, 0, 65),
               "canon_cuna": (60, 0, 150), None: (0, 0, 0)}
    sueltos = [dict(p, solid=p["solid"].moved(Pos(*offsets.get(p["pieza"], (0, 0, 0)))))
               for p in PARTS]
    return render(sueltos, out_png, hero_dir=(1.4, 1.0, 0.4), zoom=0.95,
                  win=(1250, 1450))


# ================================= MAIN =====================================
def main():
    construir_base()
    construir_tapa()
    construir_cuerpo()
    construir_canon()
    componentes()
    print(f"sólidos: {len(PARTS)}")
    # GATE de conexidad con depuración: las esquirlas de las booleanas de
    # OCCT (<1.5 cm3) se descartan con aviso —igual que el mesh-healing de un
    # slicer—; un cuerpo suelto GRANDE sigue siendo error de diseño y corta.
    todo_ok = True
    for nombre, s in PIEZAS.items():
        if not hasattr(s, "volume"):
            s = Compound(children=list(s)); PIEZAS[nombre] = s
        ss = list(s.solids())
        fused = ss[0].fuse(*ss[1:]) if len(ss) > 1 else ss[0]
        cuerpos = list(fused.solids()) if hasattr(fused, "solids") else list(fused)
        cuerpos.sort(key=lambda c: -c.volume)
        migas = [c for c in cuerpos[1:] if c.volume < 1500]
        grandes = [c for c in cuerpos[1:] if c.volume >= 1500]
        if migas:
            print(f"  [depurado] {nombre}: se descartan {len(migas)} esquirla(s) "
                  f"({sum(m.volume for m in migas)/1000:.2f} cm3)")
            principal = cuerpos[0]
            for p in PARTS:          # también en render/GLB, no solo en el STL
                if p["solid"] is s:
                    p["solid"] = principal
            s = principal
            PIEZAS[nombre] = s
        estado = "OK" if not grandes else f"*** {len(grandes)+1} CUERPOS SUELTOS ***"
        if grandes:
            todo_ok = False
        b = s.bounding_box()
        print(f"  {nombre:12s} {s.volume/1000:7.1f} cm3  "
              f"{b.size.X:5.0f} x {b.size.Y:5.0f} x {b.size.Z:5.0f} mm  conexidad: {estado}")
    if not todo_ok:
        raise SystemExit("GATE DE CONEXIDAD FALLÓ: hay piezas con partes flotantes")

    # GATE de imprimibilidad (el mismo de Fase 1): válido OCCT + estanco
    from torreta.validate import check_all
    ok_print, reporte = check_all(PIEZAS, cfg)
    print(reporte)
    if not ok_print:
        raise SystemExit("GATE DE IMPRIMIBILIDAD FALLÓ (ver reporte)")

    render(PARTS, OUT / "f2_views.png",
           views={"3/4 frente": (1.2, 1.0, 0.55), "lateral": (0.05, 1.0, 0.15),
                  "frente": (1.0, 0.05, 0.12), "picado": (0.8, 0.8, 1.2)})
    render(PARTS, OUT / "f2_hero.png", hero_dir=(1.35, 1.0, 0.42))
    render(PARTS, OUT / "f2_corte.png", hero_dir=(0.9, 1.0, 0.35),
           clip=("y", (0, 0.01, 0)))
    render_explotado(OUT / "f2_explotado.png")
    print("renders ok")

    # etiqueta GLB = "pieza__nombre": el visor HTML agrupa por pieza para explotar
    COMP2PIEZA = [("28BYJ", "base"), ("ESP32", "tapa"), ("WROOM", "tapa"),
                  ("ULN2003", "tapa"), ("LCD", "base"), ("DHT22", "base"),
                  ("Buzzer", "base"), ("Joystick", "base"), ("SG90", "cuerpo"),
                  ("M5", "cuerpo"), ("KY-008", "canon_cuna"), ("GY-521", "canon_cuna"),
                  ("HC-SR04", "canon_cuna"), ("Webcam", "canon_cuna")]
    grupos = {"base": [], "tapa": [], "cuerpo": [], "canon_cuna": []}
    for i, p in enumerate(PARTS):
        solids = p["solid"].solids() if hasattr(p["solid"], "solids") else [p["solid"]]
        c = Compound(children=list(solids))
        c.color = Color(p["color"])
        pieza = p["pieza"] or next((pz for pref, pz in COMP2PIEZA
                                    if p["name"].startswith(pref)), "base")
        c.label = f"{pieza}__{p['name']}_{i}"
        grupos[pieza].append(c)
    children = [c for cs in grupos.values() for c in cs]
    export_gltf(Compound(children=children), str(OUT / "torreta_fase2.glb"), binary=True)
    export_step(Compound(children=children), str(OUT / "torreta_fase2.step"))
    # un GLB por pieza: el visor HTML los carga como grupos explotables
    # (el writer de OCCT descarta los nombres de nodo, así que el agrupado
    # tiene que venir por archivo, no por etiqueta)
    for g, cs in grupos.items():
        export_gltf(Compound(children=cs), str(OUT / f"fase2_{g}.glb"), binary=True)
    pdir = OUT / "parts_fase2"
    pdir.mkdir(exist_ok=True)
    for nombre, s in PIEZAS.items():
        export_stl(s, str(pdir / f"{nombre}.stl"), tolerance=0.08, angular_tolerance=0.2)
    print("export ok:", OUT / "torreta_fase2.glb", "+", pdir)


if __name__ == "__main__":
    main()

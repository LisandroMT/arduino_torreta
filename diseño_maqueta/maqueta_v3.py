"""Maqueta v3 — torreta IMPRIMIBLE con todos los componentes integrados (Fase 2).

Estética gatling de Fase 1 + ingeniería de integración: la estructura es HUECA,
el cableado y la electrónica van por dentro, y cada componente del BOM de
DESCRIPCION_PROYECTO.md tiene su alojamiento con medidas de datasheet:

  ESP32 DevKit · ULN2003 · 28BYJ-48 · SG90 · HC-SR04 · KY-008 · GY-521 (MPU6050)
  DHT22 · LCD 1602 · buzzer · joystick (funda) · webcam (bandeja universal)

Piezas imprimibles (sin soportes, pared >= 2.5 mm):
  1. base          carcasa octogonal hueca + consola LCD + funda joystick
  2. tapa          tapa inferior porta-electrónica (ESP32/ULN sobre la tapa)
  3. tambor_cuerpo tambor + cuerpo blindado, hueco, cubo con agujero en D
  4. mantelete     cuna hueca: KY-008 adentro, mentonera HC-SR04, bandeja webcam
  5. racimo        racimo gatling con canal central Ø7.5 para el haz del láser

El cableado del pod baja por el interior del tambor y entra a la base por una
ranura junto al cubo; el sector ±180° (decisión del proyecto) evita el enredo.

Salidas: renders (vistas/hero/CORTE/explotado), GLB, STEP y STL por pieza.
Uso:  .venv/bin/python maqueta_v3.py
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
    Axis, Box, Color, Compound, Cylinder, Plane, Polygon, Pos, RegularPolygon,
    Rot, Sphere, export_gltf, export_step, export_stl, extrude, fillet,
)

from torreta.render import to_mesh  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE / "outputs"

# ====================== TOLERANCIAS DE IMPRESIÓN (mm) =======================
HOLGURA = 0.4        # encastres de componentes (pockets)
HOLG_AGUJERO = 0.3   # agujeros pasantes
PARED = 3.0          # pared estándar de carcasa
PILOTO = 1.8         # diámetro piloto p/ tornillos autorroscantes de servo/PCB

# ============================== POSE DEL RENDER =============================
PAN_DEG, TILT_DEG = 22, -10
PIVOTE = (0, 40, 118)        # eje de elevación: +22 sobre v. inicial para que la
                             # mentonera del HC-SR04 libre la consola al bascular

pose_pan = Rot(Z=PAN_DEG)
pose_tilt = pose_pan * Pos(*PIVOTE) * Rot(X=TILT_DEG) * Pos(-PIVOTE[0], -PIVOTE[1], -PIVOTE[2])

# ============================== PALETA / MATERIALES =========================
COL = {
    "gunmetal": "#23262B", "panel": "#191C20", "tubo": "#9DA0A4",
    "ambar": "#F2C200", "alu": "#B9C0C7", "acero": "#C8CDD2",
    "laton": "#C9A44A", "lente": "#0E1216", "servo": "#2A6FD6",
    "crema": "#E8E4D8", "blanco": "#EDEDED", "chip": "#16191D",
    "malla": "#3C4146", "pcb_azul": "#1660A8", "pcb_verde": "#1F6B34",
    "pcb_rojo": "#A4252B", "pcb_viol": "#5435A0", "pcb_esp": "#15314F",
    "lcd": "#9AD65A", "dht": "#F5F5F0",
}
MAT = {
    "plastico": dict(metallic=0.05, roughness=0.55, specular=0.3, specular_power=20, ambient=0.16, diffuse=0.85),
    "metal":   dict(metallic=0.85, roughness=0.35, specular=0.6, specular_power=50, ambient=0.16, diffuse=0.8),
    "pcb":     dict(metallic=0.0,  roughness=0.8,  specular=0.15, specular_power=10, ambient=0.2, diffuse=0.85),
    "vidrio":  dict(metallic=0.3,  roughness=0.12, specular=0.95, specular_power=90, ambient=0.12, diffuse=0.6),
    "emisivo": dict(metallic=0.0,  roughness=1.0,  specular=0.0,  specular_power=1, ambient=0.95, diffuse=0.3),
}

PARTS: list[dict] = []   # {solid, color, mat, name, pieza}
PIEZAS: dict[str, object] = {}   # sólido imprimible por nombre (pose neutra)


def add(solid, color, mat, name, *, loc=None, pieza=None):
    if not hasattr(solid, "moved"):           # ShapeList -> Compound
        solid = Compound(children=list(solid))
    if loc is not None:
        solid = solid.moved(loc)
    PARTS.append(dict(solid=solid, color=color, mat=mat, name=name, pieza=pieza))
    return solid


def octogono(r, h):
    return extrude(RegularPolygon(r, 8), h)


# ============================================================================
# PIEZA 1: BASE — carcasa octogonal hueca (fija)
# ============================================================================
def construir_base():
    R, H = 75, 50
    casc = Rot(Z=22.5) * (octogono(R, H) - Pos(0, 0, -1) * octogono(R - PARED, H - 2))
    # (caras planas al frente; techo de 3 mm en z 47..50)

    # --- consola LCD sobre el techo, cara inclinada 35° ---
    consola = Pos(0, 58, 0) * Pos(0, 0, 63) * Box(92, 24, 26)
    consola = consola - (Pos(0, 64, 84) * Rot(X=-35) * Box(96, 60, 30))
    cara = Pos(0, 56.5, 62) * Rot(X=-35)            # marco local de la cara del LCD
    consola = consola - cara * Pos(0, 0, -6) * Box(81, 37, 12)   # bolsillo del LCD
    casc = casc + consola
    casc = casc - cara * Box(65, 17, 30)                          # ventana visible

    # --- techo: montaje del stepper (cuelga por debajo) + pasacables ---
    casc = casc - Pos(0, 0, 46) * Cylinder(3.0 + HOLG_AGUJERO / 2, 10)        # eje
    for sx in (-1, 1):
        casc = casc - Pos(17.5 * sx, 0, 46) * Cylinder(2.1, 10)               # M4 brida
    casc = casc - Pos(0, -14, 46) * Box(16, 7, 10)                            # ranura cables

    # --- pared trasera: ventilación del DHT22 + salida USB ---
    for i in range(5):
        casc = casc - Pos(-12 + i * 6, -68, 28) * Box(2.4, 8, 16)
    casc = casc - Pos(25, -68, 9) * Box(14, 8, 10)

    # --- pared izquierda: rejilla del buzzer ---
    for dz in (-4, 0, 4):
        casc = casc - Pos(-68, -10, 26 + dz) * Box(8, 2.4, 2.4)

    # --- pared derecha: funda del joystick (clip en U) ---
    funda = Pos(73.5, -6, 22) * Box(13, 40, 34)
    funda = funda - Pos(74.5, -6, 24) * Box(13, 28.5, 34)     # ranura (joystick 26+holg)
    casc = casc + funda

    PIEZAS["base"] = casc
    add(casc, COL["gunmetal"], "plastico", "Base (carcasa)", pieza="base")

    # tira de luz perimetral (estética, pegada): 8 listones ámbar tangenciales
    for i in range(8):
        a = (i + 0.5) * math.pi / 4
        add(Pos(70.5 * math.sin(a), 70.5 * math.cos(a), 8) *
            Rot(Z=-math.degrees(a)) * Box(46, 2, 2.4),
            COL["ambar"], "emisivo", "tira_luz", pieza="base")


# ============================================================================
# PIEZA 2: TAPA inferior porta-electrónica
# ============================================================================
def construir_tapa():
    tapa = Rot(Z=22.5) * octogono(71.4, 2.5)
    # bosses para ESP32 (54.4x27.9, agujeros aprox 48x23) y ULN2003 (35x27)
    for cx, cy, dx, dy in ((-22, -16, 48, 23), (24, -20, 35, 27)):
        for sx in (-1, 1):
            for sy in (-1, 1):
                b = Pos(cx + sx * dx / 2, cy + sy * dy / 2, 4.75) * Cylinder(3, 4.5)
                b -= Pos(cx + sx * dx / 2, cy + sy * dy / 2, 5) * Cylinder(PILOTO / 2, 5)
                tapa = tapa + b
    PIEZAS["tapa"] = tapa
    add(tapa, COL["panel"], "plastico", "Tapa porta-electronica", pieza="tapa")


# ============================================================================
# PIEZA 3: TAMBOR + CUERPO BLINDADO (gira, hueco)
# ============================================================================
def construir_tambor_cuerpo():
    # tambor: pollera que solapa el techo de la base con 0.5 de luz
    ext = Pos(0, 0, 84.25) * Cylinder(42, 67.5)
    inte = Pos(0, 0, 84) * Cylinder(42 - PARED, 68.5)
    # cuerpo blindado: cuña facetada hueca (perfiles exterior/interior en YZ)
    perfil_ext = Plane.YZ * Polygon((-40, 118), (34, 118), (34, 130), (18, 150),
                                    (-24, 172), (-40, 172), align=None)
    perfil_int = Plane.YZ * Polygon((-37, 114), (31, 114), (31, 127.5), (15.5, 146),
                                    (-21, 169), (-37, 169), align=None)
    ext = ext + Pos(-33, 0, 0) * extrude(perfil_ext, 66)
    inte = inte + Pos(-30, 0, 0) * extrude(perfil_int, 60)
    pieza = ext - inte

    # cubo motriz: agujero en D para el eje del 28BYJ-48 (Ø5 con planos a 3)
    cubo = Pos(0, 0, 54) * Cylinder(8, 7)
    d = 5 + 0.15
    agujero_d = (Cylinder(d / 2, 16) & Box(d + 1, 3 + 0.15, 16))
    cubo = cubo - Pos(0, 0, 53) * agujero_d
    pieza = pieza + cubo
    for ang in (30, 150, 270):           # 3 rayos cubo->pared (dejan pasar cables)
        pieza = pieza + (Rot(Z=ang) * Pos(23, 0, 54) * Box(32, 5, 7))

    # brazos de muñón al frente
    for sx in (-1, 1):
        pieza = pieza + Pos(30 * sx, 45, 119) * Box(6, 32, 24)
    # derecho: pocket pasante del SG90 (cuerpo 22.5x11.8x22.7 + holgura)
    pieza = pieza - Pos(30, 45.35, 118) * Box(8, 23.1, 12.4)
    for dy in (-13.9, 13.9):             # pilotos de las aletas del servo
        pieza = pieza - Pos(31.5, 45.35 + dy, 118) * Rot(Y=90) * Cylinder(PILOTO / 2, 6)
    # izquierdo: pivote M5 pasante
    pieza = pieza - Pos(-30, 40, 118) * Rot(Y=90) * Cylinder(2.6 + HOLG_AGUJERO / 2, 10)

    # franjas y escotilla (estética del diseño original)
    PIEZAS["tambor_cuerpo"] = pieza
    add(pieza, COL["gunmetal"], "plastico", "Tambor + cuerpo (giratorio)",
        loc=pose_pan, pieza="tambor_cuerpo")
    for sx in (-1, 1):
        add(Pos(12 * sx, 33.6, 124) * Box(6, 1.4, 12), COL["ambar"], "emisivo",
            "franja", loc=pose_pan, pieza="tambor_cuerpo")


# ============================================================================
# PIEZA 4: MANTELETE (bascula, hueco) + mentonera HC-SR04 + bandeja webcam
# ============================================================================
def construir_mantelete():
    ext = Pos(0, 44, 120) * Box(52, 30, 40)
    inte = Pos(0, 42, 120) * Box(52 - 2 * 2.5, 28, 40 - 2 * 2.5)  # trasera abierta
    pieza = ext - inte
    # boca del cañón (canal del láser) Ø7.5 en la pared frontal
    pieza = pieza - Pos(0, 57.5, 118) * Rot(X=-90) * Cylinder(3.75, 6)
    # pilotos del racimo
    for dz in (-12, 12):
        pieza = pieza - Pos(0, 57.5, 118 + dz) * Rot(X=-90) * Cylinder(PILOTO / 2, 6)
    # ranura de cables del HC-SR04 (piso) y trasera ya abierta p/ mazo principal
    pieza = pieza - Pos(0, 52, 101) * Box(12, 6, 6)

    # --- mentonera HC-SR04: placa frontal con 2 agujeros Ø16.6 + cartelas ---
    menton = Pos(0, 57.5, 91) * Box(52, 3, 22)
    for sx in (-1, 1):
        menton = menton - Pos(13 * sx, 57.5, 90) * Rot(X=-90) * Cylinder(8.3, 6)
        menton = menton + Pos(24.2 * sx, 51, 95.5) * Box(1.0, 16, 13)  # cartelas
    pieza = pieza + menton

    # --- alojamiento interno del KY-008 (rieles que toman el PCB de 15.2) ---
    for sx in (-1, 1):
        pieza = pieza + Pos((15.2 / 2 + 1.6) * sx, 50, 112.5) * Box(2.4, 12, 9)
    pieza = pieza + Pos(0, 50, 107.4) * Box(19, 12, 2)            # estante

    # --- boss interno del GY-521 (2 pilotos) ---
    gy_boss = Pos(-12, 38, 104.2) * Box(20, 18, 3.5)
    for dy in (-7.6, 7.6):
        gy_boss = gy_boss - Pos(-12, 38 + dy, 104.5) * Cylinder(PILOTO / 2, 4)
    pieza = pieza + gy_boss

    # --- bandeja superior para la webcam (ranuras p/ precinto o velcro) ---
    bandeja = Pos(0, 42, 141.5) * Box(64, 44, 3)
    for sx in (-1, 1):
        for dy in (-12, 12):
            bandeja = bandeja - Pos(24 * sx, 42 + dy, 141.5) * Box(6, 5, 5)
    bandeja = bandeja + Pos(0, 63, 143.8) * Box(64, 2.5, 8)       # tope frontal
    pieza = pieza + bandeja

    # --- acoples del eje de elevación ---
    # derecha: ranura para el horn del SG90 + piloto central
    pieza = pieza - Pos(25.2, 45.35, 118) * Box(2.4, 5.2, 18.5)
    pieza = pieza - Pos(25.2, 45.35, 118) * Rot(Y=90) * Cylinder(1.1, 8)
    # izquierda: trampa hexagonal p/ tuerca M5 + pasante
    pieza = pieza - Pos(-30, 40, 118) * Rot(Y=90) * Cylinder(2.6 + HOLG_AGUJERO / 2, 12)
    hexa = Rot(Y=90) * extrude(RegularPolygon(8.1 / math.sqrt(3) + 0.1, 6), 3.4)
    pieza = pieza - Pos(-23.2, 40, 118) * hexa

    PIEZAS["mantelete"] = pieza
    add(pieza, COL["gunmetal"], "plastico", "Mantelete (cuna hueca)",
        loc=pose_tilt, pieza="mantelete")


# ============================================================================
# PIEZA 5: RACIMO GATLING (canal central libre para el haz)
# ============================================================================
def construir_racimo():
    placa = Pos(0, 61.5, 118) * Rot(X=-90) * (Cylinder(16, 5) - Cylinder(3.75, 7))
    racimo = placa
    for i in range(6):
        a = i * math.pi / 3
        racimo = racimo + Pos(10 * math.sin(a), 99, 118 + 10 * math.cos(a)) * \
            Rot(X=-90) * Cylinder(3.5, 70)
    boca = Pos(0, 138, 118) * Rot(X=-90) * (Cylinder(14, 8) - Cylinder(3.75, 10))
    for i in range(6):
        a = i * math.pi / 3
        boca = boca - Pos(10 * math.sin(a), 140, 118 + 10 * math.cos(a)) * \
            Rot(X=-90) * Cylinder(2.5, 5)
    racimo = racimo + boca
    PIEZAS["racimo"] = racimo
    add(racimo, COL["gunmetal"], "plastico", "Racimo gatling", loc=pose_tilt,
        pieza="racimo")
    # anillo ámbar decorativo del freno de boca
    add(Pos(0, 142.5, 118) * Rot(X=-90) * (Cylinder(14.2, 1.6) - Cylinder(12.5, 3)),
        COL["ambar"], "emisivo", "anillo_boca", loc=pose_tilt, pieza="racimo")


# ============================================================================
# COMPONENTES REALES (no se imprimen: van alojados)
# ============================================================================
def componentes_base():
    # 28BYJ-48 colgado del techo (z 47): brida arriba, cuerpo abajo, eje arriba
    add(Pos(0, 0, 37.5) * Cylinder(14, 19), COL["acero"], "metal", "28BYJ-48")
    fl = Box(35, 7, 1) + Pos(17.5, 0, 0) * Cylinder(3.5, 1) + Pos(-17.5, 0, 0) * Cylinder(3.5, 1)
    add(Pos(0, 0, 46.4) * fl, COL["acero"], "metal", "28BYJ-48 brida")
    add(Pos(0, 0, 52) * Cylinder(2.5, 11), COL["alu"], "metal", "28BYJ-48 eje")
    add(Pos(0, 15.5, 38) * Box(14.6, 6, 16.5), COL["servo"], "plastico", "28BYJ-48 cables")

    # ESP32 + ULN2003 sobre los bosses de la tapa
    esp = Pos(-22, -16, 8.6)
    add(esp * Box(27.9, 54.4, 1.6), COL["pcb_esp"], "pcb", "ESP32 DevKit")
    add(esp * Pos(0, -12, 2.3) * Box(18, 25.5, 3.1), COL["acero"], "metal", "WROOM-32")
    add(esp * Pos(0, 24.5, 1.6) * Box(8, 6, 3), COL["acero"], "metal", "microUSB")
    uln = Pos(24, -20, 8.6)
    add(uln * Box(35, 27, 1.6), COL["pcb_verde"], "pcb", "ULN2003")
    add(uln * Pos(-6, 0, 2.8) * Box(7, 19, 4), COL["chip"], "plastico", "ULN2003 IC")

    # LCD detrás de la ventana de la consola
    cara = Pos(0, 56.5, 62) * Rot(X=-35)
    add(cara * Pos(0, 0, -4) * Box(80, 36, 1.6), COL["pcb_verde"], "pcb", "LCD 1602 PCB")
    add(cara * Pos(0, 0, -1.8) * Box(71.2, 26.5, 5), COL["chip"], "plastico", "LCD bezel")
    add(cara * Pos(0, 0, 0.6) * Box(64.5, 16, 1), COL["lcd"], "emisivo", "LCD pantalla")

    # DHT22 frente a la ventilación trasera / buzzer tras su rejilla
    add(Pos(0, -62, 28) * Box(15.1, 7.7, 25.1), COL["dht"], "plastico", "DHT22")
    add(Pos(-61, -10, 26) * Rot(Y=90) * Cylinder(6, 9.5), COL["chip"], "plastico", "Buzzer")

    # Joystick en su funda lateral (módulo 34x26 + palanca)
    joy = Pos(76, -6, 20)
    add(joy * Box(7, 26, 32), COL["pcb_rojo"], "pcb", "Joystick PCB")
    add(joy * Pos(5.5, 0, 6) * Rot(Y=90) * Cylinder(9, 6), COL["chip"], "plastico", "Joystick domo")
    add(joy * Pos(11, 0, 6) * Rot(Y=90) * Cylinder(1.8, 8), COL["chip"], "plastico", "Joystick palanca")
    add(joy * Pos(16, 0, 6) * Sphere(5), COL["panel"], "plastico", "Joystick perilla")


def componentes_pan():
    # SG90 real cruzando el brazo derecho (aletas contra la cara externa x=33)
    sg_loc = pose_pan * Pos(33 + 16.4, 45.35, 118) * Rot(Y=-90)
    add(Pos(0.55, 0, 11.35) * Box(22.5, 11.8, 22.7), COL["servo"], "plastico", "SG90", loc=sg_loc)
    add(Pos(0.55, 0, 17.65) * Box(32.2, 11.8, 2.5), COL["servo"], "plastico", "SG90 aletas", loc=sg_loc)
    add(Pos(0, 0, 24.7) * Cylinder(5.9, 4), COL["servo"], "plastico", "SG90 tapa", loc=sg_loc)
    add(Pos(0, 0, 28.3) * Cylinder(2.3, 3.2), COL["crema"], "plastico", "SG90 eje", loc=sg_loc)
    add(Pos(0, -7, 30.1) * Box(4.5, 16, 1.6), COL["crema"], "plastico", "SG90 horn", loc=sg_loc)
    # bulón M5 del pivote izquierdo
    add(Pos(-34.5, 40, 118) * Rot(Y=90) * Cylinder(4.5, 3), COL["alu"], "metal",
        "M5 cabeza", loc=pose_pan)


def componentes_tilt():
    # KY-008 en sus rieles internos, tubo asomando al canal del cañón
    ky = Pos(0, 50, 109.2)
    add(Box(15.2, 18.5, 1.6), COL["pcb_rojo"], "pcb", "KY-008", loc=pose_tilt * ky)
    add(Rot(X=-90) * Cylinder(3.25, 10.5), COL["laton"], "metal", "KY-008 tubo",
        loc=pose_tilt * ky * Pos(0, 11, 8.8))
    # GY-521 sobre su boss interno
    add(Pos(-12, 38, 107) * Box(16.4, 21.2, 1.6), COL["pcb_viol"], "pcb", "GY-521",
        loc=pose_tilt)
    # HC-SR04 en la mentonera (PCB vertical, transductores en los agujeros)
    us = Pos(0, 55, 90)
    add(Box(45, 1.6, 20), COL["pcb_azul"], "pcb", "HC-SR04 PCB", loc=pose_tilt * us)
    for sx in (-1, 1):
        add(Rot(X=-90) * Cylinder(8, 12), COL["acero"], "metal", "HC-SR04 transductor",
            loc=pose_tilt * us * Pos(13 * sx, 6.9, 0))
        add(Rot(X=-90) * Cylinder(6.9, 0.8), COL["malla"], "plastico", "HC-SR04 malla",
            loc=pose_tilt * us * Pos(13 * sx, 13.2, 0))
    # lente de salida del láser en la boca
    add(Pos(0, 143.6, 118) * Rot(X=-90) * Cylinder(2.4, 1.4), COL["lente"], "vidrio",
        "laser salida", loc=pose_tilt)
    # webcam Gadnic WEBL56: caja genérica sobre la bandeja (medir la real)
    cam = Pos(0, 42, 147.5)
    add(Box(60, 30, 9.5), COL["chip"], "plastico", "Webcam (generica)", loc=pose_tilt * cam)
    add(Rot(X=-90) * Cylinder(7, 4), COL["panel"], "plastico", "Webcam barril",
        loc=pose_tilt * cam * Pos(0, 16.5, 0))
    add(Rot(X=-90) * Cylinder(4.5, 1.2), COL["lente"], "vidrio", "Webcam lente",
        loc=pose_tilt * cam * Pos(0, 19, 0))


# ================================ RENDER ====================================
def render(parts, out_png, *, views=None, hero_dir=None, zoom=1.05, clip=None,
           win=(1400, 1050)):
    meshes = []
    for p in parts:
        m = to_mesh(p["solid"], 0.12)
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
    """Piezas separadas en vertical (los componentes acompañan a su pieza)."""
    offsets = {"tapa": (0, 0, -55), "base": (0, 0, 0),
               "tambor_cuerpo": (0, 0, 70), "mantelete": (0, 30, 150),
               "racimo": (0, 95, 150), None: (0, 0, 0)}
    sueltos = []
    for p in PARTS:
        off = offsets.get(p["pieza"], (0, 0, 0))
        sueltos.append(dict(p, solid=Pos(*off) * p["solid"]))
    return render(sueltos, out_png, hero_dir=(1.0, 1.3, 0.35), zoom=0.95,
                  win=(1200, 1500))


# ================================= MAIN =====================================
def main():
    construir_base()
    construir_tapa()
    construir_tambor_cuerpo()
    construir_mantelete()
    construir_racimo()
    componentes_base()
    componentes_pan()
    componentes_tilt()
    print(f"sólidos en escena: {len(PARTS)}")

    comp = Compound(children=[p["solid"] for p in PARTS])
    bb = comp.bounding_box()
    print(f"bbox total: {bb.size.X:.0f} x {bb.size.Y:.0f} x {bb.size.Z:.0f} mm")
    for nombre, s in PIEZAS.items():
        if not hasattr(s, "volume"):
            s = Compound(children=list(s))
            PIEZAS[nombre] = s
        v = s.volume / 1000
        b = s.bounding_box()
        print(f"  pieza {nombre:14s} {v:7.1f} cm3   {b.size.X:5.0f} x {b.size.Y:5.0f} x {b.size.Z:5.0f} mm")

    render(PARTS, OUT / "v3_views.png",
           views={"3/4 frente": (1.0, 1.2, 0.55), "lateral": (1.0, 0.05, 0.15),
                  "frente": (0.05, 1.0, 0.12), "picado": (0.8, 0.8, 1.2)})
    render(PARTS, OUT / "v3_hero.png", hero_dir=(1.0, 1.35, 0.42))
    render(PARTS, OUT / "v3_corte.png", hero_dir=(1.0, 0.9, 0.35),
           clip=("x", (0.01, 0, 0)))
    render_explotado(OUT / "v3_explotado.png")
    print("renders ok")

    # exportes
    children = []
    for i, p in enumerate(PARTS):
        solids = p["solid"].solids() if hasattr(p["solid"], "solids") else [p["solid"]]
        c = Compound(children=list(solids))
        c.color = Color(p["color"])
        c.label = f"{p['name']}_{i}"
        children.append(c)
    export_gltf(Compound(children=children), str(OUT / "torreta_v3.glb"), binary=True)
    export_step(Compound(children=children), str(OUT / "torreta_v3.step"))
    pdir = OUT / "parts_v3"
    pdir.mkdir(exist_ok=True)
    for nombre, s in PIEZAS.items():
        export_stl(s, str(pdir / f"{nombre}.stl"), tolerance=0.08, angular_tolerance=0.2)
    print("export ok:", OUT / "torreta_v3.glb", "+", pdir)


if __name__ == "__main__":
    main()

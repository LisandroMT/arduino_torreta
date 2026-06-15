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
cfg.base.leg_length_mm = 35           # patas más cortas: estorban menos a la tapa
cfg.base.leg_thickness_mm = 10
cfg.base.leg_root_width_mm = 22       # y más angostas
cfg.base.leg_tip_width_mm = 18
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


# El OLED SSD1306 0.96" se monta en la CARA TRASERA del cuerpo blindado (que
# gira en pan): es la superficie grande y visible de atrás, hueca por dentro
# para canalizar los cables del bus I2C hacia la base. Se atornilla por sus 4
# agujeros M2 a postes-separadores (patrón ~23.5 x 23.5 mm), sin agregar carcasa.
# Coordenadas en el marco del cuerpo (cara trasera en X = -35), z a la altura
# del pivote para que el operador lo lea de frente.
X_BODY_BACK = -35
OLED_Z = 96       # altura del centro del OLED en la cara trasera

# --- cámara Gadnic CAMWEB11: cilindro de pivote (sin el clip) ---
CAM_BUJE_L = 15.0   # largo del cilindro de pivote, MEDIDO sobre la cámara real
CAM_HOLG   = 0.8    # holgura total para que el cilindro entre y pivote libre


# ============================================================================
# PIEZA: BASE (esculpida de Fase 1 + cirugía funcional)
# ============================================================================
def construir_base():
    partes = p_base.build(cfg)                       # [(solid, rol)] esculpido
    estructura = _fuse([p for p in partes if p[1] == "body"])

    # --- cámara interna ABIERTA POR ABAJO: la electrónica se accede quitando
    #     la tapa inferior. La base queda como un "vaso" invertido (paredes +
    #     techo), con un rebaje donde encastra la tapa y un tope donde apoya. ---
    # radios CIRCUNSCRITOS (la base tiene circunradio ~86.6); paredes ~11 mm
    R_CAM = 74.0                 # cámara interna (deja pared ~12 mm a la base)
    R_REB = 80.0                 # rebaje de encastre de la tapa (escalón de 6 mm)
    R_TORN = 70.0                # radio de los tornillos de la tapa (en la pared)
    Z_TECHO = 38.0               # cara inferior del techo (queda techo 38..42)
    Z_TOPE = 5.0                 # altura del tope donde apoya la tapa
    # cámara (de Z_TOPE hasta el techo)
    estructura -= Pos(0, 0, Z_TOPE) * extrude(RegularPolygon(R_CAM, 6), Z_TECHO - Z_TOPE)
    # rebaje inferior más ancho (de -1 a Z_TOPE): deja un escalón-tope en Z_TOPE
    estructura -= Pos(0, 0, -1) * extrude(RegularPolygon(R_REB, 6), Z_TOPE + 1)
    # montaje del 28BYJ-48 colgado del TECHO (eje Ø7.2 pasa al cuerpo, M4 brida)
    estructura -= Pos(0, 0, Z_TECHO) * Cylinder(radius=3.6, height=10)
    for sx in (-1, 1):
        estructura -= Pos(0, 17.5 * sx, Z_TECHO) * Cylinder(radius=2.15, height=10)
    # 3 bosses de tornillo para la tapa, pegados a la pared de la cámara
    # (a 90/210/330°, entre las patas para acceder al atornillar desde abajo)
    for ang in (90, 210, 330):
        a = math.radians(ang)
        estructura += Pos(R_TORN * math.cos(a), R_TORN * math.sin(a), Z_TOPE / 2 + 1) * \
            Cylinder(radius=4.5, height=Z_TOPE + 2)
        estructura -= Pos(R_TORN * math.cos(a), R_TORN * math.sin(a), 0) * \
            Cylinder(radius=PILOTO / 2, height=Z_TOPE + 4)
    # RANURA ARQUEADA pasacables (cable management de plataforma giratoria):
    # un semi-anillo concéntrico al eje por donde el cable del cuerpo se DESLIZA
    # al girar el azimut, sin pellizcarse. Cubre el semicírculo x<0 (~180° de
    # giro); el semicírculo x>0 queda sólido y hace de puente techo↔centro.
    # Anillo r6..14 (NO llega a los M4 a r17.5, que quedan en el anillo sólido
    # exterior → el agarre del motor no se debilita). Arco de 270°: el cable se
    # desliza por aquí en TODO el rango de giro de ±90° sin pellizcarse.
    from build123d import Polygon as _Poly
    anillo = Pos(0, 0, Z_TECHO) * Cylinder(radius=14, height=14) - \
        Pos(0, 0, Z_TECHO) * Cylinder(radius=6, height=16)
    # puente sólido de 90° en +X (sector ±45°): conecta el centro (que guía el
    # eje) con el techo exterior y mantiene todo como un solo sólido
    puente = Pos(0, 0, Z_TECHO) * extrude(_Poly((0, 0), (120, 120), (120, -120),
                                                 align=None), 16)
    estructura -= (anillo - puente)
    # (el OLED ya NO va en la base — se montó en la cara trasera de la cuna)
    # funda del joystick KY-023 (PCB real 39.4 x 27.6, palanca saliendo radial)
    # el lado de 39.4 va tangencial (Y local), 27.6 en altura (Z); pocket abierto al exterior
    funda = Rot(0, 0, 90) * Pos(76, 0, 21) * Box(14, 46, 36)
    funda -= Rot(0, 0, 90) * Pos(78, 0, 21) * Box(14, 40 + HOLGURA, 30 + HOLGURA)
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
    # (los chevrones amarillos de la base se quitaron por pedido)


def construir_tapa():
    # placa que ENCASTRA en el rebaje inferior de la base (R_REB=80, holgura 0.5)
    # y apoya contra el tope a Z_TOPE=5. Espesor 4 mm (z0..4).
    R_TORN = 70.0
    tapa = extrude(RegularPolygon(79.5, 6), 4)
    # muescas que COPIAN la forma de las patas (en 60/180/300°, donde el trípode
    # invade el área de la tapa) para que la tapa encaje alrededor de las patas
    # sin chocar al montarla. Ancho = pata (22) + holgura; radial de r38 hacia afuera.
    for ang in (60, 180, 300):
        a = math.radians(ang)
        tapa -= Pos(64 * math.cos(a), 64 * math.sin(a), 2) * Rot(0, 0, ang) * \
            Box(42, 24, 12)              # cubre la pata (r45..80) con holgura
    # orejas de tornillo que coinciden con los 3 bosses de la base (90/210/330°)
    for ang in (90, 210, 330):
        a = math.radians(ang)
        tapa += Pos(R_TORN * math.cos(a), R_TORN * math.sin(a), 2) * Cylinder(radius=5, height=4)
        tapa -= Pos(R_TORN * math.cos(a), R_TORN * math.sin(a), 0) * \
            Cylinder(radius=1.7, height=8)            # paso del tornillo M3
        tapa -= Pos(R_TORN * math.cos(a), R_TORN * math.sin(a), 0) * \
            Cylinder(radius=3.4, height=2.4)          # avellanado de la cabeza
    # bosses de la electrónica (ESP32 y ULN2003) hacia ARRIBA (a la cámara)
    for cx, cy, dx, dy in ((-18, -14, 48, 23), (20, -20, 35, 27)):
        for sx in (-1, 1):
            for sy in (-1, 1):
                b = Pos(cx + sx * dx / 2, cy + sy * dy / 2, 6.25) * Cylinder(radius=3, height=4.5)
                b -= Pos(cx + sx * dx / 2, cy + sy * dy / 2, 6.5) * Cylinder(radius=PILOTO / 2, height=5)
                tapa += b
    PIEZAS["tapa"] = tapa
    add(tapa, COL["panel"], "plastico", "Tapa inferior porta-electronica", pieza="tapa")


# ============================================================================
# PIEZA: CUERPO (esculpido de Fase 1 + D-hub + hueco + servo)
# ============================================================================
def construir_cuerpo():
    partes = p_body.build(cfg)
    cuerpo = _fuse([p for p in partes if p[1] == "body"])

    # eje impreso -> muñón-rodamiento: agujero en D para el eje del stepper
    d_hole = (Cylinder(radius=(5 + 0.15) / 2, height=16) &
              Box(7, 3 + 0.15, 16))
    cuerpo -= Pos(0, 0, 44) * d_hole          # z36..52: recibe el eje del motor (z38..48)

    # ahuecado del tambor: el hueco TERMINA en z62, dejando macizo el tope del
    # tambor (z62..65). El vaciado de la cuña arranca recién en z74. Entre z62 y
    # z74 queda un BLOQUE SÓLIDO de Ø60 que une firmemente el tambor giratorio
    # con el cuerpo (transmite el torque del azimut sin pestañas frágiles).
    cuerpo -= Pos(0, 0, 55) * Cylinder(radius=23, height=14)            # tambor hueco z48..62
    from build123d import Plane, Polygon
    z0 = 42 + cfg.neck.drum_height_mm                                   # 64
    inner = Plane.XZ * Polygon((-31, z0 + 10), (29, z0 + 10), (29, z0 + 50),
                               (-31, z0 + 74), align=None)              # vaciado cuña desde z74
    cuerpo -= Pos(0, 32, 0) * extrude(inner, amount=64)
    # pasacables: CERCA DEL EJE (r=10) para minimizar el barrido del cable al
    # girar (evita el efecto guillotina) y alinear con la ranura r6..14 de la base.
    cuerpo -= Pos(-10, 0, 58) * Box(10, 8, 40)                         # z38..78, angosto p/ giro ±90°
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

    # ---- montaje EMBUTIDO del OLED en la cara trasera del cuerpo (-X) ----
    # El display se coloca DESDE ADENTRO: la pantalla asoma por una ventana
    # pasante de su tamaño (35x23) y el PCB + el "agarre" + los cables quedan
    # ocultos dentro del cuerpo. 4 bosses internos (patrón 30x28, centro a
    # centro) con piloto M2 lo fijan por dentro; no hay tornillos a la vista.
    OLED_VENT_Y, OLED_VENT_Z = 35.0, 23.0       # ventana = pantalla visible
    OLED_HOLE_Y, OLED_HOLE_Z = 30.0, 28.0       # patrón de agujeros (centro a centro)
    cuerpo -= Pos(X_BODY_BACK, 0, OLED_Z) * Box(16, OLED_VENT_Y, OLED_VENT_Z)
    for sy in (-1, 1):
        for sz in (-1, 1):
            yc = OLED_HOLE_Y / 2 * sy
            zc = OLED_Z + OLED_HOLE_Z / 2 * sz
            boss = Pos(X_BODY_BACK + 4, yc, zc) * Rot(0, 90, 0) * Cylinder(radius=2.6, height=8)
            boss -= Pos(X_BODY_BACK + 7, yc, zc) * Rot(0, 90, 0) * Cylinder(radius=0.9, height=8)
            cuerpo += boss

    PIEZAS["cuerpo"] = cuerpo
    add(cuerpo, COL["cuerpo"], "plastico", "Cuerpo blindado (hueco)",
        loc=loc_pan, pieza="cuerpo")
    # (se quitaron los acentos decorativos del cuerpo —franjas y caja de
    #  munición de Fase 1—: al ahuecar el cuerpo quedaban metidos dentro del
    #  hueco como tabiques amarillos sin función)


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
    # (se quitaron las ranuras térmicas decorativas: eran surcos externos de
    # ~0.8 mm que un chequeador de espesor marca como pared fina —aunque debajo
    # hay ~3 mm—. Sin ellas el tubo queda liso con pared pareja de 3.5 mm.)
    freno = Pos(128, 0, 0) * eje * Cylinder(radius=12, height=18)
    for sy in (-1, 1):                            # venteos laterales del freno
        freno -= Pos(128, 9 * sy, 0) * Box(10, 6, 5)
    arma += freno
    # interior: conducto Ø13 hasta la boca, salida Ø7.4 (el KY-008 —tubo Ø6.5—
    # entra por la cuna y queda alojado en la punta, con la lente asomando).
    # Ø13 (antes Ø17) deja pared de tubo ~3.5 mm (antes 1.5, y 0.7 en las ranuras)
    arma -= Pos(75, 0, 0) * eje * Cylinder(radius=6.5, height=120)
    arma -= Pos(135.2, 0, 0) * eje * Cylinder(radius=3.7, height=6)

    # ---- cuna hueca (pocket de cables + GY-521) ----
    arma -= Pos(0, 0, -6) * Box(30, 40, 30)
    gy_boss = Pos(-6, 0, -19) * Box(24, 20, 4)
    for dy in (-7.5, 7.5):                  # MPU6050: agujeros a 15 mm centro a centro
        gy_boss -= Pos(-6, dy, -18.5) * Cylinder(radius=PILOTO / 2, height=5)
    arma += gy_boss
    # ventana trasera de la cuna (cara -X): alivia peso y da acceso al MPU6050.
    # Deja marco perimetral (~10 mm a los lados, ~5 mm abajo, ~4 arriba) y NO
    # toca el boss del MPU (z<-16) ni las paredes laterales que llegan al pivote.
    arma -= Pos(-17, 0, -3.5) * Box(12, 32, 19)

    # ---- mentonera del HC-SR04, colgada de la cuna por cartelas + espina ----
    menton = Pos(29, 0, -33) * Box(3, 52, 26)
    for sy in (-1, 1):
        menton -= Pos(29, 13 * sy, -35) * eje * Cylinder(radius=8.3, height=6)
        # cartelas: suben hasta solapar el bloque de la cuna (z -19..-12)
        menton += Pos(20.5, 24 * sy, -27) * Box(17, 2, 30)
    # espina central: une la placa con la recámara del cañón
    menton += Pos(25, 0, -16) * Box(8, 10, 12)
    arma += menton

    # ---- montaje de la cámara: 2 pestañas (horquilla) sobre el cañón ----
    # La webcam Gadnic CAMWEB11, sin su clip, deja una oreja/cilindro de pivote
    # de CAM_BUJE_L mm de largo con un agujero (medido sobre la cámara real).
    # Estas 2 pestañas reemplazan el clip: abrazan ese cilindro y un tornillo M3
    # pasante lo fija permitiendo ajustar la inclinación (agarre móvil). Coaxial
    # con el cañón; sin bandeja que choque al elevar.
    PEST_ESP = 3.0                              # espesor de cada pestaña
    sy_pest = (CAM_BUJE_L + CAM_HOLG) / 2 + PEST_ESP / 2   # centro de cada pestaña
    R_PEST = 7.0                                # radio del lomo redondeado (= medio ancho)
    for sy in (-1, 1):
        yc = sy_pest * sy
        # tramo recto desde el cañón hasta el eje del tornillo (z10..28) ...
        oreja = Pos(16, yc, 19) * Box(2 * R_PEST, PEST_ESP, 18)
        # ... rematado por un lomo SEMICIRCULAR centrado en el agujero (z28),
        # para que la pestaña deje de ser una placa rectangular
        oreja += Pos(16, yc, 28) * Rot(90, 0, 0) * Cylinder(radius=R_PEST, height=PEST_ESP)
        oreja -= Pos(16, yc, 28) * Rot(90, 0, 0) * Cylinder(radius=1.7, height=PEST_ESP + 6)
        arma += oreja

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
    # 28BYJ-48: el EJE va en r=0 (eje de giro de la torreta), pero el CUERPO Ø28
    # está DESPLAZADO 8 mm del eje (el eje no está en el centro del cuerpo).
    # La brida (2 M4 a 35 mm) se atornilla bajo el techo (z38); el cuerpo cuelga
    # en la cavidad; el eje sube y encastra en el agujero en D del cuerpo (z38..48).
    add(Pos(-8, 0, 28.5) * Cylinder(radius=14, height=19), COL["acero"], "metal", "28BYJ-48")      # cuerpo z19..38, descentrado
    add(Pos(0, 0, 37.4) * Box(8, 35, 1.2), COL["acero"], "metal", "28BYJ-48 brida")                 # brida con M4 a ±17.5
    add(Pos(0, 0, 43) * Cylinder(radius=2.5, height=10), COL["alu"], "metal", "28BYJ-48 eje")        # eje r=0, z38..48
    add(Pos(-20, 14, 28) * Box(14.6, 6, 16.5), COL["servo"], "plastico", "28BYJ-48 cables")          # cables del lado del cuerpo
    esp = Pos(-18, -14, 8.6)
    add(esp * Box(27.9, 54.4, 1.6), COL["pcb_esp"], "pcb", "ESP32 DevKit")
    add(esp * Pos(0, -12, 2.3) * Box(18, 25.5, 3.1), COL["acero"], "metal", "WROOM-32")
    uln = Pos(20, -20, 8.6)
    add(uln * Box(35, 27, 1.6), COL["pcb_verde"], "pcb", "ULN2003")
    add(uln * Pos(-6, 0, 2.8) * Box(7, 19, 4), COL["chip"], "plastico", "ULN2003 IC")
    # (el OLED se montó en el tilt, ver --- cañón / cuna --- más abajo)
    # DHT22 / buzzer / joystick
    add(Rot(0, 0, 330) * Pos(66, 0, 22) * Box(7.7, 15.1, 25.1), COL["dht"],
        "plastico", "DHT22")
    add(Rot(0, 0, 30) * Pos(66, 0, 22) * Rot(0, 90, 0) * Cylinder(radius=6, height=9.5),
        COL["chip"], "plastico", "Buzzer")
    # KY-023 real: PCB 39.4 x 27.6, palanca saliendo en +X local (radial)
    joy = Rot(0, 0, 90) * Pos(79.5, 0, 21)
    add(joy * Box(8, 39, 27), COL["pcb_rojo"], "pcb", "Joystick PCB")
    add(joy * Pos(7, 0, 0) * Rot(0, 90, 0) * Cylinder(radius=9, height=6),
        COL["chip"], "plastico", "Joystick domo")
    add(joy * Pos(13, 0, 0) * Rot(0, 90, 0) * Cylinder(radius=1.8, height=8),
        COL["chip"], "plastico", "Joystick palanca")
    # --- cuerpo (pan) ---
    # eje de salida hacia ADENTRO (-Y, engrana la cuna); cuerpo hacia afuera
    y_ear = cfg.body.ear_gap_mm / 2 + cfg.body.ear_thickness_mm / 2
    sg = loc_pan * Pos(PX, y_ear + 23.5, PZ) * Rot(90, 0, 0) * Rot(0, 0, 90)
    add(Pos(0.55, 0, 11.35) * Box(22.5, 11.8, 22.7), COL["servo"], "plastico", "SG90", loc=sg)
    add(Pos(0.55, 0, 17.65) * Box(32.2, 11.8, 2.5), COL["servo"], "plastico", "SG90 aletas", loc=sg)
    add(Pos(0, 0, 24.7) * Cylinder(radius=5.9, height=4), COL["servo"], "plastico", "SG90 tapa", loc=sg)
    add(Pos(0, 0, 28.5) * Cylinder(radius=2.3, height=4), COL["crema"], "plastico", "SG90 eje", loc=sg)
    add(Pos(0, 0, 30.8) * Cylinder(radius=7, height=1.6), COL["crema"], "plastico", "SG90 horn", loc=sg)
    add(loc_pan * Pos(PX, -(cfg.body.ear_gap_mm / 2 + cfg.body.ear_thickness_mm + 1.5), PZ) *
        Rot(90, 0, 0) * Cylinder(radius=4.5, height=3), COL["alu"], "metal", "M5 cabeza")
    # OLED EMBUTIDO desde adentro: el PCB (con el "agarre") queda DENTRO del
    # cuerpo, atornillado a los 4 bosses; la pantalla asoma por la ventana de la
    # cara trasera (-X) quedando al ras. Los cables salen del PCB hacia adentro.
    add(loc_pan * Pos(X_BODY_BACK + 6, 0, OLED_Z) * Box(1.6, 38, 34), COL["pcb_azul"], "pcb", "OLED PCB")
    add(loc_pan * Pos(X_BODY_BACK + 1.5, 0, OLED_Z) * Box(3, 35, 23), COL["chip"], "plastico", "OLED vidrio")
    add(loc_pan * Pos(X_BODY_BACK - 0.2, 0, OLED_Z) * Box(0.6, 33, 21), COL["lcd"], "emisivo", "OLED pantalla")
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
    # Webcam Gadnic CAMWEB11: cilindro de pivote (CAM_BUJE_L de largo) en Y,
    # abrazado por las 2 pestañas; cuerpo con la lente mirando a +X (coaxial).
    add(Pos(16, 0, 28) * Rot(90, 0, 0) * Cylinder(radius=4, height=CAM_BUJE_L),
        COL["chip"], "plastico", "Webcam buje", loc=loc_gun)
    add(Pos(16, 0, 40) * Box(30, 28, 16), COL["chip"], "plastico", "Webcam cuerpo",
        loc=loc_gun)
    add(Pos(32, 0, 40) * eje * Cylinder(radius=6.5, height=8), COL["panel"],
        "plastico", "Webcam barril", loc=loc_gun)
    add(Pos(37, 0, 40) * eje * Cylinder(radius=4.5, height=1.2), COL["lente"],
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

    # Mapeo componente -> pieza con la que se mueve (pan/tilt). Un PART es
    # ESTRUCTURA imprimible si tiene p["pieza"] seteado; es COMPONENTE
    # (electrónica/mecánica alojada) si p["pieza"] es None.
    COMP2PIEZA = [("28BYJ", "base"), ("ESP32", "tapa"), ("WROOM", "tapa"),
                  ("ULN2003", "tapa"), ("OLED", "cuerpo"), ("DHT22", "base"),
                  ("Buzzer", "base"), ("Joystick", "base"), ("SG90", "cuerpo"),
                  ("M5", "cuerpo"), ("KY-008", "canon_cuna"), ("GY-521", "canon_cuna"),
                  ("HC-SR04", "canon_cuna"), ("Webcam", "canon_cuna")]
    # grupos[pieza][tipo] -> lista de Compound. tipo: "estructura" | "componentes"
    grupos = {pz: {"estructura": [], "componentes": []}
              for pz in ("base", "tapa", "cuerpo", "canon_cuna")}
    for i, p in enumerate(PARTS):
        solids = p["solid"].solids() if hasattr(p["solid"], "solids") else [p["solid"]]
        c = Compound(children=list(solids))
        c.color = Color(p["color"])
        es_componente = p["pieza"] is None
        pieza = p["pieza"] or next((pz for pref, pz in COMP2PIEZA
                                    if p["name"].startswith(pref)), "base")
        tipo = "componentes" if es_componente else "estructura"
        c.label = f"{p['name']}_{i}"     # nombre legible de cada sólido en Fusion
        grupos[pieza][tipo].append(c)
    children = [c for pz in grupos.values() for cs in pz.values() for c in cs]
    export_gltf(Compound(children=children), str(OUT / "torreta_fase2.glb"), binary=True)

    # STEP con JERARQUÍA NOMBRADA (Fusion la lee como componentes agrupados):
    #   Torreta_fase2 → <Pieza> → estructura / electronica → <sólidos nombrados>
    NOMBRE = {"base": "Base", "tapa": "Tapa_porta_electronica",
              "cuerpo": "Cuerpo_pan", "canon_cuna": "Canon_cuna_tilt"}
    SUBNOMBRE = {"estructura": "estructura_imprimible", "componentes": "electronica"}
    ramas = []
    for pz, tipos in grupos.items():
        sub = []
        for tipo, cs in tipos.items():
            if not cs:
                continue
            g = Compound(children=cs)
            g.label = SUBNOMBRE[tipo]
            sub.append(g)
        rama = Compound(children=sub)
        rama.label = NOMBRE[pz]
        ramas.append(rama)
    arbol = Compound(children=ramas)
    arbol.label = "Torreta_fase2"
    export_step(arbol, str(OUT / "torreta_fase2.step"))
    # GLB por (pieza × tipo): el visor los agrupa por pieza para explotar/articular
    # y por tipo para el toggle "solo maqueta" (oculta los *_componentes).
    # (el writer de OCCT descarta los nombres de nodo → el agrupado va por archivo)
    for g, tipos in grupos.items():
        for tipo, cs in tipos.items():
            if cs:
                export_gltf(Compound(children=cs),
                            str(OUT / f"fase2_{g}_{tipo}.glb"), binary=True)
    pdir = OUT / "parts_fase2"
    pdir.mkdir(exist_ok=True)
    for nombre, s in PIEZAS.items():
        export_stl(s, str(pdir / f"{nombre}.stl"), tolerance=0.08, angular_tolerance=0.2)
    print("export ok:", OUT / "torreta_fase2.glb", "+", pdir)


if __name__ == "__main__":
    main()

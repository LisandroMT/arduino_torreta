"""Render fotorrealista (Cycles) de la torreta v2 — foto de producto.

Importa outputs/torreta_v2.glb, reasigna materiales PBR físicos por nombre de
pieza, monta un estudio (piso glossy + softboxes key/fill/rim) y renderiza con
path tracing + denoise + AgX.

Requiere el módulo `bpy` (Blender headless), instalado aparte del venv CAD:
    uv venv /tmp/blender_env --python 3.11
    uv pip install --python /tmp/blender_env/bin/python bpy
Uso:
    /tmp/blender_env/bin/python render_foto_v2.py --shot hero
    /tmp/blender_env/bin/python render_foto_v2.py --shot detalle
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import bpy

HERE = Path(__file__).parent
GLB = HERE / "outputs" / "torreta_v2.glb"


# ------------------------------ utilidades ----------------------------------
def srgb_to_linear(hexcolor: str):
    c = [int(hexcolor.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c) + (1.0,)


def make_material(name, *, color, rough=0.5, metal=0.0, coat=0.0, coat_rough=0.15,
                  emission=0.0, transmission=0.0, bevel=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes["Principled BSDF"]
    rgba = srgb_to_linear(color)
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if coat:
        bsdf.inputs["Coat Weight"].default_value = coat
        bsdf.inputs["Coat Roughness"].default_value = coat_rough
    if emission:
        bsdf.inputs["Emission Color"].default_value = rgba
        bsdf.inputs["Emission Strength"].default_value = emission
    if transmission:
        bsdf.inputs["Transmission Weight"].default_value = transmission
        bsdf.inputs["IOR"].default_value = 1.45
    if bevel:  # micro-bisel en aristas: realismo de pieza física
        bev = m.node_tree.nodes.new("ShaderNodeBevel")
        bev.samples = 4
        bev.inputs["Radius"].default_value = 0.0006
        m.node_tree.links.new(bev.outputs["Normal"], bsdf.inputs["Normal"])
    return m


# ----------------------- catálogo de materiales -----------------------------
def build_materials():
    return {
        "graphite": make_material("petg_grafito", color="#2B3036", rough=0.4,
                                  coat=0.35, coat_rough=0.18, bevel=True),
        "panel":    make_material("plastico_oscuro", color="#21252A", rough=0.5,
                                  coat=0.15, bevel=True),
        "alu":      make_material("aluminio", color="#DADEE2", rough=0.3,
                                  metal=1.0, bevel=True),
        "steel":    make_material("acero", color="#C8CDD2", rough=0.22,
                                  metal=1.0, bevel=True),
        "amber":    make_material("ambar", color="#FFB547", rough=0.28,
                                  coat=0.5, coat_rough=0.1),
        "amber_led": make_material("led_ambar", color="#FFB547", emission=6.0),
        "lcd":      make_material("lcd_verde", color="#9AD65A", emission=2.5),
        "pcb_blue": make_material("pcb_azul", color="#1660A8", rough=0.5, coat=0.5, coat_rough=0.12),
        "pcb_green": make_material("pcb_verde", color="#1F6B34", rough=0.5, coat=0.5, coat_rough=0.12),
        "pcb_red":  make_material("pcb_rojo", color="#A4252B", rough=0.5, coat=0.5, coat_rough=0.12),
        "pcb_prpl": make_material("pcb_violeta", color="#5435A0", rough=0.5, coat=0.5, coat_rough=0.12),
        "pcb_dark": make_material("pcb_esp32", color="#15314F", rough=0.5, coat=0.5, coat_rough=0.12),
        "brass":    make_material("laton", color="#C9A44A", rough=0.28, metal=1.0, bevel=True),
        "lens":     make_material("optica", color="#10151B", rough=0.06,
                                  transmission=0.85, coat=1.0, coat_rough=0.05),
        "servo":    make_material("servo_azul", color="#2A6FD6", rough=0.45, coat=0.2),
        "cream":    make_material("nylon_crema", color="#E8E4D8", rough=0.55),
        "white":    make_material("conector_blanco", color="#EDEDED", rough=0.5),
        "chip":     make_material("negro_anodizado", color="#16191D", rough=0.35,
                                  metal=0.25, coat=0.3, bevel=True),
        "mesh":     make_material("malla", color="#3C4146", rough=0.8),
    }


# prefijo de nombre de pieza -> material (el más largo gana)
NAME2MAT = [
    ("placa_inferior", "graphite"), ("placa_estator", "graphite"),
    ("separador", "alu"), ("tuerca", "alu"),
    ("28byj48_cuerpo", "steel"), ("28byj48_brida", "steel"), ("28byj48_collar", "steel"),
    ("28byj48_eje", "alu"), ("28byj48_caja_cables", "servo"), ("28byj48_jst", "white"),
    ("esp32_pcb", "pcb_dark"), ("esp32_wroom", "steel"), ("esp32_usb", "steel"),
    ("esp32_header", "chip"),
    ("uln2003_pcb", "pcb_green"), ("uln2003_ic", "chip"), ("uln2003_conector", "white"),
    ("uln2003_led", "amber_led"),
    ("consola", "graphite"), ("lcd_pcb", "pcb_green"), ("lcd_bezel", "chip"),
    ("lcd_pantalla", "lcd"),
    ("cubo_eje", "graphite"), ("plataforma", "graphite"), ("anillo_acento", "amber"),
    ("indice", "amber"),
    ("brazo", "graphite"), ("franja_brazo", "amber"), ("puente", "graphite"),
    ("sg90_eje", "cream"), ("sg90_horn", "cream"), ("sg90", "servo"),
    ("pivote", "alu"),
    ("pod", "graphite"), ("munon", "panel"), ("panel_lateral", "panel"),
    ("canon_raiz", "graphite"), ("canon", "panel"),
    ("freno_boca", "amber"), ("laser_salida", "brass"), ("laser_emisor", "lens"),
    ("ky_standoff", "alu"), ("ky008_pcb", "pcb_red"), ("ky008_tubo", "brass"),
    ("ky008_lente", "lens"), ("ky008_pines", "chip"),
    ("cam_soporte", "graphite"), ("cam_columna", "graphite"), ("cam_pcb", "pcb_green"),
    ("cam_tornillo", "alu"), ("cam_holder", "chip"), ("cam_barril", "chip"),
    ("cam_anillo_foco", "chip"), ("cam_lente", "lens"), ("cam_led", "amber_led"),
    ("us_soporte", "graphite"), ("hcsr04_pcb", "pcb_blue"),
    ("hcsr04_transductor", "steel"), ("hcsr04_malla", "mesh"),
    ("hcsr04_cristal", "steel"), ("hcsr04_pines", "chip"),
    ("gy521_pcb", "pcb_prpl"), ("gy521_mpu", "chip"), ("gy521_header", "chip"),
    ("aleta", "panel"), ("prensaestopas", "panel"), ("anillo_cable", "amber"),
]
NAME2MAT.sort(key=lambda kv: -len(kv[0]))


def assign_materials(mats):
    sin_mapa = set()
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        chosen = None
        for prefix, key in NAME2MAT:
            if obj.name.startswith(prefix):
                chosen = mats[key]
                break
        if chosen is None:
            sin_mapa.add(obj.name)
            chosen = mats["graphite"]
        obj.data.materials.clear()
        obj.data.materials.append(chosen)
        obj.cycles.shadow_terminator_geometry_offset = 0.05
    if sin_mapa:
        print("sin mapa de material (usan grafito):", sorted(sin_mapa)[:10])


# ------------------------------- estudio ------------------------------------
def build_studio():
    # Piso glossy oscuro con micro-relieve
    bpy.ops.mesh.primitive_plane_add(size=5, location=(0, 0, -0.0004))
    floor = bpy.context.object
    floor.name = "piso"
    fm = bpy.data.materials.new("piso_estudio")
    fm.use_nodes = True
    nt = fm.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.012, 0.013, 0.015, 1)
    bsdf.inputs["Roughness"].default_value = 0.32
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 900
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.012
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    floor.data.materials.append(fm)

    # Mundo: fondo oscuro neutro (el modelado lo iluminan los softboxes)
    world = bpy.data.worlds["World"] if "World" in bpy.data.worlds else bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.012, 0.014, 0.018, 1)
    bg.inputs["Strength"].default_value = 1.0

    def softbox(name, loc, rot_deg, size, power, color=(1, 1, 1)):
        light = bpy.data.lights.new(name, type="AREA")
        light.shape = "RECTANGLE"
        light.size, light.size_y = size
        light.energy = power
        light.color = color
        ob = bpy.data.objects.new(name, light)
        ob.location = loc
        ob.rotation_euler = [math.radians(a) for a in rot_deg]
        bpy.context.collection.objects.link(ob)
        return ob

    # key cálida, fill fría, rim dura: esquema clásico de producto
    softbox("key",  (0.45, -0.35, 0.55), (38, 28, 18), (0.9, 0.9), 320, (1.0, 0.96, 0.9))
    softbox("fill", (-0.65, -0.25, 0.30), (62, -38, -20), (1.2, 1.2), 80, (0.85, 0.9, 1.0))
    softbox("rim",  (-0.05, 0.75, 0.55), (-42, 0, 0), (0.7, 0.5), 260, (1.0, 1.0, 1.0))
    softbox("kick", (0.55, 0.45, 0.12), (75, 55, 0), (0.4, 0.4), 60, (1.0, 0.85, 0.6))


def add_camera(loc, target, *, focal=60, fstop=3.2, focus=None):
    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = focal
    cam_data.sensor_width = 36
    cam = bpy.data.objects.new("cam", cam_data)
    cam.location = loc
    bpy.context.collection.objects.link(cam)
    tgt = bpy.data.objects.new("target", None)
    tgt.location = target
    bpy.context.collection.objects.link(tgt)
    con = cam.constraints.new("TRACK_TO")
    con.target = tgt
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    cam_data.dof.use_dof = True
    cam_data.dof.aperture_fstop = fstop
    foc = bpy.data.objects.new("focus", None)
    foc.location = focus or target
    bpy.context.collection.objects.link(foc)
    cam_data.dof.focus_object = foc
    bpy.context.scene.camera = cam
    return cam


SHOTS = {
    #            posición cámara          mira a              focal fstop  foco
    "hero":    dict(loc=(0.24, 0.27, 0.16), target=(0, 0.005, 0.082), focal=70,
                    fstop=4.0, focus=(0, 0.04, 0.1)),
    "detalle": dict(loc=(0.10, 0.17, 0.17), target=(0, 0.02, 0.122), focal=85,
                    fstop=2.8, focus=(0, 0.03, 0.125)),
    "frontal": dict(loc=(0.05, 0.34, 0.10), target=(0, 0.01, 0.09), focal=85,
                    fstop=5.6, focus=(0, 0.05, 0.1)),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", choices=list(SHOTS), default="hero")
    ap.add_argument("--samples", type=int, default=160)
    ap.add_argument("--res", type=int, nargs=2, default=(1600, 1200))
    args = ap.parse_args()

    # escena limpia + import
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(GLB))
    print("objetos importados:", len([o for o in bpy.data.objects if o.type == "MESH"]))

    mats = build_materials()
    assign_materials(mats)
    build_studio()
    add_camera(**SHOTS[args.shot])

    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = args.samples
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = args.res
    sc.render.film_transparent = False
    try:
        sc.view_settings.view_transform = "AgX"
        sc.view_settings.look = "AgX - Punchy"
    except Exception:
        pass
    sc.view_settings.exposure = 0.35

    out = HERE / "outputs" / f"v2_foto_{args.shot}.png"
    sc.render.filepath = str(out)
    bpy.ops.render.render(write_still=True)
    print("render ->", out)


if __name__ == "__main__":
    main()

"""Cupones de prueba: recortes de la geometría REAL del modelo alrededor de
cada interfaz crítica, para imprimir SOLO eso y verificar encastres/tornillos
antes de imprimir la maqueta completa.

Cada cupón es `pieza_real & caja` (intersección): NO se re-dibuja nada, así el
cupón prueba exactamente la geometría que saldrá de la impresora.

Uso:
    ./.venv/bin/python cupones.py
Salida: outputs/cupones/*.stl + outputs/cupones/_montaje.png
"""
import torreta_fase2 as T
from build123d import Box, Pos, Compound, export_stl

OUT = T.OUT / "cupones"
OUT.mkdir(parents=True, exist_ok=True)

# construir las piezas reales (pose neutra; no se llama a componentes())
T.construir_base()
T.construir_tapa()
T.construir_cuerpo()


def solido(pieza):
    """Fusiona los sólidos de una pieza en uno solo (para intersecar)."""
    ss = list(pieza.solids())
    return ss[0].fuse(*ss[1:]) if len(ss) > 1 else ss[0]


# (nombre, pieza, centro_caja, tamaño_caja, qué prueba)
CUPONES = [
    ("01_soporte_motor", "base", (0, 0, 40), (56, 56, 12),
     "techo con eje Ø7.2 + 2 M4 a 35mm + ranura del cable: ofrecer el 28BYJ-48"),
    ("02_encastre_eje", "cuerpo", (0, 0, 43), (36, 36, 22),
     "agujero en D del cuerpo: probar que el eje del motor entra y transmite giro"),
    ("03a_boss_tapa_base", "base", (0, 70, 3), (24, 26, 14),
     "boss M3 de la base (lado base de la union tapa-base)"),
    ("03b_oreja_tapa", "tapa", (0, 70, 3), (24, 26, 12),
     "oreja M3 de la tapa (atornillar contra 03a con un M3)"),
    ("04_postes_oled", "cuerpo", (-40, 0, 96), (18, 30, 32),
     "4 postes M2 (patron 23.5mm) de la cara trasera: ofrecer el OLED real"),
]

print(f"{'CUPON':22} {'vol cm3':>8} {'solidos':>8}  bbox (mm)")
print("-" * 70)
hechos = []
for nombre, pieza, c, s, desc in CUPONES:
    caja = Pos(*c) * Box(*s)
    cup = solido(T.PIEZAS[pieza]) & caja
    sols = list(cup.solids())
    vol = sum(x.volume for x in sols) / 1000
    bb = cup.bounding_box()
    flag = "" if (vol > 0.05 and len(sols) == 1) else "  <-- REVISAR"
    print(f"{nombre:22} {vol:8.2f} {len(sols):8d}  "
          f"{bb.size.X:.0f}x{bb.size.Y:.0f}x{bb.size.Z:.0f}{flag}")
    export_stl(cup, str(OUT / f"cupon_{nombre}.stl"))
    hechos.append((cup, desc, nombre))

# render de control (montaje de los cupones separados)
parts = []
sep = 0
for cup, desc, nombre in hechos:
    bb = cup.bounding_box()
    parts.append(dict(solid=cup.moved(T.Pos(sep, 0, -bb.min.Z)),
                      color=T.COL["cuerpo"], mat="plastico", name=nombre, pieza=None))
    sep += bb.size.X + 25
T.render(parts, OUT / "_montaje.png", hero_dir=(0.6, 1.0, 0.6))
print(f"\nSTL + render en: {OUT}")

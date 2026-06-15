# Cupones de prueba — imprimí ESTO antes que la maqueta completa

Cada `.stl` es un **recorte de la geometría real** de la maqueta alrededor de
una interfaz crítica. Imprimilos (5–20 min cada uno), probá el encastre/tornillo
real y recién después mandá a imprimir las piezas grandes. Así una sorpresa te
cuesta minutos, no horas.

> Imprimí los cupones con **la misma impresora, material y altura de capa** que
> vas a usar para la maqueta — la tolerancia depende de tu setup, no del modelo.

## Qué prueba cada uno

| STL | Qué probar | Cómo |
|---|---|---|
| `cupon_01_soporte_motor.stl` | Patrón del 28BYJ-48: eje Ø7,2 + 2× M4 a 35 mm + ranura del cable | Apoyá el motor real: los 2 tornillos M4 de la brida deben entrar y el eje pasar centrado |
| `cupon_02_encastre_eje.stl` | Agujero en **D** que recibe el eje del motor | Meté el eje del 28BYJ-48: debe entrar firme y **no girar loco** (la cara plana de la D traba el giro) |
| `cupon_03a_boss_tapa_base.stl` + `cupon_03b_oreja_tapa.stl` | Unión tapa↔base con tornillo **M3** | Encimá las dos piezas y atornillá un M3: la cabeza debe avellanar en la oreja y la rosca morder el boss |
| `cupon_04_postes_oled.stl` | Patrón de 4 postes M2 (23,5 mm) del OLED | Apoyá el módulo OLED real: sus 4 agujeros deben coincidir con los postes |

## Si algo NO calza

Los huecos se controlan con dos parámetros en `torreta_fase2.py` (línea ~84):

```python
HOLGURA, PILOTO = 0.4, 1.8
```

- **`HOLGURA`** (0,4 mm): holgura general de encastres (D-hole, funda del joystick).
  - Entra **muy apretado / no entra** → subila (0,5 / 0,6).
  - Entra **flojo / con juego** → bajala (0,3 / 0,2).
- **`PILOTO`** (1,8 mm): diámetro de los agujeros piloto donde la rosca muerde
  el plástico (boss de tornillo). Si el M3 no agarra, bajalo (1,6); si raja el
  plástico, subilo (2,0).

Después de tocar un valor, regenerá los cupones:

```bash
cd diseño_maqueta
./.venv/bin/python cupones.py     # vuelve a exportar los STL ajustados
```

y reimprimí solo el cupón afectado. Cuando los 5 calcen, recién ahí generá e
imprimí la maqueta completa (`./.venv/bin/python torreta_fase2.py` → `outputs/parts_fase2`).

## Importante: estos cupones NO cubren todo

Validan los **encastres y tornillos críticos**. No prueban:
- la alineación cámara/láser/sensor a lo largo del cañón (geometría larga),
- el barrido del cable al girar (eso se verifica en Fusion, ver `MONTAJE_COMPONENTES.md`),
- componentes que todavía no tenés en STEP (láser KY-008, webcam).

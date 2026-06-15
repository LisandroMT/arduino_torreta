# Mapa de montaje — componentes reales sobre la estructura

Cómo ensamblar en **Fusion 360** los componentes reales (`.step`/`.stp` de
`diseño_maqueta/componentes/`) dentro de la estructura impresa
(`outputs/torreta_fase2.step`).

> **Por qué en Fusion y no en build123d:** los STEP de comunidad son pesados
> (el 28BYJ-48 pesa 15 MB) y hacen *core dump* en el importador de build123d.
> Fusion los importa sin problema y permite alinearlos visualmente.

## Sistema de coordenadas

- La estructura se exporta con **Z hacia arriba** (igual que Fusion).
- Origen (0,0,0): centro de la base, a la altura del piso.
- **+X = hacia el cañón** (dirección de tiro, con la torreta en pose neutra).
- **+Z = arriba.**
- Las coordenadas de abajo son el **centro del alojamiento en pose neutra**
  (azimut = 0°, elevación = 0°). Las piezas que van sobre partes móviles
  (cuerpo pan, cuna tilt) **se mueven con la articulación** — usá esta pose
  como referencia de montaje.

## Tabla de montaje

| Componente | Archivo | Centro X,Y,Z (mm) | Orientación (a dónde "mira") | Va sobre |
|---|---|---|---|---|
| **28BYJ-48** (motor) | `28BYJ-48_uln2003_assy.stp` | (-10,7 · 0 · 33,5) | eje vertical **+Z**, sube y encastra en el agujero en D del cuerpo. Cuerpo Ø28 **desplazado 8 mm** del eje | base (cavidad interna) |
| **ULN2003** (driver) | (incluido en el assy de arriba) | (20 · -20 · 10,6) | PCB **horizontal** sobre la tapa, lado largo en X | tapa inferior |
| **ESP32 DevKit V1** | `ESP32 DevkitV1.step` | (-18 · -14 · 8,6) | PCB **horizontal**, lado largo (54 mm) en Y, USB hacia un borde | tapa inferior |
| **Joystick KY-023** | `KY-023_assy.stp` | (0 · 86 · 21) | palanca saliendo en **+Y** (radial, hacia afuera de la funda) | funda lateral de la base |
| **MPU6050 (GY-521)** | `MPU6050.stp` | (32 · 0 · 86) | PCB **horizontal**, lado largo en Y | cuna del tilt |
| **OLED SSD1306** | `OLED TEMU 0.96 in.stp` | (-41,1 · 0 · 96) | pantalla mirando hacia **-X** (atrás), apaisada (lado largo en Y) | cara trasera del cuerpo |
| **SG90** (servo tilt) | `SG90 - Micro Servo 9g - Tower Pro.STEP` | (38 · 39,2 · 102,5) | eje **horizontal en Y** (eje de basculación), corona engranando la cuna hacia -Y | oreja derecha del cuerpo |
| **HC-SR04** | `Ultrasonic sensor.step` | (70,9 · 0 · 67) | transductores mirando **+X** (igual que el cañón) | mentonera del cañón |

### Componentes que todavía no tenés en STEP
| Componente | Centro X,Y,Z (mm) | Orientación | Va sobre |
|---|---|---|---|
| **Láser KY-008** | (164 · 0 · 101) | emite hacia **+X**, en la boca del cañón | punta del cañón |
| **Webcam Gadnic** | (57,3 · 0 · 138) | lente mirando **+X**, pivota sobre el buje en Y | horquilla del cañón |

(Bajá estos dos de GrabCAD cuando puedas; el resto del set ya lo tenés.)

## Paso a paso en Fusion

1. **Insert → Insert Mesh/Insert McMaster… → Upload**, o `File → Open` el
   `torreta_fase2.step` como base del ensamble.
2. Para cada componente: **Insert → Insert Derive / Open** el `.step` del
   componente → aparece en el origen.
3. Seleccionalo y usá **Modify → Align** (o **Assemble → Joint**) para matear
   sus caras contra el alojamiento. La tabla te da el centro de destino y hacia
   dónde debe mirar — empezá llevándolo a esas coordenadas con **Move/Copy →
   Set Position** y después afiná con Align/Joint sobre las caras reales.
4. Poné la estructura en **Apariencia → traslúcida** para verificar que cada
   componente entra en su hueco sin interferencia (y que los cables pasan).

## Nota sobre el `28BYJ-48_uln2003_assy.stp`

Ese archivo trae el **motor Y el driver ULN2003 juntos**, en la posición
relativa del fabricante (que **no** coincide con la del proyecto: acá el motor
va en la cavidad de la base y el ULN2003 sobre la tapa, separados). En Fusion:
hacé clic derecho sobre el componente → **Break Link / Ungroup**, separá las dos
piezas y posicioná cada una con las coordenadas de la tabla.

## Si algún día cambian las dimensiones de la estructura

Las coordenadas salen del CAD paramétrico (`torreta_fase2.py`). Si se regenera
la estructura, regenerá esta tabla con:

```bash
cd diseño_maqueta
./.venv/bin/python -c "import torreta_fase2 as T; T.componentes(); \
from build123d import Compound; \
[print(p['name'], Compound(children=[p['solid']]).bounding_box().center()) for p in T.PARTS]"
```

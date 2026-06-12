# Nodo de percepción — PC + OpenCV

Implementa el nodo de percepción de `DESCRIPCION_PROYECTO.md` (§3 y §8): captura el
video de la webcam montada en la torreta, detecta y sigue al objetivo por color,
calcula el error respecto del centro de la imagen y envía las correcciones de
apuntado al ESP32 por **USB-serie**. Muestra en pantalla la **distancia medida por
el ultrasonido** que reporta el ESP32 (requisito de §3).

## La webcam (Gadnic WEBL56)

Es una cámara **UVC estándar**: Windows y Linux la reconocen sin drivers y OpenCV
la abre directo. Notas prácticas:

- El script la configura a **640×480 con MJPG y buffer de 1 cuadro**: en cámaras de
  este tipo es la combinación de menor latencia (1080p mete >100 ms de retardo y no
  aporta nada al lazo de control).
- Es de **foco fijo**: montala de modo que el blanco trabaje a más de ~40 cm.
- La exposición automática puede "bombear" los colores con cambios de luz: iluminá
  la escena de forma pareja antes de calibrar el color.
- En Linux, si no aparece: `ls /dev/video*` y probá `--camara 1` (algunas UVC
  exponen dos dispositivos).

## Instalación

```bash
cd pc
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

En Linux, para el puerto serie: `sudo usermod -a -G dialout $USER` (cerrar sesión
y volver a entrar).

## Uso

```bash
python seguimiento.py                          # cámara 0, detecta el puerto solo
python seguimiento.py --puerto /dev/ttyUSB0    # puerto explícito (Windows: COM3)
python seguimiento.py --sin-serial             # probar la visión sin el ESP32
python seguimiento.py --calibrar               # arrancar calibrando el color
```

Teclas: `q` salir · `c` recalibrar color · `r` alternar objetivo color/mano · `h` ayuda.

## Detección de manos (MediaPipe)

Todas las manos detectadas se **encuadran en un rectángulo verde** con su
**esqueleto de 21 puntos** dibujado (MediaPipe Hands: detector de palma + regresor
de landmarks, modelo liviano en CPU). Con la tecla `r` —o arrancando con
`--modo mano`— la mano más grande pasa a ser **el objetivo que la torreta sigue**
(etiqueta "MANO (objetivo)"); con `r` de nuevo se vuelve al seguimiento por color.

> Nota: mediapipe instala su propio OpenCV (`opencv-contrib-python`); no hay que
> tener `opencv-python` instalado a la vez (se pisan).

## Calibración del color del objetivo

El blanco se detecta por color HSV (por defecto: **naranja**, pensado para una
pelota o cartulina). Con `c` se abre la ventana de calibración: ajustá las barras
hasta que la máscara (derecha) muestre el objetivo blanco y el fondo negro, y
guardá con `s`. El rango queda en `hsv.json` y se carga solo la próxima vez.

## Ajuste del lazo (constantes al tope de `seguimiento.py`)

| Constante | Qué hace | Si la torreta… |
|---|---|---|
| `PASOS_POR_PX` (0.9) | ganancia de azimut | oscila → bajarla; llega lenta → subirla |
| `GRADOS_POR_PX` (0.08) | ganancia de elevación | ídem |
| `ZONA_MUERTA_PX` (14) | radio de "centrado" | tiembla centrado → agrandarla |
| `INVERTIR_AZ / INVERTIR_EL` | sentido de giro | corrige al revés → ponerla en `True` |
| `MAX_PASOS / MAX_GRADOS` | tope por corrección | da tirones → bajarlos |

## Protocolo serie (compartido con el firmware y la simulación Wokwi)

```
PC → ESP32 :  A <pasos> <grados>   corrección relativa (A 0 0 = blanco centrado)
              L                    blanco perdido (CU-04)
ESP32 → PC :  EST;modo=..;az=..;el=..;dist=..;temp=..   telemetría cada 500 ms
              FIRE                                       disparo ejecutado
```

Cuando la PC envía `A 0 0` (blanco centrado) y el ESP32 mide distancia **en
rango**, el firmware dispara (láser + buzzer) — CU-02/CU-03 de la descripción
del proyecto. El HUD muestra la distancia en grande, el modo, la temperatura,
el estado del enlace y los FPS.

## Probar contra la simulación Wokwi

Sin hardware todavía: corré `wokwi/` en el navegador y este script con
`--sin-serial` para validar la visión; el protocolo es idéntico, así que cuando
el circuito real esté armado solo cambia el puerto.

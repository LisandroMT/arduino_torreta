#!/usr/bin/env python3
"""Nodo de percepción de la torreta — PC + OpenCV (DESCRIPCION_PROYECTO.md §3 y §8).

Captura el video de la webcam montada en la torreta (Gadnic WEBL56 u otra UVC),
detecta y sigue un objetivo por color (HSV), calcula el error en píxeles respecto
del centro de la imagen y envía correcciones de apuntado al ESP32 por USB-serie.
Recibe la telemetría (incluida la DISTANCIA del ultrasonido) y la muestra
superpuesta al video.

Protocolo serie (el mismo del firmware / simulación Wokwi):
    PC -> ESP32:   "A <pasos> <grados>"  corrección relativa (0 0 = centrado)
                   "L"                   blanco perdido
    ESP32 -> PC:   "EST;modo=...;az=...;el=...;dist=...;temp=..."  cada 500 ms
                   "FIRE"                disparo ejecutado

Uso:
    python seguimiento.py                        # cámara 0, puerto auto
    python seguimiento.py --puerto /dev/ttyUSB0
    python seguimiento.py --camara 1 --sin-serial   # probar visión sin ESP32
    python seguimiento.py --calibrar                # recalibrar el color HSV

Teclas:  q = salir · c = recalibrar color · r = objetivo color/mano ·
         h = ocultar/mostrar ayuda
"""
from __future__ import annotations

import argparse
import json
import threading
import time
from pathlib import Path

import cv2
import numpy as np

try:
    import serial
    import serial.tools.list_ports
except ImportError:  # --sin-serial sigue funcionando sin pyserial
    serial = None

# ============================== PARÁMETROS ==================================
ANCHO, ALTO = 640, 480        # resolución de trabajo (baja latencia en la WEBL56)
FPS_PEDIDOS = 30

# Lazo proporcional (§8): error en px -> corrección de actuadores
PASOS_POR_PX = 0.9            # azimut: pasos del 28BYJ-48 por píxel de error
GRADOS_POR_PX = 0.08          # elevación: grados del SG90 por píxel de error
ZONA_MUERTA_PX = 14           # |error| menor => "centrado" (A 0 0 => puede disparar)
MAX_PASOS = 120               # tope por corrección (suaviza el movimiento)
MAX_GRADOS = 4
INVERTIR_AZ = False           # poner True si la torreta corrige al revés
INVERTIR_EL = False

RADIO_MINIMO_PX = 8           # tamaño mínimo del blanco para considerarlo válido
FRAMES_PARA_PERDIDO = 10      # cuadros sin detección => avisar "L"
PERIODO_ENVIO_S = 0.066       # ~15 correcciones por segundo
BAUDIOS = 115200

# HSV por defecto: objetivo NARANJA (pelota/cartulina). Se recalibra con 'c'.
HSV_DEFECTO = {"h_min": 5, "h_max": 22, "s_min": 120, "s_max": 255,
               "v_min": 90, "v_max": 255}
ARCHIVO_HSV = Path(__file__).parent / "hsv.json"


# ============================ SERIE (ESP32) =================================
class EnlaceSerie:
    """Envía correcciones y lee la telemetría del ESP32 en un hilo aparte."""

    def __init__(self, puerto: str | None, activo: bool = True):
        self.telemetria: dict[str, str] = {}
        self.ultimo_fire = 0.0
        self.conectado = False
        self._ser = None
        if not activo or serial is None:
            return
        puerto = puerto or self._detectar_puerto()
        if puerto is None:
            print("[!] No se encontró el ESP32 (probá --puerto). Sigo sin serie.")
            return
        try:
            self._ser = serial.Serial(puerto, BAUDIOS, timeout=0.2)
            self.conectado = True
            print(f"[OK] ESP32 en {puerto} @ {BAUDIOS}")
            threading.Thread(target=self._leer, daemon=True).start()
        except Exception as e:
            print(f"[!] No pude abrir {puerto}: {e}. Sigo sin serie.")

    @staticmethod
    def _detectar_puerto() -> str | None:
        candidatos = []
        for p in serial.tools.list_ports.comports():
            desc = f"{p.description} {p.manufacturer or ''}".lower()
            if any(k in desc for k in ("cp210", "ch340", "usb serial", "uart", "esp32")):
                candidatos.append(p.device)
        return candidatos[0] if candidatos else None

    def enviar(self, linea: str) -> None:
        if self._ser is None:
            return
        try:
            self._ser.write((linea + "\n").encode())
        except Exception:
            self.conectado = False

    def _leer(self) -> None:
        while True:
            try:
                linea = self._ser.readline().decode(errors="ignore").strip()
            except Exception:
                self.conectado = False
                return
            if not linea:
                continue
            if linea.startswith("EST;"):
                for campo in linea[4:].split(";"):
                    if "=" in campo:
                        k, v = campo.split("=", 1)
                        self.telemetria[k] = v
            elif linea == "FIRE":
                self.ultimo_fire = time.monotonic()


# ============================== CÁMARA ======================================
def abrir_camara(indice: int) -> cv2.VideoCapture:
    """Abre la webcam con configuración de baja latencia.

    La Gadnic WEBL56 es UVC estándar: MJPG le permite sostener 30 fps; el
    buffer de 1 cuadro evita procesar imágenes viejas (clave para el lazo).
    """
    cap = cv2.VideoCapture(indice)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, ANCHO)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, ALTO)
    cap.set(cv2.CAP_PROP_FPS, FPS_PEDIDOS)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    if not cap.isOpened():
        raise SystemExit(f"No pude abrir la cámara {indice} (probá --camara 1)")
    return cap


# ====================== CALIBRACIÓN DE COLOR (HSV) ==========================
def cargar_hsv() -> dict:
    if ARCHIVO_HSV.exists():
        try:
            return {**HSV_DEFECTO, **json.loads(ARCHIVO_HSV.read_text())}
        except Exception:
            pass
    return dict(HSV_DEFECTO)


def calibrar_hsv(cap: cv2.VideoCapture, hsv: dict) -> dict:
    """Ventana con barras para ajustar el rango HSV mirando la máscara en vivo."""
    win = "Calibracion HSV  [s=guardar  q=cancelar]"
    cv2.namedWindow(win)
    for k, vmax in (("h_min", 179), ("h_max", 179), ("s_min", 255),
                    ("s_max", 255), ("v_min", 255), ("v_max", 255)):
        cv2.createTrackbar(k, win, hsv[k], vmax, lambda _v: None)
    while True:
        ok, frame = cap.read()
        if not ok:
            continue
        # ventana cerrada con la X => cancelar sin romper
        try:
            if cv2.getWindowProperty(win, cv2.WND_PROP_VISIBLE) < 1:
                return hsv
            valores = {k: cv2.getTrackbarPos(k, win) for k in HSV_DEFECTO}
        except cv2.error:
            return hsv
        mask = mascara_hsv(frame, valores)
        vista = np.hstack([frame, cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)])
        cv2.imshow(win, cv2.resize(vista, (ANCHO, ALTO // 2)))
        tecla = cv2.waitKey(1) & 0xFF
        if tecla == ord("s"):
            ARCHIVO_HSV.write_text(json.dumps(valores, indent=2))
            print(f"[OK] HSV guardado en {ARCHIVO_HSV}")
            cv2.destroyWindow(win)
            return valores
        if tecla == ord("q"):
            cv2.destroyWindow(win)
            return hsv


def mascara_hsv(frame: np.ndarray, hsv: dict) -> np.ndarray:
    """Umbral HSV + limpieza morfológica (quita ruido, rellena huecos)."""
    img = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lo = (hsv["h_min"], hsv["s_min"], hsv["v_min"])
    hi = (hsv["h_max"], hsv["s_max"], hsv["v_max"])
    mask = cv2.inRange(img, lo, hi)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    return mask


# =========================== DETECCIÓN DE MANOS =============================
try:
    import mediapipe as _mp
except ImportError:
    _mp = None


class DetectorManos:
    """MediaPipe Hands: detector de palma + 21 puntos por mano, en CPU.

    `model_complexity=0` usa el modelo liviano: alcanza de sobra a 640×480 y
    mantiene los fps del lazo. El tracking interno hace que entre cuadros sea
    aún más barato que la detección inicial.
    """

    def __init__(self, max_manos: int = 2):
        if _mp is None:
            raise SystemExit("Falta mediapipe: pip install mediapipe")
        self._sol = _mp.solutions.hands
        self._dibujo = _mp.solutions.drawing_utils
        self._estilos = _mp.solutions.drawing_styles
        self._hands = self._sol.Hands(model_complexity=0, max_num_hands=max_manos,
                                      min_detection_confidence=0.6,
                                      min_tracking_confidence=0.5)
        self.manos: list = []       # [(x, y, w, h, landmarks)]

    def detectar(self, frame: np.ndarray):
        h, w = frame.shape[:2]
        res = self._hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        self.manos = []
        if res.multi_hand_landmarks:
            for lms in res.multi_hand_landmarks:
                xs = [p.x for p in lms.landmark]
                ys = [p.y for p in lms.landmark]
                m = 14   # margen alrededor de los 21 puntos
                x0 = max(int(min(xs) * w) - m, 0)
                y0 = max(int(min(ys) * h) - m, 0)
                x1 = min(int(max(xs) * w) + m, w - 1)
                y1 = min(int(max(ys) * h) + m, h - 1)
                self.manos.append((x0, y0, x1 - x0, y1 - y0, lms))
        return self.manos

    def dibujar_esqueleto(self, frame, lms) -> None:
        self._dibujo.draw_landmarks(
            frame, lms, self._sol.HAND_CONNECTIONS,
            self._estilos.get_default_hand_landmarks_style(),
            self._estilos.get_default_hand_connections_style())


def mano_principal(manos):
    """La mano más grande -> (cx, cy, radio_aprox) o None."""
    if not manos:
        return None
    x, y, w, h, _lms = max(manos, key=lambda m: m[2] * m[3])
    return x + w // 2, y + h // 2, max(w, h) // 2


# ========================== DETECCIÓN / SEGUIMIENTO =========================
def detectar_blanco(mask: np.ndarray):
    """Contorno más grande de la máscara -> (cx, cy, radio) o None."""
    contornos, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contornos:
        return None
    c = max(contornos, key=cv2.contourArea)
    (x, y), r = cv2.minEnclosingCircle(c)
    if r < RADIO_MINIMO_PX:
        return None
    m = cv2.moments(c)
    if m["m00"] == 0:
        return None
    return int(m["m10"] / m["m00"]), int(m["m01"] / m["m00"]), int(r)


# ============================== OVERLAY (HUD) ===============================
def dibujar_manos(frame, manos, detector, es_objetivo):
    """Encuadra cada mano en un rectángulo verde + esqueleto de 21 puntos."""
    verde = (80, 220, 120)
    for (x, y, w, h, lms) in manos:
        detector.dibujar_esqueleto(frame, lms)
        cv2.rectangle(frame, (x, y), (x + w, y + h), verde, 2, cv2.LINE_AA)
        etiqueta = "MANO (objetivo)" if es_objetivo else "MANO"
        cv2.putText(frame, etiqueta, (x, y - 8), cv2.FONT_HERSHEY_SIMPLEX,
                    0.5, verde, 1, cv2.LINE_AA)


def dibujar_hud(frame, blanco, suave, centrado, enlace, mostrar_ayuda, fps,
                modo_objetivo):
    h, w = frame.shape[:2]
    cx, cy = w // 2, h // 2
    verde, ambar, rojo = (80, 220, 120), (60, 180, 255), (60, 60, 230)

    # retícula central + zona muerta
    cv2.drawMarker(frame, (cx, cy), ambar, cv2.MARKER_CROSS, 26, 1)
    cv2.circle(frame, (cx, cy), ZONA_MUERTA_PX, ambar, 1, cv2.LINE_AA)

    # blanco detectado: círculo + vector de error
    if blanco is not None:
        bx, by, r = suave
        color = verde if centrado else rojo
        cv2.circle(frame, (bx, by), r, color, 2, cv2.LINE_AA)
        cv2.circle(frame, (bx, by), 3, color, -1, cv2.LINE_AA)
        cv2.line(frame, (cx, cy), (bx, by), color, 1, cv2.LINE_AA)

    # ---- distancia GRANDE en pantalla (requisito §3) ----
    dist = enlace.telemetria.get("dist", "--")
    temp = enlace.telemetria.get("temp", "--")
    modo = enlace.telemetria.get("modo", "--")
    cv2.putText(frame, f"{dist} cm", (w - 195, 52),
                cv2.FONT_HERSHEY_DUPLEX, 1.4, verde, 2, cv2.LINE_AA)
    cv2.putText(frame, f"T:{temp}C  modo:{modo}", (w - 195, 78),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (210, 210, 210), 1, cv2.LINE_AA)

    # estado
    estado = ("OBJETIVO ALCANZADO" if time.monotonic() - enlace.ultimo_fire < 1.2
              else "CENTRADO - en espera de rango" if centrado
              else "SIGUIENDO" if blanco is not None else "SIN OBJETIVO")
    cv2.putText(frame, estado, (12, 30), cv2.FONT_HERSHEY_DUPLEX, 0.7,
                verde if "ALCANZADO" in estado or "CENTRADO" in estado else ambar,
                1, cv2.LINE_AA)
    cv2.putText(frame, f"objetivo: {modo_objetivo.upper()} (r cambia)", (12, 52),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (210, 210, 210), 1, cv2.LINE_AA)
    serie_txt = "serie OK" if enlace.conectado else "SIN SERIE"
    cv2.putText(frame, f"{serie_txt} · {fps:4.1f} fps", (12, h - 14),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                verde if enlace.conectado else rojo, 1, cv2.LINE_AA)
    if mostrar_ayuda:
        cv2.putText(frame, "q salir · c calibrar color · r color/mano · h ayuda",
                    (12, h - 36), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                    (180, 180, 180), 1, cv2.LINE_AA)


# ================================= MAIN =====================================
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--camara", type=int, default=0, help="índice de la webcam")
    ap.add_argument("--puerto", default=None, help="puerto serie del ESP32")
    ap.add_argument("--sin-serial", action="store_true",
                    help="solo visión (sin ESP32)")
    ap.add_argument("--calibrar", action="store_true",
                    help="arrancar calibrando el color HSV")
    ap.add_argument("--modo", choices=("color", "mano"), default="color",
                    help="qué se usa como objetivo a seguir")
    args = ap.parse_args()

    cap = abrir_camara(args.camara)
    hsv = cargar_hsv()
    if args.calibrar:
        hsv = calibrar_hsv(cap, hsv)
    enlace = EnlaceSerie(args.puerto, activo=not args.sin_serial)
    detector_manos = DetectorManos()
    modo_objetivo = args.modo

    suave = None                  # posición suavizada (EMA) del blanco
    frames_sin_blanco = 0
    perdido_avisado = False
    t_envio = 0.0
    t_fps, fps = time.monotonic(), 0.0
    mostrar_ayuda = True

    print("Seguimiento activo. 'q' para salir.")
    while True:
        ok, frame = cap.read()
        if not ok:
            print("[!] cuadro perdido")
            continue

        # manos: siempre se detectan y encuadran; según el modo, además
        # son el objetivo que la torreta sigue
        manos = detector_manos.detectar(frame)
        if modo_objetivo == "mano":
            blanco = mano_principal(manos)
        else:
            mask = mascara_hsv(frame, hsv)
            blanco = detectar_blanco(mask)
        h, w = frame.shape[:2]
        centrado = False

        if blanco is not None:
            frames_sin_blanco = 0
            perdido_avisado = False
            # suavizado exponencial: menos jitter en el lazo
            if suave is None:
                suave = blanco
            else:
                a = 0.45
                suave = tuple(int(a * n + (1 - a) * v)
                              for n, v in zip(blanco, suave))
            dx = suave[0] - w // 2          # + : blanco a la derecha
            dy = suave[1] - h // 2          # + : blanco abajo
            centrado = abs(dx) <= ZONA_MUERTA_PX and abs(dy) <= ZONA_MUERTA_PX

            ahora = time.monotonic()
            if ahora - t_envio >= PERIODO_ENVIO_S:
                t_envio = ahora
                if centrado:
                    enlace.enviar("A 0 0")   # centrado: el ESP32 decide el disparo
                else:
                    pasos = int(np.clip(dx * PASOS_POR_PX, -MAX_PASOS, MAX_PASOS))
                    grados = int(np.clip(-dy * GRADOS_POR_PX, -MAX_GRADOS, MAX_GRADOS))
                    if INVERTIR_AZ:
                        pasos = -pasos
                    if INVERTIR_EL:
                        grados = -grados
                    enlace.enviar(f"A {pasos} {grados}")
        else:
            suave = None
            frames_sin_blanco += 1
            if frames_sin_blanco >= FRAMES_PARA_PERDIDO and not perdido_avisado:
                enlace.enviar("L")           # CU-04: la torreta conserva posición
                perdido_avisado = True

        # FPS medido
        t = time.monotonic()
        fps = 0.9 * fps + 0.1 * (1.0 / max(t - t_fps, 1e-6))
        t_fps = t

        dibujar_manos(frame, manos, detector_manos,
                      es_objetivo=(modo_objetivo == "mano"))
        dibujar_hud(frame, blanco, suave or (0, 0, 0), centrado, enlace,
                    mostrar_ayuda, fps, modo_objetivo)
        cv2.imshow("Torreta - nodo de percepcion", frame)

        tecla = cv2.waitKey(1) & 0xFF
        if tecla == ord("q"):
            break
        try:   # ventana principal cerrada con la X => salir prolijo
            if cv2.getWindowProperty("Torreta - nodo de percepcion",
                                     cv2.WND_PROP_VISIBLE) < 1:
                break
        except cv2.error:
            break
        if tecla == ord("c"):
            hsv = calibrar_hsv(cap, hsv)
        if tecla == ord("r"):
            modo_objetivo = "mano" if modo_objetivo == "color" else "color"
            suave = None     # reinicia el suavizado al cambiar de objetivo
        if tecla == ord("h"):
            mostrar_ayuda = not mostrar_ayuda

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

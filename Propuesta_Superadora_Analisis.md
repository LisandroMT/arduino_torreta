# Torreta Láser → Torreta-Escáner 3D

## Análisis de la propuesta superadora y comparativa para su aprobación

**Proyecto:** TFI Arduino — UTN FRSR, Ingeniería en Sistemas (2026)
**Cambios incorporados en esta revisión:** migración a **ESP32** y agregado de **joystick** para control manual.

---

## 0. Resumen ejecutivo

La propuesta evoluciona la "Torreta Láser con Seguimiento Ultrasónico" (2D, sobre Arduino UNO) hacia una
**Torreta-Escáner 3D con visión por computadora, base rotativa 360° y control manual por joystick**, sobre **ESP32 (WiFi)**.

Cumple **todos** los requisitos de la cátedra y los supera, con componentes 100 % de tier maker y costo bajo (~USD 55–65).
Se recomienda **aprobarla por etapas**: una Fase 1 (núcleo) de bajo riesgo que ya cumple todo, y una Fase 2 (stretch) con la visión por computadora.

---

## 1. Impacto del cambio a ESP32

El ESP32 no es un simple reemplazo de pieza: reconfigura la arquitectura completa (sobre todo el cableado rotativo).

> Doble núcleo a 240 MHz · **520 KB de RAM** (vs 2 KB del UNO) · **WiFi + Bluetooth** integrados · más PWM/ADC · **interrupción en cualquier GPIO**.

### 1.1. Lo que mejora

| Aspecto | UNO R3 | ESP32 | Consecuencia |
|---|---|---|---|
| Cableado del slip ring | Cruzaban muchas señales | **WiFi → solo cruza la alimentación** | Desaparece el gran problema mecánico de la v1 |
| Cámara eye-in-hand | Webcam USB (cable que rota) | **ESP32-CAM streamea MJPEG por WiFi** | Cámara en el cabezal **sin cable que cruce la junta** |
| Procesamiento | Nada de visión | Filtrado/centroide a bordo, buffer de nube de puntos, **dashboard web** | Menos dependencia de la PC; telemetría en navegador |
| Interrupciones | Solo 2 pines (D2/D3) | **Cualquier GPIO** | El "evento crítico" del PIR es trivial; se pueden sumar más |
| Memoria | No entra una nube de puntos | Entra un barrido completo en RAM | Puede acumular antes de enviar |

### 1.2. Arquitectura recomendada

Dos placas baratas en el cabezal, ambas por WiFi; el slip ring **solo lleva los 5 V**:

- **ESP32 de control** → stepper, servos, ToF, IMU, PIR, láser, LCD, joystick.
- **ESP32-CAM** → visión eye-in-hand, streamea a la PC (OpenCV).
- **PC** → percepción pesada + visualización de la nube 3D + coordinación.

> Esto **reemplaza la webcam USB** de la versión anterior: con ESP32-CAM la cámara va arriba, rota con todo y no necesita slip ring de datos. Es estrictamente mejor para el requisito de rotación 360°.

### 1.3. Caveats reales del ESP32 (a tener en cuenta)

- **Lógica de 3,3 V (no 5 V).** Si se conserva el HC-SR04, su pin `ECHO` da 5 V → **necesita divisor resistivo**. VL53L0X, MPU6050 e I2C son nativos 3,3 V (más cómodos que con el UNO).
- **ADC2 se pelea con el WiFi.** Las lecturas analógicas (joystick) **deben ir en pines del ADC1 (GPIO 32–39)**.
- **ESP32-CAM tiene pocos GPIO libres** (los come la cámara + PSRAM) → conviene **separar control y cámara** en dos placas.

---

## 2. Análisis del joystick (control manual)

**Veredicto: sí, vale la pena.** Módulo KY-023 (2 ejes analógicos + pulsador), ~USD 1,5. Agrega una capa de **control humano-en-el-lazo**.

### 2.1. Qué aporta

- Un **modo MANUAL** en la FSM: el operador conduce azimut (stepper) y elevación (tilt); el pulsador dispara/conmuta el láser.
- Contenido nuevo y demostrable: **arbitraje de modos (AUTO ↔ MANUAL)**, lectura analógica con **zona muerta + mapeo a velocidad**, antirrebote del pulsador.
- Demo más vistosa para la defensa: poder "tomar el control" de la torreta en vivo.

### 2.2. Cómo conectarlo (decisiones concretas)

1. **Alimentar el joystick a 3,3 V** (no a 5 V): así sus salidas no superan los 3,3 V del ADC. A 5 V lo dañaría.
2. **Ejes en ADC1 (GPIO 32–39)** por el conflicto con WiFi.
3. **Ubicación** (la torreta gira y el joystick es fijo del operador):
   - **Recomendada (wireless, ESP-NOW):** mando aparte = ESP32 chico + joystick, manda valores por **ESP-NOW** al ESP32 de control. No cruza el slip ring, baja latencia, sin router.
   - **Simple (cableada):** joystick en el panel fijo; sus 5 conductores suben por el **slip ring** al ESP32 del cabezal (si hay conductores de sobra).

### 2.3. Impacto en la FSM

```
                 ┌─────── joystick / switch AUTO↔MANUAL ───────┐
                 ▼                                              │
   ESPERA ──ISR PIR──► BARRIDO 3D ──► DETECCIÓN ──► APUNTADO ──► SEGUIMIENTO
     ▲                                                          │
     └────────────────────── MANUAL (joystick) ◄───────────────┘
                    (el operador conduce pan/tilt; botón = láser)
```

---

## 3. Resumen consolidado de la propuesta superadora

**"Torreta-escáner 3D con visión por computadora, base rotativa 360° y control manual por joystick"**, sobre **ESP32 (WiFi)**:

- **Cinemática de 3 ejes:** base con **stepper 28BYJ-48 (360°, eje propio, 0,088°/paso)** + **pan-tilt (2× SG90)** para los 2 grados de libertad del cabezal.
- **Captura 3D:** por cada (azimut θ, elevación φ) se mide profundidad *r* → nube de puntos `x,y,z` (esféricas → cartesianas), acumulada y visualizada en la PC.
- **Profundidad:** ToF láser VL53L0X (haz angosto) + triangulación cámara-láser `r = f·b/d`.
- **Cámara eye-in-hand (ESP32-CAM)** rígida con el láser → detección/clasificación y **apuntado en lazo cerrado (visual servoing)**, por WiFi.
- **Sensores (3, todos con función real):** PIR (interrupción/evento crítico) + ToF (profundidad) + IMU MPU-6050 (orientación). **La LDR sale.**
- **Actuadores:** stepper + 2 servos + láser + buzzer + LCD.
- **HMI:** **joystick** (modo manual) + dashboard web por WiFi.
- **Arquitectura distribuida:** ESP32 control + ESP32-CAM + PC, enlazados por WiFi/ESP-NOW.

### 3.1. Conversión a 3D (modelo)

```
x = r · cos(φ) · cos(θ)
y = r · cos(φ) · sin(θ)
z = r · sin(φ)
```

### 3.2. Profundidad por triangulación

```
r = (f · b) / d
```
donde `f` = focal (px), `b` = línea base cámara-láser (fija y calibrada), `d` = desplazamiento del punto láser (px).

---

## 4. Comparativa: versión original vs. propuesta superadora

Leyenda: 🔼 mejora/nuevo · 🔁 reemplazo

| Punto | Versión original (informe actual) | Propuesta superadora | ¿Cambia? |
|---|---|---|---|
| **Controlador** | Arduino UNO R3 (8 bits, 2 KB) | **ESP32** (240 MHz, 520 KB, WiFi/BT) | 🔼 Sustancial |
| **Dimensiones** | 2D polar (θ, r) | **3D (nube de puntos x,y,z)** | 🔼 Objetivo nuevo |
| **Ejes / movilidad** | pan + tilt (tilt fijo) | **base 360° (stepper) + pan + tilt activos** | 🔼 Objetivo nuevo |
| **Resolución azimut** | servo ~1°, rango 0–180° | **stepper 0,088°, 360°** | 🔼 |
| **Profundidad** | ultrasónico, haz ~15° | **ToF láser + triangulación cámara-láser** | 🔼 |
| **Percepción** | "cualquier eco = blanco" | **detección + clasificación (visión)** | 🔼 |
| **Apuntado** | lazo abierto (~5°) | **lazo cerrado visual (sub-grado)** | 🔼 |
| **3er sensor** | LDR (función artificial) | **IMU (orientación real)** | 🔁 Reemplazo |
| **Cámara** | no hay (solo mencionada a futuro) | **ESP32-CAM eye-in-hand por WiFi** | 🔼 Nuevo |
| **Control humano** | no hay | **joystick → modo MANUAL** | 🔼 Nuevo |
| **Conectividad** | USB serie | **WiFi / ESP-NOW + dashboard web** | 🔼 Nuevo |
| **Cableado rotación** | (no rotaba 360°) | **slip ring solo de potencia** (datos por WiFi) | 🔼 |
| **Interrupciones** | PIR en 2 pines posibles | PIR en cualquier GPIO | 🔁 Más flexible |
| **FSM** | 5 estados | + estados **BARRIDO 3D, SEGUIMIENTO, MANUAL** | 🔼 |
| **Arquitectura SW** | monolítica en el UNO | **distribuida (2× ESP32 + PC)** | 🔼 |

---

## 5. Evaluación para aprobar o no

### 5.1. A favor

- Cumple **todos** los requisitos de la cátedra (≥3 sensores reales, ≥3 actuadores, interrupción para evento crítico, FSM, modelos teóricos) y los **supera holgadamente**.
- Mucho más **alineado con Ingeniería en Sistemas**: arquitectura distribuida, protocolos, WiFi/ESP-NOW, visión por computadora, HMI.
- **Costo bajo** (~USD 55–65 sin contar la PC) y 100 % componentes **maker** (respeta "nada profesional").
- Cada agregado **tapa una limitación ya admitida** en las conclusiones del informe (resolución angular, falta de discriminación, apuntado abierto).

### 5.2. Riesgos / contras

- **Salto de complejidad grande:** de un sketch monolítico a un sistema distribuido con WiFi, calibración de cámara y sincronización de dos placas. **Principal riesgo de cronograma.**
- **Calibración** de intrínsecos de cámara + triangulación (estándar con OpenCV, pero lleva tiempo).
- **Trampas de 3,3 V** (divisor en HC-SR04, ADC1 para joystick) y **rigidez mecánica** de la barra óptica (si flexa, se va la triangulación).
- **ESP32-CAM**: throughput y GPIO limitados → obliga a separar control y cámara.

### 5.3. Costo estimado (orientativo, tier maker)

| Componente | USD aprox. |
|---|---|
| ESP32 devkit | 6 |
| ESP32-CAM | 7 |
| Stepper 28BYJ-48 + ULN2003 | 3 |
| 2× servo SG90 | 4 |
| ToF VL53L0X | 4 |
| IMU MPU-6050 | 2 |
| PIR HC-SR501 | 2 |
| Joystick KY-023 | 1,5 |
| Slip ring | 8 |
| Módulo láser | 1 |
| LCD 16×2 I2C | 4 |
| Fuente, cap, cables, MDF, varios | ~15 |
| **Total** | **~55–60** |

### 5.4. Recomendación: aprobar por etapas

Separar un **núcleo aprobable y alcanzable** de un **stretch ambicioso**:

| | **Fase 1 — Núcleo (MVP)** | **Fase 2 — Stretch** |
|---|---|---|
| Contenido | ESP32 + base stepper 360° + tilt + ToF → **nube de puntos 3D por WiFi** + **joystick (modo MANUAL)** + PIR (interrupción) + IMU + LCD | **ESP32-CAM**: detección/clasificación + **visual servoing** + triangulación cámara-láser |
| Cumple cátedra | **Sí, completo** | Agrega percepción avanzada |
| Cumple objetivos propios | **3D ✔ · rotación propia ✔ · joystick ✔** | profundidad por cámara ✔ |
| Riesgo | Bajo–medio | Medio–alto |

**Conclusión:** se recomienda **aprobar la propuesta**, comprometiendo la **Fase 1 como entregable principal** y la **Fase 2 como extensión**. Así la nota no depende de lo más riesgoso (visión/CV), pero el proyecto queda claramente "superador" y con techo alto para la defensa.

---

## 6. Pendientes / próximos pasos

- [ ] Actualizar el diagrama de la maqueta para reflejar ESP32 (quitar Arduino, agregar ESP32-CAM eye-in-hand, joystick y enlaces WiFi/ESP-NOW).
- [ ] Armar la tabla de pines del ESP32 (con divisor en HC-SR04 y joystick en ADC1).
- [ ] Redactar las secciones nuevas para el informe (controlador ESP32, joystick/modo manual, FSM actualizada, evaluación por fases).

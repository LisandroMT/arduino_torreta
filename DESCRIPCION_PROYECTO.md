# Torreta de Seguimiento y Apuntado con Visión por Computadora

**Universidad Tecnológica Nacional — Facultad Regional San Rafael**
Ingeniería en Sistemas de Información · Electiva: Arduino · Trabajo Final Integrador · 2026

**Integrantes:** Branko Almeira · Federico Sosa · Agustín Giorlando · Lisandro Toledo · Agustín Lara

---

## 1. Resumen

Este proyecto consiste en una **torreta robótica de dos grados de libertad** capaz de
**detectar y seguir un objetivo móvil** mediante visión por computadora, **apuntarle con
precisión** y **"dispararle"** —activar un módulo láser indicador y un aviso sonoro— cuando
el objetivo se encuentra dentro de un rango de distancia válido.

El sistema se controla con un **ESP32** que actúa como controlador en tiempo real (lectura de
sensores, manejo de actuadores, máquina de estados e interrupción por hardware), mientras que
una **computadora ejecuta la percepción visual** con Python y OpenCV a partir de la **webcam
montada sobre la torreta** (coaxial con el cañón), comunicándose con el ESP32 por **cable
USB-serie**. La torreta opera en dos modos conmutables: **autónomo** (la cámara guía el
apuntado) y **manual** (el operador apunta con un joystick).

A diferencia de un radar bidimensional clásico, la fusión de la **cámara** (que aporta los
ángulos y la identidad del objetivo) con el **sensor ultrasónico** (que aporta la distancia)
permite localizar el blanco y decidir el disparo según un criterio físico de rango.

---

## 2. Objetivos

### 2.1. Objetivo general

Diseñar, programar y prototipar una torreta de seguimiento y apuntado basada en ESP32, que
integre múltiples sensores y actuadores en una arquitectura distribuida con percepción visual,
que responda a un evento crítico mediante una interrupción por hardware y que admita operación
manual y autónoma.

### 2.2. Objetivos específicos

- Diseñar la arquitectura de hardware, justificando la selección de cada componente.
- Desarrollar un firmware **modular y comentado** organizado como **máquina de estados finitos**.
- Incorporar **al menos una rutina de servicio de interrupción** (pulsador del joystick).
- Detectar y **seguir un objetivo móvil** en tiempo real mediante visión por computadora (OpenCV).
- Dotar a la torreta de **dos grados de libertad**: rotación de la base sobre su propio eje
  (azimut, sector de ±180°) y elevación del cañón (tilt).
- Medir la **distancia al objetivo** con un sensor ultrasónico y aplicar **compensación térmica**
  realimentando la velocidad del sonido con la temperatura medida en tiempo real.
- Implementar **fusión de sensores**: combinar los ángulos e identidad de la cámara con el rango
  del ultrasonido.
- **Nivelar y centrar** el cañón usando una unidad de medición inercial (referencia absoluta de
  elevación).
- Incorporar un **modo de control manual** por joystick, conmutable con el modo autónomo.
- Señalizar el estado del sistema en una **pantalla LCD** y avisar el impacto con un **buzzer**.
- Validar el funcionamiento mediante prototipo físico sobre una maqueta de bajo costo.

### 2.3. Alcance

El sistema opera en un volumen definido por el giro de la base en un sector de ±180° (azimut)
—acotado para que el cableado de la torreta no se enrede—, un rango de elevación acotado por el
servomotor (sector útil del cañón) y distancias de medición de ~2 cm a ~400 cm (límites del
sensor HC-SR04). El seguimiento de objetivos opera dentro del campo de
visión de la cámara. El "disparo" es **indicador** (láser + buzzer): **no existe proyectil
físico**. El sistema se concibe con fines educativos y demostrativos, empleando exclusivamente
componentes de nivel *maker*.

**Fuera de alcance (posible trabajo futuro):** generación de una nube de puntos 3D / escaneo
tridimensional del entorno. La torreta tiene el hardware necesario (dos ángulos + distancia),
por lo que podría incorporarse un "modo escaneo" en una etapa posterior; no forma parte de esta
versión.

---

## 3. Arquitectura del sistema

La arquitectura es **distribuida**, repartiendo la carga entre dos nodos según su naturaleza:

```
  ┌──────────────────┐   USB-serie (cable)   ┌─────────────────────────────────┐
  │   PC + Python     │  ───── comandos ────► │              ESP32              │
  │   + OpenCV        │       de apuntado     │   FSM · ISR · control en RT     │
  │(webcam en torreta)│  ◄──── estado ─────── │                                 │
  └──────────────────┘                        └──┬───────────────────────┬──────┘
   • Captura de video                            │ Actuadores            │ Sensores
   • Detección del blanco                  ┌──────┴──────┐         ┌──────┴────────┐
   • Seguimiento                           │ 28BYJ-48    │ azimut  │ HC-SR04       │ distancia
   • Cálculo del error                     │  (+ULN2003) │         │ DHT22         │ temperatura
     angular y envío                       │ SG90        │ tilt    │ MPU6050       │ nivel/cero
   • Muestra distancia en pantalla         │ Láser       │ disparo │ Joystick +    │ manual +
                                           │ Buzzer      │ aviso   │   pulsador    │   ISR
                                           │ LCD 1602 I2C│ display │               │
                                           └─────────────┘         └───────────────┘
```

- **Nodo de percepción (PC):** captura el video de la webcam montada sobre la torreta, detecta y
  sigue al objetivo móvil con OpenCV, calcula la posición del blanco en la imagen (error respecto
  al centro) y envía al ESP32 las correcciones de apuntado. Recibe del ESP32 el estado del
  sistema —incluida la **distancia medida por el ultrasonido**— y lo muestra en pantalla
  superpuesto al video.
- **Nodo de control (ESP32):** ejecuta el control en tiempo real —mueve los actuadores, lee los
  sensores, gestiona la máquina de estados y la interrupción— y reporta estado a la PC y a la LCD.
- **Comunicación:** **USB-serie (cable)**. Se elige sobre WiFi por su **latencia baja y
  determinista** —crítica para el lazo de control visual—, porque el mismo cable **alimenta el
  ESP32** y sirve de **consola de depuración**, y porque elimina la configuración y los imprevistos
  de la red. El enredo de cables se evita **acotando el azimut a un sector de ±180°**; esta misma
  restricción habilita montar la webcam USB sobre la torreta.

---

## 4. Grados de libertad y montaje mecánico

| Eje | Movimiento | Actuador | Característica |
|-----|------------|----------|----------------|
| **Azimut** | Giro de la base sobre su propio eje (sector de ±180°) | **28BYJ-48** + driver **ULN2003** | Paso a paso: la posición se conoce contando pasos (lazo abierto preciso) |
| **Elevación (tilt)** | El cañón sube y baja | **Servo SG90** | Posición por ángulo comandado; su cero se corrige con el MPU6050 |

Montados **coaxialmente con el cañón** (apuntan a donde apunta la torreta):

- **Webcam USB** → ve lo que el cañón tiene enfrente: **centrar el blanco en la imagen equivale
  a apuntarle**, sin transformación de coordenadas.
- **Módulo láser** en la punta del cañón → indicador de apuntado / "disparo".
- **Sensor ultrasónico HC-SR04** → mide la distancia a lo que el cañón tiene enfrente.

El giro acotado del azimut (±180°) permite que todos los cables que suben a la torreta —webcam
USB incluida— trabajen con una holgura simple, sin anillos rozantes.

---

## 5. Componentes y su justificación

| Componente | Función en el proyecto |
|------------|------------------------|
| **ESP32** | Microcontrolador principal. Controlador en tiempo real; se comunica con la PC por USB-serie. |
| **Webcam + OpenCV** | Percepción visual: montada sobre la torreta, coaxial con el cañón. Detecta y sigue al objetivo móvil; aporta su posición angular e identidad. |
| **HC-SR04 (ultrasonido)** | Mide la distancia al objetivo. Define el criterio de **"objetivo en rango"** para disparar. |
| **DHT22** | Mide temperatura (y humedad). Corrige la **velocidad del sonido** para que la distancia del ultrasonido sea precisa. |
| **MPU6050 (IMU)** | Acelerómetro + giróscopo de 6 ejes. Provee la **referencia absoluta de elevación** para nivelar/centrar el cañón. |
| **Joystick + pulsador** | Control manual del apuntado y **fuente de la interrupción por hardware (ISR)**. |
| **Servo SG90** | Eje de elevación (sube/baja el cañón). |
| **28BYJ-48 + ULN2003** | Eje de azimut (giro de la base, sector de ±180°). |
| **Módulo láser** | Apuntado / "disparo" indicador hacia el blanco. |
| **Buzzer** | Aviso sonoro cuando se alcanza el objetivo. |
| **LCD 1602 (I2C)** | Muestra estado, modo, distancia, temperatura y mensajes. |
| **Relés** | *No se utilizan en esta versión.* Quedan documentados como reserva/expansión por si se incorpora un actuador externo en el futuro. |

### 5.1. El papel del MPU6050 (referencia de nivel)

El servo SG90 trabaja en **lazo abierto**: se le ordena un ángulo y se confía en que lo alcanza,
pero su cero mecánico es impreciso y depende de cómo quedó montado el cañón. El **acelerómetro**
del MPU6050 mide el vector gravedad y, con él, el **ángulo de inclinación real del cañón respecto
a la horizontal**. Esto permite **cerrar el lazo de la elevación**: durante el arranque (homing),
el sistema mueve el servo hasta que el MPU lee *pitch = 0°*, dejando el cañón verdaderamente
horizontal. Así se obtiene un **cero absoluto y repetible** de la elevación.

> **Nota técnica:** el MPU6050 **no tiene magnetómetro**, por lo que no provee un "norte"
> absoluto. La referencia que aporta es de **elevación** (inclinación), no de azimut. El azimut
> se conoce por el conteo de pasos del 28BYJ-48.

### 5.2. El papel del ultrasonido (rango y fusión)

La cámara entrega **ángulos** (dónde está el blanco en la imagen) pero **no la profundidad**. El
HC-SR04, coaxial con el cañón, aporta la **distancia** al objetivo. La combinación de ambos es la
**fusión de sensores** del proyecto:

- **Cámara → ángulos e identidad** del objetivo.
- **Ultrasonido → distancia** al objetivo.

Con la distancia, el sistema decide si el blanco está **en rango** para disparar y evita falsos
positivos. La medición se corrige con la temperatura del DHT22.

---

## 6. Compensación térmica de la distancia

El HC-SR04 mide distancia por **tiempo de vuelo** del sonido. La velocidad del sonido en el aire
depende de la temperatura:

```
v(T) ≈ 331,4 + 0,606 · T          [m/s],  con T en °C
distancia = v(T) · t_vuelo / 2
```

Sin corregir, usar un valor fijo (~343 m/s) introduce un error sistemático que crece con la
diferencia de temperatura (≈ 0,6 m/s por cada °C). El **DHT22** mide la temperatura en tiempo
real y el firmware recalcula `v(T)` en cada medición, eliminando ese error.

---

## 7. Modos de operación y máquina de estados

El firmware se organiza como una **máquina de estados finitos (FSM)**:

1. **HOMING / INICIO**
   Nivela el cañón con el MPU6050 (lleva la elevación a *pitch = 0°*) y fija el cero de azimut.
   Inicializa sensores, LCD y el enlace serie con la PC.

2. **AUTÓNOMO** *(modo por defecto)*
   La PC sigue al objetivo con la cámara y envía correcciones de apuntado → el ESP32 ajusta giro
   (28BYJ-48) y elevación (SG90) hasta centrar el blanco → mide la distancia con el ultrasonido y
   la reporta a la PC, que la muestra en pantalla sobre el video → si el blanco está **en rango**,
   activa **láser + buzzer** y muestra *"Objetivo alcanzado"*.

3. **MANUAL**
   El **joystick** mueve el giro y la elevación; el operador apunta a mano. Una **pulsación corta**
   del botón **dispara** (láser + buzzer).

```
        ┌──────────┐
        │  HOMING  │  nivela el cañón (MPU) y fija el cero
        └────┬─────┘
             │ listo
             ▼
   ┌───── AUTÓNOMO ◄──────┐
   │  (cámara apunta)     │  pulsación larga
   │  en rango → dispara  │  conmuta modo
   └────────┬─────────────┘
            │ pulsación larga
            ▼
   ┌────── MANUAL ────────┐
   │  joystick apunta     │
   │  corta → dispara     │
   └──────────────────────┘
```

### 7.1. La interrupción por hardware (ISR)

La fuente de interrupción es el **pulsador del joystick**, gestionado por una rutina de servicio
de interrupción. Se distinguen dos gestos midiendo la duración de la pulsación:

- **Pulsación larga** → conmuta entre **MANUAL ⇄ AUTÓNOMO**.
- **Pulsación corta** → en **MANUAL**, ejecuta el **disparo** (láser + buzzer); en **AUTÓNOMO** el
  disparo es automático al entrar en rango.

---

## 8. Lazo de control de seguimiento (visual servoing)

El seguimiento es un **lazo de control visual proporcional**. Como la cámara va montada sobre la
torreta, coaxial con el cañón, **anular el error en la imagen equivale a apuntar al blanco**:

1. OpenCV detecta el objetivo y calcula el **error en píxeles** entre el centro del blanco y el
   centro de la imagen (Δx horizontal, Δy vertical).
2. La PC traduce ese error en correcciones de **azimut** (pasos del 28BYJ-48) y **elevación**
   (grados del SG90) y las envía al ESP32.
3. El ESP32 aplica las correcciones; la torreta se mueve para **reducir el error** hasta centrar
   el blanco.
4. El ciclo se repite a la frecuencia de cuadros, persiguiendo al objetivo mientras se mueve.

---

## 9. Casos de uso (escenarios de operación)

El actor humano del sistema es el **operador**. El **objetivo móvil** se modela como un actor
secundario: no usa el sistema, pero sus movimientos lo estimulan y disparan su comportamiento.

### CU-01 — Puesta en marcha (homing)

- **Disparador:** el operador energiza el sistema.
- **Respuesta:** el ESP32 inicializa sensores, LCD y enlace serie con la PC → mueve el servo
  hasta que el MPU6050 lee *pitch = 0°* (cañón horizontal) → fija el cero de azimut.
- **Resultado:** ceros establecidos; el sistema queda en modo **AUTÓNOMO**, a la espera de un
  objetivo. La LCD muestra el estado.

### CU-02 — Seguimiento y disparo autónomo

- **Disparador:** un objetivo entra en el campo de visión de la cámara.
- **Respuesta:** OpenCV lo detecta y calcula el error respecto del centro de la imagen → la PC
  envía correcciones por serie → la torreta gira (28BYJ-48) y eleva el cañón (SG90) hasta
  centrarlo → el HC-SR04 mide la distancia (corregida por la temperatura del DHT22) y el ESP32
  la reporta a la PC, que la muestra sobre el video.
- **Resultado:** con el blanco **centrado y en rango**, se activan **láser + buzzer** y la LCD
  muestra *"Objetivo alcanzado"*.

### CU-03 — Objetivo centrado pero fuera de rango

- **Disparador:** el blanco está centrado, pero la distancia medida excede el rango válido.
- **Respuesta:** el sistema **no dispara**; continúa el seguimiento y reporta la distancia a la
  PC y a la LCD.
- **Resultado:** el disparo queda inhibido hasta que el criterio físico de rango se cumpla
  (evita falsos positivos).

### CU-04 — Pérdida del objetivo

- **Disparador:** el blanco sale del campo de visión (o la detección se pierde).
- **Respuesta:** la PC deja de enviar correcciones; la torreta **conserva su última posición**
  a la espera de readquirir el blanco. La LCD indica que no hay objetivo.
- **Resultado:** al reaparecer el blanco, el seguimiento se reanuda (vuelve a CU-02).

### CU-05 — Conmutación de modo (AUTÓNOMO ⇄ MANUAL)

- **Disparador:** el operador hace una **pulsación larga** del botón del joystick (atendida
  por la ISR).
- **Respuesta:** la FSM conmuta de modo y la LCD informa el modo activo.
- **Resultado:** en MANUAL la cámara deja de comandar la torreta; en AUTÓNOMO el joystick deja
  de hacerlo.

### CU-06 — Apuntado y disparo manual

- **Disparador:** en modo MANUAL, el operador mueve el joystick y hace una **pulsación corta**
  para disparar.
- **Respuesta:** el joystick comanda azimut y elevación; la pulsación corta activa
  **láser + buzzer**. La distancia medida sigue mostrándose en la LCD y en la pantalla de la PC.
- **Resultado:** disparo indicador bajo control humano directo.

### CU-07 — Límite del sector de giro

- **Disparador:** el seguimiento (o el joystick) lleva el azimut al borde del sector de ±180°.
- **Respuesta:** el ESP32 **satura el movimiento en el límite** (no lo sobrepasa), protegiendo
  el cableado de la torreta.
- **Resultado:** el blanco solo puede seguirse dentro del sector útil; fuera de él aplica CU-04.

---

## 10. Cumplimiento de la consigna de la cátedra

| Requisito | Cómo se cumple |
|-----------|----------------|
| Firmware modular y comentado | Código organizado en funciones por subsistema (sensores, actuadores, comunicación, FSM). |
| Máquina de estados finitos | Estados HOMING / AUTÓNOMO / MANUAL (sección 7). |
| ≥ 1 interrupción de hardware | ISR del pulsador del joystick (sección 7.1). |
| Justificación de componentes | Sección 5. |
| Fusión de sensores | Cámara (ángulos) + ultrasonido (rango) (secciones 3 y 5.2). |
| Respuesta a evento crítico | Interrupción del pulsador. |
| Modo manual | Control por joystick conmutable (sección 7). |

---

## 11. Lista de materiales (BOM)

| # | Componente | Cantidad |
|---|------------|----------|
| 1 | ESP32 (placa de desarrollo) | 1 |
| 2 | Servomotor SG90 | 1 |
| 3 | Motor paso a paso 28BYJ-48 + driver ULN2003 | 1 |
| 4 | Sensor ultrasónico HC-SR04 | 1 |
| 5 | Sensor de temperatura y humedad DHT22 | 1 |
| 6 | IMU MPU6050 | 1 |
| 7 | Joystick analógico con pulsador | 1 |
| 8 | Pantalla LCD 1602 (con módulo I2C) | 1 |
| 9 | Módulo láser | 1 |
| 10 | Buzzer | 1 |
| 11 | Webcam (USB, montada sobre la torreta) | 1 |
| 12 | Computadora con Python + OpenCV | 1 |
| 13 | Fuente de alimentación / regulación | según consumo |
| — | Relés *(reserva, no usados en esta versión)* | 0 |

---

*Documento de descripción del proyecto. Reemplaza la versión anterior (torreta-escáner 3D con
dos servos y sensor PIR), archivada en `docs/archivo/`.*

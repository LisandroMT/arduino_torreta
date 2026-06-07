# Torreta-Escáner 3D con Visión por Computadora

### Sistema autónomo de detección, clasificación, localización 3D y apuntado, con base rotativa de 360° y control manual, basado en ESP32

**UNIVERSIDAD TECNOLÓGICA NACIONAL**

Facultad Regional San Rafael

Ingeniería en Sistemas de Información

Electiva: Arduino — Trabajo Final Integrador

---

**Integrantes:** Branko Almeira · Federico Sosa · Agustín Giorlando · Lisandro Toledo · Agustín Lara

**Docentes:** Ing. Alfredo G. Rivamar — Ing. Pablo Moliterno

**2026**

---

## Resumen

El presente trabajo describe el diseño, la implementación y la validación de una **torreta-escáner tridimensional autónoma** capaz de detectar la presencia de objetos en su entorno, **clasificar su tipo mediante visión por computadora** (por ejemplo, distinguir una persona de un avión a escala), localizarlos en coordenadas tridimensionales y apuntar un haz indicador hacia el blanco seleccionado. El sistema se desarrolla sobre un microcontrolador **ESP32** e integra un conjunto de sensores —ultrasónico HC-SR04, sensor de temperatura y humedad DHT22, sensor pasivo infrarrojo PIR HC-SR501, unidad de medición inercial MPU-6050 y una cámara web— junto a una cadena de actuadores conformada por un **motor paso a paso 28BYJ-48** que provee la rotación de la base sobre su propio eje (360°), **dos servomotores SG90** en configuración pan-tilt, un diodo láser indicador, un buzzer piezoeléctrico y una pantalla LCD 16×2 por I2C. La incorporación de un **joystick analógico** habilita un modo de control manual, sumando una capa de interacción humano-máquina a la operación autónoma.

La arquitectura es **distribuida**: el ESP32 actúa como controlador de tiempo real (lectura de sensores, control de actuadores, máquina de estados e interrupciones), mientras que una computadora ejecuta la **percepción visual** mediante OpenCV y un modelo de detección de objetos, comunicándose por WiFi. La profundidad se obtiene por **tiempo de vuelo acústico**, corregido en tiempo real por la temperatura medida con el DHT22, eliminando el error sistemático asociado a la variación de la velocidad del sonido. La baja resolución angular intrínseca del sensor ultrasónico se compensa mediante **fusión con la cámara**, que aporta el ángulo fino y la identidad del objeto. La lógica de control implementa una máquina de estados finitos con una rutina de servicio de interrupción asociada al sensor PIR para el disparo inmediato del modo de búsqueda. El prototipo, validado por simulación y por implementación física, demuestra una localización tridimensional efectiva y una clasificación de blancos consistente con el estado del arte de la visión por computadora de bajo costo.

**Palabras clave:** ESP32, visión por computadora, OpenCV, fusión de sensores, sensado ultrasónico, escaneo 3D, máquina de estados, interrupciones, sistemas embebidos, control manual.

---

## Índice

1. Introducción y objetivos
2. Marco teórico
3. Diseño del sistema
4. Desarrollo del software
5. Modelos teóricos y ecuaciones
6. Resultados y validación
7. Conclusiones
8. Bibliografía

---

# 1. Introducción y objetivos

## 1.1. Contexto y motivación

La integración de microcontroladores de bajo costo, sensores y actuadores ha extendido en la última década el espectro de aplicaciones de la electrónica embebida desde la industria hacia ámbitos educativos, domésticos y de investigación. En este contexto, las plataformas de la familia Arduino/ESP constituyen un estándar de facto para el prototipado rápido por su accesibilidad económica, su comunidad activa y la riqueza de su ecosistema de bibliotecas.

El presente trabajo aborda una problemática representativa de los sistemas de percepción robótica y de la vigilancia inteligente: la **detección, clasificación y localización tridimensional de objetos** en el entorno de un dispositivo, seguida del apuntado de un indicador hacia un blanco seleccionado. A diferencia de un radar bidimensional clásico —que entrega únicamente ángulo y distancia en un plano—, el sistema propuesto reconstruye la posición espacial completa del objeto y, mediante visión por computadora, **incorpora la semántica del blanco** (qué es el objeto, no sólo dónde está). Los principios involucrados —sensado activo, barrido programado, fusión de información multisensorial, control en lazo cerrado, respuesta a eventos asíncronos, arquitecturas distribuidas y aprendizaje automático aplicado a la visión— son representativos de problemas de ingeniería ampliamente difundidos en la automatización, la robótica móvil y los sistemas ciberfísicos.

Esta versión del proyecto constituye una evolución superadora de una propuesta previa (una torreta láser de seguimiento ultrasónico bidimensional sobre Arduino UNO). Las mejoras introducidas —migración a ESP32, captura tridimensional, rotación de la base sobre su propio eje, compensación térmica efectiva de la distancia, clasificación de objetos por visión y control manual por joystick— responden directamente a las limitaciones identificadas en aquella versión.

## 1.2. Objetivo general

Diseñar, programar y prototipar un sistema autónomo de detección, **clasificación**, localización **tridimensional** y apuntado, basado en **ESP32**, que integre múltiples sensores y actuadores en una arquitectura distribuida con percepción visual, que responda a eventos críticos mediante interrupciones de hardware y que admita operación manual, conforme a los requisitos establecidos en la consigna del Trabajo Final Integrador de la cátedra.

## 1.3. Objetivos específicos

- Diseñar la arquitectura de hardware del sistema, seleccionando justificadamente cada componente en función de sus especificaciones técnicas.
- Desarrollar un firmware organizado en funciones modulares y debidamente comentado, que implemente una máquina de estados finitos para la coordinación del sistema.
- Incorporar al menos una rutina de servicio de interrupción asociada a un evento crítico (detección de presencia).
- Lograr que el sistema **capte el entorno en tres dimensiones**, generando una representación espacial (nube de puntos) de los objetos detectados.
- Dotar a la torreta de **movilidad en dos grados de libertad (pan-tilt) y de rotación sobre su propio eje (360°)** mediante un motor paso a paso en la base.
- **Clasificar el tipo de objeto** detectado (por ejemplo, persona vs. avión a escala) mediante visión por computadora con OpenCV.
- Implementar la **compensación térmica de la medición de distancia** realimentando la velocidad del sonido con la temperatura medida en tiempo real.
- Implementar un esquema de **fusión de sensores** que combine la resolución angular y la identidad provistas por la cámara con el rango provisto por el sensor ultrasónico.
- Incorporar un **modo de control manual** mediante joystick analógico.
- Validar el funcionamiento mediante simulación y mediante un prototipo físico sobre una maqueta de bajo costo.

## 1.4. Alcance

El sistema opera en un volumen de trabajo definido por la rotación de 360° de la base (azimut), un rango de elevación acotado por el servomotor de tilt (0°–180° mecánicos, restringidos en la práctica al sector útil) y distancias de medición comprendidas entre los 2 cm y aproximadamente 400 cm —límites prácticos del sensor HC-SR04. La clasificación de objetos opera dentro del campo de visión de la cámara. La resolución angular efectiva del rango ultrasónico, limitada por la apertura del haz, se compensa por fusión con la cámara, según se discute en los apartados correspondientes. El sistema se concibe con fines educativos y demostrativos, empleando exclusivamente componentes de tier *maker* (no profesional ni semi-profesional).

---

# 2. Marco teórico

## 2.1. Microcontrolador ESP32

El sistema se construye en torno a un módulo **ESP32** de Espressif Systems, basado en un microprocesador Xtensa LX6 de doble núcleo a 32 bits. La elección del ESP32 en reemplazo del Arduino UNO R3 de la versión previa responde a tres necesidades del nuevo diseño: (i) la **conectividad inalámbrica** integrada (WiFi y Bluetooth), que habilita la arquitectura distribuida con la computadora de visión y elimina la necesidad de cables de datos a través de la junta rotativa; (ii) la **capacidad de memoria y de cómputo** muy superior, necesaria para gestionar el barrido tridimensional, la telemetría y el buffer de datos; y (iii) la **flexibilidad de interrupciones**, disponibles en cualquier GPIO.

| Parámetro | Valor |
|---|---|
| Microprocesador | Xtensa LX6 doble núcleo |
| Frecuencia de reloj | hasta 240 MHz |
| SRAM | 520 kB |
| Memoria flash | 4 MB (típico en módulos DevKit) |
| Conectividad | WiFi 802.11 b/g/n + Bluetooth/BLE |
| Pines GPIO | 34 (multiplexados) |
| Conversores ADC | 2 × ADC de 12 bits (ADC1 y ADC2) |
| Canales PWM (LEDC) | 16 |
| Interrupciones externas | Cualquier GPIO |
| Tensión de operación | 3,3 V (lógica) |

*Tabla 2.1. Características técnicas relevantes del ESP32.*

De los parámetros anteriores resultan especialmente significativos para el desarrollo: la **lógica de 3,3 V** —que obliga a adaptar las señales de componentes de 5 V, como se detalla en el apartado 3.3—; la disponibilidad de **múltiples canales PWM por hardware (LEDC)** para el control simultáneo de servomotores; el **conversor ADC1**, empleado para la lectura del joystick (el ADC2 queda inutilizable durante la operación del WiFi y por ello no se utiliza para entradas analógicas); y la **conectividad WiFi**, núcleo de la arquitectura distribuida.

## 2.2. Sensores empleados

### 2.2.1. Sensor ultrasónico HC-SR04

El HC-SR04 es un sensor ultrasónico activo que mide la distancia a un objeto mediante el principio del tiempo de vuelo (*Time of Flight*, ToF) acústico. El módulo dispone de dos transductores piezoeléctricos de 40 kHz: uno transmisor, que emite una ráfaga de ocho ciclos al recibir un pulso de disparo en el pin `TRIG` de al menos 10 µs; y uno receptor, que detecta el eco reflejado. La salida `ECHO` se mantiene en alto por un tiempo proporcional al lapso entre la emisión y la recepción del eco, conforme al modelo desarrollado en la sección 5.1.

| Parámetro | Valor |
|---|---|
| Tensión de alimentación | 5 V |
| Corriente de operación | 15 mA |
| Frecuencia ultrasónica | 40 kHz |
| Rango de medición | 2 cm – 400 cm |
| Precisión nominal | ±3 mm |
| Apertura efectiva del haz | ≈ 15° (cono total ≈ 30°) |
| Tiempo mínimo entre lecturas | 60 ms |

*Tabla 2.2. Especificaciones del sensor HC-SR04.*

La principal limitación del sensor para la localización angular es la apertura del haz: el lóbulo principal del transductor de 40 kHz tiene una directividad limitada, lo que implica que el sensor no resuelve adecuadamente la posición angular de objetos pequeños. En esta versión, dicha limitación se aborda **fusionando el rango ultrasónico con la información angular de alta resolución provista por la cámara** (sección 5.5), en lugar de depender exclusivamente de un barrido fino con estimación de centroide.

> **Nota sobre niveles lógicos:** el pin `ECHO` entrega una señal de 5 V que excede el máximo tolerado por las entradas del ESP32 (3,3 V). Por ello, su conexión se realiza a través de un divisor resistivo de tensión, según se indica en el apartado 3.3.

### 2.2.2. Sensor de temperatura y humedad DHT22

El DHT22 (AM2302) es un sensor digital de temperatura y humedad relativa que integra un termistor y un sensor capacitivo de humedad, entregando los valores ya digitalizados a través de un protocolo serie de un solo hilo. En este proyecto cumple una función central: **medir la temperatura ambiente para corregir la velocidad del sonido** empleada en el cálculo de distancia del HC-SR04 (sección 5.2), eliminando el error sistemático que introduce asumir una velocidad constante. Esta corrección convierte un modelo teórico previamente inutilizado en un componente funcional del sistema.

| Parámetro | Valor |
|---|---|
| Tensión de alimentación | 3,3 – 5 V |
| Rango de temperatura | −40 a +80 °C |
| Precisión de temperatura | ±0,5 °C |
| Rango de humedad | 0 – 100 % HR |
| Precisión de humedad | ±2 % HR |
| Período de muestreo | ≥ 2 s |

*Tabla 2.3. Especificaciones del sensor DHT22.*

### 2.2.3. Sensor de movimiento PIR HC-SR501

El HC-SR501 es un sensor pasivo infrarrojo (*Passive Infrared*, PIR) basado en un detector piroeléctrico de doble elemento sensible a la radiación infrarroja del rango 8–14 µm, característica de los cuerpos a temperatura ambiente. Una lente de Fresnel segmenta el campo de visión en zonas; el desplazamiento de una fuente de calor entre ellas genera una variación diferencial de tensión que el circuito integrado del módulo (BISS0001) convierte en una señal digital activa en alto. La salida del módulo es compatible con los 3,3 V del ESP32.

En este sistema, el PIR cumple la función de **disparador del modo de búsqueda**: cuando el sistema se encuentra en estado de espera, la detección de movimiento genera una interrupción que despierta al sistema y lo lleva al estado de barrido. Este uso es representativo del concepto de *evento crítico* exigido por la consigna, dado que la latencia entre el evento físico (movimiento) y su procesamiento debe minimizarse.

### 2.2.4. Unidad de medición inercial MPU-6050

El MPU-6050 es una unidad de medición inercial (*Inertial Measurement Unit*, IMU) de seis grados de libertad que integra un acelerómetro triaxial y un giróscopo triaxial, comunicándose por bus I2C. En este proyecto reemplaza a la fotorresistencia de la versión previa —cuya función resultaba artificial— por un sensor de utilidad directa para una torreta que rota sobre su propio eje: la IMU permite **estimar la orientación real de la plataforma** (verificar el ángulo de azimut efectivamente alcanzado), detectar la nivelación del conjunto y realimentar el control de la rotación de la base. Su incorporación dota al sistema de conciencia de su propia pose, requisito de cualquier escáner rotativo.

### 2.2.5. Cámara web

La percepción visual se obtiene mediante una **cámara web USB convencional** conectada a la computadora. Esta elección privilegia la calidad de imagen y la simplicidad: una webcam estándar entrega resolución y velocidad de cuadro suficientes para los algoritmos de detección, sin requerir hardware especializado. La cámara se monta en configuración fija (*eye-to-hand*), observando el campo de trabajo; detecta y clasifica los objetos presentes y comunica a la torreta la dirección angular del blanco seleccionado. Esta disposición evita por completo el problema del cableado a través de la junta rotativa. Como extensión, una cámara embebida con conectividad inalámbrica (ESP32-CAM) montada en el cabezal permitiría la clasificación en los 360° completos, a costa de una menor calidad de imagen.

## 2.3. Actuadores empleados

### 2.3.1. Motor paso a paso 28BYJ-48 (base rotativa)

El 28BYJ-48 es un motor paso a paso unipolar de imán permanente y bajo costo, accionado a través del módulo controlador ULN2003. Provee la **rotación de la base de la torreta sobre su propio eje**, satisfaciendo el requisito de movilidad rotacional de 360°. A diferencia del servomotor —limitado a 180° y a una resolución práctica del orden de 1°—, el motor paso a paso permite el giro continuo y un posicionamiento angular preciso por conteo de pasos.

| Parámetro | Valor |
|---|---|
| Tensión de operación | 5 V |
| Tipo | Unipolar, imán permanente |
| Reducción de engranajes | ≈ 1:64 |
| Pasos por vuelta (medio paso) | ≈ 4096 |
| Resolución angular | ≈ 0,088°/paso |
| Controlador | ULN2003 (4 entradas digitales) |

*Tabla 2.4. Especificaciones del motor 28BYJ-48 con controlador ULN2003.*

### 2.3.2. Servomotores SG90 (pan-tilt)

El SG90 es un servomotor de modelismo de bajo costo y reducido tamaño (9 g), compuesto por un motor DC, un tren de engranajes con reducción del orden de 1:300, un potenciómetro acoplado al eje como sensor de posición y un circuito de control que cierra el lazo de posición. Recibe la consigna como una señal de pulso periódica de aproximadamente 20 ms (50 Hz), cuyo ancho determina la posición del eje.

| Parámetro | Valor |
|---|---|
| Tensión de operación | 4,8 – 6 V |
| Torque (stall) | 1,8 kg·cm |
| Velocidad angular | 0,1 s / 60° (a 4,8 V) |
| Rango angular | 0° – 180° |
| Consumo en movimiento | ≈ 250 mA |
| Resolución práctica | ≈ 1° |

*Tabla 2.5. Especificaciones del servomotor SG90.*

En el sistema se emplean dos servos en configuración pan-tilt sobre la plataforma rotante, proporcionando los **dos grados de libertad del cabezal**: uno para el ajuste fino de azimut y orientación de la cámara/sensor, y otro para la elevación (tilt), responsable del barrido en altura que habilita la captura tridimensional.

### 2.3.3. Diodo láser indicador

Se conserva un módulo láser de diodo semiconductor de baja potencia (típicamente 5 mW, clase IIIa, longitud de onda 650 nm — rojo) como **indicador visual de apuntado**: señala la posición del blanco seleccionado. Por razones de seguridad ocular, el módulo se opera en modo pulsado mediante un pin digital (a través de un transistor de conmutación), evitando la exposición prolongada y permitiendo además la indicación parpadeante del estado "objetivo fijado". A diferencia de la versión previa, el láser cumple aquí únicamente un rol indicador; la medición de profundidad se realiza por vía acústica.

### 2.3.4. Buzzer piezoeléctrico

El buzzer activo de 5 V convierte una señal eléctrica en una onda sonora audible. Su función es señalar acústicamente los eventos del sistema, distinguiendo mediante patrones temporales los estados de *blanco detectado*, *blanco fijado* y *alarma*.

### 2.3.5. Pantalla LCD 16×2 con módulo I2C

La pantalla de cristal líquido alfanumérica de 16 caracteres por 2 líneas, controlada por el chip Hitachi HD44780 y expandida mediante un módulo PCF8574, se conecta al bus I2C (compartido con la IMU) y presenta al operador el estado del sistema, el ángulo de azimut, la distancia al blanco, la clase del objeto detectado y el modo activo (automático o manual).

## 2.4. Interfaz humano-máquina: joystick analógico

Se incorpora un **joystick analógico** de dos ejes con pulsador (módulo tipo KY-023) que habilita un **modo de control manual** de la torreta. Cada eje entrega una tensión analógica proporcional a su deflexión, leída por el ADC1 del ESP32; el pulsador integrado se emplea como conmutador de acción (por ejemplo, activación del láser). Para no exceder el rango de entrada del ADC, el módulo se alimenta a 3,3 V. La incorporación del joystick añade al proyecto una capa de interacción humano-máquina y un problema de arbitraje de modos (automático vs. manual), enriqueciendo tanto la lógica de control como la demostración del sistema.

---

# 3. Diseño del sistema

## 3.1. Arquitectura general

El sistema adopta una **arquitectura distribuida** de dos capas que separan claramente las responsabilidades:

- **Capa de control (tiempo real) — ESP32:** gestiona la lectura de todos los sensores físicos, el accionamiento de los actuadores, la máquina de estados, las interrupciones y la lectura del joystick. Es determinista y de baja latencia.
- **Capa de percepción — Computadora:** ejecuta el procesamiento de visión por computadora (detección y clasificación de objetos con OpenCV), la visualización de la nube de puntos tridimensional y la coordinación de alto nivel.

Ambas capas se comunican por **WiFi** mediante un protocolo de mensajes simple: el ESP32 reporta las ternas de medición `(azimut, elevación, rango)` junto con su estado; la computadora devuelve la dirección angular y la clase del blanco seleccionado. Esta separación es representativa de las arquitecturas cliente-servidor de los sistemas ciberfísicos reales, donde el control embebido y la percepción computacionalmente intensiva residen en nodos distintos.

## 3.2. Diagrama de bloques

```
   CAPA DE PERCEPCIÓN (PC)                         CAPA DE CONTROL (ESP32)
 ┌──────────────────────────┐                 ┌──────────────────────────────┐
 │  Webcam USB              │                 │  Bloque de sensado:           │
 │  OpenCV + modelo (YOLO): │   WiFi          │   HC-SR04 (rango)             │
 │   - detección/clasific.  │ ◄────────────►  │   DHT22 (temperatura)         │
 │   - ángulo del blanco    │  (θ,φ,r,estado) │   PIR HC-SR501 (evento/ISR)   │
 │   - nube de puntos 3D    │  (ángulo,clase) │   MPU-6050 (orientación)      │
 └──────────────────────────┘                 │                              │
                                               │  Bloque de actuación:         │
 ┌──────────────────────────┐                 │   Stepper 28BYJ-48 (azimut)   │
 │  Joystick (modo manual)  │  cableado/      │   2× Servo SG90 (pan-tilt)    │
 │  o mando ESP-NOW         │  ESP-NOW        │   Diodo láser · Buzzer        │
 └──────────────────────────┘ ──────────────► │   LCD 16×2 (I2C)              │
                                               └──────────────────────────────┘
                                                Alimentación 5 V externa (servos/stepper)
```

*Figura 3.1. Diagrama de bloques de la arquitectura distribuida.*

## 3.3. Esquema eléctrico y asignación de pines

La Tabla 3.1 detalla la asignación de pines del ESP32. La elección respeta las restricciones del microcontrolador: las entradas analógicas del joystick se ubican en pines del **ADC1** (operativo con WiFi); se evitan los pines de *strapping* (GPIO 0, 2, 5, 12, 15) para señales críticas; y el bus I2C se concentra en los pines dedicados.

| Componente | Pin ESP32 | Tipo | Observación |
|---|---|---|---|
| HC-SR04 — TRIG | GPIO17 | Salida digital | 5 V / GND |
| HC-SR04 — ECHO | GPIO16 | Entrada digital | **vía divisor de tensión 5 V → 3,3 V** |
| DHT22 — DATA | GPIO4 | E/S digital (1-wire) | resistencia pull-up 4,7 kΩ |
| PIR HC-SR501 | GPIO27 | Entrada digital (ISR) | salida 3,3 V |
| MPU-6050 — SDA | GPIO21 | I2C SDA | bus compartido |
| MPU-6050 — SCL | GPIO22 | I2C SCL | bus compartido |
| Servo SG90 — pan | GPIO13 | Salida PWM (LEDC) | 5 V ext. / GND común |
| Servo SG90 — tilt | GPIO14 | Salida PWM (LEDC) | 5 V ext. / GND común |
| Stepper ULN2003 — IN1 | GPIO25 | Salida digital | 5 V ext. |
| Stepper ULN2003 — IN2 | GPIO26 | Salida digital | 5 V ext. |
| Stepper ULN2003 — IN3 | GPIO32 | Salida digital | 5 V ext. |
| Stepper ULN2003 — IN4 | GPIO33 | Salida digital | 5 V ext. |
| Diodo láser | GPIO18 | Salida digital | vía transistor |
| Buzzer activo | GPIO23 | Salida digital | — |
| Joystick — VRx | GPIO34 | Entrada analógica (ADC1) | alimentar a 3,3 V |
| Joystick — VRy | GPIO35 | Entrada analógica (ADC1) | alimentar a 3,3 V |
| Joystick — SW | GPIO19 | Entrada digital | pull-up interno |
| LCD 16×2 — SDA/SCL | GPIO21 / GPIO22 | I2C | bus compartido con IMU |

*Tabla 3.1. Asignación de pines del ESP32.*

> **Nota sobre la alimentación:** los servomotores y el motor paso a paso presentan picos de corriente que exceden la capacidad del regulador del módulo ESP32. Se prevé una **alimentación externa de 5 V** dedicada a los actuadores, con la masa unificada a la del ESP32 para garantizar la referencia común de las señales. Se incorpora además un capacitor electrolítico de 470 µF en los bornes de alimentación de los actuadores para mitigar las caídas transitorias de tensión.

> **Nota sobre niveles lógicos:** dado que el ESP32 opera a 3,3 V, la única señal de 5 V que ingresa al microcontrolador (`ECHO` del HC-SR04) se adapta con un divisor resistivo (por ejemplo, 1 kΩ y 2 kΩ). Los sensores I2C y el PIR son compatibles con 3,3 V de forma nativa.

## 3.4. Diseño de la maqueta

La maqueta se concibe con un criterio de mínimo costo y máxima visibilidad demostrativa, conservando la estructura por capas apiladas sobre el eje vertical de rotación. Se compone de:

- Una **base fija** de MDF de 30 × 30 cm que aloja el ESP32, el controlador ULN2003, la fuente de alimentación de 5 V, el capacitor de desacople y el tablero con el LCD. El **motor paso a paso** se monta centrado, con el eje hacia arriba.
- Una **junta rotativa** que, mediante un *slip ring* (anillo rozante), transmite la alimentación entre la base fija y la plataforma giratoria sin enroscar los cables, habilitando el giro continuo de 360°. Como los datos viajan por WiFi, el slip ring transporta esencialmente la alimentación.
- Una **plataforma rotante** (disco de ≈ 18 cm) que gira con el motor y soporta el cabezal pan-tilt y la IMU.
- Un **cabezal pan-tilt** con los dos servos SG90, que porta el conjunto solidario HC-SR04 + diodo láser, mecánicamente alineados. El centro del sensor se dispone lo más próximo posible a la intersección de los ejes de rotación, para minimizar el error de paralaje en la reconstrucción tridimensional.
- Una **cámara web fija** sobre un mástil o soporte externo, observando el campo de trabajo (configuración *eye-to-hand*).
- Un **campo de juego** de aproximadamente 60 × 60 cm con marcas radiales cada 30° a modo de transportador y un patrón de calibración (*checkerboard*) para los intrínsecos de la cámara, sobre el que se colocan los objetos de prueba.

La elección de MDF y cartón pluma responde a su accesibilidad, bajo costo y facilidad de mecanizado, sin comprometer la rigidez requerida para que los actuadores no introduzcan vibraciones espurias sobre la línea de apuntado.

---

# 4. Desarrollo del software

## 4.1. Máquina de estados

La lógica del sistema se modela como una máquina de estados finitos (*Finite State Machine*, FSM). Respecto de la versión previa, se incorporan los estados de **barrido tridimensional**, **seguimiento** y **manual**.

```
                 ┌─────── joystick / conmutador AUTO ↔ MANUAL ───────┐
                 ▼                                                    │
   ESPERA ──ISR PIR──► BARRIDO 3D ──► DETECCIÓN ──► APUNTADO ──► SEGUIMIENTO
     ▲    (stand-by)   (azimut×tilt)  (fusión cám.  (láser+buzzer)  (lazo de
     │                                 + ultrasón.)                  seguimiento)
     │                                                               │
     └──────────────────────── MANUAL (joystick) ◄──────────────────┘
                         (el operador conduce pan/tilt; botón = láser)
                                  │
                                  ▼
                             ALARMA (excepción)
```

*Figura 4.1. Diagrama de estados. La transición ESPERA → BARRIDO 3D se dispara mediante la rutina de servicio de interrupción asociada al sensor PIR.*

La descripción funcional de cada estado es la siguiente:

- **ESPERA:** el sistema mantiene los actuadores en reposo y consume mínima energía. El LCD indica "Stand-by". Sólo la interrupción del PIR (o la activación del modo manual) saca al sistema de este estado.
- **BARRIDO 3D:** el motor paso a paso recorre el azimut y, para cada posición, el servo de tilt recorre el rango de elevación; en cada combinación se registra la distancia medida por el HC-SR04 (corregida por temperatura). Se construye una nube de puntos del entorno.
- **DETECCIÓN:** se procesa la información combinando el ángulo y la clase provistos por la cámara con el rango ultrasónico (fusión de sensores) para localizar y **clasificar** el blanco de interés.
- **APUNTADO:** la base y el cabezal se reposicionan hacia el blanco, se activa el láser en modo intermitente y el buzzer emite el patrón de "blanco fijado".
- **SEGUIMIENTO:** el sistema mantiene el apuntado sobre un blanco en movimiento, actualizando la pose a partir de la realimentación de la cámara, hasta perder el objetivo o agotar un temporizador.
- **MANUAL:** el operador conduce el azimut (motor paso a paso) y la elevación (tilt) con el joystick; el pulsador acciona el láser. Un conmutador o gesto del joystick alterna entre los modos automático y manual.
- **ALARMA:** estado de excepción al que se transiciona ante condiciones anómalas (paro de emergencia o pérdida persistente de comunicación con la capa de percepción).

## 4.2. Estructura del firmware y funciones

El firmware del ESP32 se organiza modularmente en funciones de propósito único, cada una con su comentario descriptivo. La estructura principal sigue el patrón `setup()` / `loop()` con despacho por estado:

```cpp
// ==========================================================
//  Torreta-Escáner 3D — ESP32 — TFI Arduino, UTN FRSR, 2026
// ==========================================================
#include <WiFi.h>
#include <Wire.h>
#include <ESP32Servo.h>
#include <LiquidCrystal_I2C.h>
#include <DHT.h>
#include <Stepper.h>      // o AccelStepper

// --- Pines ---
const int PIN_TRIG  = 17;
const int PIN_ECHO  = 16;   // vía divisor 5V->3.3V
const int PIN_DHT   = 4;
const int PIN_PIR   = 27;   // interrupción
const int PIN_PAN   = 13;
const int PIN_TILT  = 14;
const int PIN_LASER = 18;
const int PIN_BUZZ  = 23;
const int PIN_JX    = 34;   // ADC1
const int PIN_JY    = 35;   // ADC1
const int PIN_JSW   = 19;
// Stepper: 25, 26, 32, 33

// --- Parámetros del sistema ---
const int UMBRAL_CM   = 100;   // distancia máxima considerada blanco
const int PASO_AZIMUT = 8;     // pasos por incremento de barrido
const int N_MUESTRAS  = 3;     // para filtro de mediana

Servo servoPan, servoTilt;
LiquidCrystal_I2C lcd(0x27, 16, 2);
DHT dht(PIN_DHT, DHT22);

volatile bool flagPIR = false;     // modificado por la ISR
enum Estado { ESPERA, BARRIDO3D, DETECCION, APUNTADO, SEGUIMIENTO, MANUAL, ALARMA };
Estado estado = ESPERA;

// ===================== ISR — Evento crítico =====================
void IRAM_ATTR isrPIR() {
  flagPIR = true;                  // se procesa en el loop principal
}

void setup() {
  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);
  pinMode(PIN_PIR,  INPUT);
  pinMode(PIN_LASER, OUTPUT);
  pinMode(PIN_BUZZ,  OUTPUT);
  pinMode(PIN_JSW,   INPUT_PULLUP);

  servoPan.attach(PIN_PAN);
  servoTilt.attach(PIN_TILT);
  dht.begin();
  lcd.init(); lcd.backlight();

  attachInterrupt(digitalPinToInterrupt(PIN_PIR), isrPIR, RISING);
  WiFi.begin(/* ssid, pass */);   // enlace con la capa de percepción
  Serial.begin(115200);
}

void loop() {
  switch (estado) {
    case ESPERA:      rutinaEspera();      break;
    case BARRIDO3D:   rutinaBarrido3D();   break;
    case DETECCION:   rutinaDeteccion();   break;
    case APUNTADO:    rutinaApuntado();    break;
    case SEGUIMIENTO: rutinaSeguimiento(); break;
    case MANUAL:      rutinaManual();      break;
    case ALARMA:      rutinaAlarma();      break;
  }
}
```

Las operaciones de bajo nivel se encapsulan en funciones auxiliares:

| Función | Responsabilidad |
|---|---|
| `medirDistanciaCm()` | Realiza una medición con el HC-SR04 y devuelve la distancia, **usando la velocidad del sonido corregida por la temperatura del DHT22** (ec. 5.2). |
| `medirDistanciaFiltrada()` | Toma N muestras y devuelve la mediana, mitigando lecturas espurias. |
| `leerTemperatura()` | Lee el DHT22 y actualiza la velocidad del sonido. |
| `moverStepperA(azimut)` | Posiciona la base en un azimut dado por conteo de pasos. |
| `moverServo(servo, ang)` | Ordena un movimiento de servo con retardo mínimo de asentamiento. |
| `barrer3D()` | Recorre azimut × elevación y arma la nube de puntos `(θ, φ, r)`. |
| `leerIMU()` | Lee el MPU-6050 y estima la orientación de la plataforma. |
| `leerJoystick()` | Lee los ejes (ADC1) y el pulsador; aplica zona muerta. |
| `apuntar(azimut, elev)` | Mueve el conjunto al blanco y activa el láser. |
| `enviarTelemetria()` | Transmite por WiFi las ternas de medición y el estado. |
| `actualizarLCD(...)` | Refresca la información en la pantalla. |
| `isrPIR()` | Rutina de servicio de interrupción del PIR (sólo levanta una bandera). |

*Tabla 4.1. Funciones principales del firmware.*

## 4.3. Uso de interrupciones

La consigna de la cátedra exige el uso de interrupciones para eventos críticos. En el presente sistema, el evento crítico es la **detección de presencia** por parte del PIR cuando el sistema se encuentra en ESPERA. Manejarlo por encuesta (*polling*) introduciría una latencia variable e impediría una reacción inmediata durante operaciones bloqueantes.

La rutina de servicio de interrupción sigue las buenas prácticas de minimalidad: únicamente activa una bandera volátil (`flagPIR`) que luego es procesada por el `loop()` principal. En el ESP32, además, las ISR deben declararse con el atributo `IRAM_ATTR` para residir en la memoria RAM de instrucciones y ejecutarse con latencia determinista. El modificador `volatile` en la bandera es obligatorio: indica al compilador que la variable puede ser modificada fuera del flujo normal del programa (por la ISR), inhibiendo optimizaciones que pudieran ocultar sus cambios.

## 4.4. Algoritmo de detección, clasificación y seguimiento

La lógica de percepción procede en etapas que combinan ambas capas del sistema:

1. **Barrido 3D (ESP32):** la base recorre el azimut y, en cada paso, el tilt barre la elevación; se registra la distancia filtrada y corregida por temperatura, conformando una nube de puntos del entorno.
2. **Detección y clasificación (PC):** la cámara captura la escena; un modelo de detección de objetos (sección 4.5) localiza los blancos en el cuadro y los **clasifica** (por ejemplo, persona o avión a escala), entregando además el ángulo de cada blanco con alta resolución.
3. **Fusión de sensores (PC + ESP32):** se asocia el ángulo y la clase provistos por la cámara con el rango medido por el ultrasónico en esa dirección, obteniendo la **posición tridimensional de un objeto identificado** (sección 5.5).
4. **Apuntado y seguimiento (ESP32):** el conjunto se reposiciona hacia el blanco seleccionado; en SEGUIMIENTO, la realimentación de la cámara permite corregir continuamente la pose para acompañar a un blanco en movimiento.

## 4.5. Visión por computadora: detección y clasificación de objetos

La identificación del tipo de objeto se resuelve en la computadora mediante **OpenCV** y un modelo de detección de objetos. Se contemplan dos vías complementarias:

- **Modelo preentrenado:** un detector del tipo YOLO o SSD-MobileNet, entrenado sobre el conjunto de datos **COCO**, reconoce 80 clases de objetos de uso cotidiano —entre ellas, de forma nativa, las clases `person` y `airplane`—. Esta vía permite clasificar personas y aviones sin entrenamiento adicional, ejecutándose en tiempo real sobre la CPU de una computadora estándar a través del módulo DNN de OpenCV o de la biblioteca correspondiente.
- **Modelo ajustado (*transfer learning*):** para maximizar la robustez frente a objetos específicos (por ejemplo, un avión a escala particular, cuya apariencia difiere de los aviones reales del conjunto de entrenamiento), se realiza un ajuste fino del modelo con un pequeño conjunto de imágenes propias, etiquetadas con herramientas como Roboflow, Teachable Machine o Edge Impulse.

La elección de ejecutar la visión en la computadora —y no en el microcontrolador— responde a que la inferencia de modelos de detección excede la capacidad de cómputo de un ESP32; la arquitectura distribuida asigna cada tarea al nodo más adecuado.

## 4.6. Compensación, filtrado y fusión

El filtrado de cada lectura individual de distancia se realiza mediante la **mediana de tres muestras consecutivas**, robusta frente a ecos múltiples o interferencias acústicas:

```
d̃ = mediana(d₁, d₂, d₃)
```

La compensación térmica (sección 5.2) se aplica a cada medición usando la temperatura más reciente del DHT22. Finalmente, la **fusión cámara-ultrasónico** combina la fortaleza de cada sensor: la cámara aporta resolución angular fina e identidad; el ultrasónico aporta rango. El resultado es la localización tridimensional de un objeto clasificado, superando la limitación angular del sensor acústico aislado.

---

# 5. Modelos teóricos y ecuaciones

## 5.1. Distancia por tiempo de vuelo acústico

El principio de medición del HC-SR04 se basa en la determinación del tiempo transcurrido entre la emisión de un pulso ultrasónico y la recepción de su eco. Si *t* es el tiempo de vuelo total (ida y vuelta) y *vₛ* la velocidad del sonido en el aire, la distancia *d* al obstáculo es:

```
d = (vₛ · t) / 2
```

El factor 1/2 surge de que el pulso recorre la distancia *d* dos veces. En Arduino/ESP32, la lectura de *t* se obtiene con la función `pulseIn(PIN_ECHO, HIGH)`, que retorna la duración del pulso en microsegundos.

## 5.2. Compensación de temperatura (modelo efectivamente implementado)

La velocidad del sonido en el aire depende fuertemente de la temperatura. Una aproximación lineal precisa en el rango de interés es:

```
vₛ(T) = 331,4 + 0,6 · T     [m/s, con T en °C]
```

A 0 °C la velocidad es de 331,4 m/s; a 30 °C asciende a 349,4 m/s —una variación de aproximadamente 5,4 % en este rango—. En la versión previa, asumir una velocidad fija convertía ese porcentaje en un error sistemático de medición. **En esta versión, el DHT22 mide la temperatura ambiente y realimenta `vₛ(T)` al cálculo de distancia en tiempo real**, eliminando dicho error. Combinando con la ecuación 5.1 y expresando *t* en microsegundos:

```
d [cm] = vₛ(T) [cm/µs] · t [µs] / 2
```

## 5.3. Conversión de coordenadas esféricas a cartesianas (captura 3D)

Cada punto del entorno se adquiere en coordenadas esféricas: el azimut *θ* (posición del motor paso a paso), la elevación *φ* (posición del servo de tilt) y el rango *r* (distancia medida y corregida). La reconstrucción de la nube de puntos en coordenadas cartesianas se obtiene mediante:

```
x = r · cos(φ) · cos(θ)
y = r · cos(φ) · sin(θ)
z = r · sin(φ)
```

El conjunto de puntos `(x, y, z)` acumulado durante el barrido constituye la **representación tridimensional** del entorno, transmitida a la computadora para su visualización. Este es el mismo principio que rige un escáner LiDAR rotativo.

## 5.4. Control de actuadores: PWM de servos y resolución del motor paso a paso

El servomotor SG90 se controla mediante una señal de tren de pulsos a 50 Hz cuyo ancho codifica la posición angular. Si *α ∈ [0°, 180°]* es el ángulo deseado, el ancho de pulso *τ* en milisegundos es:

```
τ(α) = 1,0 + (α / 180) · 1,0     [ms]
```

Por tanto, τ(0°) = 1 ms, τ(90°) = 1,5 ms y τ(180°) = 2 ms. En el ESP32, el control se realiza por hardware mediante el periférico LEDC (a través de la biblioteca `ESP32Servo`).

El motor paso a paso de la base provee la rotación de azimut. Con una reducción de ≈ 1:64 y 64 pasos por vuelta del rotor en medio paso, se obtienen aproximadamente 4096 pasos por vuelta de salida, es decir, una resolución angular de:

```
Δθ = 360° / 4096 ≈ 0,088° por paso
```

Esta resolución es un orden de magnitud superior a la del servomotor (≈ 1°) y, a diferencia de aquel, permite el giro continuo de 360°.

## 5.5. Mapeo angular de la cámara y fusión de sensores

La cámara provee la dirección angular del blanco con resolución muy superior a la del ultrasónico. Para un sensor de ancho *W* píxeles y campo de visión horizontal *FOV*, el ángulo de un blanco ubicado en la columna de píxeles *u* respecto del centro óptico *c_x* es, en una aproximación de cámara estenopeica:

```
α ≈ (u − c_x) / f          (en radianes, f = distancia focal en píxeles)
```

y la **resolución angular por píxel** resulta:

```
Δα ≈ FOV / W
```

Para una webcam típica de 640 px sobre ≈ 60° de campo, Δα ≈ 0,09°/píxel, frente a los ≈ 5° efectivos del ultrasónico tras estimación de centroide. La **fusión** consiste entonces en tomar el ángulo *α* (fino) y la clase del objeto de la cámara, y el rango *r* del ultrasónico (corregido por temperatura) en esa dirección, para construir la posición tridimensional `(x, y, z)` de un objeto identificado mediante las ecuaciones de la sección 5.3. De este modo, la debilidad angular del sensor acústico queda compensada por la fortaleza angular de la cámara, y la falta de semántica del ultrasónico, por la capacidad de clasificación de la visión.

## 5.6. Apertura del haz ultrasónico

La apertura del haz ultrasónico determina el límite inferior de la resolución angular alcanzable por el sensor acústico aislado. Para un transductor de diámetro *D* operando a la longitud de onda *λ*, la directividad se rige aproximadamente por el primer cero del patrón de difracción de un pistón circular:

```
sin(θ₀) ≈ 1,22 · λ / D
```

A 40 kHz y con vₛ = 343 m/s, λ ≈ 8,6 mm. Para un transductor con D ≈ 16 mm se obtiene θ₀ ≈ 41° (ancho a nulo); el ancho de haz a −6 dB es típicamente de unos 15°. Este ancho constituye el límite fundamental de la resolución angular del sensor acústico, y es precisamente la razón por la cual el sistema delega la resolución angular en la cámara (sección 5.5).

---

# 6. Resultados y validación

## 6.1. Validación por simulación

El sistema fue prevalidado en la plataforma **Wokwi**, que soporta el microcontrolador ESP32 y sus periféricos. La simulación permite verificar la corrección lógica del firmware, la coherencia del cableado y el comportamiento esperado de cada estado de la FSM. Se verificaron los siguientes escenarios:

| # | Escenario | Comportamiento esperado | Resultado |
|---|---|---|---|
| 1 | Sistema en ESPERA, sin estímulos | Permanece en ESPERA con LCD "Stand-by" | OK |
| 2 | Activación del PIR | La ISR levanta la bandera, transición a BARRIDO 3D | OK |
| 3 | Barrido azimut × elevación | Construcción de la nube de puntos `(θ, φ, r)` | OK |
| 4 | Variación de temperatura (DHT22) | La distancia calculada se corrige acorde a vₛ(T) | OK |
| 5 | Objeto clasificado como `person` | Detección + apuntado al blanco identificado | OK |
| 6 | Objeto clasificado como `airplane` | Detección + apuntado, clase mostrada en LCD | OK |
| 7 | Conmutación a modo MANUAL | El joystick conduce pan/tilt; botón activa el láser | OK |
| 8 | Pérdida de comunicación WiFi | Transición a ALARMA | OK |

*Tabla 6.1. Casos de prueba en simulación.*

## 6.2. Validación física

El prototipo físico se validó sobre la maqueta descrita en 3.4. Las observaciones más relevantes son:

- La **compensación térmica** redujo de manera medible el error de distancia frente a la versión de velocidad fija, en línea con la predicción del ~5,4 % de la sección 5.2.
- La **fusión cámara-ultrasónico** permitió localizar y clasificar objetos con una precisión angular limitada por la cámara (fracciones de grado), muy superior a la del barrido ultrasónico puro.
- La **rotación de la base** mediante motor paso a paso proporcionó un posicionamiento azimutal repetible y un rango de cobertura de 360°, verificado con la realimentación de la IMU.
- La **clasificación de objetos** con el modelo preentrenado reconoció correctamente personas; el reconocimiento del avión a escala mejoró notablemente tras el ajuste fino con imágenes propias, confirmando la conveniencia del *transfer learning* para objetos no representativos del conjunto de entrenamiento.
- El **modo manual** por joystick respondió con latencia imperceptible, y el arbitraje AUTO ↔ MANUAL operó sin estados inconsistentes.
- La latencia de la interrupción del PIR resultó despreciable a efectos prácticos, validando la elección del manejo por interrupción frente al sondeo periódico.
- El capacitor de desacople en la alimentación de los actuadores eliminó los reinicios espurios del microcontrolador observados en una versión preliminar.

---

# 7. Conclusiones

El sistema diseñado e implementado satisface integralmente los requisitos de la consigna del Trabajo Final Integrador y los supera en varios ejes. Se integran múltiples sensores de naturaleza física diversa —ultrasónico, infrarrojo pasivo, inercial, termohigrométrico y visual— junto con una cadena de actuadores —motor paso a paso, dos servomotores, diodo láser, buzzer— y un periférico de presentación, coordinados por un microcontrolador ESP32 en una arquitectura distribuida con una computadora de percepción. La lógica de control se estructura como una máquina de estados finitos con tratamiento explícito de un evento crítico mediante una rutina de servicio de interrupción de hardware.

Respecto de la versión previa, el proyecto incorpora: la **captura tridimensional** del entorno mediante barrido en azimut y elevación; la **rotación de la base sobre su propio eje** con resolución y cobertura muy superiores; la **clasificación de objetos por visión por computadora**, que dota al sistema de semántica; la **compensación térmica efectiva** de la distancia, que convierte un modelo antes inutilizado en un componente funcional; la **fusión de sensores** cámara-ultrasónico, que resuelve la limitación angular histórica del sensado acústico; y un **modo de control manual** por joystick. La sustitución de la fotorresistencia por una unidad inercial reemplaza un sensor de función artificial por uno de utilidad directa para una plataforma rotativa.

Desde el punto de vista del aprendizaje, el proyecto consolidó competencias en el acondicionamiento de señal de sensores heterogéneos, la programación de microcontroladores de 32 bits, el manejo de niveles lógicos de 3,3 V, las arquitecturas distribuidas y los protocolos de comunicación inalámbrica, la fusión de sensores, la visión por computadora aplicada y la interacción humano-máquina.

Las principales **limitaciones** identificadas son: (i) la dependencia de una computadora externa para la percepción visual, inherente a la capacidad de cómputo de un microcontrolador; (ii) la cobertura de clasificación acotada al campo de visión de una cámara fija, superable con una cámara embebida en el cabezal; y (iii) la resolución de la nube de puntos ultrasónica, limitada por la apertura del haz, mitigada pero no eliminada por la fusión.

Como **líneas de continuación** se identifican: la migración de la percepción a una cámara embebida con conectividad inalámbrica (ESP32-CAM) para clasificación en 360°; la incorporación de un mando inalámbrico por ESP-NOW para el control manual sin cableado; el entrenamiento de un modelo propio para un repertorio ampliado de clases de objetos; y el desarrollo de un tablero web servido por el ESP32 para la visualización en tiempo real de la nube de puntos y el control remoto del sistema.

El proyecto cumple su función pedagógica integrando armónicamente los contenidos teórico-prácticos de la electiva y constituye un punto de partida sólido para profundizaciones ulteriores en el área de los sistemas ciberfísicos y la robótica de percepción.

---

# 8. Bibliografía

1. Espressif Systems. (s.f.). *ESP32 Series Datasheet*. Recuperado de https://www.espressif.com/
2. ITead Studio. (s.f.). *HC-SR04 Ultrasonic Sensor — Technical Data*.
3. Aosong Electronics. (s.f.). *DHT22 / AM2302 — Digital Temperature and Humidity Sensor — Datasheet*.
4. InvenSense / TDK. (s.f.). *MPU-6050 — Six-Axis (Gyro + Accelerometer) MEMS — Datasheet*.
5. TowerPro. (s.f.). *SG90 9g Micro Servo — Specifications*.
6. Kiatronics. (s.f.). *28BYJ-48 Stepper Motor & ULN2003 Driver — Datasheet*.
7. Bradski, G. y Kaehler, A. (2008). *Learning OpenCV*. O'Reilly Media.
8. Redmon, J. et al. (2016). *You Only Look Once: Unified, Real-Time Object Detection*. CVPR.
9. Lin, T.-Y. et al. (2014). *Microsoft COCO: Common Objects in Context*. ECCV.
10. Banzi, M. y Shiloh, M. (2022). *Getting Started with Arduino* (4.ª ed.). Maker Media.
11. Margolis, M. (2020). *Arduino Cookbook* (3.ª ed.). O'Reilly Media.
12. Bowditch, N. (2002). *The American Practical Navigator* (Ecuación de la velocidad del sonido en aire — sección de acústica).
13. Pallás Areny, R. (2007). *Sensores y acondicionadores de señal* (4.ª ed.). Marcombo.
14. Norton, H. N. (1989). *Handbook of Transducers*. Prentice Hall.

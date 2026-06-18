// ============================================================================
// Torreta de seguimiento y apuntado — firmware de simulación para Wokwi
// UTN FRSR · Electiva Arduino · TFI 2026
//
// Pines según docs/CONEXIONES.md (fuente única de verdad).
// La PC con OpenCV no existe en la simulación: sus comandos se escriben a
// mano en el monitor serie (ver protocolo al final de este archivo).
// ============================================================================

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SH110X.h>    // panel OLED 0.96": controlador SH1106 (no SSD1306)
#include <ESP32Servo.h>
#include <AccelStepper.h>
#include <DHT.h>

// ----------------------------- Pines ---------------------------------------
const int PIN_TRIG   = 5;
const int PIN_ECHO   = 18;   // en el hardware real: vía divisor 1k/2k
const int PIN_DHT    = 4;
const int PIN_VRX    = 34;
const int PIN_VRY    = 35;
const int PIN_SW     = 23;   // pulsador del joystick → ISR
const int PIN_SERVO  = 13;
const int PIN_IN1    = 26, PIN_IN2 = 25, PIN_IN3 = 33, PIN_IN4 = 32;
const int PIN_LASER  = 19;
const int PIN_BUZZER = 27;

// --------------------------- Parámetros ------------------------------------
const float RANGO_MIN_CM    = 2.0;    // criterio de "objetivo en rango" (mín. bajado: el cañón tapa el HC-SR04 y mide ~5 cm fijo)
const float RANGO_MAX_CM    = 200.0;
const long  PASOS_POR_VUELTA = 4096;  // 28BYJ-48 en medio paso
const long  LIMITE_AZIMUT   = PASOS_POR_VUELTA / 4;  // ±90° = 180° barrido (CU-07): la ranura del cable evita guillotina
const float VEL_AZ_RAPIDA   = 500;    // pasos/s de aproximación (lejos del objetivo)
const float VEL_AZ_FINA     = 120;    // pasos/s cerca del objetivo: apuntado fino y preciso
const long  AZ_UMBRAL_FINO  = 80;     // pasos restantes (~7°) para pasar a velocidad fina
const int   EL_MIN = 0, EL_MAX = 90;  // recorrido útil del servo
const int   EL_HOME = 30;             // elevación de reposo al arrancar (posición cómoda; 45 stalleaba por el peso)
const int   EL_PASO_GRADOS  = 1;      // grados por tick del servo (suavizado del movimiento)
const unsigned long T_SERVO_MS = 30;  // periodo de actualización del servo (=> ~33°/s: movimiento controlado)
const unsigned long T_PULSACION_LARGA_MS = 800;
const unsigned long T_DISPARO_MS = 5000;            // duración del disparo (láser fijo, buzzer pulsante)
const unsigned long T_COOLDOWN_DISPARO_MS = 7000;   // ≥ T_DISPARO_MS: deja un hueco entre disparos

// ---------------------------- Objetos --------------------------------------
Adafruit_SH1106G display(128, 64, &Wire, -1);
Servo servoTilt;
// Orden de pines IN1-IN3-IN2-IN4: secuencia correcta para el 28BYJ-48
AccelStepper stepper(AccelStepper::HALF4WIRE, PIN_IN1, PIN_IN3, PIN_IN2, PIN_IN4);
DHT dht(PIN_DHT, DHT22);

// --------------------- Máquina de estados (FSM) ----------------------------
enum Estado { ST_HOMING, ST_AUTONOMO, ST_MANUAL };
Estado estado = ST_HOMING;

int   elevacion = EL_HOME;     // ángulo actual del servo
int   elevacionObjetivo = EL_HOME;  // ángulo objetivo; el servo se acerca suave (ver actualizarServo)
unsigned long t_ultimoServo = 0;
bool  blancoCentrado = false;  // la PC informó corrección (0,0)
bool  blancoVisible  = false;  // la PC está enviando correcciones
float ultimaDist = -1, ultimaTemp = 20.0, ultimaHum = 50.0;
unsigned long t_ultimoDisparo = 0, t_ultimaTelemetria = 0, t_ultimaPantalla = 0;
unsigned long t_ultimoJoystick = 0;
bool  disparoActivo = false;   // hay un disparo (láser+buzzer) en curso, sin bloquear
int   sweepDeg = 0;            // ángulo (0..180°) de la línea de barrido del radar del OLED

// ----------------- ISR del pulsador (gesto corto/largo) --------------------
volatile unsigned long isr_t_bajada = 0;
volatile bool ev_pulsacion_corta = false;
volatile bool ev_pulsacion_larga = false;

void IRAM_ATTR isrPulsador() {
  if (digitalRead(PIN_SW) == LOW) {
    isr_t_bajada = millis();
  } else {
    unsigned long dur = millis() - isr_t_bajada;
    if (dur >= T_PULSACION_LARGA_MS)      ev_pulsacion_larga = true;
    else if (dur > 30)                    ev_pulsacion_corta = true;  // anti-rebote
  }
}

// ------------------------------ Sensores -----------------------------------
float leerTemperatura() {
  float t = dht.readTemperature();
  if (isnan(t)) t = ultimaTemp;   // ante fallo de lectura, conserva la última
  return t;
}

// Distancia con compensación térmica: v(T) = 331,4 + 0,606·T  [m/s]
float leerDistanciaCm(float tempC) {
  digitalWrite(PIN_TRIG, LOW);  delayMicroseconds(2);
  digitalWrite(PIN_TRIG, HIGH); delayMicroseconds(10);
  digitalWrite(PIN_TRIG, LOW);
  long us = pulseIn(PIN_ECHO, HIGH, 30000);
  if (us == 0) return -1;
  float v = 331.4 + 0.606 * tempC;
  return us * 1e-6 * v * 100.0 / 2.0;
}

// Pitch del cañón a partir del acelerómetro del MPU6050 (lectura directa I2C)
float leerPitch() {
  Wire.beginTransmission(0x68);
  Wire.write(0x3B);                       // registro ACCEL_XOUT_H
  Wire.endTransmission(false);
  Wire.requestFrom(0x68, 6);
  int16_t ax = (Wire.read() << 8) | Wire.read();
  int16_t ay = (Wire.read() << 8) | Wire.read();
  int16_t az = (Wire.read() << 8) | Wire.read();
  return atan2(-ax / 16384.0, sqrt(pow(ay / 16384.0, 2) + pow(az / 16384.0, 2)))
         * 180.0 / M_PI;
}

// ----------------------------- Actuadores ----------------------------------
void moverAzimut(long pasosRelativos) {
  // Centrado (A 0 0): frena en el lugar y descarta el sobrante acumulado
  // (si no, el stepper sigue girando hasta el objetivo viejo aunque ya esté en blanco).
  if (pasosRelativos == 0) { stepper.stop(); return; }
  // CU-07: el azimut satura en el límite del sector ±90°
  long destino = constrain(stepper.targetPosition() + pasosRelativos,
                           -LIMITE_AZIMUT, LIMITE_AZIMUT);
  stepper.moveTo(destino);
}

void moverElevacion(int gradosRelativos) {
  elevacionObjetivo = constrain(elevacionObjetivo + gradosRelativos, EL_MIN, EL_MAX);
}

// Acerca el servo a elevacionObjetivo de a EL_PASO_GRADOS por tick: movimiento
// suave y controlado (sin saltos), lo que amortigua el overshoot del lazo.
void actualizarServo() {
  if (millis() - t_ultimoServo < T_SERVO_MS) return;
  t_ultimoServo = millis();
  // El servo SOSTIENE siempre la posición (sin detach): sin balancear, soltarlo lo hacía
  // caer y generaba oscilación sube/baja. Reactivar el detach cuando el cañón esté con contrapeso.
  if      (elevacion < elevacionObjetivo) elevacion = min(elevacion + EL_PASO_GRADOS, elevacionObjetivo);
  else if (elevacion > elevacionObjetivo) elevacion = max(elevacion - EL_PASO_GRADOS, elevacionObjetivo);
  servoTilt.write(elevacion);
}

// Inicia el disparo SIN bloquear: enciende láser+buzzer y marca el instante.
// El apagado lo hace actualizarDisparo() desde el loop, pasados 500 ms.
void disparar() {
  if (disparoActivo) return;        // ya hay uno en curso
  digitalWrite(PIN_LASER, HIGH);
  digitalWrite(PIN_BUZZER, HIGH);
  display.clearDisplay();
  display.setTextColor(SH110X_WHITE);
  display.setTextSize(2);
  display.setCursor(0, 8);
  display.print("OBJETIVO");
  display.setCursor(0, 36);
  display.print("ALCANZADO!");
  display.display();
  Serial.println("FIRE");
  disparoActivo = true;
  t_ultimoDisparo = millis();       // inicio del disparo; el cooldown corre desde aquí
}

// Apaga láser+buzzer 500 ms después del disparo, sin bloquear el loop.
void actualizarDisparo() {
  if (!disparoActivo) return;
  unsigned long t = millis() - t_ultimoDisparo;
  if (t >= T_DISPARO_MS) {                          // fin del disparo
    digitalWrite(PIN_LASER, LOW);
    digitalWrite(PIN_BUZZER, LOW);
    disparoActivo = false;
    return;
  }
  digitalWrite(PIN_LASER, HIGH);                    // láser fijo encendido los 5 s
  digitalWrite(PIN_BUZZER, ((t / 150) % 2) == 0);   // buzzer pulsante tipo alarma
}

// ------------------------------- HOMING ------------------------------------
// Lleva el cañón a una elevación de reposo fija y fija el cero de azimut.
// El MPU NO comanda el servo: va atornillado fijo a la base (plano horizontal),
// así que su pitch no refleja la elevación del cañón. Queda solo para mostrar
// la inclinación en la telemetría (ver leerPitch() / enviarTelemetria()).
void hacerHoming() {
  display.clearDisplay();
  display.setTextColor(SH110X_WHITE);
  display.setTextSize(2);
  display.setCursor(0, 24);
  display.print("HOMING...");
  display.display();
  elevacion = elevacionObjetivo = EL_HOME;   // posición de reposo fija y segura
  servoTilt.write(elevacion);
  delay(500);                           // deja que el servo llegue sin tirones
  stepper.setCurrentPosition(0);        // cero de azimut
  estado = ST_AUTONOMO;
  Serial.println("HOMING OK");
}

// ------------------- Comandos de la "PC" por serie -------------------------
// A <pasos> <grados> : correccion relativa de apuntado (0 0 = blanco centrado)
// L                  : blanco perdido (CU-04: conserva la posicion)
void procesarSerial() {
  if (!Serial.available()) return;
  String linea = Serial.readStringUntil('\n');
  linea.trim();
  if (linea.length() == 0) return;

  if (linea.startsWith("A")) {
    long dAz = 0; int dEl = 0;
    sscanf(linea.c_str(), "A %ld %d", &dAz, &dEl);
    if (estado == ST_AUTONOMO) {
      moverAzimut(dAz);
      moverElevacion(dEl);
      blancoVisible  = true;
      blancoCentrado = (dAz == 0 && dEl == 0);
    }
  } else if (linea.startsWith("L")) {
    blancoVisible = blancoCentrado = false;   // CU-04: queda a la espera
  }
}

// --------------------------- Pantalla y telemetría -------------------------
// Pantalla "radar de barrido": semicírculo de 180° (= rango de azimut ±90°),
// línea de barrido que gira, marcador de la dirección real (azimut) y un blip
// parpadeante con el blanco del ultrasonido. Se redibuja entero cada frame.
void actualizarPantalla() {
  const int cx = 64, cy = 52, R = 36;   // centro (abajo-centro) y radio del radar

  display.clearDisplay();
  display.setTextColor(SH110X_WHITE);

  // --- fondo del radar: anillos de rango (200 y 100 cm) + base ---
  display.drawCircleHelper(cx, cy, R,     0x3, SH110X_WHITE);   // 0x3 = mitad superior
  display.drawCircleHelper(cx, cy, R / 2, 0x3, SH110X_WHITE);
  display.drawFastHLine(cx - R, cy, 2 * R + 1, SH110X_WHITE);

  // --- línea de barrido (avanza un poco cada frame) ---
  sweepDeg += 18;                       // paso más grande: compensa el refresco más lento (100 kHz)
  if (sweepDeg > 180) sweepDeg = 0;
  float sw = sweepDeg * PI / 180.0;
  display.drawLine(cx, cy, cx + (int)(R * cos(sw)), cy - (int)(R * sin(sw)), SH110X_WHITE);

  // --- dirección real de la torreta (azimut): triángulo en el borde ---
  float azDeg = stepper.currentPosition() * 360.0 / PASOS_POR_VUELTA;   // ±90°
  azDeg = constrain(azDeg, -90.0, 90.0);
  float thAz = (90.0 - azDeg) * PI / 180.0;          // ángulo de pantalla
  float dx = cos(thAz), dy = -sin(thAz);             // versor radial (coords de pantalla)
  float px = -dy, py = dx;                           // perpendicular
  display.fillTriangle(
    cx + (int)((R + 3) * dx),           cy + (int)((R + 3) * dy),
    cx + (int)(R * dx + 3 * px),        cy + (int)(R * dy + 3 * py),
    cx + (int)(R * dx - 3 * px),        cy + (int)(R * dy - 3 * py),
    SH110X_WHITE);

  // --- blip del blanco (parpadeante), a un radio proporcional a la distancia ---
  if (ultimaDist > 0 && ultimaDist <= RANGO_MAX_CM && (millis() / 250) % 2) {
    float rB = ultimaDist / RANGO_MAX_CM * R;
    display.fillCircle(cx + (int)(rB * dx), cy + (int)(rB * dy), 3, SH110X_WHITE);
  }

  // --- barra vertical de tilt (elevación 0..90°) en el borde derecho ---
  const int gx = 122, gtop = 16, gbot = 52;            // 90° arriba, 0° abajo
  display.drawFastVLine(gx, gtop, gbot - gtop + 1, SH110X_WHITE);
  display.drawFastHLine(gx - 2, gtop, 3, SH110X_WHITE);                // tope 90°
  display.drawFastHLine(gx - 2, (gtop + gbot) / 2, 3, SH110X_WHITE);   // 45°
  display.drawFastHLine(gx - 2, gbot, 3, SH110X_WHITE);                // 0°
  int ey = gbot - (int)((float)elevacion / 90.0 * (gbot - gtop));
  ey = constrain(ey, gtop, gbot);
  display.fillTriangle(gx - 1, ey, gx - 7, ey - 3, gx - 7, ey + 3, SH110X_WHITE);  // marca de elevación

  // --- textos: modo (arriba-izq), SCAN/FIRE (arriba-der) ---
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.print(estado == ST_AUTONOMO ? "AUTO" : "MANUAL");
  const char *etq = disparoActivo ? "FIRE" : "SCAN";
  display.setCursor(128 - 6 * (int)strlen(etq), 0);
  display.print(etq);

  // --- lectura numérica compacta (abajo): az · el · dist ---
  display.setCursor(0, 56);
  display.print("az:");  display.print((int)azDeg);  display.print((char)247);
  display.print(" el:"); display.print(elevacion);   display.print((char)247);
  display.print(" ");
  if (ultimaDist < 0) display.print("---");
  else                display.print((int)ultimaDist);
  display.print("cm");

  display.display();
}

// Estado hacia la PC: esta linea es la que la PC mostraria sobre el video
void enviarTelemetria() {
  Serial.print("EST;modo=");
  Serial.print(estado == ST_AUTONOMO ? "AUTO" : "MANUAL");
  Serial.print(";az=");   Serial.print(stepper.currentPosition());
  Serial.print(";el=");   Serial.print(elevacion);
  Serial.print(";dist="); Serial.print(ultimaDist, 1);
  Serial.print(";temp="); Serial.print(ultimaTemp, 1);
  Serial.print(";hum=");  Serial.print(ultimaHum, 0);       // humedad relativa %
  Serial.print(";pitch="); Serial.println(leerPitch(), 1);  // inclinacion del MPU
}

// ------------------------------- setup -------------------------------------
void setup() {
  Serial.begin(115200);

  // Indicador de arranque: confirma físicamente que el firmware se cargó y corre.
  // El buzzer (GPIO27) va directo al GPIO, así que avisa aunque la fuente externa
  // de 5 V aún no esté conectada. El láser ahora se conmuta a 5 V con una llave
  // NPN (GPIO19 -> base): la lógica no cambia (HIGH = encendido), pero el blink
  // del láser solo se ve una vez conectada la fuente de 5 V.
  pinMode(PIN_LASER, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_LASER, HIGH);
  for (int i = 0; i < 2; i++) {          // dos beeps cortos de "boot OK"
    digitalWrite(PIN_BUZZER, HIGH); delay(120);
    digitalWrite(PIN_BUZZER, LOW);  delay(120);
  }
  delay(1600);                           // el láser completa ~2 s encendido
  digitalWrite(PIN_LASER, LOW);
  Serial.println("BOOT OK");

  Wire.begin();                          // SDA=21, SCL=22 (I2C a 100 kHz por defecto: el OLED no era confiable a 400 kHz en este cableado)

  // Despierta el MPU6050 (sale del modo sleep)
  Wire.beginTransmission(0x68);
  Wire.write(0x6B); Wire.write(0);
  Wire.endTransmission();

  display.begin(0x3C, true);             // SH1106 en 0x3C
  display.clearDisplay();
  display.display();
  dht.begin();

  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);
  pinMode(PIN_LASER, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_SW, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PIN_SW), isrPulsador, CHANGE);

  servoTilt.setPeriodHertz(50);
  servoTilt.attach(PIN_SERVO, 500, 2400);

  stepper.setMaxSpeed(VEL_AZ_RAPIDA);   // velocidad de aproximación (el apuntado fino la baja, ver loop)
  stepper.setAcceleration(800);         // frena en menos pasos => menos overshoot

  hacerHoming();
}

// -------------------------------- loop -------------------------------------
void loop() {
  // Gestos del pulsador (seteados por la ISR)
  if (ev_pulsacion_larga) {
    ev_pulsacion_larga = false;
    estado = (estado == ST_AUTONOMO) ? ST_MANUAL : ST_AUTONOMO;
    blancoVisible = blancoCentrado = false;
  }
  if (ev_pulsacion_corta) {
    ev_pulsacion_corta = false;
    if (estado == ST_MANUAL) disparar();    // CU-06
  }

  procesarSerial();

  // Modo MANUAL: el joystick comanda azimut y elevacion (cada 100 ms)
  if (estado == ST_MANUAL && millis() - t_ultimoJoystick > 100) {
    t_ultimoJoystick = millis();
    int x = analogRead(PIN_VRX), y = analogRead(PIN_VRY);
    if (abs(x - 2048) > 500) moverAzimut(x > 2048 ? 30 : -30);     // azimut más ágil
    if (abs(y - 2048) > 500) moverElevacion(y > 2048 ? 5 : -5);    // elevación más visible
    // Diagnóstico temporal del joystick (para verificar el eje Y / servo):
    Serial.print("JOY;x="); Serial.print(x); Serial.print(";y="); Serial.println(y);
  }

  // Medicion y decision de disparo (cada 500 ms)
  if (millis() - t_ultimaTelemetria > 500) {
    t_ultimaTelemetria = millis();
    ultimaTemp = leerTemperatura();
    float h = dht.readHumidity(); if (!isnan(h)) ultimaHum = h;
    ultimaDist = leerDistanciaCm(ultimaTemp);
    enviarTelemetria();

    // CU-02 / CU-03: dispara solo con blanco centrado Y en rango
    if (estado == ST_AUTONOMO && blancoVisible && blancoCentrado &&
        ultimaDist >= RANGO_MIN_CM && ultimaDist <= RANGO_MAX_CM &&
        millis() - t_ultimoDisparo > T_COOLDOWN_DISPARO_MS) {
      disparar();
    }
  }

  if (millis() - t_ultimaPantalla > 250) {  // a 100 kHz un frame tarda ~90 ms; 250 ms deja correr el stepper entre frames
    t_ultimaPantalla = millis();
    actualizarPantalla();
  }

  actualizarServo();    // acerca el servo a su objetivo de forma suave (controlado)
  actualizarDisparo();  // apaga láser+buzzer a los 500 ms sin bloquear
  // Apuntado fino: cerca del objetivo baja la velocidad para no pasarse de largo
  stepper.setMaxSpeed(labs(stepper.distanceToGo()) < AZ_UMBRAL_FINO ? VEL_AZ_FINA : VEL_AZ_RAPIDA);
  stepper.run();        // el stepper avanza de a un paso, sin bloquear
}

// ============================================================================
// PROTOCOLO SERIE (simula a la PC con OpenCV — escribir en el monitor serie):
//   A 200 5    → corregir +200 pasos de azimut y +5° de elevacion
//   A -50 0    → corregir -50 pasos
//   A 0 0      → "blanco centrado" (si ademas esta en rango → dispara)
//   L          → blanco perdido (la torreta conserva su posicion)
// El ESP32 responde cada 500 ms:  EST;modo=...;az=...;el=...;dist=...;temp=...
// ============================================================================

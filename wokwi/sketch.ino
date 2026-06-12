// ============================================================================
// Torreta de seguimiento y apuntado — firmware de simulación para Wokwi
// UTN FRSR · Electiva Arduino · TFI 2026
//
// Pines según docs/CONEXIONES.md (fuente única de verdad).
// La PC con OpenCV no existe en la simulación: sus comandos se escriben a
// mano en el monitor serie (ver protocolo al final de este archivo).
// ============================================================================

#include <Wire.h>
#include <LiquidCrystal_I2C.h>
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
const float RANGO_MIN_CM    = 20.0;   // criterio de "objetivo en rango"
const float RANGO_MAX_CM    = 200.0;
const long  PASOS_POR_VUELTA = 4096;  // 28BYJ-48 en medio paso
const long  LIMITE_AZIMUT   = PASOS_POR_VUELTA / 2;  // sector ±180° (CU-07)
const int   EL_MIN = 0, EL_MAX = 90;  // recorrido útil del servo
const unsigned long T_PULSACION_LARGA_MS = 800;
const unsigned long T_COOLDOWN_DISPARO_MS = 2000;

// ---------------------------- Objetos --------------------------------------
LiquidCrystal_I2C lcd(0x27, 16, 2);
Servo servoTilt;
// Orden de pines IN1-IN3-IN2-IN4: secuencia correcta para el 28BYJ-48
AccelStepper stepper(AccelStepper::HALF4WIRE, PIN_IN1, PIN_IN3, PIN_IN2, PIN_IN4);
DHT dht(PIN_DHT, DHT22);

// --------------------- Máquina de estados (FSM) ----------------------------
enum Estado { ST_HOMING, ST_AUTONOMO, ST_MANUAL };
Estado estado = ST_HOMING;

int   elevacion = 45;          // ángulo actual del servo
bool  blancoCentrado = false;  // la PC informó corrección (0,0)
bool  blancoVisible  = false;  // la PC está enviando correcciones
float ultimaDist = -1, ultimaTemp = 20.0;
unsigned long t_ultimoDisparo = 0, t_ultimaTelemetria = 0, t_ultimoLcd = 0;
unsigned long t_ultimoJoystick = 0;

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
  // CU-07: el azimut satura en el límite del sector ±180°
  long destino = constrain(stepper.targetPosition() + pasosRelativos,
                           -LIMITE_AZIMUT, LIMITE_AZIMUT);
  stepper.moveTo(destino);
}

void moverElevacion(int gradosRelativos) {
  elevacion = constrain(elevacion + gradosRelativos, EL_MIN, EL_MAX);
  servoTilt.write(elevacion);
}

void disparar() {
  digitalWrite(PIN_LASER, HIGH);
  digitalWrite(PIN_BUZZER, HIGH);
  lcd.clear();
  lcd.print("OBJETIVO");
  lcd.setCursor(0, 1);
  lcd.print("ALCANZADO!");
  Serial.println("FIRE");
  delay(500);                       // aviso breve (bloqueante, aceptable aqui)
  digitalWrite(PIN_LASER, LOW);
  digitalWrite(PIN_BUZZER, LOW);
  t_ultimoDisparo = millis();
}

// ------------------------------- HOMING ------------------------------------
// Nivela el cañón con el MPU6050 (busca pitch = 0) y fija el cero de azimut.
void hacerHoming() {
  lcd.clear();
  lcd.print("HOMING...");
  servoTilt.write(elevacion);
  delay(300);
  for (int i = 0; i < 90; i++) {        // tope de intentos por seguridad
    float pitch = leerPitch();
    if (fabs(pitch) < 2.0) break;
    elevacion = constrain(elevacion + (pitch > 0 ? -1 : 1), EL_MIN, EL_MAX);
    servoTilt.write(elevacion);
    delay(40);
  }
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

// --------------------------- LCD y telemetría ------------------------------
void actualizarLcd() {
  lcd.clear();
  lcd.print(estado == ST_AUTONOMO ? "AUTO" : "MANUAL");
  lcd.print(" az:");
  lcd.print((long)(stepper.currentPosition() * 360L / PASOS_POR_VUELTA));
  lcd.setCursor(0, 1);
  lcd.print("d:");
  if (ultimaDist < 0) lcd.print("---");
  else                lcd.print((int)ultimaDist);
  lcd.print("cm t:");
  lcd.print(ultimaTemp, 1);
}

// Estado hacia la PC: esta linea es la que la PC mostraria sobre el video
void enviarTelemetria() {
  Serial.print("EST;modo=");
  Serial.print(estado == ST_AUTONOMO ? "AUTO" : "MANUAL");
  Serial.print(";az=");   Serial.print(stepper.currentPosition());
  Serial.print(";el=");   Serial.print(elevacion);
  Serial.print(";dist="); Serial.print(ultimaDist, 1);
  Serial.print(";temp="); Serial.println(ultimaTemp, 1);
}

// ------------------------------- setup -------------------------------------
void setup() {
  Serial.begin(115200);
  Wire.begin();                          // SDA=21, SCL=22

  // Despierta el MPU6050 (sale del modo sleep)
  Wire.beginTransmission(0x68);
  Wire.write(0x6B); Wire.write(0);
  Wire.endTransmission();

  lcd.init();
  lcd.backlight();
  dht.begin();

  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);
  pinMode(PIN_LASER, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_SW, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PIN_SW), isrPulsador, CHANGE);

  servoTilt.setPeriodHertz(50);
  servoTilt.attach(PIN_SERVO, 500, 2400);

  stepper.setMaxSpeed(500);
  stepper.setAcceleration(300);

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
    if (abs(x - 2048) > 500) moverAzimut(x > 2048 ? 15 : -15);
    if (abs(y - 2048) > 500) moverElevacion(y > 2048 ? 2 : -2);
  }

  // Medicion y decision de disparo (cada 500 ms)
  if (millis() - t_ultimaTelemetria > 500) {
    t_ultimaTelemetria = millis();
    ultimaTemp = leerTemperatura();
    ultimaDist = leerDistanciaCm(ultimaTemp);
    enviarTelemetria();

    // CU-02 / CU-03: dispara solo con blanco centrado Y en rango
    if (estado == ST_AUTONOMO && blancoVisible && blancoCentrado &&
        ultimaDist >= RANGO_MIN_CM && ultimaDist <= RANGO_MAX_CM &&
        millis() - t_ultimoDisparo > T_COOLDOWN_DISPARO_MS) {
      disparar();
    }
  }

  if (millis() - t_ultimoLcd > 700) {
    t_ultimoLcd = millis();
    actualizarLcd();
  }

  stepper.run();   // el stepper avanza de a un paso, sin bloquear
}

// ============================================================================
// PROTOCOLO SERIE (simula a la PC con OpenCV — escribir en el monitor serie):
//   A 200 5    → corregir +200 pasos de azimut y +5° de elevacion
//   A -50 0    → corregir -50 pasos
//   A 0 0      → "blanco centrado" (si ademas esta en rango → dispara)
//   L          → blanco perdido (la torreta conserva su posicion)
// El ESP32 responde cada 500 ms:  EST;modo=...;az=...;el=...;dist=...;temp=...
// ============================================================================

// Escáner I2C de diagnóstico — temporal (no es parte del firmware).
// Esperado en la torreta: 0x3C (OLED SSD1306) y 0x68 (MPU6050).
#include <Wire.h>

void setup() {
  Serial.begin(115200);
  Wire.begin();            // ESP32: SDA=21, SCL=22 (igual que el firmware)
  delay(400);
  Serial.println("\n=== Escaner I2C (SDA=21 SCL=22) ===");
}

void loop() {
  byte n = 0;
  for (byte a = 1; a < 127; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) {
      Serial.print("  encontrado en 0x");
      if (a < 16) Serial.print('0');
      Serial.println(a, HEX);
      n++;
    }
  }
  if (n == 0) Serial.println("  NINGUN dispositivo I2C (revisar SDA/SCL/GND/VCC)");
  else        { Serial.print("  total: "); Serial.println(n); }
  Serial.println("---");
  delay(2000);
}

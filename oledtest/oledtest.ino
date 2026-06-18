// Test directo de la librería SSD1306 — diagnóstico (temporal).
// Escanea el bus e intenta inicializar el OLED en 0x3C y 0x3D,
// reportando por serie el resultado de cada paso.
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

Adafruit_SSD1306 display(128, 64, &Wire, -1);

void escanear() {
  byte n = 0;
  Serial.print("  bus I2C: ");
  for (byte a = 1; a < 127; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) {
      Serial.print("0x"); if (a < 16) Serial.print('0'); Serial.print(a, HEX); Serial.print(' ');
      n++;
    }
  }
  if (n == 0) Serial.print("(vacio)");
  Serial.println();
}

void setup() {
  Serial.begin(115200);
  Wire.begin();
  delay(400);
  Serial.println("\n=== TEST LIBRERIA OLED ===");
}

void loop() {
  escanear();

  Serial.print("  begin(0x3C): ");
  if (display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("OK <-- el OLED responde en 0x3C");
    display.clearDisplay();
    display.setTextSize(2); display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, 20); display.print("OLED OK!");
    display.display();
  } else {
    Serial.println("FALLO (no contesta en 0x3C)");
    Serial.print("  begin(0x3D): ");
    if (display.begin(SSD1306_SWITCHCAPVCC, 0x3D)) {
      Serial.println("OK <-- el OLED responde en 0x3D (cambiar direccion en el firmware)");
      display.clearDisplay();
      display.setTextSize(2); display.setTextColor(SSD1306_WHITE);
      display.setCursor(0, 20); display.print("0x3D!");
      display.display();
    } else {
      Serial.println("FALLO (tampoco en 0x3D) -> modulo no responde al bus");
    }
  }
  Serial.println("---");
  delay(3000);
}

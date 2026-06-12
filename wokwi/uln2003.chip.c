// Chip personalizado de Wokwi: driver ULN2003 (didáctico)
//
// Replica el rol del módulo ULN2003 del circuito real: recibe la secuencia
// IN1..IN4 del ESP32 y la entrega amplificada a las bobinas del motor.
//
// Nota de fidelidad: el ULN2003 real es un arreglo Darlington INVERSOR de
// colector abierto (la salida conduce a GND cuando la entrada está en alto)
// y el 28BYJ-48 es unipolar con punto común a +5V. Como el motor de Wokwi
// es bipolar y se anima según la secuencia lógica que recibe, este chip se
// modela como buffer no inversor para que la animación coincida con la
// secuencia que genera el firmware (la misma del hardware real).

#include "wokwi-api.h"
#include <stdlib.h>

typedef struct {
  pin_t in[4];
  pin_t out[4];
} chip_state_t;

static void on_pin_change(void *user_data, pin_t pin, uint32_t value) {
  chip_state_t *chip = (chip_state_t *)user_data;
  for (int i = 0; i < 4; i++) {
    if (chip->in[i] == pin) {
      pin_write(chip->out[i], value);
      return;
    }
  }
}

void chip_init() {
  chip_state_t *chip = malloc(sizeof(chip_state_t));
  const char *in_names[]  = { "IN1", "IN2", "IN3", "IN4" };
  const char *out_names[] = { "OUT1", "OUT2", "OUT3", "OUT4" };

  for (int i = 0; i < 4; i++) {
    chip->in[i]  = pin_init(in_names[i], INPUT);
    chip->out[i] = pin_init(out_names[i], OUTPUT);

    pin_watch_config_t config = {
      .edge = BOTH,
      .pin_change = on_pin_change,
      .user_data = chip,
    };
    pin_watch(chip->in[i], &config);
  }
}

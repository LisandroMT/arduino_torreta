# Simulación en Wokwi

Simulación del circuito completo de la torreta en [Wokwi](https://wokwi.com), con el mismo
mapa de pines que `docs/CONEXIONES.md` y un firmware de prueba que implementa la FSM
(HOMING → AUTÓNOMO ⇄ MANUAL), la ISR del pulsador, la compensación térmica y el criterio
de disparo por rango.

## Cómo correrla

1. Entrar a [wokwi.com](https://wokwi.com) → **New Project** → **ESP32**.
2. Reemplazar el contenido de `sketch.ino` con el de este directorio.
3. En la pestaña `diagram.json`, pegar el contenido de `diagram.json`.
4. Con el botón **+** junto a las pestañas, crear tres archivos y pegar los de acá:
   `libraries.txt`, `uln2003.chip.json` y `uln2003.chip.c` (el chip personalizado que
   representa al driver del stepper; Wokwi lo compila solo al dar Play).
5. Play ▶.

## Diferencias con el hardware real

| Real | En Wokwi | Motivo |
|---|---|---|
| Láser KY-008 | LED rojo + resistencia 220 Ω | Wokwi no tiene módulo láser |
| 28BYJ-48 + ULN2003 | Stepper genérico + **chip personalizado ULN2003** (`uln2003.chip.c`) | Wokwi no trae el ULN2003; el chip propio replica su rol (GPIO 26/25/33/32 → IN1..IN4 → bobinas) con la misma lógica de control (AccelStepper HALF4WIRE). Se modela como buffer no inversor — ver nota en el `.chip.c` |
| Divisor 1kΩ/2kΩ en ECHO | ECHO directo a GPIO18 | La simulación no modela niveles de tensión; **en el hardware real el divisor es obligatorio** |
| PC con Python + OpenCV | Comandos tipeados en el monitor serie | Wokwi no ejecuta el nodo de percepción |

## Cómo probar cada caso de uso

La simulación arranca en HOMING (nivela el servo con el MPU6050) y pasa a AUTÓNOMO.

- **CU-01 Homing:** antes de dar Play, clic en el MPU6050 y dale una inclinación a los
  sliders del acelerómetro: al arrancar, el servo busca pitch = 0.
- **CU-02 Disparo autónomo:** clic en el HC-SR04 y fijá una distancia entre 20 y 200 cm.
  En el monitor serie escribí `A 200 5` (la torreta gira) y después `A 0 0` (blanco
  centrado) → el LED "láser" y el buzzer se activan y la pantalla OLED muestra *OBJETIVO ALCANZADO*.
- **CU-03 Fuera de rango:** fijá la distancia del HC-SR04 en 300 cm y mandá `A 0 0` →
  no dispara; la pantalla OLED sigue mostrando la distancia.
- **CU-04 Blanco perdido:** mandá `L` → la torreta conserva su posición.
- **CU-05 Conmutación de modo:** mantené apretado el botón del joystick > 0,8 s →
  cambia a MANUAL (se ve en la pantalla OLED).
- **CU-06 Disparo manual:** en MANUAL, mové el joystick (la torreta sigue) y hacé una
  pulsación corta → dispara.
- **CU-07 Límite de sector:** en MANUAL, sostené el joystick hacia un lado: el azimut
  avanza hasta ±90° (±1024 pasos) y satura ahí (el rango que la ranura del cable permite
  sin pellizcarlo).
- **Compensación térmica:** clic en el DHT22 y cambiá la temperatura: la distancia
  reportada (`EST;...;dist=...`) varía levemente con la misma distancia física —
  es la corrección v(T) actuando.

El ESP32 reporta su estado cada 500 ms por serie (`EST;modo=...;az=...;el=...;dist=...;temp=...`),
que es la telemetría que en el sistema real consume la PC para mostrar la distancia en pantalla.

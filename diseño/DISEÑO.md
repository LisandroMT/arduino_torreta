# Documento de diseño — Torreta CAD paramétrica (Fase 1)

**Proyecto:** TFI Arduino — Torreta-Escáner 3D, UTN FRSR 2026
**Fecha:** 2026-06-05
**Objetivo:** modelar en código paramétrico una réplica estética de la torreta de
`image.png`, que se renderice en 3D y se exporte para impresión 3D, con calidad
profesional.

## Decisiones de diseño

| Decisión | Elección | Motivo |
|---|---|---|
| Motor CAD | **build123d** | Sólidos B-rep exactos (OpenCASCADE), API moderna, exporta STEP/STL/3MF/GLB |
| Fuente de parámetros | **`turret.yaml`** validado | Sin números mágicos; cotas verificadas al cargar |
| Render | **PyVista (VTK) offscreen** | Sombreado de calidad de presentación (matplotlib no alcanza) |
| Alcance Fase 1 | **una sola pieza fusionada, sin electrónica** | "De menos a más"; primero la estética y el pipeline |

## Alcance Fase 1 (entregado)

Réplica estética fiel, **posada** (pan/tilt/spin desde el YAML) y **fusionada en un
único sólido estanco**, que:
- se renderiza a PNG multi-vista (verificación visual contra la referencia);
- exporta STEP (editable), STL/3MF (impresión) y GLB con colores (visualización);
- pasa un **gate de imprimibilidad**: 1 sólido conexo, volumen > 0, válido en
  OpenCASCADE y superficie estanca (0 bordes abiertos).

Fuera de alcance (fases siguientes): pockets para electrónica (SG90/láser/N20),
partición en piezas imprimibles con holguras, articulación real, mapeo a pines.

## Anatomía (descomposición de la referencia)

1. **Base / trípode** — collar octogonal biselado, tira de luz perimetral, `n_legs`
   patas planas con textura de pisada y agujero de fijación.
2. **Pedestal** — tambor cilíndrico giratorio (pan) con panel lines.
3. **Cuerpo blindado** — cuña facetada (alta atrás, baja al frente), ventana de
   sensor, mástil de antena, muñones (eje de elevación) al frente.
4. **Mantelete + cargador** — bloque que pivota en tilt; cargador amarillo en cuña
   con triángulo de advertencia grabado.
5. **Cañón gatling** — `n_tubes` en bolt circle, eje central hueco (futuro láser),
   placa trasera, freno de boca con un orificio por tubo + perforaciones.

## Cinemática

- **pan**: gira {pedestal + cuerpo + cabezal} sobre Z; la base queda fija.
- **tilt**: eleva {mantelete + cañón} sobre el eje Y del muñón.
- **spin**: gira el racimo sobre su propio eje (cosmético).

## Metodología

Construcción **incremental con verificación visual**: cada hito (base → pedestal →
cuerpo → mantelete → cañón → pose) se renderizó y se comparó con la referencia
antes de avanzar. El gate de imprimibilidad actúa como "test" automático previo a
exportar. La parametrización se validó con una variante (8 tubos, 4 patas, escala
1.3) que regenera todo desde otro YAML.

## Resultado

Sólido único, estanco, ~314 cm³, bounding box 142 × 141 × 110 mm a escala 1.0.
Lee inequívocamente como la torreta de la referencia.

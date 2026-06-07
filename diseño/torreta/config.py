"""Carga y validación de turret.yaml hacia dataclasses tipadas.

Cada campo tiene un valor por defecto razonable: el YAML solo necesita sobrescribir
lo que cambie, y agregar/quitar claves no rompe la carga (las desconocidas se
ignoran con aviso). La validación de invariantes geométricas e imprimibilidad
ocurre al cargar, no en medio del modelado.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_YAML = Path(__file__).resolve().parent.parent / "turret.yaml"


@dataclass
class GlobalCfg:
    scale: float = 1.0
    min_wall_mm: float = 1.6
    fillet_mm: float = 1.0
    tessellation_mm: float = 0.10
    clearance_mm: float = 0.35


@dataclass
class BaseCfg:
    hex_across_flats_mm: float = 96
    height_mm: float = 17
    top_chamfer_mm: float = 6
    n_legs: int = 3
    leg_orient_deg: float = 180
    leg_length_mm: float = 70
    leg_root_width_mm: float = 30
    leg_tip_width_mm: float = 26
    leg_thickness_mm: float = 9
    tread_rows: int = 5
    tread_cols: int = 3
    chevron_accents: bool = True
    pan_socket_dia_mm: float = 26
    pan_socket_depth_mm: float = 14
    pan_screw_dia_mm: float = 3.2


@dataclass
class NeckCfg:
    drum_dia_mm: float = 52
    drum_height_mm: float = 18
    shaft_height_mm: float = 13
    panel_lines: int = 2


@dataclass
class BodyCfg:
    width_mm: float = 58
    depth_mm: float = 60
    back_height_mm: float = 60
    front_height_mm: float = 40
    facet_chamfer_mm: float = 7
    side_stripes: bool = True
    ammo_box: bool = True
    side_window: bool = True
    antenna: bool = True
    trunnion_z_mm: float = 30
    trunnion_x_mm: float = 30
    trunnion_pin_dia_mm: float = 3.2
    ear_thickness_mm: float = 6
    ear_gap_mm: float = 46


@dataclass
class CradleCfg:
    width_mm: float = 44
    height_mm: float = 30
    depth_mm: float = 34
    chamfer_mm: float = 4


@dataclass
class BarrelsCfg:
    n_tubes: int = 6
    bolt_circle_dia_mm: float = 11
    tube_dia_mm: float = 3.2
    length_mm: float = 76
    breech_dia_mm: float = 22
    breech_length_mm: float = 18
    clamp_count: int = 2
    clamp_width_mm: float = 4
    clamp_extra_r_mm: float = 1.4
    central_axis_dia_mm: float = 4
    hollow_axis: bool = True
    muzzle_ring_mm: float = 3


@dataclass
class PoseCfg:
    pan_deg: float = 30
    tilt_deg: float = 14
    spin_deg: float = 0


@dataclass
class StyleCfg:
    body_color: str = "#23262B"
    tube_color: str = "#9DA0A4"
    accent_color: str = "#F2C200"
    background: str = "#3A3A3A"


@dataclass
class Config:
    glb: GlobalCfg
    base: BaseCfg
    neck: NeckCfg
    body: BodyCfg
    cradle: CradleCfg
    barrels: BarrelsCfg
    pose: PoseCfg
    style: StyleCfg

    @classmethod
    def load(cls, path: str | Path = DEFAULT_YAML) -> "Config":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        cfg = cls(
            glb=_build(GlobalCfg, data.get("global", {})),
            base=_build(BaseCfg, data.get("base", {})),
            neck=_build(NeckCfg, data.get("neck", {})),
            body=_build(BodyCfg, data.get("body", {})),
            cradle=_build(CradleCfg, data.get("cradle", {})),
            barrels=_build(BarrelsCfg, data.get("barrels", {})),
            pose=_build(PoseCfg, data.get("pose", {})),
            style=_build(StyleCfg, data.get("style", {})),
        )
        cfg.validate()
        return cfg

    def validate(self) -> None:
        errors: list[str] = []
        for section in (self.glb, self.base, self.neck, self.body, self.cradle,
                        self.barrels):
            for f in fields(section):
                val = getattr(section, f.name)
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    if f.name.endswith("_mm") and val <= 0:
                        errors.append(f"{type(section).__name__}.{f.name} debe ser > 0 ({val})")
                    if f.name.startswith("n_") and val < 1:
                        errors.append(f"{type(section).__name__}.{f.name} debe ser >= 1 ({val})")

        if self.body.front_height_mm >= self.body.back_height_mm:
            errors.append("body: front_height_mm debe ser < back_height_mm (cuña)")

        # La cuna debe entrar entre las orejas del muñón con holgura.
        if self.cradle.width_mm > self.body.ear_gap_mm - 2 * self.glb.clearance_mm:
            errors.append("cradle.width_mm no entra en body.ear_gap_mm (con holgura)")

        # Tubos sin solape en el bolt circle.
        import math
        n = self.barrels.n_tubes
        if n >= 2:
            r_bc = self.barrels.bolt_circle_dia_mm / 2
            gap = 2 * r_bc * math.sin(math.pi / n) - self.barrels.tube_dia_mm
            if gap < 0:
                errors.append(
                    f"barrels: {n} cañones Ø{self.barrels.tube_dia_mm} se solapan en el "
                    f"bolt circle Ø{self.barrels.bolt_circle_dia_mm} ({-gap:.1f} mm)")

        # El eje del cuerpo debe entrar en el socket de la base.
        shaft = self.base.pan_socket_dia_mm - 2 * self.glb.clearance_mm
        if shaft <= self.base.pan_screw_dia_mm + 2:
            errors.append("neck/base: el eje de pan es demasiado fino para el tornillo")

        if errors:
            raise ValueError("turret.yaml inválido:\n  - " + "\n  - ".join(errors))


def _build(klass: type, raw: dict[str, Any]):
    """Instancia una dataclass desde el YAML; ignora claves desconocidas con aviso."""
    known = {f.name for f in fields(klass)}
    extra = set(raw) - known
    if extra:
        print(f"[config] aviso: claves ignoradas en {klass.__name__}: {sorted(extra)}")
    return klass(**{k: v for k, v in raw.items() if k in known})


assert is_dataclass(Config)

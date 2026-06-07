"""Gate de imprimibilidad para el modelo articulado (varias piezas).

Cada pieza física (base, body, gun) debe ser, por separado, un único sólido conexo,
válido en OpenCASCADE y estanco. Además se informa el bounding box de cada una para
verificar que entran en la cama de impresión.
"""
from __future__ import annotations

from dataclasses import dataclass

from .config import Config
from .render import to_mesh


@dataclass
class PartReport:
    name: str
    ok: bool
    n_solids: int
    volume_mm3: float
    occ_valid: bool
    watertight: bool
    open_edges: int
    bbox_mm: tuple

    def line(self) -> str:
        bx, by, bz = self.bbox_mm
        flag = "OK " if self.ok else "!! "
        return (f"  {flag}{self.name:5s} | sólidos={self.n_solids} "
                f"vol={self.volume_mm3/1000:6.1f}cm³ válido={self.occ_valid} "
                f"estanco={self.watertight}({self.open_edges}) "
                f"bbox={bx:.0f}×{by:.0f}×{bz:.0f}mm")


def check_part(name: str, solid, cfg: Config) -> PartReport:
    tol = cfg.glb.tessellation_mm
    n_solids = len(solid.solids())
    volume = float(solid.volume)
    try:
        iv = solid.is_valid
        occ_valid = iv() if callable(iv) else bool(iv)
    except Exception:
        occ_valid = False

    mesh = to_mesh(solid, tol).clean(tolerance=1e-4, absolute=True)
    edges = mesh.extract_feature_edges(boundary_edges=True, feature_edges=False,
                                       manifold_edges=False, non_manifold_edges=False)
    open_edges = int(edges.n_cells)
    watertight = open_edges == 0
    b = mesh.bounds
    bbox = (b[1] - b[0], b[3] - b[2], b[5] - b[4])
    ok = (n_solids == 1) and (volume > 0) and occ_valid and watertight
    return PartReport(name, ok, n_solids, volume, occ_valid, watertight, open_edges, bbox)


def check_all(part_solids: dict, cfg: Config) -> tuple[bool, str]:
    reports = [check_part(n, s, cfg) for n, s in part_solids.items()]
    all_ok = all(r.ok for r in reports)
    head = "TODAS LAS PIEZAS APTAS PARA IMPRIMIR" if all_ok else "HAY PIEZAS NO APTAS"
    body = "\n".join(r.line() for r in reports)
    return all_ok, f"[{head}]\n{body}"


if __name__ == "__main__":
    from .assembly import part_solids
    cfg = Config.load()
    ok, report = check_all(part_solids(cfg), cfg)
    print(report)

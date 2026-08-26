from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .three_d import TrainingFree3DGRPO, curves_to_svg


@dataclass(frozen=True)
class ExperimentSpec:
    modality: str
    coordinate_mode: str
    format: str

    @property
    def name(self) -> str:
        return f"{self.modality}_{self.coordinate_mode}_{self.format}"


EXPERIMENTS = [
    ExperimentSpec(modality, coordinate, output_format)
    for modality in ("2d", "3d")
    for coordinate in ("integer", "real")
    for output_format in ("svg", "json")
]


def run_3d_matrix(prompt: str, output_root: str | Path = "outputs/experiments", *, epochs: int = 1, samples: int = 2):
    root = Path(output_root)
    records = []
    for spec in EXPERIMENTS:
        if spec.modality != "3d":
            continue
        run_dir = root / spec.name
        result = TrainingFree3DGRPO(coordinate_mode=spec.coordinate_mode, samples=samples, output_dir=run_dir).run(prompt, epochs=epochs)
        path = run_dir / f"final.{spec.format}"
        if spec.format == "json":
            path.write_text(result.to_json(), encoding="utf-8")
        else:
            # SVG is a 2D projection artifact; JSON remains the native 3D truth.
            path.write_text(curves_to_svg(result.curves), encoding="utf-8")
        records.append({"experiment": spec.name, "path": str(path), "curves": len(result.curves), "metadata": result.metadata})
    (root / "3d_matrix.json").parent.mkdir(parents=True, exist_ok=True)
    (root / "3d_matrix.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    return records

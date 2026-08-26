from __future__ import annotations

from dataclasses import dataclass
from .providers import SketchProvider
from .schema import Sketch
from .validator import ValidationResult, validate_sketch, validate_sketch3d


@dataclass
class DrawConfig:
    model: str = "gpt-5.6-terra"
    temperature: float = 0.7
    candidates: int = 1


class Drawer:
    """Coordinates generation, validation, and optional test-time scaling."""

    def __init__(self, provider: SketchProvider, config: DrawConfig | None = None):
        self.provider = provider
        self.config = config or DrawConfig()

    def draw(self, stage_prompt: str) -> tuple[Sketch, ValidationResult]:
        candidates: list[tuple[Sketch, ValidationResult]] = []
        for index in range(max(1, self.config.candidates)):
            sketch = self.provider.draw(stage_prompt, model=self.config.model, temperature=self.config.temperature + index * 0.05)
            validation = validate_sketch3d(sketch) if hasattr(sketch, "curves") else validate_sketch(sketch)
            candidates.append((sketch, validation))
        valid = [item for item in candidates if item[1].valid]
        return (valid or candidates)[0]

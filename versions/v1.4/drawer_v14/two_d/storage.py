from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sketch_agent.rendering import render_svg_png
from sketch_agent.schema import Sketch

from .document import SVGDocument
from .schema import RevisionRecord, StrokePatch


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


class RevisionStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.revisions_root = self.root / "revisions"
        self.index_path = self.root / "revisions.json"

    def initialize(self, *, width: int, height: int, metadata: dict[str, Any] | None = None) -> RevisionRecord:
        self.root.mkdir(parents=True, exist_ok=True)
        self.revisions_root.mkdir(parents=True, exist_ok=True)
        if self.index_path.exists():
            raise FileExistsError(f"revision store already initialized: {self.root}")
        document = SVGDocument(Sketch(width=width, height=height, strokes=[], metadata=dict(metadata or {})))
        return self._commit(document, parent=None, round_index=0, patch=None, allow_empty=True)

    def commit(
        self,
        document: SVGDocument,
        *,
        parent: str,
        round_index: int,
        patch: StrokePatch,
    ) -> RevisionRecord:
        if parent not in self.records_by_id():
            raise ValueError(f"unknown parent revision: {parent}")
        return self._commit(document, parent=parent, round_index=round_index, patch=patch, allow_empty=False)

    def _commit(
        self,
        document: SVGDocument,
        *,
        parent: str | None,
        round_index: int,
        patch: StrokePatch | None,
        allow_empty: bool,
    ) -> RevisionRecord:
        records = self.records()
        revision_id = f"revision_{len(records):03d}"
        revision_dir = self.revisions_root / revision_id
        if revision_dir.exists():
            raise FileExistsError(f"immutable revision exists: {revision_id}")
        if not allow_empty and not document.sketch.strokes:
            raise ValueError("cannot commit empty drawing revision")
        revision_dir.mkdir(parents=True)
        sketch_path = revision_dir / "sketch.json"
        svg_path = revision_dir / "sketch.svg"
        preview_path = revision_dir / "preview.png"
        state_path = revision_dir / "state.json"
        patch_path = revision_dir / "patch.json" if patch else None
        sketch_path.write_text(document.sketch.to_json(), encoding="utf-8")
        svg_path.write_text(document.to_svg(), encoding="utf-8")
        render_svg_png(document.to_svg(), preview_path, width=document.sketch.width, height=document.sketch.height)
        if patch_path and patch:
            _write_json(patch_path, patch.to_dict())
        state = {
            "revision_id": revision_id,
            "parent_revision": parent,
            "round_index": round_index,
            "retired_ids": sorted(document.retired_ids),
            "stroke_ids": list(document.stroke_ids),
        }
        _write_json(state_path, state)
        record = RevisionRecord(
            revision_id=revision_id,
            parent_revision=parent,
            round_index=round_index,
            sketch_path=str(sketch_path.relative_to(self.root)),
            svg_path=str(svg_path.relative_to(self.root)),
            preview_path=str(preview_path.relative_to(self.root)),
            patch_path=str(patch_path.relative_to(self.root)) if patch_path else None,
            stroke_count=len(document.sketch.strokes),
        )
        records.append(record)
        _write_json(self.index_path, [item.to_dict() for item in records])
        return record

    def records(self) -> list[RevisionRecord]:
        if not self.index_path.exists():
            return []
        values = json.loads(self.index_path.read_text(encoding="utf-8"))
        return [RevisionRecord(**item) for item in values]

    def records_by_id(self) -> dict[str, RevisionRecord]:
        return {item.revision_id: item for item in self.records()}

    def load_document(self, revision_id: str) -> SVGDocument:
        record = self.records_by_id().get(revision_id)
        if record is None:
            raise ValueError(f"unknown revision: {revision_id}")
        sketch = Sketch.from_json((self.root / record.sketch_path).read_text(encoding="utf-8"))
        state = json.loads((self.revisions_root / revision_id / "state.json").read_text(encoding="utf-8"))
        return SVGDocument(sketch, retired_ids=state.get("retired_ids", []))

    def preview_path(self, revision_id: str) -> Path:
        record = self.records_by_id()[revision_id]
        return self.root / record.preview_path

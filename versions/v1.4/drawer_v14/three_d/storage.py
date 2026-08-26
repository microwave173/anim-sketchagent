from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from .document import Path3DDocument
from .patch import Path3DPatch, RevisionRecord
from .renderer import DEFAULT_CAMERAS, render_scene_views
from .schema import Path3DStroke


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


class Path3DRevisionStore:
    def __init__(self, root: str | Path, *, width: int, height: int) -> None:
        self.root = Path(root)
        self.width = width
        self.height = height
        self.revisions_root = self.root / "revisions"
        self.index_path = self.root / "revisions.json"

    def initialize(self, *, prompt: str) -> RevisionRecord:
        self.root.mkdir(parents=True, exist_ok=True)
        self.revisions_root.mkdir(parents=True, exist_ok=True)
        if self.index_path.exists():
            raise FileExistsError(f"revision store already initialized: {self.root}")
        return self._commit(Path3DDocument(prompt), parent=None, round_index=0, patch=None, allow_empty=True)

    def commit(
        self,
        document: Path3DDocument,
        *,
        parent: str,
        round_index: int,
        patch: Path3DPatch,
    ) -> RevisionRecord:
        if parent not in self.records_by_id():
            raise ValueError(f"unknown parent revision: {parent}")
        return self._commit(document, parent=parent, round_index=round_index, patch=patch, allow_empty=False)

    def _commit(
        self,
        document: Path3DDocument,
        *,
        parent: str | None,
        round_index: int,
        patch: Path3DPatch | None,
        allow_empty: bool,
    ) -> RevisionRecord:
        records = self.records()
        revision_id = f"revision_{len(records):03d}"
        revision_dir = self.revisions_root / revision_id
        if revision_dir.exists():
            raise FileExistsError(f"immutable revision exists: {revision_id}")
        if not allow_empty and not document.strokes:
            raise ValueError("cannot commit empty Path3D revision")
        revision_dir.mkdir(parents=True)
        scene_path = revision_dir / "scene.json"
        state_path = revision_dir / "state.json"
        patch_path = revision_dir / "patch.json" if patch else None
        views_dir = revision_dir / "views"
        _write_json(scene_path, document.to_dict())
        if document.strokes:
            render_scene_views(document.to_scene(), views_dir, width=self.width, height=self.height)
        else:
            self._render_blank_views(views_dir)
        if patch_path and patch:
            _write_json(patch_path, patch.to_dict())
        _write_json(state_path, {
            "revision_id": revision_id,
            "parent_revision": parent,
            "round_index": round_index,
            "retired_ids": sorted(document.retired_ids),
            "stroke_ids": list(document.stroke_ids),
        })
        record = RevisionRecord(
            revision_id,
            parent,
            round_index,
            str(scene_path.relative_to(self.root)),
            str((views_dir / "contact_sheet.png").relative_to(self.root)),
            str(views_dir.relative_to(self.root)),
            str(patch_path.relative_to(self.root)) if patch_path else None,
            len(document.strokes),
        )
        records.append(record)
        _write_json(self.index_path, [item.to_dict() for item in records])
        return record

    def _render_blank_views(self, output: Path) -> None:
        output.mkdir(parents=True, exist_ok=True)
        paths = []
        for camera in DEFAULT_CAMERAS:
            path = output / f"view_{camera.name}.png"
            Image.new("RGB", (self.width, self.height), "white").save(path)
            paths.append(path)
        sheet = Image.new("RGB", (self.width * 2, self.height * 2), "white")
        draw = ImageDraw.Draw(sheet)
        for index, path in enumerate(paths):
            x, y = (index % 2) * self.width, (index // 2) * self.height
            draw.text((x + 14, y + 12), path.stem.removeprefix("view_"), fill="#111111")
        sheet.save(output / "contact_sheet.png")

    def records(self) -> list[RevisionRecord]:
        if not self.index_path.exists():
            return []
        return [RevisionRecord(**item) for item in json.loads(self.index_path.read_text(encoding="utf-8"))]

    def records_by_id(self) -> dict[str, RevisionRecord]:
        return {item.revision_id: item for item in self.records()}

    def load_document(self, revision_id: str) -> Path3DDocument:
        record = self.records_by_id().get(revision_id)
        if record is None:
            raise ValueError(f"unknown revision: {revision_id}")
        value = json.loads((self.root / record.scene_path).read_text(encoding="utf-8"))
        state = json.loads((self.revisions_root / revision_id / "state.json").read_text(encoding="utf-8"))
        return Path3DDocument(
            str(value.get("prompt", "")),
            (Path3DStroke.from_dict(item) for item in value.get("strokes", [])),
            retired_ids=state.get("retired_ids", []),
        )

    def contact_sheet_path(self, revision_id: str) -> Path:
        return self.root / self.records_by_id()[revision_id].contact_sheet_path

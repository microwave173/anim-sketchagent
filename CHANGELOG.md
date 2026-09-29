# Changelog

## v2.1.0 — JointPlanKey

### Architecture

- Generate the storyboard and all sparse keyframes in one model request, allowing key construction to revise story beats before either is committed.
- Keep the existing parallel gap stage: each gap receives one local event plus accepted FROM and TO keyframes.
- Preserve the previous Markdown and JSON two-stage planners behind `--plan-format storyboard` and `--plan-format json`.
- Add atomic checkpoints and optional compressed `reasoning_content` capture for the joint stage and gaps.

### Drawing and output

- Use a shared drawing contract for Naive, keys and gaps.
- Export standard SVG path data for 2D, fixed black strokes, immutable line width and semantic stroke descriptions.
- Keep 2D and 3D orchestration aligned while retaining genuine Path3D geometry and perspective SVG export.
- Allow off-canvas coordinates and rely on normal viewport clipping.
- Improve small-canvas composition, natural quadruped motion, gait alternation, visible contacts and motion space.

### Reliability

- Validate joint storyboard coverage, beat exits, sparse key indices and frame geometry together.
- Normalize the common shared-boundary notation `1-9, 9-18` to exclusive frame coverage instead of regenerating the full response.
- Keep output-limit gap splitting, concurrent execution and checkpoint resume.
- Expand the Light V2 test suite to 15 passing tests.

### Baselines and research

- Add a true one-shot Naive baseline using the same drawing prompt, geometry validator and renderer.
- Add 2D/3D long-story runners and timing records for Naive versus staged evaluation.
- Document observed Naive failures, KeyGap hypotheses, storyboard ablations, reasoning analysis and the JointPlanKey decision.

See `docs/README.md`, `docs/RESEARCH_HISTORY_ZH.md`, and `docs/JOINT_STORYBOARD_KEYFRAMES_ZH.md` for the full design history and evaluation notes.

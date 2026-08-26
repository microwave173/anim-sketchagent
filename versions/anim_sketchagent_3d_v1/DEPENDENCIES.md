# anim_sketchagent_3d_v1 dependencies

Frozen project dependencies:

- `versions/path3d_v1/` — Path3D schema, parser, one-shot system prompt, four-view renderer
- `versions/path3d_json_v1/` — structured Path3D compiler
- `versions/path3d_incremental_base_v1/` — incremental key drawer loop and prompts
- `versions/v1.4/drawer_v14/three_d/` — revision store and patch validation
- `versions/anim_sketchagent_2d_v1/` — frozen 2D method baseline
- `src/terra_client.py` — frozen local copy of the Zhipu/GLM HTTP client

Runtime:

- Python 3.9+
- `numpy`, `Pillow`, `python-dotenv`, `openai`
- project-root `.env` with the Zhipu/GLM and DeepSeek Vision credentials used by `terra_client.py`

Model routing frozen by the source:

- text planner and one-shot inbetweens: `glm-5.3`
- contact-sheet review, incremental edit, and best-revision selection: `deepseek-v4-flash-vision-exp`

The dependency directories above are referenced in place and are intentionally not copied into this snapshot.

# Structured Path3D JSON v1

这是对扁平 Path3D 字符串协议的独立替代实验。模型直接输出结构化命令，每个关键点、控制点和终点都是独立的 `[x,y,z]` 三元组；工具层再确定性编译为 Path3D 字符串并复用现有渲染器。

```json
{
  "command": "C3",
  "control_1": [-0.3, 0.9, 0.6],
  "control_2": [0.3, -0.9, -0.5],
  "end": [0.8, 0.5, 0.75]
}
```

运行：

```bash
PYTHONPATH=versions/path3d_json_v1:versions/path3d_v1:. \
python3 -m path3d_json \
  --prompt "A 3D wireframe dragon" \
  --output outputs/structured_dragon \
  --model gpt-5.6-terra
```

输出：

- `raw_response.txt`：模型原文；
- `structured_scene.json`：规范化的三元组命令；
- `scene.json`：编译后的旧 Path3D，供渲染和兼容使用；
- `views/`：四视角和 contact sheet。

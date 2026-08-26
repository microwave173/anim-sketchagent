# Structured Path3D Agents v1

该实验版本保留 v1.4 与单次 `path3d_json_v1`，将结构化三元组命令用于两种迭代方式。

## 增量更新

```bash
PYTHONPATH=versions/path3d_json_agents_v1:versions/v1.4:versions/path3d_json_v1:versions/path3d_v1:. \
python3 -m path3d_json_agents incremental \
  --prompt "A recognizable 3D wireframe dragon breathing a curved stream of fire" \
  --output outputs/path3d_json_incremental_dragon_fire
```

Planner 只查看目标与 front/side/top/perspective 四视图，负责判断问题、优先级、继续/重建/结束，并给出高层视觉目标。它不指定坐标、笔画数、stroke ID 或具体增删操作。

Editor 同时看到四视图和完整 scene，自行理解目标、选择画法、决定笔画数，并可局部修改或批量重建。默认每个 patch 最多新增或删除 48 个 semantic strokes；该上限只用于拦截异常失控输出，不作为正常绘画预算。Editor 返回结构化 JSON patch，再确定性编译为 Path3D。每个 revision 同时保存 `structured_patch.json` 与编译后的 `scene.json`。

Planner instruction 固定为高层字段：

```json
{
  "objective": "视觉目标",
  "priority": "当前最高优先级",
  "success_criteria": ["可观察的完成条件"],
  "scope": "高层范围描述"
}
```

Planner 输出坐标、stroke ID、具体增删列表或保护列表会被视为越权并拒绝。

## 视觉反思完整重画

```bash
PYTHONPATH=versions/path3d_json_agents_v1:versions/v1.4:versions/path3d_json_v1:versions/path3d_v1:. \
python3 -m path3d_json_agents reflection \
  --prompt "A recognizable 3D wireframe dragon breathing a curved stream of fire" \
  --samples 3 --max-loops 2 \
  --output outputs/path3d_json_reflection_dragon_fire
```

每轮并行完整生成候选；视觉 critic 与 selector 并行查看四视图；经验角色重写完整经验；下一轮根据经验从头重画。历史 progress judge 选择最终结果并可在无明显进步时提前停止。

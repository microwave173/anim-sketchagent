# JSON Plan 并行版

## 版本位置

- 早期原始版本：`versions/anim_sketchagent_2d_v1/archive_xml_src/`
- 当前实现入口：`light_agent/cli.py`
- JSON schema 与校验：`light_agent/json_plan.py`
- JSON planner 提示词：`light_agent/prompts/PLANNER_JSON.md`

早期版本使用 JSON 的 `parts / keys / gaps` 规划，但绘图协议是旧 XML，后续生成基本串行。当前实现保留这三个规划层级，把绘图和执行换成目前的标准 SVG 流程。

## 当前流程

1. 一次 planner 调用生成结构化 `plan.json`。
2. 一次 key batch 调用联合生成全部关键帧，减少角色和场景身份漂移。
3. 每对相邻 key 形成一个 gap；所有 gap 使用 `ThreadPoolExecutor` 并发生成。
4. 每个 plan、key batch、gap 都独立保存 checkpoint，可以断点续跑。
5. 合并全部帧并输出标准 SVG、GIF、contact sheet 和网页。

`parts` 现在只表示角色、物体和场景的语义身份，不强制映射为固定 SVG stroke ID。2D 与 3D 使用同一规划和并发逻辑，区别只在 Path2D / Path3D 几何协议与投影渲染。

## 运行方法

```bash
cd /root/autodl-tmp/anim-sketchagent
.venv-light/bin/python light_agent/cli.py \
  --prompt "A character throws a ball against a wall and catches the rebound." \
  --dim 2 \
  --frames 40 \
  --frame-ms 120 \
  --out outputs/my_json_plan_run \
  --plan-format json \
  --gap-workers 6 \
  --max-tokens 393216
```

`--plan-format storyboard` 继续使用现有 Markdown storyboard；默认值仍是 storyboard，因此原有脚本的行为不变。

## 已验证结果

端到端测试目录：`outputs/json_plan_parallel_smoke_2d/`

- 16 帧，2D，5 个 gaps
- key frames：`1, 5, 7, 9, 12, 16`
- 4 个 worker；日志中 `gap_01` 到 `gap_04` 同时启动
- `gap_wall_seconds`: 100.104
- 总时间：201.012 秒
- 结果文件：`plan.json`、`animation.json`、`clip.gif`、`contact_sheet.jpg`、`index.html`、`metrics.json`

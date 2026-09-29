# Anim SketchAgent：已完成工作与产物

## 当前系统

服务器项目位于 `/root/autodl-tmp/anim-sketchagent`。当前推荐实现为 `light_agent/`，2D 和 3D 共用同一控制流程：

```text
Storyboard 与 sparse keys 联合生成 → 各 gap 并发补帧 → 严格校验 → GIF/SVG 渲染
```

主要入口：

- Staged agent：`light_agent/cli.py`
- Naive 单次问答 baseline：`light_agent/naive_cli.py`
- 共享 provider、校验与渲染：`provider.py`、`scene.py`、`render.py`
- 提示词：`light_agent/prompts/`
- Python 环境：`.venv-light/bin/python`

## 已实现能力

- 2D/3D 使用同一套 JointPlanKey → gaps 流程。默认在一次请求中联合确定 storyboard 与全部 sparse keys，使绘制 key 时发现的空间或动作问题能直接修正故事；旧 Markdown/JSON 两阶段 planner 保留用于消融。
- Gaps 默认最多 6 路并发，并支持 checkpoint 恢复和局部重做；每个 gap 只接收局部事件及 FROM/TO keys。
- 2D 输出使用标准 SVG path data；3D 保存 Path3D，并导出 perspective 投影的标准 SVG。
- 所有结果固定为白底纯黑线条、统一线宽和圆角连接。原生设计画布为 320px，当前原生线宽 3px，平滑放大到 640px 后约 6px。
- 提示词已加入圆形人物头部、腿部交替与支撑相、手脚和道具接触、小主体与更大运动空间、因果先后和最终状态保持等规则。
- 3D 已同步 2D 的构图、动作幅度、步态和低分辨率设计原则，同时保留真实深度结构规则。
- 每次运行输出 `request.json`、`storyboard.md`、`joint_plan_keys.json`、`animation.json`、`clip.gif`、`animation.svg`、逐帧 SVG、contact sheet、网页和完整 metrics。
- Metrics 记录墙钟时间、各阶段、每次 API 调用、token usage、finish reason 和恢复会话累计数据。

## 已完成实验与结果

### JointPlanKey 猫鼠回归

60 帧自然四足猫鼠任务验证了 storyboard 与 keys 联合生成：模型在构造 keys 时同步修改陷阱机制与空间调度，最终完整表现搭陷阱、伏击、取饵、扑击和反扣。成功联合响应相对旧 planner+keys 合计减少约 27% reasoning tokens；完整数据和设计结论见 `docs/JOINT_STORYBOARD_KEYFRAMES_ZH.md`。精简可视化示例位于 `examples/jointplankey_cat_mouse_60f/`。

### 12 个多阶段任务

已完成同一组 12 个任务的 2D 和 3D staged 生成，每题 24 帧。当前细线版本结果：

- 2D：`outputs/baseline_advantage_12_svg_motion_2d3d/2d/`
- 3D：`outputs/baseline_advantage_12_synced_3d_v2/3d/`
- 打包文件：`outputs/baseline_advantage_12_final_2d3d.tar.gz`

任务覆盖因果链、物体交接、遮挡后重现、多人协作、工具使用、状态变化、属性选择和空间路线。

### Naive baseline

已实现与 staged 共用风格、协议、校验和渲染的单次问答基线。它在一个回答中返回全部帧，并输出相同的 GIF/SVG/JSON 产物，便于直接比较。实现文件：

- `light_agent/naive.py`
- `light_agent/naive_cli.py`
- `light_agent/prompts/NAIVE_ONE_SHOT.md`

### 128 帧长故事对比

已完成 4 个故事 × 2D/3D × naive/staged 的实验矩阵。可播放结果、原始 metrics 和任务定义位于：

- 结果：`outputs/montage128_v1/`
- Prompts：`outputs/montage128_tasks.json`
- 最终状态：`outputs/montage128_status_final.json`
- 耗时/token：`outputs/montage128_timing_final.csv`
- 查看用归档：`outputs/montage128_final_viewable.tar.gz`

Staged 共完成 8 个 128 帧结果；Naive 共完成 2 个通过严格校验的 128 帧结果。详细研究结论见根目录 `NAIVE_VS_STAGED_ONE_PAGE_ZH.md`。

## 使用示例

```bash
cd /root/autodl-tmp/anim-sketchagent

# Staged
.venv-light/bin/python light_agent/cli.py \
  --prompt "YOUR STORY" --dim 2 --frames 128 --frame-ms 160 --size 640 \
  --max-tokens 393216 --gap-workers 6 --out outputs/my_staged_run

# Naive
.venv-light/bin/python light_agent/naive_cli.py \
  --prompt "YOUR STORY" --dim 2 --frames 128 --frame-ms 160 --size 640 \
  --max-tokens 393216 --out outputs/my_naive_run
```

单个成功任务可直接打开其目录中的 `index.html`，或查看 `clip.gif`、`animation.svg` 和 `contact_sheet.jpg`。

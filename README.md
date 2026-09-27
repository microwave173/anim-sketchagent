# Anim SketchAgent

Anim SketchAgent 是一套 pose-to-pose 线稿动画实验仓库，同时保存可复现的 2D 与 3D 入口。当前提示词把事件写成严格的因果顺序，并以观众能否从线稿中直接辨认主体、动作、接触和状态变化作为画面约束。


## Agent 版本并存

- **Classic V1**：原有复杂 agent，源码及示例保留在 `versions/anim_sketchagent_2d_v1`、`versions/anim_sketchagent_3d_v1`。
- **Light V2（最新）**：`light_agent/`，Markdown 规划 → 全部关键帧一次生成 → gap 并发批量生成。支持 2D/3D，当前 2D 使用 320px 设计目标、粗线火柴人和抗锯齿平滑放大；机器人采用机械造型。

[新版使用与服务器部署文档](docs/LIGHT_V2_USAGE_ZH.md)。只运行新版可安装 `requirements-light.txt`。

## Classic V1 的两个维度

| 版本 | 关键帧 | 中间帧 | 代表结果 |
|---|---|---|---|
| 2D Path2D | oneshot Path2D scene | oneshot 因果中间帧（可选 `--lerp`） | [羽毛球](versions/anim_sketchagent_2d_v1/examples/path2d_badminton_rally/clip.gif) · [打瓶子](versions/anim_sketchagent_2d_v1/examples/path2d_bottleshot/clip.gif) · [逗猫](versions/anim_sketchagent_2d_v1/examples/path2d_catwand/clip.gif) |
| 3D Path3D | incremental 或 oneshot Path3D | DeepSeek one-shot 完整 Path3D scene | [电梯](versions/anim_sketchagent_3d_v1/examples/elevator/clip.gif) · [羽毛球](versions/anim_sketchagent_3d_v1/examples/badminton/clip.gif) |

当前版本还包括跨 key 的 identity anchor、相邻 motion neighborhood、按真实播放时长分配动作密度，以及 3D 动画专用的原子 pose replacement。Planner schema 保持精简：这些约束写入已有的 `action`、key `notes` 和 gap `why`，不增加连续性专用字段。

详细说明：

- [2D 文档](versions/anim_sketchagent_2d_v1/README_ZH.md)
- [3D 文档](versions/anim_sketchagent_3d_v1/README_ZH.md)
- [Path2D 协议](versions/path2d_v1/README_ZH.md)

## 目录

```text
versions/
  anim_sketchagent_2d_v1/       Path2D 源码、测试、代表输出（XML lerp 在 archive_xml_src/）
  anim_sketchagent_3d_v1/       Path3D 源码、测试、代表输出
  path2d_v1/                    Path2D schema/parser/renderer
  path3d_v1/                    Path3D schema/parser/renderer
  path3d_json_v1/               structured Path3D compiler
  path3d_incremental_base_v1/   incremental 3D drawer
  v1.4/                         3D revision/patch 基础设施
sketch_agent/                   共享模型配置
third_party/SketchAgent-main/   旧 XML 渲染所需的最小第三方文件
tools/                          长动画包装器：放宽帧数并按 key-to-key gap 整段生成
```

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

在 `.env` 中填写实际 API 凭据。不要提交 `.env`。

## 运行 2D

```bash
python3 versions/anim_sketchagent_2d_v1/src/glm_anim_2d.py \
  --task catwand --model glm-5.3 --keys 3 --frames 12 \
  --plan-effort high --key-effort high --first-key-effort high \
  --out outputs/2d_catwand
```

单帧重绘并重建 GIF / contact sheet：

```bash
python3 versions/anim_sketchagent_2d_v1/src/glm_anim_2d.py \
  --task catwand --model glm-5.3 --from-run outputs/2d_catwand \
  --redraw-frame 3 --draw-effort high
```

只从已有 `scene.json` 重出预览：`--rebuild-clip`。

## 运行 3D

```bash
python3 versions/anim_sketchagent_3d_v1/src/glm_anim_3d.py \
  --task badminton --keys 3 --max-rounds 4 \
  --out outputs/3d_badminton
```

也可用 `--task elevator`。

## 新版 Complex：每个 gap 一次生成

当前大规模实验先生成 plan 与所有 key，再让模型在一次响应中生成一个 key-to-key 区间的全部中间帧。这样同一区间内的帧共享完整上下文，也减少 API 调用次数。

2D 示例：

```bash
python3 tools/run_native.py --dim 2 --task bounce \
  --prompt "A person pulls a fire alarm; the sprinkler activates and puts out a fire." \
  --frames 24 --keys-only --model deepseek-flash \
  --plan-effort high --draw-effort high --key-effort high --first-key-effort high \
  --out outputs/alarm_2d
python3 tools/run_gap_complex.py --dim 2 \
  --prompt "A person pulls a fire alarm; the sprinkler activates and puts out a fire." \
  --run outputs/alarm_2d --reasoning-effort high
```

3D 将第一条命令换成 `--dim 3 --task tabledrop --key-mode oneshot --reasoning-effort high`，第二条命令使用 `--dim 3`。`run_gap_complex.py` 会输出 perspective 主 GIF；3D 同时输出四个命名视角。

## 测试与校验

```bash
(cd versions/anim_sketchagent_2d_v1/src && python3 -m unittest -v test_anim_2d.py)
(cd versions/anim_sketchagent_3d_v1/src && python3 -m unittest -v test_anim_3d.py test_animation_incremental.py test_reasoning_override.py)

(cd versions/anim_sketchagent_2d_v1 && shasum -a 256 -c SHA256SUMS)
(cd versions/anim_sketchagent_3d_v1 && shasum -a 256 -c SHA256SUMS)
```

## 模型

- `--model gpt-5.6-sol`（2D 默认）、`glm-5.3`、`deepseek-v4-flash`
- 3D incremental 视觉编辑仍走 DeepSeek Vision
- 2D 中间帧默认也是模型 oneshot；`--lerp` 才是本地几何插值

## 安全与第三方

- 仓库不包含 API 密钥或本地 `.env`。
- `third_party/SketchAgent-main/` 保留原项目的 MIT License。
- `SHA256SUMS` 用于确认源码和代表输出未被意外修改。

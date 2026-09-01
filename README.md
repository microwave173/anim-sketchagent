# Anim SketchAgent

Anim SketchAgent 是一套 pose-to-pose 线稿动画实验仓库，同时保存可复现的 2D 与 3D 入口。

## 两个版本

| 版本 | 关键帧 | 中间帧 | 代表结果 |
|---|---|---|---|
| 2D Path2D | oneshot Path2D scene | oneshot 因果中间帧（可选 `--lerp`） | [羽毛球](versions/anim_sketchagent_2d_v1/examples/path2d_badminton_rally/clip.gif) · [打瓶子](versions/anim_sketchagent_2d_v1/examples/path2d_bottleshot/clip.gif) · [逗猫](versions/anim_sketchagent_2d_v1/examples/path2d_catwand/clip.gif) |
| 3D Path3D | incremental Path3D | GLM one-shot 完整 Path3D scene | [电梯](versions/anim_sketchagent_3d_v1/examples/elevator/clip.gif) · [羽毛球](versions/anim_sketchagent_3d_v1/examples/badminton/clip.gif) |

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

## 测试与校验

```bash
(cd versions/anim_sketchagent_2d_v1/src && python3 -m unittest -v test_anim_2d.py)
(cd versions/anim_sketchagent_3d_v1/src && python3 -m unittest -v test_anim_3d.py)

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

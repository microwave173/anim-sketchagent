# Anim SketchAgent

Anim SketchAgent 是一套 pose-to-pose 线稿动画实验仓库，同时保存可复现的 2D 与 3D v1 基线。

## 两个版本

| 版本 | 关键帧 | 中间帧 | 代表结果 |
|---|---|---|---|
| 2D | GLM-5.3 输出 SketchAgent XML；可选 DeepSeek Vision 审稿 | 按稳定 `<id>` 做几何插值 | [篮球 GIF](versions/anim_sketchagent_2d_v1/examples/basketball_scale2/clip.gif) |
| 3D | incremental Path3D：DeepSeek Vision 看四视图并编辑 | GLM-5.3 one-shot 输出完整 Path3D scene | [篮球 GIF](versions/anim_sketchagent_3d_v1/examples/basketball_smoke/clip.gif) |

详细设计和冻结说明：

- [2D v1 文档](versions/anim_sketchagent_2d_v1/README_ZH.md)
- [3D v1 文档](versions/anim_sketchagent_3d_v1/README_ZH.md)

## 目录

```text
versions/
  anim_sketchagent_2d_v1/       2D 源码、gold、代表输出
  anim_sketchagent_3d_v1/       3D 源码、测试、代表输出
  path3d_v1/                    Path3D schema/parser/renderer
  path3d_json_v1/               structured Path3D compiler
  path3d_incremental_base_v1/   incremental 3D drawer
  v1.4/                         3D revision/patch 基础设施
sketch_agent/                   共享模型配置
third_party/SketchAgent-main/   2D XML 渲染所需的最小第三方文件
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
python3 versions/anim_sketchagent_2d_v1/src/glm_anim_keys.py \
  --task basketball --no-reflect \
  --out outputs/2d_basketball
```

可用短任务包括 `basketball`、`badminton`、`saber`。Planner 默认自行选择至少两个关键帧，总帧数默认约 12，但不固定。

## 运行 3D

```bash
python3 versions/anim_sketchagent_3d_v1/src/glm_anim_3d.py \
  --task basketball --max-rounds 4 \
  --out outputs/3d_basketball
```

3D 版使用语义 part IDs、首关键帧锚点复用和固定世界坐标 framing，避免篮架、地面与镜头逐帧漂移。

## 测试与校验

```bash
(cd versions/anim_sketchagent_3d_v1/src && python3 -m unittest -v test_anim_3d.py)

(cd versions/anim_sketchagent_2d_v1 && shasum -a 256 -c SHA256SUMS)
(cd versions/anim_sketchagent_3d_v1 && shasum -a 256 -c SHA256SUMS)
```

## 模型与费用

- 文本规划与 one-shot：`glm-5.3`
- 视觉审稿与 incremental 编辑：`deepseek-v4-flash-vision-exp`
- 2D 中间帧是本地几何插值；3D 中间帧需要逐帧模型调用，成本明显更高。

## 安全与第三方

- 仓库不包含 API 密钥或本地 `.env`。
- `third_party/SketchAgent-main/` 保留原项目的 MIT License。
- 冻结版本的 `SHA256SUMS` 用于确认源码和代表输出未被意外修改。

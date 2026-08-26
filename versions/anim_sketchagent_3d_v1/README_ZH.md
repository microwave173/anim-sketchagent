# 3D Anim SketchAgent

日期：2026-08-26。

把冻结的 2D pose-to-pose 动画（`versions/anim_sketchagent_2d_v1/`）改成 3D：整体仍是 **plan + draw keys + fill gaps**，但画法换成 Path3D。

这是只读基线快照。后续开发继续在 `experiments/anim_3d/`；本目录只保存 v1 源码、测试、依赖清单、校验和与代表输出。

## 和 2D 的对应

| 步骤 | 2D | 3D |
|---|---|---|
| Plan | GLM-5.3 文本，无视觉 | 同样，GLM-5.3 文本 |
| 关键帧 | GLM 一次画一张 SketchAgent XML | **逐步** Path3D incremental（Planner 看四视图、Editor 打 patch）。这是 `path3d_incremental_base_v1`，**没有** `reflection` 那种多样本批量重画 |
| 中间帧 | 按 `<id>` 几何 lerp | **单次** Path3D one-shot：一次输出整个物体（`path3d_v1` 的生成协议，走 GLM） |
| 视觉 | 可选 DeepSeek 审 key | incremental 里凡带 contact sheet 的调用用 DeepSeek 视觉；纯文本用 GLM |

选用 incremental 而不是 `path3d_json_agents reflection`：文档里它是当前最好的逐步 3D drawer，且明确不是批量生产+经验重画。one-shot 只给中间帧，避免每帧再跑 7–9 轮。

## 模型

- 无图：`glm-5.3`（Zhipu）
- 有图（四视图审稿、选历史最佳、Editor 看 contact sheet）：`deepseek-v4-flash-vision-exp`

## 调用成本

- 一段 clip：1 次 GLM plan。
- 每个 key、每个 incremental round：通常 1 次 DeepSeek 四视图审稿 + 1 次 DeepSeek 结构编辑；结束时另有 1 次 DeepSeek 历史最佳选择。无效 JSON 会触发有限修复。
- 每个中间帧：通常 1 次 GLM 完整 scene one-shot；schema 或 ID 失败最多有限重试。
- 篮球 smoke 是 3 keys × 4 rounds + 9 个 one-shot 中间帧，因此明显比 2D 几何插帧昂贵。

## 运行

```bash
cd /Users/lalala/Desktop/sketch
python3 versions/anim_sketchagent_3d_v1/src/glm_anim_3d.py \
  --task basketball --max-rounds 4 \
  --out /tmp/anim3d_basketball_repro
```

`--max-rounds` 是**每个 key** 的 incremental 轮数，默认 4（每轮 Planner 看四视图 + Editor 打 patch，都走 DeepSeek 视觉）。不要一上来跑很多 round：3 个 key × 4 轮已经是一次完整试跑。任务目前：`basketball`、`walk`。user prompt 仍是一句英文。脚本会自己把冻结 Drawer 和 `path3d_v1` 加进 `sys.path`。

输出：`plan.json`、`action.txt`、`keys/<name>/final/views/`、`frames/fXX/`、`clip.gif`（perspective）、`contact_sheet.png`。冻结代表输出在 `examples/basketball_smoke/`。

## 跨帧契约

- `parts[].id` 是跨帧契约；每个 key 和 one-shot 中间帧都必须包含这些 exact ids。辅助笔画只能使用 `<part_id>_...` 前缀。
- 第一张 key 定义 canonical stroke ids。后续 key 和中间帧缺少 canonical id 会被拒绝并有限重试。
- `motion: anchored` 的地面、篮架、篮筐、球网等从第一张 key 原样复制，模型不能让它们漂移。
- 最终四视图与 GIF 使用固定世界坐标 `[-1,1]` 和固定相机，关闭逐帧 recenter/normalize，避免镜头缩放抖动。Incremental 内部审稿仍使用原 renderer 的归一化预览。

## 测试

```bash
cd versions/anim_sketchagent_3d_v1/src
python3 -m unittest -v test_anim_3d.py
python3 -m compileall -q .
```

底层 Path3D、structured compiler、incremental agent 的测试需要把项目根目录和对应冻结版本放入 `PYTHONPATH`；本次冻结前会一并运行。

## 依赖版本（不要改）

- `versions/path3d_incremental_base_v1/`：逐步 key
- `versions/path3d_v1/`：Path3D 语法与四视角渲染；one-shot 的 system prompt
- `versions/v1.4/drawer_v14/three_d/`：revision store / patch 校验
- `versions/anim_sketchagent_2d_v1/`：2D 方法说明（本实验的对照）

精确文件列表与哈希见 `DEPENDENCIES.md` 和 `SHA256SUMS`。本快照不复制、不修改上述底层冻结版本。

## 篮球 smoke

- 代表输出：planner 选择 3 个 key、12 帧；每帧 13 个 canonical strokes，4 个 anchored parts（ground、hoop pole/rim/net）逐帧完全复用。
- 9 个 one-shot 中间帧全部一次通过 ID/schema 契约；固定世界坐标渲染没有逐帧镜头缩放。
- 两次端到端运行都完成。第二次的线稿可读性较差，因此代表样例保留第一次更清晰的输出；这不是从多样本 reflection 中挑图，而是 smoke 后选择发布基线。
- DeepSeek 视觉审稿偶尔给出缺字段 JSON。冻结源码会先做一次结构修复，再回退到保守 `continue` 指令；不会因此无限重试。

## 已知边界

- 3D 中间帧不是几何 lerp，而是 GLM 对相邻 key scene 的完整 one-shot 重画；因此成本高于 2D，动作连续性也更依赖 ID 契约。
- Path3D 是空间线稿，不是 mesh 或骨骼动画；没有遮挡表面、关节权重或物理仿真。
- 固定世界 framing 要求模型遵守 `[-1,1]`。越界几何会被如实裁切，不会自动缩回画布。

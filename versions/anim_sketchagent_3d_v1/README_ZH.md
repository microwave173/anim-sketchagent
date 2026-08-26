# 3D Anim SketchAgent

日期：2026-08-27。

把冻结的 2D pose-to-pose 动画改成 3D：整体仍是 **plan + draw keys + fill gaps**，画法换成 Path3D。

本目录是 GitHub 仓库里的 3D 入口：源码、测试、依赖清单、校验和，以及电梯 / 羽毛球代表输出。

## 和 2D 的对应

| 步骤 | 2D | 3D |
|---|---|---|
| Plan | GLM-5.3 文本，无视觉 | 同样，GLM-5.3 文本 |
| 关键帧 | GLM 一次画一张 SketchAgent XML | **逐步** Path3D incremental（Planner 看四视图、Editor 打 patch）。这是 `path3d_incremental_base_v1`，**没有** `reflection` 那种多样本批量重画 |
| 中间帧 | 按 `<id>` 几何 lerp | **单次** Path3D one-shot：一次输出整个物体（`path3d_v1` 的生成协议，走 GLM） |
| 视觉 | 可选 DeepSeek 审 key | incremental 里凡带 contact sheet 的调用用 DeepSeek 视觉；纯文本用 GLM |

one-shot 只给中间帧，避免每帧再跑 7–9 轮 incremental。动画 Editor 的 system prompt 禁止换 id（不能删旧 id 再造 `_new` / `_emerge`）。

## 模型

- 无图：`glm-5.3`（Zhipu）
- 有图（四视图审稿、选历史最佳、Editor 看 contact sheet）：`deepseek-v4-flash-vision-exp`

## 调用成本

- 一段 clip：1 次 GLM plan。
- 每个 key、每个 incremental round：通常 1 次 DeepSeek 四视图审稿 + 1 次 DeepSeek 结构编辑；结束时另有 1 次 DeepSeek 历史最佳选择。无效 JSON 会触发有限修复。
- 每个中间帧：通常 1 次 GLM 完整 scene one-shot；schema 或 ID 失败最多有限重试。
- 羽毛球代表 clip：3 keys × 4 rounds + 10 个 one-shot 中间帧，墙钟 **617.73s**（`/usr/bin/time -p real`）。

## 运行

从仓库根目录：

```bash
python3 versions/anim_sketchagent_3d_v1/src/glm_anim_3d.py \
  --task badminton --keys 3 --max-rounds 4 \
  --out outputs/3d_badminton
```

`--max-rounds` 是**每个 key** 的 incremental 轮数，默认 4。任务：`basketball`、`walk`、`pillar_peek`、`ball_door`、`elevator`、`crane_gap`、`badminton`。脚本会把冻结 Drawer 和 `path3d_v1` 加进 `sys.path`。

`--keys-only` 只画关键帧。`--from-run PATH` 复用已有 plan+keys，只补中间帧。

```bash
python3 versions/anim_sketchagent_3d_v1/src/glm_anim_3d.py \
  --task elevator --keys 3 --max-rounds 4 --keys-only \
  --out outputs/3d_elevator_keys
python3 versions/anim_sketchagent_3d_v1/src/glm_anim_3d.py \
  --from-run outputs/3d_elevator_keys --out outputs/3d_elevator
```

输出：`plan.json`、`action.txt`、`keys/<name>/final/views/`、`frames/fXX/`、`clip.gif`（perspective）、`contact_sheet.png`、`summary.json`（含 `wall_seconds`）。代表输出：

| 任务 | 目录 |
|---|---|
| 进电梯（跨门槛中步） | `examples/elevator/` |
| 羽毛球对打 | `examples/badminton/` |

样例只保留最终 scene / 四视图 / GIF，不含 incremental 每轮 dump。

## 跨帧契约

- `parts[].id` 是跨帧契约；每个 key 和 one-shot 中间帧都必须包含这些 exact ids。辅助笔画只能使用 `<part_id>_...` 前缀。
- 第一张 key 定义 canonical stroke ids。后续 key 和中间帧缺少 canonical id 会被拒绝并有限重试。
- `motion: anchored` 的地面、网、轿厢、柱子等从第一张 key 原样复制。人、球、滑动门是 moving。
- 最终四视图与 GIF 使用固定世界坐标 `[-1,1]` 和固定相机，关闭逐帧 recenter/normalize。Incremental 内部审稿仍使用原 renderer 的归一化预览。
- 行走 / 击球要求真跨步（一腿在前、对侧臂），不要滑步 T-pose。

## 测试

```bash
cd versions/anim_sketchagent_3d_v1/src
python3 -m unittest -v test_anim_3d.py
python3 -m compileall -q .
```

```bash
cd versions/anim_sketchagent_3d_v1
shasum -a 256 -c SHA256SUMS
```

底层 Path3D、structured compiler、incremental agent 的测试需要把项目根目录和对应冻结版本放入 `PYTHONPATH`。

## 依赖版本（不要改）

- `versions/path3d_incremental_base_v1/`：逐步 key
- `versions/path3d_v1/`：Path3D 语法与四视角渲染；one-shot 的 system prompt
- `versions/v1.4/drawer_v14/three_d/`：revision store / patch 校验
- `versions/anim_sketchagent_2d_v1/`：2D 方法说明（本实验的对照）

精确文件列表与哈希见 `DEPENDENCIES.md` 和 `SHA256SUMS`。本快照不复制、不修改上述底层冻结版本。

## 已知边界

- 3D 中间帧不是几何 lerp，而是 GLM 对相邻 key scene 的完整 one-shot 重画；因此成本高于 2D，动作连续性也更依赖 ID 契约。
- Path3D 是空间线稿，不是 mesh 或骨骼动画；没有遮挡表面、关节权重或物理仿真。
- 固定世界 framing 要求模型遵守 `[-1,1]`。越界几何会被如实裁切，不会自动缩回画布。
- 早期篮球 smoke 能过 ID 契约，但线稿可读性不稳定；当前代表样例改为电梯与羽毛球。

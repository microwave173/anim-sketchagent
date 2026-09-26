# Anim SketchAgent 2D（Path2D）

日期：2026-09-26。

当前 2D 入口是 **Path2D pose-to-pose**：Planner 出稀疏 key 与 `gaps[].n_inbetween`，Drawer **oneshot** 画每一张 key，中间帧也是 **oneshot**（不再按 id 几何 lerp，除非显式 `--lerp`）。坐标 `[-1,1]`，`+x` 右、`+y` 上。

早期 SketchAgent XML + lerp 的源码留在 `archive_xml_src/`，gold 与 `examples/basketball_scale2` 等仍是那套输出，只作对照。

## 方法

```text
用户一句 prompt
  -> 文本 Planner（plan.json：action / notes / parts / keys / gaps）
  -> oneshot 画 keys（同一套 part id）
  -> oneshot 画因果中间帧（FROM=上一帧，TO=下一 key）
  -> clip.gif + contact_sheet.png
```

根目录的 `tools/run_gap_complex.py` 提供当前实验所用的 gap one-shot 模式：一个 API 响应生成一对相邻 key 之间的全部中间帧，并同时参考前一 key、后一 key 和第一张 identity anchor。

- `notes` 只保存简短的固定体型、布局、运动通道和关键连接；动作顺序写在 `action` 与 key `notes` 中。
- 原因必须先可见完成，结果才能开始；例如先触发报警器，再启动喷淋，水接触火焰后火焰才能消失。
- 画面以观众识别为目标：关键动作使用清楚的轮廓、间距、接触和状态差异，不依赖 prompt 解释。
- 第一张 key 是身份锚点；后续 key 从相邻 pose 延续位移、朝向、主导肢体、持物状态和角色比例。
- `n_inbetween` 是两拍之间的时间，不是凑帧；`why` 要说明快/中/慢。
- 单帧返工：`--from-run DIR --redraw-frame N`（可选 `--redraw-note`、`--redraw-cascade`）。
- 只重出预览：`--from-run DIR --rebuild-clip`（不调模型）。

## 运行

从仓库根目录：

```bash
python3 versions/anim_sketchagent_2d_v1/src/glm_anim_2d.py \
  --task catwand --model glm-5.3 --keys 3 --frames 12 \
  --plan-effort high --key-effort high --first-key-effort high --draw-effort medium \
  --out outputs/path2d_catwand
```

`--model`：`gpt-5.6-sol`（默认）、`deepseek-flash`（DeepSeek-V4.1-Flash）、`deepseek-v4-flash`、`glm-5.3`。GLM 没有 `medium` thinking，会落到 `low`。

```bash
python3 versions/anim_sketchagent_2d_v1/src/glm_anim_2d.py \
  --task catwand --model glm-5.3 --from-run outputs/path2d_catwand \
  --redraw-frame 3 --draw-effort high \
  --redraw-note "keep FROM height; do not flatten the cat"
```

```bash
python3 versions/anim_sketchagent_2d_v1/src/glm_anim_2d.py \
  --from-run outputs/path2d_catwand --rebuild-clip
```

评测短任务默认套件：`bounce`、`billiards`、`bottleshot`、`badminton`、`catjump`。另有 `catwand` 等。

## 代表结果

| 任务 | 目录 |
|---|---|
| 羽毛球对打 | `examples/path2d_badminton_rally/` |
| 打瓶子 | `examples/path2d_bottleshot/` |
| 逗猫棒（含 f02/f03 单帧重绘） | `examples/path2d_catwand/` |

样例只保留 plan、最终 key、帧 PNG/JSON、GIF / contact sheet。

## 测试

```bash
cd versions/anim_sketchagent_2d_v1/src
python3 -m unittest -v test_anim_2d.py
```

```bash
cd versions/anim_sketchagent_2d_v1
shasum -a 256 -c SHA256SUMS
```

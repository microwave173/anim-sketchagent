# Anim SketchAgent 2D v1（冻结）

冻结日期：2026-08-26。

这是当前已经可用的 **2D pose-to-pose 动画 SketchAgent**：Planner 只出稀疏关键帧，Drawer 只画那些 key，中间帧按 `<id>` 几何插值。不要在这份快照上继续改 prompt；新实验请复制目录或改 `experiments/grpo_sa_pilot/`。

源码副本、suite 入口、完整 gold 和代表输出都在本目录中；不再依赖工作目录里的样例文件。运行仍依赖项目根目录的 `third_party/SketchAgent-main/` 与 `.env`。校验：

```bash
cd versions/anim_sketchagent_2d_v1
shasum -a 256 -c SHA256SUMS
```

## 方法

```text
用户一句 prompt
  -> GLM-5.3 文本 Planner（无视觉）
       action 扩写 + keys[] + gaps[]
  -> GLM-5.3 Drawer 只画 keys（SketchAgent XML，50×50，原点左上）
  -> 可选：DeepSeek 视觉只审 key（默认可关 --no-reflect）
  -> 按 <id> lerp 中间帧
  -> GIF + contact sheet
```

- 关键帧数量 ≥2，由 Planner 决定（`--keys` 可钉死）。
- 总帧数默认约 12，由 keys + `n_inbetween` 决定（`--frames` 可钉死）。
- 运动人物身高约画布边长 1/4–1/3；Drawer 不要抄 circle 示例的直径，整个人等比例缩小。
- 身份（头大小/体型）写 UNCHANGING；手臂、重心、飞行物要动，但只做一件清楚的事。

## 模型

| 步骤 | 模型 |
|---|---|
| Plan / 画 key | glm-5.3（文本，无视觉） |
| 审 key（可选） | `deepseek-v4-flash-vision-exp` |
| 中间帧 | 代码 lerp，不再调模型 |

## 目录

```text
src/       冻结源码，以及 run_key_suite.py / run_naive_suite.py
gold/      9 个 pose-to-pose gold clip 与 manifest
examples/  basketball_scale2 / badminton_rally / saber_free
```

## 运行（推荐从工作副本）

```bash
cd experiments/grpo_sa_pilot
python3 glm_anim_keys.py --task basketball --no-reflect --out outputs/glm53_keys_basketball_scale2
python3 glm_anim_keys.py --task badminton --no-reflect
python3 glm_anim_keys.py --task saber --no-reflect
```

短 user prompt 任务：`basketball`、`badminton`（一句英文）。更早的长 prompt 任务仍在 `TASKS` 里（kick / saber / …）。

## 当时较好的样例

| 任务 | 目录 |
|---|---|
| 篮球（比例更接近 1/3） | `examples/basketball_scale2/` |
| 羽毛球对打 | `examples/badminton_rally/` |
| 格挡子弹 | `examples/saber_free/` |
| 早期 gold 套件 | `gold/pose_to_pose/` |

看片协议见 `gold/README.md`：身份是否同一人、接触/分离是否发生、锚点是否漂移、节奏是否一边鞭一下爬。

## 3D 续作

同结构的 3D 版在 `experiments/anim_3d/`：key 用逐步 Path3D incremental（无批量反思），中间帧用单次 Path3D one-shot。

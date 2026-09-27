# V2 平面实体问题：提示词对照与修订

本批次已按用户要求暂停，停止 launcher 和 API worker，保留成果及 checkpoint。未自动重启，也没有修改已生成的几何。以下修订仅经过代码测试，未做新的模型生成。

## 实际证据

`outputs/previous_12_parallel_24_legacy_style/ramp_seesaw_basket/3d/animation.json` 的全部帧中，`basket_rim`、`basket_body` 的端点及控制点均为 y=0。桶口是 x-z 竖直平面上的椭圆，桶身也在此平面。投影可以产生立体观感，但它不具有桶的空间深度。同一帧斜坡和跷跷板有深度，说明问题是实体构造退化，不能用整个场景有不同 y 值来证明每个物体都为实体。

前一批 `previous_12_parallel_24` 中对应篮筐的 y 值有 -0.09、0.06、0.21，说明平面化并非 V2 每次必然发生。它不是严格控制变量实验，也不能仅凭多个 y 值认定形状完全正确。

## 提示词差异

| 位置 | 旧版备份 | 原 V2 |
|---|---|---|
| Planner | `anim_3d/prompts.py` 的 KEY_PLAN_SYSTEM 明确要求球体多个垂直大圆、箱体前后连接边、各视图能看出体积，禁止 flat circular billboard | 共享 Markdown planner 主要强调故事、时间、简洁轮廓；没有形状级空间构造要求 |
| Key 绘画 | 同文件 key_draw_user 再次注入 Spatial volume (hard)，并要求保留 depth construction | 只有 Path3D 协议的 Use real depth, not flat 2D geometry，加上共享风格、身份约束 |
| 身份延续 | identity_anchor_context 明确保留 box thickness、depth construction、各视图附件关系 | 保留 ID、尺寸、比例、特征形状，但缺少具体空间结构约束 |
| 检查 | 本次未证明旧版有统一的实体体积强制检查 | 路径格式、范围、ID 与时间覆盖合法即可接受，不判断空间体积 |

旧版来源：`baseline_snapshot_20260927/experiments/anim_3d/prompts.py`，重点见 KEY_PLAN_SYSTEM、key_draw_user、identity_anchor_context。V2 来源：`scene.py`、`prompts/PLANNER.md`、`prompts/ANIMATION_GUIDE.md`。

## 判断及其限度

最直接的实现差异是重构时丢失了旧版具体的空间构造提示。简洁线稿/闭合轮廓偏好没有同时要求实体深度，可能进一步诱导模型用二维图标表达桶和球。模型在 XYZ 语法中成功输出一个轮廓，不代表它理解了真实三维形状。

因此提示词遗漏是有依据的原因假设；没有相同随机条件下的消融实验，不能断言这是唯一原因，或旧版绝不会平面化。全部关键帧 one-shot、采样差异和模型执行偏差也没有在本次证据中被排除。Gap 并发不是桶最初平面化的直接来源：桶在首个关键帧就已是平面，后续固定背景复用保持了该形状。

## 已做修订

新增 `prompts/SPATIAL_3D.md`，仅在 3D planner、key 和 gap 注入：实体不能是平面 billboard；球、箱、桶采用少量有实际深度且对应连接的轮廓；竖直桶口在水平 x-y 平面展开；禁止用任意 y 抖动伪造体积。真实平面物体、火柴人单线肢体和单平面运动保持合法。

没有增加 planner 字段、parts 库、额外检查轮次或默认多视图渲染。将来恢复测试应使用新目录，原批次是旧提示词结果；需要视觉检查及不同视角验证，不能仅靠代码测试宣称问题已解决。

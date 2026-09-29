# Anim SketchAgent 研究与优化历程

本文记录 Light V2 / KeyGap 从实验原型到 JointPlanKey v2.1.0 的主要判断、证据和设计变化。具体运行方法见 `LIGHT_V2_USAGE_ZH.md`。

## 1. 研究问题

项目目标不是单纯增加 agent 步骤，而是证明相对一次性生成全部帧的 Naive baseline，结构化 agent 在明确场景中具有优势。当前核心假设有两类：

1. Storyboard 能把简短故事扩充为更丰富、节奏更合理的可见事件。
2. 时间线拆成 sparse keys 与局部 gaps，能提高长动画的完成率、后段结构稳定性和局部细节。

每个新增模块首先要对短中任务近似无损，再通过针对性任务验证优势。

## 2. Naive baseline 与长度 gap

Naive 使用一次模型调用返回完整时间线，与 staged agent 共用绘画 prompt、Path2D/Path3D 协议、校验器和渲染器。128 帧 2D/3D 实验确认：

- Naive 的局部动作可以很好，例如包裹运输任务的下雨段。
- 长输出容易出现后段形态崩坏，例如腿部拉长、头部变扁和楼梯穿模。
- 3D 长任务会逐渐把物体与场景结构画得过于简单。
- 任何一帧的路径语法错误都可能让整个 one-shot 结果失效；3D 风车样例达到 384K 输出上限并截断。
- Staged 的主要收益是长输出可完成性、局部错误隔离和可恢复性，代价是更多 token 与调用。

详细结果见根目录 `NAIVE_VS_STAGED_ONE_PAGE_ZH.md`。

## 3. 统一绘画合同

为了让对比只反映 agent 结构，Naive、KeyGap keys 和 KeyGap gaps 逐步改为共用同一绘画 system prompt。Gap 的用户输入收缩为：

- 当前局部事件与退出状态；
- 局部帧数和时间；
- FROM 与 TO 两端 keyframes。

移除了全局故事重复、首帧身份参考、前后多个 keys、强制 stroke ID 白名单和固定静态锚点。坐标超出可见区域不再被校验器拒绝，由 SVG viewport 正常裁切。

## 4. 视觉和格式优化

- 2D 使用标准 SVG path `d` 数据，程序固定白底、黑线、统一线宽、圆角端点和连接。
- 模型不能改变颜色或线宽；每条 stroke 保留稳定语义 ID 与 description。
- 低分辨率设计后平滑放大，角色和物体保持适中比例，为移动、跳跃和转向留出空间。
- 提示词强调圆形人物头部、步行腿部交替、支撑脚、准确接触和动作因果。
- 3D 同步 2D 的故事、节奏、构图和小画布原则，只保留维度与投影差异。
- 动物默认保持物种典型的四足姿态，使用嘴、爪、头和身体重量操作物体，避免无意拟人化。

## 5. Storyboard 消融

60 帧 one-shot 消融比较了普通 Naive 与 storyboard-conditioned Naive。Storyboard 版本通常产生更丰富的事件，未观察到稳定的基础绘画能力下降；也暴露了过度拟人化和故事过长的风险。由此得到两个要求：

- Storyboard 应扩充可见情节和分配时间，不能为了丰富而加入无法在片长内读清的动作。
- 用户要求的动作必须出现在时间线内，不能只写在故事摘要或放到 frame 1 之前。

## 6. 从 keys reasoning 发现冻结 Storyboard 的问题

猫鼠 60 帧 keys request 的完整 reasoning 表明，模型知道自己只需输出 sparse keys，却在绘画阶段才发现上游故事的空间冲突：箱子开口、支点、猫设置机关的位置以及后续伏击位置难以同时成立。模型反复修改几何和站位，最后把无法解决的换边留给未绘制帧。

旧流程的问题是：

```text
Request A 生成并冻结 storyboard
Request B 绘制 keys 时才发现空间或动作问题
Request B 无权修改 storyboard，只能局部妥协
```

Reasoning 并非完全多余；真正浪费的是它发现问题后不能反馈到故事设计。完整分析见 `JOINT_STORYBOARD_KEYFRAMES_ZH.md`。

## 7. JointPlanKey

v2.1.0 把 storyboard 与 sparse keys 合并到一次请求：

```text
用户故事
  → 一次 reasoning 联合决定故事、节奏、空间和 key poses
  → 同时输出结构化 storyboard 与完整 sparse keys
  → 并行 gaps
  → SVG/GIF 渲染
```

模型尝试构造 key 时，如果发现换边、遮挡、接触或时间不足，可以在最终回答前直接修改 beat。Storyboard 因而成为已通过可绘制性检查的决策记录，而不是不可修改的上游合同。

联合输出使用 JSON envelope，是为了可靠关联 beat ends、key indices 和几何 frames；程序仍导出便于阅读的 `storyboard.md`。

## 8. 猫鼠联合回归

V1 联合运行一次通过，联合阶段使用 99,054 reasoning tokens，但为了易画把搭陷阱移到了 frame 1 之前。V2 明确要求所有用户动作在 beats 内可见，最终完整表现猫用鼻子推动奶酪、抬起箱子、退到伏击点、老鼠取饵、猫扑击和箱子反扣。

V2 成功联合响应使用 177,942 reasoning tokens，相比旧 planner + keys 的 242,993 tokens 少约 27%。该次运行最初因模型使用共享 beat 边界 `1-9, 9-18` 而整包重试；当前 prompt 已明确独占范围格式，解析器也会确定性归一化共享边界。

这说明联合设计能够让绘画反馈修正故事，但单次 reasoning 仍可能很长。后续优化应分别测量联合阶段与 gaps，避免用一条全局规则降低质量。

## 9. 当前结论与下一步

- JointPlanKey 是当前默认架构，旧两阶段模式保留用于对照。
- 继续用多任务实验验证联合设计是否稳定降低 token、提高相邻 keys 可连接性，并保持情节丰富度。
- Gap reasoning 仍是主要成本之一，需要分析哪些局部任务产生重复坐标推演。
- 大型联合响应出现局部 SVG 错误时，应优先做局部几何恢复，避免重画有效 storyboard 与全部 keys。
- 3D 评测优先采用连续空间与固定主视角，减少分镜切换和三维重建问题混杂。

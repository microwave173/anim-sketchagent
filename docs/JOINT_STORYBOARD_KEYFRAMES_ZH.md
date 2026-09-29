# JointPlanKey：一次请求联合生成 Storyboard 与 Keyframes

> 状态：已实现并成为 Light V2 默认模式；旧 `storyboard` / `json` 两阶段模式保留为显式回退与实验对照。

## 决策摘要

将当前串行的“先生成 storyboard，再用另一次请求生成全部 keys”改为一次请求联合生成 storyboard 和 sparse keyframes。Storyboard 不再是提前冻结、随后只能被执行的上游文本，而是模型在确认关键姿势确实可画、相邻 keys 确实可连接之后，对最终故事设计的结构化记录。

后续 gap 并行流程保持不变：联合请求完成后，程序从同一个响应中取得 beat 时间表和 keyframes，再让每个 gap 使用局部 beat、FROM key 和 TO key 补齐中间帧。

## 当前实现

- CLI：`light_agent/cli.py`，`--plan-format joint`，当前默认值即为 `joint`。
- 联合控制流：`light_agent/pipeline.py`，checkpoint stage 为 `joint_plan_keys`。
- 联合提示词：`light_agent/prompts/JOINT_PLAN_KEYS.md`。
- 联合 system prompt 构造：`light_agent/drawing_prompt.py::joint_plan_key_system`。
- Storyboard JSON 校验及 Markdown 导出：`light_agent/storyboard.py`。
- 机器产物：`joint_plan_keys.json`；人读产物：`storyboard.md`。
- `--debug` 保存联合 prompt、每次响应和每次 `reasoning_content`。
- 单元测试覆盖联合生成、并行 gaps、checkpoint 恢复及共享 beat 边界归一化；部署时 15 项测试通过。

联合 JSON 是模型与程序之间的机器接口，不改变 storyboard 的人读形式。程序会把结构化 storyboard 导出为 Markdown。使用 JSON 的原因是需要在同一响应内可靠关联 beat ends、key indices 和 SVG keyframes。

## 这项设计来自什么观察

猫鼠 60 帧实验对原始 keys drawing request 做了独立重放，并记录了完整 `reasoning_content`：

- 指定 keys：`[1, 11, 20, 27, 37, 45, 53, 60]`
- keys 输出数量正确：8 帧
- reasoning：110,525 tokens，324,584 字符
- wall time：464.646 秒

完整证据位于：

- `outputs/keygap_v4_cat_mouse_natural_60f_keys_replay_reasoning/REASONING_SUMMARY_ZH.md`
- `outputs/keygap_v4_cat_mouse_natural_60f_keys_replay_reasoning/keys_reasoning.txt`
- `outputs/keygap_v4_cat_mouse_natural_60f_keys_replay_reasoning/keys_prompt.txt`

Reasoning 表明，模型并没有误解成需要输出全部 60 帧。它知道只需输出 8 个 keys，但在绘画阶段才发现 storyboard 的空间和机械调度难以同时成立：箱子的开口、支点和旋转方向决定猫需要在右侧设置木棍，而后续 key 又要求猫已经退到箱子左侧。模型反复讨论并修改箱子几何、猫的站位、遮挡和过渡方案，最后因为 F21–F26 不属于 keys request，接受了 F20 到 F27 之间难以自然连接的换边。

## 当前两次请求为什么浪费 reasoning

当前流程是：

```text
用户故事
  → Request A：决定 storyboard
  → 冻结为自然语言 storyboard
  → Request B：理解 storyboard、设计空间并绘制 keys
  → 并行 gaps
```

Request A 结束后，故事和 beat 已经冻结。Request B 即使在真正构造 SVG 时发现以下问题，也无法修改 storyboard：

- 某个动作在指定镜头中无法清楚表现；
- 角色需要在相邻 keys 之间突然换边、转向或重新布置；
- 道具的支点、开口、接触和最终状态互相冲突；
- 给定帧数不足以完成 storyboard 暗含的过渡；
- 自然语言上合理的事件无法形成易连接的边界姿势。

因此 keys drawer 只能反复寻找局部补丁。它可能改变构图、近似物理关系，或者把困难动作藏在未采样的帧段中，但无论 reasoning 多充分，都不能回头修改造成问题的故事设计。这些推演没有进入可执行的 storyboard，也无法消除上游矛盾。

问题的本质不是 keys drawer 思考得不够少，而是做出最终空间决策的模型没有修改故事的权限。

## 联合生成如何解决

新流程是：

```text
用户故事
  → 一个 Request：联合决定故事、节奏、空间调度和 key poses
  → 同时输出 storyboard + sparse keyframes
  → 校验二者对应关系
  → 并行 gaps
```

同一次 reasoning 中，模型可以循环执行：

1. 提议一个 beat 和退出状态；
2. 尝试构造对应 key pose；
3. 检查它与前后 key 是否能在给定帧数内连续连接；
4. 如果画的时候发现换边、遮挡、接触或空间冲突，直接修改 beat 或 key pose；
5. 最终同时提交已经互相一致的 storyboard 和 keys。

这样，绘制 keys 时产生的新信息会反馈到 storyboard。Reasoning 仍可用于解决真正必要的问题，但不会被迫围绕一个已经冻结且不合理的设计反复打补丁。

## Storyboard 在新流程中的角色

Storyboard 仍然保留，因为它负责：

- 把简短用户 prompt 扩充成可见的故事；
- 按真实播放时间分配 beats；
- 为每个 gap 提供局部事件和退出状态；
- 作为可读的规划记录和实验分析材料。

它应当是联合决策的结果，不是绘制之前不可修改的合同。Storyboard 只记录最终事件、时间范围、镜头和必要的空间关系；无需解释力矩、精确碰撞或详细推导。

## 建议的响应结构

```json
{
  "storyboard": {
    "shot": "continuous side view",
    "notes": ["stable camera", "natural quadruped animals"],
    "beats": [
      {
        "start": 1,
        "end": 11,
        "event": "...",
        "exit": "..."
      }
    ]
  },
  "keyframes": [
    {
      "i": 1,
      "strokes": [
        {"id": "...", "d": "M ...", "description": "..."}
      ]
    }
  ]
}
```

响应校验应保证：

- 每个 beat 的 `end` 对应一个 keyframe；
- key indices 严格递增并覆盖首尾帧；
- beats 连续覆盖完整时间线；
- storyboard 中的角色、道具和关键状态能在对应 key 中找到；
- 相邻 keys 不依赖瞬移、无说明的换边或无法容纳的复杂重排。

## 联合请求的提示词重点

建议直接表达以下职责：

> Plan the storyboard and draw its sparse keyframes as one jointly consistent result. Revise the storyboard whenever constructing a key pose reveals an unclear action, spatial conflict, or transition that cannot fit the available frames.

> Every adjacent pair of keyframes must be connectable by a simple continuous action within its assigned interval. Do not hide a teleport, side switch, major restaging, or unshown mechanical operation between sampled keys.

> Use simple readable cartoon mechanics. Do not explain or prove forces, torques, or exact collisions. Choose the simplest staging that communicates the event and is drawable at the target resolution.

这几条的目的不是禁止 reasoning，而是让 reasoning 有权修正 storyboard，并让最终输出只保留已经收敛的设计。

## 预期收益

- Storyboard 与 keys 来自同一组空间和动作决策。
- 绘画阶段发现的问题可以直接修正故事与节奏。
- 减少 planner 与 keys 对同一动作的重复推演。
- 降低相邻 keys 难以连接、迫使 gap 补救的概率。
- 保留 storyboard 的情节丰富度和时间规划价值。
- 保留 gaps 的并发、局部错误隔离和长任务可完成性优势。

## 风险与验证

联合响应更长，一个格式错误可能同时影响 storyboard 和 keys；需要整体 checkpoint、严格 schema 校验，以及仅针对格式错误的重试。模型也可能为了易画而过度简化故事，因此实验仍需评估情节丰富度。

第一组受控实验应使用同一用户 prompt、模型、thinking、token 上限和 gap 流程，对比：

1. 当前 `storyboard request → keys request`；
2. `JointPlanKey request → storyboard + keys`。

记录并比较：

- planner + keys 的总 reasoning tokens、总 completion tokens 和 wall time；
- storyboard 的情节丰富度与节奏；
- 相邻 keys 的可连接性；
- gap 中的穿模、瞬移、身份漂移和动作阶段错误；
- 最终动画质量；
- 完整响应和各 gap 的成功率。

猫鼠箱子任务适合作为首个回归样例，因为现有 reasoning 已明确暴露 storyboard 冻结后无法修正的问题。

## 首轮猫鼠回归结果

测试设置：2D、60 帧、120 ms/frame、640px、high reasoning、`max_tokens=393216`、8 个 gap workers；动物要求始终自然四足。

### JointPlanKey V1

- 输出：`outputs/jointplankey_v1_cat_mouse_natural_60f`
- 一次联合调用成功，联合阶段 431.124 秒、99,054 reasoning tokens。
- 完整运行 747.618 秒，7 个 keys、6 个 gaps。
- 相比旧两阶段原始猫鼠运行的 planner + keys 共 242,993 reasoning tokens，联合阶段减少约 59%。
- 联合 reasoning 能直接修改故事机关，没有再进行力矩证明；但故事简化过度，把猫搭陷阱移到了 frame 1 之前，实际 beats 从老鼠接近已搭好的陷阱开始。

### JointPlanKey V2

- 输出：`outputs/jointplankey_v2_cat_mouse_natural_60f`
- Prompt 增加：用户要求的动作必须在 beats 内可见；frame 1 位于最早必需动作之前；storyboard 不写坐标或物理计算；长区间优先用于可见运动。
- 成功 storyboard 从猫用鼻子推奶酪、抬起箱子开始，完整包含搭陷阱、退到伏击点、老鼠取饵、猫扑击、箱子反扣和结尾。
- 最终输出 8 个 keys、7 个并行 gaps、60 帧完整动画；猫鼠整体保持动物造型。
- 成功的第二次联合响应使用 177,942 reasoning tokens；单次仍比旧 planner + keys 合计少约 27%。
- 本次总墙钟 1,647.950 秒，因为第一次响应写成共享 beat 边界 `1-9, 9-18...`，旧解析器触发整包重试，两次联合 reasoning 合计 333,962 tokens。

共享边界在动画语义上有效，只是与程序的独占帧区间表示不同。当前 system prompt 已明确要求 `1-9, 10-18, 19-26`，解析器也会把 `1-9, 9-18, 18-26` 确定性归一化，不再为这一表示差异重画 storyboard 和 keys。

首轮结果支持联合设计的核心动机：模型在画 keys 时可以改变故事机关与空间调度，并把修改后的故事一起提交。它也暴露了两个需要继续评测的问题：单次联合 reasoning 仍可能很长，以及较大的联合响应需要针对真正的局部 SVG 错误设计比整包重试更细的恢复策略。

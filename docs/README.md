# Anim SketchAgent 文档索引

这是项目文档的统一入口。文档不搬迁，以免破坏已有链接；这里按用途和状态整理。

## 建议阅读顺序

1. [项目 README](../README.md)：仓库入口、版本和目录。
2. [Light V2 使用与服务器部署](LIGHT_V2_USAGE_ZH.md)：当前命令、参数、输出和恢复方法。
3. [KeyGap 优势与评测](KEYGAP_ADVANTAGES_AND_EVAL_ZH.md)：研究目标、无损要求和实验设计。
4. [JointPlanKey 架构决策](JOINT_STORYBOARD_KEYFRAMES_ZH.md)：基于 keys reasoning 观察提出的下一版核心改进。
5. [研究与优化历程](RESEARCH_HISTORY_ZH.md)：从 Naive 对照、绘画合同到 JointPlanKey v2.1.0 的完整演进。

## 当前实现

| 文档 | 状态 | 用途 |
|---|---|---|
| [Light V2 使用与服务器部署](LIGHT_V2_USAGE_ZH.md) | 当前 | 运行 2D/3D KeyGap、Naive、断点恢复及查看输出。 |
| [标准 SVG 输出](SVG_OUTPUT_ZH.md) | 当前 | 2D 标准 SVG schema、固定样式与导出文件。 |
| [Light V2 设计草案](../light_agent/DESIGN_ZH.md) | 当前实现背景 | 解释 Light V2 的最初取舍；部分研究方向可能早于最新实验结论。 |
| [3D 空间审计](../light_agent/SPATIAL_3D_AUDIT_ZH.md) | 当前参考 | 3D 坐标、相机和空间结构检查。 |

## 研究问题与架构决策

| 文档 | 状态 | 用途 |
|---|---|---|
| [KeyGap 优势与评测](KEYGAP_ADVANTAGES_AND_EVAL_ZH.md) | 当前研究框架 | Storyboard 与时间线拆分应产生什么优势，以及怎样证明。 |
| [JointPlanKey：联合生成 Storyboard 与 Keys](JOINT_STORYBOARD_KEYFRAMES_ZH.md) | 当前默认架构 | 说明冻结 storyboard 的问题、联合实现、猫鼠回归数据和恢复策略。 |
| [研究与优化历程](RESEARCH_HISTORY_ZH.md) | v2.1.0 总结 | 汇总近期实验观察、关键设计选择和下一步问题。 |
| [JSON Plan 并行版](JSON_PLAN_PARALLEL_ZH.md) | 暂停实验 | 记录 JSON plan 路线和运行方式；当前没有作为优先方向。 |

## 实验观察与总结

| 文档 | 状态 | 用途 |
|---|---|---|
| [Naive 共性问题](NAIVE_COMMON_ISSUES_ZH.md) | 持续补充 | 每个共性问题一句话的观察清单。 |
| [Naive vs Staged 一页总结](../NAIVE_VS_STAGED_ONE_PAGE_ZH.md) | 已完成实验 | 128 帧 2D/3D 长任务的主要结果。 |
| [已完成工作与产物](../PROJECT_WORK_SUMMARY_ZH.md) | 项目记录 | 已实现功能、实验和重要输出位置。 |
| [JointPlanKey 架构决策](JOINT_STORYBOARD_KEYFRAMES_ZH.md) | 已完成实验 | 汇总猫鼠 keys 独立重放的 reasoning 观察、统计及由此形成的架构决策。 |

## 验证记录

| 文档 | 状态 | 用途 |
|---|---|---|
| [服务器验证记录](SERVER_VALIDATION.json) | 时间点快照 | Python、测试、smoke run 和依赖版本；不代表之后每次修改都已重新验证。 |

## 当前关键结论

- KeyGap 的目标是让 storyboard 丰富情节与节奏，让 gaps 提高长任务完成率和局部细节，同时对短任务近似无损。
- 已记录的 keys reasoning 显示：模型会在真正构造几何时发现冻结 storyboard 的空间与动作问题，却无法回头修改故事。
- JointPlanKey 已实现为默认流程：一次请求联合生成 storyboard 和 sparse keyframes，再保持现有 gap 并行流程；旧两阶段模式仍可用于消融。

# Incremental Path3D Drawer Base v1

冻结日期：2026-07-26。

这是目前作为项目基础的 3D Incremental Drawer 设计。该快照保存当前已经验证的角色边界和行为，后续 capability probe、Scout 和 capability-aware planning 实验不得直接修改本目录。

## 基础设计

```text
Target
  -> Visual Planner
  -> Autonomous Visual Editor
  -> Structured JSON patch
  -> Path3D compiler and four-view renderer
  -> next visual review
```

Planner 只负责：

- 查看 front、side、top、perspective 四视图；
- 判断当前最重要的视觉问题；
- 给出高层 objective、priority 和 success criteria；
- 决定继续、重建、回滚或结束。

Planner 不负责：

- 解释具体应该画多少笔；
- 指定坐标或 Q3/C3 控制点；
- 指定 stroke ID、增删列表或保护列表；
- 替 Editor 决定对象内部的几何分解。

Editor 同时看到完整 scene 和四视图，自行决定对象理解、绘画方法、stroke 数量、局部修改或整体重建。默认单个 patch 最多新增或删除 48 个 semantic strokes，该限制只用于拦截异常输出。

## 基线状态

- Structured JSON 是模型输出协议；
- 编译后的 Path3D 是渲染协议；
- 视觉角色使用四视图 contact sheet；
- JSON repair 会携带原始错误响应和解析错误；
- reflection 使用最多 6 条的短结构化 experience；
- 该版本在 `baby bunny on pancakes` 实验中允许 Editor 自主执行 18-22 stroke 的完整重建。

## 使用

```bash
PYTHONPATH=versions/path3d_incremental_base_v1:versions/v1.4:versions/path3d_json_v1:versions/path3d_v1:. \
python3 -m path3d_json_agents incremental \
  --prompt "A complex 3D object" \
  --output outputs/base_incremental_run
```

## 完整性

`SHA256SUMS` 记录行为关键源码和测试文件。检查：

```bash
cd versions/path3d_incremental_base_v1
shasum -a 256 -c SHA256SUMS
```

原开发目录说明保存在 `README_SOURCE_ZH.md`。

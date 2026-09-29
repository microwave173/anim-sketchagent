# Light V2 标准 SVG 输出

2D 模型输出仍使用 JSON 批次封装，以便一次生成多个帧；每条笔画的几何已经改为标准 SVG `path` 的 `d` 数据：

```json
{
  "i": 1,
  "strokes": [
    {
      "id": "actor_head",
      "d": "M -0.2 0 C -0.2 0.2 0.2 0.2 0.2 0 C 0.2 -0.2 -0.2 -0.2 -0.2 0 Z",
      "description": "circular head"
    }
  ]
}
```

`id` 是跨帧稳定的部件标识，`description` 说明该笔画的语义。模型不能指定样式；即使响应中出现样式字段，验证器也会忽略它们。

每次 2D 运行额外导出：

- `animation.svg`：用 CSS 分帧播放的标准 SVG 动画。
- `frames_svg/frame_XXXX.svg`：每帧一份独立标准 SVG。
- `animation.json`：含 `d`、`id`、`description` 的结构化时间线。
- `presentation.json`：记录实际固定样式和输出线宽。

SVG 渲染约束由程序统一执行：

- `fill="none"`
- `stroke="#000000"`
- 所有 path 使用相同的固定 `stroke-width`
- `stroke-linecap="round"`
- `stroke-linejoin="round"`
- 每个 `<path>` 带 `data-part-id`、`data-description` 和 `<title>`

坐标范围仍为 `[-1,1]`，模型按 `+y` 向上绘制；标准 SVG 根节点使用 `viewBox`，绘图组使用 `transform="scale(1 -1)"` 完成坐标转换。旧 checkpoint 中的 `path` 字段可继续读取，但新输出统一写成 `d`。

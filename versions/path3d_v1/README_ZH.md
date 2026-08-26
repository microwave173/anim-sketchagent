# Path3D v1

这是一个独立的 3D 空间笔画实验。它保留 SVG path 的“控制笔尖移动”思想，但每个点使用三维坐标。

## 语法

```text
M x y z
L x y z
Q3 cx cy cz x y z
C3 c1x c1y c1z c2x c2y c2z x y z
Z
```

- `+x` 向右，`+y` 向场景深处，`+z` 向上；
- v1 只接受大写绝对命令；
- 三维曲线使用 `Q3`/`C3`，避免模型把它们误解成二维 SVG 的 4/6 参数命令；解析后仍对应标准 quadratic/cubic Bezier 数学定义；
- 与标准 SVG 类似，同一命令后可以连续提供多组坐标；`M` 后的额外坐标组视为 `L`；
- 同一个 path 可以用多个 `M` 创建多个 subpaths；
- 坐标建议在 `[-1, 1]`，渲染器会对整个 scene 居中并等比缩放；
- Path3D 是项目自定义格式，不是标准 SVG。

## 曲线选择

- `Q3` 后是两组三维点：`[control] [endpoint]`，共 6 个数字；适合圆弧、轮子、圆环、圆润截面和简单单向弯曲。
- `C3` 后是三组三维点：`[control 1] [control 2] [endpoint]`，共 9 个数字；适合 S 形尾巴、颈部、空间轨迹，或需要分别控制离开起点和接近终点方向的曲线。
- 多段曲线必须在每段前重新写 `Q3` 或 `C3`，不能把下一段的不完整参数直接堆在前一命令后。
- `L` 只用于真正的直线结构，不应用折线代替本应平滑的有机轮廓。

正确的多段 `Q3` 空间圆和单段 `C3` 空间 S 曲线示例、实验来源及渲染见：`outputs/PATH3D_SPATIAL_CIRCLE_EXPERIMENT_20260726.md`。

## CLI

```bash
PYTHONPATH=versions/path3d_v1:. \
python3 -m path3d \
  --prompt "A simple 3D wireframe chair" \
  --output outputs/path3d_chair \
  --model gpt-5.6-terra
```

输出包含模型原文、结构化 `scene.json`、四视角 PNG 和 `contact_sheet.png`。

只渲染已有 scene，不调用模型：

```bash
PYTHONPATH=versions/path3d_v1:. \
python3 -m path3d.render_cli \
  --scene outputs/path3d_single_chair_terra_c3_v1/scene.json \
  --output outputs/path3d_chair_rerender
```

渲染器参考 3DrawAgent 的多相机透视投影流程，但采用 NumPy 计算三维 Bezier 采样与相机投影、Pillow 超采样绘制，不依赖训练侧的 PyTorch/pydiffvg。当前输出是无表面的空间线稿；它按平均深度排序 strokes，但不做实体表面遮挡。

## 单次 LLM smoke

- Prompt：`A simple 3D wireframe chair with four legs, a rectangular seat, and a curved backrest`
- Model：`gpt-5.6-terra`，reasoning effort `medium`
- 输出：`outputs/path3d_single_chair_terra_c3_v1/`
- 结果：单次生成成功，9 个语义 strokes；座面、四腿、后侧支架和两条曲线椅背在四个视角中保持一致。

协议开发中发现，直接复用 `Q/C` 会触发模型强烈的二维 SVG 参数先验。最终改用 `Q3/C3` 明确区分三维曲线，解析后仍使用标准 quadratic/cubic Bezier 数学定义。此前失败的原始响应保留在 `outputs/path3d_single_chair_terra_v2/` 和 `outputs/path3d_single_chair_terra_v3/`，不计作最终 smoke。

## 测试

```bash
PYTHONPATH=versions/path3d_v1:. \
python3 -m unittest discover -s versions/path3d_v1/tests -v
```

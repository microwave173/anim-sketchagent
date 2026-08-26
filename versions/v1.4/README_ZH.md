# Drawer v1.4

v1.4 将标准 incremental 2D Drawer 与 incremental Path3D Drawer 合并为同一个 agent CLI tool。统一入口只负责分派；两种模式使用不同的 system prompts、坐标协议、document、validator、revision store 和 renderer。

```text
drawer_v14 CLI
├── --mode 2d -> SVG Planner / SVG Editor / 2D renderer
└── --mode 3d -> Path3D Planner / Path3D Editor / multiview renderer
```

## 2D

```bash
PYTHONPATH=versions/v1.4:. \
python3 -m drawer_v14 \
  --mode 2d \
  --prompt "A cute penguin" \
  --width 512 --height 512 \
  --output outputs/v1_4_penguin
```

2D 延续 incremental v1：原生 SVG path、Planner 视觉审稿、Editor 原子增删、不可变 revision、repair、rollback 和历史最佳选择。`--outline-only` 仅适用于 2D。

## 3D

```bash
PYTHONPATH=versions/v1.4:. \
python3 -m drawer_v14 \
  --mode 3d \
  --prompt "A simple 3D wireframe chair" \
  --width 512 --height 512 \
  --output outputs/v1_4_chair
```

3D 使用独立 Path3D 协议：

```text
M x y z
L x y z
Q3 cx cy cz x y z
C3 c1x c1y c1z c2x c2y c2z x y z
Z
```

每个 revision 渲染 front、side、top、perspective 和 contact sheet。3D Planner 必须同时观察四视角；3D Editor 看到完整 Path3D 并批量增删空间 strokes。

曲线使用规则：圆弧、轮子和简单圆润轮廓优先使用多段 `Q3`；S 形尾巴、颈部和需要独立控制两端切线的空间轨迹使用 `C3`。每段必须显式重复命令，并完整提供 xyz 控制点和终点。3D Planner 会把不必要的多边形化视为视觉问题。

## 通用参数

- `--mode 2d|3d`
- `--prompt TEXT`
- `--width INT`
- `--height INT`
- `--output PATH`
- `--model MODEL`
- `--max-rounds INT`
- `--max-patch-attempts INT`
- `--max-additions INT`

stdout 最后一行是单个 JSON 对象，适合作为 Manager/CLI agent tool 调用。

## 测试

```bash
PYTHONPATH=versions/v1.4:. \
python3 -m unittest discover -s versions/v1.4/tests -v
```

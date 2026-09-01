# Path2D v1

2D 线稿协议：与 Path3D 同构的 `scene.json`，坐标在 `[-1,1]`，`+x` 右、`+y` 上，原点在画布中心。

```text
M x y
L x y
Q cx cy x y
C c1x c1y c2x c2y x y
Z
```

动画实验入口：`versions/anim_sketchagent_2d_v1/src/glm_anim_2d.py`。早期 SketchAgent XML lerp 跑法在 `archive_xml_src/`。

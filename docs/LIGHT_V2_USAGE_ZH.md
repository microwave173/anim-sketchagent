# Anim SketchAgent Light V2 使用与服务器部署

## 版本与设计

本仓库并列保留两个 agent：Classic V1 位于 `versions/anim_sketchagent_2d_v1` / `versions/anim_sketchagent_3d_v1`，其代码和已有示例不改动；Light V2 位于 `light_agent/`，作为当前推荐入口。二者共用 Path2D/Path3D 格式库，不共用规划或绘画流程。

Light V2 所有片长统一使用：一次 Markdown 分镜规划 → 一次全部关键帧生成 → 各关键帧区间批量生成并发执行 → 结构校验及渲染。不要求 parts 表，不逐帧进行多轮绘画。默认最多六个 gap 并发；截断时区间拆批，拆批内部顺序执行。约定包括因果先后、主体身份、固定场景、可辨认接触和事件时序，但结构通过不保证视觉或物理正确。

2D 默认人物为圆头单线火柴人，动物简洁可爱；机器人用机械头、机壳与机械肢体。当前原生设计目标 320×320、原生线宽 4px，经 4 倍超采样、Lanczos 抗锯齿与双三次放大；640px 输出线宽约 8px。输出小于 320px 时使用较小原生画布。3D 使用真实空间坐标与有深度的物体，默认只渲染 perspective。风格位于 `light_agent/prompts/STYLE_2D.md`，渲染配置位于 `PRESENTATION_2D.json`，空间规则位于 `SPATIAL_3D.md`。

## 安装与 API

```bash
cd anim-sketchagent
python3 -m venv .venv-light
.venv-light/bin/python -m pip install -r requirements-light.txt
cp .env.example .env
```

在仓库根目录 `.env` 填写 `DEEPSEEK_API_KEY`，不要上传凭据。也可以使用同名进程环境变量（优先级高于 `.env`）。Light V2 仅依赖 numpy、Pillow、python-dotenv，不需要 GPU 或模型权重。

`--api-profile official` 固定使用官方 `https://api.deepseek.com` 与 `deepseek-flash`，凭据来自环境或 `.env`；为兼容旧工作区，可回退到根目录 `old_key.txt`，新部署无需这个文件。`--api-profile env` 使用 `.env` 的 `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL` / `DEEPSEEK_API_KEY`。阿里云 token-plan 域名发送 `enable_thinking=true`，其余端点发送 `thinking.type=enabled` 和 `reasoning_effort`。不对自定义端点的参数兼容性作保证。

默认 thinking high、max_tokens=393216、请求超时 600 秒；`--effort low` 可用于快速运行验证。预算包含思考和最终输出，以供应商实际支持为准；并非每次都用满预算。

## 生成动画

```bash
.venv-light/bin/python light_agent/cli.py \
  --prompt "A person pulls a fire alarm, triggering an overhead sprinkler that extinguishes a fire." \
  --dim 2 --frames 24 --frame-ms 120 --size 640 \
  --api-profile official --effort high --gap-workers 6 \
  --out outputs/sprinkler_2d
```

改 `--dim 3`，并使用新的 `--out outputs/sprinkler_3d` 即可生成 3D。帧数支持 40、60、120 等；内容和时长应相匹配。24 帧 × 120ms = 2.88 秒；120 帧 = 14.4 秒。并发可用 `--gap-workers 1` 降为串行；`--debug` 保存实际提示词。

相同命令、相同输出目录可以恢复成功阶段。任务、维度、帧数等变更须使用新目录；提示词源码改变会使对应 checkpoint 失效。恢复耗时保留在 `previous_sessions`，不要仅取最后一次请求时间作为完整实验耗时。

## 输出与耗时

每次运行目录包含：

- `storyboard.md`：模型规划及时间表。
- `animation.json`：完整逐帧路径；`clip.gif`、`contact_sheet.jpg`、`index.html`：展示产物。
- `metrics.json`：总墙钟、分阶段、每次 API 请求耗时与 usage、错误、恢复记录；`gap_wall_seconds` 为并发区间阶段实际墙钟。
- `request.json`：不含密钥的运行参数；`checkpoints/`：恢复数据与压缩响应；`presentation.json`：2D 实际渲染配置。

并发阶段时间相加是工作量，不等于总墙钟。长动画请求超时、输出截断和合法但画错是不同问题，需要结合日志、finish_reason 与视觉检查判断。进程结束返回码非零表示未成功，不应把输出目录存在当作完成。

```bash
.venv-light/bin/python light_agent/test_light.py
.venv-light/bin/python -m http.server 8000 --bind 127.0.0.1
```

本机浏览 `http://127.0.0.1:8000/outputs/sprinkler_2d/`。单元测试覆盖结构、批量生成、对象消失、固定背景、并发、截断拆批和恢复；不替代视觉评审。

## 当前 AutoDL 部署

SSH：`ssh -p 33993 root@connect.westd.seetacloud.com`。密码另行保存，不写入本文件。

部署目录：`/root/autodl-tmp/anim-sketchagent`；文档：`docs/LIGHT_V2_USAGE_ZH.md`；API 配置：根目录 `.env`（权限 600）；新版 Python：`.venv-light/bin/python`。

服务器的裸 `python3` 当前不在非交互 PATH，可用 `/root/miniconda3/bin/python` 建立虚拟环境。生成时进入部署目录并使用上面的虚拟环境完整路径。后台运行建议：

```bash
cd /root/autodl-tmp/anim-sketchagent
mkdir -p outputs/sprinkler_2d
nohup .venv-light/bin/python -u light_agent/cli.py \
  --prompt "A person pulls a fire alarm, triggering an overhead sprinkler that extinguishes a fire." \
  --dim 2 --frames 24 --size 640 --out outputs/sprinkler_2d \
  > outputs/sprinkler_2d/run.log 2>&1 < /dev/null &
```

查看日志：`tail -f outputs/sprinkler_2d/run.log`。不要把密钥或完整 `.env` 打印到日志。

如需浏览服务器 HTML，在服务器用虚拟环境启动绑定 127.0.0.1 的 http.server，然后本地：

```bash
ssh -p 33993 -L 8000:127.0.0.1:8000 root@connect.westd.seetacloud.com
```

本地浏览 `http://127.0.0.1:8000/outputs/`。部署只同步源码、已有小型示例和文档，不同步本地实验全集；新版结果写在 `outputs/`，不进入 Git。单个任务的 debug/checkpoint 数据会增加占用，确认不再需要恢复后可归档或移走；不要删除尚在运行任务的 checkpoint。

服务器部署验证记录见 `docs/SERVER_VALIDATION.json`，包括 Python、依赖、测试以及实际 2D/3D API 烟测。烟测用于验证环境与生成链路，少帧 low thinking 的结果不作为质量对比实验。

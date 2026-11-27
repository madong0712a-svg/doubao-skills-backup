---
name: bb-video
description: 将数学/物理问题自动生成 Manim 动画短片（MP4）或讲解文稿。当用户要求制作数学动画、物理演示视频、几何/公式可视化、把一个问题变成动画短片、或提到 Manim / Math-To-Manim / 数学视频 / 科普动画时使用。底层调用本地已安装的 math-to-manim CLI（mythos 六阶段流水线）。
---

# BB-Video（Math-To-Manim 本地封装）

把一个数学/物理问题（自然语言）交给本地 `math-to-manim` CLI，它经过六个推理阶段（意图→知识图谱→课程→数学档案→分镜→场景规格），生成 Manim 场景代码并渲染成 MP4。

## 固定路径（Windows 本地）

- 项目根目录：`C:\Users\madong\Doubao\tools\Math-To-Manim`
- 虚拟环境 Python：`C:\Users\madong\Doubao\tools\Math-To-Manim\.venv\Scripts\python.exe`
- CLI 可执行文件目录：`C:\Users\madong\Doubao\tools\Math-To-Manim\.venv\Scripts\`
- 产物输出：`C:\Users\madong\Doubao\tools\Math-To-Manim\runs\mythos\<时间戳-问题slug>\`

**每次执行前必须先 `Set-Location` 到项目根目录**，因为产物写到当前目录下的 `runs/`。

## 常用命令

用 `&` 调用完整路径的 exe，不要依赖 PATH：

```powershell
$root = "C:\Users\madong\Doubao\tools\Math-To-Manim"
Set-Location $root
$cli = "$root\.venv\Scripts\math-to-manim-mythos.exe"

# 1. 体检（检查 manim/ffmpeg/latex）
& $cli doctor

# 2. 离线演练（不调用模型，生成固定 4 镜头规格 + 场景代码，不渲染）
& $cli run "为什么陀螺会进动？" --offline

# 3. 完整生成（调用 Claude Code 模型 + 渲染成 MP4）
& $cli run "解释一个数学概念，用3D几何" --render -q m

# 4. 列出历史运行 / 查看某个运行状态
& $cli runs
```

画质档位（`-q`）：`l`=480p15（最快）、`m`=720p30（推荐）、`h`=1080p60、`k`=240p。

## 已确认的环境状态（2026-11 安装时）

- [ok] manim 0.22.1、ffmpeg 已就绪
- [ok] 离线（`--offline`）六阶段流水线可完整跑通
- [FAIL] **未安装 LaTeX / dvisvgm**：含 `MathTex`/`Tex` 的公式渲染会失败；纯几何图形和 `Text` 文字正常。需要公式渲染时提示用户安装 MiKTeX（Windows 推荐，per-user 安装，再用 MiKTeX Console 装 `dvisvgm` 和 Manim 模板宏包）。
- [--] 模型后端走本机 Claude Code CLI（`claude`），登录态未验证；真实生成前用户需先在终端完成 `claude` 登录。离线模式不需要任何模型/密钥。

## 执行要点

- 生成是长任务（模型阶段可能数分钟）；用后台任务跑并轮询输出，不要前台阻塞。
- 产物目录内关键文件：`01_intent.json` … `06_scene_spec.json`（各阶段结果）、`mythos_scene.py`（Manim 源码）、`manifest.json`（运行状态/失败原因）、渲染后的 `.mp4`。
- 若渲染报缺 `latex`/`dvisvgm`，属已知环境问题，直接在回复里说明并建议装 MiKTeX，不要反复重试。
- 不要把 `runs/` 当可清理缓存——里面是用户的作品，保留。

---
name: original-bgm-forge
description: |
  原创 BGM 生成工坊。按情绪/时长/主题创作可商用、零版权的原创背景音乐，三层引擎智能路由——
  ①物理建模合成（零依赖/纯CPU/秒级/100%原创/真乐器音色）②ACE-Step 1.5 本地开源大模型
  （MIT许可/商用级质量/4GB显存即可运行）③外部API（预留）。
  内置 12 种物理建模乐器音色（钢琴/古筝/木琴/钟/弦乐/竖琴/管风琴/电钢等），
  9 种情绪预设、23 组和弦走向、可自由换 seed 出不同曲目，支持视频时长自动匹配、
  批量出库、wav/mp3 输出、与 typography-video-pipeline 无缝对接。
  触发场景：「配个BGM」「生成背景音乐」「要原创配乐」「找不到合适的无版权音乐」
  「给视频做个原创BGM」「BGM太电音了想要真乐器」「换一首」。
  与 doubao-tts / local-whisper 的分工：本技能只管**配乐**，不碰人声与转写。
version: 1.1.0
license: MIT
tags: BGM, 原创音乐, 配乐, 物理建模, 音色合成, ACE-Step, 无版权, 短视频, 国学, 零依赖
slug: original-bgm-forge
display_name: 原创BGM生成工坊
display_name_en: Original BGM Forge
description_zh: 按情绪/时长/主题创作可商用、零版权的原创背景音乐。三层引擎：①物理建模合成（零依赖/纯CPU/秒级/真乐器音色，开箱即用）②ACE-Step 1.5 本地开源大模型（商用级质量，需本地部署权重）③外部 API（预留）。12 种乐器音色、9 种情绪预设、支持视频时长自动匹配、wav/mp3 输出。短视频/视频号/Vlog 配乐刚需。
description_en: "Create royalty-free original background music by mood, duration, and theme. Three-tier engine: physical-modeling synthesis (zero-dependency, CPU-only, instant, real instrument timbres, works out of the box), local ACE-Step 1.5 open-source model (commercial-grade quality, local weights required), and reserved external API. 12 instrument timbres, 9 mood presets, automatic video-length matching, wav/mp3 export. A must-have for short-video and Vlog scoring."
author: 用户自定义
agent_created: true
pricing: 免费
market_category: 内容创作
service_category: 工具/图片处理
category: 媒体生产
---

# 原创 BGM 生成工坊（original-bgm-forge）

> **🚀 30 秒上手**：绝大多数场景用 L1 就够了——`python scripts/bgm_forge.py --mood 治愈 --seconds 30 --out bgm.wav`，纯 CPU、零依赖、3 秒出曲，100% 原创零版权。想要更高质感再上 L2（ACE-Step，需自备 4.89GB 权重，见下文「技术参考」）。下文明细很长，普通用户看完这一段即可开干。

## 触发场景

- 要一段**原创、可商用、零版权**的背景音乐（BGM）
- 素材库里翻不到合适的 BGM，希望能**按需生成**
- 给视频**自动配乐**（读取视频时长，生成贴合长度的曲目）
- 批量为图文/短视频产线**囤一整套情绪 BGM 库**
- 嫌弃合成音色"太电子"，想要**真实乐器质感**
- 明确排斥第三方在线音乐服务（Suno/Beatra 等）的付费与版权风险

## 核心优势

| 维度 | 说明 |
|---|---|
| **真乐器音色** | 物理建模合成（模态/弦模型/FM），非静态正弦叠加，有真实谐波衰减 |
| **零版权风险** | 100% 数学合成，不含任何采样素材；L2 用 MIT 许可模型，输出权利归你 |
| **三层兜底** | 任何一层失败自动降级，最终保底 L1，**永不失败** |
| **零依赖起步** | L1 只需 numpy，纯 CPU，3 秒出 30 秒 BGM |
| **本地离线** | 全程不联网（L2 首次需下权重），不耗任何 API 积分 |
| **响度一致** | 内置 RMS 校准，9 种情绪响度统一，切歌不炸耳 |
| **视频友好** | `--match-video` 自动读时长；输出带淡入淡出，绝无咔嗒声 |

## 三层引擎

### L1 · procedural（默认 / 兜底）

纯 Python + numpy 程序化作曲 + **物理建模音色**，代码见 `scripts/procedural_bgm.py` + `scripts/instrument_voices.py`。

**作曲层**：和弦进行 → 三/七和弦堆叠 → 琶音主旋律 + 低音线 → 多抽头延迟混响 → 软削波 → 响度校准。

**音色层（物理建模）**——这是"听起来像真乐器"的关键：

| 方法 | 原理 | 代表音色 |
|---|---|---|
| **模态合成** | 乐器 = 一组共振模态，每个模态独立衰减；频率比决定材质（整数比=弦，非整数比=木/金属） | 钢琴、古筝、木琴、钟、弦乐、竖琴、管风琴 |
| **Karplus-Strong** | 噪声激励 + 延迟线反馈 + 低通滤波，物理仿真拨弦 | 拨弦、吉他 |
| **FM 合成** | 载波+调制器，调制指数随时间衰减（DX7 原理） | 电钢、钟琴 |

**真实性关键**：高次谐波衰减速度**必须大于**低次（真实乐器铁律）。实测新引擎谐波保留率 0.4~1.1，旧静态叠加仅 0.02。

**演奏级细节**：和弦滚奏（8~22ms 逐音延迟）、微时序偏移（±11ms）、力度弧线（小节内呼吸）、音高微漂移。

### L2 · ACE-Step 1.5（高质量 / 已部署就绪 ✅）

调用本地部署的 [ACE-Step 1.5](https://github.com/ace-step/ACE-Step-1.5) 开源音乐大模型。

- **MIT 许可**，商用无限制，输出权利归你
- **<4GB 显存**即可运行（纯 DiT 模式；GTX 1660 6GB 实测属官方 Tier 2）
- 商用级质量（官方称介于 Suno v4.5 ~ v5 之间）
- 支持 10 秒 ~ 10 分钟、1000+ 乐器风格、纯器乐输出
- **官方 Windows 便携包**：`ACE-Step-1.5.7z`（2.24GB，内含 Python + 全部依赖，推荐）

**本机部署状态（2026-10-09 已跑通）**：

| 项目 | 值 |
|---|---|
| 部署方式 | 官方便携包（推荐） |
| 安装目录 | `<ACE_STEP_DIR>`（由环境变量 `ACESTEP_DIR` 指定，默认 `<技能目录>/acestep`） |
| 环境 | `python_embeded` / Python 3.11.9 |
| torch | 2.7.1+cu128（CUDA 12.8，GPU 实测可用） |
| 模型 | `acestep-v15-turbo`（2B / 8 步 / DiT-only） |
| 权重 | 4.89GB，位于 `ACESTEP_DIR` 指定的权重子目录（如 `acestep-v15-turbo`） |

安装步骤见 `references/INSTALL_ACESTEP.md`。

> ⚠ 早期文档提到 Windows 便携包但未落地。**2026-10-09 已实际走通**：
> uv/pip 手工装 4 次失败 → 改用官方便携包一次成功。

### L3 · api（可选）

预留外部音乐 API 接口，有 Key 时可接入。

## 快速开始

### 1. 立刻出片（零配置）

```bash
# 用本机 python（venv 或系统 python 均可），脚本路径相对技能目录
PY=python
S=scripts

# 60 秒国风 BGM（默认古筝音色）
"$PY" "$S/bgm_forge.py" --mood guofeng --duration 60 --out bgm.wav

# 指定乐器（钢琴/古筝/木琴/钟/弦乐/竖琴/管风琴/电钢…）
"$PY" "$S/bgm_forge.py" --mood guofeng --instrument grand_piano --duration 60 --out bgm.mp3 --mp3

# 换 seed = 换一首曲子（同情绪不同旋律走向）
"$PY" "$S/bgm_forge.py" --mood guofeng --seed 7 --duration 60 --out bgm_s7.wav
"$PY" "$S/bgm_forge.py" --mood guofeng --seed 8 --duration 60 --out bgm_s8.wav

# 看看有哪些乐器 / 情绪
"$PY" "$S/bgm_forge.py" --list-instruments
"$PY" "$S/procedural_bgm.py" --list

# 跟着视频时长自动配乐（BGM = 视频时长 + 2s）
"$PY" "$S/bgm_forge.py" --mood healing --match-video myvideo.mp4 --out bgm.wav

# 批量囤一整套情绪库（9 条 mp3）
"$PY" "$S/bgm_forge.py" --mood all --duration 45 --outdir ./bgm_library --mp3
```

### 2. 启用 ACE-Step 高质量引擎

```bash
"$PY" "$S/acestep_bridge.py" --check          # 检查安装状态
"$PY" "$S/bgm_forge.py" --mood epic --duration 90 --engine acestep

# ⭐ 自由创作：任意英文描述，不受 9 种预设约束
"$PY" "$S/acestep_bridge.py" \
  --prompt "lo-fi hip hop beat, vinyl crackle, mellow jazz piano, rainy night cafe" \
  --duration 30 --out lofi.mp3 --mode direct

# 在预设基础上追加描述（--extra 追加到 prompt 末尾）
"$PY" "$S/acestep_bridge.py" --mood guofeng \
  --extra "with distant temple bells, misty mountain atmosphere" \
  --duration 45 --out guofeng_fog.mp3 --mode direct
```

> 实测：`lo-fi 咖啡馆` 与 `阿拉伯沙漠` 两条自由 prompt，频谱重心 993Hz vs 4057Hz，
> 相关性 0.03 —— 完全是两首不同风格的曲子，说明 L2 不依赖任何预设。

### 3. 对接 typography-video-pipeline

```bash
"$PY" "$S/bgm_forge.py" --mood guofeng --duration 60 --out bgm.wav --json-snippet
```

输出的 JSON 片段直接贴进你的视频脚本 JSON：

```json
{ "bgm": "D:\\...\\bgm.wav", "bgm_volume": 0.3 }
```

## 12 种乐器音色

| 音色名 | 方法 | 说明 |
|---|---|---|
| `grand_piano` | 模态 | 钢琴（大三角），音板共鸣+三弦微失谐 |
| `guzheng` | 模态 | 古筝 / 琵琶，弹拨物理弦 |
| `marimba` | 模态 | 木琴 / 马林巴，非谐波木块模态 |
| `bell` | 模态 | 钟 / 碰铃，强非谐波+超长衰减 |
| `strings` | 模态 | 弦乐群奏，多演奏者失谐厚度 |
| `harp` | 模态 | 竖琴 / 琉特 |
| `ambient_pad` | 模态 | 空灵铺底，极慢衰减 |
| `organ` | 模态 | 管风琴 / 簧风琴，持续无衰减 |
| `pluck_ks` | KS | 物理弦（Karplus-Strong） |
| `guitar_ks` | KS | 吉他式拨弦 |
| `epiano` | FM | FM 电钢 |
| `glocken` | FM | FM 钟琴 |

## 9 种情绪预设

| mood | 中文 | 默认乐器 | BPM | 适用场景 |
|---|---|---|---|---|
| `guofeng` | 国风 / 古韵 | 古筝 | 68 | 国学、诗词、水墨 |
| `healing` | 治愈 / 温暖 | 竖琴 | 76 | 日常感悟、亲子、正能量 |
| `sad` | 伤感 / 怀旧 | 钢琴 | 62 | 离别、乡愁、人生感慨 |
| `light` | 轻快 / 活泼 | 木琴 | 104 | 萌宠、生活、搞笑 |
| `epic` | 恢弘 / 大气 | 弦乐群奏 | 72 | 历史、人物、品牌片 |
| `dark` | 压抑 / 悬疑 | 管风琴 | 56 | 悬疑、警示、深度思考 |
| `warm` | 午后 / 悠闲 | 古筝 | 84 | vlog、慢生活 |
| `tense` | 紧张 / 推进 | FM 电钢 | 112 | 盘点、悬念、信息密集 |
| `meditation` | 冥想 / 助眠 | 竖琴 | 48 | 冥想、助眠、放松 |

## 能变出多少首不同曲目？

**结论：可以随意创建，且数量在百万量级以上，每首都不同。**

### 变化维度（全部是命令行参数，不用改代码）

| 维度 | 取值范围 | 作用 |
|---|---|---|
| `--mood` | 9 种情绪 | 换调式/音阶/和弦库/BPM/音色倾向 |
| `--seed` | 任意整数 | 换和弦拼接顺序 + 旋律节奏 + 音高跳进 |
| `--instrument` | 12 种音色 | 换乐器物理模型（音色/衰减/泛音结构） |
| `--bpm` | 任意整数 | 速度 |
| `--duration` | 任意秒数 | 时长 |
| `--reverb` | 0~1 连续 | 空间感 |
| `--loop` | 开/关 | 无缝循环版 |
| `--prompt`（L2） | 任意英文描述 | **完全自由创作，不受预设约束** |

### 组合数量

- **离散**：9 情绪 × 23 组内置和弦走向 × 12 音色 = **2484 种**
- **叠加连续维度**（seed / bpm / duration / reverb / loop）→ **百万量级**
- **L2 自由 prompt** → 无上限（自然语言描述即可）

### 实测证据（2026-10-09）

| 检验项 | 结果 |
|---|---|
| 同 mood 换 seed（11/22/33/44） | 两两 \|corr\| 平均 **0.1150** → 是不同曲子，非重渲染 ✔ |
| 同 seed 跑两次 | \|corr\| = **1.000000** → 完全可复现 ✔ |
| 12 条跨情绪/跨音色组合 md5 | **12/12 全部唯一**，零撞车 ✔ |
| 9 情绪频谱重心跨度 | 1077 ~ 2722 Hz（跨 **1645Hz**）✔ |
| L2 自由 prompt 两条对比 | 993Hz vs 4057Hz，\|corr\| = **0.0300** ✔ |

### 各引擎的"自由"边界（重要）

| 引擎 | 多样性的本质 | 适用 |
|---|---|---|
| **L1 procedural** | **情绪配方 + 随机变奏**。调式/音阶/和弦库受 9 个预设约束，seed 在同情绪内变奏 | 批量稳定出库、快速草稿、要可复现 |
| **L2 ACE-Step** | **真正的按描述创作**。`--prompt` 任意英文，不依赖任何预设 | 要特定风格（lo-fi/阿拉伯/爵士…）、正式成片 |

> L1 不是作曲 AI，是"参数化配方引擎"——胜在秒级、零依赖、完全确定性；
> 要"想要什么就给什么"，用 L2 的 `--prompt`。

## 常用参数

| 参数 | 说明 |
|---|---|
| `--mood` | 情绪预设名，`all` = 批量出 9 条 |
| `--instrument` | **覆盖乐器音色**，可传 12 个原生名（`guzheng`/`grand_piano`…）或情绪别名（`pluck`/`soft_piano`…）；用 `--list-instruments` 查看 |
| `--list-instruments` | 列出所有可用乐器音色 |
| `--preset` | **L2 专用**：用预设库里的场景配方（`guoxue_ink`/`emotion_healing`…），只在 `--engine acestep` 时生效 |
| `--list-presets` | 列出 L2 prompt 预设库（14 条） |
| `--duration` | 时长（秒） |
| `--match-video` | 读视频时长自动定长（优先级高于 `--duration`） |
| `--pad` | BGM 超出视频的秒数，默认 2.0 |
| `--engine` | `auto`(默认) / `procedural` / `acestep` / `api` |
| `--bpm` / `--seed` / `--reverb` | 覆盖预设值 |
| `--loop` | 生成可无缝循环版本 |
| `--mp3` / `--bitrate` | mp3 输出与码率（默认 192k） |
| `--volume` / `--fade-in` / `--fade-out` | 后处理音量与淡入淡出 |
| `--no-post` | 跳过 ffmpeg 后处理 |
| `--out` / `--outdir` | 输出文件 / 批量目录 |
| `--json-snippet` | 打印可贴进视频脚本的 JSON |

## 引擎自动路由规则

```
用户指定 engine？
├─ 是 → 用指定引擎（acestep 未就绪则降级 procedural）
└─ 否 → ACE-Step 已就绪 且 duration > 90s ？
        ├─ 是 → acestep（长曲质量收益大）
        └─ 否 → procedural（短曲秒出，够用且零依赖）
```

## 输出规格

- 采样率 44100 Hz，16-bit PCM
- 默认立体声（右声道微延迟产生宽度感）
- 目标响度 RMS ≈ 0.16（-16 dBFS 量级），峰值 ≤ 0.95 不破音
- 谐波保留率 0.4~1.1（旧静态叠加仅 0.02 —— 这是"真实感"的来源）

## 验证证据（2026-10-09 实测）

### L2 · ACE-Step 1.5（已跑通）

| 项目 | 结果 |
|---|---|
| 部署验证（7 层） | ✅ **ALL PASSED**（目录/解释器/依赖/CUDA/权重/导入） |
| 环境 | Python 3.11.9 + torch 2.7.1+cu128 + CUDA 12.8 + flash-attn |
| GPU 实推理 | ✅ 显存峰值 2213MB / 利用率 86%（GTX1660 6GB） |
| 单条 10s 出片 | ✅ **4 分 30 秒**（含首次 4.8GB 权重加载） |
| 单条 15s 出片 | ✅ 约 80 秒（权重重载后） |
| 产物规格 | mp3 / 48000Hz / 立体声 / 时长精确（10.000000s、15.000000s） |
| 响度 / 峰值 | -16.4 ~ -20.9 dB / 峰值 -0.9 ~ -1.0 dB（无削波） |
| 多情绪验证 | ✅ guofeng / healing / epic 三条全部成功 |

### L1 · 物理建模版（默认引擎）

| 项目 | 结果 |
|---|---|
| 单条 30s 生成耗时 | **3.4 秒**（纯 CPU） |
| 批量 9 条 45s mp3 | **47 秒**，9/9 成功 |
| 高频能量占比 | 4~39%（旧版仅 2~5%） |
| 谐波衰减（高次快于低次） | 单音实测 0.4~1.1 保留率，符合物理规律 |
| 峰值 / 爆音 | 全部 <0.66 · **0 爆音** |
| 响度一致性 | 9 条 RMS -16.6 ~ -19.5 dBFS |

#### 低频嗡声修复（2026-10-09）

**问题**：用户反馈 L1 有明显"嗡声"。实测 20~120Hz 能量 **-19.8dB**，比 L2（-39.3dB）高 19.5dB。

**四个根因与修法**：

| # | 根因 | 修法 |
|---|---|---|
| ① | 贝斯 `octave_shift=-2`，国风 C 根音落到 **65Hz** 嗡声区 | 改 `-1` 八度 → 131Hz |
| ② | 贝斯用 `pad` 慢起音长音 + 音量 0.42，低频堆积 | 改 `soft_piano`（有衰减）+ 音量 0.30 |
| ③ | `soft_clip` drive=1.15，tanh 非线性压平低频产生互调失真 | drive 降至 **1.02** |
| ④ | **`to_stereo` 全频段统一延迟 52 样本（1.18ms）**，低频左右相位差造成空洞嗡声 | 新增一阶分频：**低频归中不延迟，只延迟高频** |
| + | 缺少低切 | 新增 `low_cut(cutoff=90Hz)`，置于削波**之前** |

**修复效果**（8 种情绪全测，平均降 14dB）：

| 情绪 | 修复前 | 修复后 | 降幅 |
|---|---|---|---|
| guofeng | -19.9 | **-37.1** | 17.2 dB |
| warm | -18.6 | **-34.6** | 16.0 dB |
| healing | -20.0 | **-35.5** | 15.5 dB |
| light | -19.6 | **-35.0** | 15.4 dB |
| epic | -19.0 | **-32.3** | 13.3 dB |
| meditation | -23.3 | **-35.9** | 12.6 dB |
| sad | -19.5 | **-31.5** | 12.0 dB |
| tense | -23.7 | **-34.1** | 10.4 dB |

**副作用检查**：高频 2k-8k 反而**提亮 4.5dB**（低频不再掩盖细节）——典型的"低切后变通透"。
响度一致性、峰值保护均未受影响。

**关键教训**：低频不做声道间延迟是专业混音常识。固定样本延迟对高频是宽度感，
对低频（周期远大于延迟量）会造成相位抵消，听感即"空洞嗡声"。正确做法是低频归中、只给高频做宽度。

### 三引擎对比

| 维度 | L1 物理建模 | L2 ACE-Step |
|---|---|---|
| 速度 | 3.4 秒 / 30s | ~80 秒 / 15s |
| 依赖 | 仅 numpy | 2.24GB 便携包 + 4.89GB 权重 |
| 显存 | 不需要（纯 CPU） | ~2.2GB（推理时） |
| 音色 | 器乐质感，仍是合成音 | **商用级**，接近真实录音 |
| 适用 | 短曲、批量、快速迭代 | 长曲、精品、正式成片 |

### 旧版对比（静态正弦叠加）

| 项目 | 旧版 | 新版 |
|---|---|---|
| 合成方法 | 固定泛音 + 单一包络 | 模态/KS/FM 物理建模 |
| 谐波保留率 | 0.02（高频瞬间消失） | 0.4~1.1 |
| 听感 | 电子琴/玩具琴 | 乐器质感 |

## 文件结构

```
original-bgm-forge/
├── SKILL.md                        # 本文档
├── scripts/
│   ├── instrument_voices.py        # ★物理建模音色引擎（模态/KS/FM）
│   ├── procedural_bgm.py           # L1 作曲引擎（和弦/琶音/混响/响度）
│   ├── acestep_bridge.py           # L2 ACE-Step 桥接器（含预设库读取）
│   └── bgm_forge.py                # 统一调度器（智能路由 + 后处理）★入口
├── assets/
│   └── l2_prompts.json             # L2 prompt 预设库（14 条场景化配方）
└── references/
    ├── INSTALL_ACESTEP.md          # ACE-Step 一次性部署指南（含 ModelScope 下载）
    ├── TECHNICAL_ANALYSIS.md       # 逆向分析：闭源方案拆解与本方案技术选型
    ├── VOICE_ENGINE.md             # 物理建模音色引擎技术说明
    └── SECURITY_AUDIT.md           # 安全审计报告
```

## L2 prompt 预设库（14 条场景化配方）

`assets/l2_prompts.json` 把常用风格沉淀为可复用条目，
不用自己攒英文 prompt，直接 `--preset <id>` 调用。

| 分类 | 预设 id | 场景 |
|---|---|---|
| **国学** | `guoxue_ink` | 水墨古韵 · 古琴/竹笛/水墨画面 |
| | `guoxue_temple` | 禅寺晨钟 · 修行感悟 / 道家佛家 |
| | `guoxue_epic_history` | 史书大气 · 历史人物 / 家国情怀 |
| **情感** | `emotion_healing` | 温柔治愈 · 女性成长 / 自我和解 |
| | `emotion_release` | 释怀离别 · 告别 / 放下 |
| | `emotion_empower` | 觉醒力量 · 逆袭 / 女性力量 |
| **银发** | `silver_nostalgia` | 岁月怀旧 · 亲情 / 旧时光 |
| | `silver_morning` | 晨间清朗 · 晨练 / 慢生活 |
| **通用** | `daily_vlog` | 慢生活 vlog · 咖啡馆 / 书房 |
| | `tension_open` | 开场悬念 · 前 3 秒抓人 |
| | `dark_mystery` | 暗色压抑 · 警示 / 深度思考 |
| | `ending_elevate` | 尾声升华 · 金句收束 |
| | `broll_nature` | 山水空镜 · 四季 / 云海 |
| | `arabic_exotic` | 大漠丝路 · 异域文化 |

```bash
# 查看全部预设（含完整 prompt 文本）
"$PY" "$S/bgm_forge.py" --list-presets

# 直接用一个预设出片
"$PY" "$S/bgm_forge.py" --engine acestep --preset guoxue_ink --duration 30 \
  --out guoxue.mp3 --mp3

# 在预设基础上追加描述
"$PY" "$S/acestep_bridge.py" --preset guoxue_ink \
  --extra "with distant temple bells, misty mountain" \
  --duration 30 --out v2.mp3 --mode direct
```

**优先级**：显式 `--prompt` > `--preset` > `--mood`。

## 已知约束

- L1 是**器乐合成**，不出人声（BGM 场景本就不需要）
- L1 音色已达"乐器质感"，但仍是**合成音**，与真实录音有差距；**要录音级真实度请上 L2**
- L2 **本机已部署完成**（便携包 + 4.89GB 权重），无需再下载；迁移机器时需重走 `INSTALL_ACESTEP.md`
- L2 首次调用要加载 4.8GB 权重（约 4~5 分钟），**同一进程内连续生成则快得多**（约 80 秒/条）
- L2 权重已裁剪为仅 DiT + VAE（省 4.5GB），纯 DiT 模式**不加载 LM**，故无"智能规划"能力——
  对我们"已用情绪 preset 写好 prompt"的场景无影响
- `--mp3` 与 `--match-video` 需系统有 ffmpeg（本机已装：`C:/ffmpeg/bin/ffmpeg`）
- 物理建模计算量约为旧版的 1.7 倍（30s：2.2s → 3.4s），换来真实音色
- **不传 `--seed` 时**，seed 由 `sha256(mood|duration|bpm)` 确定性派生 →
  同参数**永远同一首**（2026-10-09 修复；此前用内置 `hash()` 受
  PYTHONHASHSEED 随机盐影响，同命令两次结果不同、无法复现）。
  想要新曲子请显式换 `--seed`
- 1 条 BGM 的多样性只受 `--mood` 的调式/音阶/和弦库约束（L1 是配方引擎）；
  要突破这个约束请用 L2 的 `--prompt`


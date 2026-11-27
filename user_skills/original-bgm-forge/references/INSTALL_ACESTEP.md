# ACE-Step 1.5 本地部署指南（Windows / GTX1660 6GB）

> 本文是 `original-bgm-forge` 技能 L2 引擎的一次性部署说明。
> 目标：让本机具备"商用级"原创 BGM 生成能力，全程本地、零版权、零 API 费用。
>
> **本机部署状态（2026-10-09 实测完成）**
>
> | 项目 | 实际值 |
> |---|---|
> | 部署方式 | **官方便携包**（推荐，一次到位） |
> | 安装目录 | `<ACE_STEP_DIR>/portable/extracted` |
> | 权重目录 | `<ACE_STEP_DIR>/checkpoints`（用 Junction 联接到安装目录下） |
> | 环境 | `python_embeded`（Python 3.11.9 + 依赖预装，含 flash-attn） |
> | torch | **2.7.1+cu128**（CUDA 12.8，与本机驱动匹配） |
> | 模型 | `acestep-v15-turbo`（2B / 8 步 / 官方质量 Very High） |
> | 权重体积 | **4.89 GB**（仅 DiT + VAE，LM 部分已裁掉 4.5GB） |
> | 便携包体积 | 2.24 GB（下载 4 分 22 秒，8 线程分片，均值 13MB/s） |
> | 备选路径 | 源码部署 `.venv`（uv/pip），见文末「坑 A/B/C」，本机未走通 |
>
> **一句话结论**：**用官方便携包，不要手工 uv/pip 拼装。**
> 便携包 2.24GB 一次搞定全部依赖，比手工路线（torch 2.5GB + 依赖 2GB + 权重 4.9GB ≈ 9.4GB）省一大半，且零踩坑。

## 零、推荐路径：官方便携包（一次到位）

官方文档明确标注 **"Windows Portable Package (Recommended for Windows)"**。

```bash
# 1. 下载（2.24GB；源站单连接限速约 0.5MB/s，务必多线程）
#    见下方「多线程分片下载」，或用任意下载器开多线程
#    地址：https://files.acemusic.ai/acemusic/win/ACE-Step-1.5.7z

# 2. 解压（约 2 分 40 秒，解压后 7.9GB / 52057 文件）
7z x ACE-Step-1.5.7z -oextracted -y

# 3. 权重就位（若已单独下载过，用 Junction 免复制）
#    PowerShell:
#    New-Item -ItemType Junction `
#      -Path "D:\...\extracted\checkpoints" `
#      -Target "D:\WORKBuddy\ace-step\checkpoints"

# 4. 验证（应输出 ALL PASSED）
python tools/verify_acestep.py --dir <extracted> --ckpt <extracted>/checkpoints
```

**便携包内含**：`python_embeded/`（Python 3.11.9 + 全依赖）、`acestep/`（源码）、`cli.py`、
`pyproject.toml`、`PortableGit/`、`examples/`、`docs/`、启动脚本。
**不含**：`checkpoints/` 权重 —— 需单独下载（ModelScope，或复用已下载的）。

**启动服务**（可选，供 api 模式用）：

```bash
# 直接调解释器，绕开 start_api_server.bat 的交互式更新确认
python_embeded\python.exe acestep\api_server.py --host 127.0.0.1 --port 8001
```

> ⚠ 目录名拼写坑：便携包实际是 **`python_embeded`**（少一个 d），
> 但官方 `start_api_server.bat` 里判断的是 `python_embedded`（多一个 d）。
> `acestep_bridge.py` 的 `find_python()` 两种拼写都会尝试，不受影响。

### 多线程分片下载（破解源站限速）

`files.acemusic.ai` **单连接限速约 0.5MB/s**，单线程下 2.24GB 需 75 分钟以上。
该源**支持 HTTP Range（206）**，用多线程分片可把速度提到 **13~32MB/s（快 20~30 倍）**。

本机已有工具：`D:/WorkBuddyData/2026-10-09-12-38-06/tools/parallel_download.py`

```bash
python parallel_download.py <url> <out_path> --threads 8 --chunk-mb 32
```

- 断点续传：已存在的 `.parts/` 分片自动跳过（本次复用 512MB）
- 单文件已下部分：用 `_split_parts.py` 切成分片格式即可接续
- 实测：2.24GB / 4 分 22 秒完成，字节数精确匹配 2403883448


## 一、为什么选 ACE-Step

在多渠道比对了所有开源音乐生成方案后，ACE-Step 1.5 是**唯一同时满足**以下全部条件的选择：

| 模型 | 许可 | 显存 | 商用 | 纯器乐 | 评价 |
|---|---|---|---|---|---|
| **ACE-Step 1.5** | **MIT** | **<4GB** | **✅** | ✅ | **★ 首选** |
| YuE | Apache 2.0 | 16~24GB | ✅ | ❌ 必须人声 | 本机显存不够 |
| MusicGen | CC-BY-NC | 8~16GB | **❌** | ✅ | **许可陷阱，不能用** |
| Stable Audio Open | 社区许可 | ~12GB | 有营收门槛 | ✅ | 显存吃紧、只 47s |
| MiniMax-Music3 | 自定义 | 待定 | 有营收门槛 | ❌ | 工具链未成熟 |
| DiffRhythm | 开源 | 16GB | ✅ | ✅ | 显存吃紧 |
| Suno / Udio / Beatra | 闭源 | 云端 | 按条款 | ❌ | 需付费、版权存疑 |

**关键结论**：MusicGen 是著名陷阱——下载完全免费，但权重是 CC-BY-NC，**输出不能商用**。做自媒体变现绝不能用。

## 二、本机环境核对

| 项目 | 实际值 | 是否满足 |
|---|---|---|
| GPU | GTX 1660 6GB | ✅ 官方「≤6GB」档支持 |
| 计算能力 | 7.5（Turing） | ✅ ≥7.0，fp16 可用（bf16 不支持） |
| 驱动 | 616.64 | ✅ |
| Python | 系统 3.13（不符） | ⚠ 需 3.11~3.12，uv 自动拉 3.12.13 |
| uv | `uv` v0.12.3 | ✅ |
| git | 2.55.0.windows.3 | ✅ |
| 可用磁盘 | D 盘 701G | ✅ |
| **E 盘** | **不存在** | ⚠ 早期文档写 E 盘，实际部署在 D 盘 |

## 三、官方显存分档（本机 = ≤6GB 档）

官方 README 的显存-模型对照表：

| VRAM | 推荐 DiT | 推荐 LM | 后端 | 说明 |
|---|---|---|---|---|
| **≤6GB** | **2B turbo** | **None（DiT only）** | — | **LM 默认禁用；INT8 量化 + 全 CPU offload** |
| 6-8GB | 2B turbo | `acestep-5Hz-lm-0.6B` | `pt` | 轻量 LM |
| 8-16GB | 2B turbo/sft | 0.6B / 1.7B | `vllm` | — |
| ≥12GB | XL (4B) turbo | 1.7B | `vllm` | 本机跑不动 |

官方文档原文（`docs/en/INSTALL.md`）：
> `| VRAM | ≥4GB for DiT-only mode; ≥6GB for LLM+DiT |`

**关键结论**：**纯 DiT 模式只要 ≥4GB**，GTX1660 6GB 完全够。牺牲的是 LM 的"智能规划"能力（自动生成 caption/歌词/元数据），但对我们"**已经用情绪 preset 写好 prompt**"的场景毫无影响。

## 四、安装步骤（实测流程 + 踩坑修正）

### 步骤 1：克隆仓库（走 gh-proxy 加速）

```bash
mkdir -p /d/WORKBuddy/ace-step
cd /d/WORKBuddy/ace-step
env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy \
  git clone --depth 1 https://gh-proxy.com/https://github.com/ACE-Step/ACE-Step-1.5.git
```

> ⚠ ghfast.top / ghproxy.net 实测 403，**只用 gh-proxy.com**。
> 实测：1222 文件 / 5 秒完成。

### 步骤 2：配置 `.env`（关键！决定行为）

复制 `.env.example` 为 `.env`，改这几项：

```ini
ACESTEP_CONFIG_PATH=acestep-v15-turbo   # 6GB 档唯一选择
ACESTEP_LM_MODEL_PATH=                  # 留空 = 不加载 LM
ACESTEP_LM_BACKEND=pt
ACESTEP_INIT_LLM=false                  # 强制纯 DiT（6GB 必须）
ACESTEP_DOWNLOAD_SOURCE=modelscope      # ⭐ 本机 HF 不可达，必须显式指定
ACESTEP_CHECKPOINTS_DIR=<ACE_STEP_DIR>/checkpoints
PORT=7860
```

> ⭐ **`ACESTEP_DOWNLOAD_SOURCE=modelscope` 是最重要的一项**。
> 代码里 `can_access_google()` 会探测 Google 连通性来自动选源——**本机 Google 可达**，
> 所以 `auto` 会选 HuggingFace，然后全部 502 失败。必须显式写死 modelscope。

### 步骤 3：建环境（uv sync）—— ⚠ 有坑

**直接 `uv sync` 会卡死**。原因有两个，都要修：

#### 坑 A：WorkBuddy 注入的代理不转发外部流量

```bash
# ❌ 直接跑会全部超时（HTTP_PROXY 指向 127.0.0.1:14667，不转发外部）
uv sync

# ✅ 必须摘掉代理
env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy \
  UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple \
  uv sync --python 3.12
```

#### 坑 B：flash-attn 从 GitHub 下载会超时（★ 实测卡 14 分钟）

`nano-vllm`（`acestep/third_parts/nano-vllm`，**只服务 LM 推理**）声明了 flash-attn 的
**GitHub Releases 直链依赖**：

```
flash-attn @ https://github.com/sdbds/flash-attention-for-windows/releases/download/...
```

本机 GitHub 直连不通 → uv 会一直重试直到超时。**两个修法（实测都有效，建议一起用）**：

**修法 1：给 URL 加 gh-proxy 前缀**

改 `acestep/third_parts/nano-vllm/pyproject.toml`：

```diff
- "flash-attn @ https://github.com/sdbds/flash-attention-for-windows/releases/..."
+ "flash-attn @ https://gh-proxy.com/https://github.com/sdbds/flash-attention-for-windows/releases/..."
```

**修法 2：收窄 `required-environments`（省一半下载量）**

原 `pyproject.toml` 声明了 4 个平台，导致 uv 为**用不上的 linux/darwin** 也下载轮子：

```diff
 [tool.uv]
 required-environments = [
     "sys_platform == 'win32' and platform_machine == 'AMD64'",
-    "sys_platform == 'linux' and platform_machine == 'x86_64'",
-    "sys_platform == 'linux' and platform_machine == 'aarch64'",
-    "sys_platform == 'darwin' and platform_machine == 'arm64'",
 ]
```

> 💡 **附加说明**：flash-attn 的 marker 要求 `python_version == '3.11'`。
> 用 `--python 3.12` 理论上可跳过它，但 `required-environments` 的跨平台声明会让 uv
> 仍然为 3.11 环境解析依赖。所以**收窄平台比换 Python 版本更有效**。
>
> 💡 **flash-attn 是可选优化，不是硬依赖**。证据：`acestep/llm_inference.py:658` 明确写了
> *"flash_attn not installed: disabling CUDA graph capture for nano-vllm"*（有降级路径）。
> 且我们的纯 DiT 模式下，它两处用点（nano-vllm 的 LM 加速 + DiT 的 `flash_attention_2`
> 可选实现）都用不上。**装不上不影响出片**。

### 步骤 4：下载模型权重（走 ModelScope）—— ⭐ 只下需要的

**权重清单（实测 ModelScope API 返回，全量 9.40 GB）**：

| 组件 | 大小 | 纯 DiT 模式需要？ |
|---|---|---|
| `acestep-v15-turbo/model.safetensors` | **4.57 GB** | ✅ 核心 |
| `vae/diffusion_pytorch_model.safetensors` | **0.32 GB** | ✅ 必需 |
| `acestep-v15-turbo/{config.json, configuration_*.py, modeling_*.py, silence_latent.pt}` | ~3.8 MB | ✅ 必需 |
| `vae/config.json` | 425 B | ✅ 必需 |
| `acestep-5Hz-lm-1.7B/*` | 3.54 GB | ❌ LM 已关，跳过 |
| `Qwen3-Embedding-0.6B/*` | 1.14 GB | ❌ LM 附属，跳过 |

**只需下 4.89 GB，省掉 4.5 GB。** 逐个文件下载：

```bash
CKPT="<ACE_STEP_DIR>/checkpoints"
mkdir -p "$CKPT/acestep-v15-turbo" "$CKPT/vae"
BASE="https://www.modelscope.cn/api/v1/models/ACE-Step/Ace-Step1.5/repo?Revision=master&FilePath="

# 大文件（支持断点续传 -C -）
env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy \
  curl -L -C - -o "$CKPT/acestep-v15-turbo/model.safetensors" \
  "${BASE}acestep-v15-turbo/model.safetensors"

env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy \
  curl -L -C - -o "$CKPT/vae/diffusion_pytorch_model.safetensors" \
  "${BASE}vae/diffusion_pytorch_model.safetensors"

# 小文件（配置 + 建模代码 + silence_latent）
for f in "acestep-v15-turbo/config.json" \
         "acestep-v15-turbo/configuration_acestep_v15.py" \
         "acestep-v15-turbo/modeling_acestep_v15_turbo.py" \
         "acestep-v15-turbo/silence_latent.pt" \
         "vae/config.json"; do
  env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy \
    curl -sL -o "$CKPT/$f" "${BASE}${f}"
done
```

**校验方法**（字节数必须精确匹配）：

```bash
ls -l "$CKPT/acestep-v15-turbo/model.safetensors"   # 应为 4787825604
ls -l "$CKPT/vae/diffusion_pytorch_model.safetensors"  # 应为 337431388
# safetensors 文件头应为 {"__meta...
head -c 16 "$CKPT/acestep-v15-turbo/model.safetensors"
```

> 💡 备用源：`uv run modelscope download --model ACE-Step/Ace-Step1.5 --local_dir ./checkpoints`
> 会拉全量 9.4GB，不推荐（LM 部分用不上）。
>
> 💡 列 ModelScope 文件清单的 API：
> ```bash
> curl -s "https://www.modelscope.cn/api/v1/models/ACE-Step/Ace-Step1.5/repo/files?Revision=master&Recursive=true"
> ```

### 步骤 5：接进本技能

```bash
PY=python
S=<技能目录>/scripts

# 检查安装（会探测 venv / acestep / torch / CUDA / 权重）
"$PY" "$S/acestep_bridge.py" --check

# 看可用模型（含显存档位推荐）
"$PY" "$S/acestep_bridge.py" --list-models

# 出 60 秒国风 BGM（走 CLI 模式）
"$PY" "$S/acestep_bridge.py" --mood guofeng --duration 60 --out out.mp3

# 或经统一调度器（engine=acestep 强制走 L2）
"$PY" "$S/bgm_forge.py" --mood epic --duration 90 --engine acestep
```

固化安装位置（可选）：

```bash
export ACESTEP_DIR="<ACE_STEP_DIR>/ACE-Step-1.5"
```

## 五、6GB 显存专项调优

| 手段 | 做法 | 效果 |
|---|---|---|
| **用 turbo 模型** | `ACESTEP_CONFIG_PATH=acestep-v15-turbo` | 8 步推理，显存与速度最优 |
| **关闭 LM** | `ACESTEP_INIT_LLM=false` | 省下 3.5GB 权重 + 推理显存 |
| **强制 CPU offload** | `OFFLOAD_TO_CPU=true` | DiT 在 GPU、其余在内存 |
| **INT8 量化** | 低显存自动开启 | 权重显存约减半 |
| **batch=1** | 桥接器已固定 | 避免显存峰值 |
| **别用 XL 模型** | XL(4B) 需 ≥12GB | 6GB 会 OOM |

**注意 Turing 架构限制**：GTX1660 计算能力 7.5，**不支持 bf16**，会退化到 fp16。

## 六、故障排查（全部为本次实测）

| 现象 | 原因 | 解决 |
|---|---|---|
| `uv sync` 卡 10+ 分钟无输出 | **flash-attn 从 GitHub 直连超时** | 见步骤 3「坑 B」两个修法 |
| `uv sync` 全部超时 | WorkBuddy 代理不转发 | 命令前加 `env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy` |
| `uv sync` 下载量异常大 | `required-environments` 跨平台 | 收窄为仅 `win32 + AMD64` |
| 权重下载 502 | HF 不可达 | `ACESTEP_DOWNLOAD_SOURCE=modelscope` |
| 权重下载 302 但无内容 | 用了网页版 URL | 用 `api/v1/models/.../repo?FilePath=` 接口 |
| `git clone` 403 | 镜像失效 | 换 `https://gh-proxy.com/` 前缀 |
| CUDA OOM | 显存不足 | 开 offload + INT8 + turbo + batch=1 |
| 出人声 | prompt 没约束 | 确认 prompt 含 `instrumental only, no vocals`（桥接器已自动追加） |
| 推理极慢 | 未启用 turbo / 未量化 | 换 `acestep-v15-turbo`，确认量化已开 |
| bf16 报错 | Turing 不支持 bf16 | 用 fp16；本机计算能力 7.5 支持 fp16 |
| `flash_attn` import 失败 | 未安装（可接受） | 无需处理，代码有 SDPA 降级路径 |

## 七、兜底策略

**如果 ACE-Step 部署失败或太慢，直接回退 L1**：

```bash
"$PY" "$S/bgm_forge.py" --mood guofeng --duration 60 --engine procedural
```

L1 物理建模引擎**零依赖、纯 CPU、秒级出片**（30 秒 BGM 实测 3.4 秒），
12 种乐器音色、9 种情绪，**同样是 100% 原创、可商用**。
调度器的 `auto` 模式在 L2 不可用时也会自动回退 L1。

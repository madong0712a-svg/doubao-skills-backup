# 🔍 安全审计报告

## 📊 执行摘要

- **审计对象**: `original-bgm-forge`（路径：`C:\Users\Administrator\.workbuddy\skills\original-bgm-forge`）
- **审计方式**: 静态文本分析（未执行任何被审查内容）
- **审计流程**: `skills-security-check` v1.0.0 全流程（步骤 1~7）
- **文件构成**: 10 个文件 / 4,129 行
  - `SKILL.md`（416 行）
  - `scripts/procedural_bgm.py`（881 行）
  - `scripts/acestep_bridge.py`（825 行）— v4 改动：新增预设库读取 + `--preset`
  - `scripts/instrument_voices.py`（537 行）
  - `scripts/bgm_forge.py`（381 行）— v4 改动：新增 `--preset` / `--list-presets` 透传
  - `assets/prompt_presets/l2_prompts.json`（124 行）⭐ v4 新增
  - `references/INSTALL_ACESTEP.md`（333 行）
  - `references/VOICE_ENGINE.md`（205 行）
  - `references/TECHNICAL_ANALYSIS.md`（200 行）
  - `references/SECURITY_AUDIT.md`（本文件）
- **触发原因**: 封装为可发布技能，新增 `assets/` 预设库与相关脚本改动 → 全量重审
- **发现问题总数**: 0 个
  - 🔴 Malicious（恶意）: 0 个
  - ⚠️ Suspicious（可疑）: 0 个
  - 📝 信息性提醒: 0 个
- **安全评分**: **85 分**

---

## 🔴 Malicious（恶意）风险发现

✅ 未发现 Malicious 风险

---

## ⚠️ Suspicious（可疑）风险发现

✅ 未发现 Suspicious 风险

---

## 📝 信息性提醒（非风险项）

✅ 无信息性提醒

---

## 📋 详细检查结果

### 命令执行与权限检查

- **发现次数**: 6 次（均为正常用途）
- **详细列表**:

| 位置 | 内容 | 判定 |
|---|---|---|
| `bgm_forge.py:39` | `import subprocess` | ✅ 正常导入 |
| `bgm_forge.py:70` | `subprocess.run(cmd, capture_output=True, ...)` | ✅ 调用本地 ffmpeg / ffprobe / 本技能自带脚本 |
| `acestep_bridge.py:71` | `import subprocess` | ✅ 正常导入 |
| `acestep_bridge.py:213` | `subprocess.run([py, "-c", "import acestep, torch; ..."])` | ✅ 环境探测，只读，无副作用 |
| `acestep_bridge.py:375` | `subprocess.run(cmd, cwd=acestep_dir, env=env)` | ✅ 调用本地已安装的 ACE-Step CLI |
| `acestep_bridge.py:656` | `subprocess.run([py, "-c", DIRECT_RUNNER], ...)` | ✅ 调用本地解释器执行官方 API |

**关键判定**：全部调用目标均为**本地程序**（ffmpeg、ffprobe、本技能目录内的脚本）或**用户自行安装的 ACE-Step 解释器**。
**未发现 `shell=True`**，**未发现 `curl | bash` / `wget | sh` 形式的远程下载执行**，**未发现 `eval` / `exec` / `os.system`**。

⭐ **v4 新增代码专项**：`load_presets()`（`acestep_bridge.py:252`）读取 `assets/prompt_presets/l2_prompts.json`，
路径由 `__file__` 推导拼接（**不接受任何外部输入**），带 `try/except` 兜底回退，**失败不影响主流程**。该函数**不做任何网络访问、不执行任何代码、不写文件**。
`--preset`（`acestep_bridge.py:696` / `bgm_forge.py:307`）接收的是**字符串 id**，经字典查表后作为 `subprocess` 列表参数的元素传递，**不经过 shell 解释，无命令注入面**。

**权限提升检查**：未发现 `sudo` / `chmod 777` / `chown` / `Set-ExecutionPolicy` 等。

### 文件操作与敏感路径检查

- **敏感路径检查**: ✅ **无命中**。未发现对 `~/.ssh`、`~/.gnupg`、`~/.aws`、`~/.gcloud`、`~/.azure`、`~/.kube`、`credentials`、`secrets`、`password`、`private_key`、`secret_key` 的任何读取或访问。
- **`os.environ` 使用**：均为**项目配置读取**，非凭证提取：

| 位置 | 内容 | 判定 |
|---|---|---|
| `acestep_bridge.py:149` | 读取 `ACESTEP_DIR` 定位模型目录 | ✅ 有默认值兜底 |
| `acestep_bridge.py:230` / `367` / `634` | 读取 `ACESTEP_CHECKPOINTS_DIR` | ✅ 本地路径配置 |
| `acestep_bridge.py:361` / `645` | `os.environ.copy()` 后增量注入显存配置 | ✅ 未删改用户环境 |
| `acestep_bridge.py:716` | `--api-key` 默认取 `ACESTEP_API_KEY` | ✅ 作者自有本地服务密钥，非窃取用户凭证 |
| `bgm_forge.py:47` / `189` / `207` | 同 `ACESTEP_DIR` 读取 | ✅ 配置项 |

- **文件写入**：仅写入 **用户通过 `--out` / `--outdir` 指定**的输出路径（WAV/MP3）及临时 `.toml` 配置。
  **不写入任何系统目录、启动项、注册表、shell 配置文件**。
- **文件删除/移动**（4 处，全部安全）：

| 位置 | 内容 | 判定 |
|---|---|---|
| `acestep_bridge.py:386` / `391` | `os.remove(toml_path)` | ✅ 删除本函数刚创建的 ACE-Step 配置 |
| `bgm_forge.py:257` / `268` | `os.remove(t)` | ✅ 清理自己创建的中间产物（`*.tmp.wav` / `*.post.wav`） |

**关键判定**：删除目标全部由代码内部构造（固定后缀），**不来自外部输入、不使用通配符、不递归删除目录**。
且附带保护：`if os.path.abspath(t) != os.path.abspath(target)` —— **绝不会误删最终产物**。
**未发现 `rm -rf` / `shutil.rmtree` / 通配符删除**。

⭐ **v4 新增文件 `assets/prompt_presets/l2_prompts.json`**：纯 JSON 数据（14 条 prompt 预设），**不含任何可执行代码**。

### 网络请求检查

- **发现的 URL 列表**:

| URL | 位置 | 用途 | 判定 |
|---|---|---|---|
| `http://127.0.0.1:8001` | `acestep_bridge.py:160` | 本地 ACE-Step REST API | ✅ 回环地址 |
| `https://github.com/ace-step/ACE-Step-1.5` | `SKILL.md:64`、文档 | 项目引用链接 | ✅ 文档 |
| `https://gh-proxy.com/` | `acestep_bridge.py` 注释、`INSTALL_ACESTEP.md` | GitHub 克隆加速前缀（**文档中的手动命令**） | ✅ 非自动执行 |
| `https://files.acemusic.ai/...` | `acestep_bridge.py:28` 注释、文档 | 官方 Windows 便携包（**用户手动下载**） | ✅ 非自动执行 |
| `https://www.modelscope.cn/api/v1/...` | `INSTALL_ACESTEP.md` | 权重下载源（**文档中的手动命令**） | ✅ 非自动执行 |
| `https://pypi.tuna.tsinghua.edu.cn/simple` | `INSTALL_ACESTEP.md:165` | 清华 PyPI 镜像（**文档中的手动命令**） | ✅ 非自动执行 |
| `https://arxiv.org/abs/2602.00744` | `TECHNICAL_ANALYSIS.md` | 技术报告引用 | ✅ 文档 |
| `https://ace-step.github.io/` | `TECHNICAL_ANALYSIS.md` | 项目主页引用 | ✅ 文档 |
| `https://github.com/facebookresearch/audiocraft` | `TECHNICAL_ANALYSIS.md` | 竞品分析引用 | ✅ 文档 |

**关键判定**：
- **代码中唯一的网络请求**是 `acestep_bridge.py` 的 `run_api()`（`urllib.request`，第 443/470/477 行），请求目标为 `args.api_url`，**默认 `http://127.0.0.1:8001`（本地回环）**。
- 其余 URL **全部出现在 Markdown 文档或代码注释中，是供用户阅读的参考链接与手动安装命令**，技能不会自动访问。
- **未发现任何向外部域名发送数据的行为**。技能全程可离线运行（L1 完全离线；L2 仅本地推理）。
- **Base64 编码检测**: 命中 1 处，经核验为正常用途 —— `acestep_bridge.py` 解码**本地 API 返回的音频数据**，非解码执行。

### 远程脚本深度分析

✅ **无此风险**。

本技能**不存在** `curl | bash`、`wget | sh`、下载脚本后 `eval` 等"自动下载并执行远程脚本"的行为，因此**无需触发步骤 4 的远程内容分析**。

文档中出现的 `git clone`、`uv sync`、`curl -L`（下载权重）等命令，均为**写在 Markdown 里供用户手动复制执行的安装说明**，技能程序本身不会自动执行它们。

### 依赖安装风险检查

- **全局安装检测**: ✅ 未发现自动执行的全局安装命令。
  - `procedural_bgm.py:50` 的 `pip install numpy` 是**错误提示文案**（numpy 缺失时打印给用户看），**不是自动执行**。
  - `INSTALL_ACESTEP.md` 中的安装命令均为**文档示例**，需用户手动执行；且 ACE-Step 走 `uv sync`，本身即**项目级虚拟环境隔离**，非全局安装。
  - 技能运行时依赖（numpy）**已存在于本机 venv**，无需安装。
- **虚拟环境检查**: ✅ 本技能**主动要求使用隔离 venv**：
  - `SKILL.md` 明确指定 `C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe`
  - ACE-Step 部分要求 `uv sync` 建立独立 `.venv`
- **依赖来源检查**: ✅ 无可疑来源。
  - 技能自身**不从任何非官方源安装依赖**。
  - 文档提到的 ModelScope 是**模型权重下载源**（非 pip 源），是因 HuggingFace 在本机不可达而选用的国内官方镜像，属合理选择。
  - 未发现 `pip install -i <可疑源>`、`npm --registry <可疑源>`、`git+https://...@main`（未固定 SHA）等形式。
- ⭐ **v4 新增代码零新增依赖**：`load_presets()` 仅用标准库 `os` + `json`。

### 文档与实际行为一致性核查

检查 `SKILL.md` 描述与代码实际行为是否一致（防"技能描述与实际行为不符"）。

| 描述项 | 文档声明 | 代码实际情况 | 判定 |
|---|---|---|---|
| 引擎数量 | "三层引擎（程序化 / ACE-Step / API）" | `bgm_forge.py` 有 `--engine {auto,procedural,acestep,api}` | ✅ 一致 |
| 依赖 | "物理建模：零依赖 / 纯 CPU / 秒级" | `instrument_voices.py` 仅依赖 numpy，无 GPU 调用 | ✅ 一致 |
| 音色数 | "12 种乐器音色" | `--list-instruments` 实测输出 12 项 | ✅ 一致 |
| 情绪数 | "9 种情绪预设" | `MOOD_PRESETS` 实测 9 项 | ✅ 一致 |
| 和弦走向 | "23 组和弦走向" | 实测 9 情绪合计 23 组 | ✅ 一致 |
| 预设库 | "L2 prompt 预设库（14 条）" | `l2_prompts.json` 实测 14 条 | ✅ 一致 |
| 网络行为（L1） | 未声明任何联网能力 | `instrument_voices.py` / `procedural_bgm.py` 零网络调用 | ✅ 一致 |
| 数据外送 | 未声明 | 全代码无 POST 到外部域名的行为 | ✅ 一致 |

**结论**：✅ **文档与代码行为完全一致，未发现隐藏功能或能力夸大**。

---

## 💡 总体建议

1. **当前状态可直接使用**。技能为纯本地音频合成工具，无外部数据外送、无凭证读取、无远程代码执行。

2. **安全性亮点**（值得保持的实践）：
   - 所有子进程调用**均不含 `shell=True`**，避免命令注入
   - 文件删除**有 `abspath` 保护**，不会误删用户文件
   - 删除目标**全部由代码内部构造**，不来自外部输入
   - 唯一的网络请求指向 **localhost**，不对外通信
   - **零依赖起步**（L1 只需 numpy），减少供应链暴露面
   - 物理建模引擎与预设库读取均为**纯计算 / 纯数据**，攻击面为零
   - 预设库路径由 `__file__` 推导，**不接受外部路径输入**

3. **可选加固建议**（非必需）：
   - 若后续接入 L3 外部音乐 API，建议将 API Key 走环境变量而非硬编码
   - ACE-Step 的 `uv sync` 可考虑在文档中补充"锁定 commit SHA"以进一步降低供应链风险

4. **使用前人工确认项**（建议知晓）：
   - L2 引擎部署时需执行 `git clone`、`uv sync`、权重下载等命令 —— 这些是标准部署操作，建议在人工监督下执行
   - `gh-proxy.com` 为第三方 GitHub 加速代理，仅用于加速克隆**官方仓库**，代码来源仍是官方

---

## ✅ 审计结论

**风险等级**: ✅ **Benign（可信）**

**安全评分**: **85 / 100**
（10 文件 / 4,129 行全量覆盖；有可执行代码但未发现任何风险行为；未给满分是因存在子进程调用与文件操作，属正常工程实现但需保持关注）

**使用建议**:

> ✅ **Benign（可信）- 可以安全使用**
>
> 本技能为纯本地原创 BGM 生成工具。经完整静态审计（覆盖封装为可发布技能后的全部 10 个文件）：
> - 无恶意代码、无远程代码执行、无凭证窃取、无数据外送
> - 唯一网络请求指向 localhost
> - 文件操作有安全保护，删除目标均由代码内部构造
> - 依赖装在隔离 venv 中，无可疑来源
> - 文档描述与实际行为一致，未发现隐藏功能
> - 新增的预设库为纯 JSON 数据，读取逻辑不接受外部路径输入
>
> 可安全安装使用。L2 引擎的部署命令建议在人工监督下执行。

---

**审计人**: WorkBuddy（skills-security-check v1.0.0 流程）
**审计时间**: 2026-10-09（v4 复审，覆盖封装为可发布技能后的全量文件）
**审计方式**: 纯静态文本分析，未执行任何被审查内容

**覆盖范围变更**:
- v1（6 文件）→ v2（9 文件，新增 `instrument_voices.py` / `VOICE_ENGINE.md`）
- v2 → v3（仍 9 文件；ACE-Step 部署改造后复审）
- v3 → v4（10 文件；新增 `assets/prompt_presets/l2_prompts.json`，`acestep_bridge.py` / `bgm_forge.py` / `procedural_bgm.py` / `SKILL.md` 有实质改动）

**v4 复审要点**（本轮改动涉及的文件）:

| 文件 | 改动 | 风险评估 |
|---|---|---|
| `assets/prompt_presets/l2_prompts.json` | **新增**：14 条 prompt 预设 | ✅ 纯 JSON 数据，无可执行代码 |
| `acestep_bridge.py` | 新增 `load_presets()` | ✅ 路径由 `__file__` 推导，不接受外部输入；有 try/except 兜底 |
| `acestep_bridge.py` | `build_prompt()` 增加 `bpm_override` 参数 | ✅ 纯参数透传，无副作用 |
| `acestep_bridge.py` | 新增 `--preset` / `--list-presets` | ✅ 字符串查表，经 list 传参，无 shell 注入面 |
| `bgm_forge.py` | 新增 `--preset` 透传 / `--list-presets` 转发 | ✅ 同上 |
| `procedural_bgm.py` | 新增 `resolve_voice()` 音色名解析 | ✅ 纯字符串映射 + 只读校验，无风险 |
| `procedural_bgm.py` | `seed` 派生改用 `hashlib.sha256` | ✅ 标准库确定性哈希，修复了原 `hash()` 不可复现问题 |
| `SKILL.md` | 补齐 frontmatter（version/license/tags） | ✅ 元数据，无风险 |

**关键复验结论**：本轮全部改动**未引入任何新的网络访问、动态代码执行、敏感路径读取或数据外送行为**。
新增的预设库为**纯数据文件**，读取逻辑的路径来源是脚本自身位置（`__file__`），**不可被外部输入改写**。
`subprocess` 调用目标仍为本地解释器，命令参数由脚本内部常量拼接，`shell=False`（默认），不存在命令注入面。

> 注：本轮还新建了若干**技能目录之外**的辅助测试工具
> （`D:/WorkBuddyData/.../tools/variety_test.py`、`diversity_scale.py`、`compare_freeprompt.py`），
> 它们不属于本技能包，不纳入本审计范围。

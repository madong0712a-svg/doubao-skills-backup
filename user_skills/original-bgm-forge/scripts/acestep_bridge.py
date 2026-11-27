#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
acestep_bridge.py — ACE-Step 1.5 本地高质量 BGM 生成桥接器

定位
----
original-bgm-forge 技能的【第二层引擎】：调用本地部署的 ACE-Step 1.5
（MIT 许可 / 开源权重）生成商用级音乐，输出无人声的纯器乐 BGM。

为什么不直接写进主脚本
----------------------
ACE-Step 依赖重（torch cu128 + 数 GB 权重 + CUDA），不适合每次调用。
本脚本用「子进程隔离」的方式调用，只有在真正需要大模型质量时才走这条路。

本机实测部署状态（2026-10-09）
------------------------------
  安装目录 : D:/WORKBuddy/ace-step/ACE-Step-1.5
  环境     : 官方便携包 python_embedded（推荐）／ .venv（源码部署，备选）
  模型     : acestep-v15-turbo（2B / 8 步 / 官方标注质量 Very High）
  显存档位 : GTX1660 6GB → 官方「≤6GB」档 = 纯 DiT 模式 + INT8 量化 + CPU offload
  下载源   : ModelScope（本机 HuggingFace 不可达 502）
  权重位置 : D:/WORKBuddy/ace-step/checkpoints（由 .env 的 ACESTEP_CHECKPOINTS_DIR 指定）
  服务端口 : 8001（官方 start_api_server.bat 默认值）

官方 Windows 便携包
-------------------
  地址 : https://files.acemusic.ai/acemusic/win/ACE-Step-1.5.7z （约 2.24 GB）
  特点 : 内含 python_embedded + 全部依赖，解压即用，官方标注 "Recommended for Windows"
  启动 : 直接跑 python_embedded\\python.exe acestep\\api_server.py --host 127.0.0.1 --port 8001
         （绕开 start_api_server.bat 的交互式更新确认，便于自动化）

两种调用方式
------------
  ┌─ mode=cli ─────────────────────────────────────────────────────────┐
  │ 走仓库自带 cli.py + 生成的 .toml 配置文件。                         │
  │ 特点：无需常驻服务，一次调用一个进程，最省内存。                     │
  │ 代价：每次都要重新加载模型（首次较慢）。                            │
  └────────────────────────────────────────────────────────────────────┘

  ┌─ mode=api ─────────────────────────────────────────────────────────┐
  │ 走官方 REST API（POST /release_task）。                             │
  │ 特点：模型常驻显存，连续生成快。                                    │
  │ 代价：需先 `uv run acestep-api` 常驻服务。                          │
  └────────────────────────────────────────────────────────────────────┘

  ┌─ mode=direct ──────────────────────────────────────────────────────┐
  │ 直接 import acestep 的 Python API（最底层，最灵活）。               │
  │ 用仓库的 .venv 解释器执行内联脚本，无需起服务。                     │
  └────────────────────────────────────────────────────────────────────┘

用法
----
    # 情绪映射模式（推荐）：复用 procedural_bgm 的情绪名
    python acestep_bridge.py --mood guofeng --duration 60 --out bgm.wav

    # 自由 prompt 模式
    python acestep_bridge.py --prompt "guqin, bamboo flute, peaceful" \\
        --duration 60 --out bgm.wav

    # 检查安装状态
    python acestep_bridge.py --check

    # 列出可用的 ACE-Step 模型
    python acestep_bridge.py --list-models
"""

import argparse
import json
import os
import subprocess
import sys

# ---------------------------------------------------------------------------
# 情绪 -> ACE-Step 英文 prompt 映射
# 关键词策略：乐器 + 情绪 + "instrumental, no vocals" 确保纯器乐
# ---------------------------------------------------------------------------
MOOD_TO_ACESTEP = {
    "guofeng": {
        "prompt": ("traditional Chinese instrumental, guqin, bamboo flute dizi, "
                   "guzheng, erhu, pentatonic scale, ancient oriental, "
                   "serene, elegant"),
        "bpm": 68,
        "keyscale": "D minor",
        "label": "国风 / 古韵",
    },
    "healing": {
        "prompt": ("warm healing instrumental, soft piano, light strings pad, "
                   "gentle arpeggio, uplifting, hopeful, cinematic ambient"),
        "bpm": 76,
        "keyscale": "C major",
        "label": "治愈 / 温暖",
    },
    "sad": {
        "prompt": ("melancholic instrumental, slow solo piano, soft cello, "
                   "nostalgic, lonely, rainy mood, emotional, minor key"),
        "bpm": 62,
        "keyscale": "A minor",
        "label": "伤感 / 怀旧",
    },
    "light": {
        "prompt": ("upbeat happy instrumental, marimba, ukulele, "
                   "pizzicato strings, playful, cheerful, bouncy rhythm"),
        "bpm": 104,
        "keyscale": "E major",
        "label": "轻快 / 活泼",
    },
    "epic": {
        "prompt": ("epic cinematic orchestral, layered strings, french horns, "
                   "timpani, taiko drums, heroic, grand, sweeping, trailer music"),
        "bpm": 72,
        "keyscale": "G minor",
        "label": "恢弘 / 大气",
    },
    "dark": {
        "prompt": ("dark ambient instrumental, low drone, dissonant strings, "
                   "tension, suspense, mystery, unsettling atmosphere"),
        "bpm": 56,
        "keyscale": "D minor",
        "label": "压抑 / 悬疑",
    },
    "warm": {
        "prompt": ("warm acoustic instrumental, fingerstyle guitar, "
                   "light shaker, lazy afternoon, cozy, chill, mixolydian"),
        "bpm": 84,
        "keyscale": "A major",
        "label": "午后 / 悠闲",
    },
    "tense": {
        "prompt": ("tense driving instrumental, pulsing synth bass, "
                   "staccato strings, ticking percussion, urgent, "
                   "build up, documentary score"),
        "bpm": 112,
        "keyscale": "B minor",
        "label": "紧张 / 推进",
    },
    "meditation": {
        "prompt": ("meditation ambient instrumental, singing bowls, "
                   "open fifths, deep pad, slow breathing rhythm, "
                   "spacious, calm, sleep music"),
        "bpm": 48,
        "keyscale": "C major",
        "label": "冥想 / 助眠",
    },
}

# ACE-Step 安装位置解析（优先级：环境变量 > 技能目录 acestep/ > 作者本机默认）
# 旧版写死 D:/WORKBuddy/... 仅适用于作者本机，已改为相对默认，换机不再依赖特定盘符
_HERE = os.path.dirname(os.path.abspath(__file__))


def _resolve_acestep_dir():
    env = os.environ.get("ACESTEP_DIR")
    if env and os.path.isdir(env):
        return env
    local = os.path.join(_HERE, "..", "acestep")
    if os.path.isdir(local):
        return local
    author = "D:/WORKBuddy/ace-step/ACE-Step-1.5"
    if os.path.isdir(author):
        return author
    return env or local


DEFAULT_ACESTEP_DIR = _resolve_acestep_dir()

# 官方 6GB 档位推荐模型
DEFAULT_DIT_MODEL = "acestep-v15-turbo"

# 官方文件名（用于 --check 判断权重是否就绪）
REQUIRED_SUBDIRS = ["acestep-v15-turbo", "vae"]

# 官方 API 服务默认端口（见仓库 start_api_server.bat 的 set PORT=8001）
DEFAULT_API_URL = "http://127.0.0.1:8001"

# 解释器候选（按优先级）。注意：
#   python_embedded  —— 官方便携包实际目录名（见 start_api_server.bat）
#   python_embeded   —— 官方 README 的拼写（少一个 d，保留兼容）
#   .venv            —— 源码部署（uv sync / pip 手动装）方案
_PY_CANDIDATES = [
    ("python_embedded", "python.exe"),   # 便携包（Windows）
    ("python_embeded",  "python.exe"),   # 便携包（README 拼写）
    ("python_embedded", "bin/python"),   # 便携包（*nix 兜底）
    (".venv",           "Scripts/python.exe"),
    (".venv",           "bin/python"),
]


def find_python(acestep_dir):
    """
    在 ACE-Step 目录下定位可用的 Python 解释器。

    返回 (path, kind)，找不到返回 (None, None)。
    kind ∈ {"portable", "venv"}
    """
    for sub, rel in _PY_CANDIDATES:
        p = os.path.join(acestep_dir, sub, *rel.split("/"))
        if os.path.isfile(p):
            kind = "portable" if sub.startswith("python_embed") else "venv"
            return p, kind
    return None, None


# ===========================================================================
# 一、安装状态检查
# ===========================================================================
def check_installation(acestep_dir=None):
    """检查 ACE-Step 是否可用。返回 (ok, message, details)"""
    d = acestep_dir or DEFAULT_ACESTEP_DIR
    details = {"dir": d}

    if not os.path.isdir(d):
        return False, f"未找到 ACE-Step 目录：{d}", details

    details["repo_ok"] = True

    # 找可用的 python 解释器（便携包优先，其次 .venv）
    py, kind = find_python(d)
    details["python"] = py
    details["python_kind"] = kind
    if not py:
        tried = ", ".join(f"{s}/{r}" for s, r in _PY_CANDIDATES)
        return False, (f"未找到可用的 Python 解释器（已尝试：{tried}）。"
                       f"请放入官方便携包，或在该目录执行 uv sync / pip 安装依赖。"), details

    # 检查 ace-step 包是否已装 + CUDA 是否可用
    r = subprocess.run(
        [py, "-c", "import acestep, torch; "
                   "print('acestep ok'); "
                   "print('torch', torch.__version__); "
                   "print('cuda', torch.cuda.is_available()); "
                   "print('dev', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'cpu')"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=300,
    )
    details["probe_stdout"] = (r.stdout or "").strip()
    details["probe_stderr"] = (r.stderr or "").strip()[-500:]
    if r.returncode != 0:
        return False, "解释器中 acestep/torch 未就绪（依赖未装全）", details

    details["cuda_available"] = "cuda True" in (r.stdout or "")

    # 检查权重
    ckpt_dir = os.environ.get(
        "ACESTEP_CHECKPOINTS_DIR", os.path.join(d, "checkpoints")
    )
    details["checkpoints_dir"] = ckpt_dir
    if os.path.isdir(ckpt_dir):
        got = [s for s in REQUIRED_SUBDIRS
               if os.path.isdir(os.path.join(ckpt_dir, s))]
        details["weights_found"] = got
        if len(got) < len(REQUIRED_SUBDIRS):
            missing = [s for s in REQUIRED_SUBDIRS if s not in got]
            return True, (f"环境就绪，但权重未下全（缺 {', '.join(missing)}）"
                          f"—— 首次生成时会自动从 ModelScope 下载"), details
    else:
        details["weights_found"] = []
        return True, "环境就绪，权重目录尚未创建（首次生成时自动下载）", details

    return True, f"ACE-Step 完全就绪（{kind} 环境）", details


# ===========================================================================
# 二、prompt 构造
# ===========================================================================
def load_presets():
    """
    读取 assets/l2_prompts.json 预设库。

    预设库把"常用的风格描述"沉淀成可复用条目（国学水墨、情感治愈、银发怀旧…），
    用户不必自己攒英文 prompt，直接 --preset <id> 即可。

    返回 {} 表示库不存在或损坏——此时调用方应回退到 --prompt / --mood，
    不应因此中断生成（保持"永不失败"原则）。
    """
    p = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "assets", "l2_prompts.json",
    )
    if not os.path.isfile(p):
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f).get("presets", {}) or {}
    except Exception as e:
        print(f"[WARN] 预设库读取失败({e})，请改用 --prompt", file=sys.stderr)
        return {}


def build_prompt(mood=None, raw_prompt=None, extra="",
                 bpm_override=None, keyscale_override=""):
    """
    构造最终英文 prompt。

    参数
    ----
    mood      : 情绪名（见 MOOD_TO_ACESTEP）
    raw_prompt: 自由 prompt（优先级高于 mood）
    extra     : 附加描述
    bpm_override / keyscale_override : 外部指定（如 --preset 的 bpm_hint）
                仅在 mood 未命中时生效，避免覆盖情绪预设的调性

    返回
    ----
    (prompt_str, bpm, keyscale)
    """
    bpm, keyscale = bpm_override, keyscale_override or ""
    if raw_prompt:
        base = raw_prompt.strip()
    elif mood and mood in MOOD_TO_ACESTEP:
        cfg = MOOD_TO_ACESTEP[mood]
        base = cfg["prompt"]
        bpm = cfg["bpm"]
        keyscale = cfg["keyscale"]
    else:
        base = "cinematic instrumental, expressive, emotional"

    # 强制纯器乐：ACE-Step 的 caption 里显式声明，避免出现人声
    parts = [base]
    if extra:
        parts.append(extra.strip())
    parts.append("instrumental only, no vocals, background music")
    return ", ".join(parts), bpm, keyscale


# ===========================================================================
# 三、调用方式 1：CLI + toml 配置
# ===========================================================================
def _write_toml(path, prompt, out_path, args, bpm, keyscale):
    """按官方 cli.py 的配置结构写 .toml。"""
    # 注意：ACE-Step 的 toml 键名与 GenerationParams 字段一一对应
    lines = [
        "# 由 original-bgm-forge / acestep_bridge.py 自动生成",
        f'task_type = "text2music"',
        f'caption = {json.dumps(prompt, ensure_ascii=False)}',
        'lyrics = "[Instrumental]"',
        'instrumental = true',
        f"duration = {float(args.duration)}",
        f"inference_steps = {int(args.steps)}",
        f"seed = {int(args.seed) if args.seed is not None else -1}",
        f'enable_normalization = true',
        f'normalization_db = -1.0',
        f'audio_format = "{args.format}"',
        f'batch_size = 1',
    ]
    if bpm:
        lines.append(f"bpm = {int(bpm)}")
    if keyscale:
        lines.append(f'keyscale = {json.dumps(keyscale)}')
    lines.append(f'output_dir = {json.dumps(os.path.dirname(os.path.abspath(out_path)), ensure_ascii=False)}')
    lines.append("thinking = false")          # 6GB 档位：关闭 LM 思考
    lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def run_cli(args, prompt, out_path, acestep_dir, bpm=None, keyscale=None):
    """
    走仓库自带 cli.py（非交互，靠 --config 驱动）。

    说明：官方 cli.py 只有 --config / --configure 两个入口，
    参数全部写进 .toml，因此这里先生成 toml 再调用。
    """
    py, kind = find_python(acestep_dir)
    if not py:
        print(f"[ACE-Step CLI] 未找到可用的 Python 解释器：{acestep_dir}", file=sys.stderr)
        return False
    print(f"[ACE-Step CLI] 解释器 = {py}（{kind}）")

    toml_path = os.path.abspath(out_path) + ".config.toml"
    _write_toml(toml_path, prompt, out_path, args, bpm, keyscale)

    cmd = [py, "cli.py", "--config", toml_path, "--log-level", "WARNING"]

    env = os.environ.copy()
    env.update({
        "ACESTEP_INIT_LLM": "false",              # 纯 DiT 模式（6GB 必须）
        "ACESTEP_CONFIG_PATH": args.dit_model,
        "ACESTEP_DOWNLOAD_SOURCE": "modelscope",  # 本机 HF 不可达
    })
    ckpt = os.environ.get("ACESTEP_CHECKPOINTS_DIR")
    if ckpt:
        env["ACESTEP_CHECKPOINTS_DIR"] = ckpt

    print(f"[ACE-Step CLI] cwd  = {acestep_dir}")
    print(f"[ACE-Step CLI] conf = {toml_path}")
    print(f"[ACE-Step CLI] 首次运行会从 ModelScope 下载权重（约 4-6GB），请耐心等待…")

    r = subprocess.run(
        cmd, cwd=acestep_dir, env=env,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=args.timeout,
    )
    tail = (r.stdout or "")[-2500:]
    if tail:
        print(tail)
    if r.returncode != 0:
        print("[stderr]", (r.stderr or "")[-2500:], file=sys.stderr)
        try:
            os.remove(toml_path)
        except Exception:
            pass
        return False
    try:
        os.remove(toml_path)
    except Exception:
        pass

    # cli.py 把结果写进 output_dir，文件名由它决定；这里做一次查找
    return _collect_output(out_path, args)


def _collect_output(out_path, args, search_dirs=None):
    """cli.py 输出到目录，这里把最新产物搬到用户指定的 out_path。"""
    if os.path.isfile(out_path):
        return True
    dirs = search_dirs or [
        os.path.dirname(os.path.abspath(out_path)),
        os.getcwd(),
    ]
    exts = {".mp3", ".wav", ".flac", ".opus", ".aac"}
    newest, newest_t = None, -1
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            if os.path.splitext(fn)[1].lower() not in exts:
                continue
            fp = os.path.join(d, fn)
            t = os.path.getmtime(fp)
            if t > newest_t:
                newest, newest_t = fp, t
    if newest:
        import shutil
        if os.path.abspath(newest) != os.path.abspath(out_path):
            shutil.move(newest, out_path)
        print(f"[ACE-Step] 产物 → {out_path}")
        return True
    print("[ACE-Step] 未在输出目录找到产物", file=sys.stderr)
    return False


# ===========================================================================
# 四、调用方式 2：REST API（POST /release_task）
# ===========================================================================
def run_api(args, prompt, out_path, bpm=None, keyscale=None):
    """
    走官方 REST API。

    官方端点（从 acestep/api/http/release_task_route.py 读出的真实契约）：
        POST /release_task
        body = GenerateMusicRequest（见 acestep/api/http/release_task_models.py）
        → 返回 job_id
        POST /query_result  {"job_id": ...}  轮询取结果
    """
    import time
    import urllib.request

    base = args.api_url.rstrip("/")
    payload = {
        "prompt": prompt,
        "lyrics": "[Instrumental]",
        "thinking": False,              # 6GB：不走 LM
        "model": args.dit_model,
        "task_type": "text2music",
        "inference_steps": int(args.steps),
        "audio_duration": float(args.duration),
        "audio_format": args.format,
        "batch_size": 1,
        "use_random_seed": args.seed is None,
        "vocal_language": "unknown",
    }
    if args.seed is not None:
        payload["seed"] = int(args.seed)
    if bpm:
        payload["bpm"] = int(bpm)
    if keyscale:
        payload["key_scale"] = keyscale

    if args.api_key:
        payload["_token"] = args.api_key

    def _post(path, obj, timeout=60):
        req = urllib.request.Request(
            base + path,
            data=json.dumps(obj).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        if args.api_key:
            req.add_header("Authorization", f"Bearer {args.api_key}")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    print(f"[ACE-Step API] POST {base}/release_task")
    try:
        info = _post("/release_task", payload)
    except Exception as e:
        print(f"[API] 提交失败：{e}", file=sys.stderr)
        print("[API] 提示：需先启动服务 `uv run acestep-api`", file=sys.stderr)
        return False

    job_id = (info.get("job_id") or info.get("id")
              or (info.get("data") or {}).get("job_id"))
    if not job_id:
        print(f"[API] 未拿到 job_id：{str(info)[:400]}", file=sys.stderr)
        return False
    print(f"[ACE-Step API] job_id = {job_id}，轮询结果…")

    deadline = time.time() + args.timeout
    while time.time() < deadline:
        time.sleep(3)
        try:
            res = _post("/query_result", {"job_id": job_id}, timeout=30)
        except Exception as e:
            print(f"[API] 轮询异常（继续重试）：{e}", file=sys.stderr)
            continue

        status = str(res.get("status", "")).lower()
        data = res.get("data") or res
        if status in ("failed", "error"):
            print(f"[API] 任务失败：{str(res)[:400]}", file=sys.stderr)
            return False

        audio = None
        for key in ("audio_path", "audio", "file_path", "path", "output"):
            if isinstance(data, dict) and data.get(key):
                audio = data[key]
                break
        if audio and isinstance(audio, str) and os.path.isfile(audio):
            import shutil
            shutil.copy2(audio, out_path)
            print(f"[ACE-Step API] 产物 → {out_path}")
            return True

        if status in ("completed", "success", "done", "finished"):
            print(f"[API] 任务完成但未定位到音频字段：{str(res)[:400]}",
                  file=sys.stderr)
            return False
        print(f"  … {status or 'pending'}")

    print("[API] 轮询超时", file=sys.stderr)
    return False


# ===========================================================================
# 五、调用方式 3：直接 import（用仓库 venv 跑内联脚本）
# ===========================================================================
DIRECT_RUNNER = r'''
import os, sys, json

cfg_obj = json.loads(os.environ["ACE_JOB"])
root = cfg_obj["root"]
ckpt = cfg_obj.get("ckpt") or os.path.join(root, "checkpoints")
os.environ.setdefault("ACESTEP_CHECKPOINTS_DIR", ckpt)

sys.path.insert(0, root)
os.chdir(root)

# --- 真实 API 链路（照抄官方 cli.py 的做法）---
# 依赖：acestep.handler.AceStepHandler + acestep.llm_inference.LLMHandler
# 入口：acestep.inference.generate_music(dit_handler, llm_handler, params, config, save_dir)
from acestep.handler import AceStepHandler
from acestep.llm_inference import LLMHandler
from acestep.inference import GenerationParams, GenerationConfig, generate_music

import torch
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[direct] device = {device}")

# DiT handler（核心权重）
dit_handler = AceStepHandler()
try:
    use_fa = dit_handler.is_flash_attention_available(device)
except Exception:
    use_fa = False
print(f"[direct] flash_attention = {use_fa}")

# 6GB 档位：开 CPU offload（INT8 由 handler 内部按显存自动选）
dit_handler.initialize_service(
    project_root=root,
    config_path=cfg_obj["dit_model"],
    device=device,
    use_flash_attention=use_fa,
    compile_model=False,
    offload_to_cpu=True,
    offload_dit_to_cpu=True,
)
print("[direct] DiT handler 初始化完成")

# LLM handler：纯 DiT 模式不初始化（省 4.5GB 权重 + 显存）
llm_handler = LLMHandler()
print("[direct] LLM 已禁用（DiT-only 模式）")

params = GenerationParams(
    task_type="text2music",
    caption=cfg_obj["prompt"],
    lyrics="[Instrumental]",
    instrumental=True,
    duration=float(cfg_obj["duration"]),
    inference_steps=int(cfg_obj["steps"]),
    seed=int(cfg_obj["seed"] if cfg_obj.get("seed") is not None else -1),
    thinking=False,
    enable_normalization=True,
    normalization_db=-1.0,
)
if cfg_obj.get("bpm"):
    params.bpm = int(cfg_obj["bpm"])
if cfg_obj.get("keyscale"):
    params.keyscale = cfg_obj["keyscale"]

config = GenerationConfig(batch_size=1, audio_format=cfg_obj.get("format", "mp3"))

print(f"[direct] 开始生成：{cfg_obj['duration']}s / {cfg_obj['steps']} 步 …", flush=True)
res = generate_music(dit_handler, llm_handler, params, config,
                     save_dir=cfg_obj["outdir"])

# 产物路径（兼容多种结果字段）
paths = []
for attr in ("audio_paths", "files", "output_paths", "paths"):
    v = getattr(res, attr, None)
    if v:
        paths = list(v) if isinstance(v, (list, tuple)) else [v]
        break
if not paths:
    try:
        dd = res.to_dict()
        for k in ("audio_paths", "files", "paths"):
            if dd.get(k):
                paths = dd[k]
                break
    except Exception:
        pass
print("ACE_PATHS=" + json.dumps([str(p) for p in paths]))
'''


def run_direct(args, prompt, out_path, acestep_dir, bpm=None, keyscale=None):
    """用仓库自身解释器直接跑 Python API（真实 handler 链路）。"""
    py, kind = find_python(acestep_dir)
    if not py:
        print(f"[ACE-Step direct] 未找到可用的 Python 解释器：{acestep_dir}", file=sys.stderr)
        return False
    print(f"[ACE-Step direct] 解释器 = {py}（{kind}）")

    outdir = os.path.dirname(os.path.abspath(out_path))
    job = {
        "root": os.path.abspath(acestep_dir),
        "ckpt": os.environ.get("ACESTEP_CHECKPOINTS_DIR", ""),
        "prompt": prompt,
        "duration": float(args.duration),
        "steps": int(args.steps),
        "seed": args.seed,
        "format": args.format,
        "bpm": bpm,
        "keyscale": keyscale,
        "dit_model": args.dit_model,
        "outdir": outdir,
    }
    env = os.environ.copy()
    env.update({
        "ACE_JOB": json.dumps(job, ensure_ascii=False),
        "ACESTEP_INIT_LLM": "false",
        "ACESTEP_CONFIG_PATH": args.dit_model,
        "ACESTEP_DOWNLOAD_SOURCE": "modelscope",
        "PYTHONIOENCODING": "utf-8",
        "ACESTEP_CHECKPOINTS_DIR": job["ckpt"] or os.path.join(job["root"], "checkpoints"),
    })

    print("[ACE-Step direct] 用仓库解释器直接调用 Python API（首次需加载权重，较慢）…")
    r = subprocess.run(
        [py, "-c", DIRECT_RUNNER], cwd=acestep_dir, env=env,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=args.timeout,
    )
    out = r.stdout or ""
    print(out[-3000:])
    if r.returncode != 0:
        print("[stderr]", (r.stderr or "")[-3000:], file=sys.stderr)
        return False

    # 优先用 runner 报回的精确路径
    for line in out.splitlines():
        if line.startswith("ACE_PATHS="):
            try:
                ps = json.loads(line[len("ACE_PATHS="):])
            except Exception:
                ps = []
            if ps:
                import shutil
                src = ps[0]
                if os.path.isfile(src) and os.path.abspath(src) != os.path.abspath(out_path):
                    shutil.move(src, out_path)
                    print(f"[ACE-Step direct] 产物 → {out_path}")
                    return True
    return _collect_output(out_path, args)


# ===========================================================================
# 六、CLI 入口
# ===========================================================================
def main():
    ap = argparse.ArgumentParser(
        description="ACE-Step 1.5 本地 BGM 生成桥接器（original-bgm-forge L2 引擎）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="情绪可选：\n  " + "\n  ".join(
            f"{k:<12}{v['label']}" for k, v in MOOD_TO_ACESTEP.items()),
    )
    ap.add_argument("--mood", help="情绪名（见 epilog），自动映射 prompt")
    ap.add_argument("--prompt", help="自由英文 prompt（优先级高于 --mood）")
    ap.add_argument("--preset", default=None,
                    help="使用 assets/l2_prompts.json 里的预设 id，"
                         "如 guoxue_ink / emotion_healing。用 --list-presets 查看全部。"
                         "优先级高于 --mood，低于显式 --prompt")
    ap.add_argument("--list-presets", action="store_true",
                    help="列出 L2 prompt 预设库后退出")
    ap.add_argument("--extra", default="", help="附加描述，追加到 prompt 末尾")
    ap.add_argument("--duration", type=float, default=60.0,
                    help="目标时长（秒），10~600，默认 60")
    ap.add_argument("--steps", type=int, default=8,
                    help="扩散步数。turbo 模型用 8；base/sft 用 32~50")
    ap.add_argument("--seed", type=int, default=None, help="随机种子（默认随机）")
    ap.add_argument("--out", default=None, help="输出文件路径")
    ap.add_argument("--format", default="mp3",
                    choices=["mp3", "wav", "flac", "opus", "aac"],
                    help="输出格式，默认 mp3")
    ap.add_argument("--mode", default="cli", choices=["cli", "api", "direct"],
                    help="调用方式：cli=配置文件直跑 / api=常驻服务 / direct=Python API")
    ap.add_argument("--api-url", default=DEFAULT_API_URL,
                    help=f"REST API 地址（mode=api 时用），默认 {DEFAULT_API_URL}")
    ap.add_argument("--api-key", default=os.environ.get("ACESTEP_API_KEY", ""),
                    help="REST API 鉴权 key（如服务端启用）")
    ap.add_argument("--acestep-dir", default=None, help="ACE-Step 安装目录")
    ap.add_argument("--dit-model", default=DEFAULT_DIT_MODEL,
                    help=f"DiT 模型名，默认 {DEFAULT_DIT_MODEL}")
    ap.add_argument("--timeout", type=int, default=3600,
                    help="单次调用超时（秒），默认 3600（首次含权重下载）")
    ap.add_argument("--check", action="store_true", help="检查安装状态后退出")
    ap.add_argument("--list-models", action="store_true", help="列出可用模型后退出")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出结果")

    args = ap.parse_args()

    # --- 状态检查 ---
    if args.check:
        ok, msg, det = check_installation(args.acestep_dir)
        print(("✅ " if ok else "❌ ") + msg)
        print(json.dumps(det, ensure_ascii=False, indent=2))
        return 0 if ok else 1

    # --- 列出预设库 ---
    if args.list_presets:
        presets = load_presets()
        if not presets:
            print("预设库为空或未找到 "
                  "(assets/l2_prompts.json)", file=sys.stderr)
            return 1
        print(f"L2 prompt 预设库（共 {len(presets)} 条）")
        print("=" * 74)
        for pid, pr in presets.items():
            print(f"\n  {pid}")
            print(f"    场景  {pr.get('label', '')} — {pr.get('scene', '')}")
            print(f"    建议  BPM≈{pr.get('bpm_hint', '-')}  "
                  f"时长≈{pr.get('duration_hint', '-')}s")
            print(f"    prompt {pr.get('prompt', '')}")
        print("\n" + "=" * 74)
        print("用法：--preset <id> --duration 30 --out x.mp3 --mode direct")
        return 0

    # --- 列出模型 ---
    if args.list_models:
        print("官方 DiT 模型（按显存档位）")
        print("-" * 62)
        rows = [
            ("acestep-v15-turbo", "2B", "8", "≤6GB", "Very High", "★ 本机推荐"),
            ("acestep-v15-sft", "2B", "50", "6-8GB", "High", ""),
            ("acestep-v15-base", "2B", "50", "6-8GB", "Medium", ""),
            ("acestep-v15-xl-turbo", "4B", "8", "≥12GB", "Very High", "本机跑不动"),
            ("acestep-v15-xl-sft", "4B", "50", "≥20GB", "Very High", "本机跑不动"),
        ]
        print(f"{'模型':<24}{'参数':<6}{'步数':<6}{'显存':<9}{'质量':<11}备注")
        for r in rows:
            print(f"{r[0]:<24}{r[1]:<6}{r[2]:<6}{r[3]:<9}{r[4]:<11}{r[5]}")
        print("\n官方 LM 模型（本机已关闭，纯 DiT 模式）")
        print("-" * 62)
        print("  acestep-5Hz-lm-0.6B   (Qwen3-0.6B 底座)")
        print("  acestep-5Hz-lm-1.7B   (Qwen3-1.7B 底座)")
        print("  acestep-5Hz-lm-4B     (Qwen3-4B 底座)")
        return 0

    # --- 生成 ---
    if not args.out:
        print("[错误] 未指定 --out", file=sys.stderr)
        return 2

    d = args.acestep_dir or DEFAULT_ACESTEP_DIR

    # --- 预设解析（优先级：显式 --prompt > --preset > --mood）---
    p_bpm, p_key = None, ""
    if args.preset and not args.prompt:
        presets = load_presets()
        if args.preset not in presets:
            print(f"[错误] 未知预设 '{args.preset}'。"
                  f"可用：{', '.join(presets) or '（预设库为空）'}\n"
                  f"       用 --list-presets 查看详情，或改用 --prompt",
                  file=sys.stderr)
            return 2
        pr = presets[args.preset]
        args.prompt = pr.get("prompt", "")
        p_bpm = pr.get("bpm_hint")
        print(f"[preset] {args.preset} — {pr.get('label', '')}")

    prompt, bpm, keyscale = build_prompt(args.mood, args.prompt, args.extra,
                                         p_bpm, p_key)
    print(f"[prompt] {prompt}")
    print(f"[meta]   bpm={bpm} key={keyscale} dur={args.duration}s "
          f"steps={args.steps} model={args.dit_model}")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)

    if args.mode == "cli":
        ok = run_cli(args, prompt, args.out, d, bpm, keyscale)
    elif args.mode == "api":
        ok = run_api(args, prompt, args.out, bpm, keyscale)
    else:
        ok = run_direct(args, prompt, args.out, d, bpm, keyscale)

    if args.json:
        print(json.dumps({"success": ok, "out": args.out,
                          "prompt": prompt}, ensure_ascii=False))
    if ok:
        sz = os.path.getsize(args.out) if os.path.isfile(args.out) else 0
        print(f"\n✅ 生成成功：{args.out}（{sz/1024/1024:.2f} MB）")
        return 0
    print("\n❌ 生成失败", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())

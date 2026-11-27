#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bgm_forge.py — 原创 BGM 生成统一调度器（智能路由）

三层引擎，按需自动选择
----------------------
  L1 procedural : 纯程序化合成（零依赖/纯CPU/秒级/零版权）→ 默认兜底
  L2 acestep    : ACE-Step 1.5 本地开源大模型（MIT/商用级质量）→ 需一次性部署
  L3 api        : 外部音乐 API（可选）→ 有 Key 时可用

设计原则：**永不失败**。任何一层出错自动降级到下一层，最终保底 L1。

典型用法
--------
  # 直接按情绪出 60 秒国风 BGM（自动选引擎）
  python bgm_forge.py --mood guofeng --duration 60 --out bgm.wav

  # 跟着视频时长自动配乐（读视频时长，生成稍长的 BGM）
  python bgm_forge.py --mood sad --match-video myvideo.mp4 --out bgm.wav

  # 批量出整套情绪库
  python bgm_forge.py --mood all --duration 45 --outdir ./bgm_library

  # 指定引擎
  python bgm_forge.py --mood epic --engine acestep --duration 90

  # 输出 mp3（需 ffmpeg）
  python bgm_forge.py --mood light --duration 30 --out bgm.mp3 --mp3

  # 与 typography-video-pipeline 集成：生成后直接给出 JSON 片段
  python bgm_forge.py --mood guofeng --duration 60 --json-snippet
"""

import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

# ACE-Step 默认安装位置（优先级：环境变量 > 技能目录 acestep/ > 作者本机默认）
# 旧版写死 D:/WORKBuddy/... 仅适用于作者本机，已改为相对默认
def _resolve_acestep_dir():
    env = os.environ.get("ACESTEP_DIR")
    if env and os.path.isdir(env):
        return env
    local = os.path.join(HERE, "..", "acestep")
    if os.path.isdir(local):
        return local
    author = "D:/WORKBuddy/ace-step/portable/extracted"
    if os.path.isdir(author):
        return author
    return env or local


DEFAULT_ACESTEP_DIR = _resolve_acestep_dir()

MOODS = ["guofeng", "healing", "sad", "light", "epic",
         "dark", "warm", "tense", "meditation"]


def run(cmd, **kw):
    """
    执行子进程并捕获输出。

    ⚠ 关键：ffmpeg/ffprobe 的 stderr 输出量很大，若用 pipe 捕获而不同时消费，
    管道缓冲区（Windows 约 4KB）塞满后子进程会**死锁挂起**——表现为批量
    跑到一半就卡住、mp3 被截断。因此这里统一把 stderr 降为 CRITICAL 级别，
    并对超长输出做安全读取。
    """
    # ffmpeg 系列命令自动加静默参数，避免管道阻塞
    if cmd and os.path.basename(str(cmd[0])).lower() in ("ffmpeg", "ffmpeg.exe"):
        if "-loglevel" not in cmd and "-v" not in cmd:
            cmd = list(cmd[:1]) + ["-loglevel", "error", "-nostdin"] + list(cmd[1:])
    elif cmd and os.path.basename(str(cmd[0])).lower() in ("ffprobe", "ffprobe.exe"):
        if "-v" not in cmd:
            cmd = list(cmd[:1]) + ["-v", "error"] + list(cmd[1:])
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **kw)


def probe_video_duration(path):
    """用 ffprobe 读视频/音频时长（秒）。失败返回 None。"""
    ffprobe = shutil.which("ffprobe") or "ffprobe"
    r = run([ffprobe, "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", path])
    if r.returncode == 0:
        try:
            return float(r.stdout.strip())
        except ValueError:
            return None
    return None


def wav_to_mp3(wav_path, mp3_path, bitrate="192k"):
    """wav -> mp3（需 ffmpeg）。"""
    r = run(["ffmpeg", "-y", "-i", wav_path, "-b:a", bitrate, mp3_path])
    return r.returncode == 0 and os.path.isfile(mp3_path)


def apply_fade_and_volume(in_path, out_path, fade_in=0.5, fade_out=1.5,
                          volume=1.0):
    """ffmpeg 后处理：淡入淡出 + 音量。用于让 BGM 更贴合视频。"""
    af = (f"afade=t=in:st=0:d={fade_in},"
          f"volume={volume}")
    # 需要总时长才能算淡出起点
    dur = probe_video_duration(in_path)
    if dur:
        st = max(0.0, dur - fade_out)
        af += f",afade=t=out:st={st:.2f}:d={fade_out}"
    r = run(["ffmpeg", "-y", "-i", in_path, "-af", af, out_path])
    return r.returncode == 0 and os.path.isfile(out_path)


# ---------------------------------------------------------------------------
# L1：程序化
# ---------------------------------------------------------------------------
def gen_procedural(mood, duration, bpm, seed, loop, out_wav, reverb=None,
                   instrument=None):
    print(f"[L1 程序化] mood={mood} duration={duration}s")
    cmd = [PY, os.path.join(HERE, "procedural_bgm.py"),
           "--mood", mood, "--duration", str(duration), "--out", out_wav]
    if bpm:
        cmd += ["--bpm", str(bpm)]
    if seed is not None:
        cmd += ["--seed", str(seed)]
    if reverb is not None:
        cmd += ["--reverb", str(reverb)]
    if loop:
        cmd += ["--loop"]
    if instrument:
        cmd += ["--instrument", instrument]
    r = run(cmd)
    if r.returncode != 0:
        print(r.stderr[-800:], file=sys.stderr)
        return False
    return os.path.isfile(out_wav)


# ---------------------------------------------------------------------------
# L2：ACE-Step
# ---------------------------------------------------------------------------
def gen_acestep(mood, duration, bpm, seed, out_path, acestep_dir=None,
                dit="acestep-v15-turbo", mode="cli", preset=None):
    print(f"[L2 ACE-Step] mood={mood} duration={duration}s dit={dit}"
          + (f" preset={preset}" if preset else ""))
    cmd = [PY, os.path.join(HERE, "acestep_bridge.py"),
           "--mood", mood, "--duration", str(duration),
           "--out", out_path, "--mode", mode, "--dit-model", dit]
    # 注：桥接器的 bpm 由 --mood 的情绪映射表自动带出，
    # 不暴露独立 --bpm 参数（避免与情绪预设冲突）。此处不再透传。
    if preset:
        cmd += ["--preset", preset]
    if seed is not None:
        cmd += ["--seed", str(seed)]
    if acestep_dir:
        cmd += ["--acestep-dir", acestep_dir]
    r = run(cmd, timeout=2400)
    if r.returncode != 0:
        print(r.stderr[-800:], file=sys.stderr)
        return False
    return os.path.isfile(out_path)


# ---------------------------------------------------------------------------
# 智能路由
# ---------------------------------------------------------------------------
def decide_engine(user_engine, duration, acestep_ready):
    """
    自动选引擎：
      - 用户指定则听用户的（但 acestep 不可用时降级）
      - auto：≤90s 且 acestep 未就绪 → procedural（秒出够用）
              acestep 已就绪且时长>90s 或需要高质量 → acestep
    """
    if user_engine and user_engine != "auto":
        if user_engine == "acestep" and not acestep_ready:
            print("[路由] 请求 acestep 但未就绪 → 降级 procedural")
            return "procedural"
        return user_engine
    if acestep_ready and duration > 90:
        return "acestep"
    return "procedural"


def check_acestep(acestep_dir):
    """
    判断 L2（ACE-Step）是否就绪。

    就绪条件（比"目录存在"更严格，避免误判后走到一半失败）：
      1. 仓库目录存在且有 pyproject.toml
      2. 有可用 Python 解释器（便携包 python_embeded 优先，其次 .venv）
      3. 权重目录存在（有 acestep-v15-turbo 子目录）

    注：本机实际部署在 D 盘（早期文档写 E 盘，但本机无 E 盘）。
    2026-10-09 起主推官方便携包：D:/WORKBuddy/ace-step/portable/extracted
    """
    d = acestep_dir or os.environ.get(
        "ACESTEP_DIR", DEFAULT_ACESTEP_DIR)
    if not (os.path.isdir(d) and os.path.isfile(
            os.path.join(d, "pyproject.toml"))):
        return False

    # 解释器：便携包 → .venv（两种拼写都试）
    cands = [
        os.path.join(d, "python_embeded", "python.exe"),
        os.path.join(d, "python_embedded", "python.exe"),
        os.path.join(d, "python_embeded", "bin", "python"),
        os.path.join(d, ".venv", "Scripts", "python.exe"),
        os.path.join(d, ".venv", "bin", "python"),
    ]
    if not any(os.path.isfile(c) for c in cands):
        return False

    # 权重（先看环境变量，再看仓库内 checkpoints，最后看同级 checkpoints）
    ckpt = os.environ.get("ACESTEP_CHECKPOINTS_DIR")
    for path in filter(None, [
        ckpt,
        os.path.join(d, "checkpoints"),
        os.path.join(os.path.dirname(d), "checkpoints"),
    ]):
        if os.path.isdir(os.path.join(path, "acestep-v15-turbo")):
            return True
    return False


def generate_one(mood, duration, args, out_path):
    """生成单条 BGM，含自动降级。返回 (成功, 使用的引擎)。"""
    base, ext = os.path.splitext(out_path)
    tmp_wav = base + ".tmp.wav"
    acestep_ready = check_acestep(args.acestep_dir)
    engine = decide_engine(args.engine, duration, acestep_ready)

    used = None
    if engine == "acestep":
        if gen_acestep(mood, duration, args.bpm, args.seed, tmp_wav,
                       args.acestep_dir, args.dit, args.acestep_mode,
                       getattr(args, "preset", None)):
            used = "acestep"
        else:
            print("[降级] ACE-Step 失败 → procedural")
    if used is None:
        if gen_procedural(mood, duration, args.bpm, args.seed,
                          args.loop, tmp_wav, args.reverb,
                          getattr(args, "instrument", None)):
            used = "procedural"
    if used is None:
        return False, None

    # 后处理：淡入淡出 / 音量 / 转 mp3
    if args.no_post:
        final_tmp = tmp_wav
    else:
        post_tmp = base + ".post.wav"
        ok = apply_fade_and_volume(tmp_wav, post_tmp,
                                   fade_in=args.fade_in,
                                   fade_out=args.fade_out,
                                   volume=args.volume)
        final_tmp = post_tmp if ok else tmp_wav

    if ext.lower() == ".mp3" or args.mp3:
        target = out_path if ext.lower() == ".mp3" else base + ".mp3"
        if wav_to_mp3(final_tmp, target, args.bitrate):
            for t in (tmp_wav, base + ".post.wav", base + ".tmp.wav"):
                if os.path.isfile(t) and os.path.abspath(t) != os.path.abspath(target):
                    os.remove(t)
            return True, used
        print("[警告] mp3 转换失败，保留 wav", file=sys.stderr)
        target = base + ".wav"

    target = out_path if ext.lower() == ".wav" else base + ".wav"
    if os.path.abspath(final_tmp) != os.path.abspath(target):
        shutil.move(final_tmp, target)
    # 清理所有中间产物
    for t in (tmp_wav, base + ".post.wav", base + ".tmp.wav"):
        if os.path.isfile(t) and os.path.abspath(t) != os.path.abspath(target):
            os.remove(t)
    return True, used


def main():
    ap = argparse.ArgumentParser(
        description="原创 BGM 生成统一调度器（程序化 / ACE-Step / API 三层）"
    )
    ap.add_argument("--mood", default="guofeng",
                    help=f"情绪预设，或 'all' 批量。可选：{MOODS}")
    ap.add_argument("--duration", type=float, default=60, help="时长（秒）")
    ap.add_argument("--match-video", help="读取视频时长自动定 BGM 长度")
    ap.add_argument("--pad", type=float, default=2.0,
                    help="BGM 比视频多出的秒数（默认 +2s）")
    ap.add_argument("--engine", default="auto",
                    choices=["auto", "procedural", "acestep", "api"])
    ap.add_argument("--bpm", type=int, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--reverb", type=float, default=None)
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--out", default=None, help="输出文件（单条模式）")
    ap.add_argument("--outdir", default="./bgm_library",
                    help="批量模式输出目录")
    ap.add_argument("--mp3", action="store_true", help="输出 mp3")
    ap.add_argument("--bitrate", default="192k")
    ap.add_argument("--volume", type=float, default=1.0)
    ap.add_argument("--fade-in", type=float, default=0.5)
    ap.add_argument("--fade-out", type=float, default=1.5)
    ap.add_argument("--no-post", action="store_true", help="跳过淡入淡出后处理")
    ap.add_argument("--acestep-dir", default=None)
    ap.add_argument("--acestep-mode", default="direct",
                    choices=["direct", "cli", "api"],
                    help="ACE-Step 调用方式。direct=直接 Python API（推荐，无需起服务）"
                         " / cli=配置文件 / api=常驻 REST 服务")
    ap.add_argument("--dit", default="acestep-v15-turbo")
    ap.add_argument("--instrument", default=None,
                    help="覆盖乐器音色（钢琴/古筝/木琴/钟/弦乐/竖琴/管风琴/电钢…）")
    ap.add_argument("--list-instruments", action="store_true",
                    help="列出所有可用乐器音色")
    ap.add_argument("--preset", default=None,
                    help="L2 专用：使用 assets/l2_prompts.json 的预设 id"
                         "（如 guoxue_ink / emotion_healing），只在 --engine acestep 时生效。"
                         "用 --list-presets 查看全部")
    ap.add_argument("--list-presets", action="store_true",
                    help="列出 L2 prompt 预设库后退出")
    ap.add_argument("--json-snippet", action="store_true",
                    help="输出可直接贴进 typography-video-pipeline JSON 的片段")
    args = ap.parse_args()

    if args.list_instruments:
        proc = os.path.join(HERE, "procedural_bgm.py")
        r = run([PY, proc, "--list-instruments"])
        sys.stdout.write(r.stdout or "")
        return

    if args.list_presets:
        # 转发到 ACE-Step 桥接器（预设库由它维护）
        br = os.path.join(HERE, "acestep_bridge.py")
        r = run([PY, br, "--list-presets"])
        sys.stdout.write(r.stdout or "")
        if r.returncode != 0:
            sys.stderr.write(r.stderr or "")
        return

    # 视频时长匹配
    if args.match_video:
        vd = probe_video_duration(args.match_video)
        if vd:
            args.duration = round(vd + args.pad, 1)
            print(f"[视频匹配] {args.match_video} 时长 {vd:.2f}s "
                  f"→ BGM {args.duration}s")
        else:
            print("[警告] 无法读取视频时长，沿用 --duration", file=sys.stderr)

    results = []

    if args.mood == "all":
        os.makedirs(args.outdir, exist_ok=True)
        print(f"\n===== 批量生成 {len(MOODS)} 条情绪 BGM → {args.outdir} =====\n")
        for m in MOODS:
            ext = ".mp3" if args.mp3 else ".wav"
            out = os.path.join(args.outdir, f"{m}_{int(args.duration)}s{ext}")
            ok, used = generate_one(m, args.duration, args, out)
            results.append((m, ok, used, out))
            print(f"  {'✔' if ok else '✗'} {m:<12} engine={used}\n")
    else:
        out = args.out or f"{args.mood}_{int(args.duration)}s" + \
            (".mp3" if args.mp3 else ".wav")
        ok, used = generate_one(args.mood, args.duration, args, out)
        results.append((args.mood, ok, used, out))

    # 汇总
    print("\n" + "=" * 56)
    print("生成汇总")
    print("=" * 56)
    for m, ok, used, out in results:
        size = f"{os.path.getsize(out)/1024/1024:.2f}MB" if os.path.isfile(out) else "-"
        print(f"  {'OK  ' if ok else 'FAIL'} {m:<12} {used or '-':<12} {size:>9}  {out}")
    success = sum(1 for _, ok, _, _ in results if ok)
    print(f"\n成功 {success}/{len(results)}  引擎分布: "
          f"{ {u for _,_,u,_ in results} }")

    if args.json_snippet and len(results) == 1 and results[0][1]:
        print("\n--- typography-video-pipeline JSON 片段（复制到你的脚本 JSON 里）---")
        print(json.dumps({
            "bgm": os.path.abspath(results[0][3]),
            "bgm_volume": 0.3
        }, ensure_ascii=False, indent=2))

    sys.exit(0 if success == len(results) else 1)


if __name__ == "__main__":
    main()

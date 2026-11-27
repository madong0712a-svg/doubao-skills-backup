#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
procedural_bgm.py — 纯程序化原创 BGM 生成器（零依赖 / 纯 CPU / 秒级 / 零版权）

设计意图
--------
这是 original-bgm-forge 技能的【第一层兜底引擎】：
不依赖任何大模型、不联网、不耗显存，只用 numpy + Python 标准库，
按"情绪 + 调式 + BPM + 时长"确定性地合成一段原创器乐 BGM。

为什么要有它
------------
1. 大模型（ACE-Step）虽然强，但首次需下载数 GB 权重、占显存、要 CUDA 环境；
2. 本管线（国学/情感图文视频）需要的往往只是"一段 30~90 秒、贴情绪、无人声"的底噪级 BGM；
3. 程序化合成 100% 原创、可商用、可复现（给定 seed 恒定输出），完美契合零版权红线。

音乐原理
--------
- 和弦进行（progression）：每个情绪预设绑定若干罗马数字和弦走向
  （如 5371 = V-iii-VII-I 的国风声学），由音级在半音空间展开。
- 三和弦/七和弦堆叠：root + 三度 + 五度（+ 七度），构成和声底色。
- 琶音（arpeggio）：把和弦音按节奏逐一点出，形成流动感（竖琴/古筝听感）。
- 低音线（bass）：根音低八度长音，撑住低频。
- ADSR 包络：attack/decay/sustain/release 控制每个音符的起落，避免爆音。
- 混响：用多抽头延迟（comb + allpass 简化版）营造空间感，不引入外部 IR。
- 软削波 + 归一化：保证响度一致、不破音。

用法
----
  python procedural_bgm.py --mood guofeng --duration 60 --out bgm.wav
  python procedural_bgm.py --mood healing --duration 45 --bpm 72 --seed 42
  python procedural_bgm.py --list                 # 查看所有情绪预设
  python procedural_bgm.py --mood sad --duration 30 --loop   # 生成可无缝循环的版本

免责：全部波形由本脚本数学合成，不含任何采样素材，输出为纯原创。
"""

import argparse
import json
import math
import os
import struct
import sys
import wave

try:
    import numpy as np
except ImportError:
    print("[FATAL] 需要 numpy。请先安装：pip install numpy", file=sys.stderr)
    sys.exit(1)

SR = 44100  # 采样率

# ---------------------------------------------------------------------------
# 一、情绪预设库
# ---------------------------------------------------------------------------
# key: 调式根音（MIDI 音高，60 = 中央 C）
# scale: 音阶半音偏移，大调 0 2 4 5 7 9 11 / 小调 0 2 3 5 7 8 10
# progressions: 和弦走向，数字为"音阶级数"（1=主和弦），每项是一段进行
# tempo: 推荐 BPM
# timbre: 音色倾向（影响泛音配比与包络）
# reverb: 混响强度 0~1
MOOD_PRESETS = {
    "guofeng": {
        "label": "国风 / 古韵",
        "key": 62,                      # D
        "scale": [0, 2, 3, 5, 7, 8, 10],  # 羽调式（小调色彩，东方感）
        "progressions": [
            [1, 6, 3, 5],   # i - VI - III - v
            [1, 4, 5, 1],   # i - iv - v - i
            [6, 3, 1, 5],   # VI - III - i - v
        ],
        "tempo": 68,
        "timbre": "pluck",     # 古筝/琵琶物理弦（模态合成）
        "reverb": 0.42,
        "desc": "五声音阶 + 弹拨音色，适合国学、诗词、水墨画面",
    },
    "healing": {
        "label": "治愈 / 温暖",
        "key": 60,                      # C
        "scale": [0, 2, 4, 5, 7, 9, 11],
        "progressions": [
            [1, 5, 6, 4],   # I - V - vi - IV（经典治愈走向）
            [4, 5, 3, 6],   # IV - V - III - vi
            [1, 3, 4, 5],   # I - III - IV - V
        ],
        "tempo": 76,
        "timbre": "harp",      # 竖琴 → 温暖有颗粒感
        "reverb": 0.35,
        "desc": "明亮大调 + 柔和铺底，适合日常感悟、亲子、正能量",
    },
    "sad": {
        "label": "伤感 / 怀旧",
        "key": 57,                      # A
        "scale": [0, 2, 3, 5, 7, 8, 10],
        "progressions": [
            [1, 6, 4, 5],   # i - VI - iv - V
            [1, 7, 6, 5],   # i - VII - VI - V
            [6, 4, 1, 5],   # VI - iv - i - V
        ],
        "tempo": 62,
        "timbre": "soft_piano",  # 三角钢琴
        "reverb": 0.48,
        "desc": "小调 + 慢速钢琴，适合离别、乡愁、人生感慨",
    },
    "light": {
        "label": "轻快 / 活泼",
        "key": 64,                      # E
        "scale": [0, 2, 4, 5, 7, 9, 11],
        "progressions": [
            [1, 4, 5, 1],   # I - IV - V - I
            [6, 4, 1, 5],   # vi - IV - I - V
            [1, 5, 4, 5],   # I - V - IV - V
        ],
        "tempo": 104,
        "timbre": "marimba",   # 木块模态（非谐波，真实木质感）
        "reverb": 0.25,
        "desc": "快速大调 + 跳跃音色，适合萌宠、生活、搞笑",
    },
    "epic": {
        "label": "恢弘 / 大气",
        "key": 55,                      # G
        "scale": [0, 2, 3, 5, 7, 8, 10],
        "progressions": [
            [1, 6, 3, 7],   # i - VI - III - VII（史诗进行）
            [1, 5, 6, 4],   # i - v - VI - IV
            [6, 7, 1, 1],   # VI - VII - i - i
        ],
        "tempo": 72,
        "timbre": "strings",   # 弦乐群奏（多演奏者失谐厚度）
        "reverb": 0.55,
        "desc": "小调 + 层叠弦乐 + 长混响，适合历史、人物、品牌片",
    },
    "dark": {
        "label": "压抑 / 悬疑",
        "key": 50,                      # D 低八度
        "scale": [0, 1, 3, 5, 6, 8, 10],  # 含小二度，增紧张感
        "progressions": [
            [1, 2, 1, 5],   # i - II - i - v
            [1, 6, 2, 1],   # i - VI - II - i
        ],
        "tempo": 56,
        "timbre": "drone",     # 管风琴（持续无衰减）
        "reverb": 0.6,
        "desc": "半音摩擦 + 长音铺底，适合悬疑、警示、深度思考",
    },
    "warm": {
        "label": "午后 / 悠闲",
        "key": 58,
        "scale": [0, 2, 4, 5, 7, 9, 10],  # 混合利底亚，慵懒
        "progressions": [
            [1, 7, 4, 5],   # I - VII - IV - V
            [4, 1, 5, 7],   # IV - I - V - VII
        ],
        "tempo": 84,
        "timbre": "pluck",
        "reverb": 0.3,
        "desc": "慵懒调式 + 木质感，适合日常 vlog、慢生活",
    },
    "tense": {
        "label": "紧张 / 推进",
        "key": 59,
        "scale": [0, 2, 3, 5, 7, 8, 11],
        "progressions": [
            [1, 1, 6, 5],
            [1, 5, 2, 1],
        ],
        "tempo": 112,
        "timbre": "pulse",     # FM 电钢（起音锐利）
        "reverb": 0.2,
        "desc": "脉冲式节奏 + 短促音，适合盘点、悬念、信息密集",
    },
    "meditation": {
        "label": "冥想 / 助眠",
        "key": 60,
        "scale": [0, 2, 4, 7, 9, 12, 14],  # 空五度堆叠，无紧张感
        "progressions": [
            [1, 1, 5, 5],
            [1, 4, 1, 1],
        ],
        "tempo": 48,
        "timbre": "pad",
        "reverb": 0.7,
        "desc": "空五度 + 极慢速 + 长留白，适合冥想、助眠、放松",
    },
}


# ---------------------------------------------------------------------------
# 二、基础音高工具
# ---------------------------------------------------------------------------
def midi_to_freq(m):
    """MIDI 音高 -> 频率（Hz）。A4 = 69 = 440Hz。"""
    return 440.0 * (2.0 ** ((m - 69) / 12.0))


def degree_to_midi(degree, scale, key, octave_shift=0):
    """
    把"音阶级数"映射为 MIDI 音高。
    degree: 1 起算的音阶级数（1=根音），支持 >7 自动升八度、<1 自动降八度
    scale:  音阶半音表
    key:    调式根音 MIDI
    """
    deg0 = degree - 1
    octv = deg0 // len(scale)
    idx = deg0 % len(scale)
    return key + scale[idx] + 12 * (octv + octave_shift)


# ---------------------------------------------------------------------------
# 三、音色合成（物理建模引擎）
# ---------------------------------------------------------------------------
# 【重要变更 2026-10-09】
# 旧实现是"静态谐波叠加 + 单一指数包络"，听感如同电子琴/玩具琴。
# 新实现改为调用 instrument_voices.py 的物理建模引擎：
#   - 模态合成（Modal Synthesis）：乐器 = 一组共振模态，各模态独立衰减
#   - 平滑包络：在物理建模波形之上再套一层 ADSR，控制音符起落
#   - Humanization：音高微漂移 + 力度微变化，消除机械感
#
# 音色映射：本文件的 timbre 名 → instrument_voices 的 voice 名
TIMBRE_TO_VOICE = {
    "pluck":      "guzheng",        # 弹拨 → 古筝物理模型
    "pad":        "ambient_pad",    # 铺底 → 空灵合成
    "soft_piano": "grand_piano",    # 柔钢琴 → 三角钢琴模型
    "marimba":    "marimba",        # 木琴 → 木块模态
    "strings":    "strings_ensemble",  # 弦乐 → 群奏模型
    "drone":      "organ",          # 持续低音 → 管风琴（无衰减）
    "pulse":      "epiano",         # 脉冲 → FM 电钢（起音锐利）
    "bell":       "bell",
    "harp":       "harp",
}

# 平滑包络参数（叠加在物理波形上）：(attack, decay, sustain_level, release)
# 键同时覆盖「情绪别名」和「引擎原生 voice 名」，
# 避免用户用 --instrument guzheng 时包络回落到 pad（长起音）而听感不对。
ADSR = {
    # --- 情绪别名 ---
    "pluck":      (0.003, 0.25, 0.55, 0.45),
    "pad":        (0.30,  0.5,  0.80, 0.90),
    "soft_piano": (0.004, 0.5,  0.60, 0.60),
    "marimba":    (0.001, 0.2,  0.25, 0.25),
    "strings":    (0.18,  0.4,  0.82, 0.70),
    "drone":      (0.60,  0.8,  0.90, 1.20),
    "pulse":      (0.002, 0.10, 0.40, 0.20),
    # --- 引擎原生 voice 名（与上表语义对齐）---
    "guzheng":       (0.003, 0.25, 0.55, 0.45),   # = pluck
    "grand_piano":   (0.004, 0.5,  0.60, 0.60),   # = soft_piano
    "marimba_v":     (0.001, 0.2,  0.25, 0.25),
    "bell":          (0.001, 0.6,  0.30, 1.40),   # 钟：起音极快、余韵长
    "strings_ensemble": (0.18, 0.4, 0.82, 0.70),
    "harp":          (0.004, 0.4,  0.50, 0.60),   # 竖琴：颗粒清晰
    "ambient_pad":   (0.30, 0.5,  0.80, 0.90),
    "organ":         (0.60, 0.8,  0.90, 1.20),    # 管风琴：无衰减持续
    "pluck_ks":      (0.002, 0.30, 0.50, 0.40),
    "guitar_ks":     (0.002, 0.30, 0.50, 0.40),
    "epiano":        (0.002, 0.10, 0.40, 0.20),
    "glocken":       (0.001, 0.5,  0.35, 1.20),
}


def _envelope(n, attack, decay, sustain_level, release):
    """生成平滑 ADSR 包络数组，长度 n（叠加在物理建模波形之上）。"""
    a = max(1, int(attack * SR))
    d = max(1, int(decay * SR))
    r = max(1, int(release * SR))
    s = max(0, n - a - d - r)

    env = np.zeros(n, dtype=np.float64)
    a = min(a, n)
    env[:a] = np.linspace(0.0, 1.0, a, endpoint=False)
    if s > 0:
        env[a:a + d] = 1.0 + (sustain_level - 1.0) * (
            1.0 - np.exp(-np.linspace(0, 5, d))
        )
        env[a + d:a + d + s] = sustain_level
        start = a + d + s
        r = min(r, n - start)
        if r > 0:
            env[start:start + r] = sustain_level * np.exp(
                -np.linspace(0, 5, r)
            )
    else:
        rest = n - a
        if rest > 0:
            env[a:] = 1.0 + (sustain_level - 1.0) * (
                1.0 - np.exp(-np.linspace(0, 5, rest))
            )
    return env


# 延迟导入物理建模引擎（同目录）
_INSTRUMENT_ENGINE = None


def _get_engine():
    """惰性加载 instrument_voices，避免循环依赖。"""
    global _INSTRUMENT_ENGINE
    if _INSTRUMENT_ENGINE is None:
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "instrument_voices",
                os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "instrument_voices.py"),
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _INSTRUMENT_ENGINE = mod
        except Exception as e:
            print(f"[WARN] 物理建模引擎加载失败({e})，回退简化合成",
                  file=sys.stderr)
            _INSTRUMENT_ENGINE = False
    return _INSTRUMENT_ENGINE


def _fallback_note(freq, dur, timbre):
    """兜底合成（物理引擎不可用时）：改良版正弦叠加 + 谐波独立衰减。"""
    n = int(dur * SR)
    if n <= 1:
        return np.zeros(0, dtype=np.float64)
    t = np.arange(n, dtype=np.float64) / SR
    out = np.zeros(n, dtype=np.float64)
    for h in range(1, 9):
        f = freq * h
        if f >= SR * 0.45:
            break
        # 高次谐波衰减更快（比旧版改进）
        env = np.exp(-t * (0.6 + 0.35 * h))
        out += (1.0 / h) * env * np.sin(2 * np.pi * f * t)
    return out * 0.5


def resolve_voice(timbre):
    """
    把用户传入的音色名解析为物理建模引擎的 voice 名。

    为什么需要这层（2026-10-09 修复）：
      --list-instruments 列出的是引擎的**原生** voice 名（guzheng / grand_piano …），
      但 synth_note 内部只认 TIMBRE_TO_VOICE 的**键**（pluck / soft_piano …）。
      早期实现写成 `TIMBRE_TO_VOICE.get(timbre, "grand_piano")`，
      于是用户把列表里的 `guzheng` 直接传进 --instrument 时会静默回落到钢琴——
      实测 guzheng 与 grand_piano 输出频谱完全一致（都是 1745Hz / RMS 0.1431），
      属于"参数看着生效、其实没生效"的隐蔽缺陷。

    解析顺序：
      1. 命中情绪预设别名（pluck → guzheng）
      2. 命中引擎原生 voice 名（guzheng → guzheng）
      3. 都未命中 → grand_piano 兜底
    """
    if not timbre:
        return "grand_piano"
    if timbre in TIMBRE_TO_VOICE:
        return TIMBRE_TO_VOICE[timbre]
    engine = _get_engine()
    if engine:
        try:
            names = {nm for nm, _m, _l in engine.list_voices()}
            if timbre in names:
                return timbre
        except Exception:
            pass
    return "grand_piano"


def synth_note(freq, dur, timbre, velocity=0.85, seed=0):
    """
    合成单个音符（物理建模版）。

    流程：
      1. 用物理建模引擎生成原始波形（含乐器自身衰减特性）
      2. 叠加平滑 ADSR 包络，控制音符在乐句中的起落
      3. Humanization：音高微漂移 + 力度微变化

    timbre  : 情绪别名（pluck/soft_piano…）或引擎原生 voice 名（guzheng…）
    velocity: 力度 0~1
    seed    : 随机种子
    """
    n = int(dur * SR)
    if n <= 1:
        return np.zeros(0, dtype=np.float64)

    voice = resolve_voice(timbre)
    engine = _get_engine()

    # --- Humanization：音高微漂移（真实演奏不可能每次音准一致）---
    rng = np.random.RandomState(seed & 0x7FFFFFFF)
    micro_detune = 1.0 + rng.uniform(-0.0009, 0.0009)
    vel_jitter = velocity * rng.uniform(0.88, 1.0)

    # --- 1. 物理建模波形 ---
    if engine:
        wave_out = engine.render_note(
            freq * micro_detune, dur, voice=voice,
            velocity=vel_jitter, seed=seed,
        )
    else:
        wave_out = _fallback_note(freq * micro_detune, dur, timbre)

    # 长度对齐
    if len(wave_out) < n:
        wave_out = np.concatenate([wave_out, np.zeros(n - len(wave_out))])
    else:
        wave_out = wave_out[:n]

    # --- 2. 平滑 ADSR（控制乐句中的起落）---
    attack, decay, sus, release = ADSR.get(voice, ADSR.get(timbre, ADSR["pad"]))
    # 音符太短则压缩包络
    if dur < attack + release:
        k = dur / (attack + release + 1e-6)
        attack *= k
        decay *= k
        release *= k
    wave_out = wave_out * _envelope(n, attack, decay, sus, release)

    # --- 3. 归一化 ---
    m = np.max(np.abs(wave_out))
    if m > 1e-9:
        wave_out = wave_out / m * 0.72

    return wave_out


# ---------------------------------------------------------------------------
# 四、轨道生成
# ---------------------------------------------------------------------------
def build_progression(mood, bars, seed):
    """按情绪预设展开和弦进行，返回长度为 bars 的级数序列。"""
    rng = np.random.RandomState(seed)
    presets = MOOD_PRESETS[mood]
    progs = presets["progressions"]
    out = []
    while len(out) < bars:
        p = progs[rng.randint(len(progs))]
        out.extend(p)
    return out[:bars]


def render_track(mood, duration, bpm, seed, with_melody=True, instrument=None):
    """
    渲染完整 BGM 轨道，返回 float64 单声道数组（范围约 [-1,1]）。
    结构：低音线 + 和弦铺底 + 琶音主旋律
    """
    preset = MOOD_PRESETS[mood]
    scale = preset["scale"]
    key = preset["key"]
    # 音色：命令行 --instrument 可覆盖情绪预设的默认乐器
    timbre = instrument or preset["timbre"]

    beat_dur = 60.0 / bpm          # 每拍秒数
    bar_dur = beat_dur * 4         # 4/4 拍，每小节 4 拍
    total_bars = max(1, int(math.ceil(duration / bar_dur)))
    total_len = int(total_bars * bar_dur * SR) + SR  # 尾部留 1s 给混响尾巴

    rng = np.random.RandomState(seed)
    chord_seq = build_progression(mood, total_bars, seed)

    mix = np.zeros(total_len, dtype=np.float64)

    # 每个乐器声部单独用不同的 random seed（避免同相位造成"合成感"）
    vseed_base = seed * 7919

    for bar_idx, degree in enumerate(chord_seq):
        bar_start = int(bar_idx * bar_dur * SR)
        if bar_start >= total_len:
            break

        # 小节力度：做整体起伏（2 小节一个呼吸，像真实演奏的强弱）
        bar_dyn = 0.82 + 0.18 * np.sin(bar_idx * 0.9 + seed * 0.01)

        # --- 1) 和弦音（三和弦 / 七和弦，偶尔加七度） ---
        use_seventh = rng.random() < 0.35
        chord_degrees = [degree, degree + 2, degree + 4]
        if use_seventh:
            chord_degrees.append(degree + 6)

        # 和弦铺底：整小节长音，音量较低
        # 关键：和弦音之间做"滚奏"(strumming)，不是同时精确对齐
        for ci, d in enumerate(chord_degrees):
            midi = degree_to_midi(d, scale, key, octave_shift=0)
            # 和弦音依次微延迟 8~22ms，模拟真实按弦/拨弦
            strum = ci * rng.uniform(0.008, 0.022)
            note = synth_note(midi_to_freq(midi), bar_dur * 0.95, timbre,
                              velocity=0.62 * bar_dyn,
                              seed=vseed_base + bar_idx * 31 + ci)
            st = bar_start + int(strum * SR)
            end = min(st + len(note), total_len)
            if end > st:
                mix[st:end] += note[:end - st] * 0.30

        # --- 2) 低音线：根音低一个八度，半小节一换 ---
        # 注：早期版本用 octave_shift=-2，国风 C 根音会落到 65Hz，
        # 叠加 pad 慢起音长音后在 20~120Hz 堆积出明显"嗡声"（实测比 L2 高 19.5dB）。
        # 改为 -1 八度（约 131Hz）退出嗡声区，同时改用有衰减的 soft_piano 音色
        # 避免长音互叠；音量也从 0.42 降到 0.30。
        bass_midi = degree_to_midi(degree, scale, key, octave_shift=-1)
        bass_dur = bar_dur / 2
        # 低音音色：脉冲类音色用 epiano 保持节奏感，其余一律用有衰减的钢琴，
        # 避免长音互叠产生低频堆积。
        # 注：这里用 resolve_voice 归一化，用户传 "epiano"/"pulse" 都能正确命中。
        _bass_voice = "epiano" if resolve_voice(timbre) == "epiano" \
            else "soft_piano"
        for half in range(2):
            b_start = bar_start + int(half * bass_dur * SR)
            note = synth_note(midi_to_freq(bass_midi), bass_dur * 0.9,
                              _bass_voice,
                              velocity=0.62 * bar_dyn,
                              seed=vseed_base + bar_idx * 37 + half)
            end = min(b_start + len(note), total_len)
            if end > b_start:
                mix[b_start:end] += note[:end - b_start] * 0.30

        # --- 3) 琶音主旋律：把和弦音按节奏点出 ---
        if with_melody:
            # 节奏型：八分音符为骨架，随机加入休止与装饰
            steps = 8  # 每小节 8 个八分音符
            step_dur = bar_dur / steps
            pattern_pool = [degree, degree + 2, degree + 4,
                            degree + 4, degree + 2, degree]
            # 旋律力度弧线：小节内先渐强后渐弱（真实演奏的呼吸）
            for s in range(steps):
                # 情绪决定密度：治愈/伤感稀疏，轻快/紧张密集
                density = {
                    "healing": 0.62, "sad": 0.55, "guofeng": 0.58,
                    "light": 0.85, "epic": 0.6, "dark": 0.4,
                    "warm": 0.7, "tense": 0.9, "meditation": 0.3,
                }.get(mood, 0.65)
                if rng.random() > density:
                    continue
                deg = pattern_pool[s % len(pattern_pool)]
                # 偶尔跳高八度，增加层次
                oct_shift = 1 if rng.random() < 0.22 else 0
                midi = degree_to_midi(deg, scale, key, octave_shift=oct_shift)
                n_dur = step_dur * rng.choice([0.9, 1.4, 1.9])
                # 力度弧线：小节内第 1-3 拍渐强，第 4 拍回落
                arc = 0.55 + 0.45 * math.sin(math.pi * s / steps)
                note = synth_note(midi_to_freq(midi), n_dur, timbre,
                                  velocity=0.58 * arc * bar_dyn,
                                  seed=vseed_base + bar_idx * 101 + s)
                # 微时序偏移：模拟人手不可能完全在拍上
                jitter = rng.uniform(-0.011, 0.014)
                n_start = bar_start + int(max(0.0, s * step_dur + jitter) * SR)
                end = min(n_start + len(note), total_len)
                if end > n_start:
                    mix[n_start:end] += note[:end - n_start] * 0.26

    # 截断到目标时长（+ 混响尾巴）
    target = int(duration * SR) + int(1.2 * SR)
    if len(mix) > target:
        mix = mix[:target]

    return mix, preset


# ---------------------------------------------------------------------------
# 五、空间处理：简化混响 + 软削波 + 归一化
# ---------------------------------------------------------------------------
def simple_reverb(sig, amount=0.35, seed=0):
    """用多抽头延迟模拟混响（comb + allpass 简化版），无外部 IR 依赖。"""
    if amount <= 0.001:
        return sig
    out = sig.copy()
    # 若干质数延迟抽头（毫秒），避免梳状叠加产生明显共鸣
    taps = [(37, 0.55), (61, 0.42), (89, 0.32), (127, 0.24), (173, 0.17)]
    for delay_ms, gain in taps:
        d = int(delay_ms * SR / 1000.0)
        if d >= len(sig):
            continue
        delayed = np.zeros_like(sig)
        delayed[d:] = sig[:-d]
        out += delayed * gain * amount
    return out


def soft_clip(sig, drive=1.02):
    """
    软削波：tanh 压缩动态，防止数字破音，听感更"暖"。

    注意（2026-10-09 修正）：drive 不宜过大。tanh 是非线性函数，
    对低频大信号会做"压平"处理，产生互调失真（低频嗡声）。
    早期用 1.15 时实测 20~120Hz 能量比 L2 高 19.5dB，明显发闷。
    降到 1.02 后仅在峰值附近轻微作用，既防破音又不引入嗡声。
    """
    return np.tanh(sig * drive)


def low_cut(sig, cutoff=90.0, order=1):
    """
    一阶高通滤波：砍掉 cutoff 以下的超低频。

    为什么需要：物理建模的钢琴/古筝低音区 + 贝斯叠加后，
    20~120Hz 会积累出人耳感知为"嗡嗡声"的能量。
    真实乐器最低音（古筝 D2≈73Hz、钢琴 A0≈27Hz 但能量极弱且快速衰减）
    在 BGM 混音里本就不该有持续低频堆叠，因此做低切是标准母带处理手法。

    order=1 为单极点（-6dB/oct），斜率平缓，不会让声音变"薄"。
    """
    import math
    if cutoff <= 0 or cutoff >= SR / 2:
        return sig
    rc = 1.0 / (2 * math.pi * cutoff)
    dt = 1.0 / SR
    alpha = rc / (rc + dt)
    out = np.empty_like(sig)
    prev_in = sig[0]
    prev_out = sig[0]
    for i in range(len(sig)):
        x = sig[i]
        y = alpha * (prev_out + x - prev_in)
        out[i] = y
        prev_in, prev_out = x, y
    if order > 1:
        for _ in range(order - 1):
            prev_in = out[0]
            prev_out = out[0]
            for i in range(len(out)):
                x = out[i]
                y = alpha * (prev_out + x - prev_in)
                out[i] = y
                prev_in, prev_out = x, y
    return out


def normalize(sig, peak=0.89):
    """峰值归一化到指定电平。"""
    m = np.max(np.abs(sig))
    if m < 1e-9:
        return sig
    return sig * (peak / m)


def calibrate_loudness(sig, target_rms=0.16, peak_ceiling=0.95):
    """
    响度校准：把整轨 RMS 拉齐到 target_rms（约 -16 dBFS）。
    为什么需要：不同情绪的节奏密度差异大（tense 脉冲稀疏、epic 弦乐密集），
    若只做峰值归一化，切歌时音量会忽大忽小。配乐必须响度一致。
    做了双重保护：既对齐 RMS，又保证峰值不超 ceiling。
    """
    cur = np.sqrt(np.mean(sig ** 2))
    if cur < 1e-9:
        return sig
    gain = target_rms / cur
    out = sig * gain
    # 若增益后峰值超限，回退增益（优先保峰值不破音）
    pk = np.max(np.abs(out))
    if pk > peak_ceiling:
        out = out * (peak_ceiling / pk)
    return out


def fade_edges(sig, fade_in=0.35, fade_out=1.2):
    """首尾淡入淡出，避免咔嗒声；循环版本可关闭。"""
    n = len(sig)
    fi = min(int(fade_in * SR), n // 2)
    fo = min(int(fade_out * SR), n // 2)
    if fi > 0:
        sig[:fi] *= np.linspace(0, 1, fi)
    if fo > 0:
        sig[-fo:] *= np.linspace(1, 0, fo)
    return sig


def make_loopable(sig, xfade=1.6):
    """把尾部与首部做交叉淡化，生成可无缝循环的版本。"""
    n = len(sig)
    xf = min(int(xfade * SR), n // 3)
    if xf <= 0:
        return sig
    head = sig[:xf].copy()
    tail = sig[-xf:].copy()
    # 交叉淡化：尾部逐渐被头部替换
    ramp = np.linspace(0, 1, xf)
    blended = tail * (1 - ramp) + head * ramp
    out = np.concatenate([sig[:-xf], blended[:0] if False else sig[-xf:][:0]])
    out = np.concatenate([sig[:-xf], np.zeros(0)])
    out = np.concatenate([sig[:n - xf], blended])
    # 重新构造：去掉结尾 xf 段，把混合段作为新的尾声
    out = np.concatenate([sig[:n - xf], blended])
    return out


# ---------------------------------------------------------------------------
# 六、输出 WAV（纯标准库，不依赖 scipy）
# ---------------------------------------------------------------------------
def write_wav(path, sig, sample_rate=SR):
    """写 16-bit PCM 单声道 WAV。"""
    data = np.clip(sig, -1.0, 1.0)
    ints = (data * 32767.0).astype("<i2")
    raw = ints.tobytes()
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(raw)


def to_stereo(sig, width=0.12, bass_mono_hz=200.0):
    """
    转立体声：右声道加微小延迟/衰减，产生宽度感。
    返回 interleaved int16 bytes。

    ⚠ 关键修正（2026-10-09）：低频不做声道延迟。

    早期版本对整个信号统一延迟固定样本数（width=0.12 → 约 52 样本 ≈ 1.18ms）。
    这对高频是宽度感，但低频周期远大于 1.18ms，左右声道会形成明显相位差，
    听感上就是空洞的"嗡声"（相位抵消效应）。

    正确做法（专业混音标准）：**低频归中单声道，只给高频做宽度**。
    这里用一阶分频：bass_mono_hz 以下不延迟，以上按 width 延迟。
    """
    import math
    d = int(width * SR / 100)
    left = sig
    if d <= 0:
        right = sig * 0.97
    else:
        # 一阶分频：低频（不延迟）+ 高频（延迟）
        rc = 1.0 / (2 * math.pi * bass_mono_hz)
        dt = 1.0 / SR
        alpha = rc / (rc + dt)
        low = np.empty_like(sig)
        high = np.empty_like(sig)
        prev_in = sig[0]
        prev_low = sig[0]
        for i in range(len(sig)):
            x = sig[i]
            y = alpha * (prev_low + x - prev_in)
            low[i] = y
            high[i] = x - y
            prev_in, prev_low = x, y

        # 只有高频部分参与延迟，低频保持左右一致
        del_high = np.zeros_like(high)
        del_high[d:] = high[:-d]
        del_high[:d] = high[:d]
        right = low + del_high
    right = right * 0.97
    stereo = np.stack([left, right], axis=1)
    stereo = np.clip(stereo, -1.0, 1.0)
    ints = (stereo * 32767.0).astype("<i2")
    return ints.tobytes()


def write_wav_stereo(path, sig, sample_rate=SR):
    raw = to_stereo(sig)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(raw)


# ---------------------------------------------------------------------------
# 七、主入口
# ---------------------------------------------------------------------------
def generate(mood="guofeng", duration=60, bpm=None, seed=None,
             reverb=None, melody=True, loop=False, stereo=True,
             out="bgm.wav", instrument=None):
    """一站式生成 BGM 并写出文件，返回元信息 dict。"""
    if mood not in MOOD_PRESETS:
        raise ValueError(f"未知情绪 '{mood}'，可选：{list(MOOD_PRESETS)}")

    preset = MOOD_PRESETS[mood]
    bpm = bpm or preset["tempo"]
    if seed is None:
        # ⚠ 不能用内置 hash()（2026-10-09 修复）：
        # Python 对 str/bytes 的 hash 带 PYTHONHASHSEED 随机盐，
        # 每个进程的哈希值都不同 → 同一条命令跑两次会得到不同曲子，
        # 输出无法复现（实测同命令两次 seed 分别为 863302501 / 1474680290）。
        # 改用 hashlib 的确定性摘要，保证"不给 seed 时同参数永远同一首"。
        import hashlib
        _k = f"{mood}|{duration}|{bpm}".encode("utf-8")
        seed = int.from_bytes(hashlib.sha256(_k).digest()[:4], "big") % (2 ** 31)
    rev = preset["reverb"] if reverb is None else reverb

    print(f"[1/4] 渲染轨道  mood={mood}({preset['label']}) "
          f"BPM={bpm} 时长={duration}s seed={seed}")
    sig, preset = render_track(mood, duration, bpm, seed,
                               with_melody=melody, instrument=instrument)

    print(f"[2/4] 空间处理  混响={rev}")
    sig = simple_reverb(sig, amount=rev, seed=seed)

    print("[3/4] 动态处理  低切 + 软削波 + 峰值归一化 + 响度校准")
    # 先低切再削波：避免 tanh 把超低频"压平"产生互调嗡声
    sig = low_cut(sig, cutoff=90.0, order=1)
    sig = soft_clip(sig)
    sig = normalize(sig, peak=0.89)
    sig = calibrate_loudness(sig, target_rms=0.16, peak_ceiling=0.95)

    if loop:
        print("      循环处理  首尾交叉淡化")
        sig = make_loopable(sig)
    else:
        sig = fade_edges(sig)

    print(f"[4/4] 写出文件  {out}")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    if stereo:
        write_wav_stereo(out, sig)
    else:
        write_wav(out, sig)

    dur_actual = len(sig) / SR
    meta = {
        "mood": mood,
        "mood_label": preset["label"],
        "bpm": bpm,
        "duration_requested": duration,
        "duration_actual": round(dur_actual, 2),
        "seed": seed,
        "reverb": rev,
        "loop": loop,
        "stereo": stereo,
        "sample_rate": SR,
        "output": os.path.abspath(out),
        "license": "原创程序化合成 / 无采样素材 / 可商用",
    }
    return meta


def main():
    ap = argparse.ArgumentParser(
        description="纯程序化原创 BGM 生成器（零依赖 / 纯 CPU / 零版权）"
    )
    ap.add_argument("--mood", default="guofeng", help="情绪预设名")
    ap.add_argument("--duration", type=float, default=60, help="时长（秒）")
    ap.add_argument("--bpm", type=int, default=None, help="速度，默认取预设")
    ap.add_argument("--seed", type=int, default=None, help="随机种子，决定确定性输出")
    ap.add_argument("--reverb", type=float, default=None, help="混响强度 0~1")
    ap.add_argument("--no-melody", action="store_true", help="只出和弦垫，不加琶音")
    ap.add_argument("--loop", action="store_true", help="生成可无缝循环版本")
    ap.add_argument("--mono", action="store_true", help="输出单声道")
    ap.add_argument("--out", default="bgm.wav", help="输出 wav 路径")
    ap.add_argument("--instrument", default=None,
                    help="覆盖乐器音色。可传引擎原生名（guzheng/grand_piano/"
                         "marimba/bell/strings/harp/ambient_pad/organ/"
                         "pluck_ks/guitar_ks/epiano/glocken），"
                         "也可传情绪别名（pluck/soft_piano/pad/drone/pulse）")
    ap.add_argument("--list-instruments", action="store_true",
                    help="列出所有可用乐器音色")
    ap.add_argument("--list", action="store_true", help="列出所有情绪预设")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出元信息")
    args = ap.parse_args()

    if args.list_instruments:
        eng = _get_engine()
        if eng:
            print("可用乐器音色（物理建模）：\n")
            print(f"  {'音色名':<18}{'合成方法':<8}说明")
            print("  " + "-" * 50)
            for nm, method, label in eng.list_voices():
                print(f"  {nm:<18}{method:<8}{label}")
            print("\n用法：--instrument <音色名>")
        else:
            print("物理建模引擎不可用（检查 instrument_voices.py）",
                  file=sys.stderr)
        return

    if args.list:
        print("可用情绪预设：\n")
        for k, v in MOOD_PRESETS.items():
            print(f"  {k:<12} {v['label']:<12} BPM={v['tempo']:<4} {v['desc']}")
        return

    meta = generate(
        mood=args.mood, duration=args.duration, bpm=args.bpm,
        seed=args.seed, reverb=args.reverb, melody=not args.no_melody,
        loop=args.loop, stereo=not args.mono, out=args.out,
        instrument=args.instrument,
    )
    if args.json:
        print(json.dumps(meta, ensure_ascii=False, indent=2))
    else:
        print("\n完成 ✔")
        for k, v in meta.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()

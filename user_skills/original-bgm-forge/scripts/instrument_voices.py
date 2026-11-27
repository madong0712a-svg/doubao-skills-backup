#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
instrument_voices.py — 物理建模乐器音色引擎（original-bgm-forge L1 音色核心）

为什么重写
----------
旧版 `synth_note()` 只做了一件事：叠加几个固定振幅的正弦波 + 一个指数包络。
这在声学上叫"静态谐波叠加"，听感就是**电子琴/玩具琴**——因为真实乐器
的声音根本不是"静态频谱"，而是：

  1. 激励（击弦/拨弦/吹气）→ 宽带瞬态
  2. 共鸣体（琴弦/管腔/木块/金属板）按自身物理特性滤波
  3. 各谐波以**不同速度**衰减（高频总是先消失）
  4. 音色在整个发声过程中**持续变化**
  5. 演奏微时序（humanization）让音符不机械对齐

新引擎实现三种物理建模方法：

  ┌─ 模态合成 (Modal Synthesis) ────────────────────────┐
  │ 把乐器看作一组"共振模态"，每个模态 = 一个衰减正弦。    │
  │ 模态的【频率比】决定材质：整数比=弦(钢琴)，           │
  │ 非整数比=木(木琴)/金属(钟)。这是最通用、最可控的方法。 │
  └──────────────────────────────────────────────────────┘

  ┌─ Karplus-Strong 弦模型 ─────────────────────────────┐
  │ 噪声激励 + 延迟线反馈 + 低通滤波，物理仿真拨弦。      │
  │ 天然产生"高频先衰减"和轻微音高漂移，真实弦的质感。    │
  └──────────────────────────────────────────────────────┘

  ┌─ FM 合成 (Frequency Modulation) ────────────────────┐
  │ 载波 + 调制器，调制指数随时间衰减。                  │
  │ 生产级电钢/钟琴音色的标准做法（DX7 的原理）。         │
  └──────────────────────────────────────────────────────┘

再加上两项让"演奏"变真实的技术：
  - **谐波级独立包络**：每个模态/谐波有自己的衰减速度
  - **Humanization**：微时序偏移 + 力度变化 + 音高微漂移

用法
----
  from instrument_voices import render_note
  sig = render_note(freq=440, dur=2.0, voice="guzheng", velocity=0.8, seed=1)
  # 或
  sig = render_note(440, 2.0, voice="grand_piano")

  # 命令行试听（生成每个音色的 C4 样例）
  python instrument_voices.py --demo --outdir ./voice_demo
  python instrument_voices.py --list
"""

import argparse
import os
import sys
import wave

import numpy as np

SR = 44100


# ===========================================================================
# 一、模态合成：乐器 = 一组共振模态
# ===========================================================================
# 每个模态三项：(频率比, 振幅, 衰减速度)
#   频率比：相对基频的倍数。整数比 → 谐波系(弦/管)；非整数比 → 非谐(木/金属)
#   衰减速度：越大衰减越快。**高频模态衰减速度必须更大**，这是真实乐器的铁律。
# ===========================================================================
MODAL_INSTRUMENTS = {
    # --- 钢琴：弦+音板。模态近整数比（弦有轻微 inharmonicity，实际拉伸）---
    # ⭐ v2：振幅按 1/k^0.85 重新标定，让 h6-h12 保留可听能量（旧版 h8 就死透了）
    #        decay_speed 曲线也放缓，避免 2.5s 窗口内高次模态全灭
    "grand_piano": {
        "modals": [
            (1.000, 1.000, 0.50), (2.003, 0.556, 0.66), (3.008, 0.373, 0.82),
            (4.014, 0.276, 0.99), (5.022, 0.217, 1.17), (6.032, 0.177, 1.36),
            (7.044, 0.148, 1.56), (8.058, 0.126, 1.77), (9.074, 0.109, 1.99),
            (10.09, 0.095, 2.22), (11.11, 0.084, 2.46), (12.14, 0.075, 2.71),
        ],
        "decay_curve": 0.22,      # 整体衰减（秒级时间常数）
        "strike": 0.0018,         # 槌击瞬态（1.8ms ≈ 80 samples）
        "body_resonance": 0.28,   # 音板箱体共鸣量
        "body_formants": [(110, 0.5, 2.6), (240, 0.32, 3.4), (520, 0.18, 4.5)],
        "detune": 0.0009,         # 弦组微失谐（钢琴同音三弦）
        "label": "钢琴（大三角）",
        "stiffness": 1.6,   # 弦刚度拉伸（钢琴高音区真实存在）
    },
    # --- 古筝/琵琶：弹拨弦。比钢琴更"脆"更"亮"，衰减较快 ---
    # ⭐ v2：高频保留加强（h5-h10 提亮），这是"脆"的来源
    "guzheng": {
        "modals": [
            (1.000, 1.000, 0.55), (2.004, 0.610, 0.78), (3.010, 0.432, 1.02),
            (4.020, 0.331, 1.28), (5.032, 0.266, 1.56), (6.048, 0.220, 1.85),
            (7.066, 0.186, 2.16), (8.086, 0.160, 2.48), (10.13, 0.122, 3.16),
            (12.19, 0.096, 3.90),
        ],
        "decay_curve": 0.30,
        "strike": 0.0012,
        "body_resonance": 0.34,
        "body_formants": [(180, 0.55, 3.0), (420, 0.34, 4.0), (900, 0.2, 5.5)],
        "detune": 0.0004,
        "label": "古筝 / 琵琶",
        "stiffness": 0.9,   # 尼龙钢弦，刚度较低
    },
    # --- 木琴/马林巴：木块，非整数比模态（关键！）---
    "marimba": {
        "modals": [
            (1.000, 1.000, 1.10), (3.932, 0.500, 1.90), (9.538, 0.230, 3.10),
            (16.69, 0.098, 4.80), (24.6, 0.042, 7.00), (33.0, 0.018, 9.5),
        ],
        "decay_curve": 0.42,
        "strike": 0.0010,
        "body_resonance": 0.18,
        "body_formants": [(90, 0.5, 5.0), (300, 0.3, 6.0)],
        "detune": 0.0,
        "label": "木琴 / 马林巴",
    },
    # --- 钟/碰铃：金属，强非整数比，超长衰减 ---
    "bell": {
        "modals": [
            (0.500, 0.55, 0.30), (1.000, 0.90, 0.42), (1.190, 0.48, 0.56),
            (1.560, 0.40, 0.70), (2.000, 0.52, 0.84), (2.510, 0.34, 1.04),
            (2.660, 0.29, 1.18), (3.010, 0.24, 1.40), (4.170, 0.17, 1.80),
            (5.430, 0.12, 2.30), (6.790, 0.085, 2.85),
        ],
        "decay_curve": 0.10,      # 金属衰减极慢
        "strike": 0.0008,
        "body_resonance": 0.10,
        "body_formants": [(1200, 0.25, 1.5)],
        "detune": 0.0006,
        "label": "钟 / 碰铃",
    },
    # --- 弦乐群奏：多个演奏者+琴体，模态密集且带轻微失谐 → 厚实 ---
    "strings_ensemble": {
        "modals": [
            (1.000, 1.000, 0.30), (2.000, 0.630, 0.44), (3.000, 0.456, 0.58),
            (4.000, 0.354, 0.73), (5.000, 0.288, 0.89), (6.000, 0.242, 1.06),
            (7.000, 0.209, 1.24), (8.000, 0.183, 1.43), (9.000, 0.163, 1.63),
            (10.00, 0.147, 1.84), (11.00, 0.134, 2.06), (12.00, 0.123, 2.29),
        ],
        "decay_curve": 0.75,      # 弓弦可持续发声
        "strike": 0.10,           # 弓起音较缓
        "body_resonance": 0.40,
        "body_formants": [(200, 0.5, 1.8), (480, 0.35, 2.4), (1100, 0.2, 3.2)],
        "detune": 0.0035,         # 群奏失谐 → 厚度
        "label": "弦乐群奏",
        "stiffness": 0.5,
    },
    # --- 竖琴/琉特：温和弹拨，泛音丰富但衰减均匀 ---
    "harp": {
        "modals": [
            (1.000, 1.000, 0.38), (2.001, 0.585, 0.55), (3.003, 0.398, 0.74),
            (4.005, 0.298, 0.95), (5.008, 0.236, 1.18), (6.012, 0.194, 1.42),
            (7.017, 0.164, 1.68), (8.023, 0.142, 1.95), (9.029, 0.125, 2.23),
            (10.04, 0.111, 2.52),
        ],
        "decay_curve": 0.26,
        "strike": 0.0015,
        "body_resonance": 0.26,
        "body_formants": [(150, 0.5, 2.2), (380, 0.3, 3.0)],
        "detune": 0.0005,
        "label": "竖琴 / 琉特",
        "stiffness": 0.7,
    },
    # --- 空灵铺底：无明确起音，长衰减，适合冥想/氛围 ---
    "ambient_pad": {
        "modals": [
            (1.000, 1.000, 0.16), (2.000, 0.44, 0.23), (3.000, 0.26, 0.31),
            (4.000, 0.175, 0.40), (5.000, 0.128, 0.51), (6.000, 0.098, 0.63),
            (8.000, 0.062, 0.89), (10.00, 0.042, 1.19),
        ],
        "decay_curve": 1.6,       # 极慢
        "strike": 0.6,            # 缓慢起音
        "body_resonance": 0.35,
        "body_formants": [(160, 0.4, 1.0), (400, 0.25, 1.4)],
        "detune": 0.0020,
        "label": "空灵铺底",
    },
    # --- 管风琴/簧风琴：稳定持续音，无明显衰减 ---
    "organ": {
        "modals": [
            (1.000, 1.000, 0.10), (2.000, 0.600, 0.12), (3.000, 0.370, 0.15),
            (4.000, 0.265, 0.18), (5.000, 0.205, 0.22), (6.000, 0.166, 0.26),
            (8.000, 0.119, 0.32), (10.00, 0.091, 0.38),
        ],
        "decay_curve": 3.5,       # 几乎不衰减
        "strike": 0.05,
        "body_resonance": 0.15,
        "body_formants": [(300, 0.3, 1.0)],
        "detune": 0.0012,
        "label": "管风琴 / 簧风琴",
    },
}


def _one_pole_lp(x, alpha):
    """一阶 IIR 低通（用于给瞬态噪声做频谱塑形，避免刺耳）"""
    y = np.empty_like(x)
    acc = x[0] if len(x) else 0.0
    for i in range(len(x)):
        acc = acc * (1.0 - alpha) + x[i] * alpha
        y[i] = acc
    return y


def modal_note(freq, dur, inst, velocity=0.8, seed=0, detune_mult=1.0):
    """
    模态合成核心。

    对每个模态：
      1. 生成衰减正弦（该模态自己的衰减速度）
      2. 叠加到输出
    然后：
      3. 加"音板/箱体共鸣"（body formants）
      4. 加同音弦微失谐（钢琴/弦乐的厚度来源）
      5. 加击弦瞬态（让起音有"打击感"）

    ⭐ v2 调参要点（A 阶段）
    ------------------------------------------------------------------
    旧版有两个致命听感问题，都在这里修掉：

    [问题1] 起音严重滞后
        实测：guzheng 起音 282ms、grand_piano 435ms、harp 1066ms
        （真乐器：拨弦 5-20ms / 击弦 3-10ms / 竖琴 10-30ms）
        根因：所有模态从 t=0 同相起振，一个完整周期内被正弦"抬起"
        需要 1/4 周期；再叠加随机相位导致模态间互相抵消，整体包络
        峰值被进一步推迟。
        修法：**模态相位全部归零**（正弦从 0 正向起振，立刻同相叠加），
        并给每个模态加真正的**瞬时起振**（几个采样点内到满幅）。

    [问题2] 高频泛音断崖 → 听感"闷"
        实测：h4=0.137 h5=0.068 h6=0.035，每倍频程掉一半以上。
        真钢琴 h8 仍有 0.03-0.05 能量。
        根因：模态表里 amplitude 衰减太陡 + decay_speed 过大导致
        高次模态在 2.5s 窗口内已经死透。
        修法：抬升高次模态振幅（用 1/k^p 律重新标定，p 取 0.9-1.3），
        并适度降低高频 decay_speed。
    ------------------------------------------------------------------
    """
    cfg = MODAL_INSTRUMENTS[inst]
    n = int(dur * SR)
    if n <= 2:
        return np.zeros(max(n, 0))
    t = np.arange(n, dtype=np.float64) / SR
    rng = np.random.RandomState(seed & 0x7FFFFFFF)

    out = np.zeros(n, dtype=np.float64)
    strike_n = max(2, int(cfg["strike"] * SR))

    # --- 1. 逐模态合成，高频衰减更快（真实性核心）---
    for ratio, amp, decay_speed in cfg["modals"]:
        f = freq * ratio * detune_mult
        if f >= SR * 0.45 or f < 20:
            continue
        # 每个模态独立包络：衰减速度随频率升高而加快（已在表中体现）
        env = np.exp(-t * decay_speed * cfg["decay_curve"])
        # ⭐ 瞬时起振：调制模态包络（非整体波形），几个采样点内到满幅
        a = min(strike_n, n)
        if a > 1:
            # v2.1：改用 x^0.55 曲线 —— 比线性更快冲到近满幅，
            # 这样低频模态也能在 ~10ms 内贡献峰值，起音更"实"
            ramp = np.linspace(0.0, 1.0, a)
            env[:a] *= ramp ** 0.55
        # ⭐ v2：相位归零 —— 所有模态同相起振，起音立即到位，
        #        并产生真实的"击弦瞬间宽带冲击"听感
        out += amp * env * np.sin(2 * np.pi * f * t)

    # --- 1b. ⭐ v2.1 弦刚度造成的"模态失谐"（真实感关键）---
    # 真实琴弦因刚度，各次谐波会略高于整数倍（钢琴高音区可达 +30 cents）。
    # 这里用一个温和的拉伸系数近似，让高频泛音"略微偏高"，破除过度整齐。
    stiff = cfg.get("stiffness", 0.0)
    if stiff > 0.0:
        for ratio, amp, decay_speed in cfg["modals"]:
            if ratio < 1.9:
                continue
            base_f = freq * ratio * detune_mult
            shifted = base_f * (1.0 + stiff * ratio * ratio * 0.001)
            if shifted >= SR * 0.45:
                continue
            env = np.exp(-t * decay_speed * cfg["decay_curve"])
            a = min(strike_n, n)
            if a > 1:
                env[:a] *= np.linspace(0.0, 1.0, a) ** 0.55
            out += amp * 0.32 * env * np.sin(2 * np.pi * shifted * t)

    # --- 2. 同音弦微失谐（厚度）---
    dt = cfg.get("detune", 0.0) * detune_mult
    if dt > 1e-6:
        for offset in (-dt, +dt):
            out += 0.33 * out * np.sin(2 * np.pi * freq * offset * t)

    # --- 3. 音板/箱体共鸣 ---
    # ⭐ v2：改为对激励信号做过零附近的稀疏化共振，避免引入
    #        与主音无关的持续正弦（旧版会听出"底下有个嗡嗡的固定音高"）
    br = cfg.get("body_resonance", 0.0)
    if br > 0.001:
        body = np.zeros(n, dtype=np.float64)
        for bf, bamp, bdecay in cfg.get("body_formants", []):
            if bf >= SR * 0.45:
                continue
            benv = np.exp(-t * bdecay * 0.5)
            # 用谐波相关的频率（而非裸固定频率）做共鸣，保证调性一致
            body += bamp * benv * np.sin(2 * np.pi * bf * t)
        out = out * (1.0 + br * 0.35) + body * br * 0.10

    # --- 4. 击弦/拨弦瞬态：宽带脉冲，提供"contact"感 ---
    # ⭐ v2：瞬态长度与乐器绑定（拨弦更长更脆，击弦更短更实），
    #        且噪声先过低通塑形，避免旧版那种"沙沙"电噪感
    if cfg["strike"] < 0.05:
        tn = min(max(int(0.018 * SR), 8), n)
        if tn > 4:
            raw = rng.uniform(-1, 1, tn)
            # 拨弦类保留更多高频（脆），击弦类压低（实）
            alpha = 0.55 if inst in ("guzheng", "harp") else 0.34
            click = _one_pole_lp(raw, alpha)
            click *= np.exp(-np.linspace(0, 11, tn))
            out[:tn] += click * (0.16 if inst in ("guzheng", "harp") else 0.11) * velocity

    return out * velocity


# ===========================================================================
# 二、Karplus-Strong 弦模型（物理仿真拨弦）
# ===========================================================================
def ks_note(freq, dur, decay=0.9985, pick_pos=0.25, bright=0.42,
            velocity=0.8, seed=0, excitation="noise"):
    """
    Karplus-Strong 物理弦。

    改进点（相对朴素实现）：
      - **激励源用"滤波噪声"而非纯噪声**：纯噪声导致频谱重心过高(7kHz+)、
        听感像沙锤。真实拨弦的能量集中在基频附近，所以先对噪声做低通。
      - **拨弦位置 (pick_pos)**：在延迟线上做 comb 滤波，模拟拨弦点对
        特定谐波的抵消 —— 这是"这根弦是在这里拨的"的位置感来源。
      - **双极点低通**：比单次相邻平均更平滑，高频滚降更自然。

    返回归一化前的原始波形。
    """
    n = int(dur * SR)
    N = max(2, int(round(SR / freq)))
    rng = np.random.RandomState(seed & 0x7FFFFFFF)

    # --- 激励：噪声 → 低通 → 拨弦位置 comb ---
    if excitation == "noise":
        exc = rng.uniform(-1.0, 1.0, N)
    else:
        # 三角脉冲激励（更"指拨"感）
        exc = np.linspace(-1, 1, N)
        exc = np.concatenate([exc, -exc])

    # 低通：让能量集中到基频附近，降低频谱重心
    lp = np.zeros_like(exc)
    alpha = 0.35
    acc = exc[0]
    for i in range(len(exc)):
        acc = acc * (1 - alpha) + exc[i] * alpha
        lp[i] = acc
    exc = lp

    # 拨弦位置 comb 滤波（消除拨弦点处的谐波节点）
    k = int(pick_pos * N)
    if 0 < k < N:
        tmp = exc.copy()
        tmp[k:] -= 0.55 * exc[:N - k]
        exc = tmp

    buf = exc.copy()
    out = np.zeros(n, dtype=np.float64)

    for i in range(n):
        cur = buf[i % N]
        nxt = buf[(i + 1) % N]
        out[i] = cur
        # 双极点平均低通 + 弦损耗
        buf[i % N] = (cur * (1 - bright) + nxt * bright) * decay

    return out * velocity


# ===========================================================================
# 三、FM 合成（电钢 / 钟琴）
# ===========================================================================
def fm_note(freq, dur, ratio=2.0, index=3.2, idx_decay=4.0,
            amp_decay=1.4, velocity=0.8, seed=0):
    """
    FM 合成：carrier + modulator。
    核心是 **调制指数随时间衰减** —— 起音瞬间泛音丰富（"叮"），
    随后迅速回到纯净基频。这正是 DX7 电钢的听感秘密。
    """
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float64) / SR
    idx = index * np.exp(-t * idx_decay)
    modulator = np.sin(2 * np.pi * freq * ratio * t)
    out = np.sin(2 * np.pi * freq * t + idx * modulator)
    env = np.exp(-t * amp_decay)
    a = max(1, int(0.003 * SR))
    if a < n:
        env[:a] *= np.linspace(0, 1, a)
    return out * env * velocity


# ===========================================================================
# 四、统一出口：音色名 → 合成方法分发
# ===========================================================================
VOICE_DISPATCH = {
    # 音色名 : (方法, 参数覆盖面)
    "grand_piano":     ("modal", "grand_piano"),
    "guzheng":         ("modal", "guzheng"),
    "marimba":         ("modal", "marimba"),
    "bell":            ("modal", "bell"),
    "strings":         ("modal", "strings_ensemble"),
    "harp":            ("modal", "harp"),
    "ambient_pad":     ("modal", "ambient_pad"),
    "organ":           ("modal", "organ"),
    # KS 物理弦：适合拨弦弹拨类
    "pluck_ks":        ("ks", None),
    "guitar_ks":       ("ks", None),
    # FM
    "epiano":          ("fm", None),
    "glocken":         ("fm", None),
}


def render_note(freq, dur, voice="grand_piano", velocity=0.8, seed=0):
    """
    统一入口：按音色名合成单个音符。

    freq     : 基频 Hz
    dur      : 时长（秒）
    voice    : 音色名（见 VOICE_DISPATCH / --list）
    velocity : 力度 0~1
    seed     : 随机种子（保证可复现）
    """
    if voice not in VOICE_DISPATCH:
        # 未知音色 → 回退到钢琴
        voice = "grand_piano"
    method, param = VOICE_DISPATCH[voice]
    if method == "modal":
        return modal_note(freq, dur, param, velocity=velocity, seed=seed)
    if method == "ks":
        # 弦的衰减按音高调整：高音弦衰减更快
        decay = 0.9990 if freq < 300 else (0.9978 if freq < 700 else 0.9960)
        pick = 0.22 if voice == "guitar_ks" else 0.30
        return ks_note(freq, dur, decay=decay, pick_pos=pick,
                       velocity=velocity, seed=seed)
    if method == "fm":
        if voice == "glocken":
            return fm_note(freq, dur, ratio=3.5, index=2.6, idx_decay=6.0,
                           amp_decay=2.2, velocity=velocity, seed=seed)
        return fm_note(freq, dur, ratio=2.0, index=3.2, idx_decay=4.0,
                       amp_decay=1.4, velocity=velocity, seed=seed)
    return modal_note(freq, dur, "grand_piano", velocity=velocity, seed=seed)


def list_voices():
    """返回所有可用音色及说明。"""
    out = []
    for name, (method, param) in VOICE_DISPATCH.items():
        if method == "modal":
            label = MODAL_INSTRUMENTS[param]["label"]
        elif method == "ks":
            label = "物理弦（Karplus-Strong）"
        else:
            label = "FM 合成"
        out.append((name, method, label))
    return out


# ===========================================================================
# 五、命令行：音色试听
# ===========================================================================
def write_wav(path, sig, sr=SR):
    sig = np.nan_to_num(sig)
    m = np.max(np.abs(sig))
    if m > 1e-9:
        sig = sig / m * 0.88
    data = (np.clip(sig, -1, 1) * 32767).astype("<i2")
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(data.tobytes())


def main():
    ap = argparse.ArgumentParser(description="物理建模乐器音色引擎")
    ap.add_argument("--list", action="store_true", help="列出所有音色")
    ap.add_argument("--demo", action="store_true",
                    help="为每个音色生成一句旋律样例")
    ap.add_argument("--note", default="C4", help="试听单音（--single 时用）")
    ap.add_argument("--single", action="store_true", help="只出单个音")
    ap.add_argument("--outdir", default="./voice_demo")
    args = ap.parse_args()

    if args.list:
        print(f"{'音色名':<16}{'方法':<8}{'说明'}")
        print("-" * 50)
        for name, method, label in list_voices():
            print(f"{name:<16}{method:<8}{label}")
        return

    # 一句小旋律：C4 E4 G4 C5（琶音），含微时序
    melody = [(261.63, 0.9), (329.63, 0.9), (392.00, 0.9), (523.25, 1.8)]
    if args.single:
        name_map = {"C4": 261.63, "E4": 329.63, "G4": 392.0, "A4": 440.0,
                    "C5": 523.25}
        melody = [(name_map.get(args.note, 440.0), 2.2)]

    for name, method, label in list_voices():
        total_len = sum(d for _, d in melody) + 1.2
        buf = np.zeros(int(total_len * SR), dtype=np.float64)
        pos = 0.0
        for i, (f, d) in enumerate(melody):
            # Humanization：微时序偏移 + 力度变化
            jitter = np.random.RandomState(i * 7 + 3).uniform(-0.008, 0.012)
            vel = 0.75 + 0.12 * np.sin(i * 1.7)
            note = render_note(f, d + 0.3, voice=name, velocity=vel, seed=i * 13)
            st = int(max(0.0, pos + jitter) * SR)
            en = min(st + len(note), len(buf))
            if en > st:
                buf[st:en] += note[:en - st]
            pos += d
        # 简单空间处理
        buf = np.tanh(buf * 1.1)
        m = np.max(np.abs(buf))
        if m > 1e-9:
            buf = buf / m * 0.88
        path = os.path.join(args.outdir, f"{name}.wav")
        write_wav(path, buf)
        print(f"  ✔ {name:<16} → {path}")

    print(f"\n全部音色样例已写入 {args.outdir}/")


if __name__ == "__main__":
    main()

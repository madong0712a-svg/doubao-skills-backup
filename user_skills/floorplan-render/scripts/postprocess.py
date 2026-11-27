#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
floorplan-render 出图后处理脚本

四步：
  1. 水印检测  —— 右下角 ROI 局部残差 + 5%/99% 分位对比度拉伸
  2. 水印处置  —— 按底色类型走决策树（渐变/平涂/多结构）
  3. 乱码字修复 —— 颜色检出笔画 -> inpaint -> 凸包色块 + 羽化
  4. 尺寸规范化 —— LANCZOS4 缩放到目标尺寸

⚠️ Windows 中文路径：cv2.imread/imwrite 在中文路径下静默返回 None，
    必须走 imdecode/imencode + fromfile/tofile。

用法：
    python postprocess.py --detect  <图片...>
    python postprocess.py --fix     <图片...>            # 自动决策 + 修复
    python postprocess.py --crop    <图片...>            # 判定不可修时直接裁切
    python postprocess.py --normalize <图片> --size 1536x1024
    python postprocess.py --stretch <图片>               # 只输出放大检视图

设计原则：数值达标 ≠ 视觉达标。任何处理后都必须切回正常视角目视确认。
"""

import argparse
import os
import sys

import cv2
import numpy as np

# ── 中文路径安全 IO ────────────────────────────────────────────────
def imread(p):
    return cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_COLOR)


def imwrite(p, img):
    ext = os.path.splitext(p)[1]
    ok, buf = cv2.imencode(ext, img)
    if not ok:
        raise IOError("encode failed: %s" % p)
    buf.tofile(p)


# ── 1. 水印检测 ────────────────────────────────────────────────────
def detect_watermark(img, roi_h=110, roi_w=360, save_stretch=None):
    """
    返回 (has_watermark, metrics)。
    判定依据：局部残差（灰度 - 高斯模糊）的峰值与超阈像素数。

    ⚠️ 已知误判场景：背景是大面积平滑渐变时残差极低；画面主体（大块纹理、
       布料、木纹）落进 ROI 时残差会顶满。这两种情况都**不能只看数值**，
       必须配合 stretch_watermark() 目视读数。
    """
    h, w = img.shape[:2]
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    x0 = max(0, w - roi_w)
    y0 = max(0, h - roi_h)
    roi = g[y0:h, x0:w].astype(np.float32)
    blur = cv2.GaussianBlur(roi, (0, 0), 12)
    res = roi - blur

    metrics = {
        "max": float(res.max()),
        "over6": int((res > 6).sum()),
        "std": float(roi.std()),
    }
    has = metrics["over6"] > 300
    if save_stretch:
        stretch_watermark(img, save_stretch)
    return has, metrics


def stretch_watermark(img, out_path):
    """
    对比度拉伸放大 —— 自动检测全部失效时唯一可靠的读数手段。
    5%~99% 分位拉伸（不是 min/max，避免极值干扰）到 0~255，
    再 8x 最近邻放大，肉眼读有无文字笔画。
    """
    h, w = img.shape[:2]
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    roi = g[max(0, h - 110):h, max(0, w - 360):w].astype(np.float32)
    lo, hi = np.percentile(roi, 5), np.percentile(roi, 99)
    st = np.clip((roi - lo) / max(hi - lo, 1) * 255, 0, 255).astype(np.uint8)
    st = cv2.resize(st, None, fx=2.2, fy=2.2, interpolation=cv2.INTER_NEAREST)
    imwrite(out_path, st)
    return out_path


def classify_background(img):
    """
    判定水印底下是什么底色 —— 决定用哪种修复法。
    返回 'gradient' | 'flat' | 'texture'
    """
    h, w = img.shape[:2]
    roi = img[max(0, h - 110):h, max(0, w - 360):w]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY).astype(np.float32)
    # 局部梯度能量：纹理底 >> 平涂底
    lap = cv2.Laplacian(gray, cv2.CV_32F)
    energy = float(np.abs(lap).mean())
    # 直方图峰数：平涂/渐变底的高频值集中在少数几个
    hist = np.bincount(cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY).ravel(),
                       minlength=256).astype(np.float32)
    top3 = np.sort(hist)[-3:].sum() / max(hist.sum(), 1)

    if energy > 6.0 or top3 < 0.55:
        return "texture"
    if energy > 2.0:
        return "gradient"
    return "flat"


# ── 2. 水印处置 ────────────────────────────────────────────────────
def remove_watermark_gradient(img, box=None, win=70, smooth_v=9):
    """
    逐行横向线性外推 + 纵向平滑 —— 大面积平滑渐变底唯一达标解法。
    残留率约 0.23%，残差 std 约 1.02。
    """
    h, w = img.shape[:2]
    if box is None:
        box = (w - 300, h - 80, w, h)
    x0, y0, x1, y1 = box
    out = img.astype(np.float32)
    for y in range(y0, y1):
        band = out[y, max(0, x0 - win):x0]
        if band.shape[0] < 8:
            continue
        xs = np.arange(band.shape[1], dtype=np.float32)
        # 用左侧干净带拟合直线，向右外推
        k, b = np.polyfit(xs, band.mean(axis=1), 1)
        out[y, x0:x1] = k * np.arange(x1 - x0, dtype=np.float32) + b
    # 纵向均值平滑，消除横向条带
    out[y0:y1] = cv2.blur(out[y0:y1], (1, smooth_v))
    return np.clip(out, 0, 255).astype(np.uint8)


def remove_watermark_flat(img, box=None):
    """平涂色块底：取邻域中值填充。"""
    h, w = img.shape[:2]
    if box is None:
        box = (w - 300, h - 80, w, h)
    x0, y0, x1, y1 = box
    out = img.copy()
    pad = np.pad(out[y0:y1], ((0, 0), (20, 20), (0, 0)), mode="edge")
    med = np.median(pad, axis=1)
    out[y0:y1] = np.repeat(med[:, None, :], x1 - x0, axis=1)
    return out


def crop_away(img, box=None):
    """
    多结构底（纹理/线稿/材质交界）：**直接裁切，不要试修复**。
    已验证 inpaint / 曲面重建 / 中值差分 / alpha 反推 / 笔画掩膜全部失败。
    裁切前先看主体位置：主体偏左上、水印在右下时，裁右下对构图无损。
    """
    h, w = img.shape[:2]
    if box is None:
        box = (w - 300, h - 80, w, h)
    x0, y0, _, _ = box
    side = max(x0, y0)
    return img[:side, :side].copy()


# ── 3. 乱码字修复 ──────────────────────────────────────────────────
def fix_garbled_text(img, roi, color_target, tol=(50, 40, 95)):
    """
    模型自己"画"出来的乱码字（书本标签、画框、道具标识）。
    即使提示词写了"简化为纯色块"，模型仍可能给你一串伪汉字。

    roi: (x0, y0, x1, y1) 待处理区域
    color_target: (B, G, R) 目标纯色
    tol: (r-g, r-b, r) 三个差分阈值

    幂等：重复执行时色块本身会被当成笔画重新检出、重新生成，不叠加污染。
    """
    x0, y0, x1, y1 = roi
    sub = img[y0:y1, x0:x1]
    if sub.size == 0:
        return img
    b, g, r = sub[:, :, 0].astype(np.int32), sub[:, :, 1].astype(np.int32), sub[:, :, 2].astype(np.int32)
    stroke = ((r - g > tol[0]) & (r - b > tol[1]) & (r > tol[2])).astype(np.uint8)

    if stroke.sum() == 0:
        return img  # 没有乱码，幂等返回

    sd = cv2.dilate(stroke, np.ones((3, 3), np.uint8), 1)
    base = cv2.inpaint(sub, sd, 4, cv2.INPAINT_TELEA)

    # 凸包做色块轮廓，外扩 2px，距离高斯羽化
    cnts, _ = cv2.findContours(sd, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return img
    hull = cv2.convexHull(np.vstack([c.reshape(-1, 2) for c in cnts]))
    blk = np.zeros_like(sd)
    cv2.fillConvexPoly(blk, hull, 1)
    blk = cv2.dilate(blk, np.ones((3, 3), np.uint8), 1)
    alpha = np.clip(cv2.GaussianBlur(blk.astype(np.float32), (0, 0), 1.6)[:, :, None] * 1.6, 0, 1)

    # 目标色 + 与周边同量颗粒（否则平得像贴纸）
    grain = max(float(np.std(cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY)[stroke == 0])) * 0.35, 2.0)
    patch = np.array(color_target, dtype=np.float32)[None, None, :] + \
        np.random.normal(0, grain, sub.shape)
    out = base.astype(np.float32) * (1 - alpha) + patch * alpha

    img = img.copy()
    img[y0:y1, x0:x1] = np.clip(out, 0, 255).astype(np.uint8)
    return img


# ── 4. 尺寸规范化 ──────────────────────────────────────────────────
def normalize_size(img, size):
    """
    精确尺寸一律本地后处理，不要指望提示词要到尺寸。
    size: "1536x1024"
    """
    tw, th = [int(x) for x in size.lower().split("x")]
    if img.shape[1] == tw and img.shape[0] == th:
        return img
    interp = cv2.INTER_LANCZOS4 if (tw * th < img.shape[0] * img.shape[1]) else cv2.INTER_AREA
    return cv2.resize(img, (tw, th), interpolation=interp)


# ── CLI ────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="floorplan-render 出图后处理")
    ap.add_argument("images", nargs="+")
    ap.add_argument("--detect", action="store_true", help="只检测水印")
    ap.add_argument("--fix", action="store_true", help="自动决策 + 修复")
    ap.add_argument("--crop", action="store_true", help="直接裁切掉右下")
    ap.add_argument("--stretch", action="store_true", help="输出 8x 拉伸检视图")
    ap.add_argument("--size", default="", help="目标尺寸，如 1536x1024")
    ap.add_argument("--stretch-out", default="", help="拉伸检视图输出目录")
    args = ap.parse_args()

    if not (args.detect or args.fix or args.crop or args.stretch or args.size):
        ap.error("至少指定一个动作：--detect / --fix / --crop / --stretch / --size")

    out_dir = args.stretch_out or os.path.dirname(os.path.abspath(args.images[0]))
    os.makedirs(out_dir, exist_ok=True)

    for p in args.images:
        if not os.path.exists(p):
            print("[SKIP] 不存在: %s" % p)
            continue
        img = imread(p)
        if img is None:
            print("[FAIL] 读取失败（可能是中文路径）: %s" % p)
            continue

        h, w = img.shape[:2]
        base = os.path.splitext(os.path.basename(p))[0]
        print("\n=== %s (%dx%d) ===" % (base, w, h))

        if args.detect or args.fix or args.stretch:
            sp = None
            if args.stretch or args.fix:
                sp = os.path.join(out_dir, base + "_stretch.png")
            has, m = detect_watermark(img, save_stretch=sp)
            bg = classify_background(img) if has else "-"
            print("  水印判定: %s" % ("疑似存在" if has else "未检出"))
            print("  残差指标: max=%.1f  >6的像素=%d  std=%.2f" % (m["max"], m["over6"], m["std"]))
            print("  底色类型: %s" % bg)
            if sp:
                print("  检视图  : %s" % sp)
            print("  ⚠️  数值只作辅助，最终以 8x 检视图目视为准")

        if args.fix and has:
            if bg == "texture":
                print("  → 多结构底，按决策树应 --crop 裁切，不做修复")
            else:
                img = (remove_watermark_gradient(img) if bg == "gradient"
                       else remove_watermark_flat(img))
                print("  → 已按 %s 底修复" % bg)

        if args.crop:
            img = crop_away(img)
            print("  → 已裁切为 %dx%d" % (img.shape[1], img.shape[0]))

        if args.size:
            img = normalize_size(img, args.size)
            print("  → 已规范化为 %dx%d" % (img.shape[1], img.shape[0]))

        if args.fix or args.crop or args.size:
            dst = os.path.join(out_dir, base + "_clean.png")
            imwrite(dst, img)
            print("  输出: %s" % dst)
            print("  ⚠️  请切回正常视角目视确认无新瑕疵")

    print("\nOK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

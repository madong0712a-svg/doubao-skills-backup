# -*- coding: utf-8 -*-
"""
手写采购清单图片预处理脚本
用法: python preprocess_qd.py <原图路径> [输出目录] [放大倍数=2]
输出: 全图放大 / 上下两段裁剪放大 / 两段增强版(灰度+自动对比度+锐化)，便于辨认潦草字迹。
"""
import sys
import os
from PIL import Image, ImageOps, ImageFilter


def enhance(img):
    g = ImageOps.grayscale(img)
    g = ImageOps.autocontrast(g, cutoff=2)
    g = g.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
    return g


def main():
    src = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.abspath(src))
    scale = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(src))[0]

    img = Image.open(src)
    w, h = img.size
    print("原图尺寸", w, h)

    # 全图放大
    full = img.resize((w * scale, h * scale), Image.LANCZOS)
    full.save(os.path.join(out_dir, f"{base}_full.png"))

    # 上、下两段（留少量重叠）
    bands = [
        ("top", (0, 0, w, int(h * 0.55))),
        ("bot", (0, int(h * 0.48), w, h)),
    ]
    for tag, box in bands:
        seg = img.crop(box)
        seg_big = seg.resize((seg.width * scale, seg.height * scale), Image.LANCZOS)
        seg_big.save(os.path.join(out_dir, f"{base}_{tag}.png"))
        enhance(seg_big).save(os.path.join(out_dir, f"{base}_{tag}_enh.png"))
        print("已生成", tag)

    print("输出目录", out_dir)


if __name__ == "__main__":
    main()

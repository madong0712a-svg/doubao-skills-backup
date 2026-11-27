#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""floorplan-to-render：效果图 prompt 生成器。

按「风格 × 房间」输出结构化 prompt 清单（JSON），供调用 ImageGen 图生图使用。
户型图作为 image1 输入，prompt 控制风格与视角。

仅 Python 3 标准库；pathlib 全路径；macOS / Windows 通用。

macOS / Linux:
    python3 scripts/prompt_builder.py --style nordic --rooms all --out ./out/prompts.json
Windows (PowerShell):
    python scripts\\prompt_builder.py --style nordic --rooms all --out .\\out\\prompts.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------- 风格库
# 每个风格：英文 prompt 片段（喂给 ImageGen）+ 中文说明（写进报告）+ 配色（报告色卡）
STYLES: dict[str, dict] = {
    "modern": {
        "cn": "现代简约",
        "prompt": "modern minimalist interior design, clean lines, neutral palette of white grey and black, "
                  "handleless flat-panel cabinetry, recessed lighting, large format matte tiles, "
                  "subtle metal accents, uncluttered surfaces",
        "notes": "以「少即是多」为纲：平顶无主灯、隐形收纳、大板砖通铺，靠材质对比做层次。",
        "palette": ["#F5F5F3", "#D9D9D6", "#8A8D91", "#3B3B3B", "#C0A062"],
    },
    "nordic": {
        "cn": "原木北欧",
        "prompt": "scandinavian japandi interior design, light oak wood floors and furniture, warm white walls, "
                  "linen textiles, paper pendant lamp, green plants, cozy hygge atmosphere, soft daylight",
        "notes": "浅橡木 + 暖白 + 亚麻织物，强调自然光与绿植，小户型的安全牌。",
        "palette": ["#FAF7F2", "#E8DCC8", "#C9A876", "#7A8B6F", "#4A4A45"],
    },
    "cream": {
        "cn": "奶油风",
        "prompt": "cream style interior design, warm off-white and beige tones, curved arch doorways, "
                  "boucle fabric sofa, microcement walls, soft diffused lighting, rounded furniture edges, "
                  "gentle and cozy ambiance",
        "notes": "低饱和奶咖色系 + 弧形元素 + 羊羔绒，柔光漫反射，适合采光一般的户型。",
        "palette": ["#FBF6EE", "#F0E3D0", "#DCC3A5", "#B89B7B", "#6E5B4C"],
    },
    "lightlux": {
        "cn": "轻奢",
        "prompt": "light luxury interior design, marble texture surfaces, brushed brass and champagne gold accents, "
                  "velvet upholstery, fluted wood panels, layered lighting with pendant and wall washers, "
                  "elegant hotel-like atmosphere",
        "notes": "大理石纹 + 黄铜/香槟金 + 绒面材质，重点做灯光层次，预算要留给五金和灯。",
        "palette": ["#F7F4EF", "#E3D9C6", "#C8A96A", "#5C5A58", "#2E2C2A"],
    },
    "newchinese": {
        "cn": "新中式",
        "prompt": "new chinese style interior design, dark walnut wood, ink painting artwork, round moon gate elements, "
                  "plain linen curtains, ceramic vases with dry branches, symmetrical layout, zen oriental aesthetics, "
                  "warm ambient lighting",
        "notes": "黑胡桃木 + 留白 + 中式符号点到为止（月洞/格栅/水墨），忌堆砌红木雕花。",
        "palette": ["#F6F1E8", "#D8CBB4", "#8B6B4A", "#3E352C", "#1F1B16"],
    },
    "industrial": {
        "cn": "工业风",
        "prompt": "industrial loft interior design, exposed concrete and red brick walls, black metal frame partitions, "
                  "edison bulb lighting, leather sofa, open shelving, dark wood floor, raw and masculine atmosphere",
        "notes": "清水混凝土 + 裸砖 + 黑铁件，适合层高 ≥2.8m 的户型，低层高慎用深色顶面。",
        "palette": ["#EFEDEA", "#C9C4BC", "#8C857B", "#4A4540", "#232120"],
    },
}

# ---------------------------------------------------------------- 房间库
# prompt 片段 + 建议出图尺寸 + 中文空间说明
ROOMS: dict[str, dict] = {
    "aerial": {
        "cn": "全屋 3D 鸟瞰",
        "prompt": "transform this 2d floor plan into a 3d axonometric cutaway dollhouse view of the entire apartment, "
                  "isometric top-down perspective, fully furnished rooms, {style}, "
                  "clean white background, architectural visualization quality",
        "size": "1024x1024",
        "notes": "整体格局总览：动线、分区、家具落位一目了然，适合放在报告首页。",
    },
    "living": {
        "cn": "客厅",
        "prompt": "photorealistic interior rendering of the living room based on this floor plan layout, "
                  "sofa facing tv wall, {style}, wide angle eye-level view, natural window light, "
                  "interior design magazine quality, 8k",
        "size": "1536x1024",
        "notes": "家庭门面：先定沙发朝向与电视墙做法，再决定收纳与灯光层次。",
    },
    "dining": {
        "cn": "餐厅",
        "prompt": "photorealistic interior rendering of the dining area based on this floor plan layout, "
                  "dining table with pendant light above, sideboard cabinet, {style}, "
                  "eye-level view, warm inviting lighting, interior design magazine quality, 8k",
        "size": "1536x1024",
        "notes": "小户可做客餐一体：餐桌靠厨房动线最短，吊灯距桌面 65-80cm。",
    },
    "master": {
        "cn": "主卧",
        "prompt": "photorealistic interior rendering of the master bedroom based on this floor plan layout, "
                  "double bed with upholstered headboard, bedside tables, wardrobe with sliding doors, "
                  "{style}, soft morning light through curtains, cozy relaxing atmosphere, "
                  "interior design magazine quality, 8k",
        "size": "1536x1024",
        "notes": "睡眠优先：遮光窗帘 + 3000K 暖光 + 床头双控开关，衣柜能做顶天立地就别留缝。",
    },
    "second": {
        "cn": "次卧/儿童房",
        "prompt": "photorealistic interior rendering of the secondary bedroom based on this floor plan layout, "
                  "single bed with desk and bookshelf combo, wardrobe, {style}, bright and fresh, "
                  "eye-level view, interior design magazine quality, 8k",
        "size": "1536x1024",
        "notes": "多功能定位：儿童房留成长性（可调节桌椅），客房优先榻榻米/墨菲床释放地面。",
    },
    "kitchen": {
        "cn": "厨房",
        "prompt": "photorealistic interior rendering of the kitchen based on this floor plan layout, "
                  "L-shaped cabinet layout following the wall structure, countertop with sink and stove, "
                  "range hood, {style}, bright task lighting under wall cabinets, "
                  "interior design magazine quality, 8k",
        "size": "1536x1024",
        "notes": "动线铁律：洗-切-炒三角总长 4-6m 最顺手；高低台面（水槽区 90cm/灶台区 80cm）护腰。",
    },
    "bath": {
        "cn": "卫生间",
        "prompt": "photorealistic interior rendering of the bathroom based on this floor plan layout, "
                  "walk-in shower with glass partition, wall-hung vanity, backlit mirror, {style}, "
                  "clean and bright, spa-like atmosphere, interior design magazine quality, 8k",
        "size": "1536x1024",
        "notes": "干湿分离是底线：玻璃隔断比浴帘好打理；暗卫务必做风暖 + 防雾镜 + 浅色系提亮。",
    },
    "balcony": {
        "cn": "阳台",
        "prompt": "photorealistic interior rendering of the balcony based on this floor plan layout, "
                  "laundry area with washing machine cabinet and utility sink, plants and small tea corner, "
                  "{style}, bright daylight, interior design magazine quality, 8k",
        "size": "1536x1024",
        "notes": "先定位再设计：家政阳台（洗衣柜+吊柜）还是休闲阳台（茶台+绿植），二选一不混做。",
    },
}

DEFAULT_ROOMS = ["aerial", "living", "master", "kitchen", "bath"]


def build_prompts(style_key: str, room_keys: list[str]) -> list[dict]:
    style = STYLES[style_key]
    items: list[dict] = []
    for rk in room_keys:
        room = ROOMS[rk]
        items.append({
            "room": rk,
            "room_cn": room["cn"],
            "file": f"{rk}.png",
            "size": room["size"],
            "quality": "high",
            "prompt": room["prompt"].format(style=style["prompt"]),
            "design_note": room["notes"],
        })
    return items


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="效果图 prompt 生成器（floorplan-to-render）")
    p.add_argument("--style", choices=sorted(STYLES.keys()), required=True,
                   help="装修风格：" + " / ".join(f"{k}={v['cn']}" for k, v in STYLES.items()))
    p.add_argument("--rooms", default="all",
                   help="逗号分隔的房间键，或 all（默认全部 8 个）/ default（精选 5 个）。"
                        "可选：" + ",".join(ROOMS.keys()))
    p.add_argument("--out", type=Path, default=None,
                   help="把 prompt 清单写入 JSON 文件（默认只打印到 stdout）")
    args = p.parse_args(argv)

    if args.rooms == "all":
        room_keys = list(ROOMS.keys())
    elif args.rooms == "default":
        room_keys = list(DEFAULT_ROOMS)
    else:
        room_keys = [r.strip() for r in args.rooms.split(",") if r.strip()]
        unknown = [r for r in room_keys if r not in ROOMS]
        if unknown:
            p.error(f"未知房间键: {unknown}，可选: {list(ROOMS.keys())}")

    style = STYLES[args.style]
    result = {
        "style": args.style,
        "style_cn": style["cn"],
        "style_notes": style["notes"],
        "palette": style["palette"],
        "usage": "对每条 item 调用 ImageGen：image1=户型图路径, prompt=item.prompt, "
                 "size=item.size, quality=item.quality；生成后把图片重命名为 item.file 放入同一目录。",
        "items": build_prompts(args.style, room_keys),
    }
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"written: {args.out} ({len(result['items'])} prompts, style={style['cn']})")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

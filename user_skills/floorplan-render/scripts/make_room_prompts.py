#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""make_room_prompts.py — 从平面图 JSON 自动生成「逐房间布局卡 + 效果图提示词」

为什么需要它（v4.6.0 核心修复）
--------------------------------
实测事故：AI 把平面图**手工转写**成效果图提示词时，漏写/写偏了三处——
主卧多出书桌、次卧床朝向反了且床头柜多一个、卫生间马桶朝向错。
根因不是提示词技巧，而是「**人工转写**」这个环节本身会漂移。

本脚本消灭这个环节：把平面图 JSON 当作唯一事实源，**程序直接导出**
每个房间的方位、门窗、家具（含尺寸与贴墙朝向），再拼成提示词骨架。
手不碰数据，就不会写偏。

关键设计
--------
1. **方位自动推导**：房间 polygon 的四条边 → N/E/S/W，与 walls 按坐标匹配。
   数据坐标 y 向上为北，x 向右为东。
2. **贴墙自动推断**：家具 rect 距某墙内表面 < `ADHERE_TOL` 视为贴该墙；
   也可用显式字段 `against`(N/S/E/SW…) 或 `head`(床头朝向) 覆盖。
3. **禁止清单自动生成**：房间里有几件就写几件，没写的显式禁止。
   例：只有 1 只床头柜 → 提示词自动写 "exactly ONE nightstand, NO second one"。
   这是本次事故最有效的一条约束（模型不会主动「补齐对称」）。
4. **尺寸不给模型猜**：布局卡里给净尺寸供人看；**提示词里不放具体毫米数**
   （模型读不懂 2900×3450 只会乱猜），改用「相对关系 + 数量」表达。

用法
----
  python make_room_prompts.py plan.json                  # 全屋布局卡
  python make_room_prompts.py plan.json --room R06       # 只看某间
  python make_room_prompts.py plan.json --prompt R06     # 只出提示词
  python make_room_prompts.py plan.json --check          # 只做一致性预检
  python make_room_prompts.py plan.json --dry-run        # 出图前预审包（不调生图）
  python make_room_prompts.py plan.json --dry-run --platform sd   # 指定目标平台
  python make_room_prompts.py plan.json --dry-run --pano           # 每房 4 机位环拍（漫游用）
  python make_room_prompts.py plan.json --dry-run --variations 3   # 同户型 3 个风格版本对比
  python make_room_prompts.py plan.json --dry-run --seed 20261019 # 指定 seed（跨房间一致）
  python make_room_prompts.py plan.json --dry-run --out-json prompts.json  # 机器可读，供 render.py 出图

一致性预检（--check）会报出：
  - 关键家具（bed/sofa/wardrobe/toilet）缺 `against`/`head` 显式朝向
  - 家具不与任何墙贴合（悬空/居中），提示词无法表达「贴哪面墙」
  - 同一墙上有多个门窗且间距过小（模型易合并）

出图前预审（--dry-run，v4.6.1 新增）
  **正式出图前必须先跑这一步。** 输出「一致性预检 + 交付顺序 + 逐房间布局卡
  + 逐房间提示词 + 平台负面词 + 参数建议」全套，**不调用任何生图接口**。
  用户审阅通过后才逐房间出图；预审未过（预检有 ⚠️）不得出图。

平台适配（--platform，v4.6.1 新增）
  提示词本身与平台无关，但**负面提示词与参数**必须分平台：
    auto   默认，通用负面词（等价旧行为）
    mj     Midjourney —— 不用负面词，改追加 --no 列表与 --ar/--v/--q 后缀
    sd     Stable Diffusion —— 长串负面词 + steps/cfg/sampler
    flux   FLUX.1 —— 中长负面词 + guidance
    ideogram / dalle —— 各自后缀与负面词口径
  详见 `references/platform_negative.md`。

十二段式提示词（v4.7.0 升级）
  第 1–3 段   场景 + 风格 + 机位
  第 4–6 段   ★方位锁 / ★数量锁 / ★否定锁（核心资产，本版不动）
  第 7 段     ★平台适配层（负面词分平台 + 参数建议，已由 --platform 落地）
  第 8 段     ★seed 记录与复现（同一户型所有镜头共用一个 seed，
              由计划文件内容哈希默认生成，--seed 可覆盖；
              竞品靠同一 designId 保一致，我方靠 seed）
  第 9 段     ★动态负面词（从本房间家具清单**逆向生成**：
              平面图没有书桌 → 自动写 no desk, no office chair；
              没有浴缸 → no bathtub…… 由静态清单升级为按房生成）
  第 10 段   材质/光影
  第 11 段   一致性分级声明（L1–L4，如实标注不吹完全一致）
  第 12 段   ★尺寸口径声明 —— **按 3.0「提示词瘦身」决策只放交付层**，
              不进 prompt 正文（对渲染无用、只稀释硬约束权重），
              文案：「效果图为风格与材质意向图，家具尺寸与占墙比例以平面俯视图为准」

多变体（--variations N，v4.7.0 新增，P1-3）
  同户型一次出 N 个风格版本供对比：结构/家具/方位锁全部不变，
  只换配色材质语句（STYLE_VARIANTS 前 N 项），用户挑定再全屋铺开。

全景环拍（--pano，v4.7.0 新增，P1-4）
  每房间输出东南西北 4 个机位提示词，三锁不变；交付时可拼简易漫游。

机器可读出口（--out-json，v4.7.0 新增）
  供 `scripts/render.py` 直接消费：含每镜头的 prompt / 负面词 / seed /
  机位 / 风格变体。**效果图提示词必须来自本脚本或其 JSON，禁止人工转写。**
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ADHERE_TOL = 120.0     # 距墙内表面 ≤ 此值(mm)视为贴墙
# 必须贴墙的家具类型（不贴墙则提示词无法表达方位，预检报警）
ADHERE_REQUIRED = {"bed", "sofa", "wardrobe", "toilet", "kitchen_counter",
                   "tv_cabinet", "basin", "shower", "fridge", "washing_machine"}
# 必须给朝向的类型（最易画反，必须显式 N/S/E/W）
HEAD_REQUIRED = {"bed": "床头朝向", "toilet": "水箱贴墙方位"}

# 方位 → 英文（用于提示词）
ROOM_EN = {
    "客厅": "living room", "起居室": "living room", "餐厅": "dining room",
    "厨房": "kitchen", "主卧": "master bedroom", "次卧": "second bedroom",
    "卧室": "bedroom", "卧室（北）": "north bedroom", "卧室（南）": "south bedroom",
    "卧室（东北）": "north-east bedroom", "卧室（东南）": "south-east bedroom",
    "卫生间": "bathroom", "浴室": "bathroom", "玄关": "entry hall",
    "入户": "entry hall", "阳台（南）": "south balcony", "阳台（东）": "east balcony",
    "阳台": "balcony", "书房": "study", "走廊": "corridor", "过道": "corridor",
}
FURN_EN = {
    "双人床": "double bed", "单人床": "single bed", "床头柜": "nightstand",
    "衣柜": "wardrobe", "沙发": "sofa", "茶几": "coffee table", "电视柜": "TV console",
    "餐桌": "dining table", "餐椅": "dining chair", "椅子": "chair",
    "橱柜（北）": "kitchen cabinet", "橱柜（西）": "kitchen cabinet", "水槽": "sink",
    "灶台": "cooktop", "冰箱": "fridge", "马桶": "toilet", "洗手台": "vanity",
    "淋浴间": "shower enclosure", "洗衣机": "washing machine", "绿植": "plant",
    "休闲椅": "lounge chair", "小几": "side table", "书桌": "desk",
}

DIR_EN = {"N": "NORTH", "S": "SOUTH", "E": "EAST", "W": "WEST",
          "NE": "NORTH-EAST", "NW": "NORTH-WEST",
          "SE": "SOUTH-EAST", "SW": "SOUTH-WEST"}
DIR_ZH = {"N": "北", "S": "南", "E": "东", "W": "西",
          "NE": "东北", "NW": "西北", "SE": "东南", "SW": "西南"}

# ------------------------------------------------------ 平台适配（v4.6.1）
# 提示词正文与平台无关；**负面提示词与生成参数**必须分平台。
# 负面词分三档：none（MJ 不用负面词）/ mid（FLUX 等）/ long（SD 要长串才压得住）。
# 案例专属排除项（如 no desk）不走这里 —— 那层写在提示词正文里，与平台无关。
NEG_BASE = (
    "blurry, low quality, distorted, deformed, unnatural proportions, "
    "poorly rendered, unbalanced composition"
)
NEG_MID = NEG_BASE + ", cluttered, messy, dark, poorly lit, amateur, low resolution"
NEG_LONG = NEG_MID + (
    ", watermark, signature, text, letters, numbers, logo, username, "
    "duplicate, cloned furniture, mirrored furniture, extra furniture, "
    "missing furniture, floating furniture, furniture clipping through walls, "
    " tilted walls, bent walls, non-vertical lines, wrong perspective, "
    "fisheye distortion, oversaturated, HDR overprocessed, cartoon, illustration, 3d render look"
)
PLATFORMS = {
    "auto": {
        "label": "通用（未指定平台）",
        "negative": NEG_MID,
        "no_list": None,
        "suffix": "",
        "params": {"说明": "未指定平台，负面词取中档；参数由宿主工具决定"},
    },
    "mj": {
        "label": "Midjourney (v6)",
        # MJ 没有 negative prompt 概念，排除项走 --no
        "negative": None,
        "no_list": (
            "wall-hung toilet, sintered stone, vessel sink, ornate ceiling, "
            "crown moulding, patterned wallpaper, gold trim, tufted upholstery, "
            "cluttered, plants, artwork, text, letters, numbers, logos, watermark"
        ),
        "suffix": " --ar 16:9 --v 6 --style raw --q 2",
        "params": {
            "宽高比": "--ar 16:9（室内全景）；建筑外观 3:2；细部特写 1:1",
            "质量": "--q 2（高品质，推荐）",
            "风格": "--style raw（减少 MJ 自作主张的美化）",
        },
    },
    "sd": {
        "label": "Stable Diffusion (WebUI / ComfyUI)",
        "negative": NEG_LONG,
        "no_list": None,
        "suffix": "",
        "params": {
            "采样器": "DPM++ 2M Karras",
            "步数": "30",
            "CFG Scale": "7",
            "分辨率": "1024×768（横向房间）",
            "hires fix": "建议开，0.5x upscale，出图更锐",
        },
    },
    "flux": {
        "label": "FLUX.1 (schnell / dev / pro)",
        "negative": NEG_MID,
        "no_list": None,
        "suffix": "",
        "params": {
            "schnell": "steps 4，免 guidance（免费档首选）",
            "dev": "steps 28，guidance 3.5",
            "pro": "steps 25，guidance 3",
            "说明": "schnell 不吃长负面词，压中档即可",
        },
    },
    "ideogram": {
        "label": "Ideogram",
        "negative": NEG_MID,
        "no_list": None,
        "suffix": "",
        "params": {"风格": "Design/General", "魔法提示": "可开，画面更精致但更偏离字面"},
    },
    "dalle": {
        "label": "DALL·E 3",
        # DALL·E 3 会自动改写提示词，负面词效果有限
        "negative": NEG_BASE,
        "no_list": None,
        "suffix": "",
        "params": {
            "注意": "DALL·E 3 会自行扩写并可能忽略排除项，**不要用于要求严格一致的场景**",
            "尺寸": "1024×1792 / 1792×1024",
        },
    },
}


def platform_cfg(platform):
    return PLATFORMS.get((platform or "auto").lower(), PLATFORMS["auto"])


def render_negative_block(platform):
    """输出平台负面词 + --no 列表 + 参数建议（dry-run / 分平台出图用）。"""
    cfg = platform_cfg(platform)
    L = [f"**目标平台：{cfg['label']}**\n"]
    if cfg["negative"]:
        L.append("负面提示词（Negative Prompt）\n```text")
        L.append(cfg["negative"])
        L.append("```\n")
    if cfg["no_list"]:
        L.append("排除参数（Midjourney 用 --no，不用负面词）\n```text")
        L.append("--no " + cfg["no_list"])
        L.append("```\n")
    if cfg["params"]:
        L.append("参数建议\n")
        L.append("| 项 | 值 |")
        L.append("|---|---|")
        for k, v in cfg["params"].items():
            L.append(f"| {k} | {v} |")
        L.append("")
    if cfg["suffix"]:
        L.append(f"提示词后缀（追加在正文之后）\n```text{cfg['suffix']}\n```\n")
    return "\n".join(L)


# 交付排序：客餐厅 → 主卧 → 次卧 → 其他（与主流工具一致，符合阅读习惯）
ROOM_DELIVERY_ORDER = ["客厅", "起居室", "客餐厅", "餐厅", "主卧", "次卧",
                       "卧室", "书房", "厨房", "卫生间", "浴室", "洗衣房",
                       "阳台", "玄关", "走廊", "过道"]


def delivery_rank(name):
    for i, k in enumerate(ROOM_DELIVERY_ORDER):
        if k in name:
            return i
    return len(ROOM_DELIVERY_ORDER)


# ------------------------------------------------------ 风格变体库（v4.7.0 P1-3）
# 多变体对比用：结构/家具/三锁全部不变，只换配色材质语句。
# 第 1 项为默认基线（等价旧行为：不额外插句）。
STYLE_VARIANTS = [
    {"name": "minimalist", "zh": "现代简约", "clause": ""},
    {"name": "warm Scandinavian", "zh": "北欧原木",
     "clause": "Warm Scandinavian palette - light oak wood tones, off-white walls, "
               "linen and cotton textiles, a few ceramic accessories."},
    {"name": "modern Japanese", "zh": "现代日式",
     "clause": "Modern Japanese palette - warm wood and paper-white tones, "
               "low-profile furniture, calm and uncluttered, paper screens."},
    {"name": "light luxury", "zh": "轻奢",
     "clause": "Light-luxury palette - cream white with restrained brass accents, "
               "marble tops, a single velvet cushion."},
    {"name": "soft contemporary", "zh": "奶油现代",
     "clause": "Soft contemporary palette - warm off-white and beige tones, "
               "gently rounded cabinet profiles, matte textures."},
]

# -------------------------------------------- 动态缺失负面词（v4.7.0 第 9 段升级）
# 由「本房间没有的家具类型」逆向生成。键 = furniture[].type；值 = 提示词否定句。
# 原则：只列**该房型可能被误画**的项 —— 静态段落已覆盖的（plants/artwork/text…）
# 不重复列；明显不属于该房型的（如卧室里的冰箱）也不列，避免负面词膨胀稀释权重。
ABSENCE_NEGATIVE = [
    ("bathtub", "no bathtub, no freestanding tub"),
    ("desk", "no desk, no office chair"),
    ("dining_table", "no dining table, no dining chairs"),
    ("sofa", "no sofa"),
    ("tv_cabinet", "no television, no TV screen"),
    ("washing_machine", "no washing machine"),
    ("fridge", "no refrigerator"),
    ("wardrobe", "no wardrobe, no open clothes rack"),
    ("coffee_table", "no coffee table"),
    ("bookshelf", "no bookshelf, no open shelving"),
    ("treadmill", "no treadmill, no exercise equipment"),
    ("piano", "no piano, no musical instruments"),
    ("aquarium", "no fish tank, no aquarium"),
    ("range_hood", "no range hood, no hanging cabinets"),
]
_NEG_MAP = dict(ABSENCE_NEGATIVE)

# 每种房型只允许否定「可能被误画」的项；按房间名关键词匹配，先命中先生效。
ABSENCE_SCOPE = [
    (("卫生间", "浴室", "洗手间"), ("bathtub", "washing_machine")),
    (("厨房",), ("dining_table", "sofa", "washing_machine")),
    (("阳台", "露台"), ("bathtub", "washing_machine")),
    (("玄关", "走廊", "过道", "入户"), ()),
    (("餐厅",), ("desk", "washing_machine", "bookshelf", "treadmill",
                 "piano", "aquarium", "bathtub", "range_hood")),
    (("客厅", "起居室"), ("desk", "washing_machine", "bookshelf", "treadmill",
                          "piano", "aquarium", "bathtub", "range_hood",
                          "dining_table")),
]
# 卧室/书房及其它未列名房型的默认范围（全部为卧室可能被误补的件）
ABSENCE_DEFAULT = ("desk", "sofa", "tv_cabinet", "washing_machine", "bookshelf",
                   "treadmill", "piano", "aquarium", "coffee_table")


def absence_scope(name):
    for keys, scope in ABSENCE_SCOPE:
        if any(k in name for k in keys):
            return scope
    return ABSENCE_DEFAULT


def dynamic_absence(info):
    """第 9 段：按本房间房型 + 家具清单逆向生成「不得出现」清单。"""
    name = info["room"].get("name", "")
    present = {f["type"] for f in info["furniture"]}
    return [_NEG_MAP[k] for k in absence_scope(name) if k not in present]


# ------------------------------------------------------ 环拍机位（v4.7.0 P1-4）
# (相机所在墙, 视线朝向)：东南西北各一张，拼起来是简易漫游。
PANO_DIRS = [("N", "S"), ("S", "N"), ("E", "W"), ("W", "E")]

# 第 12 段：尺寸口径声明（只进交付层，不进 prompt 正文 —— 见 docstring 瘦身决策）
SIZE_DISCLAIMER = ("效果图为风格与材质意向图，家具尺寸与占墙比例以平面俯视图为准。")


def plan_seed(data):
    """第 8 段：由计划文件内容派生确定性 seed（同一户型 → 同一 seed）。

    同一户型的全部镜头共用一个 seed，是跨房间风格/色调一致的保底手段
    （竞品靠同一 designId，我们没有 designId，用 seed 顶上）。
    """
    import hashlib
    blob = json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return int(hashlib.md5(blob).hexdigest()[:8], 16) % 2147483647


# ------------------------------------------------------------------ 几何工具
def poly_bbox(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def room_sides(poly):
    """返回房间四条外边：{'N': y值, 'S': y值, 'E': x值, 'W': x值}"""
    x0, y0, x1, y1 = poly_bbox(poly)
    return {"N": y1, "S": y0, "E": x1, "W": x0}


def wall_of_room(walls, sides, bbox=None, tol=60):
    """把房间四条边匹配到 walls（按中心线坐标重合）。返回 {'N': wall, ...}

    bbox 传入时必须做**空间重叠校验**：同一坐标上可能有多道不重叠的墙
    （如 x=2050 上 W13 管 y 0–5750、W16 管 y 7800–11400），
    只认与房间边实际共线的那道——否则墙 id/墙厚/门窗归属全错。
    """
    out = {}
    x0, y0, x1, y1 = bbox if bbox else (None, None, None, None)
    for d, coord in sides.items():
        for w in walls:
            (wx1, wy1), (wx2, wy2) = w["p1"], w["p2"]
            if d in ("N", "S"):
                if abs(wy1 - wy2) >= 1 or abs(wy1 - coord) > tol:
                    continue
                if bbox and max(wx1, wx2) < x0 - tol:
                    continue
                if bbox and min(wx1, wx2) > x1 + tol:
                    continue
            else:
                if abs(wx1 - wx2) >= 1 or abs(wx1 - coord) > tol:
                    continue
                if bbox and max(wy1, wy2) < y0 - tol:
                    continue
                if bbox and min(wy1, wy2) > y1 + tol:
                    continue
            out[d] = w
            break
    return out


def net_bounds(poly, side_walls):
    """按所属墙的厚度内缩，得到房间净边界。"""
    x0, y0, x1, y1 = poly_bbox(poly)
    ids = {}
    for d, w in side_walls.items():
        if w:
            t = w.get("thickness", 100) / 2.0
            if d == "N":
                y1 -= t
            elif d == "S":
                y0 += t
            elif d == "E":
                x1 -= t
            elif d == "W":
                x0 += t
            ids[d] = w["id"]
    return x0, y0, x1, y1, ids


def adhere_dirs(rect, nb, tol=ADHERE_TOL):
    """家具贴哪几面墙（可多重，如 L 形柜同时贴两面墙）。"""
    x, y, w, h = rect
    nx0, ny0, nx1, ny1 = nb
    out = []
    if abs(y + h - ny1) <= tol:
        out.append("N")
    if abs(y - ny0) <= tol:
        out.append("S")
    if abs(x + w - nx1) <= tol:
        out.append("E")
    if abs(x - nx0) <= tol:
        out.append("W")
    return out


def long_axis(rect):
    """返回 'x' 或 'y'（长边方向）。"""
    return "x" if rect[2] >= rect[3] else "y"


# ------------------------------------------------------------------ 单房间
def describe_room(data, room):
    walls = data["walls"]
    openings = data["openings"]
    furniture = data["furniture"]

    poly = room["polygon"]
    sides = room_sides(poly)
    side_walls = wall_of_room(walls, sides, poly_bbox(poly))
    nb_full = net_bounds(poly, side_walls)
    nb = nb_full[:4]
    nx0, ny0, nx1, ny1 = nb
    wall_ids = nb_full[4]
    net_w, net_d = nx1 - nx0, ny1 - ny0

    # 门窗：按所属墙归到方位
    wall_dir = {v["id"]: k for k, v in side_walls.items() if v}
    ops = []
    for o in openings:
        d = wall_dir.get(o["wall"])
        if not d:
            continue
        # 同一道墙可能服务多个房间：只收落在本房间该边投影范围内的洞口
        cx, cy = o.get("center", [0, 0])
        half = o.get("width", 0) / 2.0
        if d in ("N", "S"):
            if not (nx0 - half <= cx <= nx1 + half):
                continue
        else:
            if not (ny0 - half <= cy <= ny1 + half):
                continue
        ops.append({
            "id": o["id"], "dir": d, "type": o.get("type", "door"),
            "width": o.get("width", 0),
            "center": o.get("center", [0, 0]),
            "hinge": o.get("hinge_side"), "open": o.get("open_side"),
        })
    ops.sort(key=lambda o: (o["dir"], o["id"]))

    # 家具
    furns = []
    for f in furniture:
        if f.get("room") != room["id"]:
            continue
        rect = f["rect"]
        ad = f.get("against")
        if ad:
            ad = [ad] if isinstance(ad, str) else list(ad)
        else:
            ad = adhere_dirs(rect, nb)
        # 判断该件是否只占墙面一部分：用「离门更近/更远」表达，模型比百分比听得懂
        short = ""
        if ad and rect[2] * rect[3] > 0:
            span = (nx1 - nx0) if ad[0] in ("N", "S") else (ny1 - ny0)
            along = rect[2] if ad[0] in ("N", "S") else rect[3]
            if span > 0 and along < span * 0.8:
                short = (" - NOTE: this piece is SHORT, it covers only about "
                         f"{along / span * 100:.0f} percent of that wall's clear length; "
                         "the remaining stretch of the same wall stays completely bare "
                         "white plaster, and the doorway side of the wall must be empty")
        furns.append({
            "id": f["id"], "name": f.get("name", f["id"]), "_short": short,
            "type": f.get("type", ""), "rect": rect,
            "w": rect[2], "h": rect[3],
            "against": ad,
            "head": f.get("head"),
            "axis": long_axis(rect),
            "cx": rect[0] + rect[2] / 2.0,
            "cy": rect[1] + rect[3] / 2.0,
        })

    return {
        "room": room, "sides": sides, "wall_ids": wall_ids,
        "net": (nx0, ny0, nx1, ny1), "net_w": net_w, "net_d": net_d,
        "openings": ops, "furniture": furns,
    }


def camera_hint(info):
    """机位建议：站在门所在墙面朝对侧看；无门则站南侧朝北。"""
    doors = [o for o in info["openings"] if o["type"] in ("door", "sliding_door")]
    if not doors:
        return "S", "N"
    d = doors[0]["dir"]
    opp = {"N": "S", "S": "N", "E": "W", "W": "E"}[d]
    return d, opp


# ------------------------------------------------------------------ 布局卡
def render_card(info, idx=None):
    r = info["room"]
    nx0, ny0, nx1, ny1 = info["net"]
    L = []
    title = r.get("name", r["id"])
    L.append(f"### {('机位 %d｜' % idx) if idx else ''}{title}（{r['id']}）\n")

    # 结构
    L.append("**[2] 结构与净尺寸**")
    L.append(f"- 净值：**{info['net_w']:.0f} × {info['net_d']:.0f} mm**"
             f"（{'南北向进深' if info['net_d'] > info['net_w'] else '东西向面宽'}较大）")
    L.append("- 四周墙：" + "、".join(
        f"{DIR_ZH[d]}墙" + (f"({info['wall_ids'][d]})" if d in info["wall_ids"] else "")
        for d in ("N", "E", "S", "W") if d in info["wall_ids"]))
    L.append("")

    # 门窗
    L.append("**[门/窗：逐樘锁定]**")
    if not info["openings"]:
        L.append("- 本房间无门窗（内隔间）——**画面中不得出现任何窗或采光井**")
    for o in info["openings"]:
        t = {"door": "平开门", "window": "窗", "sliding_door": "推拉门",
             "bay_window": "飘窗"}.get(o["type"], o["type"])
        extra = ""
        if o["type"] == "door":
            extra = f"，铰链在{'西/起点' if o['hinge']=='p1' else '东/终点'}侧，向{'外' if o['open']==1 else '内'}开"
        L.append(f"- **{DIR_ZH[o['dir']]}墙**：{t}，洞口宽 {o['width']:.0f}mm{extra}")
    L.append("")

    # 家具
    L.append("**[家具：逐件锁定，数量与朝向不得增删]**")
    L.append("")
    L.append("| 家具 | 尺寸(mm) | 贴墙 | 长边方向 | 备注 |")
    L.append("|---|---|---|---|---|")
    for f in info["furniture"]:
        ad = "/".join(DIR_ZH[a] for a in f["against"]) or "—（不贴墙）"
        ax = "东西向" if f["axis"] == "x" else "南北向"
        note = ""
        if f["type"] == "bed":
            note = f"**床头朝{DIR_ZH.get(f['head'], f['head'])}**" if f["head"] else "⚠️ 床头朝向未标注"
        if f["type"] == "wardrobe":
            note = "通高、无把手"
        L.append(f"| {f['name']} | {f['w']:.0f}×{f['h']:.0f} | {ad} | {ax} | {note} |")
    L.append("")
    if not info["furniture"]:
        L.append("- **本房间不放家具**\n")

    # 机位
    fd, td = camera_hint(info)
    L.append("**[7] 机位**")
    L.append(f"- 站在**{DIR_ZH[fd]}墙**（门口）朝**{DIR_ZH[td]}**看，视高 1.5m，一点透视")
    L.append("")
    return "\n".join(L)


# ------------------------------------------------------------------ 提示词
def render_prompt(info, style="minimalist", platform="auto", camera=None,
                  variant_clause=""):
    """生成单镜头提示词。

    camera: (所在墙, 朝向) 覆盖默认门位机位（--pano 环拍用）。
    variant_clause: 风格变体的配色材质句（--variations 用；空 = 默认基线）。
    """
    r = info["room"]
    name = r.get("name", r["id"])
    if camera:
        fd, td = camera
        at_door = False
    else:
        fd, td = camera_hint(info)
        at_door = True

    # 方位 → 画面左右
    # 朝北看：东在右；朝南看：西在右；朝东看：南在右；朝西看：北在右
    right_of = {"N": "E", "S": "W", "E": "S", "W": "N"}
    left_of = {"N": "W", "S": "E", "E": "N", "W": "S"}
    R, Lf = right_of[td], left_of[td]

    lines = []
    cam = (f"just inside the doorway on the {DIR_EN[fd]} wall" if at_door
           else f"at the {DIR_EN[fd]} wall")
    lines.append(
        f"Photorealistic interior render of a {('small ' if info['net_w'] < 2600 or info['net_d'] < 2600 else '')}"
        f"{style} {ROOM_EN.get(name, 'room')}. "
        f"Camera stands {cam}, "
        f"looking straight {DIR_EN[td]} at eye level, one-point perspective. "
        f"Layout must match EXACTLY as described - do NOT add, remove, move, "
        f"resize or mirror anything, and do not invent extra furniture to fill space.")
    lines.append("")

    # 逐墙
    by_dir = {}
    for o in info["openings"]:
        by_dir.setdefault(o["dir"], []).append(o)
    # 每件家具只归到「主贴墙」= against 的第一项，避免重复描述
    by_furn = {}
    for f in info["furniture"]:
        # 归墙优先级：head（床头/水箱所靠墙）> against 第一项 > 居中
        if f.get("head"):
            key = f["head"]
        else:
            key = (f["against"] or ["CENTER"])[0]
        by_furn.setdefault(key, []).append(f)

    for d in (td, R, Lf, fd):
        label = {"far": DIR_EN[d] + " WALL (far / straight ahead)"}
        seg = []
        for o in by_dir.get(d, []):
            if o["type"] == "window":
                seg.append(f"one window, {o['width']:.0f} mm wide, normal flat window "
                           f"(not floor-to-ceiling, not a door)")
            elif o["type"] == "sliding_door":
                seg.append(f"one floor-to-ceiling sliding glass door, "
                           f"{o['width']:.0f} mm wide, with a clearly visible aluminium FLOOR TRACK")
            elif o["type"] == "door":
                side = "west" if o["hinge"] == "p1" else "east"
                seg.append(f"one open doorway (plain door opening), {o['width']:.0f} mm wide, "
                           f"door leaf hinged on its {side} side")
            elif o["type"] == "bay_window":
                seg.append(f"one bay window, {o['width']:.0f} mm wide")
        for f in by_furn.get(d, []):
            seg.append(_furn_clause(f))
        pos = "ahead" if d == td else ("on the RIGHT" if d == R else
                                       ("on the LEFT" if d == Lf else "behind the camera"))
        if seg:
            lines.append(f"- {DIR_EN[d]} WALL ({pos}): " + "; ".join(seg) + ".")
        else:
            lines.append(f"- {DIR_EN[d]} WALL ({pos}): plain bare white wall, empty, nothing on it.")

    # 中央家具（不贴墙）
    if by_furn.get("CENTER"):
        lines.append("- FLOOR CENTRE: " + "; ".join(_furn_clause(f) for f in by_furn["CENTER"]) + ".")

    # 数量守恒（本次事故最有效的一条）
    lines.append("")
    lines.append("COUNT LOCK — the room contains exactly these items and nothing else:")
    if info["furniture"]:
        cnt = {}
        for f in info["furniture"]:
            nm = FURN_EN.get(f["name"], f["name"])
            cnt[nm] = cnt.get(nm, 0) + 1
        lines.append("- " + "; ".join(f"{v} × {k}" for k, v in cnt.items()) + ".")
        # 显式否定易被模型「补对称」的项（实测事故驱动，保留）
        names = [f["type"] for f in info["furniture"]]
        negs = []
        if names.count("nightstand") <= 1:
            negs.append("no second nightstand")
        if "desk" not in names:
            negs.append("no desk, no office chair")
        if "chair" not in names and "dining_table" not in names:
            negs.append("no chair, no bench, no stool")
        if negs:
            lines.append("- FORBIDDEN: " + "; ".join(negs) + ".")
    else:
        lines.append("- NO furniture at all.")
    lines.append("")

    # 第 9 段（v4.7.0 升级）：动态缺失否定 —— 从本房间家具清单逆向生成
    absence = dynamic_absence(info)
    if absence:
        lines.append("ABSENCE LOCK — the following items are NOT in this room, "
                     "do not draw them: " + "; ".join(absence) + ".")
        lines.append("")

    # 第 10 段：材质/光影（变体配色句插在最前，结构纪律段保持不变）
    if variant_clause:
        lines.append(variant_clause)
        lines.append("")
    lines.append("STYLE: pure white matte walls, handleless flush cabinetry, flat ceiling "
                 "with one slim recessed linear LED light at 3500K, no cornice, no chandelier, "
                 "no pendant, straight clean lines, restrained palette, generous negative space, "
                 "matte finishes. Real interior photography, soft daylight, true material textures, "
                 "stable verticals, correct perspective, everything firmly on the floor.")
    lines.append("")
    lines.append("No wall-hung toilet, no sintered stone, no vessel sink, no top-hung sliding "
                 "door. No ornate ceiling, no crown moulding, no patterned wallpaper, no gold trim, "
                 "no tufted upholstery, no decorative clutter, no plants, no artwork, "
                 "no text, no letters, no numbers, no logos, no watermark.")
    # 平台专属后缀（如 Midjourney 的 --ar/--v/--q）追加在正文之后
    suffix = platform_cfg(platform).get("suffix", "")
    if suffix:
        lines.append("")
        lines.append(f"（追加后缀）{suffix.strip()}")
    return "\n".join(lines)


# ------------------------------------------------------------------ 预审包
def build_shots(infos, style, variations=1, pano=False):
    """把「房间 × 机位 × 风格变体」展开成镜头列表（dry-run / JSON 共用）。"""
    if variations > 1:
        variants = STYLE_VARIANTS[:variations]
    else:
        variants = [{"name": style, "zh": "", "clause": ""}]
    shots = []
    for info in infos:
        cams = PANO_DIRS if pano else [None]
        for cam in cams:
            for v in variants:
                if cam:
                    tag = f"{DIR_ZH[cam[0]]}墙机位"
                elif variations > 1:
                    tag = v["zh"] or v["name"]
                else:
                    tag = ""
                shots.append({
                    "info": info, "style": v["name"], "clause": v["clause"],
                    "camera": cam, "tag": tag, "variant_zh": v["zh"],
                })
    return shots


def render_dry_run(data, infos, style, platform, seed=None, variations=1, pano=False,
                   seed_explicit=False):
    """--dry-run：出图前预审包。不调用任何生图接口。"""
    cfg = platform_cfg(platform)
    if seed is None:
        seed = plan_seed(data)
    shots = build_shots(infos, style, variations, pano)
    chunks = ["# 出图前预审包（--dry-run，不调用生图）\n",
              "> **用途**：正式出图前，先在这里审阅。布局卡 + 提示词 + 负面词 + 参数，"
              "全部由平面图数据程序生成。",
              "> **顺序**：用户审阅通过 → 才逐房间出图。**预检有 ⚠️ 时不得出图。**",
              f"> **目标平台**：{cfg['label']}\n",
              "---\n"]

    # 0. 一致性预检
    probs = consistency_check(data, infos)
    chunks.append("## 0. 一致性预检\n")
    if probs:
        chunks.append(f"❌ **未通过，发现 {len(probs)} 项。补齐后才允许出图。**\n")
        chunks += [f"- ⚠️ {p}" for p in probs]
    else:
        chunks.append("✅ **通过**（关键家具朝向齐备、无同墙多门窗）")
    chunks.append("\n---\n")

    # 1. 交付顺序
    chunks.append("## 1. 交付顺序（固定规则）\n")
    chunks.append("**客餐厅 → 主卧 → 次卧 → 其他**（与主流设计工具一致，符合阅读习惯）。\n")
    chunks.append("本次实际顺序：\n")
    for i, info in enumerate(infos, 1):
        chunks.append(f"{i}. {info['room'].get('name', info['room']['id'])}"
                      f"（{info['room']['id']}，净 {info['net_w']:.0f}×{info['net_d']:.0f} mm）")
    mode = []
    if pano:
        mode.append(f"全景环拍：每间 {len(PANO_DIRS)} 个机位")
    if variations > 1:
        mode.append(f"风格变体：每镜 {variations} 版")
    if mode:
        chunks.append(f"\n> 本批镜头数：**{len(shots)}**（{'；'.join(mode)}）")
    chunks.append("\n---\n")

    # 2. 逐房间布局卡
    chunks.append("## 2. 逐房间布局卡\n")
    for i, info in enumerate(infos, 1):
        chunks.append(render_card(info, idx=i))
    chunks.append("---\n")

    # 3. 逐镜头提示词
    chunks.append("## 3. 逐房间提示词（逐字复制使用，禁止人工转写）\n")
    chunks.append("**十二段式结构**：1–3 场景/风格/机位 · 4–6 ★方位锁/数量锁/否定锁 · "
                  "7 ★平台适配（见第 4 节） · 8 ★seed（见第 4 节） · "
                  "9 ★动态缺失否定（按房逆向生成） · 10 材质光影 · "
                  "11 一致性分级 L1–L4 · 12 尺寸口径声明（见第 5 节）。\n")
    for i, info in enumerate(infos, 1):
        nm = info["room"].get("name", info["room"]["id"])
        room_shots = [s for s in shots if s["info"] is info]
        for s in room_shots:
            label = f"机位 {i}｜{nm}" + (f"｜{s['tag']}" if s["tag"] else "")
            chunks.append(f"### {label}\n")
            chunks.append("```text")
            chunks.append(render_prompt(info, style=s["style"], platform=platform,
                                        camera=s["camera"], variant_clause=s["clause"]))
            chunks.append("```\n")
    chunks.append("---\n")

    # 4. 平台负面词与参数 + 第 8 段 seed + 第 9 段说明
    chunks.append("## 4. 负面提示词与参数建议\n")
    chunks.append(render_negative_block(platform))
    chunks.append(f"### 第 8 段 · seed 记录与复现\n")
    chunks.append(f"| 项 | 值 |\n|---|---|")
    chunks.append(f"| 本批 seed | **{seed}** |")
    chunks.append(f"| 来源 | {'--seed 显式指定' if seed_explicit else '计划文件内容哈希（同户型重跑必得同值）'} |")
    chunks.append(f"| 用法 | 同一户型**所有镜头共用同一 seed**；改户型才换 seed |")
    chunks.append(f"| 复现 | 重跑 `make_room_prompts.py plan.json` 得同一 seed；"
                  f"出图参数记入 render.py 的 manifest |")
    chunks.append("")
    chunks.append("> 竞品靠同一 `designId` 保证跨房间一致，我方没有 designId，"
                  "用固定 seed 顶上：同 seed + 同风格库，色调与光比不会在房间间跳。\n")
    chunks.append("### 第 9 段 · 动态缺失负面词说明\n")
    chunks.append("本批每个镜头的 `ABSENCE LOCK` 段由该房间家具清单**逆向生成**"
                  "（如：平面图没有书桌 → 提示词自动写 `no desk, no office chair`；"
                  "没有浴缸 → `no bathtub`）。这是从「静态清单」升级为「按房生成」，"
                  "补模型最爱凭空补齐的件。\n")
    chunks.append("---\n")

    # 5. 出图 checklist + 第 12 段尺寸口径声明
    chunks.append("## 5. 出图前 Checklist\n")
    chunks.append("- [ ] 一致性预检 ✅ 通过（第 0 节无 ⚠️）")
    chunks.append("- [ ] 平面俯视图已生成并**交用户确认**（4.6.0 铁律：平面图未确认，一张效果图都不许出）")
    chunks.append("- [ ] 家具布局清单已与用户确认（4.7.0 P1-5：平面图确认后、效果图前的确认闸）")
    chunks.append("- [ ] 每间房的机位与朝向已与用户对齐")
    chunks.append("- [ ] 提示词已**逐字**取自第 3 节，未人工改写")
    chunks.append("- [ ] 负面词与参数已按目标平台取用（第 4 节）")
    chunks.append(f"- [ ] 出图 seed 固定为 **{seed}**，全批镜头一致")
    chunks.append("- [ ] 出图后每张过三查：结构查 / 清单查 / 朝向查")
    chunks.append("- [ ] 同一间最多重试 2 次，仍不一致则停止并如实标注（不得声称完全一致）")
    chunks.append("")
    chunks.append(f"**第 12 段 · 尺寸口径声明（交付层固定文案，随每批交付）**：")
    chunks.append(f"> {SIZE_DISCLAIMER}")
    chunks.append("")
    return "\n".join(chunks)


def render_prompts_json(data, infos, style, platform, seed=None, variations=1,
                        pano=False, src="", seed_explicit=False):
    """机器可读出口：供 scripts/render.py 直接消费出图。"""
    if seed is None:
        seed = plan_seed(data)
    cfg = platform_cfg(platform)
    shots = build_shots(infos, style, variations, pano)
    out = {
        "generated_by": "make_room_prompts.py v4.7.0",
        "source_plan": os.path.basename(src) if src else "",
        "platform": platform,
        "platform_label": cfg["label"],
        "seed": seed,
        "seed_source": "explicit" if seed_explicit else "plan-hash",
        "style": style,
        "variations": variations,
        "pano": pano,
        "size_disclaimer": SIZE_DISCLAIMER,
        "shots": [],
    }
    for s in shots:
        info = s["info"]
        nm = info["room"].get("name", info["room"]["id"])
        core = render_prompt(info, style=s["style"], platform="auto",
                             camera=s["camera"], variant_clause=s["clause"])
        suffix = cfg.get("suffix", "")
        out["shots"].append({
            "room": nm,
            "room_id": info["room"]["id"],
            "tag": s["tag"],
            "style": s["style"],
            "prompt": core,
            "prompt_with_suffix": (core + suffix) if suffix else core,
            "negative": cfg.get("negative"),
            "no_list": cfg.get("no_list"),
            "suffix": suffix,
            "seed": seed,
            "aspect": "16:9",
        })
    return json.dumps(out, ensure_ascii=False, indent=2)


def _furn_clause(f):
    """把一件家具转成一句方位锁定的英文。"""
    t = f["type"]
    size = f"{f['w']:.0f} by {f['h']:.0f} mm"
    ad = f["against"]
    dirs = " and ".join(DIR_EN[a] for a in ad) if ad else ""
    anchor = f"against the {dirs} wall" if ad else "standing free on the floor"

    if t == "bed":
        head = DIR_EN.get(f["head"], "")
        axis = "east-west" if f["axis"] == "x" else "north-south"
        if head:
            return (f"one double bed, {size}, running {axis} with its "
                    f"HEADBOARD against the {head} wall and its foot pointing "
                    f"toward the opposite wall")
        return f"one double bed, {size}, running {axis}, {anchor}"
    if t == "wardrobe":
        return (f"one floor-to-ceiling handleless built-in wardrobe, {size} in plan, "
                f"flush doors with shadow gaps, {anchor}{f.get('_short', '')}")
    if t == "nightstand":
        primary = DIR_EN.get(ad[0], "") if ad else ""
        tail = f"against the {primary} wall" if primary else "standing on the floor"
        return f"one small nightstand ONLY, {size}, {tail}"
    if t == "toilet":
        head = DIR_EN.get(f["head"], "")
        tail = f", water tank against the {head} wall so the bowl faces away from it" if head else f", {anchor}"
        return f"one FLOOR-STANDING toilet with visible full base{tail}"
    if t == "basin":
        return f"a vanity with an UNDERSMOUNT basin and a 15 mm thick quartz top, {size}, {anchor}"
    if t == "shower":
        return f"a frameless glass-partitioned shower zone, {size}, {anchor}"
    if t == "kitchen_counter":
        return f"a single run of base cabinets, {size} in plan, with a quartz top {anchor}"
    if t == "fridge":
        return f"one freestanding fridge, {size}, {anchor}"
    if t == "sofa":
        return f"one sofa, {size}, {anchor}"
    if t == "coffee_table":
        return f"one low coffee table, {size}, {anchor}"
    if t == "tv_cabinet":
        return f"one low TV console, {size}, {anchor}"
    if t == "dining_table":
        return f"one rectangular dining table, {size}, {anchor}"
    if t == "chair":
        return f"one chair, {size}, {anchor}"
    if t == "washing_machine":
        return f"one washing machine, {size}, {anchor}"
    if t == "plant":
        return f"one small potted plant, {size}, {anchor}"
    # 兜底：名称必须过 FURN_EN 映射 —— 中文漏进英文 prompt 会被模型渲染成乱码
    en_name = FURN_EN.get(f["name"], f["name"])
    return f"one {en_name}, {size}, {anchor}"


# ------------------------------------------------------------------ 预检
def consistency_check(data, infos):
    probs = []
    for info in infos:
        rn = info["room"].get("name", info["room"]["id"])
        for f in info["furniture"]:
            if f["type"] in ADHERE_REQUIRED and not f["against"]:
                probs.append(f"[{rn}] 「{f['name']}」不与任何墙贴合——提示词无法表达贴哪面墙，"
                             f"请补 `against` 或在平面图上贴墙布置")
            if f["type"] == "bed" and not f["head"]:
                probs.append(f"[{rn}] 「{f['name']}」未标注床头朝向（`head`）——"
                             f"床朝向是最易画反的项，必须显式给出 N/S/E/W")
            if f["type"] == "toilet" and not f["head"]:
                probs.append(f"[{rn}] 「{f['name']}」未标注水箱贴哪面墙（`head`）——"
                             f"马桶朝向必须显式给出")
        # 同墙多樘门窗
        cnt = {}
        for o in info["openings"]:
            cnt[o["dir"]] = cnt.get(o["dir"], 0) + 1
        for d, n in cnt.items():
            if n > 1:
                probs.append(f"[{rn}] {DIR_ZH[d]}墙有 {n} 樘门窗——模型易合并或漏画，"
                             f"建议拆分机位或明确其相对位置")
    return probs


def main():
    ap = argparse.ArgumentParser(description="从平面图 JSON 生成逐房间布局卡与提示词")
    ap.add_argument("json_path")
    ap.add_argument("--room", help="只处理指定房间 id")
    ap.add_argument("--prompt", metavar="ROOM_ID", help="只输出该房间的提示词")
    ap.add_argument("--check", action="store_true", help="只做一致性预检")
    ap.add_argument("--dry-run", action="store_true",
                    help="出图前预审包：预检+布局卡+提示词+负面词+参数，不调用生图")
    ap.add_argument("--platform", default="auto",
                    choices=list(PLATFORMS.keys()),
                    help="目标平台，决定负面词与参数（默认 auto=通用）")
    ap.add_argument("--style", default="minimalist", help="风格词（英文）；"
                    "--variations>1 时改从 STYLE_VARIANTS 取前 N 项")
    ap.add_argument("--seed", type=int, default=None,
                    help="固定 seed（第 8 段）。缺省由计划文件内容哈希生成，同户型必得同值")
    ap.add_argument("--variations", type=int, default=1, metavar="N",
                    help="同户型出 N 个风格版本对比（P1-3，1-5）")
    ap.add_argument("--pano", action="store_true",
                    help="每房间输出东南西北 4 个机位提示词（P1-4 漫游用）")
    ap.add_argument("--out-json", action="store_true",
                    help="输出机器可读 JSON（供 render.py 出图），优先于 --dry-run 的 md")
    ap.add_argument("-o", "--out", help="写入文件")
    args = ap.parse_args()

    if args.variations < 1 or args.variations > len(STYLE_VARIANTS):
        sys.exit(f"--variations 只支持 1-{len(STYLE_VARIANTS)}")

    with open(args.json_path, encoding="utf-8") as f:
        data = json.load(f)

    rooms = data["rooms"]
    if args.room:
        rooms = [r for r in rooms if r["id"] == args.room]
        if not rooms:
            sys.exit(f"找不到房间 {args.room}")
    infos = [describe_room(data, r) for r in rooms]

    # 交付排序：客餐厅 → 主卧 → 次卧 → 其他；同级按面积从大到小
    infos.sort(key=lambda i: (delivery_rank(i["room"].get("name", "")),
                              -(i["net_w"] * i["net_d"])))

    # 第 8 段 seed：显式指定优先，否则按计划内容哈希（同户型重跑必得同值）
    seed = args.seed if args.seed is not None else plan_seed(data)

    if args.check:
        probs = consistency_check(data, infos)
        if probs:
            print("一致性预检：发现 %d 项，出图前必须补齐——" % len(probs))
            for p in probs:
                print("  ⚠️ ", p)
            sys.exit(2)
        print("一致性预检：通过（关键家具朝向齐备、无同墙多门窗）")
        return

    if args.out_json:
        out = render_prompts_json(data, infos, args.style, args.platform,
                                  seed=seed, variations=args.variations,
                                  pano=args.pano, src=args.json_path,
                                  seed_explicit=args.seed is not None)
    elif args.dry_run:
        out = render_dry_run(data, infos, args.style, args.platform, seed=seed,
                             variations=args.variations, pano=args.pano,
                             seed_explicit=args.seed is not None)
    elif args.prompt:
        info = next((i for i in infos if i["room"]["id"] == args.prompt), None)
        if not info:
            sys.exit(f"找不到房间 {args.prompt}")
        shots = build_shots([info], args.style, args.variations, args.pano)
        blocks = []
        for s in shots:
            nm = info["room"].get("name", info["room"]["id"])
            head = nm + (f"｜{s['tag']}" if s["tag"] else "")
            blocks.append(f"### {head}\n```text\n" + render_prompt(
                info, style=s["style"], platform=args.platform,
                camera=s["camera"], variant_clause=s["clause"]) + "\n```")
        out = "\n\n".join(blocks)
    else:
        chunks = ["# 逐房间布局卡（由平面图数据自动导出，禁止手工改写）\n",
                  "> 本文件由 `make_room_prompts.py` 从布局 JSON 生成。",
                  "> **效果图提示词必须逐字取自本文件的「提示词」段，不得人工转写。**\n",
                  f"> 目标平台：{platform_cfg(args.platform)['label']}",
                  f"> 本批 seed：**{seed}**（第 8 段，全批镜头共用；改户型才换）\n"]
        probs = consistency_check(data, infos)
        if probs:
            chunks.append("## ⚠️ 一致性预检未通过（补齐后再出图）\n")
            chunks += [f"- {p}" for p in probs]
            chunks.append("")
        for i, info in enumerate(infos, 1):
            chunks.append(render_card(info, idx=i))
            if i == 1:
                chunks.append("**[8] 提示词（逐字使用）**\n")
                chunks.append("```text")
                chunks.append(render_prompt(info, style=args.style, platform=args.platform))
                chunks.append("```\n")
        out = "\n".join(chunks)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"已写入 {args.out}")
    else:
        print(out)


if __name__ == "__main__":
    main()
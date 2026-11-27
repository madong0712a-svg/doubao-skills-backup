#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""mep_calc.py — 从平面图 JSON 生成「水电施工参考」全套表格（v4.7.0 / P1-2）

为什么需要它
------------
竞品（home-design 等）把水电当卖点但用**硬编码模板**：换户型数字不改。
本脚本反过来：**平面图 JSON 是唯一事实源**——
  房间 polygon → 面积/周长/净尺寸/对角线
  家具 type   → 水电点位（sink/basin/toilet/shower/washing_machine……）
  墙厚        → 净边界（防水周长、配电箱到房距离）
手不碰数据，数字就不会飘。

输出（对齐 references/mep_spec.md §四，缺一不可）
  1. 回路划分表   2. 插座点位表   3. 开关点位表
  4. 给排水点表   5. 防水面积表   6. 材料清单   7. 施工说明
另附「待确认事项」：自动捞取 plan meta.pending_confirm 里与水电影有关的条目
（原图未标强弱电箱/给排水立管/层高等），**不静默跳过**。

口径边界（每份交付必带，写死在输出头部）
  本表为**设计参考口径**，用于方案沟通、预算估算与施工交底辅助；
  正式施工图须由持证设计单位出图，现场以实测与物业核定为准。
  电表容量、入户主线规格以电业局核定为准；给水主管径以市政接入为准。

用法
----
  python mep_calc.py plan.json                      # 全套表格（stdout）
  python mep_calc.py plan.json --panel-room 玄关     # 指定配电箱所在房间（id 或名）
  python mep_calc.py plan.json --water-room 厨房 --drain-room 卫生间
  python mep_calc.py plan.json --floor-height 2.8   # 层高（排水立管长度）
  python mep_calc.py plan.json -o mep.md            # 写入文件

规则与 references/mep_spec.md **一一对应**；改规则两处必须同步（规范 §五）。
工程量与造价口径（人工/主材价）不属本模块——要报价转造价流程。
"""
from __future__ import annotations

import argparse
import json
import math
import sys

# ============================================================ 常量区（改规则改这里）
# ---- 房型分类：命中即归类，与 make_room_prompts.py 的 ROOM_EN 口径一致
ROOM_CAT_KEYWORDS = [
    ("kitchen", ("厨房",)),
    ("bath", ("卫生间", "浴室", "洗手间")),
    ("balcony", ("阳台", "露台")),
    ("entry", ("玄关", "入户", "走廊", "过道")),
    ("study", ("书房",)),
    ("bedroom", ("主卧", "次卧", "卧室", "儿童房", "老人房")),
    ("living", ("客厅", "起居室", "客餐厅")),
    ("dining", ("餐厅", "饭厅")),
]
DEFAULT_CAT = "other"

# ---- 插座点位（JGJ 242 口径）。每个分类的点位清单 = 数量下限本身，
#      不再单列一张「下限表」，杜绝两处数字漂移。字段：位置/个数/高度mm/用途
SOCKET_POINTS = {
    "bedroom": [("床头两侧", 2, "700–1000", "手机充电/台灯（其中 1 个带 USB）"),
                ("书桌/梳妆区", 1, "1000–1100", "电脑/镜前灯")],
    "study": [("书桌台面", 2, "1000–1100", "电脑/台灯"),
              ("角落", 1, "300", "备用/吸尘器")],
    "living": [("电视墙", 2, "300–1100", "电视/机顶盒/路由"),
               ("沙发两侧", 2, "300", "落地灯/手机充电"),
               ("角落备用", 1, "300", "移动电器/吸尘器")],
    "dining": [("餐桌旁", 1, "300", "火锅/小家电"),
               ("餐边柜", 1, "1100", "热水壶/咖啡机")],
    "kitchen": [("台面", 2, "1100–1200", "小家电（避开灶台与水槽正上方）"),
                ("冰箱后", 1, "500", "冰箱"),
                ("油烟机", 1, "2200", "16A 专用，距台面 1.8m")],
    "bath": [("洗手台侧", 1, "1500", "防溅盒，吹风机/剃须刀")],
    "balcony": [("洗衣机位", 1, "1200", "防溅盒，洗衣机/吸尘器/晾衣机")],
    "entry": [("鞋柜区", 1, "300", "烘鞋/充电")],
    "other": [("通用", 2, "300", "按需")],
}
# 家具触发的插座增量：平面图里有这件家具 → 该房间按下表追加插座
EXTRA_SOCKET_TYPES = {"desk": 1, "dressing_table": 1, "treadmill": 1, "piano": 1,
                      "aquarium": 1, "dishwasher": 1, "dryer": 1, "massage_chair": 1}
EXTRA_SOCKET_DETAIL = {
    "desk": ("书桌处", "1000–1100", "台灯/电脑"),
    "dressing_table": ("梳妆台处", "1000–1100", "镜前灯/美容仪"),
    "treadmill": ("跑步机位", "300", "跑步机"),
    "piano": ("钢琴位", "300", "电钢琴/节拍器"),
    "aquarium": ("鱼缸位", "300", "增氧/加热棒"),
    "dishwasher": ("洗碗机位", "300", "洗碗机"),
    "dryer": ("烘干机位", "1200", "烘干机"),
    "massage_chair": ("按摩椅位", "300", "按摩椅"),
}

# ---- 回路划分（GB 50054 口径，mep_spec §2.1）
LIGHT_AREA_THRESHOLD = 90.0   # 建筑面积 > 90㎡ → 照明 2 路
LIGHT_ROOMS_THRESHOLD = 6     # 房间数 > 6     → 照明 2 路
SOCKET_PER_CIRCUIT_MAX = 10   # 每回路插座数上限
ROOMS_PER_CIRCUIT_MAX = 3     # 每回路房间数上限
AC_TYPES = {"air_conditioner", "ac", "split_ac", "ac_indoor"}
WATER_HEATER_TYPES = {"water_heater", "电热水器"}
WASHER_TYPES = {"washing_machine", "washer"}
DRYER_TYPES = {"dryer"}

# ---- 断路器整定（mep_spec §2.1 线径配套）
BREAKER = {
    "light": "1P C16",
    "socket": "1P C20 + RCD 30mA",
    "kitchen": "2P C25 + RCBO 30mA",
    "bath_heater": "2P C25 + RCBO 30mA",
    "ac": "2P C25 + RCBO 30mA",
    "washer": "1P C20 + RCD 30mA",
}

# ---- 电线长度估算（mep_spec §2.3）
WIRE_COIL = 1.4              # 绕线系数（含转角与上返）
PANEL_MARGIN_M = 0.05        # 配电箱内余量（spec：+50mm）
# 口径注：估算未含底盒预留（每盒约 100–150mm）与绕梁增量，按现场走线；
#         与正式算量差异 ±20% 内属正常。

# ---- 给排水点（mep_spec §3.1）。supply: 给水制式；drain: 是否有排水点
WATER_POINTS = {
    "sink":            {"zh": "水槽", "supply": "冷+热", "dn": "De20", "drain": "De50"},
    "basin":           {"zh": "洗手台", "supply": "冷+热", "dn": "De20", "drain": "De50"},
    "toilet":          {"zh": "马桶", "supply": "单冷", "dn": "De20", "drain": "De110"},
    "shower":          {"zh": "淋浴", "supply": "冷+热", "dn": "De20", "drain": "De50"},
    "washing_machine": {"zh": "洗衣机", "supply": "单冷", "dn": "De20", "drain": "De50"},
    "washer":          {"zh": "洗衣机", "supply": "单冷", "dn": "De20", "drain": "De50"},
    "dishwasher":      {"zh": "洗碗机", "supply": "单冷", "dn": "De20", "drain": "De50"},
    "dryer":           {"zh": "烘干机", "supply": "单冷（冷凝水）", "dn": "De20", "drain": "De50"},
    "faucet":          {"zh": "水龙头", "supply": "单冷", "dn": "De20", "drain": None},
    "tap":             {"zh": "水龙头", "supply": "单冷", "dn": "De20", "drain": None},
    "water_heater":    {"zh": "电热水器", "supply": "单冷（进水）", "dn": "De20", "drain": None},
}
# 给排水长度估算（mep_spec §3.3）：支管 = 点到水源/立管距离 × 1.2
PIPE_COIL = 1.2
MAIN_DN_IN = "De25"           # 入户给水主管
STACK_DEFAULT_H = 2.8         # 排水立管按层高计（常见住宅净层高口径，可 --floor-height 覆盖）

# ---- 防水（GB 55030 口径，mep_spec §3.2）
WATERPROOF_WALL_BATH = 1.8    # 卫生间墙面设防高度
WATERPROOF_WALL_SHOWER = 2.0  # 淋浴区墙面设防高度
WATERPROOF_WALL_KITCHEN = 0.3  # 厨房台面上返
WATERPROOF_WALL_BALCONY = 0.3  # 阳台上返
WATERPROOF_THRESHOLD = 0.3    # 卫生间门口外延
WATERPROOF_COAT_KG_PER_M2 = 2.2  # 涂料用量估算（两遍，一底一面）
BALCONY_WATER_TRIGGER = {"washing_machine", "washer", "faucet", "tap", "sink"}

# ---- 施工说明标准条款（GB 50303 / GB 50054 / GB 50015 / GB 55030 / GB 50327）
WORK_NOTES = [
    "强弱电分开：强电与弱电（网线/电视）平行间距 ≥300mm，交叉处加屏蔽或直角跨越；底盒不得同侧并贴。",
    "布线穿管：单管穿线截面总和 ≤ 管内截面 40%；禁止在承重梁/柱上凿深槽，梁上开孔须经结构确认。",
    "导线色标：相线 L 红/绿/黄，零线 N 淡蓝，地线 PE 黄绿双色；配电箱内回路标识与现场一致。",
    "绝缘电阻：插座与照明回路绝缘电阻 ≥0.5MΩ（500V 兆欧表），通电前必测。",
    "给水试验：试验压力为工作压力 1.5 倍且不小于 0.6MPa，稳压 1h，压降 ≤0.05MPa、各接口无渗漏为合格。",
    "排水坡度：De50 横管坡度 ≥2.5%，De110 ≥1.2%（GB 50015）；通球试验通畅。",
    "闭水试验：卫生间蓄水深度 20–30mm，闭水 ≥24h（建议 48h），楼下顶棚与墙角无渗漏为合格。",
    "防水基层：阴阳角做 R≥50mm 圆弧，管根/地漏周边附加层宽 ≥150mm；涂料两遍，第二遍与第一遍垂直。",
    "卫生间门槛：防水层门口外延 300mm 且门槛处做止水坎，防止水汽外渗（GB 55030）。",
    "插座防溅：卫生间/阳台/厨房湿区插座必须配防溅盒；卫生间插座回路独立设 RCD 30mA。",
    "空调专线：每台 ≥1.5P 空调独立回路 4mm²，不得与照明/插座共用；电加热器按大功率设备同样处理。",
    "底盒预埋：盒口与完成面齐平，偏差 ≤2mm；并列底盒间距 ≥10mm，保证面板安装。",
    "点位保护：水电完工后标识拍照留档（每处点位拍照），封槽前与业主确认无遗漏。",
    "燃气相关：燃气热水器点位与燃气管道间距 ≥300mm，燃气改管由燃气公司实施，水电班组不得动燃气。",
]
# 待确认事项的关键词（从 plan meta.pending_confirm 里捞与水电影有关的）
MEP_PENDING_KEYWORDS = ("电", "水", "防水", "给排", "管井", "立管", "烟道", "强弱电箱",
                        "层高", "梁位", "地漏", "冷热", "空调", "AC")

EXIT_OK = 0
EXIT_NO_CONFIG = 2      # 文件缺失/房间找不到（与 render.py 对齐）
EXIT_USAGE = 4          # 参数错误（与 render.py 的自定义 _Parser 对齐）


class _Parser(argparse.ArgumentParser):
    """argparse 默认用法错误退 2，与 EXIT_NO_CONFIG 撞码 —— 覆写退 4（对齐 render.py）。"""

    def error(self, message):
        sys.stderr.write("参数错误：%s\n" % message)
        sys.exit(EXIT_USAGE)


# ============================================================ 几何工具
# （与 make_room_prompts.py 的同名函数保持一致；两脚本各自独立运行，不互相 import）

def poly_bbox(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def poly_area(poly):
    """鞋带公式，mm² → ㎡（plan 单位 mm）。"""
    s = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0 / 1e6


def poly_perimeter(poly):
    """周长（m）。polygon 为墙中线，未扣洞口——估算口径见输出说明。"""
    tot = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        tot += math.hypot(x2 - x1, y2 - y1)
    return tot / 1000.0


def poly_centroid(poly):
    n = len(poly)
    cx = sum(p[0] for p in poly) / n
    cy = sum(p[1] for p in poly) / n
    return cx, cy


def room_sides(poly):
    x0, y0, x1, y1 = poly_bbox(poly)
    return {"N": y1, "S": y0, "E": x1, "W": x0}


def wall_of_room(walls, sides, bbox=None, tol=60):
    """把房间四条边匹配到 walls（按中心线坐标重合）。

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
    """按所属墙厚内缩得净边界（mm）。"""
    x0, y0, x1, y1 = poly_bbox(poly)
    for d, w in side_walls.items():
        if not w:
            continue
        t = w.get("thickness", 100) / 2.0
        if d == "N":
            y1 -= t
        elif d == "S":
            y0 += t
        elif d == "E":
            x1 -= t
        elif d == "W":
            x0 += t
    return x0, y0, x1, y1


def adhere_dirs(rect, nb, tol=120):
    """家具贴哪几面墙（mm 容差与 make_room_prompts.py 的 ADHERE_TOL 一致）。"""
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


# ============================================================ 房间加工
def classify_room(name):
    for cat, kws in ROOM_CAT_KEYWORDS:
        if any(k in name for k in kws):
            return cat
    return DEFAULT_CAT


def find_room(data, key):
    """按房间 id（R09）或名称子串（玄关）找房间；找不到返回 None。"""
    if not key:
        return None
    for r in data["rooms"]:
        if r["id"] == key:
            return r
    hits = [r for r in data["rooms"] if key in r.get("name", "")]
    return hits[0] if hits else None


def describe_room(data, room):
    """提取本模块需要的全部几何/家具事实（不依赖其他脚本）。"""
    walls = data["walls"]
    openings = data.get("openings", [])
    poly = room["polygon"]
    bbox = poly_bbox(poly)
    sides = room_sides(poly)
    side_walls = wall_of_room(walls, sides, bbox)
    nb = net_bounds(poly, side_walls)
    wall_dir = {v["id"]: k for k, v in side_walls.items() if v}

    doors = []
    for o in openings:
        d = wall_dir.get(o.get("wall"))
        if not d or o.get("type") not in ("door", "sliding_door"):
            continue
        cx, cy = o.get("center", [0, 0])
        half = o.get("width", 0) / 2.0
        if d in ("N", "S"):
            if not (nb[0] - half <= cx <= nb[2] + half):
                continue
        else:
            if not (nb[1] - half <= cy <= nb[3] + half):
                continue
        doors.append({"id": o["id"], "dir": d, "type": o["type"],
                      "width": o.get("width", 0)})

    furns = []
    for f in data.get("furniture", []):
        if f.get("room") != room["id"]:
            continue
        rect = f["rect"]
        furns.append({
            "id": f["id"], "name": f.get("name", f["id"]),
            "type": f.get("type", ""), "rect": rect,
            "cx": rect[0] + rect[2] / 2.0,
            "cy": rect[1] + rect[3] / 2.0,
            "against": adhere_dirs(rect, nb),
        })

    net_w, net_d = nb[2] - nb[0], nb[3] - nb[1]
    corners = [(nb[0], nb[1]), (nb[0], nb[3]), (nb[2], nb[1]), (nb[2], nb[3])]
    return {
        "room": room, "name": room.get("name", room["id"]),
        "cat": classify_room(room.get("name", "")),
        "area": poly_area(poly),
        "area_text": room.get("area_text", ""),
        "perimeter": poly_perimeter(poly),
        "net": nb, "net_w": net_w, "net_d": net_d,
        "diag": math.hypot(net_w, net_d),
        "corners": corners,
        "center": ((nb[0] + nb[2]) / 2.0, (nb[1] + nb[3]) / 2.0),
        "poly_rect": len(poly) <= 4,   # 仅矩形房间可按四边算防水周长
        "doors": doors, "furniture": furns,
    }


# ============================================================ 电路
def room_sockets(info):
    """房间插座点位清单：[{pos, n, h, use}]，含家具触发增量。"""
    pts = []
    raw = SOCKET_POINTS.get(info["cat"], SOCKET_POINTS["other"])
    if info["cat"] == "balcony":
        # 阳台点位按实际家具改标签：有洗衣机才叫洗衣机位，否则就是防溅备用位
        has_washer = any(f["type"] in WASHER_TYPES for f in info["furniture"])
        raw = [(("洗衣机位" if has_washer else "防溅备用位"), n, h, use)
               if pos == "洗衣机位" else (pos, n, h, use)
               for pos, n, h, use in raw]
    for pos, n, h, use in raw:
        pts.append({"pos": pos, "n": n, "h": h, "use": use})
    for f in info["furniture"]:
        if f["type"] in EXTRA_SOCKET_TYPES:
            pos, h, use = EXTRA_SOCKET_DETAIL[f["type"]]
            pts.append({"pos": f"{pos}（{f['name']}）", "n": EXTRA_SOCKET_TYPES[f["type"]],
                        "h": h, "use": use})
    return pts


def room_switches(info):
    """开关位：入口 1 位；卧室/客厅双控 +1。"""
    n = 2 if info["cat"] in ("bedroom", "living") else 1
    dual = info["cat"] in ("bedroom", "living")
    return n, dual


def circuit_length(infos, panel_center):
    """L = 1.4 ×(配电箱→最远用电点 + 房间对角线/2) + 0.05m（mep_spec §2.3）。

    「最远用电点」取成员房间净边界四角中离配电箱最远的那个（保守口径）。
    """
    best = None
    for info in infos:
        d = max(math.hypot(cx - panel_center[0], cy - panel_center[1])
                for cx, cy in info["corners"])
        if best is None or d > best[0]:
            best = (d, info)
    if best is None:
        return 0.0
    d, info = best
    return (WIRE_COIL * (d / 1000.0 + info["diag"] / 2000.0) + PANEL_MARGIN_M)


def build_circuits(infos, panel_center, flags):
    """生成回路列表。元素：{name, scope, wire, breaker, rooms:[info], length, kind}"""
    circuits = []
    by_cat = {}
    for i in infos:
        by_cat.setdefault(i["cat"], []).append(i)

    # 1) 照明：全屋 1–2 路（面积/房间数超限取 2，按与配电箱距离中位数切分）
    total_area = sum(i["area"] for i in infos)
    n_light = 2 if (total_area > LIGHT_AREA_THRESHOLD or
                    len(infos) > LIGHT_ROOMS_THRESHOLD) else 1
    if n_light == 2:
        ordered = sorted(infos, key=lambda i: math.hypot(
            i["center"][0] - panel_center[0], i["center"][1] - panel_center[1]))
        half = len(ordered) // 2
        groups = [ordered[:half], ordered[half:]]
    else:
        groups = [list(infos)]
    for gi, g in enumerate(groups, 1):
        if not g:
            continue
        circuits.append({
            "name": f"照明{'①②'[gi-1] if n_light == 2 else ''}",
            "scope": "、".join(i["name"] for i in g),
            "wire": "BV 1.5mm²", "breaker": BREAKER["light"],
            "rooms": g, "length": circuit_length(g, panel_center),
            "kind": "light",
        })

    # 2) 普通插座：排除厨房与卫生间（均独立回路，mep_spec §2.1），按交付顺序贪心装桶
    socket_rooms = [i for i in infos if i["cat"] not in ("kitchen", "bath")]
    order = {"living": 0, "dining": 1, "bedroom": 2, "study": 3, "bath": 4,
             "balcony": 5, "entry": 6, "other": 7}
    socket_rooms.sort(key=lambda i: (order.get(i["cat"], 9), -i["area"]))
    bucket, n_sock = [], 0
    idx = 0
    for info in socket_rooms:
        s = sum(p["n"] for p in room_sockets(info))
        if bucket and (n_sock + s > SOCKET_PER_CIRCUIT_MAX or
                       len(bucket) >= ROOMS_PER_CIRCUIT_MAX):
            idx += 1
            circuits.append({
                "name": f"普通插座{'①②③④'[idx-1]}",
                "scope": "、".join(b["name"] for b in bucket),
                "wire": "BV 2.5mm²", "breaker": BREAKER["socket"],
                "rooms": bucket, "length": circuit_length(bucket, panel_center),
                "kind": "socket",
            })
            bucket, n_sock = [], 0
        bucket.append(info)
        n_sock += s
    if bucket:
        idx += 1
        circuits.append({
            "name": f"普通插座{'①②③④'[idx-1]}",
            "scope": "、".join(b["name"] for b in bucket),
            "wire": "BV 2.5mm²", "breaker": BREAKER["socket"],
            "rooms": bucket, "length": circuit_length(bucket, panel_center),
            "kind": "socket",
        })

    # 3) 厨房独立回路（台面插座 + 冰箱 + 油烟机）
    for info in by_cat.get("kitchen", []):
        circuits.append({
            "name": f"厨房（{info['name']}）", "scope": info["name"],
            "wire": "BV 4mm²", "breaker": BREAKER["kitchen"],
            "rooms": [info], "length": circuit_length([info], panel_center),
            "kind": "kitchen",
        })

    # 4) 卫生间独立回路（含电热水器与洗手台插座，与普通插座分开；无热水器时同样独立）
    for info in by_cat.get("bath", []):
        has_heater = any(f["type"] in WATER_HEATER_TYPES for f in info["furniture"])
        circuits.append({
            "name": f"卫生间（{info['name']}）",
            "scope": info["name"] + ("（含电热水器）" if has_heater else ""),
            "wire": "BV 4mm²", "breaker": BREAKER["bath_heater"],
            "rooms": [info], "length": circuit_length([info], panel_center),
            "kind": "bath_heater",
        })
        if not has_heater:
            flags.append(f"⚠️ 「{info['name']}」家具清单未见电热水器（type=water_heater）："
                         "若装电热水器已含在本独立回路内；若装燃气热水器则本回路仅供插座，"
                         "燃气改管由燃气公司实施（见施工说明第 14 条）。")

    # 5) 洗衣机/烘干机独立回路
    washer_rooms = [i for i in infos
                    if any(f["type"] in WASHER_TYPES | DRYER_TYPES for f in i["furniture"])]
    for info in washer_rooms:
        circuits.append({
            "name": f"洗衣机/烘干机（{info['name']}）", "scope": info["name"],
            "wire": "BV 2.5mm²", "breaker": BREAKER["washer"],
            "rooms": [info], "length": circuit_length([info], panel_center),
            "kind": "washer",
        })

    # 6) 空调：每台独立回路（按家具 type 识别）
    ac_units = [(i, f) for i in infos for f in i["furniture"] if f["type"] in AC_TYPES]
    for info, f in ac_units:
        circuits.append({
            "name": f"空调（{f['name']}@{info['name']}）", "scope": info["name"],
            "wire": "BV 4mm²", "breaker": BREAKER["ac"],
            "rooms": [info], "length": circuit_length([info], panel_center),
            "kind": "ac",
        })
    if not ac_units:
        flags.append("⚠️ 平面图家具清单未见空调内机（type=air_conditioner/ac/split_ac）："
                     "若按 meta 预留的 AC 设备平台布置，每台 ≥1.5P 需独立回路（BV 4mm²）；"
                     "请补充家具后重跑，或由业主/设计确认空调形式（挂机/风管机/中央空调）。")
    return circuits


# ============================================================ 水路
def build_water(infos, water_center, drain_center, stack_h, flags):
    """给排水点 + 管长估算。返回 (points, supply_m, drain_m, main_m)。"""
    points = []
    for info in infos:
        for f in info["furniture"]:
            spec = WATER_POINTS.get(f["type"])
            if not spec:
                continue
            d_supply = math.hypot(f["cx"] - water_center[0], f["cy"] - water_center[1]) * PIPE_COIL / 1000.0
            n_supply = 2 if spec["supply"] == "冷+热" else 1
            drain_m = 0.0
            if spec["drain"]:
                drain_m = (math.hypot(f["cx"] - drain_center[0], f["cy"] - drain_center[1])
                           * PIPE_COIL / 1000.0)
            points.append({
                "room": info["name"], "name": f["name"], "zh": spec["zh"],
                "supply": spec["supply"], "dn": spec["dn"],
                "drain": spec["drain"] or "—",
                "supply_m": d_supply * n_supply,
                "drain_m": drain_m,
            })
    if not points:
        flags.append("⚠️ 全屋未识别到任何用水家具（sink/basin/toilet/shower/"
                     "washing_machine/faucet……）——水路表为空。请检查家具 type 词表。")
    supply_m = sum(p["supply_m"] for p in points)
    drain_m = sum(p["drain_m"] for p in points)
    # 入户给水主管 De25：水表（水源房间）→ 最远给水点
    main_m = 0.0
    if points:
        main_m = max(
            math.hypot(f["cx"] - water_center[0], f["cy"] - water_center[1]) * PIPE_COIL / 1000.0
            for info in infos for f in info["furniture"] if f["type"] in WATER_POINTS)
    return points, supply_m, drain_m, main_m


# ============================================================ 防水
def build_waterproof(infos):
    """返回 [{'room','cat','wall_h_note','wall_m2','ground_m2','thr_m2','total_m2','kg'}]"""
    out = []
    for info in infos:
        cat = info["cat"]
        if cat == "bath":
            # 淋浴间贴墙段按 2.0m，其余墙面 1.8m（按各边净长分别计）
            wall_m2, notes = 0.0, []
            seg = {"N": info["net_w"], "S": info["net_w"],
                   "E": info["net_d"], "W": info["net_d"]}
            shower_dirs = set()
            for f in info["furniture"]:
                if f["type"] == "shower":
                    shower_dirs.update(f["against"])
            if info["poly_rect"]:
                for d in ("N", "E", "S", "W"):
                    h = WATERPROOF_WALL_SHOWER if d in shower_dirs else WATERPROOF_WALL_BATH
                    wall_m2 += seg[d] / 1000.0 * h
                if shower_dirs:
                    notes.append("淋浴区贴墙段（%s）按 %.1fm，其余 %.1fm"
                                 % ("/".join({"N": "北", "S": "南", "E": "东", "W": "西"}[d]
                                             for d in sorted(shower_dirs)),
                                    WATERPROOF_WALL_SHOWER, WATERPROOF_WALL_BATH))
                else:
                    notes.append("未识别到淋浴间贴墙方位，全墙按 %.1fm" % WATERPROOF_WALL_BATH)
            else:
                wall_m2 = info["perimeter"] * WATERPROOF_WALL_BATH
                notes.append("非矩形房间，按周长 × %.1fm 统一估算" % WATERPROOF_WALL_BATH)
            thr = 0.0
            for d in info["doors"]:
                thr += d["width"] / 1000.0 * WATERPROOF_THRESHOLD
            notes.append("门口外延 300mm" if thr > 0 else "未识别到门洞（外延按 0，需现场确认）")
            ground = info["area"]
        elif cat == "kitchen":
            # 有台面的墙面上返 300mm；无橱柜数据时按全周长 × 0.3m（保守）
            counter_dirs = set()
            for f in info["furniture"]:
                if f["type"] == "kitchen_counter":
                    counter_dirs.update(f["against"])
            if counter_dirs and info["poly_rect"]:
                seg = {"N": info["net_w"], "S": info["net_w"],
                       "E": info["net_d"], "W": info["net_d"]}
                wall_m2 = sum(seg[d] / 1000.0 * WATERPROOF_WALL_KITCHEN for d in counter_dirs)
                notes = ["仅橱柜贴墙面（%s）上返 %.1fm"
                         % ("/".join({"N": "北", "S": "南", "E": "东", "W": "西"}[d]
                                     for d in sorted(counter_dirs)), WATERPROOF_WALL_KITCHEN)]
            else:
                wall_m2 = info["perimeter"] * WATERPROOF_WALL_KITCHEN
                notes = ["未识别到橱柜贴墙方位，按周长 × %.1fm 保守估算"
                         % WATERPROOF_WALL_KITCHEN]
            thr = 0.0
            has_drain = any(f["type"] in ("sink", "dishwasher") for f in info["furniture"])
            ground = info["area"] if has_drain else 0.0
            notes.append("地面全做（厨房有排水点）" if has_drain
                         else "厨房无排水点，地面按惯例仍需做防潮层（按项目要求）")
        elif cat == "balcony":
            trigger = any(f["type"] in BALCONY_WATER_TRIGGER for f in info["furniture"])
            wall_m2 = info["perimeter"] * WATERPROOF_WALL_BALCONY if trigger else 0.0
            ground = info["area"]
            thr = 0.0
            notes = (["有洗衣机/水龙头，墙面按 %.1fm" % WATERPROOF_WALL_BALCONY] if trigger
                     else ["无用水点，墙面防水按 0（仅地面）"])
        else:
            continue
        total = wall_m2 + ground + thr
        out.append({
            "room": info["name"], "cat": cat,
            "wall_note": "；".join(notes),
            "wall_m2": wall_m2, "ground_m2": ground, "thr_m2": thr,
            "total_m2": total, "kg": total * WATERPROOF_COAT_KG_PER_M2,
        })
    return out


# ============================================================ 渲染
def fmt_m(v):
    return f"{v:.1f}"


def render(data, infos, circuits, water_points, supply_m, drain_m, main_m,
           waterproof, flags, panel_room, water_room, drain_room, stack_h):
    L = []
    meta = data.get("meta", {})
    L.append("# 水电施工参考（由平面图 JSON 自动生成，禁止手工改写数字）\n")
    L.append(f"- 项目：{meta.get('project', '未命名')}")
    L.append(f"- 数据来源：`{meta.get('source_plan', 'plan JSON')}`（rooms/walls/openings/furniture）")
    L.append(f"- 配电箱预设房间：**{panel_room['name']}**；水表预设房间：**{water_room['name']}**；"
             f"排水立管预设房间：**{drain_room['name']}**；层高按 **{stack_h}m**")
    L.append(f"- 生成脚本：`scripts/mep_calc.py`（口径见 `references/mep_spec.md`）\n")
    L.append("> **边界声明**：本表为**设计参考口径**，用于前期方案沟通、预算估算与施工交底辅助；"
             "正式施工图须由持证设计单位出图，现场以实测与物业核定为准。"
             "电表容量、入户主线规格以电业局核定为准；给水主管径以市政接入为准。\n")

    # ---- 总览
    total_sock = sum(p["n"] for i in infos for p in room_sockets(i))
    total_sw = sum(room_switches(i)[0] for i in infos)
    total_wire = sum(c["length"] for c in circuits)
    L.append("## 总览\n")
    L.append("| 项 | 数量 |")
    L.append("|---|---|")
    L.append(f"| 回路总数 | **{len(circuits)}** 路 |")
    L.append(f"| 插座总数 | **{total_sock}** 个 |")
    L.append(f"| 开关总数 | **{total_sw}** 位（含双控） |")
    L.append(f"| 给水点 | {len(water_points)} 处 |")
    L.append(f"| 排水点 | {sum(1 for p in water_points if p['drain'] != '—')} 处 |")
    L.append(f"| 防水面积 | {sum(w['total_m2'] for w in waterproof):.1f} ㎡ |")
    L.append(f"| 电线合计 | {total_wire:.1f} m（不含入户主线） |")
    L.append("")

    # ---- 1 回路划分表
    L.append("## 1. 回路划分表\n")
    L.append("| 回路 | 供电范围 | 线径（BV 铜芯） | 断路器 | 估算长度(m) |")
    L.append("|---|---|---|---|---|")
    for c in circuits:
        L.append(f"| {c['name']} | {c['scope']} | {c['wire']} | {c['breaker']} | {fmt_m(c['length'])} |")
    L.append("| 入户主线 | 电表→配电箱 | 6–10mm²（预留） | 电业局核定 | — |")
    L.append("")
    L.append("> 估算口径 `L = 1.4 ×(配电箱→最远用电点 + 房间对角线÷2) + 0.05m`；"
             "未含底盒预留（每盒约 100–150mm）与绕梁增量，与正式算量差异 ±20% 内属正常。\n")

    # ---- 2 插座点位表
    L.append("## 2. 插座点位表\n")
    L.append("| 房间 | 点位位置 | 数量 | 安装高度(mm) | 用途 |")
    L.append("|---|---|---|---|---|")
    for info in infos:
        for p in room_sockets(info):
            L.append(f"| {info['name']} | {p['pos']} | {p['n']} | {p['h']} | {p['use']} |")
    L.append("")
    L.append("> 高位插座（床头/书桌/台面）避开门后开启区与家具背板；"
             "16A 空调插座需单独回路，不得与 10A 插座混接面板。\n")

    # ---- 3 开关点位表
    L.append("## 3. 开关点位表\n")
    L.append("| 房间 | 开关位 | 双控关系 | 备注 |")
    L.append("|---|---|---|---|")
    for info in infos:
        n, dual = room_switches(info)
        door = info["doors"][0] if info["doors"] else None
        at = (f"入口（{door['dir'] and {'N': '北', 'S': '南', 'E': '东', 'W': '西'}[door['dir']]}墙门侧）"
              if door else "入口（开放区，按动线就近）")
        if dual:
            rel = "入口 ↔ 床头/沙发侧"
            note = "双控，两侧各 1 位"
        else:
            rel, note = "—", "单控"
        L.append(f"| {info['name']} | {n} | {rel} | {at}；{note} |")
    L.append("")
    L.append("> 卫生间/阳台潮湿环境用防溅型开关面板；厨房建议留小厨宝/洗碗机专线位（见家具增量）。\n")

    # ---- 4 给排水点表
    L.append("## 4. 给排水点表\n")
    L.append("| 房间 | 点位 | 给水 | 给水管径 | 排水点径 | 给水支管估(m) | 排水横管估(m) |")
    L.append("|---|---|---|---|---|---|---|")
    for p in water_points:
        L.append(f"| {p['room']} | {p['name']} | {p['supply']} | {p['dn']} | {p['drain']} "
                 f"| {p['supply_m']:.1f} | {p['drain_m']:.1f} |")
    L.append("")
    L.append(f"- 入户给水主管 **{MAIN_DN_IN}**：约 {main_m:.1f} m（水表→最远用水点 × {PIPE_COIL}）")
    L.append(f"- 排水横管合计约 {drain_m:.1f} m；排水立管 1 根约 {stack_h} m（按层高，穿楼层按实际）")
    L.append(f"- 给水支管合计约 {supply_m:.1f} m（冷热双管按 2 根计）")
    L.append("> 坡度口径：De50 ≥2.5%、De110 ≥1.2%（GB 50015）；管径越大坡度越小。\n")

    # ---- 5 防水面积表
    L.append("## 5. 防水面积表\n")
    L.append("| 区域 | 墙面口径 | 墙面(㎡) | 地面(㎡) | 外延(㎡) | 合计(㎡) | 涂料估(kg) |")
    L.append("|---|---|---|---|---|---|---|")
    for w in waterproof:
        L.append(f"| {w['room']} | {w['wall_note']} | {w['wall_m2']:.1f} | {w['ground_m2']:.1f} "
                 f"| {w['thr_m2']:.1f} | {w['total_m2']:.1f} | {w['kg']:.1f} |")
    tot = sum(w["total_m2"] for w in waterproof)
    tot_kg = sum(w["kg"] for w in waterproof)
    L.append(f"| **合计** | — | {sum(w['wall_m2'] for w in waterproof):.1f} "
             f"| {sum(w['ground_m2'] for w in waterproof):.1f} "
             f"| {sum(w['thr_m2'] for w in waterproof):.1f} | **{tot:.1f}** | **{tot_kg:.1f}** |")
    L.append("")
    L.append(f"> 涂料按 {WATERPROOF_COAT_KG_PER_M2} kg/㎡（两遍，一底一面）估算；"
             "周长按墙中线未扣洞口（估算偏安全）；门口外延按门洞宽 × 0.3m。\n")

    # ---- 6 材料清单
    L.append("## 6. 材料清单（不含价格；造价口径转造价流程）\n")
    L.append("| 分类 | 材料/规格 | 数量 | 单位 | 备注 |")
    L.append("|---|---|---|---|---|")
    wire_sum = {}
    for c in circuits:
        wire_sum.setdefault(c["wire"], 0.0)
        wire_sum[c["wire"]] += c["length"]
    for k in sorted(wire_sum):
        rolls = math.ceil(wire_sum[k] / 100)
        L.append(f"| 电线 | {k} | {fmt_m(wire_sum[k])} | m | 按 100m/卷采购约 {rolls} 卷 |")
    L.append(f"| 线管 | SC20/JDG20 | {fmt_m(total_wire)} | m | 与同回路电线同管穿设 |")
    boxes = total_sock + total_sw + sum(1 for _ in infos)  # 插座+开关+灯位（每室 1 主灯位）
    L.append(f"| 底盒 | 86 型暗装 | {boxes} | 个 | 插座+开关+灯位 |")
    L.append(f"| 开关插座面板 | 10A/16A 按需 | {total_sock + total_sw} | 位 | 湿区配防溅盒 |")
    brk = {}
    for c in circuits:
        brk.setdefault(c["breaker"], 0)
        brk[c["breaker"]] += 1
    for k, v in sorted(brk.items()):
        L.append(f"| 断路器 | {k} | {v} | 个 | 配电箱内 |")
    L.append(f"| 给水管 | PPR {MAIN_DN_IN} | {fmt_m(main_m)} | m | 入户主管 |")
    L.append(f"| 给水管 | PPR De20 | {fmt_m(supply_m)} | m | 支管，冷热分色（红/蓝） |")
    L.append(f"| 排水管 | PVC De50 | {fmt_m(sum(p['drain_m'] for p in water_points if p['drain'] == 'De50'))} | m | 横管 |")
    d110 = sum(p["drain_m"] for p in water_points if p["drain"] == "De110")
    if d110 > 0:
        L.append(f"| 排水管 | PVC De110 | {fmt_m(d110)} | m | 马桶横管 |")
    L.append(f"| 排水立管 | PVC De110 | {fmt_m(stack_h)} | m | 穿楼层按实际层高 |")
    L.append(f"| 防水涂料 | 聚合物水泥基（两遍） | {tot_kg:.1f} | kg | 按 5kg/桶约 {math.ceil(tot_kg / 5)} 桶 |")
    n_cold_hot = sum(2 if p["supply"] == "冷+热" else 1 for p in water_points)
    L.append(f"| 角阀 | 球芯（冷/热分色） | {n_cold_hot} | 个 | 每个给水点 1 个（冷热点 2 个） |")
    n_hose = sum(1 for p in water_points if p["zh"] in ("洗衣机", "马桶", "洗手台"))
    L.append(f"| 软管 | 304 编织软管 | {n_hose} | 根 | 洗衣机/马桶/洗手台 |")
    n_trap = sum(1 for p in water_points if p["drain"] != "—")
    L.append(f"| 地漏 | 防臭地漏 | {n_trap} | 个 | 洗衣机位用专用地漏 |")
    L.append("")

    # ---- 7 施工说明
    L.append("## 7. 施工说明（标准条款）\n")
    for i, note in enumerate(WORK_NOTES, 1):
        L.append(f"{i}. {note}")
    L.append("")

    # ---- 待确认事项
    L.append("## 待确认事项（不静默跳过）\n")
    if flags:
        for f in flags:
            L.append(f"- {f}")
    pending = [p for p in meta.get("pending_confirm", []) if any(k in p for k in MEP_PENDING_KEYWORDS)]
    if pending:
        L.append("- 来自 plan meta.pending_confirm（与本模块相关）：")
        for p in pending:
            L.append(f"  - {p}")
    if not flags and not pending:
        L.append("- 无。")
    L.append("")
    L.append("---")
    L.append("> 规则变动须同步 `references/mep_spec.md` 与本脚本常量区（规范 §五）。")
    return "\n".join(L)


# ============================================================ 主流程
def main():
    ap = _Parser(description="从平面图 JSON 生成水电施工参考（回路/点位/工程量/防水）")
    ap.add_argument("json_path", help="平面图 plan JSON 路径")
    ap.add_argument("--panel-room", default=None,
                    help="配电箱所在房间（id 如 R09 或名称子串如 玄关）；"
                         "缺省按 玄关→入户→走廊→过道→最小房间 推定")
    ap.add_argument("--water-room", default=None,
                    help="水表/给水水源所在房间；缺省按 厨房→餐厅→卫生间→首房间 推定")
    ap.add_argument("--drain-room", default=None,
                    help="排水立管所在房间；缺省按 卫生间→厨房 推定")
    ap.add_argument("--floor-height", type=float, default=STACK_DEFAULT_H,
                    help=f"层高 m（排水立管长度，默认 {STACK_DEFAULT_H}）")
    ap.add_argument("-o", "--out", help="写入文件（缺省打印 stdout）")
    args = ap.parse_args()

    try:
        with open(args.json_path, encoding="utf-8") as f:
            data = json.load(f)
    except OSError as e:
        sys.stderr.write("打不开 plan JSON：%s\n" % e)
        sys.exit(EXIT_NO_CONFIG)

    for key in ("rooms", "walls"):
        if key not in data:
            sys.stderr.write("plan JSON 缺少必需字段：%s\n" % key)
            sys.exit(EXIT_NO_CONFIG)

    infos = [describe_room(data, r) for r in data["rooms"]]

    # 配电箱房间
    panel_room = (find_room(data, args.panel_room) if args.panel_room else None)
    if args.panel_room and not panel_room:
        sys.stderr.write("找不到配电箱房间：%s（按 id 或名称子串匹配）\n" % args.panel_room)
        sys.exit(EXIT_NO_CONFIG)
    if not panel_room:
        for key in ("玄关", "入户", "走廊", "过道"):
            panel_room = find_room(data, key)
            if panel_room:
                break
    if not panel_room:
        panel_room = min(data["rooms"], key=lambda r: abs(
            (max(p[0] for p in r["polygon"]) - min(p[0] for p in r["polygon"])) *
            (max(p[1] for p in r["polygon"]) - min(p[1] for p in r["polygon"]))))
    panel_info = describe_room(data, panel_room)

    # 水源/立管房间
    def pick(keys):
        for k in keys:
            r = find_room(data, k)
            if r:
                return r
        return data["rooms"][0]

    water_room = (find_room(data, args.water_room) if args.water_room else None)
    if args.water_room and not water_room:
        sys.stderr.write("找不到水源房间：%s\n" % args.water_room)
        sys.exit(EXIT_NO_CONFIG)
    if not water_room:
        water_room = pick(("厨房", "餐厅", "卫生间"))
    drain_room = (find_room(data, args.drain_room) if args.drain_room else None)
    if args.drain_room and not drain_room:
        sys.stderr.write("找不到排水立管房间：%s\n" % args.drain_room)
        sys.exit(EXIT_NO_CONFIG)
    if not drain_room:
        drain_room = pick(("卫生间", "厨房"))
    water_info = describe_room(data, water_room)
    drain_info = describe_room(data, drain_room)

    flags = []
    pending_text = "；".join(data.get("meta", {}).get("pending_confirm", []))
    if not args.panel_room:
        flags.append(f"配电箱预设于「{panel_room['name']}」（缺省推定）——"
                     "原图未标注强弱电箱位置，须以现场/物业核定为准")
    if not args.water_room:
        flags.append(f"水表预设于「{water_room['name']}」（缺省推定）——"
                     "原图未标注给水立管/水表位置，须以现场核定为准")
    if not args.drain_room:
        flags.append(f"排水立管预设于「{drain_room['name']}」（缺省推定）——"
                     "原图未标注排水立管位置，须以现场核定为准")
    if "层高" not in pending_text:
        flags.append(f"层高按默认 {args.floor_height}m 计（--floor-height 可覆盖）——"
                     "plan meta 未提层高，排水立管长度按实际调整")

    circuits = build_circuits(infos, panel_info["center"], flags)
    water_points, supply_m, drain_m, main_m = build_water(
        infos, water_info["center"], drain_info["center"], args.floor_height, flags)
    waterproof = build_waterproof(infos)

    out = render(data, infos, circuits, water_points, supply_m, drain_m, main_m,
                 waterproof, flags, panel_room, water_room, drain_room, args.floor_height)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out)
        print("已写入 %s" % args.out)
    else:
        print(out)


if __name__ == "__main__":
    main()

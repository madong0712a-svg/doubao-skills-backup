# -*- coding: utf-8 -*-
"""
draw_floorplan.py — 2D 平面俯视图（线稿风格）绘图引擎（v4.5.0）
=====================================================

输入：户型结构化数据 JSON（schema 见 templates/floorplan_layout_data.md）
输出：单张高清平面图 PNG（默认 200 dpi，可配 300 dpi）+ 自检报告

设计原则（不可协商）：
  1. 严格按 JSON 数据绘制 —— 墙体、承重墙、门窗洞口位置与尺寸零改动
  2. 家具按真实比例摆放，脚本内置自检十一项：门扇扫掠区遮挡 / 通道净宽 / 家具嵌墙 /
     尺寸线避让 / 家具越界 / 门窗挂接 / 单位与标注一致性 / 标注落点归属 /
     标注文字互相遮挡 / 房间名与开间标注压墙 / 尺寸线防交叉与穿字
  3. 尺寸标注由数据显式驱动（dimensions 数组），标注线与图元重叠时给出 warning
  4. 线稿风格：白底黑线，仅房间淡填充区分，无渲染无透视无渐变
  5. 单张成图：构图完整（指北针 + 比例尺 + 图题栏），可直接作为后续效果图渲染的布局依据
  6. v4.3 强制输出：本图为效果图的强制伴生交付物；单位声明（meta.unit: mm/m）必须
     合法并在图题栏标明；墙体厚度用 kind=wall 标注；报告附 room_dimensions 供
     「平面图 ↔ 效果图」同源对照
  7. v4.3.1 面积口径正名：rooms 多边形为墙中线模型，图面自动标注为"中线面积"，
     图题栏面积行自适应——用户提供 meta.total_area 才标"建筑面积（用户提供）"，
     否则标"房间面积合计（墙中线）"；净面积/建筑面积不得用中线面积冒充
  8. v4.3.2 窄房间标注自适应：房间标注支持可选覆盖字段 name_pos / area_text /
     area_pos / area_fs（缺省行为与 v4.3.1 完全一致）——走廊、阳台等窄房间可
     缩短或移位面积标注，防止文字溢出压盖墙体；房间名不得被家具/标注/线条压盖
  9. v4.3.3 标注落点归属自检 + 分步计时：第 8 项自检「标注落点归属」强制
     ①家具名称标注落点不得跨出所属房间；②房间名/面积文字不得被家具图块
     压盖或越出房间——这两类是七项时代的目视盲区（F20/F25 返工源），
     现由脚本兜底；主流程分步输出 prepare/render/selfcheck 计时与图元计数，
     便于量化定位耗时瓶颈
  10. v4.4.0 通俗图标版式 + 尺寸压字（参照市面常规户型图）：
     家具由白底线框升级为浅灰填充剪影；家具/家电尺寸数值直接压在对应
     图元上或紧邻位置（排版自适应：一行→两行→窄高旋转→缩字号→紧贴
     下方→显式 offset 兜底），不再用引线拉到图外——省去逐个人工核算
     offset 的返工；房间名支持可选 pinyin 字段（中文名下方小字读音，
     缺省行为不变）；避坑判定不受图标简化影响（落地马桶/台下盆等口径不变）
  11. v4.5.0 中文统一 + 标注分层配色 + 文字防互撞（用户实测反馈修订）：
     ① 房间名称统一中文——拼音仅当 meta.show_pinyin 显式为 true 时显示，
        默认关闭（中文图面不出现拼音或中英混排）；
     ② 尺寸标注按层分色（总尺寸链藏青 / 房间开间深灰 / 门窗亮蓝 /
        墙厚赭棕 / 通道青绿 / 家具压字墨灰），窗洞图元改亮蓝与深灰墙体
        明确区分，门扇与门弧改赭棕——语义一致（图元与其标注同族）、
        整体协调、层次分明；
     ③ 新增第 9/10 项自检——渲染端每个文字入 _TEXT_LOG，自检端做
        两两碰撞检测（同组两行压字豁免）与房间名/开间标注压墙检测，
        文字必须完整、互不遮挡、不压墙线；这是第 8 项只管"在哪个房间"
        的盲区（历史返工：房间开间标注压门洞标注、窗洞标注压总尺寸数字）
  12. v4.5.0 CAD 制图标准（用户 CAD 标注规范要求，与第 11 条同版落地）：
     ① 起止符号统一 45° 中粗斜短划线（_tick，建筑制图标准，替代实心箭头）；
     ② 总尺寸排与细部排间距 CHAIN_TOTAL_GAP=260mm（≥2×字高，防挤排）；
     ③ 标注文字高度全图统一 DIM_FS=6pt（细部/总尺寸/门窗/墙厚/通道一致）；
     ④ 尺寸标注独立成层（zorder 7~9），单位与精度全图一致；
     ⑤ 新增第 11 项自检「尺寸线防交叉与穿字」——不同 group 尺寸线两两
        求交判 FAIL；细部排/总排/走廊线穿过任何文字框判 FAIL（墙厚引线
        按设计豁免；数字压自有线同组豁免）——对应 CAD 规范"禁止尺寸线、
        尺寸界线相互交叉或穿过其他标注"；
     ⑥ 第 8 项落点自检加严：房间名/面积文字框与家具轮廓重叠同样判 FAIL
        （"标注不得遮挡图形轮廓和构件"）

单位约定（v4.3）：JSON 内部坐标值一律毫米整数；meta.unit 仅决定图面显示单位
（mm 显示整数毫米，m 显示米、最多两位小数），显示层换算，自检阈值恒为 mm。

用法：
  python draw_floorplan.py data.json -o out.png [--dpi 300] [--report report.json] [--title 图名]
"""

import argparse
import json
import math
import os
import re
import sys
import time
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon, Circle, Ellipse, Arc
from matplotlib.lines import Line2D
import matplotlib.font_manager as fm

# --------------------------------------------------------------------------
# 常量
# --------------------------------------------------------------------------

CHECK_TOL_WALL = 0.5           # 家具嵌入墙体判定阈值（mm）：净距 < -0.5 判 FAIL
DOOR_CLEAR_DEPTH = 900.0       # 门扇扫掠半径（标准门宽）
WINDOW_CLEAR_DEPTH = 600.0     # 预留：窗前方净距（高柜贴窗提示用）
MIN_CORRIDOR = 600.0           # 通道净宽下限（通用家庭）
MIN_CORRIDOR_ELDER = 900.0     # 通道净宽下限（老人同住）
ATTACH_TOL = 150.0             # 家具间距小于此值视为贴邻组合（桌椅/洁具贴台），不判通道

# 高柜清单（贴窗/贴门时触发遮挡告警的家具类型）
TALL_FURNITURE = {"wardrobe", "shoe_cabinet", "bookshelf", "kitchen_counter", "cabinet", "fridge"}

# 墙体角色 → 填充色 / 线宽（v4.4.0 对齐市面户型图：墙体统一深灰填充）
WALL_STYLE = {
    "exterior":    {"fc": "#333333", "lw": 1.0},
    "loadbearing": {"fc": "#1f1f1f", "lw": 1.4},
    "interior":    {"fc": "#7a7a7a", "lw": 0.8},
}

# 家具类型 → 中文默认名（JSON 未给 name 时兜底）
FURNITURE_DEFAULT_NAME = {
    "bed": "床", "sofa": "沙发", "coffee_table": "茶几", "tv_stand": "电视柜",
    "dining_table": "餐桌", "chair": "椅", "wardrobe": "衣柜", "cabinet": "柜",
    "shoe_cabinet": "鞋柜", "kitchen_counter": "橱柜", "fridge": "冰箱",
    "sink": "水槽", "toilet": "马桶", "bathroom_sink": "洗手台", "shower": "淋浴",
    "bathtub": "浴缸", "washing_machine": "洗衣机", "desk": "书桌",
    "bookshelf": "书柜", "nightstand": "床头柜", "plant": "绿植", "rug": "地毯",
}

ROOM_FILL = "#f5f5f5"          # 房间底色（极淡，仅区分空间）
ROOM_EDGE = "#999999"
FURNITURE_EDGE = "#222222"
FURNITURE_FC = "#d9d9d9"       # 家具填充：浅灰剪影（v4.4.0 通俗图标风，原纯白）
ICON_FC = "#bcbcbc"            # 图标细节填充（枕头/靠背/台面等，深于家具底）

# v4.5.0 标注分层配色（白底低饱和稳重色系；语义一致：图元与其标注同族）
DIM_COLORS = {
    "chain":     "#1f4e79",   # 总尺寸链（第一层）：藏青——最外层、最稳重
    "room":      "#333333",   # 房间开间进深（第二层）：深灰
    "opening":   "#1f6fb2",   # 门窗洞口（第三层）：亮蓝——与窗洞图元同族
    "wall":      "#8a5a2b",   # 墙体厚度：赭棕——与门扇/门弧同族
    "corridor":  "#1f7a6d",   # 通道净宽：青绿
    "furniture": "#2b2b2b",   # 家具压字（第四层）：墨灰
}
DIM_COLOR = DIM_COLORS["chain"]   # 兼容旧引用的默认色（=总尺寸链藏青）
WINDOW_COLOR = "#1f6fb2"      # 窗洞图元：亮蓝（与深灰墙体明确区分，v4.5.0）
DOOR_COLOR = "#8a5a2b"        # 门扇/门弧/铰点：赭棕（v4.5.0）
LABEL_COLOR = "#111111"       # 房间名：近黑
AREA_COLOR = "#555555"        # 面积文字：深灰
PINYIN_COLOR = "#777777"      # 拼音小字（仅 meta.show_pinyin=true 时显示）

# v4.5.0 CAD 制图标准常量（用户 CAD 标注规范要求）：
# ① 总尺寸排与细部排间距：平行尺寸线间距 ≥ 2×字高（6pt 字估算高 204mm）→ 取 260mm
CHAIN_TOTAL_GAP = 260.0
# ② 起止符号：45° 中粗斜短划线（建筑制图标准，替代实心箭头），半长 90mm（全长 180mm）
TICK_LEN = 90.0
# ③ 标注文字高度全图统一 6pt（细部/总尺寸/门窗/墙厚/通道一致）
DIM_FS = 6.0

# v4.5.1 P1 画布预算常量（替代 bbox_inches='tight'，实测 savefig 491→280ms，-43%）：
# ④ 文字外扩余量：文字锚点在数据坐标、渲染向外扩。实测 A4 户型 tight bbox
#    比数据范围每边大 ~227mm（6pt 字 + 白底衬底），取 300 留 33% 余量。
CANVAS_PAD = 300.0
# ⑤ 出图像素密度（px/mm）：标定自 v4.5.0 现状 tight 输出
#    （画布宽 = W+2*PAD = 18862mm 应映射到 1586px → 1586/18862 ≈ 0.0841），
#    使新输出与现状尺寸一致；小户型画布保底 1400px（render_figure 内）。
TARGET_PX_PER_MM = 0.0841

# v4.5.0 文字日志：渲染端每个文字入册，自检端做两两碰撞/压墙检测
# （图上怎么画、自检怎么查，逐字一致——延续 v4.3.3/v4.4.0 原则）
_TEXT_LOG = []


def reset_text_log():
    _TEXT_LOG.clear()


def log_text(kind, text, x, y, fs, rot=0, group=None, anchor="c"):
    """文字入册：按 anchor/rot 换算几何中心，记录保守包围盒（mm）。

    rot=0  时 anchor c/b/t/l/r 对应 matplotlib ha/va；
    rot=90 时 anchor l（ha=left，文字自锚点向上伸）/ r（ha=right，向下伸）。
    包围盒宽/高取保守偏大估值（全角 fs×28mm、半角 fs×14mm、行高 fs×34mm），
    宁可误判不可漏判——自检 9/10/11 项与渲染端共用同一份日志。
    """
    w, h = _est_text_w(text, fs), fs * 34.0     # w=文字长, h=文字高
    if rot:
        # 旋转 90°：文字沿 y 向延伸，x 向只占文字高
        cy = y + w / 2.0 if anchor == "l" else (y - w / 2.0 if anchor == "r" else y)
        cx = x
        bbox = (cx - h / 2.0, cy - w / 2.0, cx + h / 2.0, cy + w / 2.0)
    else:
        cy = y + h / 2.0 if anchor == "b" else (y - h / 2.0 if anchor == "t" else y)
        cx = x + w / 2.0 if anchor == "l" else (x - w / 2.0 if anchor == "r" else x)
        bbox = (cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0)
    _TEXT_LOG.append({"kind": kind, "text": text, "fs": fs, "rot": rot,
                      "group": group, "bbox": bbox})


# --------------------------------------------------------------------------
# 工具函数
# --------------------------------------------------------------------------

def setup_chinese_font():
    """自适应中文字体；找不到时返回 None（调用方降级英文标签并告警）。"""
    preferred = [
        "microsoft yahei", "msyh", "simhei", "simsun",
        "noto sans cjk sc", "noto sans sc", "source han sans sc",
        "pingfang sc", "heiti sc", "wenquanyi micro hei",
    ]
    installed = {f.name.lower() for f in fm.fontManager.ttflist}
    for name in preferred:
        if name in installed:
            plt.rcParams["font.family"] = [name, "sans-serif"]
            plt.rcParams["axes.unicode_minus"] = False
            return name
    for path in [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyh.ttf",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
    ]:
        try:
            fm.fontManager.addfont(path)
            fname = fm.FontProperties(fname=path).get_name()
            plt.rcParams["font.family"] = [fname, "sans-serif"]
            plt.rcParams["axes.unicode_minus"] = False
            return fname
        except Exception:
            continue
    return None


def rot_point(px, py, cx, cy, deg):
    """绕 (cx, cy) 旋转 deg 度。"""
    a = math.radians(deg)
    dx, dy = px - cx, py - cy
    return (cx + dx * math.cos(a) - dy * math.sin(a),
            cy + dx * math.sin(a) + dy * math.cos(a))


def poly_rotated(rect, rot=0.0):
    """rect 绕自身中心旋转 rot 度后的多边形。"""
    x, y, w, h = rect
    cx, cy = x + w / 2.0, y + h / 2.0
    pts = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]
    if rot:
        pts = [list(rot_point(px, py, cx, cy, rot)) for px, py in pts]
    return pts


def poly_bounds(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def seg_point_distance(p1, p2, pt):
    """点 pt 到线段 p1-p2 的距离。"""
    x1, y1 = p1
    x2, y2 = p2
    px, py = pt
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L2))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def rect_overlap_area(a, b):
    """两轴对齐矩形重叠面积。"""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ox = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    oy = max(0.0, min(ay2, by2) - max(ay1, by1))
    return ox * oy


def point_in_poly(pt, poly):
    """射线法判断点是否在多边形内。"""
    x, y = pt
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and \
           (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def polygon_area(poly):
    s = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return s / 2.0


def fmt_mm(v, unit="mm"):
    """按图面声明单位格式化尺寸数值（内部坐标恒为 mm，仅在显示层换算）。"""
    if unit == "m":
        s = f"{v / 1000.0:.2f}".rstrip("0").rstrip(".")
        return s if s else "0"
    return str(int(round(v)))


def seg_seg_intersect(a1, a2, b1, b2):
    """两线段是否相交（含端点接触）。"""
    def cross(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
    d1 = cross(b1, b2, a1)
    d2 = cross(b1, b2, a2)
    d3 = cross(a1, a2, b1)
    d4 = cross(a1, a2, b2)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def seg_rect_intersect(p1, p2, rect):
    """线段与轴对齐矩形是否相交（含端点）。"""
    x1, y1, x2, y2 = rect
    for p in (p1, p2):
        if x1 <= p[0] <= x2 and y1 <= p[1] <= y2:
            return True
    edges = [((x1, y1), (x2, y1)), ((x2, y1), (x2, y2)),
             ((x2, y2), (x1, y2)), ((x1, y2), (x1, y1))]
    for e1, e2 in edges:
        if seg_seg_intersect(p1, p2, e1, e2):
            return True
    return False


# --------------------------------------------------------------------------
# 数据加载
# --------------------------------------------------------------------------

def load_plan(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for key in ("walls", "rooms"):
        if key not in data or not isinstance(data[key], list):
            raise ValueError(f"JSON 缺少必需字段或类型错误: {key}")
    data.setdefault("openings", [])
    data.setdefault("furniture", [])
    data.setdefault("dimensions", [])
    data.setdefault("meta", {})
    data["meta"].setdefault("unit", "mm")
    if data["meta"]["unit"] not in ("mm", "m"):
        raise ValueError(
            "meta.unit 只支持 'mm' / 'm'；JSON 坐标值一律为毫米整数，"
            "unit 仅决定图面显示单位（显示层换算）")
    return data


def get_furniture_poly(f):
    """取家具多边形（支持 rect+rot 或显式 polygon）。"""
    if "polygon" in f:
        return [list(p) for p in f["polygon"]]
    rect = f.get("rect")
    if rect:
        return poly_rotated(rect, f.get("rot", 0.0))
    raise ValueError(f"家具 {f.get('id')} 缺少 rect 或 polygon")


def wall_by_id(data):
    return {w["id"]: w for w in data["walls"] if "id" in w}


def wall_frame(w):
    """墙 → (p1, p2, L, 单位向量 u, 法向 n, 半墙厚 ht)。"""
    x1, y1 = w["p1"]
    x2, y2 = w["p2"]
    L = math.hypot(x2 - x1, y2 - y1)
    if L == 0:
        return None
    ux, uy = (x2 - x1) / L, (y2 - y1) / L
    return (x1, y1), (x2, y2), L, (ux, uy), (-uy, ux), w.get("thickness", 200) / 2.0


def opening_frame(w, op):
    """门窗 → (断口起点 a, 断口终点 b, 法向 n)。"""
    (x1, y1), (x2, y2), L, u, n, ht = wall_frame(w)
    cx, cy = op["center"]
    t = ((cx - x1) * u[0] + (cy - y1) * u[1])
    a = (x1 + u[0] * (t - op["width"] / 2.0), y1 + u[1] * (t - op["width"] / 2.0))
    b = (x1 + u[0] * (t + op["width"] / 2.0), y1 + u[1] * (t + op["width"] / 2.0))
    return a, b, n, u


# --------------------------------------------------------------------------
# 绘制：房间
# --------------------------------------------------------------------------

def show_pinyin_enabled(data):
    """拼音总开关（v4.5.0）：仅 meta.show_pinyin 显式为 true 时显示。
    默认关闭——房间名称统一中文，图面不出现拼音或中英混排。"""
    return bool(data.get("meta", {}).get("show_pinyin", False))


def draw_rooms(ax, data):
    pinyin_on = show_pinyin_enabled(data)
    for r in data["rooms"]:
        poly = r["polygon"]
        ax.add_patch(Polygon(poly, closed=True, facecolor=ROOM_FILL,
                             edgecolor=ROOM_EDGE, linewidth=0.8, zorder=1))
        area_m2 = abs(polygon_area(poly)) / 1e6
        cx = sum(p[0] for p in poly) / len(poly)
        cy = sum(p[1] for p in poly) / len(poly)
        name = r.get("name", r.get("id", ""))
        pinyin = r.get("pinyin") if pinyin_on else None
        name_pos = r.get("name_pos")
        nx, ny = name_pos if name_pos else (cx, cy)
        ax.text(nx, ny, name, ha="center", va="center", fontsize=9,
                color=LABEL_COLOR, zorder=6, fontweight="bold")
        log_text("room_name", name, nx, ny, 9)
        if pinyin:
            ax.text(nx, ny - 190, pinyin, ha="center", va="center",
                    fontsize=5.5, color=PINYIN_COLOR, zorder=6)
            log_text("pinyin", pinyin, nx, ny - 190, 5.5)
        area_text = r.get("area_text", f"中线面积 {area_m2:.1f}㎡")
        if area_text:
            area_pos = r.get("area_pos")
            # v4.5.0：房名(fs9 半高153)与面积(fs6.5 半高110.5)所需最小间距 263.5mm，
            # 旧缺省 260 天生互撞 → 统一放大到 320（CAD 平行间距 ≥2×字高）
            ax_, ay_ = area_pos if area_pos else (nx, ny - (430 if pinyin else 320))
            ax.text(ax_, ay_, area_text, ha="center", va="center",
                    fontsize=r.get("area_fs", 6.5), color=AREA_COLOR, zorder=6)
            log_text("area", area_text, ax_, ay_, r.get("area_fs", 6.5))


# --------------------------------------------------------------------------
# 绘制：墙体（含门窗断口）
# --------------------------------------------------------------------------

def wall_openings(data):
    """wall_id -> [(start_t, end_t, opening)]，t 为沿墙参数 0~1。"""
    result = {}
    walls = wall_by_id(data)
    for op in data["openings"]:
        w = walls.get(op.get("wall"))
        if not w:
            continue
        fr = wall_frame(w)
        if not fr:
            continue
        (x1, y1), (x2, y2), L, u, n, ht = fr
        cx, cy = op["center"]
        t = ((cx - x1) * u[0] + (cy - y1) * u[1])
        half = (op["width"] / 2.0) / L
        result.setdefault(w["id"], []).append(
            (max(0.0, t - half), min(1.0, t + half), op))
    return result


def draw_walls(ax, data):
    op_map = wall_openings(data)
    for w in data["walls"]:
        role = w.get("role", "interior")
        style = WALL_STYLE.get(role, WALL_STYLE["interior"])
        fr = wall_frame(w)
        if not fr:
            continue
        (x1, y1), (x2, y2), L, u, n, ht = fr
        segs = [(0.0, 1.0)]
        for s, e, op in op_map.get(w["id"], []):
            new_segs = []
            for a, b in segs:
                if e <= a or s >= b:
                    new_segs.append((a, b))
                    continue
                if a < s:
                    new_segs.append((a, s))
                if e < b:
                    new_segs.append((e, b))
            segs = new_segs
        for a, b in segs:
            ax_ = x1 + u[0] * L * a
            ay_ = y1 + u[1] * L * a
            bx_ = x1 + u[0] * L * b
            by_ = y1 + u[1] * L * b
            poly = [
                [ax_ + n[0] * ht, ay_ + n[1] * ht],
                [bx_ + n[0] * ht, by_ + n[1] * ht],
                [bx_ - n[0] * ht, by_ - n[1] * ht],
                [ax_ - n[0] * ht, ay_ - n[1] * ht],
            ]
            ax.add_patch(Polygon(poly, closed=True, facecolor=style["fc"],
                                 edgecolor="black", linewidth=style["lw"], zorder=3))
            if role == "loadbearing":
                ax.add_patch(Polygon(poly, closed=True, facecolor="none",
                                     edgecolor=style["fc"], linewidth=0.0,
                                     hatch="////", zorder=3))


# --------------------------------------------------------------------------
# 绘制：门窗
# --------------------------------------------------------------------------

def draw_openings(ax, data):
    walls = wall_by_id(data)
    for op in data["openings"]:
        w = walls.get(op.get("wall"))
        if not w:
            continue
        fr = wall_frame(w)
        if not fr:
            continue
        (x1, y1), (x2, y2), L, u, n, ht = fr
        a, b, nn, uu = opening_frame(w, op)
        otype = op.get("type", "door")

        if otype == "door":
            hinge_side = op.get("hinge_side", "p1")
            open_side = op.get("open_side", 1)
            hinge = a if hinge_side == "p1" else b
            tip = (hinge[0] + nn[0] * op["width"] * open_side,
                   hinge[1] + nn[1] * op["width"] * open_side)
            ax.add_line(Line2D([hinge[0], tip[0]], [hinge[1], tip[1]],
                               color=DOOR_COLOR, lw=1.0, zorder=4))
            free_ang = 0.0 if hinge_side == "p1" else 180.0
            tip_ang = 90.0 if open_side > 0 else 270.0
            theta1, theta2 = min(free_ang, tip_ang), max(free_ang, tip_ang)
            ax.add_patch(Arc(hinge, 2 * op["width"], 2 * op["width"],
                             angle=math.degrees(math.atan2(uu[1], uu[0])),
                             theta1=theta1, theta2=theta2,
                             color=DOOR_COLOR, lw=0.7, ls=(0, (3, 2)), zorder=4))
            ax.plot([hinge[0]], [hinge[1]], marker="o", ms=2.2, color=DOOR_COLOR, zorder=5)

        elif otype == "window":
            for k, off in enumerate((-0.35, 0.0, 0.35)):
                o = off * op.get("thickness", 100)
                pa = (a[0] + nn[0] * o, a[1] + nn[1] * o)
                pb = (b[0] + nn[0] * o, b[1] + nn[1] * o)
                ax.add_line(Line2D([pa[0], pb[0]], [pa[1], pb[1]],
                                   color=WINDOW_COLOR, lw=1.6 if k == 1 else 0.7, zorder=4))

        elif otype == "sliding_door":
            for off in (-0.28, 0.28):
                o = off * op.get("thickness", 100)
                pa = (a[0] + nn[0] * o, a[1] + nn[1] * o)
                pb = (b[0] + nn[0] * o, b[1] + nn[1] * o)
                ax.add_line(Line2D([pa[0], pb[0]], [pa[1], pb[1]],
                                   color=WINDOW_COLOR, lw=1.1, zorder=4))
            mx = (a[0] + b[0]) / 2.0
            my = (a[1] + b[1]) / 2.0
            ax.annotate("", xy=(mx + uu[0] * op["width"] * 0.3, my + uu[1] * op["width"] * 0.3),
                        xytext=(mx - uu[0] * op["width"] * 0.3, my - uu[1] * op["width"] * 0.3),
                        arrowprops=dict(arrowstyle="<->", lw=0.6, color=WINDOW_COLOR), zorder=5)

        elif otype == "bay_window":
            for off in (-0.3, 0.3):
                o = off * op.get("thickness", 100)
                pa = (a[0] + nn[0] * o, a[1] + nn[1] * o)
                pb = (b[0] + nn[0] * o, b[1] + nn[1] * o)
                ax.add_line(Line2D([pa[0], pb[0]], [pa[1], pb[1]],
                                   color=WINDOW_COLOR, lw=0.7, zorder=4))
            depth = op.get("depth", 600)
            out_side = op.get("out_side", 1)
            c1 = (a[0] + nn[0] * out_side * depth, a[1] + nn[1] * out_side * depth)
            c2 = (b[0] + nn[0] * out_side * depth, b[1] + nn[1] * out_side * depth)
            ax.add_patch(Polygon([list(a), list(c1), list(c2), list(b)], closed=True,
                                 facecolor="none", edgecolor=WINDOW_COLOR, lw=0.7,
                                 ls=(0, (4, 2)), zorder=4))


# --------------------------------------------------------------------------
# 绘制：家具
# --------------------------------------------------------------------------

def draw_furniture_item(ax, f, suppress_name=False):
    poly = get_furniture_poly(f)
    ftype = f.get("type", "default")
    name = f.get("name", FURNITURE_DEFAULT_NAME.get(ftype, ftype))

    ax.add_patch(Polygon(poly, closed=True, facecolor=FURNITURE_FC,
                         edgecolor=FURNITURE_EDGE, linewidth=0.9, zorder=5))

    cx = sum(p[0] for p in poly) / len(poly)
    cy = sum(p[1] for p in poly) / len(poly)
    x1, y1, x2, y2 = poly_bounds(poly)
    w, h = x2 - x1, y2 - y1

    if ftype == "bed":
        ax.add_patch(Rectangle((x1, y2 - 0.16 * h), w, 0.16 * h,
                               facecolor=ICON_FC, edgecolor=FURNITURE_EDGE, lw=0.5, zorder=6))
        for px in (x1 + 0.12 * w, x1 + 0.56 * w):
            ax.add_patch(Rectangle((px, y2 - 0.34 * h), 0.32 * w, 0.18 * h,
                                   facecolor="none", edgecolor=FURNITURE_EDGE, lw=0.5, zorder=6))
    elif ftype == "sofa":
        ax.add_patch(Rectangle((x1, y2 - 0.22 * h), w, 0.22 * h,
                               facecolor=ICON_FC, edgecolor=FURNITURE_EDGE, lw=0.5, zorder=6))
        for px in (x1, x2 - 0.14 * w):
            ax.add_patch(Rectangle((px, y1), 0.14 * w, h,
                                   facecolor=ICON_FC, edgecolor=FURNITURE_EDGE, lw=0.5, zorder=6))
    elif ftype == "chair":
        ax.add_patch(Rectangle((x1, y2 - 0.25 * h), w, 0.25 * h,
                               facecolor=ICON_FC, edgecolor=FURNITURE_EDGE, lw=0.5, zorder=6))
    elif ftype in ("coffee_table", "dining_table"):
        ax.add_patch(Ellipse((cx, cy), 0.8 * w, 0.7 * h,
                             facecolor="none", edgecolor=FURNITURE_EDGE, lw=0.5, zorder=6))
    elif ftype in ("wardrobe", "cabinet", "shoe_cabinet", "bookshelf"):
        ax.add_line(Line2D([cx, cx], [y1, y2], color=FURNITURE_EDGE, lw=0.5, zorder=6))
        if ftype == "bookshelf":
            for k in (1, 2, 3):
                yy = y1 + k * h / 4.0
                ax.add_line(Line2D([x1, x2], [yy, yy], color=FURNITURE_EDGE, lw=0.4, zorder=6))
        if ftype == "shoe_cabinet":
            for k in range(3):
                yy = y1 + (k + 0.5) * h / 3.0
                ax.add_line(Line2D([x1, x2], [yy, yy], color="#888888", lw=0.4, zorder=6))
    elif ftype == "kitchen_counter":
        ax.add_line(Line2D([x1, x2], [cy, cy], color=FURNITURE_EDGE, lw=0.5, zorder=6))
    elif ftype == "fridge":
        ax.add_line(Line2D([x1, x2], [y1, y2], color=FURNITURE_EDGE, lw=0.5, zorder=6))
        ax.plot([cx], [cy], marker="o", ms=2.5, mfc="none", mec=FURNITURE_EDGE, zorder=6)
    elif ftype == "sink":
        ax.add_patch(Rectangle((x1 + 0.15 * w, y1 + 0.25 * h), 0.7 * w, 0.5 * h,
                               facecolor="none", edgecolor=FURNITURE_EDGE, lw=0.6, zorder=6))
        ax.plot([x1 + 0.88 * w], [y1 + 0.15 * h], marker="o", ms=1.8,
                color=FURNITURE_EDGE, zorder=6)
    elif ftype == "toilet":
        ax.add_patch(Rectangle((x1 + 0.15 * w, y2 - 0.28 * h), 0.7 * w, 0.28 * h,
                               facecolor=ICON_FC, edgecolor=FURNITURE_EDGE, lw=0.6, zorder=6))
        ax.add_patch(Ellipse((cx, cy - 0.08 * h), 0.62 * w, 0.55 * h,
                             facecolor="none", edgecolor=FURNITURE_EDGE, lw=0.6, zorder=6))
    elif ftype == "bathroom_sink":
        ax.add_patch(Ellipse((cx, cy), 0.66 * w, 0.6 * h,
                             facecolor="none", edgecolor=FURNITURE_EDGE, lw=0.6, zorder=6))
        ax.add_line(Line2D([cx, cx], [cy, y2], color=FURNITURE_EDGE, lw=0.6, zorder=6))
    elif ftype == "shower":
        for p1, p2 in (((x1, y1), (x2, y2)), ((x1, y2), (x2, y1))):
            ax.add_line(Line2D([p1[0], p2[0]], [p1[1], p2[1]],
                               color="#888888", lw=0.4, ls=(0, (3, 2)), zorder=6))
        ax.plot([cx], [cy], marker="o", ms=2, mfc="none", mec="#888888", zorder=6)
    elif ftype == "bathtub":
        ax.add_patch(Rectangle((x1 + 0.12 * w, y1 + 0.15 * h), 0.76 * w, 0.7 * h,
                               facecolor="none", edgecolor=FURNITURE_EDGE, lw=0.6, zorder=6))
    elif ftype == "washing_machine":
        ax.add_patch(Circle((cx, cy), 0.22 * min(w, h),
                            facecolor="none", edgecolor=FURNITURE_EDGE, lw=0.6, zorder=6))
    elif ftype == "desk":
        ax.add_line(Line2D([x1, x2], [cy, cy], color=FURNITURE_EDGE, lw=0.4, zorder=6))
    elif ftype == "rug":
        if ax.patches:
            ax.patches[-1].set_linestyle((0, (4, 3)))
            ax.patches[-1].set_facecolor("none")
    elif ftype == "plant":
        ax.add_patch(Circle((cx, cy), 0.3 * min(w, h),
                            facecolor="none", edgecolor=FURNITURE_EDGE, lw=0.5, zorder=6))
        for ang in (45, 135, 225, 315):
            ar = math.radians(ang)
            r = 0.34 * min(w, h)
            ax.add_line(Line2D([cx, cx + r * math.cos(ar)], [cy, cy + r * math.sin(ar)],
                               color=FURNITURE_EDGE, lw=0.4, zorder=6))

    if not suppress_name:
        fs = 5.5 if min(w, h) >= 400 else 4.5
        ax.text(cx, cy - 0.28 * h if ftype in ("bed", "sofa") else cy, name,
                ha="center", va="center", fontsize=fs, color="#333333", zorder=7)


def draw_furniture(ax, data):
    # v4.4.0：已有尺寸压字的家具，图块内自动名让位（名称随压字上图，避免同块双名）
    suppress = set()
    for d in data["dimensions"]:
        if d.get("kind") == "furniture" and d.get("ref"):
            f = next((x for x in data["furniture"] if x.get("id") == d["ref"]), None)
            if f:
                suppress.add(d["ref"])
    for f in data["furniture"]:
        draw_furniture_item(ax, f, suppress_name=f.get("id") in suppress)


# --------------------------------------------------------------------------
# 家具尺寸压字排版（v4.4.0）—— 渲染端与自检端共用，落点公式逐字一致
# --------------------------------------------------------------------------

def _est_text_w(text, fs):
    """估算文字宽度（mm）：全角按 fs×28mm、半角按 fs×14mm（保守偏大，防漏判碰撞）。"""
    return sum(fs * (28.0 if ord(ch) > 0x2E80 else 14.0) for ch in text)


def _label_bbox(pos, text, fs, rot=0):
    """文字包围盒（mm）：(x1, y1, x2, y2)，供压字避让判定。"""
    tw, th = _est_text_w(text, fs), fs * 34.0
    if rot:
        tw, th = th, tw
    return (pos[0] - tw / 2.0, pos[1] - th / 2.0,
            pos[0] + tw / 2.0, pos[1] + th / 2.0)


def _room_label_boxes(data):
    """房间名/拼音/面积文字的包围盒列表（压字紧贴避让用；公式与 draw_rooms 一致）。
    v4.5.0：入参改为整份 data（拼音受 meta.show_pinyin 总开关控制）。"""
    boxes = []
    pinyin_on = show_pinyin_enabled(data)
    for r in data["rooms"]:
        poly = r["polygon"]
        cx = sum(p[0] for p in poly) / len(poly)
        cy = sum(p[1] for p in poly) / len(poly)
        name_pos = r.get("name_pos")
        nx, ny = name_pos if name_pos else (cx, cy)
        boxes.append(_label_bbox((nx, ny), r.get("name", ""), 9))
        pinyin = r.get("pinyin") if pinyin_on else None
        if pinyin:
            boxes.append(_label_bbox((nx, ny - 190), pinyin, 5.5))
        area_text = r.get("area_text")
        if area_text is None:
            area_text = f"中线面积 {abs(polygon_area(poly)) / 1e6:.1f}㎡"
        if area_text:
            area_pos = r.get("area_pos")
            # 与 draw_rooms 逐字一致：缺省间距 320（房名↔面积防互撞，v4.5.0）
            ax_, ay_ = area_pos if area_pos else (nx, ny - (430 if pinyin else 320))
            boxes.append(_label_bbox((ax_, ay_), area_text, 6.5))
    return boxes


def furniture_dim_text(f, d, unit="mm"):
    """家具尺寸标注文字：显式 text 优先；缺省自动生成「名称 宽×深」
    （名称随压字上图，图块内自动名同步让位，避免同块双名）。"""
    if d.get("text"):
        return d["text"]
    bx1, by1, bx2, by2 = poly_bounds(get_furniture_poly(f))
    name = f.get("name", FURNITURE_DEFAULT_NAME.get(f.get("type", ""), f.get("type", "")))
    return f"{name} {fmt_mm(bx2 - bx1, unit)}×{fmt_mm(by2 - by1, unit)}"


def furniture_label_layout(f, d, text, furn, data):
    """家具尺寸压字排版（不再用引线拉到图外）。返回 dict：
    mode(inline/inline2/below/offset) / pos / fs / rot / lines / text。
    顺序：显式 offset → 一行 → 两行 → 窄高旋转(≥4.5pt) → 紧贴下方
    （避让其他家具与房间名，且须不越出所属房间）→ 旋转兜底(4.0pt)
    → 默认 offset 兜底。落点仍受第 8 项自检房间归属约束。
    v4.5.0：入参 rooms 改为整份 data（拼音受 meta.show_pinyin 控制，
    避让盒与渲染端逐字一致）。"""
    poly = get_furniture_poly(f)
    x1, y1, x2, y2 = poly_bounds(poly)
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    w, h = x2 - x1, y2 - y1
    rooms = data["rooms"]

    off = d.get("offset")
    if off:
        return {"mode": "offset", "pos": (cx + off[0], cy + off[1]),
                "fs": 5.5, "rot": 0, "text": text}

    name_part, _, dim_part = text.rpartition(" ")
    room = None
    rid = f.get("room")
    if rid:
        room = next((r for r in rooms if r.get("id") == rid), None)

    def _in_room(pt):
        return room is None or point_in_poly(pt, room["polygon"])

    for fs in (5.5, 5.0, 4.5):
        # 1) 一行压在图元内
        if _est_text_w(text, fs) <= 0.92 * w and fs * 34.0 <= 0.85 * h:
            return {"mode": "inline", "pos": (cx, cy), "fs": fs, "rot": 0, "text": text}
        # 2) 两行压在图元内（名称行 + 尺寸行）
        if name_part and dim_part and \
                max(_est_text_w(name_part, fs), _est_text_w(dim_part, fs)) <= 0.92 * w and \
                2 * fs * 34.0 <= 0.85 * h:
            return {"mode": "inline2", "pos": (cx, cy), "fs": fs, "rot": 0,
                    "lines": [name_part, dim_part], "text": text}
        # 3) 窄高图元：旋转 90° 压在图元内
        if h > w and _est_text_w(text, fs) <= 0.92 * h and fs * 34.0 <= 0.85 * w:
            return {"mode": "inline", "pos": (cx, cy), "fs": fs, "rot": 90, "text": text}

    # 4) 紧贴图元下方（避让其他家具 rect 与房间名/面积文字，且不越出所属房间）
    avoid = [poly_bounds(get_furniture_poly(g)) for g in furn if g is not f]
    avoid += _room_label_boxes(data)
    for step in range(6):
        ty = y1 - 150 - step * 60
        bb = _label_bbox((cx, ty), text, 5.0)
        if _in_room((cx, ty)) and all(rect_overlap_area(bb, a) <= 1.0 for a in avoid):
            return {"mode": "below", "pos": (cx, ty), "fs": 5.0, "rot": 0, "text": text}

    # 5) 旋转兜底（4.0pt）
    if h > w and _est_text_w(text, 4.0) <= 0.92 * h and 4.0 * 34.0 <= 0.85 * w:
        return {"mode": "inline", "pos": (cx, cy), "fs": 4.0, "rot": 90, "text": text}

    # 6) 默认 offset 兜底（旧公式）；落点由第 8 项自检验证
    return {"mode": "offset", "pos": (cx + 0.45 * w + 350, cy + 0.45 * h + 350),
            "fs": 5.5, "rot": 0, "text": text}


# --------------------------------------------------------------------------
# 绘制：尺寸标注
# --------------------------------------------------------------------------

def draw_dimensions(ax, data, ext_gap=6.0, ext_ext=10.0, unit="mm"):
    """按 dimensions 数组绘制标注（v4.5.0 分层配色 + 文字入册 + CAD 制图标准）。
    返回 (dim_segments, warnings)；dim_segments 元素为 (p1, p2, kind, group) 四元组，
    kind ∈ chain-seg / chain-total / corridor / wall-leader，group 用于自检 11 项
    「尺寸线防交叉与穿字」的同组豁免判定。
    """
    warnings = []
    dim_lines = []

    for d in data["dimensions"]:
        kind = d.get("kind")
        c = DIM_COLORS.get(kind, DIM_COLOR)   # 分层配色：图元与其标注同族

        if kind == "chain":
            axis = d.get("axis", "x")
            at = d["at"]
            side = d.get("side", "below" if axis == "x" else "left")
            off = d.get("offset", 14.0)
            total_from = d["from"]
            total_to = d["to"]
            segs = d["segments"]
            show_total = d.get("show_total", True)
            gid = f"chain-{id(d)}"

            if axis == "x":
                y_dim = at - off if side == "below" else at + off
                xs = sorted({v for s in segs for v in s} | {total_from, total_to})
                for x in xs:
                    ax.add_line(Line2D(
                        [x, x],
                        [at - ext_gap if side == "below" else at + ext_gap,
                         y_dim + (ext_ext if side == "below" else -ext_ext)],
                        color=c, lw=0.5, zorder=8))
                for a, b in segs:
                    ax.add_line(Line2D([a, b], [y_dim, y_dim], color=c, lw=0.7, zorder=8))
                    _tick(ax, a, y_dim, color=c)
                    _tick(ax, b, y_dim, color=c)
                    txt = fmt_mm(b - a, unit)
                    ty = y_dim + (4 if side == "below" else -4)
                    ax.text((a + b) / 2.0, ty, txt, ha="center",
                            va="bottom" if side == "below" else "top",
                            fontsize=DIM_FS, color=c, zorder=9)
                    log_text("chain", txt, (a + b) / 2.0, ty, DIM_FS,
                             anchor="b" if side == "below" else "t", group=gid)
                    dim_lines.append(((a, y_dim), (b, y_dim), "chain-seg", gid))
                if show_total:
                    # 总尺寸排外移：与细部排间距 ≥2×字高（CAD 标准，防挤排/穿字）
                    y_tot = y_dim + (-CHAIN_TOTAL_GAP if side == "below" else CHAIN_TOTAL_GAP)
                    ax.add_line(Line2D([total_from, total_to], [y_tot, y_tot],
                                       color=c, lw=0.9, zorder=8))
                    _tick(ax, total_from, y_tot, color=c)
                    _tick(ax, total_to, y_tot, color=c)
                    txt = fmt_mm(total_to - total_from, unit)
                    ty = y_tot + (4 if side == "below" else -4)
                    ax.text((total_from + total_to) / 2.0, ty, txt, ha="center",
                            va="bottom" if side == "below" else "top",
                            fontsize=DIM_FS, color=c, zorder=9)
                    log_text("chain", txt, (total_from + total_to) / 2.0, ty, DIM_FS,
                             anchor="b" if side == "below" else "t", group=gid)
                    dim_lines.append(((total_from, y_tot), (total_to, y_tot),
                                      "chain-total", gid))
            else:
                x_dim = at - off if side == "left" else at + off
                ys = sorted({v for s in segs for v in s} | {total_from, total_to})
                for y in ys:
                    ax.add_line(Line2D(
                        [at - ext_gap if side == "left" else at + ext_gap,
                         x_dim + (ext_ext if side == "left" else -ext_ext)],
                        [y, y], color=c, lw=0.5, zorder=8))
                for a, b in segs:
                    ax.add_line(Line2D([x_dim, x_dim], [a, b], color=c, lw=0.7, zorder=8))
                    _tick(ax, x_dim, a, color=c)
                    _tick(ax, x_dim, b, color=c)
                    txt = fmt_mm(b - a, unit)
                    tx = x_dim + (-4 if side == "left" else 4)
                    ax.text(tx, (a + b) / 2.0, txt,
                            ha="right" if side == "left" else "left",
                            va="center", fontsize=DIM_FS, color=c, zorder=9,
                            rotation=90)
                    log_text("chain", txt, tx, (a + b) / 2.0, DIM_FS, rot=90,
                             anchor="r" if side == "left" else "l", group=gid)
                    dim_lines.append(((x_dim, a), (x_dim, b), "chain-seg", gid))
                if show_total:
                    # 总尺寸排外移：与细部排间距 ≥2×字高（CAD 标准，防挤排/穿字）
                    x_tot = x_dim + (-CHAIN_TOTAL_GAP if side == "left" else CHAIN_TOTAL_GAP)
                    ax.add_line(Line2D([x_tot, x_tot], [total_from, total_to],
                                       color=c, lw=0.9, zorder=8))
                    _tick(ax, x_tot, total_from, color=c)
                    _tick(ax, x_tot, total_to, color=c)
                    txt = fmt_mm(total_to - total_from, unit)
                    tx = x_tot + (-4 if side == "left" else 4)
                    ax.text(tx, (total_from + total_to) / 2.0, txt,
                            ha="right" if side == "left" else "left",
                            va="center", fontsize=DIM_FS, color=c, zorder=9,
                            rotation=90)
                    log_text("chain", txt, tx, (total_from + total_to) / 2.0, DIM_FS,
                             rot=90, anchor="r" if side == "left" else "l", group=gid)
                    dim_lines.append(((x_tot, total_from), (x_tot, total_to),
                                      "chain-total", gid))

        elif kind == "room":
            room = next((r for r in data["rooms"] if r.get("id") == d.get("room")), None)
            if not room:
                warnings.append(f"尺寸标注引用了不存在的房间: {d.get('room')}")
                continue
            pos = d.get("at") or _room_label_pos(room)
            ax.text(pos[0], pos[1], d["text"], ha="center", va="center",
                    fontsize=DIM_FS, color=c, zorder=9,
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))
            log_text("room", d["text"], pos[0], pos[1], DIM_FS)

        elif kind == "furniture":
            f = next((x for x in data["furniture"] if x.get("id") == d.get("ref")), None)
            if not f:
                warnings.append(f"尺寸标注引用了不存在的家具: {d.get('ref')}")
                continue
            # v4.4.0：尺寸数值直接压在图元上/紧邻，不用引线拉到图外
            text = furniture_dim_text(f, d, unit)
            lay = furniture_label_layout(f, d, text, data["furniture"], data)
            px, py = lay["pos"]
            if lay["mode"] == "inline2":
                n = len(lay["lines"])
                for i, line in enumerate(lay["lines"]):
                    dy = (n - 1) / 2.0 * lay["fs"] * 34.0 - i * lay["fs"] * 34.0
                    ax.text(px, py + dy, line, ha="center", va="center",
                            fontsize=lay["fs"], color=c, zorder=7,
                            bbox=dict(boxstyle="round,pad=0.1", fc="white",
                                      ec="none", alpha=0.85))
                    log_text("furniture", line, px, py + dy, lay["fs"],
                             group=f"furn-{d.get('ref')}")
            else:
                ax.text(px, py, lay["text"], ha="center", va="center",
                        fontsize=lay["fs"], color=c, zorder=7,
                        rotation=lay["rot"],
                        bbox=dict(boxstyle="round,pad=0.1", fc="white",
                                  ec="none", alpha=0.85))
                log_text("furniture", lay["text"], px, py, lay["fs"], rot=lay["rot"])

        elif kind == "opening":
            # 门窗洞口尺寸标注（第三层）：引线 + 文字，洞口定位写入文字内容
            op = next((o for o in data["openings"] if o.get("id") == d.get("ref")), None)
            if not op:
                warnings.append(f"尺寸标注引用了不存在的门窗: {d.get('ref')}")
                continue
            cx, cy = op["center"]
            off = d.get("offset", [900, 900])
            ax.annotate(d["text"], xy=(cx, cy), xytext=(cx + off[0], cy + off[1]),
                        fontsize=DIM_FS, color=c, ha="center", va="center", zorder=9,
                        arrowprops=dict(arrowstyle="-", lw=0.5, color=c),
                        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))
            log_text("opening", d["text"], cx + off[0], cy + off[1], DIM_FS,
                     group=f"opening-{d.get('ref')}")

        elif kind == "corridor":
            p1, p2 = d["p1"], d["p2"]
            mx, my = (p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0
            cid = f"corridor-{id(d)}"
            ax.add_line(Line2D([p1[0], p2[0]], [p1[1], p2[1]],
                               color=c, lw=0.7, zorder=8))
            for p in (p1, p2):
                dx_, dy_ = p2[0] - p1[0], p2[1] - p1[1]
                L = math.hypot(dx_, dy_) or 1.0
                tx, ty = -dy_ / L * 90, dx_ / L * 90
                ax.add_line(Line2D([p[0] - tx, p[0] + tx], [p[1] - ty, p[1] + ty],
                                   color=c, lw=0.8, zorder=8))
            off = d.get("offset", [0, 300])
            suffix = d.get("suffix", "（通道净宽）")
            txt = f"{d['text']}{suffix}"
            ax.annotate(txt, xy=(mx, my),
                        xytext=(mx + off[0], my + off[1]),
                        fontsize=DIM_FS, color=c, ha="center", va="center", zorder=9,
                        arrowprops=dict(arrowstyle="-", lw=0.5, color=c),
                        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))
            log_text("corridor", txt, mx + off[0], my + off[1], DIM_FS, group=cid)
            dim_lines.append((tuple(p1), tuple(p2), "corridor", cid))

        elif kind == "wall":
            # 墙体厚度标注（4.3 新增）：墙中点 → 法向引线 → "墙厚200"（按 unit 显示）
            w = next((x for x in data["walls"] if x.get("id") == d.get("ref")), None)
            if not w:
                warnings.append(f"尺寸标注引用了不存在的墙体: {d.get('ref')}")
                continue
            fr = wall_frame(w)
            if not fr:
                warnings.append(f"墙体 {d.get('ref')} 数据异常（零长或非法），无法标注厚度")
                continue
            (x1, y1), (x2, y2), L, u, n, ht = fr
            at = d.get("at", 0.5)
            mx = x1 + (x2 - x1) * at
            my = y1 + (y2 - y1) * at
            off = d.get("offset", 500.0)
            side = d.get("side", 1)          # 法向方向：1 / -1
            tx, ty = mx + n[0] * off * side, my + n[1] * off * side
            text = d.get("text") or f"墙厚{fmt_mm(w.get('thickness', 200), unit)}"
            ax.annotate(text, xy=(mx, my), xytext=(tx, ty),
                        fontsize=DIM_FS, color=c, ha="center", va="center", zorder=9,
                        arrowprops=dict(arrowstyle="-", lw=0.5, color=c),
                        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))
            log_text("wall", text, tx, ty, DIM_FS, group=f"wall-{d.get('ref')}")
            dim_lines.append(((mx, my), (tx, ty), "wall-leader", f"wall-{d.get('ref')}"))

    return dim_lines, warnings


def _tick(ax, x, y, size=TICK_LEN, color=None):
    """尺寸线起止符号：45° 中粗斜短划线（建筑制图标准 CAD 起止符，替代实心箭头）。
    两端倾斜方向一致（恒为 "/"），长度 2×size，线宽 0.9，颜色随所属标注层。"""
    k = size * 0.7071
    ax.add_line(Line2D([x - k, x + k], [y - k, y + k],
                       color=color or DIM_COLOR, lw=0.9, zorder=9))


def _room_label_pos(room):
    poly = room["polygon"]
    cx = sum(p[0] for p in poly) / len(poly)
    cy = sum(p[1] for p in poly) / len(poly)
    return [cx, cy - 500]


# --------------------------------------------------------------------------
# 绘制：指北针 / 比例尺 / 图题栏
# --------------------------------------------------------------------------

def draw_north(ax, x, y, angle_deg=0.0, r=420.0):
    a = math.radians(angle_deg)
    dx, dy = math.sin(a), math.cos(a)
    tip = (x + dx * r, y + dy * r)
    ax.add_patch(Polygon([[x, y],
                          [x + dx * r * 0.55 - dy * r * 0.16, y + dy * r * 0.55 + dx * r * 0.16],
                          [x + dx * r * 0.55 + dy * r * 0.16, y + dy * r * 0.55 - dx * r * 0.16]],
                         closed=True, facecolor="black", edgecolor="black", lw=0.6, zorder=10))
    ax.text(tip[0], tip[1], "N", ha="center", va="center", fontsize=8,
            fontweight="bold", zorder=10)
    ax.add_patch(Circle((x, y), r, facecolor="none", edgecolor="black", lw=0.6, zorder=10))


def draw_scale_bar(ax, x, y, unit_mm=2000.0, total_len=6000.0):
    n = int(total_len // unit_mm)
    for i in range(n):
        ax.add_patch(Rectangle((x + i * unit_mm, y), unit_mm, 160,
                               facecolor="black" if i % 2 == 0 else "white",
                               edgecolor="black", lw=0.6, zorder=10))
        ax.text(x + i * unit_mm, y - 260, str(i), ha="center", va="top",
                fontsize=5.5, zorder=10)
    ax.text(x + n * unit_mm, y - 260, f"{n} m", ha="center", va="top",
            fontsize=5.5, zorder=10)
    ax.text(x + n * unit_mm / 2.0, y + 320, "比例尺", ha="center", va="bottom",
            fontsize=6, zorder=10)


def draw_title_block(ax, x, y, w, h, rows):
    rh = h / len(rows)
    ax.add_patch(Rectangle((x, y), w, h, facecolor="white",
                           edgecolor="black", lw=0.9, zorder=10))
    for i, (label, value) in enumerate(rows):
        yy = y + h - (i + 1) * rh
        if i > 0:
            ax.add_line(Line2D([x, x + w], [yy + rh, yy + rh], color="black", lw=0.5, zorder=10))
        ax.add_line(Line2D([x + 0.34 * w, x + 0.34 * w], [yy, yy + rh],
                           color="black", lw=0.5, zorder=10))
        ax.text(x + 0.03 * w, yy + rh / 2.0, label, ha="left", va="center",
                fontsize=5.5, zorder=11)
        ax.text(x + 0.37 * w, yy + rh / 2.0, str(value), ha="left", va="center",
                fontsize=5.5, zorder=11)


# --------------------------------------------------------------------------
# 自检
# --------------------------------------------------------------------------

def door_sweep_zone(w, op):
    """门扇实际扫掠区 bbox（铰链→自由端→门扇末端 三点包围盒 + 容差）。"""
    a, b, n, u = opening_frame(w, op)
    hinge = a if op.get("hinge_side", "p1") == "p1" else b
    free = b if op.get("hinge_side", "p1") == "p1" else a
    side = op.get("open_side", 1)
    tip = (hinge[0] + n[0] * op["width"] * side,
           hinge[1] + n[1] * op["width"] * side)
    pts = [hinge, free, tip]
    bx1 = min(p[0] for p in pts) - 50
    by1 = min(p[1] for p in pts) - 50
    bx2 = max(p[0] for p in pts) + 50
    by2 = max(p[1] for p in pts) + 50
    return (bx1, by1, bx2, by2)


def self_check(data, dim_lines):
    checks = []
    walls = data["walls"]
    furn = data["furniture"]
    openings = data["openings"]
    walls_by_id = wall_by_id(data)
    furn_by_id = {f["id"]: f for f in furn if "id" in f}

    def add(item, level, detail):
        checks.append({"item": item, "level": level, "detail": detail})

    # 1) 家具与墙体净距（贴墙=净距0 PASS；嵌入>0.5mm FAIL）
    embedded, tight = [], []
    for f in furn:
        bx1, by1, bx2, by2 = poly_bounds(get_furniture_poly(f))
        min_d = None
        worst_wall = None
        for w in walls:
            fr = wall_frame(w)
            if not fr:
                continue
            (x1, y1), (x2, y2), L, u, n, ht = fr
            for s in ((bx1, by1), (bx2, by1), (bx2, by2), (bx1, by2),
                      ((bx1 + bx2) / 2, (by1 + by2) / 2)):
                d = seg_point_distance((x1, y1), (x2, y2), s) - ht
                if min_d is None or d < min_d:
                    min_d = d
                    worst_wall = w.get("id")
        if min_d is not None and min_d < -CHECK_TOL_WALL:
            embedded.append((f.get("name", f.get("id")), min_d, worst_wall))
        elif min_d is not None and min_d < -0.01:
            tight.append((f.get("name", f.get("id")), min_d, worst_wall))
    if embedded:
        add("家具与墙体净距", "FAIL",
            "以下家具嵌入墙体（穿墙）：" +
            "；".join(f"{n} 嵌入 {abs(d):.0f}mm（墙 {wid}）" for n, d, wid in embedded))
    elif tight:
        add("家具与墙体净距", "WARN",
            "以下家具压墙线（≤0.5mm，建议微调）：" +
            "；".join(f"{n}（墙 {wid}）" for n, d, wid in tight))
    else:
        add("家具与墙体净距", "PASS", "所有家具未嵌入墙体（贴墙放置净距为 0，属正常）")

    # 2) 门扇扫掠区遮挡检查
    blocked = []
    for op in openings:
        if op.get("type") != "door":
            continue
        w = walls_by_id.get(op.get("wall"))
        if not w:
            continue
        zone = door_sweep_zone(w, op)
        for f in furn:
            fb = poly_bounds(get_furniture_poly(f))
            if rect_overlap_area(fb, zone) > 1.0:
                blocked.append((op.get("id"), f.get("name", f.get("id"))))
    if blocked:
        add("门洞遮挡", "WARN",
            "以下门扇扫掠区内有家具（开门会撞）：" +
            "；".join(f"门 {b[0]} ↔ {b[1]}" for b in blocked))
    else:
        add("门洞遮挡", "PASS", "所有门扇扫掠区（门宽半径）内无家具")

    # 3) 通道净宽（跨墙家具对豁免；<ATTACH_TOL 或 attach_to 同组视为贴邻组合豁免）
    attach_of = {f.get("id"): f.get("attach_to") for f in furn}
    min_gap = None
    attached_skipped = 0
    crosswall_skipped = 0
    for i in range(len(furn)):
        for j in range(i + 1, len(furn)):
            fi, fj = furn[i], furn[j]
            id_i, id_j = fi.get("id"), fj.get("id")
            if attach_of.get(id_i) in (id_j, attach_of.get(id_j)) or \
               attach_of.get(id_j) == id_i or \
               (attach_of.get(id_i) and attach_of.get(id_i) == attach_of.get(id_j)):
                attached_skipped += 1
                continue
            fa = poly_bounds(get_furniture_poly(fi))
            fb2 = poly_bounds(get_furniture_poly(fj))
            ca = ((fa[0] + fa[2]) / 2.0, (fa[1] + fa[3]) / 2.0)
            cb = ((fb2[0] + fb2[2]) / 2.0, (fb2[1] + fb2[3]) / 2.0)
            if any(seg_seg_intersect(ca, cb, w["p1"], w["p2"]) for w in walls):
                crosswall_skipped += 1
                continue
            gx = max(fa[0] - fb2[2], fb2[0] - fa[2], 0.0)
            gy = max(fa[1] - fb2[3], fb2[1] - fa[3], 0.0)
            gap = math.hypot(gx, gy)
            if gap < ATTACH_TOL:
                attached_skipped += 1
                continue
            if min_gap is None or gap < min_gap[0]:
                min_gap = (gap, fi.get("name", id_i), fj.get("name", id_j))
    if min_gap:
        add("家具间通道净宽", "PASS" if min_gap[0] >= MIN_CORRIDOR else "WARN",
            f"最小可通行间距 {min_gap[0]:.0f}mm（{min_gap[1]} ↔ {min_gap[2]}；"
            f"通用家庭下限 {MIN_CORRIDOR:.0f}mm，老人同住建议 {MIN_CORRIDOR_ELDER:.0f}mm；"
            f"跨墙 {crosswall_skipped} 对、贴邻/挂接 {attached_skipped} 对已豁免）")
    elif furn:
        add("家具间通道净宽", "PASS", "家具均为贴邻组合或跨墙分布，无独立通行间距")

    # 4) 家具越界检查（四角是否在任一房间内）
    out_of_room = []
    for f in furn:
        poly = get_furniture_poly(f)
        ok = any(all(point_in_poly(p, r["polygon"]) for p in poly) for r in data["rooms"])
        if not ok:
            out_of_room.append(f.get("name", f.get("id")))
    if out_of_room:
        add("家具房间归属", "WARN",
            "以下家具顶点越出房间净边界（可能压墙或跨间）：" + "、".join(out_of_room))
    else:
        add("家具房间归属", "PASS", "所有家具均在房间净边界内")

    # 5) 尺寸线穿越图元检查（dim_lines 四元组 (p1, p2, kind, group)，v4.5.0）
    hits = []
    for (p1, p2, _kind, _group) in dim_lines:
        for f in furn:
            fb = poly_bounds(get_furniture_poly(f))
            if seg_rect_intersect(p1, p2, fb):
                hits.append(f.get("name", f.get("id")))
                break
    if hits:
        add("尺寸线避让", "WARN",
            "以下图元被尺寸线穿过（需调整 offset）：" + "、".join(sorted(set(hits))))
    else:
        add("尺寸线避让", "PASS", "尺寸线未穿过任何家具图元")

    # 6) 数据完整性
    missing = [op.get("id") for op in openings if op.get("wall") not in walls_by_id]
    if missing:
        add("门窗挂接", "FAIL", "以下门窗未挂到有效墙体: " + "、".join(map(str, missing)))
    else:
        add("门窗挂接", "PASS", f"{len(openings)} 个门窗全部挂接到墙体")

    # 7) 单位声明与标注一致性（4.3 强制输出新增：单位统一 + 标注数值与数据一致）
    unit = data["meta"].get("unit", "mm")
    k = 1000.0 if unit == "m" else 1.0   # 标注文字数值 → mm 的换算系数
    if unit not in ("mm", "m"):
        add("单位与标注一致性", "FAIL", f"meta.unit='{unit}' 非法，只支持 mm / m")
    else:
        problems = []
        # 7a. 房间标注（text 中的 A×B）vs 房间净边界实际宽深
        for d in data["dimensions"]:
            if d.get("kind") != "room":
                continue
            room = next((r for r in data["rooms"] if r.get("id") == d.get("room")), None)
            if not room:
                continue
            xs = [p[0] for p in room["polygon"]]
            ys = [p[1] for p in room["polygon"]]
            rw, rh = max(xs) - min(xs), max(ys) - min(ys)
            pairs = re.findall(r"(\d+(?:\.\d+)?)\s*[×xX\*]\s*(\d+(?:\.\d+)?)",
                               d.get("text", ""))
            if not pairs:
                continue    # 文字未含宽×深（如只标面积），不判
            ok = any(
                (abs(float(a) * k - rw) <= 1.0 and abs(float(b) * k - rh) <= 1.0) or
                (abs(float(a) * k - rh) <= 1.0 and abs(float(b) * k - rw) <= 1.0)
                for a, b in pairs)
            if not ok:
                problems.append(
                    f"房间「{room.get('name', d.get('room'))}」标注“{d.get('text')}”"
                    f"与净宽深 {fmt_mm(rw, unit)}×{fmt_mm(rh, unit)} 不符")
        # 7b. 墙体厚度标注（text 中数字）vs wall.thickness
        for d in data["dimensions"]:
            if d.get("kind") != "wall":
                continue
            w = walls_by_id.get(d.get("ref"))
            if not w:
                continue
            nums = [float(x) * k for x in re.findall(r"\d+(?:\.\d+)?", d.get("text", ""))]
            if nums and all(abs(t - w.get("thickness", 200)) > 0.5 for t in nums):
                problems.append(
                    f"墙体 {w['id']} 厚度标注“{d.get('text')}”与 "
                    f"thickness={fmt_mm(w.get('thickness', 200), unit)} 不符")
        # 7c. 家具尺寸压字（显式 text 中的 W×D）vs 家具图元实际宽深
        for d in data["dimensions"]:
            if d.get("kind") != "furniture":
                continue
            f = furn_by_id.get(d.get("ref"))
            if not f or not d.get("text"):
                continue    # 自动生成的压字与图元天然一致，只校验显式 text
            bx1, by1, bx2, by2 = poly_bounds(get_furniture_poly(f))
            rw, rh = bx2 - bx1, by2 - by1
            for a, b in re.findall(r"(\d+(?:\.\d+)?)\s*[×xX\*]\s*(\d+(?:\.\d+)?)",
                                   d["text"]):
                if not ((abs(float(a) * k - rw) <= 1.0 and abs(float(b) * k - rh) <= 1.0) or
                        (abs(float(a) * k - rh) <= 1.0 and abs(float(b) * k - rw) <= 1.0)):
                    problems.append(
                        f"家具「{f.get('name', f.get('id'))}」标注“{d['text']}”"
                        f"与图元实际 {fmt_mm(rw, unit)}×{fmt_mm(rh, unit)} 不符")
        if problems:
            add("单位与标注一致性", "WARN", "；".join(problems) + "（需人工复核，不得带病交付）")
        else:
            add("单位与标注一致性", "PASS",
                f"单位声明 {unit} 合法；房间开间进深/墙体厚度标注与数据一致")

    # 8) 标注落点归属（v4.3.3 新增，v4.4.0 随压字改制同步公式）：
    #    规则① 家具尺寸标注（压字/offset）落点不得跨出该家具所属房间；
    #    规则② 房间名/面积文字不得被家具图块压盖、不得越出本房间。
    #    这两类是前七项的目视盲区（历史返工：书桌标注落起居室、梳妆台标注落卫生间），
    #    现由脚本几何兜底，落点公式与绘制端共用 furniture_label_layout，逐字一致。
    rooms_by_id = {r["id"]: r for r in data["rooms"] if "id" in r}
    label_fail, label_warn = [], []

    def _room_containing(pt):
        return [rid for rid, r in rooms_by_id.items()
                if point_in_poly(pt, r["polygon"])]

    def _furniture_under(pt):
        for f in furn:
            fb = poly_bounds(get_furniture_poly(f))
            if fb[0] <= pt[0] <= fb[2] and fb[1] <= pt[1] <= fb[3]:
                return f.get("name", f.get("id"))
        return None

    # 8a 家具尺寸压字：落点必须落在该家具所属房间内（公式与渲染端共用）
    for d in data["dimensions"]:
        if d.get("kind") != "furniture":
            continue
        f = furn_by_id.get(d.get("ref"))
        if not f:
            continue    # 引用缺失已由尺寸标注数据告警覆盖
        bx1, by1, bx2, by2 = poly_bounds(get_furniture_poly(f))
        cx, cy = (bx1 + bx2) / 2.0, (by1 + by2) / 2.0
        text = furniture_dim_text(f, d, unit)
        lay = furniture_label_layout(f, d, text, furn, data)
        tx, ty = lay["pos"]
        rid = f.get("room")
        room = rooms_by_id.get(rid)
        if room is None:
            hits = _room_containing((cx, cy))
            if len(hits) == 1:
                room = rooms_by_id[hits[0]]
            else:
                label_warn.append(
                    f"家具「{f.get('name', f.get('id'))}」未声明 room 且几何归属"
                    f"{'跨房间' if hits else '不在任何房间内'}，标注落点无法核验")
                continue
        rname = room.get("name", rid)
        if not point_in_poly((tx, ty), room["polygon"]):
            label_fail.append(
                f"家具「{f.get('name', f.get('id'))}」尺寸标注落点 "
                f"({tx:.0f},{ty:.0f}) 不在所属房间「{rname}」内"
                f"（规则①：家具标注不得跨房间，压字/offset 均受约束）")
        elif not point_in_poly((cx, cy), room["polygon"]):
            label_warn.append(
                f"家具「{f.get('name', f.get('id'))}」中心不在其声明房间"
                f"「{rname}」内，room 字段或坐标可能有误")

    # 8b 房间开间标注（kind=room）：落点须在该房间内
    for d in data["dimensions"]:
        if d.get("kind") != "room":
            continue
        room = rooms_by_id.get(d.get("room"))
        if not room:
            continue
        pos = d.get("at") or _room_label_pos(room)
        if not point_in_poly((pos[0], pos[1]), room["polygon"]):
            label_fail.append(
                f"房间「{room.get('name', d.get('room'))}」开间标注落点 "
                f"({pos[0]:.0f},{pos[1]:.0f}) 不在本房间内，请调整 at")

    # 8c 房间名 / 面积文字：落点须在本房间内，且不得压在家具图块上
    #     （v4.5.0 起加严：除中心点判定外，文字包围盒与家具图块包围盒
    #      重叠同样判 FAIL——「标注不得遮挡图形轮廓和构件」，CAD 易读性优先）
    for r in data["rooms"]:
        poly = r["polygon"]
        cx = sum(p[0] for p in poly) / len(poly)
        cy = sum(p[1] for p in poly) / len(poly)
        name_pos = r.get("name_pos")
        nx, ny = name_pos if name_pos else (cx, cy)
        rname = r.get("name", r.get("id"))
        if not point_in_poly((nx, ny), poly):
            label_fail.append(
                f"房间「{rname}」名称落点 ({nx:.0f},{ny:.0f}) 不在本房间内"
                f"（name_pos 越界）")
        else:
            hit = _furniture_under((nx, ny))
            if hit:
                label_fail.append(
                    f"房间「{rname}」名称压在家具「{hit}」图块上"
                    f"（规则②：房间名不得被家具压盖，请用 name_pos 移至空处）")
            else:
                # 包围盒级：房名边缘擦碰家具轮廓同样不许（文字须完整清晰）
                nb = _label_bbox((nx, ny), r.get("name", ""), 9)
                for f in furn:
                    fb = poly_bounds(get_furniture_poly(f))
                    if rect_overlap_area(nb, fb) > 1.0:
                        label_fail.append(
                            f"房间「{rname}」名称文字框与家具「{f.get('name', f.get('id'))}」"
                            f"轮廓重叠（文字须完整清晰、不得遮挡构件，请用 name_pos 微调）")
                        break
        area_text = r.get("area_text", f"中线面积 {abs(polygon_area(poly)) / 1e6:.1f}㎡")
        if area_text:
            area_pos = r.get("area_pos")
            # 与 draw_rooms / _room_label_boxes 逐字一致：缺省间距 320（v4.5.0）
            ax_, ay_ = area_pos if area_pos else (nx, ny - 320)
            if not point_in_poly((ax_, ay_), poly):
                label_fail.append(
                    f"房间「{rname}」面积文字落点 ({ax_:.0f},{ay_:.0f}) 不在本房间内"
                    f"（溢出压墙风险，请用 area_pos / area_text 覆盖）")
            else:
                ab = _label_bbox((ax_, ay_), area_text, 6.5)
                for f in furn:
                    fb = poly_bounds(get_furniture_poly(f))
                    if rect_overlap_area(ab, fb) > 1.0:
                        label_fail.append(
                            f"房间「{rname}」面积文字框与家具「{f.get('name', f.get('id'))}」"
                            f"轮廓重叠（请用 area_pos 微调）")
                        break

    if label_fail:
        add("标注落点归属", "FAIL", "；".join(label_fail))
    elif label_warn:
        add("标注落点归属", "WARN", "；".join(label_warn))
    else:
        add("标注落点归属", "PASS",
            "家具尺寸标注均在所属房间内；房间名/面积文字未被家具图块压盖")

    # 9) 标注文字互相遮挡（v4.5.0 新增）：_TEXT_LOG 两两碰撞，同组豁免
    #    （同组 = inline2 两行压字这类有设计叠加的文字）
    collide = []
    logs = _TEXT_LOG
    for i in range(len(logs)):
        for j in range(i + 1, len(logs)):
            a, b = logs[i], logs[j]
            if a["group"] is not None and a["group"] == b["group"]:
                continue
            ov = rect_overlap_area(a["bbox"], b["bbox"])
            if ov > 1.0:
                collide.append((a["kind"], a["text"], b["kind"], b["text"], ov))
    if collide:
        add("标注文字防互撞", "FAIL",
            "以下标注文字互相遮挡（文字须完整清晰、不得互相压盖）：" +
            "；".join(f"「{t1}」({k1}) ↔ 「{t2}」({k2})" for k1, t1, k2, t2, _ in collide))
    else:
        add("标注文字防互撞", "PASS",
            f"{len(logs)} 个图面文字两两无遮挡（含房间名/面积/六层标注/家具压字）")

    # 10) 房间名与开间标注压墙（v4.5.0 新增）：文字不得跨房间、不得压墙线
    def _wall_buffer_rects():
        rects = []
        for w in walls:
            fr = wall_frame(w)
            if not fr:
                continue
            (x1, y1), (x2, y2), L, u, n, ht = fr
            xmin, xmax = min(x1, x2) - ht, max(x1, x2) + ht
            ymin, ymax = min(y1, y2) - ht, max(y1, y2) + ht
            rects.append((xmin, ymin, xmax, ymax))
        return rects

    wall_rects = _wall_buffer_rects()
    press = []
    for e in _TEXT_LOG:
        if e["kind"] not in ("room_name", "area", "room", "pinyin"):
            continue
        for wr in wall_rects:
            if rect_overlap_area(e["bbox"], wr) > 1.0:
                press.append((e["kind"], e["text"]))
                break
    furn_press = []
    for e in _TEXT_LOG:
        if e["kind"] != "furniture":
            continue
        for wr in wall_rects:
            if rect_overlap_area(e["bbox"], wr) > 1.0:
                furn_press.append(e["text"])
                break
    if press:
        add("房间名与开间标注压墙", "FAIL",
            "以下文字压墙线或跨房间（应移回所属房间内部空位）：" +
            "；".join(f"「{t}」({k})" for k, t in press))
    elif furn_press:
        add("房间名与开间标注压墙", "WARN",
            "以下家具压字贴墙线（可接受，注意目视）：" + "；".join(f"「{t}」" for t in furn_press))
    else:
        add("房间名与开间标注压墙", "PASS",
            "房间名/面积/开间标注文字均未压墙线；家具压字未贴墙")

    # 11) 尺寸线防交叉与穿字（v4.5.0 CAD 标注规范新增）：
    #     ① 不同 group 的尺寸线两两求交 → FAIL（禁止尺寸线相互交叉）；
    #     ② 细部排/总排尺寸线与走廊线穿过任何文字框 → FAIL（禁穿其他标注；
    #        墙厚引线豁免——其设计即指向自身文字；同组豁免——数字压自有线）。
    cross_line, through_text = [], []
    segs = [(p1, p2, k, g) for (p1, p2, k, g) in dim_lines]
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            a, b = segs[i], segs[j]
            if a[3] == b[3]:
                continue        # 同组（同一尺寸链的分段线共端点）不判
            if seg_seg_intersect(a[0], a[1], b[0], b[1]):
                cross_line.append((a[2], b[2]))
    for (p1, p2, k, g) in dim_lines:
        if k not in ("chain-seg", "chain-total", "corridor"):
            continue            # wall-leader 引线按设计指向文字，豁免
        for e in _TEXT_LOG:
            if e["group"] is not None and e["group"] == g:
                continue        # 同组：数字压自有尺寸线（CAD 常态，白底遮掩）
            if seg_rect_intersect(p1, p2, e["bbox"]):
                through_text.append((k, e["kind"], e["text"]))
    if cross_line:
        add("尺寸线防交叉", "FAIL",
            "以下尺寸线相互交叉（禁止尺寸线/界线交叉或穿过其他标注）：" +
            "；".join(f"{a}×{b}" for a, b in cross_line))
    elif through_text:
        add("尺寸线防穿字", "FAIL",
            "以下尺寸线穿过标注文字（须断开或引出，文字须完整清晰）：" +
            "；".join(f"{k}线穿「{t}」({tk})" for k, tk, t in through_text))
    else:
        add("尺寸线防交叉与穿字", "PASS",
            "尺寸线两两无交叉；细部排/总排/走廊线未穿过任何标注文字"
            f"（共检 {len(dim_lines)} 条尺寸线）")

    return checks


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="2D 平面俯视图（线稿风格）绘图引擎")
    ap.add_argument("json_path", help="户型结构化数据 JSON")
    ap.add_argument("-o", "--output", default="floorplan_2d.png", help="输出 PNG 路径")
    ap.add_argument("--dpi", type=int, default=200, help="输出 DPI（默认 200，高清用 300）")
    ap.add_argument("--report", default=None, help="自检报告输出路径（JSON）")
    ap.add_argument("--title", default=None, help="图题栏项目名（覆盖 JSON meta）")
    args = ap.parse_args()

    t0 = time.perf_counter()
    data = load_plan(args.json_path)
    font = setup_chinese_font()
    t_prep = time.perf_counter()

    # v4.5.1：绘图段抽到 render_figure()，与 render_batch 共用同一条路径
    dim_lines, dim_warn, scale_ratio = render_figure(
        data, args.output, args.dpi, title=args.title)
    t_render = time.perf_counter()

    # 自检与报告
    checks = self_check(data, dim_lines)
    for wmsg in dim_warn:
        checks.append({"item": "尺寸标注数据", "level": "WARN", "detail": wmsg})
    t_check = time.perf_counter()

    n_pass = sum(1 for c in checks if c["level"] == "PASS")
    n_warn = sum(1 for c in checks if c["level"] == "WARN")
    n_fail = sum(1 for c in checks if c["level"] == "FAIL")
    print(f"[draw_floorplan] 输出: {args.output}  dpi={args.dpi}  字体={font or '未找到中文字体(标签降级)'}")
    print(f"[draw_floorplan] 自检: PASS {n_pass} / WARN {n_warn} / FAIL {n_fail}")
    for c in checks:
        print(f"  [{c['level']:>4}] {c['item']}: {c['detail']}")

    if args.report:
        report = build_report(data, checks, output=args.output, font=font,
                              scale_ratio=scale_ratio,
                              unit=data["meta"].get("unit", "mm"),
                              timing=_make_timing(t0, t_prep, t_render, t_check,
                                                  args.dpi, data, args.output))
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        timing = report["timing"]
        print(f"[draw_floorplan] 计时: prepare={timing['prepare_s']}s "
              f"render={timing['render_s']}s selfcheck={timing['selfcheck_s']}s "
              f"total={timing['total_s']}s（dpi={args.dpi}, "
              f"房间 {timing['counts']['rooms']} / 家具 {timing['counts']['furniture']} / "
              f"墙体 {timing['counts']['walls']} / 门窗 {timing['counts']['openings']} / "
              f"标注 {timing['counts']['dimensions']}）")

    if n_fail > 0:
        sys.exit(2)
    return 0


def _make_timing(t0, t_prep, t_render, t_check, dpi, data, output=None):
    """v4.5.1：抽出的计时字典构造，供 main 与 render_batch 共用。"""
    return {
        "prepare_s": round(t_prep - t0, 3),
        "render_s": round(t_render - t_prep, 3),
        "selfcheck_s": round(t_check - t_render, 3),
        "total_s": round(time.perf_counter() - t0, 3),
        "dpi": dpi,
        "png_bytes": (os.path.getsize(output)
                      if output and os.path.exists(output) else None),
        "counts": {"walls": len(data["walls"]),
                   "openings": len(data["openings"]),
                   "rooms": len(data["rooms"]),
                   "furniture": len(data["furniture"]),
                   "dimensions": len(data["dimensions"])},
    }


def build_report(data, checks, output, font, scale_ratio, unit, timing):
    """v4.5.1：自检报告 JSON 构造（main 与 render_batch 共用，字段零漂移）。"""
    room_dims = {}
    for r in data["rooms"]:
        xs = [p[0] for p in r["polygon"]]
        ys = [p[1] for p in r["polygon"]]
        room_dims[r["id"]] = (
            f"{r.get('name', r['id'])} "
            f"{fmt_mm(max(xs) - min(xs), unit)}×{fmt_mm(max(ys) - min(ys), unit)}")
    return {
        "output": output, "checks": checks,
        "font": font, "scale": scale_ratio, "unit": unit,
        "room_dimensions": room_dims, "timing": timing,
        "dims_layer": {
            "note": "尺寸标注独立成层（zorder 7~9，不占墙体/家具层）",
            "zorder": {"家具压字": 7, "尺寸线/尺寸界线": 8, "尺寸文字": 9},
            "colors": DIM_COLORS,
            "total_gap_mm": CHAIN_TOTAL_GAP,
            "tick": "45° 中粗斜短划线（建筑制图标准起止符）",
            "font_size_pt": DIM_FS,
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def render_figure(data, output, dpi, title=None, bbox_tight=False):
    """v4.5.1：单张出图（绘图 + 图面要素 + savefig），返回 (dim_lines, dim_warn)。

    main() 与 render_batch.render_one() 共用同一条绘图路径，
    保证批量出图与单张出图**逐像素一致**。
    返回前已完成 savefig 与 plt.close，调用方负责自检。
    """
    # v4.5.1 P1：默认不再用 bbox_inches='tight'（省 ~45% savefig 耗时）。
    # tight 的本质是"对每个 artist 求显示坐标路径并做贝塞尔裁剪求交"，
    # 而画布范围其实完全可预知：数据范围 + 文字外扩余量。改为显式预算画布，
    # axes 铺满 figure，输出即内容本身，无白边、无求交。
    # bbox_tight=True 保留旧行为作为逃生口（交付前对比验证用）。
    fig, ax = plt.subplots(figsize=(12, 10))
    ax.set_aspect("equal")

    # 第一趟：画内容，用 autoscale 取真实范围（含尺寸标注线）
    reset_text_log()
    draw_rooms(ax, data)
    draw_walls(ax, data)
    draw_openings(ax, data)
    draw_furniture(ax, data)
    unit = data["meta"].get("unit", "mm")
    dim_lines, dim_warn = draw_dimensions(ax, data, unit=unit)

    ax.relim()
    ax.autoscale_view()
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    margin = 3000  # 外圈留给总尺寸线/指北针/比例尺/图题栏
    xmin, xmax = x0 - margin, x1 + margin
    ymin, ymax = y0 - margin, y1 + margin
    ax.axis("off")

    W = xmax - xmin
    H = ymax - ymin

    if bbox_tight:
        # 旧行为：画布含大量空白，靠 tight 裁剪（慢）
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)
        fig.set_size_inches(max(10.0, W / 1000.0 * 0.55),
                            max(8.0, H / 1000.0 * 0.55))
        save_kw = dict(bbox_inches="tight")
    else:
        # 新行为（v4.5.1）：画布 = 数据范围 + 文字外扩余量，axes 铺满，无白边
        # CANVAS_PAD：文字锚点在数据坐标、渲染向外扩的余量。
        # 实测（A4 户型）tight bbox 比数据范围每边大 ~227mm，取 300 留 33% 余量。
        # TARGET_PX_PER_MM：出图像素密度，标定自现状 tight 输出（1586px/18715mm≈0.0848），
        # 取 0.0868 使本例输出 1585px，与现状 1586px 几乎一致；小户型保底 1400px。
        canvas_w = W + 2 * CANVAS_PAD
        canvas_h = H + 2 * CANVAS_PAD
        target_px_w = max(1400.0, canvas_w * TARGET_PX_PER_MM)
        fw = target_px_w / dpi
        fh = fw * canvas_h / canvas_w
        fig.set_size_inches(fw, fh)
        ax.set_position([0, 0, 1, 1])
        ax.set_xlim(xmin - CANVAS_PAD, xmax + CANVAS_PAD)
        ax.set_ylim(ymin - CANVAS_PAD, ymax + CANVAS_PAD)
        save_kw = {}

    # 第二趟：图面要素（位于外圈 margin 区，不与尺寸线相接）
    draw_north(ax, xmax - 1800, ymax - 1800, data["meta"].get("north_angle", 0.0))
    draw_scale_bar(ax, xmin + 900, ymin + 900)
    meta = data["meta"]
    total_area = meta.get("total_area")
    if total_area is None:
        total_area = sum(abs(polygon_area(r["polygon"])) for r in data["rooms"]) / 1e6
        area_row = ("房间面积合计（墙中线）", f"约 {total_area:.1f} ㎡")
    else:
        area_row = ("建筑面积（用户提供）", f"约 {total_area:.1f} ㎡")
    scale_ratio = _guess_scale(W)
    pending = meta.get("pending_confirm", [])
    title_rows = [
        ("项目名称", title or meta.get("project", "未命名户型")),
        area_row,
        ("尺寸单位", "毫米（mm）" if unit == "mm" else "米（m）"),
        ("装修风格", meta.get("style", "未指定")),
        ("居住需求", meta.get("occupancy", "通用家庭")),
        ("绘图比例", scale_ratio),
        ("图纸性质", "AI 布局示意图（非施工图）"),
    ]
    if pending:
        title_rows.append(("待核实项", f"{len(pending)} 项（见交付说明）"))
    draw_title_block(ax, xmax - 5200, ymin + 300, 4700,
                     260 + 320 * len(title_rows), title_rows)

    out_dir = os.path.dirname(os.path.abspath(output))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    fig.savefig(output, dpi=dpi, facecolor="white", edgecolor="none", **save_kw)
    plt.close(fig)
    return dim_lines, dim_warn, scale_ratio


def _guess_scale(W_mm):
    w_m = W_mm / 1000.0
    for ratio in (50, 75, 100, 150, 200):
        if w_m / ratio <= 1.0:
            return f"约 1:{ratio}"
    return "约 1:250"


if __name__ == "__main__":
    sys.exit(main())

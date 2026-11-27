#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""现代选房风水 · 三层评分卡

由外而内评分：室外环境 45 分 + 楼栋 15 分 + 宅内 40 分 = 100 分
用法：
  # 1) 生成空白评分模板
  python3 fengshui_score.py --template > pingfen.json
  # 2) 填好后计算得分与等级
  python3 fengshui_score.py --input pingfen.json
  # 3) 直接在命令行看评分表（不写文件）
  python3 fengshui_score.py --help
"""
import argparse
import json
import sys

# 评分项定义：(层级, key, 名称, 满分, 低于满分60%时的化解/处理建议)
ITEMS = [
    ("outdoor", "shui", "水局（明堂见水/水聚天心/玉带环腰，须活水清澈）", 15,
     "无活水或为死水/发臭水体：以园景或城市视野替代，重点转向采光与通风"),
    ("outdoor", "cangfeng", "藏风（柔和轻风为宜，忌强风直吹/风口）", 10,
     "处于风口或强风直吹：加装厚窗帘与密封门窗，实地在大风天复看一次"),
    ("outdoor", "sixiang", "四象（后有靠山、右低于左、前方开阔明亮）", 10,
     "靠山不足或前方遮挡：优先选小区内部楼栋，避开临街首排与空地前排"),
    ("outdoor", "sha", "煞气（尖角/天斩/反弓/路冲/顶心，按无煞满分递减）", 10,
     "存在煞气：按 references/outdoor-fengshui.md 逐项化解；天斩煞与反弓煞以换房为根本解"),
    ("building", "position", "楼栋位置（小区中心/有靠山为佳）", 8,
     "楼栋位于边缘或临街：核实噪音与灰尘实测，必要时更换楼栋"),
    ("building", "relation", "楼栋关系（后方有楼栋作靠山、右低左高）", 4,
     "楼栋关系不理想：优先选被其他楼栋环抱的位置"),
    ("building", "access", "出入动线（步行归家路径是否安静、有序）", 3,
     "动线不佳：观察早晚高峰与实际通行噪音"),
    ("indoor", "entry", "大门玄关（不直冲、隔断透而适中、采光不阴暗）", 8,
     "玄关问题：加通透隔断（磨砂玻璃/镂空木架）并配暖光照明，灯光排成方/圆形"),
    ("indoor", "kitchen", "厨房（方位得当、灶不对水龙头、厨卫不相邻直对）", 8,
     "厨房问题：调整水龙头朝向、刀具收纳于刀架、冰箱移至角落或与灶台成斜角"),
    ("indoor", "bedroom", "卧室（床不靠窗、不正对镜、不在横梁下）", 8,
     "卧室问题：调整床位避开窗/镜/横梁；横梁下方用暖光射灯或灯带减弱压抑感"),
    ("indoor", "huxing", "户型方正与缺角（中心无卫生间、无明显缺角）", 10,
     "户型缺陷：按 references/huxing-fengshui.md 核对；中心卫生间与严重缺角建议直接放弃"),
    ("indoor", "light", "采光通风（起居室/厨房/卫生间采光依次评估）", 6,
     "采光不足：优先选南北通透户型，必要时在装修阶段优化隔断与窗型"),
]

# 一票否决项（存在任一即判 D，不进入常规打分）
VETO_ITEMS = {
    "unclean_history": "历史上为屠宰场/刑场等不洁用途",
    "abnormal_event": "曾发生凶杀、自杀等非正常事件",
    "special_use": "曾用于殡葬、停尸间、神坛等忌讳用途",
    "danger_terrain": "位于悬崖、陡壁、近水岸、沼泽等危险地势",
    "bad_foundation": "宅基有问题（采矿隧道、暗渠、洼地填土、地基杂物）",
    "basement_living": "地下采光不良空间长期住人",
    "flood_prone": "地势低洼易淹水",
    "weird_building": "建筑体造型奇特（三角形/缺角/高低不均）",
}

GRADE_TABLE = [
    (85, "A", "优选", "外部与内部均无明显硬伤，可作为重点候选。"),
    (70, "B", "合格", "整体可接受，按建议优化个别项即可。"),
    (55, "C", "需化解", "存在明显缺陷，须逐项落实化解方案后再决定。"),
    (0, "D", "不建议", "硬伤较多，换房成本虽高，但长期居住代价更高。"),
]


def build_template():
    tpl = {
        "project": "填写项目/小区名称",
        "veto": [],
        "veto_options": VETO_ITEMS,
        "scores": {},
    }
    for layer, key, name, mx, _ in ITEMS:
        tpl["scores"][key] = {"layer": layer, "name": name, "max": mx, "score": None}
    return tpl


def grade_of(total):
    for threshold, letter, label, advice in GRADE_TABLE:
        if total >= threshold:
            return letter, label, advice
    return "D", "不建议", ""


def calc(data):
    veto = data.get("veto") or []
    rows, layer_sum = [], {}
    for layer, key, name, mx, fix in ITEMS:
        item = (data.get("scores") or {}).get(key) or {}
        raw = item.get("score")
        score = 0 if raw is None else float(raw)
        if score < 0 or score > mx:
            raise ValueError("评分项 %s 的分数应在 0-%s 之间，当前为 %s" % (key, mx, score))
        layer_sum[layer] = layer_sum.get(layer, 0) + score
        rows.append({"layer": layer, "key": key, "name": name, "score": score,
                     "max": mx, "ratio": score / mx, "fix": fix})
    total = sum(layer_sum.values())
    letter, label, advice = grade_of(total)

    print("=" * 64)
    print("现代选房风水 · 三层评分卡")
    print("项目：%s" % data.get("project", "（未填写）"))
    print("=" * 64)
    layer_names = {"outdoor": "室外环境", "building": "楼栋", "indoor": "宅内布局"}
    mx_by_layer = {"outdoor": 45, "building": 15, "indoor": 40}
    for layer in ("outdoor", "building", "indoor"):
        print("\n【%s】%s / %s 分" % (layer_names[layer], layer_sum.get(layer, 0), mx_by_layer[layer]))
        for r in rows:
            if r["layer"] != layer:
                continue
            bar = "█" * int(round(r["ratio"] * 10)) + "·" * (10 - int(round(r["ratio"] * 10)))
            print("  %-34s %5.1f/%-3s %s" % (r["name"][:32], r["score"], r["max"], bar))

    print("\n" + "-" * 64)
    print("总分：%.1f / 100    等级：%s（%s）" % (total, letter, label))
    print("结论：%s" % advice)

    if veto:
        print("\n⚠️  一票否决项（存在以下情况，无论总分高低均不建议）：")
        for v in veto:
            print("   ✗ %s" % VETO_ITEMS.get(v, v))
        print("   结论：D（不建议）——此类情况无有效化解之法。")

    weak = [r for r in rows if r["ratio"] < 0.6]
    if weak:
        print("\n需要化解/重点关注的项：")
        for r in sorted(weak, key=lambda x: x["ratio"]):
            print("   • %s（%.1f/%s）→ %s" % (r["name"], r["score"], r["max"], r["fix"]))
    else:
        print("\n各评分项均达标，无需特别化解。")
    print("\n数据来源：references/outdoor-fengshui.md、indoor-fengshui.md、huxing-fengshui.md")
    return total, letter, label


def main():
    ap = argparse.ArgumentParser(description="现代选房风水三层评分卡")
    ap.add_argument("--template", action="store_true", help="输出空白评分模板 JSON")
    ap.add_argument("--input", help="填写好的评分 JSON 文件路径")
    args = ap.parse_args()

    if args.template:
        print(json.dumps(build_template(), ensure_ascii=False, indent=2))
        return 0
    if not args.input:
        ap.print_help()
        return 1
    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)
    calc(data)
    return 0


if __name__ == "__main__":
    sys.exit(main())

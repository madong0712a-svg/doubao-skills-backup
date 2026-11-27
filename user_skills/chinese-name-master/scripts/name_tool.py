#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中文起名工具：按喜用神五行选字、评测候选名、生成取名报告。

用法示例：
  python name_tool.py gen --surname 马 --yongshen 木,水 --gender male --theme 品德,学识 --count 20
  python name_tool.py score --surname 马 --name 梓涵 --yongshen 木 --theme 学识
  python name_tool.py report --surname 马 --yongshen 木,水 --gender female --theme 学识 --out 取名报告.html

数据文件：scripts/data/chars.json（常用起名用字，含五行/笔画/声调/寓意标签）
"""
import argparse
import json
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data", "chars.json")

INITIALS = ["zh", "ch", "sh", "b", "p", "m", "f", "d", "t", "n", "l",
            "g", "k", "h", "j", "q", "x", "r", "z", "c", "s", "y", "w"]

# 禁止用字（含义不吉或明显不雅）
FORBIDDEN = set("死屎尿屁粪癌灾祸衰丧奸淫贱残凶恶病贫鬼尸毒屠妓嫖赌诈骗愚蠢丑臭疯傻呆债刑狱葬坟墓棺孝疾痛瘟疫劫难亡孤寡苦悲愁恨怨仇杀伤废绝灭败穷困危邪魔妖孽耻辱罪")

# 全名连读的不雅谐音（无声调拼音，命中即严重提示）
BAD_PINYIN = [
    "shizhenxiang", "duziteng", "zhuyiqun", "fantong", "xiajian", "yangwei",
    "shenjingbing", "qinshousheng", "laiyuejing", "houzi", "goushi", "zhutou",
    "wangbadan", "bendan", "feiwu", "laji", "shabi", "chunzhu", "danshen",
    "meiyong", "wuneng", "ruozhi", "baichi", "sile", "yaosi", "bingfei",
]

# 主题同义扩展：用户说“才华”，命中“学识/文雅/才华”都算
THEME_SYNONYMS = {
    "才华": ["才华", "学识", "文雅", "智慧", "聪慧"],
    "学识": ["学识", "才华", "智慧", "文雅", "书香"],
    "品德": ["品德", "诚信", "仁爱", "善良", "美德", "谦和", "端正"],
    "志向": ["志向", "进取", "格局", "担当", "胸怀"],
    "健康": ["平安", "安宁", "活力", "朝气"],
    "平安": ["平安", "安宁", "稳固", "安定"],
    "财富": ["福泽", "兴盛", "荣耀", "丰硕"],
    "事业": ["进取", "兴盛", "担当", "格局", "成就"],
    "美貌": ["柔美", "优雅", "明艳", "雅致", "端庄"],
    "气质": ["儒雅", "雅致", "从容", "端庄", "风度"],
    "阳光": ["阳光", "开朗", "光明", "朝气"],
}

# 常见姓氏：字 -> (拼音, 声调, 笔画, 结构)
SURNAMES = {
    "马": ("ma", 3, 3, "独体"), "王": ("wang", 2, 4, "独体"), "李": ("li", 3, 7, "上下"),
    "张": ("zhang", 1, 7, "左右"), "刘": ("liu", 2, 6, "左右"), "陈": ("chen", 2, 7, "左右"),
    "杨": ("yang", 2, 7, "左右"), "赵": ("zhao", 4, 9, "半包围"), "黄": ("huang", 2, 11, "上下"),
    "周": ("zhou", 1, 8, "半包围"), "吴": ("wu", 2, 7, "上下"), "徐": ("xu", 2, 10, "左右"),
    "孙": ("sun", 1, 6, "左右"), "胡": ("hu", 2, 9, "左右"), "朱": ("zhu", 1, 6, "独体"),
    "高": ("gao", 1, 10, "上下"), "林": ("lin", 2, 8, "左右"), "何": ("he", 2, 7, "左右"),
    "郭": ("guo", 1, 10, "左右"), "罗": ("luo", 2, 8, "上下"), "梁": ("liang", 2, 11, "上下"),
    "宋": ("song", 4, 7, "上下"), "郑": ("zheng", 4, 8, "左右"), "谢": ("xie", 4, 12, "左右"),
    "韩": ("han", 2, 12, "左右"), "唐": ("tang", 2, 10, "半包围"), "冯": ("feng", 2, 5, "左右"),
    "于": ("yu", 2, 3, "独体"), "董": ("dong", 3, 12, "上下"), "萧": ("xiao", 1, 11, "上下"),
    "程": ("cheng", 2, 12, "左右"), "曹": ("cao", 2, 11, "上下"), "袁": ("yuan", 2, 10, "上下"),
    "邓": ("deng", 4, 4, "左右"), "许": ("xu", 3, 6, "左右"), "傅": ("fu", 4, 12, "左右"),
    "沈": ("shen", 3, 7, "左右"), "曾": ("zeng", 1, 12, "上下"), "彭": ("peng", 2, 12, "左右"),
    "吕": ("lv", 3, 6, "上下"), "苏": ("su", 1, 7, "上下"), "卢": ("lu", 2, 5, "上下"),
    "蒋": ("jiang", 3, 12, "上下"), "蔡": ("cai", 4, 14, "上下"), "贾": ("jia", 3, 10, "上下"),
    "丁": ("ding", 1, 2, "独体"), "魏": ("wei", 4, 17, "左右"), "薛": ("xue", 1, 16, "上下"),
    "叶": ("ye", 4, 5, "左右"), "阎": ("yan", 2, 11, "半包围"), "余": ("yu", 2, 7, "上下"),
    "潘": ("pan", 1, 15, "左右"), "杜": ("du", 4, 7, "左右"), "戴": ("dai", 4, 17, "半包围"),
    "夏": ("xia", 4, 10, "上下"), "钟": ("zhong", 1, 9, "左右"), "汪": ("wang", 1, 7, "左右"),
    "田": ("tian", 2, 5, "独体"), "任": ("ren", 2, 6, "左右"), "姜": ("jiang", 1, 9, "上下"),
    "范": ("fan", 4, 8, "上下"), "方": ("fang", 1, 4, "独体"), "石": ("shi", 2, 5, "半包围"),
    "姚": ("yao", 2, 9, "左右"), "谭": ("tan", 2, 14, "左右"), "廖": ("liao", 4, 14, "半包围"),
    "邹": ("zou", 1, 7, "左右"), "熊": ("xiong", 2, 14, "上下"), "金": ("jin", 1, 8, "上下"),
    "陆": ("lu", 4, 7, "左右"), "郝": ("hao", 3, 9, "左右"), "孔": ("kong", 3, 4, "左右"),
    "白": ("bai", 2, 5, "独体"), "崔": ("cui", 1, 11, "上下"), "康": ("kang", 1, 11, "半包围"),
    "毛": ("mao", 2, 4, "独体"), "邱": ("qiu", 1, 7, "左右"), "秦": ("qin", 2, 10, "上下"),
    "江": ("jiang", 1, 6, "左右"), "史": ("shi", 3, 5, "独体"), "顾": ("gu", 4, 10, "左右"),
    "侯": ("hou", 2, 9, "左右"), "邵": ("shao", 4, 7, "左右"), "孟": ("meng", 4, 8, "上下"),
    "龙": ("long", 2, 5, "独体"), "万": ("wan", 4, 3, "独体"), "段": ("duan", 4, 9, "左右"),
    "雷": ("lei", 2, 13, "上下"), "钱": ("qian", 2, 10, "左右"), "汤": ("tang", 1, 6, "左右"),
    "尹": ("yin", 3, 4, "独体"), "黎": ("li", 2, 15, "上下"), "易": ("yi", 4, 8, "上下"),
    "常": ("chang", 2, 11, "上下"), "武": ("wu", 3, 8, "半包围"), "乔": ("qiao", 2, 6, "上下"),
    "贺": ("he", 4, 9, "上下"), "赖": ("lai", 4, 13, "左右"), "龚": ("gong", 1, 11, "上下"),
    "文": ("wen", 2, 4, "独体"), "严": ("yan", 2, 7, "独体"), "岳": ("yue", 4, 8, "上下"),
}


def load_chars():
    with open(DATA, encoding="utf-8") as f:
        rows = json.load(f)
    seen, out = set(), []
    for r in rows:
        if r["c"] in seen:
            continue
        seen.add(r["c"])
        out.append(r)
    return out


CHARS = {r["c"]: r for r in load_chars()}


def split_initial(pinyin):
    for ini in INITIALS:
        if pinyin.startswith(ini):
            return ini, pinyin[len(ini):]
    return "", pinyin


def grade(total):
    if total >= 85:
        return "优秀"
    if total >= 75:
        return "良好"
    if total >= 60:
        return "一般"
    return "不建议"


def surname_info(surname, custom=None):
    if surname in SURNAMES:
        p, t, s, st = SURNAMES[surname]
        return {"c": surname, "p": p, "t": t, "s": s, "st": st, "known": True}
    if custom:
        return {"c": surname, "p": custom[0], "t": int(custom[1]), "s": int(custom[2]),
                "st": custom[3] if len(custom) > 3 else "未知", "known": True}
    return {"c": surname, "p": "", "t": 0, "s": 0, "st": "未知", "known": False}


def score_name(surname, given, yongshen, jishen, theme, sinfo):
    """返回评测详情 dict。given 为名字（不含姓）。"""
    chars = []
    unknown = []
    for ch in given:
        if ch in CHARS:
            chars.append(dict(CHARS[ch]))
        else:
            chars.append({"c": ch, "p": "", "t": 0, "s": 0, "w": "未知", "g": "neutral",
                          "k": [], "pop": 3, "st": "未知"})
            unknown.append(ch)

    notes = []
    severe = []

    # 1) 五行契合 40 分（喜用神按优先级加权）
    wx_score = 0.0
    per = 40.0 / len(chars)
    weights = [1.0, 0.9, 0.82]
    for ch in chars:
        if ch["w"] in yongshen:
            idx = yongshen.index(ch["w"])
            wx_score += per * weights[min(idx, len(weights) - 1)]
        elif ch["w"] in jishen:
            wx_score -= per * 0.5
            notes.append(f"「{ch['c']}」属{ch['w']}，为忌神五行")
        elif ch["w"] == "未知":
            wx_score += per * 0.3
            notes.append(f"「{ch['c']}」不在字库，五行未收录")
        else:
            wx_score += per * 0.5
    wx_score = max(0.0, min(40.0, wx_score))

    # 2) 音韵 20 分
    tone_score = 20.0
    if not sinfo["known"]:
        tone_score = 15.0
        notes.append("姓氏未收录，音韵未完整校验，建议补 --surname-info")
    tones = [sinfo["t"]] + [c["t"] for c in chars]
    pinyins = [sinfo["p"]] + [c["p"] for c in chars]
    initials = [split_initial(p)[0] for p in pinyins]
    finals = [split_initial(p)[1] for p in pinyins]
    valid_tones = [t for t in tones if t]
    if len(set(valid_tones)) == 1 and len(valid_tones) >= 3:
        tone_score -= 8
        notes.append("三字声调全同，读起来平板")
    elif len(valid_tones) >= 2 and len(set(valid_tones)) == 1:
        tone_score -= 3
        notes.append("名字两字声调相同，缺少起伏")
    if len(valid_tones) >= 3 and valid_tones[-2] == valid_tones[-1]:
        tone_score -= 3
        notes.append("名中两字同调，建议一平一仄")
    for i in range(1, len(initials)):
        if initials[i] and initials[i] in initials[:i]:
            tone_score -= 2
            notes.append("名中声母重复，稍显拗口")
            break
    for i in range(1, len(finals)):
        if finals[i] and finals[i] in finals[:i]:
            tone_score -= 2
            notes.append("名中韵母重复，读音粘连")
            break
    if len(chars) == 2 and chars[0]["p"] and chars[0]["p"] == chars[1]["p"]:
        tone_score -= 5
        notes.append("两字同音，辨识度低")
    tone_score = max(0.0, min(20.0, tone_score))

    full_py = "".join(p for p in pinyins if p)
    if full_py in BAD_PINYIN or any(b in full_py for b in BAD_PINYIN if len(b) >= 4 and b in full_py):
        tone_score = 0.0
        severe.append("全名连读疑似不雅谐音，务必换字")

    # 3) 字形 15 分
    shape = 15.0
    strokes = [c["s"] for c in chars if c["s"]]
    if strokes:
        total_strokes = sum(strokes)
        low, high = (8, 20) if len(strokes) == 1 else (16, 32)
        if total_strokes < low:
            shape -= 4
            notes.append("用字笔画偏少，字形偏单薄")
        elif total_strokes > high + 8:
            shape -= 5
            notes.append("用字笔画过繁，书写负担重")
        elif total_strokes > high:
            shape -= 2
            notes.append("用字笔画略繁，可再轻一点")
    structs = [c["st"] for c in chars if c["st"] != "未知"]
    if len(structs) >= 2 and len(set(structs)) == 1:
        shape -= 3
        notes.append("名字两字结构相同，缺少错落感")
    if structs and sinfo["st"] != "未知" and sinfo["st"] in structs:
        shape -= 2
        notes.append("名与姓结构相同，整体偏板")
    for ch in chars:
        if ch["c"] in FORBIDDEN:
            shape -= 8
            severe.append(f"「{ch['c']}」含义不吉，不建议入名")
        if ch["pop"] >= 5:
            shape -= 3
            notes.append(f"「{ch['c']}」偏生僻，可能带来识读与录入麻烦")
    shape = max(0.0, min(15.0, shape))

    # 4) 寓意 15 分
    meaning = 5.0
    tags = [t for c in chars for t in c["k"]]
    if theme:
        hit = 0
        for t in theme:
            keys = THEME_SYNONYMS.get(t, [t])
            if any(any(k in tag for k in keys) for tag in tags):
                hit += 1
        meaning = min(15.0, 5.0 + hit * 5.0)
        if hit == 0:
            notes.append("用字寓意与期望主题关联弱")
    else:
        meaning = 10.0 if len(tags) >= 2 else 6.0

    # 5) 重名度 10 分（越热门越低分）
    pops = [c["pop"] for c in chars]
    avg = sum(pops) / len(pops) if pops else 3
    table = {1: 6.0, 2: 9.0, 3: 9.5, 4: 7.0, 5: 4.0}
    dup = table.get(int(round(avg)), 7.0)
    if avg <= 1.5:
        notes.append("用字热门，重名率偏高")

    total = round(wx_score + tone_score + shape + meaning + dup, 1)
    if severe:
        total = min(total, 55.0)

    return {
        "name": sinfo["c"] + given,
        "given": given,
        "total": total,
        "grade": grade(total),
        "detail": {
            "五行契合(40)": round(wx_score, 1),
            "音韵(20)": round(tone_score, 1),
            "字形(15)": round(shape, 1),
            "寓意(15)": round(meaning, 1),
            "重名度(10)": round(dup, 1),
        },
        "wuxing": "".join(c["w"] for c in chars),
        "strokes": [c["s"] for c in chars],
        "tones": [c["t"] for c in chars],
        "pinyin": " ".join([sinfo["p"]] + [c["p"] for c in chars]).strip(),
        "tags": sorted(set(tags)),
        "notes": notes,
        "severe": severe,
        "unknown": unknown,
    }


def cmd_gen(args):
    yongshen = [x for x in re.split(r"[,，\s]+", args.yongshen or "") if x]
    jishen = [x for x in re.split(r"[,，\s]+", args.jishen or "") if x]
    theme = [x for x in re.split(r"[,，\s]+", args.theme or "") if x]
    sinfo = surname_info(args.surname, args.surname_info)

    pool = [c for c in CHARS.values() if c["c"] != args.surname]
    if args.gender != "neutral":
        pool = [c for c in pool if c["g"] in (args.gender, "neutral")]
    if yongshen:
        wx_pool = [c for c in pool if c["w"] in yongshen]
    else:
        wx_pool = list(pool)

    if args.chars_len == 1:
        results = [score_name(args.surname, c["c"], yongshen, jishen, theme, sinfo) for c in wx_pool]
    else:
        results = []
        for i, a in enumerate(wx_pool):
            for b in wx_pool[i + 1:]:
                if a["p"] == b["p"]:
                    continue
                results.append(score_name(args.surname, a["c"] + b["c"], yongshen, jishen, theme, sinfo))

    results = [r for r in results if not r["severe"]]
    results.sort(key=lambda r: r["total"], reverse=True)
    top = results[: args.count]
    if not top:
        print("没有可用候选，请放宽五行或性别条件。")
        return

    print(f"姓氏：{args.surname}　喜用神：{'、'.join(yongshen) or '未指定'}　"
          f"忌神：{'、'.join(jishen) or '无'}　主题：{'、'.join(theme) or '未指定'}")
    if not sinfo["known"]:
        print("提示：姓氏未收录，音韵与字形评分不完整，可用 --surname-info 补充 拼音,声调,笔画,结构。")
    print(f"候选 {len(results)} 个，列出前 {len(top)} 个：\n")
    for idx, r in enumerate(top, 1):
        d = r["detail"]
        print(f"{idx:02d}. {r['name']}（{r['pinyin']}）　总分 {r['total']}　{r['grade']}")
        print(f"    五行 {r['wuxing']}｜笔画 {'+'.join(map(str, r['strokes']))}")
        print(f"    分项 五行{d['五行契合(40)']} 音韵{d['音韵(20)']} 字形{d['字形(15)']} 寓意{d['寓意(15)']} 重名{d['重名度(10)']}")
        print(f"    寓意 {'、'.join(r['tags']) or '—'}")
        if r["notes"]:
            print(f"    提示 {'；'.join(r['notes'][:3])}")
        print()

    if args.out:
        write_report(args, sinfo, top, yongshen, jishen, theme)


def cmd_score(args):
    yongshen = [x for x in re.split(r"[,，\s]+", args.yongshen or "") if x]
    jishen = [x for x in re.split(r"[,，\s]+", args.jishen or "") if x]
    theme = [x for x in re.split(r"[,，\s]+", args.theme or "") if x]
    sinfo = surname_info(args.surname, args.surname_info)
    given = args.name
    if given.startswith(args.surname):
        given = given[len(args.surname):]
    r = score_name(args.surname, given, yongshen, jishen, theme, sinfo)
    print(f"{r['name']}（{r['pinyin']}）　总分 {r['total']}　{r['grade']}")
    for k, v in r["detail"].items():
        print(f"  {k}: {v}")
    print(f"  五行: {r['wuxing']}｜笔画: {'+'.join(map(str, r['strokes']))}")
    print(f"  寓意标签: {'、'.join(r['tags']) or '—'}")
    for s in r["severe"]:
        print(f"  ⚠ {s}")
    for n in r["notes"]:
        print(f"  · {n}")
    if args.out:
        write_report(args, sinfo, [r], yongshen, jishen, theme)


def write_report(args, sinfo, rows, yongshen, jishen, theme):
    rows_html = []
    for i, r in enumerate(rows, 1):
        d = r["detail"]
        rows_html.append(f"""<tr><td>{i}</td><td class="nm">{r['name']}</td><td>{r['pinyin']}</td>
<td class="sc">{r['total']}</td><td>{r['grade']}</td><td>{r['wuxing']}</td>
<td>{'+'.join(map(str, r['strokes']))}</td><td>{'、'.join(r['tags'])}</td>
<td>{'；'.join(r['notes'][:3]) or '—'}</td></tr>""")
    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>{args.surname}氏取名候选</title>
<style>
body{{font-family:"Microsoft YaHei",system-ui,sans-serif;max-width:1100px;margin:40px auto;padding:0 20px;color:#222;line-height:1.7}}
h1{{font-size:24px;border-left:5px solid #9b2d20;padding-left:12px}}
.meta{{color:#666;font-size:14px;margin-bottom:24px}}
table{{width:100%;border-collapse:collapse;font-size:14px}}
th,td{{border:1px solid #e3e3e3;padding:9px 10px;text-align:left;vertical-align:top}}
th{{background:#faf7f2}}
.nm{{font-size:18px;font-weight:700;letter-spacing:2px}}
.sc{{font-weight:700;color:#9b2d20}}
.note{{margin-top:28px;font-size:13px;color:#777;border-top:1px dashed #ddd;padding-top:14px}}
</style></head><body>
<h1>{args.surname}氏取名候选（{len(rows)} 个）</h1>
<div class="meta">喜用神：{'、'.join(yongshen) or '未指定'}　｜　忌神：{'、'.join(jishen) or '无'}　｜　期望主题：{'、'.join(theme) or '未指定'}</div>
<table><thead><tr><th>#</th><th>姓名</th><th>拼音</th><th>总分</th><th>评级</th><th>五行</th><th>笔画</th><th>寓意</th><th>提示</th></tr></thead>
<tbody>{''.join(rows_html)}</tbody></table>
<div class="note">评分口径：五行契合 40 分、音韵 20 分、字形 15 分、寓意 15 分、重名度 10 分，满分 100。笔画按简体计，不采用康熙笔画，不做五格三才吉凶判定。五行喜忌为参考意见，最终用字请结合家族字辈、方言读音与个人偏好确定。</div>
</body></html>"""
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"报告已生成：{os.path.abspath(args.out)}")


def main():
    ap = argparse.ArgumentParser(description="中文起名工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("gen", help="按喜用神生成候选名")
    g.add_argument("--surname", required=True)
    g.add_argument("--yongshen", default="", help="喜用神五行，如 木,水")
    g.add_argument("--jishen", default="", help="忌神五行，如 金,土")
    g.add_argument("--gender", default="neutral", choices=["male", "female", "neutral"])
    g.add_argument("--theme", default="", help="期望主题，如 品德,学识,志向")
    g.add_argument("--len", dest="chars_len", type=int, default=2, choices=[1, 2])
    g.add_argument("--count", type=int, default=20)
    g.add_argument("--surname-info", dest="surname_info", default=None,
                   help="未收录姓氏：拼音,声调,笔画,结构")
    g.add_argument("--out", default=None, help="HTML 报告输出路径")
    g.set_defaults(func=cmd_gen)

    s = sub.add_parser("score", help="评测已有名字")
    s.add_argument("--surname", required=True)
    s.add_argument("--name", required=True, help="全名或名字部分")
    s.add_argument("--yongshen", default="")
    s.add_argument("--jishen", default="")
    s.add_argument("--theme", default="")
    s.add_argument("--surname-info", dest="surname_info", default=None)
    s.add_argument("--out", default=None)
    s.set_defaults(func=cmd_score)

    args = ap.parse_args()
    if isinstance(getattr(args, "surname_info", None), str):
        args.surname_info = args.surname_info.split(",")
    args.func(args)


if __name__ == "__main__":
    main()

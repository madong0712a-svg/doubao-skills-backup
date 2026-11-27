# -*- coding: utf-8 -*-
"""
采购清单识别自检脚本
用法: python check_qd.py [qd_data.json]
支持两种结构：
  旧单：{date, title, rows:[{name,qty,price,note}]}
  多单：{sheets:[{date, rows:[...]}], grand:{...}}
读取清单数据 + 食材词库，输出：品名匹配、单价区间、数量/金额勾稽、分表与总计汇总。
仅作识别辅助提示，存疑项仍需用户审核定稿。
"""
import sys
import os
import json
import math

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def load_dict():
    p = os.path.join(ROOT, "assets", "ingredients_dict.json")
    with open(p, encoding="utf-8") as f:
        return json.load(f)["items"]


def match_item(name, items):
    key = (name or "").replace(" ", "").strip()
    for it in items:
        if key == it["standard"] or key in it.get("aliases", []):
            return it
    # 别名包含匹配（宽松）
    for it in items:
        if key and (key in it["standard"] or it["standard"] in key):
            return it
    return None


def check_rows(rows, items, label):
    warns = []
    total_qty = 0.0
    total_amt = 0.0
    print(f"\n=== {label} ===")

    for i, row in enumerate(rows, start=1):
        name = row.get("name", "")
        qty = row.get("qty")
        price = row.get("price")
        notes = []
        item = match_item(name, items)

        if item is None:
            notes.append("词库未收录品名，需人工核对")
        else:
            std = item["standard"]
            if std != name:
                notes.append(f"品名归并为「{std}」")
            lo, hi = item.get("price_hint", [None, None])
            if price is not None and lo is not None and not (lo <= price <= hi):
                notes.append(f"单价 {price} 超出常见区间 {lo}~{hi}，复核数字(5/9、1/7)")

        # 数量与金额勾稽
        amt = None
        if isinstance(qty, (int, float)) and isinstance(price, (int, float)):
            amt = round(qty * price, 2)
            total_qty += qty
            total_amt += amt
            if qty < 0:
                notes.append("数量为负，异常")
            if isinstance(qty, float) and not math.isclose(qty, round(qty), rel_tol=0, abs_tol=1e-9):
                notes.append("数量含小数，复核小数点位置")
        else:
            notes.append("数量或单价缺失，待补充")

        flag = "⚠️ " if notes else "✅ "
        amt_s = f"{amt:.2f}" if amt is not None else "—"
        print(f"{flag}{i:2d}. {name}  {qty}斤 × {price}元 = {amt_s}")
        for n in notes:
            print(f"      · {n}")
            warns.append((i, name, n))

    print(f"合计：{len(rows)} 样，{total_qty:g} 斤，金额 {total_amt:.2f} 元")
    return len(rows), total_qty, total_amt, warns


def main():
    data_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "qd_data.json")
    with open(data_path, encoding="utf-8") as f:
        data = json.load(f)
    items = load_dict()

    all_warns = []
    g_items = g_qty = g_amt = 0

    if "sheets" in data:
        print(f"清单来源：{data.get('restaurant', '')} / {data.get('supplier', '')}")
        for idx, sheet in enumerate(data["sheets"], start=1):
            label = f"第{idx}单 {sheet.get('date', '')}"
            n, q, a, w = check_rows(sheet.get("rows", []), items, label)
            g_items += n
            g_qty += q
            g_amt += a
            all_warns += [(label,) + x for x in w]
    else:
        label = f"{data.get('title', '')}  收货日期：{data.get('date', '')}"
        n, q, a, w = check_rows(data.get("rows", []), items, label)
        g_items, g_qty, g_amt, all_warns = n, q, a, w

    print("\n" + "=" * 64)
    print(f"总计：{g_items} 样，{g_qty:g} 斤，金额 {g_amt:.2f} 元")
    if "grand" in data:
        g = data["grand"]
        print(f"定稿对照：{g.get('items')} 样，{g.get('qty')} 斤，{g.get('amt')} 元")

    if all_warns:
        print(f"\n共 {len(all_warns)} 条提示（交用户审核前重点复核）：")
        for entry in all_warns:
            label, i, name, n = entry[0], entry[-3], entry[-2], entry[-1]
            print(f"  - {label} 第{i}行 {name}：{n}")
    else:
        print("\n全部通过词库与区间校验。")


if __name__ == "__main__":
    main()

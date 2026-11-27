# -*- coding: utf-8 -*-
"""
采购清单待审核表生成脚本（可复用模板）
用法:
  1. 复制 qd_data.example.json 为 qd_data.json，填入当天日期与清单行
  2. python make_qd.py [qd_data.json]
生成: output_dir 下《标题（待审核）.xlsx》
"""
import sys
import json
import os
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side


def build(data: dict) -> str:
    title = data["title"]
    date = data["date"]
    rows = data["rows"]
    out_dir = data.get("output_dir", ".")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{title}（待审核）.xlsx")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = title[:31]

    ws["A1"] = f"{title}（待审核）"
    ws["A2"] = f"收货日期：{date}"
    ws["A3"] = "说明：标注“待核对/待补充”的行，请按手写原单确认品名、数量或单价后再录入小程序。"
    ws.append(["序号", "品名", "数量(斤)", "单价(元)", "金额(元)", "备注"])

    start = 5
    for i, row in enumerate(rows, start=1):
        r = start + i - 1
        name = row.get("name")
        qty = row.get("qty")
        price = row.get("price")
        note = row.get("note", "")
        ws.cell(r, 1, i)
        ws.cell(r, 2, name)
        if qty is not None:
            ws.cell(r, 3, qty)
        if price is not None:
            ws.cell(r, 4, price)
        if qty is not None and price is not None:
            ws.cell(r, 5, f"=C{r}*D{r}")
        ws.cell(r, 6, note)

    total_row = start + len(rows)
    ws.cell(total_row, 2, "合计")
    ws.cell(total_row, 3, f"=SUM(C{start}:C{total_row-1})")
    ws.cell(total_row, 5, f"=SUM(E{start}:E{total_row-1})")

    thin = Side(style="thin", color="999999")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    header_fill = PatternFill("solid", fgColor="4472C4")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    center = Alignment(horizontal="center", vertical="center")
    left = Alignment(horizontal="left", vertical="center")

    ws.merge_cells("A1:F1")
    ws["A1"].font = Font(bold=True, size=14)
    ws["A1"].alignment = center
    ws.merge_cells("A2:F2")
    ws["A2"].alignment = left
    ws.merge_cells("A3:F3")
    ws["A3"].font = Font(color="C00000", size=10)
    ws["A3"].alignment = left

    for c in range(1, 7):
        cell = ws.cell(4, c)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center
        cell.border = border

    for r in range(start, total_row + 1):
        for c in range(1, 7):
            cell = ws.cell(r, c)
            cell.border = border
            cell.alignment = left if c in (2, 6) else center

    for c in range(1, 7):
        ws.cell(total_row, c).font = Font(bold=True)

    widths = [6, 12, 10, 10, 10, 34]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

    wb.save(out)
    return out


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "qd_data.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    print(build(data))

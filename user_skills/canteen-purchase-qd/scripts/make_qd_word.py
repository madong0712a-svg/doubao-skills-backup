# -*- coding: utf-8 -*-
"""
采购清单待审核 Word 多表生成脚本（可复用模板）
用法:
  1. 按 qd_data.example.json 结构填写（支持单张 rows 或多张 sheets）
  2. python make_qd_word.py [qd_data.json]
生成: output_dir 下《title（待审核）.docx》

JSON 结构（多单）:
{
  "title": "11月29日-12月3日采购清单",
  "output_dir": "C:\\\\Users\\\\madong\\\\Doubao\\\\chats\\\\2026-11-27\\\\new-chat-3",
  "restaurant": "合阳县新池镇中学",
  "supplier": "合阳县腾婷青菜干菜店",
  "source": "微信「黑池彤彤」",
  "sheets": [
    {"date": "11月29日", "rows": [
      {"name": "蒜苔", "qty": 6, "price": 3.9, "note": ""}
    ]}
  ]
}
兼容旧单结构: {date, title, rows:[...]}
"""
import sys
import os
import json
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

CN_NUM = "一二三四五六七八九十"


def set_cell_font(cell, text, bold=False, size=10.5, align="center", color=None):
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER if align == "center" else WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(str(text))
    run.bold = bold
    run.font.size = Pt(size)
    run.font.name = "宋体"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    if color:
        run.font.color.rgb = RGBColor(*color)


def shade_cell(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), hexcolor)
    tcPr.append(shd)


def fmt_num(v):
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def normalize_sheets(data):
    """兼容旧单 rows 与多单 sheets，统一返回 sheets 列表。"""
    if "sheets" in data:
        return data["sheets"]
    return [{"date": data.get("date", ""), "rows": data.get("rows", [])}]


def build(data: dict) -> str:
    title = data.get("title", "采购清单")
    out_dir = data.get("output_dir", ".")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{title}（待审核）.docx")

    sheets = normalize_sheets(data)
    restaurant = data.get("restaurant", "合阳县新池镇中学")
    supplier = data.get("supplier", "合阳县腾婷青菜干菜店")
    source = data.get("source", "微信「黑池彤彤」")

    doc = Document()
    sec = doc.sections[0]
    sec.left_margin = Cm(2.2)
    sec.right_margin = Cm(2.2)
    sec.top_margin = Cm(2.2)
    sec.bottom_margin = Cm(2.2)
    style = doc.styles["Normal"]
    style.font.name = "宋体"
    style.font.size = Pt(10.5)
    style.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")

    h = doc.add_paragraph()
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = h.add_run("食堂采购清单（待审核）")
    r.bold = True
    r.font.size = Pt(18)
    r.font.name = "黑体"
    r._element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")

    for line in [
        f"采购餐厅：{restaurant}",
        f"供应商：{supplier}",
        f"清单来源：{source}",
        "计量单位：斤　　金额单位：元",
    ]:
        p = doc.add_paragraph()
        p.add_run(line).font.size = Pt(10.5)

    note = doc.add_paragraph()
    rn = note.add_run("说明：本表为手写清单识别初稿，请逐项核对品名、数量、单价；标注“待核对”的行需确认后再录入采购申请。")
    rn.font.size = Pt(10.5)
    rn.font.color.rgb = RGBColor(0xC0, 0x00, 0x00)

    headers = ["序号", "品名", "数量(斤)", "单价(元/斤)", "金额(元)", "备注"]
    widths = [Cm(1.4), Cm(3.6), Cm(2.2), Cm(2.4), Cm(2.2), Cm(4.6)]

    grand_qty = 0.0
    grand_amt = 0.0
    grand_items = 0
    doubts = []

    for idx, sheet in enumerate(sheets, start=1):
        rows = sheet["rows"]
        qty = round(sum(float(x["qty"]) for x in rows), 2)
        amt = round(sum(round(float(x["qty"]) * float(x["price"]), 2) for x in rows), 2)
        grand_qty = round(grand_qty + qty, 2)
        grand_amt = round(grand_amt + amt, 2)
        grand_items += len(rows)
        date = sheet.get("date", "")

        tp = doc.add_paragraph()
        tr = tp.add_run(f"{CN_NUM[idx-1]}、{date} 采购清单（{len(rows)}样，合计 {fmt_num(qty)} 斤 / {amt:.2f} 元）")
        tr.bold = True
        tr.font.size = Pt(12)
        tr.font.name = "黑体"
        tr._element.rPr.rFonts.set(qn("w:eastAsia"), "黑体")

        table = doc.add_table(rows=1, cols=6)
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.style = "Table Grid"
        table.autofit = False

        hdr = table.rows[0].cells
        for c, name in enumerate(headers):
            set_cell_font(hdr[c], name, bold=True, size=10.5)
            shade_cell(hdr[c], "D9E2F3")
            hdr[c].width = widths[c]

        for i, row in enumerate(rows, start=1):
            name, q, price = row["name"], row["qty"], row["price"]
            remark = row.get("note", "")
            amount = round(float(q) * float(price), 2)
            cells = table.add_row().cells
            vals = [str(i), name, fmt_num(q), fmt_num(price), f"{amount:.2f}", remark]
            aligns = ["center", "left", "center", "center", "center", "left"]
            for c, v in enumerate(vals):
                set_cell_font(cells[c], v, size=10.5, align=aligns[c])
                cells[c].width = widths[c]
                if remark and c == 5:
                    for run in cells[c].paragraphs[0].runs:
                        run.font.color.rgb = RGBColor(0xC0, 0x00, 0x00)
            if remark:
                doubts.append(f"{date} 第{i}行 {name}（{fmt_num(q)}斤，{fmt_num(price)}元/斤）：{remark}")

        total_cells = table.add_row().cells
        set_cell_font(total_cells[0], "合计", bold=True)
        total_cells[0].merge(total_cells[1])
        set_cell_font(total_cells[2], fmt_num(qty), bold=True)
        set_cell_font(total_cells[3], "—", bold=True)
        set_cell_font(total_cells[4], f"{amt:.2f}", bold=True)
        set_cell_font(total_cells[5], "", bold=True)
        for c in range(6):
            shade_cell(total_cells[c], "F2F2F2")

        doc.add_paragraph()

    sp = doc.add_paragraph()
    sr = sp.add_run(f"合计：{grand_items} 样，{fmt_num(grand_qty)} 斤，{grand_amt:.2f} 元。")
    sr.bold = True
    sr.font.size = Pt(11)

    if doubts:
        doc.add_paragraph()
        wp = doc.add_paragraph()
        wr = wp.add_run("待核对事项（录入前请确认）：")
        wr.bold = True
        wr.font.size = Pt(11)
        for d in doubts:
            p = doc.add_paragraph()
            run = p.add_run("· " + d)
            run.font.size = Pt(10.5)
            run.font.color.rgb = RGBColor(0xC0, 0x00, 0x00)

    doc.save(out)
    print("SAVED:", out)
    print("ITEMS:", grand_items, "QTY:", fmt_num(grand_qty), "AMT:", f"{grand_amt:.2f}")
    return out


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "qd_data.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    build(data)

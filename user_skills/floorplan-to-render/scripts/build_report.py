#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""floorplan-to-render：设计报告组装器。

扫描输出目录中的效果图（<room>.png / .jpg），把图片 base64 内嵌进一份
自包含 HTML 报告：封面信息 + 风格说明 + 色卡 + 逐空间图卡 + 落地清单。

仅 Python 3 标准库；pathlib 全路径；macOS / Windows 通用。

macOS / Linux:
    python3 scripts/build_report.py --dir ./out --prompts ./out/prompts.json \
        --title "张先生家 · 89㎡ 两室一厅" --output ./out/design-report.html
Windows (PowerShell):
    python scripts\\build_report.py --dir .\\out --prompts .\\out\\prompts.json `
        --title "张先生家 · 89㎡ 两室一厅" --output .\\out\\design-report.html
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import sys
from pathlib import Path

IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def find_image(dir_path: Path, room: str) -> Path | None:
    for ext in IMG_EXTS:
        cand = dir_path / f"{room}{ext}"
        if cand.exists():
            return cand
    # 容错：文件名包含房间键的图片
    for f in sorted(dir_path.iterdir()):
        if f.suffix.lower() in IMG_EXTS and room in f.stem.lower():
            return f
    return None


def img_data_uri(path: Path) -> str:
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def build_report(dir_path: Path, prompts: dict, title: str,
                 floorplan: Path | None) -> str:
    items = prompts["items"]
    found, missing = [], []
    for it in items:
        img = find_image(dir_path, it["room"])
        (found if img else missing).append((it, img))

    swatches = "".join(
        f"<div class='sw'><div class='swc' style='background:{esc(c)}'></div>"
        f"<span>{esc(c)}</span></div>" for c in prompts.get("palette", []))

    floorplan_html = ""
    if floorplan and floorplan.exists():
        floorplan_html = f"""
<h2>原始户型图</h2>
<div class='card'><img src='{img_data_uri(floorplan)}' alt='户型图'></div>"""

    cards = []
    for it, img in found:
        cards.append(f"""
<div class='card'>
  <h3>{esc(it['room_cn'])}</h3>
  <img src='{img_data_uri(img)}' alt='{esc(it['room_cn'])}效果图'>
  <p class='note'>{esc(it['design_note'])}</p>
</div>""")
    if missing:
        miss = "、".join(esc(it["room_cn"]) for it, _ in missing)
        cards.append(f"<p class='warn'>⚠️ 以下空间的效果图未找到，未纳入报告：{miss}</p>")

    checklist = """
<h2>效果图 → 落地核对清单</h2>
<table><thead><tr><th>阶段</th><th>要核对的事</th></tr></thead><tbody>
<tr><td>量房复核</td><td>效果图家具尺寸 vs 实测净空（尤其过道 ≥600mm、柜门开启半径）</td></tr>
<tr><td>硬装交底</td><td>把效果图打印给施工方：吊顶高度、灯位、插座高度逐图标尺</td></tr>
<tr><td>主材选样</td><td>按色卡选砖/地板/墙漆，索要小样在自然光下比对，展厅灯光会骗人</td></tr>
<tr><td>软装下单</td><td>沙发/床/餐桌三大件先定，尺寸卡住动线后再配小件；色差以实物为准</td></tr>
<tr><td>预算兜底</td><td>效果图为风格参考非施工图纸；复杂造型（弧形/隐形门）逐项问价再决定</td></tr>
</tbody></table>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>{esc(title)} · 装修效果图方案</title>
<style>
:root {{ --ink:#33302b; --line:#ddd6c9; --accent:#8b6b4a; --bg:#fbf9f5; --soft:#f2ede3; }}
* {{ box-sizing:border-box; }}
body {{ font-family:"PingFang SC","Microsoft YaHei",sans-serif; color:var(--ink);
  background:var(--bg); max-width:860px; margin:24px auto; padding:0 20px; line-height:1.7; }}
h1 {{ font-size:26px; border-bottom:3px solid var(--accent); padding-bottom:8px; }}
h2 {{ font-size:19px; margin-top:34px; border-left:5px solid var(--accent); padding-left:10px; }}
.meta {{ background:var(--soft); border:1px solid var(--line); border-radius:8px;
  padding:10px 14px; font-size:14px; }}
.card {{ background:#fff; border:1px solid var(--line); border-radius:10px;
  padding:16px; margin:16px 0; }}
.card img {{ width:100%; border-radius:6px; display:block; }}
.card h3 {{ margin:0 0 10px; color:var(--accent); }}
.note {{ font-size:13.5px; color:#6b6459; margin:10px 0 0; }}
.swatches {{ display:flex; gap:14px; flex-wrap:wrap; margin:10px 0; }}
.sw {{ text-align:center; font-size:12px; color:#6b6459; }}
.swc {{ width:56px; height:56px; border-radius:8px; border:1px solid var(--line); }}
table {{ width:100%; border-collapse:collapse; font-size:13.5px; margin-top:10px; }}
th, td {{ border:1px solid var(--line); padding:8px 10px; text-align:left; }}
th {{ background:var(--soft); }}
.warn {{ background:#fdf3e7; border:1px solid #e3c99a; border-radius:8px; padding:10px 14px; }}
.footer {{ margin-top:36px; font-size:12px; color:#97907f; border-top:1px solid var(--line);
  padding-top:10px; }}
@media print {{ body {{ margin:0; max-width:none; }} .card {{ page-break-inside:avoid; }} }}
</style></head><body>
<h1>{esc(title)}</h1>
<div class="meta">🎨 设计风格：<b>{esc(prompts['style_cn'])}</b> &nbsp;·&nbsp;
🖼️ 效果图 {len(found)} 张 &nbsp;·&nbsp; 由 floorplan-to-render v1.0.0 生成<br>
{esc(prompts.get('style_notes', ''))}</div>

<h2>风格色卡</h2>
<div class="swatches">{swatches}</div>
{floorplan_html}

<h2>空间效果图</h2>
{''.join(cards)}
{checklist}
<div class="footer">效果图为 AI 生成的风格意向图，非施工图纸；尺寸、材料、造价以实测与报价为准。</div>
</body></html>"""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="设计报告组装器（floorplan-to-render）")
    p.add_argument("--dir", type=Path, required=True, help="效果图所在目录")
    p.add_argument("--prompts", type=Path, required=True, help="prompt_builder 生成的 prompts.json")
    p.add_argument("--title", default="家装效果图方案", help="报告标题")
    p.add_argument("--floorplan", type=Path, default=None, help="原始户型图路径（可选，嵌入报告）")
    p.add_argument("--output", type=Path, default=None,
                   help="报告输出路径（默认 <dir>/design-report.html）")
    args = p.parse_args(argv)

    if not args.dir.is_dir():
        p.error(f"目录不存在: {args.dir}")
    prompts = json.loads(args.prompts.read_text(encoding="utf-8"))
    output = args.output or (args.dir / "design-report.html")

    html_text = build_report(args.dir, prompts, args.title, args.floorplan)
    output.write_text(html_text, encoding="utf-8")

    found = [it["room"] for it in prompts["items"] if find_image(args.dir, it["room"])]
    print(json.dumps({
        "report": str(output),
        "images_embedded": len(found),
        "rooms_found": found,
        "size_kb": round(output.stat().st_size / 1024, 1),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

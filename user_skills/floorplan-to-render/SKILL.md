---
name: floorplan-to-render
description: "Turn a residential floor plan image into a full interior design rendering package (户型图生成装修效果图): read the layout, help the user pick a style, generate per-room photorealistic renderings plus a 3D aerial dollhouse view via image-to-image, and assemble a self-contained HTML design report with palette swatches, per-room design notes and a landing checklist. This skill should be used when the user provides a floor plan (户型图/平面图) and asks for 装修效果图/设计方案/风格参考/3D鸟瞰图, or asks to visualize an apartment layout before renovation."
version: "1.0.0"
display_name: 户型图效果图工坊
display_name_en: Floorplan to Render
description_zh: "上传户型图即可生成全套装修效果图：解读户型格局、选定装修风格、逐房间生成写实效果图与全屋 3D 鸟瞰图，并组装成带色卡、设计说明与落地清单的自包含 HTML 设计报告。"
description_en: "Upload a floor plan and get a full rendering package: layout reading, style selection, per-room photorealistic renderings plus a 3D aerial view, assembled into a self-contained HTML report with palette, design notes and landing checklist."
visibility: "public"
agent_created: true
---

# Floorplan to Render（户型图效果图工坊）

## Overview

Turn one floor plan image into a complete interior design rendering package: layout reading → style selection → per-room AI renderings (image-to-image with the floor plan as reference) → printable self-contained HTML design report. Scripts are pure Python 3 standard library, cross-platform (macOS / Windows).

Deliverables (in the chosen output directory):
- `prompts.json` — structured prompt list for the image generation step
- `<room>.png` — one rendering per room (aerial 全屋鸟瞰 / living / dining / master / second / kitchen / bath / balcony)
- `design-report.html` — self-contained report: style palette, floor plan, per-room rendering cards with design notes, landing checklist

## Workflow

### Step 1: Read the floor plan

Read the user's floor plan image and produce a 户型解读表 (格局 / 面积 / 朝向 / 优点 / 注意点). Follow the checklist in `references/style-and-floorplan-guide.md` §1 — extract load-bearing walls, window positions, and room dimensions BEFORE any design discussion. Never propose removing load-bearing walls in renderings.

### Step 2: Confirm style and scope

Ask the user to pick one style (offer the style-selection matrix in `references/style-and-floorplan-guide.md` §2 based on their profile):

| --style | 风格 | | --style | 风格 |
|---|---|---|---|---|
| modern | 现代简约 | | lightlux | 轻奢 |
| nordic | 原木北欧 | | newchinese | 新中式 |
| cream | 奶油风 | | industrial | 工业风 |

Also confirm room scope: `default` (aerial + living + master + kitchen + bath), `all` (8 views), or a custom comma list.

### Step 3: Generate the prompt list

macOS / Linux:
```bash
python3 scripts/prompt_builder.py --style nordic --rooms default --out <输出目录>/prompts.json
```
Windows (PowerShell):
```powershell
python scripts\prompt_builder.py --style nordic --rooms default --out <输出目录>\prompts.json
```

### Step 4: Generate renderings via image generation

For each item in prompts.json, call the image generation tool (ImageGen) with:
- `image1` = the user's floor plan path
- `prompt` = `item.prompt` (verbatim; the `{style}` placeholder is already substituted)
- `size` = `item.size`, `quality` = `high`

Generate the `aerial` (3D 鸟瞰) FIRST and show it to the user to confirm the layout reading before rendering the rest — this minimizes rework. Then rename each generated image to `item.file` (e.g. `living.png`) inside the output directory. See `references/style-and-floorplan-guide.md` §3 for retry/prompt-tuning tactics.

### Step 5: Assemble the design report

macOS / Linux:
```bash
python3 scripts/build_report.py --dir <输出目录> --prompts <输出目录>/prompts.json \
    --floorplan <户型图路径> --title "XX家 · 89㎡ 两室一厅" --output <输出目录>/design-report.html
```
Windows (PowerShell):
```powershell
python scripts\build_report.py --dir <输出目录> --prompts <输出目录>\prompts.json `
    --floorplan <户型图路径> --title "XX家 · 89㎡ 两室一厅" --output <输出目录>\design-report.html
```

Images are embedded as base64 — the HTML is self-contained and printable. Present `design-report.html` first, then the individual renderings.

### Step 6: Set expectations

Always close with the boundaries in `references/style-and-floorplan-guide.md` §4: renderings are style-intent images, not construction drawings; AI may flatter proportions; verify dimensions and prices before ordering.

## Cross-platform notes

- Python 3 standard library only (argparse, json, base64, html, pathlib). No pip install.
- All paths via `pathlib`; no hardcoded separators; no unix-only commands or APIs.
- The image generation step itself uses the agent's image tool, not shell commands — no platform dependency.

## Resources

### scripts/
- `prompt_builder.py` — 6 styles × 8 room views prompt matrix; prints or writes prompts.json.
- `build_report.py` — scans an output directory for `<room>.png` images and assembles the self-contained HTML report (base64 embedded).
- `selftest.py` — 7-assertion self-check; run after any edit to scripts.

### references/
- `style-and-floorplan-guide.md` — floor plan reading checklist, style-selection matrix with budget notes, prompt tactics for image-to-image, and mandatory expectation-setting boundaries.

## Self-check

macOS / Linux: `python3 scripts/selftest.py` — expect `SELFTEST OK (7/7)`.
Windows (PowerShell): `python scripts\selftest.py`.

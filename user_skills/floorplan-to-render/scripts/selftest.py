#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""floorplan-to-render 自检：7 项断言，全部通过打印 SELFTEST OK。

仅标准库；临时目录用 tempfile（macOS / Windows 通用）。

macOS / Linux:  python3 scripts/selftest.py
Windows:        python scripts\\selftest.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPT_BUILDER = ROOT / "scripts" / "prompt_builder.py"
REPORT_BUILDER = ROOT / "scripts" / "build_report.py"

# 1x1 像素 PNG（测试用占位图）
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c626001000000ffff03000006000557bfabd40000000049"
    "454e44ae426082")

checks: list[str] = []


def ok(name: str) -> None:
    checks.append(name)
    print(f"  ✓ {name}")


def run(script: Path, args: list[str]) -> subprocess.CompletedProcess:
    r = subprocess.run([sys.executable, str(script)] + args,
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise AssertionError(f"{script.name} failed: {r.stderr[-500:]}")
    return r


def main() -> int:
    print("floorplan-to-render selftest")
    with tempfile.TemporaryDirectory(prefix="fpr_test_") as td:
        base = Path(td)

        # 1. 6 种风格 × all 房间均可生成 prompt
        for style in ("modern", "nordic", "cream", "lightlux", "newchinese", "industrial"):
            r = run(PROMPT_BUILDER, ["--style", style, "--rooms", "all"])
            data = json.loads(r.stdout)
            assert len(data["items"]) == 8, (style, len(data["items"]))
            for it in data["items"]:
                assert it["prompt"] and "{style}" not in it["prompt"], it
                assert it["size"] in ("1024x1024", "1536x1024"), it
        ok("6 种风格 × 8 房间的 prompt 全部生成且占位符已替换")

        # 2. default 房间集 = 5 个（含全屋鸟瞰）
        r = run(PROMPT_BUILDER, ["--style", "modern", "--rooms", "default"])
        data = json.loads(r.stdout)
        rooms = [it["room"] for it in data["items"]]
        assert rooms == ["aerial", "living", "master", "kitchen", "bath"], rooms
        ok("default 房间集 = aerial/living/master/kitchen/bath")

        # 3. 指定房间子集 + 写入 JSON 文件
        pj = base / "prompts.json"
        run(PROMPT_BUILDER, ["--style", "cream", "--rooms", "living,kitchen",
                             "--out", str(pj)])
        data = json.loads(pj.read_text(encoding="utf-8"))
        assert [it["room"] for it in data["items"]] == ["living", "kitchen"]
        assert data["style_cn"] == "奶油风" and len(data["palette"]) == 5
        ok("房间子集选择 + prompts.json 落盘")

        # 4. 未知房间键报错退出
        r = subprocess.run([sys.executable, str(PROMPT_BUILDER), "--style", "modern",
                            "--rooms", "garage"], capture_output=True, text=True, timeout=60)
        assert r.returncode != 0 and "garage" in r.stderr
        ok("未知房间键被拒绝并提示")

        # 5. 报告组装：有图房间嵌图，缺图房间给警告
        out_dir = base / "case5"
        out_dir.mkdir()
        (out_dir / "living.png").write_bytes(TINY_PNG)
        (out_dir / "kitchen.png").write_bytes(TINY_PNG)
        r = run(REPORT_BUILDER, ["--dir", str(out_dir), "--prompts", str(pj),
                                 "--title", "测试宅"])
        summary = json.loads(r.stdout)
        assert summary["images_embedded"] == 2, summary
        report = Path(summary["report"]).read_text(encoding="utf-8")
        assert "data:image/png;base64," in report and "测试宅" in report
        ok("报告嵌入 2 张 base64 效果图")

        # 6. 报告自包含：无外链资源，含色卡与落地清单
        assert "http://" not in report and "https://" not in report
        for key in ("风格色卡", "空间效果图", "落地核对清单", "@media print"):
            assert key in report, key
        ok("报告自包含且含色卡/图卡/落地清单/打印样式")

        # 7. 户型图嵌入（--floorplan）与缺图警告
        fp = base / "floorplan.png"
        fp.write_bytes(TINY_PNG)
        pj2 = base / "prompts2.json"
        run(PROMPT_BUILDER, ["--style", "nordic", "--rooms", "living,bath", "--out", str(pj2)])
        r = run(REPORT_BUILDER, ["--dir", str(out_dir), "--prompts", str(pj2),
                                 "--floorplan", str(fp), "--output", str(base / "r2.html")])
        report2 = Path(base / "r2.html").read_text(encoding="utf-8")
        assert "原始户型图" in report2 and "未找到" in report2  # bath.png 缺失
        ok("户型图嵌入 + 缺图房间警告")

    print(f"\nSELFTEST OK ({len(checks)}/7)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

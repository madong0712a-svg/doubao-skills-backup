#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""render_batch.py — 平面俯视图批量出图（v4.5.1 性能优化 P0）

为什么需要它
------------
单张出图的真实耗时里，**Python 冷启动 + matplotlib 导入约 1.27s**，
而真正的矢量绘图只有 48ms、savefig 约 0.44s、自检 17ms。
多次出图（改参数试稿、多方案对比、多房间分别出图）时，
每次都付一次冷启动税，累计浪费极大（实测 3 张：独立进程 5.8s → 单进程 1.8s，3.3×）。

本脚本**不复制任何绘图逻辑**——直接调用 `draw_floorplan.render_figure()` /
`build_report()` / `self_check()`，与单张出图走**同一条代码路径**，
输出**逐像素一致**（已用 PIL ImageChops 验证 diff bbox = None）。

用法
----
  # 同一份数据出多个 dpi
  python render_batch.py "plan.json@200=plan_200.png" "plan.json@300=plan_300.png"

  # 多份数据顺序出图（推荐：串行，启动税只付一次）
  python render_batch.py "a.json@200=a.png" "b.json@200=b.png"

  # 指定图题栏项目名（覆盖 JSON meta.project）
  python render_batch.py "plan.json@200=out.png" --title "A4 户型"

  # 只跑自检不出图（最快，纯几何校验，~20ms/张）
  python render_batch.py --check-only plan1.json plan2.json

安全性
------
- 串行执行，不引入并发（进程启动税会吃掉并发收益）；
- `render_figure()` 内每轮新建 fig/ax 并 `plt.close()`，且开头 `reset_text_log()`
  清模块级文字台账 —— 第 8/9/10/11 项自检依赖它，绝不跨轮复用；
- **不缓存任何计算结果**（含 self_check）——改了数据必须重算，
  缓存自检报告会产出「数据已改、报告是旧的」这种严重错误。

退出码：0 = 全部 FAIL=0；2 = 有 FAIL（不得交付）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: F401  (Agg 后端必须先于 pyplot)

import draw_floorplan as D  # noqa: E402


def parse_job(job: str):
    """'data.json@dpi=out.png' -> (src, dpi, out)；格式错返回 None。"""
    try:
        src, rest = job.split("@", 1)
        dpi_s, out = rest.split("=", 1)
        return src, int(dpi_s), out
    except ValueError:
        return None


def run_check_only(src: str):
    """只跑自检：走与出图相同的绘图路径取 dim_lines，再交给 self_check，不落图。"""
    t0 = time.perf_counter()
    data = D.load_plan(src)
    D.setup_chinese_font()
    fig, ax = plt.subplots(figsize=(12, 10))
    D.reset_text_log()
    for fn in (D.draw_rooms, D.draw_walls, D.draw_openings, D.draw_furniture):
        fn(ax, data)
    unit = data["meta"].get("unit", "mm")
    dim_lines, dim_warn = D.draw_dimensions(ax, data, unit=unit)
    plt.close(fig)
    checks = D.self_check(data, dim_lines)
    for wmsg in dim_warn:
        checks.append({"item": "尺寸标注数据", "level": "WARN", "detail": wmsg})
    return checks, (time.perf_counter() - t0) * 1000


def main():
    ap = argparse.ArgumentParser(
        description="平面俯视图批量出图（单进程复用，省掉每次冷启动）")
    ap.add_argument("jobs", nargs="*",
                    help="任务，格式 data.json@dpi=out.png（可多个）")
    ap.add_argument("--title", default=None, help="图题栏项目名（覆盖 JSON meta）")
    ap.add_argument("--check-only", action="store_true", help="只跑自检不出图")
    ap.add_argument("--no-report", action="store_true", help="不写自检报告 JSON")
    args = ap.parse_args()

    print("[render_batch] 解释器启动 + import 已完成（此后不再重复付）")

    jobs = []
    if args.check_only:
        jobs = [(j, None, None) for j in args.jobs]
    else:
        for j in args.jobs:
            p = parse_job(j)
            if p is None:
                print(f"[render_batch] 跳过（格式应为 data.json@dpi=out.png）：{j}")
                continue
            jobs.append(p)

    if not jobs:
        ap.error("没有有效任务。用法见文件头 docstring，或加 --check-only 传 json 路径。")

    n_fail_total = 0
    total = 0.0
    t_all = time.perf_counter()
    for src, dpi, out in jobs:
        t0 = time.perf_counter()
        n_pass = n_warn = n_fail = 0
        if args.check_only:
            checks, el = run_check_only(src)
            n_pass = sum(1 for c in checks if c["level"] == "PASS")
            n_warn = sum(1 for c in checks if c["level"] == "WARN")
            n_fail = sum(1 for c in checks if c["level"] == "FAIL")
            print(f"[render_batch] [自检] {os.path.basename(src)}  "
                  f"PASS {n_pass} / WARN {n_warn} / FAIL {n_fail}")
        else:
            data = D.load_plan(src)
            font = D.setup_chinese_font()
            t_prep = time.perf_counter()
            dim_lines, dim_warn, scale_ratio = D.render_figure(
                data, out, dpi, title=args.title)
            t_render = time.perf_counter()
            checks = D.self_check(data, dim_lines)
            for wmsg in dim_warn:
                checks.append({"item": "尺寸标注数据", "level": "WARN", "detail": wmsg})
            t_check = time.perf_counter()

            n_pass = sum(1 for c in checks if c["level"] == "PASS")
            n_warn = sum(1 for c in checks if c["level"] == "WARN")
            n_fail = sum(1 for c in checks if c["level"] == "FAIL")

            if args.no_report:
                rep_name = "(未写报告)"
            else:
                rep_path = os.path.splitext(out)[0] + ".report.json"
                report = D.build_report(
                    data, checks, output=out, font=font,
                    scale_ratio=scale_ratio,
                    unit=data["meta"].get("unit", "mm"),
                    timing=D._make_timing(t0, t_prep, t_render, t_check,
                                          dpi, data, out))
                with open(rep_path, "w", encoding="utf-8") as f:
                    json.dump(report, f, ensure_ascii=False, indent=2)
                rep_name = os.path.basename(rep_path)

            el = (time.perf_counter() - t0) * 1000
            print(f"[render_batch] {os.path.basename(out)}  dpi={dpi}  {el:.0f} ms  "
                  f"自检 PASS {n_pass} / WARN {n_warn} / FAIL {n_fail}  → {rep_name}")
        total += el
        n_fail_total += n_fail

    wall = (time.perf_counter() - t_all) * 1000
    print(f"[render_batch] 合计 {total:.0f} ms / {len(jobs)} 张，"
          f"均摊 {total / len(jobs):.0f} ms每张；总墙钟 {wall:.0f} ms")
    if n_fail_total:
        print(f"[render_batch] 有 {n_fail_total} 项 FAIL —— 不得交付，改数据后重跑")
    else:
        print("[render_batch] 全部 FAIL=0；WARN 请逐条进交付检查表")

    sys.exit(2 if n_fail_total else 0)


if __name__ == "__main__":
    main()
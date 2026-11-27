#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render.py — 效果图出图层（多服务商文生图 / 图生图）

定位（v4.7.0 新增，P1-1）
------------------------
本技能此前的出图依赖宿主 ImageGen 工具，**没有自己的出图层**：
不知道用什么模型、不知道成本、无法固定 seed 保证跨房间一致。
本脚本补上这一层，并且**只消费 make_room_prompts.py 产出的 prompts JSON** ——
效果图提示词禁止人工转写（4.6.0 铁律二），本脚本从入口上执行这条铁律。

设计要点
--------
1. **零成本优先**：默认走硅基流动免费档 `FLUX.1-schnell`，出图不计费，
   单次交付毛利接近 100%；要更高质量再 `--tier pro` 切 `FLUX.1-dev`（按服务商计费，
   出图前必须已向用户说明）。
2. **seed 一致**：同一户型的全部镜头共用同一 seed（第 8 段），
   来自 prompts JSON（由 make_room_prompts.py 按计划内容哈希生成），`--seed` 可覆盖。
   竞品靠同一 designId 保跨房间一致，我方靠 seed。
3. **失败回落**：退出码 2（无凭证）/ 3（调用失败）→ 上层流程回落到宿主 ImageGen，
   **出图失败不阻塞交付，永远有图可出**。
4. **密钥零硬编码**：全部走环境变量，脚本内不出现任何 Key。

用法
----
  # 先看要发什么（不消耗额度，每次出图前先跑）
  python3 render.py --prompts prompts.json --dry-run

  # 真实出图（硅基流动免费档，成本 0）
  export FLOORPLAN_IMAGE_KEY=<你的 SiliconFlow API Key>
  python3 render.py --prompts prompts.json --provider siliconflow --save-dir ./效果图

  # 每镜头出 2 张挑一张
  python3 render.py --prompts prompts.json --provider siliconflow --repeat 2 --save-dir ./out

  # 图生图：以平面图/参考图为条件（风格更贴原始户型）
  python3 render.py --prompts prompts.json --ref plan.png --provider siliconflow

  # 高质量档（付费，出图前须已向用户说明成本）
  python3 render.py --prompts prompts.json --tier pro --save-dir ./out

  # 自建端点（OpenAI 兼容 / 本地 SD WebUI）
  export FLOORPLAN_API_URL=http://127.0.0.1:7860
  python3 render.py --prompts prompts.json --provider generic --api-style sdwebui

  python3 render.py --list-providers      # 看支持的服务商与所需环境变量

退出码（供上层流程判断回落）
--------------------------
  0  成功
  2  未配置凭证 / prompts 文件缺失或不可读 → 回落宿主 ImageGen
  3  调用或解析失败 → 回落宿主 ImageGen
  4  用法错误（不回落，是命令写错了）

环境变量
--------
  FLOORPLAN_IMAGE_KEY    通用 Key（任一服务商都认这个变量）
  SILICONFLOW_KEY        硅基流动专用 Key（优先于 FLOORPLAN_IMAGE_KEY）
  ZHIPU_KEY              智谱专用
  DASHSCOPE_API_KEY      通义万相专用
  REPLICATE_API_TOKEN    Replicate 专用
  FLOORPLAN_API_URL      generic 自建端点地址（必填）
  FLOORPLAN_API_KEY      generic 端点 Key（可选）

依赖: 无（纯标准库）。
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request

EXIT_OK = 0
EXIT_NO_CONFIG = 2      # 无凭证 / 输入缺失 → 上层回落 ImageGen
EXIT_API_ERROR = 3      # 调用失败 → 上层回落 ImageGen
EXIT_USAGE = 4           # 用法错误

VERSION = "4.7.0"
TIMEOUT = 180
POLL_INTERVAL = 3        # 异步任务轮询间隔（秒）
POLL_TIMEOUT = 300       # 异步任务最长等待（秒）

# ------------------------------------------------------------------ 服务商
PROVIDERS = {
    "siliconflow": {
        "label": "硅基流动 SiliconFlow",
        "url": "https://api.siliconflow.cn/v1/images/generations",
        "model_free": "black-forest-labs/FLUX.1-schnell",   # 免费，成本 0
        "model_pro": "black-forest-labs/FLUX.1-dev",        # 付费/试用额度
        "key_env": ["SILICONFLOW_KEY", "FLOORPLAN_IMAGE_KEY"],
        "note": "国内直连；默认免费档 schnell 出图成本 0，单次毛利接近 100%",
        "supports_seed": True,
        "supports_negative": True,
        "supports_image": True,
    },
    "zhipu": {
        "label": "智谱 Zhipu",
        "url": "https://open.bigmodel.cn/api/paas/v4/images/generations",
        "model_free": "cogview-4",
        "model_pro": "cogview-4",
        "key_env": ["ZHIPU_KEY", "FLOORPLAN_IMAGE_KEY"],
        "note": "低价（约 ¥0.01/张）+ 新用户赠送额度；不是完全免费，超了扣费",
        "supports_seed": False,
        "supports_negative": False,
        "supports_image": False,
    },
    "wanxiang": {
        "label": "阿里通义万相",
        "url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/"
               "text2image/image-synthesis",
        "model_free": "wanx2.1-t2i-turbo",
        "model_pro": "wanx2.1-t2i-plus",
        "key_env": ["DASHSCOPE_API_KEY", "FLOORPLAN_IMAGE_KEY"],
        "note": "异步任务：创建后轮询，脚本已内置",
        "supports_seed": False,
        "supports_negative": True,
        "supports_image": False,
    },
    "replicate": {
        "label": "Replicate",
        "url": "https://api.replicate.com/v1/predictions",
        "model_free": "black-forest-labs/flux-schnell",
        "model_pro": "black-forest-labs/flux-dev",
        "key_env": ["REPLICATE_API_TOKEN", "FLOORPLAN_IMAGE_KEY"],
        "note": "社区模型托管；按运行秒计费",
        "supports_seed": True,
        "supports_negative": False,
        "supports_image": True,
    },
    "generic": {
        "label": "自建/兼容端点",
        "url": os.environ.get("FLOORPLAN_API_URL", ""),
        "model_free": "",
        "model_pro": "",
        "key_env": ["FLOORPLAN_API_KEY"],
        "note": "OpenAI 兼容 /images/generations，或本地 SD WebUI /sdapi/v1/txt2img"
                "（地址必填 FLOORPLAN_API_URL，风格用 --api-style 切）",
        "supports_seed": True,
        "supports_negative": True,
        "supports_image": True,
    },
}

# 宽高比 → 各服务商尺寸字符串（16:9 为室内全景默认）
ASPECT_SIZE = {
    "siliconflow": {"16:9": "1024x576", "1:1": "1024x1024", "9:16": "576x1024"},
    "zhipu": {"16:9": "1344x768", "1:1": "1024x1024", "9:16": "768x1344"},
    "wanxiang": {"16:9": "1280*720", "1:1": "1024*1024", "9:16": "720*1280"},
    "replicate": {"16:9": "16:9", "1:1": "1:1", "9:16": "9:16"},
    "generic": {"16:9": "1024x576", "1:1": "1024x1024", "9:16": "576x1024"},
}


def provider_key(provider):
    """按优先级取 Key：服务商专用变量 > 通用 FLOORPLAN_IMAGE_KEY。"""
    for env in PROVIDERS[provider]["key_env"]:
        v = os.environ.get(env, "").strip()
        if v:
            return v
    return ""


def provider_url(provider):
    if provider == "generic":
        return os.environ.get("FLOORPLAN_API_URL", "").strip()
    return PROVIDERS[provider]["url"]


# ------------------------------------------------------------------ HTTP
def http_json(url, body=None, headers=None, method="POST", timeout=TIMEOUT,
              raw=False):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        blob = resp.read()
    return blob if raw else json.loads(blob.decode("utf-8"))


def image_to_data_uri(path):
    if not os.path.exists(path):
        sys.stderr.write(f"ERROR: 参考图不存在: {path}\n")
        sys.exit(EXIT_API_ERROR)
    mime = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as f:
        return f"data:{mime};base64,{base64.b64encode(f.read()).decode('ascii')}"


# ------------------------------------------------------------------ 各服务商
def build_body(provider, model, prompt, negative, size, seed, ref_uri, tier,
               api_style, repeat):
    cfg = PROVIDERS[provider]
    body = {}
    if provider == "siliconflow":
        body = {
            "model": model,
            "prompt": prompt,
            "image_size": size,
            "batch_size": repeat,
            "num_inference_steps": 4 if tier == "free" else 28,
        }
        if cfg["supports_negative"] and negative:
            body["negative_prompt"] = negative
        if tier == "pro":
            body["guidance_scale"] = 3.5
        if cfg["supports_seed"] and seed is not None:
            body["seed"] = seed
        if ref_uri and cfg["supports_image"]:
            body["image"] = ref_uri
            body["image_strength"] = 0.55     # 图生图：保留户型结构为主
    elif provider == "zhipu":
        body = {"model": model, "prompt": prompt, "size": size}
    elif provider == "wanxiang":
        body = {"model": model,
                "input": {"prompt": prompt,
                          "negative_prompt": negative or ""},
                "parameters": {"size": size.replace("x", "*"),
                               "n": repeat}}
    elif provider == "replicate":
        body = {"version": model,
                "input": {"prompt": prompt, "num_outputs": repeat,
                          "aspect_ratio": size, "seed": seed if seed is not None else 0,
                          "output_format": "png", "output_quality": 90}}
        if negative:
            body["input"]["negative_prompt"] = negative
        if ref_uri:
            body["input"]["image"] = ref_uri
    else:  # generic
        if api_style == "sdwebui":
            body = {"prompt": prompt, "negative_prompt": negative or "",
                    "steps": 30, "cfg_scale": 7, "width": int(size.split("x")[0]),
                    "height": int(size.split("x")[1]), "batch_size": repeat,
                    "seed": seed if seed is not None else -1,
                    "sampler_name": "DPM++ 2M Karras"}
        else:
            body = {"model": model, "prompt": prompt, "size": size,
                    "n": repeat, "response_format": "b64_json"}
            if negative:
                body["negative_prompt"] = negative
            if ref_uri:
                body["image"] = ref_uri
    return body


def call_provider(provider, key, url, body, api_style):
    """返回 [(kind, value), ...]；kind ∈ {url, b64}。异步服务商在此轮询。"""
    hdrs = {}
    if provider == "replicate":
        hdrs = {"Authorization": f"Token {key}", "Prefer": "wait"}
    else:
        hdrs = {"Authorization": f"Bearer {key}"}

    if provider == "wanxiang":
        hdrs["X-DashScope-Async"] = "enable"
        res = http_json(url, body, hdrs)
        task_id = (res.get("output") or {}).get("task_id")
        if not task_id:
            raise RuntimeError(f"通义万相未返回 task_id: {json.dumps(res, ensure_ascii=False)[:200]}")
        deadline = time.time() + POLL_TIMEOUT
        while time.time() < deadline:
            time.sleep(POLL_INTERVAL)
            st = http_json(f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}",
                           method="GET", headers=hdrs)
            out = st.get("output") or {}
            status = out.get("task_status")
            if status == "SUCCEEDED":
                pairs = []
                for item in (out.get("results") or []):
                    if item.get("url"):
                        pairs.append(("url", item["url"]))
                if not pairs:
                    raise RuntimeError("通义万相任务成功但无图片 URL")
                return pairs
            if status in ("FAILED", "CANCELED"):
                raise RuntimeError(f"通义万相任务 {status}: "
                                   f"{json.dumps(out, ensure_ascii=False)[:200]}")
        raise RuntimeError(f"通义万相轮询超时（{POLL_TIMEOUT}s）")

    if provider == "replicate":
        res = http_json(url, body, hdrs)
        pid = res.get("id")
        deadline = time.time() + POLL_TIMEOUT
        while res.get("status") not in ("succeeded", "failed", "canceled") \
                and time.time() < deadline:
            time.sleep(POLL_INTERVAL)
            res = http_json(f"https://api.replicate.com/v1/predictions/{pid}",
                            method="GET", headers=hdrs)
        if res.get("status") != "succeeded":
            raise RuntimeError(f"Replicate {res.get('status')}: {res.get('error')}")
        return [("url", u) for u in (res.get("output") or []) if isinstance(u, str)]

    res = http_json(url, body, hdrs)
    return parse_images(res, api_style)


def parse_images(res, api_style="openai"):
    """从各家响应提取图片。SD WebUI 返回 {images:[b64]}。"""
    out = []
    if not isinstance(res, dict):
        return out
    if api_style == "sdwebui":
        for b in (res.get("images") or []):
            if isinstance(b, str):
                out.append(("b64", b))
        return out
    for item in (res.get("data") or []):
        if isinstance(item, dict):
            if item.get("url"):
                out.append(("url", item["url"]))
            elif item.get("b64_json"):
                out.append(("b64", item["b64_json"]))
    for item in ((res.get("output") or {}).get("results") or []):
        if isinstance(item, dict) and item.get("url"):
            out.append(("url", item["url"]))
    if res.get("image"):
        out.append(("b64", res["image"]))
    if isinstance(res.get("output"), list):
        for u in res["output"]:
            if isinstance(u, str):
                out.append(("url", u))
    for k in ("images", "urls"):
        v = res.get(k)
        if isinstance(v, list):
            for x in v:
                if isinstance(x, str):
                    out.append(("url", x))
                elif isinstance(x, dict) and x.get("url"):
                    out.append(("url", x["url"]))
    return out


def save_pairs(pairs, save_dir, fname):
    os.makedirs(save_dir, exist_ok=True)
    paths = []
    for i, (kind, val) in enumerate(pairs):
        p = os.path.join(save_dir, fname if len(pairs) == 1
                         else f"{os.path.splitext(fname)[0]}_{i + 1}.png")
        if kind == "b64":
            with open(p, "wb") as f:
                f.write(base64.b64decode(val))
        else:
            blob = http_json(val, method="GET", raw=True)
            with open(p, "wb") as f:
                f.write(blob)
        paths.append(p)
    return paths


def safe_name(s):
    keep = "-_.() []"
    return "".join(c if (c.isalnum() or c in keep) else "_" for c in s).strip() \
        or "shot"


# ------------------------------------------------------------------ 主流程
def load_prompts(path):
    if not path or not os.path.exists(path):
        sys.stderr.write(
            "ERROR: 缺少 prompts 文件。效果图提示词必须由 make_room_prompts.py 生成：\n"
            "  python make_room_prompts.py plan.json --out-json prompts.json\n"
            "  python render.py --prompts prompts.json --provider siliconflow\n")
        sys.exit(EXIT_NO_CONFIG)
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except Exception as e:
        sys.stderr.write(f"ERROR: prompts 文件不可读: {e}\n")
        sys.exit(EXIT_NO_CONFIG)
    shots = d.get("shots")
    if not isinstance(shots, list) or not shots:
        sys.stderr.write("ERROR: prompts 文件无 shots 数组（不是 make_room_prompts.py 的产物？）\n")
        sys.exit(EXIT_NO_CONFIG)
    for s in shots:
        if not s.get("prompt"):
            sys.stderr.write("ERROR: shots 中存在无 prompt 的镜头\n")
            sys.exit(EXIT_NO_CONFIG)
    if "make_room_prompts" not in str(d.get("generated_by", "")):
        sys.stderr.write("WARN: prompts 文件 generated_by 不是 make_room_prompts.py，"
                         "请确认提示词来源（4.6.0 铁律二：禁止人工转写）\n")
    return d


class _Parser(argparse.ArgumentParser):
    """用法错误统一退 4（argparse 默认退 2，会与「无凭证回落」撞码）。"""

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(EXIT_USAGE, f"{self.prog}: error: {message}\n")


def main():
    ap = _Parser(
        description="效果图出图层：消费 make_room_prompts.py 的 prompts JSON，多服务商出图")
    ap.add_argument("--prompts", default="",
                    help="make_room_prompts.py --out-json 产出的 JSON")
    ap.add_argument("--provider", default="siliconflow",
                    choices=list(PROVIDERS.keys()), help="服务商（默认硅基流动免费档）")
    ap.add_argument("--tier", default="free", choices=["free", "pro"],
                    help="free=免费模型（默认，成本 0）；pro=付费高质量模型")
    ap.add_argument("--api-style", default="openai",
                    choices=["openai", "sdwebui"],
                    help="generic 端点的接口风格（默认 openai 兼容）")
    ap.add_argument("--model", default="", help="覆盖默认模型")
    ap.add_argument("--seed", type=int, default=None,
                    help="覆盖 prompts JSON 的 seed（同户型应保持全批一致，慎用）")
    ap.add_argument("--repeat", type=int, default=1, metavar="N",
                    help="每镜头出 N 张挑一张（1-4）")
    ap.add_argument("--ref", default="", help="参考图（平面图/实景图，图生图）")
    ap.add_argument("--save-dir", default="", help="图片保存目录（不填则不下载）")
    ap.add_argument("--prefix", default="效果图", help="保存文件名前缀")
    ap.add_argument("--dry-run", action="store_true",
                    help="只打印将发送的内容，不调用 API、不消耗额度")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--list-providers", action="store_true", help="列出服务商后退出")
    args = ap.parse_args()

    if args.list_providers:
        for k, v in PROVIDERS.items():
            print(f"[{k}] {v['label']}  — {v['note']}")
            print(f"    免费档 {v['model_free'] or '(端点自定)'} | "
                  f"付费档 {v['model_pro'] or '(端点自定)'}")
            print(f"    Key 环境变量: {' 或 '.join(v['key_env'])}")
        return

    if args.repeat < 1 or args.repeat > 4:
        sys.stderr.write("--repeat 只支持 1-4\n")
        sys.exit(EXIT_USAGE)

    doc = load_prompts(args.prompts)
    shots = doc["shots"]
    seed = args.seed if args.seed is not None else doc.get("seed")
    if seed is None:
        # prompts JSON 没有 seed（旧版产物）→ 按内容 md5 兜底，仍保证全批一致
        # （不能用 str.__hash__：进程盐化，重跑就变）
        import hashlib
        blob = json.dumps(doc, sort_keys=True, ensure_ascii=False).encode("utf-8")
        seed = int(hashlib.md5(blob).hexdigest()[:8], 16) % 2147483647
    model = args.model or (PROVIDERS[args.provider]["model_pro"] if args.tier == "pro"
                           else PROVIDERS[args.provider]["model_free"])
    url = provider_url(args.provider)
    key = provider_key(args.provider)

    # ---- dry-run：不调用、不扣费 ----
    if args.dry_run:
        info = {
            "version": VERSION,
            "provider": args.provider,
            "provider_label": PROVIDERS[args.provider]["label"],
            "model": model,
            "tier": args.tier,
            "seed": seed,
            "seed_source": "--seed 覆盖" if args.seed is not None
                           else doc.get("seed_source", "prompts-json"),
            "ref_image": args.ref or None,
            "repeat": args.repeat,
            "size_map": ASPECT_SIZE.get(args.provider, {}),
            "shots": len(shots),
            "estimated_cost": ("0（免费档）" if args.tier == "free"
                               else "按服务商计费（出图前须已向用户说明）"),
            "detail": [{"room": s.get("room"), "tag": s.get("tag", ""),
                        "style": s.get("style", ""), "seed": seed,
                        "prompt_head": s.get("prompt", "")[:80]} for s in shots],
        }
        if args.json:
            print(json.dumps(info, ensure_ascii=False, indent=2))
        else:
            print("=" * 64)
            print(f"效果图出图预览（render.py v{VERSION} --dry-run，不消耗额度）")
            print("=" * 64)
            print(f"服务商  {args.provider} · {PROVIDERS[args.provider]['note']}")
            print(f"模型    {model}（{args.tier} 档）")
            print(f"seed    {seed}（全批 {len(shots)} 个镜头共用）")
            print(f"每镜    {args.repeat} 张 | 参考图 {args.ref or '无（纯文生图）'}")
            print(f"成本    {info['estimated_cost']}")
            print("-" * 64)
            for i, s in enumerate(shots, 1):
                print(f"\n[{i}] {s.get('room')}"
                      f"{('｜' + s['tag']) if s.get('tag') else ''}"
                      f"（{s.get('style', '')}）")
                print("  正向：" + s.get("prompt", "")[:160] + "…")
                if s.get("negative"):
                    print("  负向：" + s["negative"][:100] + "…")
            print("\n" + "=" * 64)
            print("确认无误后去掉 --dry-run 即可真实出图。")
        return

    # ---- 凭证与地址检查（缺失 → 退出码 2，上层回落宿主 ImageGen）----
    if not url:
        sys.stderr.write("ERROR: generic 端点未配置 FLOORPLAN_API_URL\n")
        sys.exit(EXIT_NO_CONFIG)
    if not key:
        envs = " 或 ".join(PROVIDERS[args.provider]["key_env"])
        sys.stderr.write(
            f"WARN: 未设置 {envs}，无法调用 {args.provider}。\n"
            "      请申请 Key 后重试；或直接走宿主 ImageGen 默认通道（退出码 2 已标明）。\n")
        sys.exit(EXIT_NO_CONFIG)

    ref_uri = image_to_data_uri(args.ref) if args.ref else None
    size_of = ASPECT_SIZE.get(args.provider, ASPECT_SIZE["generic"])
    results = []
    for idx, s in enumerate(shots, 1):
        aspect = s.get("aspect", "16:9")
        size = size_of.get(aspect, size_of.get("16:9", "1024x576"))
        negative = s.get("negative") or ""
        prompt = s.get("prompt_with_suffix") or s.get("prompt")
        body = build_body(args.provider, model, prompt, negative, size, seed,
                          ref_uri, args.tier, args.api_style, args.repeat)
        try:
            pairs = call_provider(args.provider, key, url, body, args.api_style)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "ignore")[:400]
            sys.stderr.write(f"ERROR: {args.provider} 返回 {e.code}：{detail}\n")
            sys.exit(EXIT_API_ERROR)
        except urllib.error.URLError as e:
            sys.stderr.write(f"ERROR: 网络请求失败: {e}\n")
            sys.exit(EXIT_API_ERROR)
        except Exception as e:  # noqa
            sys.stderr.write(f"ERROR: 出图异常: {e}\n")
            sys.exit(EXIT_API_ERROR)
        if not pairs:
            sys.stderr.write("ERROR: 响应中未解析到图片（返回结构可能有变）\n")
            sys.exit(EXIT_API_ERROR)

        saved = []
        if args.save_dir:
            base = f"{args.prefix}_{idx:02d}_{safe_name(s.get('room', ''))}"
            if s.get("tag"):
                base += f"_{safe_name(s['tag'])}"
            saved = save_pairs(pairs, args.save_dir, base + ".png")

        results.append({
            "room": s.get("room"), "room_id": s.get("room_id"),
            "tag": s.get("tag", ""), "style": s.get("style", ""),
            "seed": seed, "prompt": prompt,
            "images": [v if k == "url" else "<base64>" for k, v in pairs],
            "saved": saved,
        })

    if args.save_dir:
        manifest = {
            "version": VERSION, "provider": args.provider, "model": model,
            "tier": args.tier, "seed": seed, "seed_source":
                "--seed 覆盖" if args.seed is not None else doc.get("seed_source"),
            "source_prompts": os.path.abspath(args.prompts),
            "size_disclaimer": doc.get("size_disclaimer", ""),
            "results": results,
        }
        mpath = os.path.join(args.save_dir, "manifest.json")
        with open(mpath, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        results_note = f"；清单已写入 {mpath}"
    else:
        results_note = ""

    if args.json:
        print(json.dumps({"provider": args.provider, "seed": seed,
                          "results": results}, ensure_ascii=False, indent=2))
    else:
        for r in results:
            print(f"\n[{r['room']}{('｜' + r['tag']) if r['tag'] else ''}] seed={r['seed']}")
            for u in r["images"]:
                print("  " + u)
            for p in r["saved"]:
                print("  已保存 → " + p)
        print(f"\n共 {len(results)} 个镜头成功{results_note}")
    sys.exit(EXIT_OK)


if __name__ == "__main__":
    main()

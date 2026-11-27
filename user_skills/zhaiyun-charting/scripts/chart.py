# -*- coding: utf-8 -*-
"""命令行客户端：向计算服务要可复算符号，或把报告 JSON 交给服务渲染成 HTML。

本脚本只使用 Python 标准库，不导入 sxtwl，也不在本机排盘。
计算服务地址写在 DEFAULT_API_BASE，发布专家包前改为公网地址。
环境变量 YIXUE_API_BASE 可覆盖，便于本机联调。

用法:
  python -B chart.py 1986 5 12 10 30 男 --place-code 310101
  python -B chart.py 1986 5 12 10 30 男 121.47          （用户亲口给出经度时）
  python -B chart.py 1986 5 12 10 30 男 --year 2026
  python -B chart.py 1990 4 22 14 30 男 --lunar         （用户报的是农历生日时）
  python -B chart.py 1990 5 1 14 30 男 --lunar --leap   （农历闰五月）
  python -B chart.py render 报告.json
  python -B chart.py render 报告.json --out 输出目录
  python -B chart.py liunian 1986 5 12 10 30 男 2026 --place-code 310101
  python -B chart.py liuyue 1986 5 12 10 30 男 2026 8 --place-code 310101
                                         月支是地支序号：子=0 … 寅=2 … 申=8 … 亥=11
  python -B chart.py fengshui 1990 女 离 --year 2026

--place-code 是 references/geo-*.tsv 里的行政区划代码。脚本按代码取出经度和全称，
经度不经手抄写。报告 JSON 的 birth 里写 place_code，render 时同样按表换成经度。

--lunar 表示 year month day 按农历解释，不给就是公历；--leap 表示该月是闰月，
只能与 --lunar 同用。report 与 fengshui 不接受这两个开关（报告的农历生日写在 birth 里）。
农历换算在服务端完成，本机不做历法计算；闰月不存在、日数超出当月等非法农历由服务端返回 400。

排盘把符号 JSON 打到标准输出，不写报告文件。方案写在报告 JSON 的 scheme 字段里。
render 把服务返回的 HTML 写到报告 JSON 的同目录，或 --out 指定的目录，不写进技能目录。
报告名为「图文报告-八字-2026-10-12.html」这种形式：可读前缀 + 解读类型 + 日期，
不沿用 JSON 的随机名；同一天同一类型再生成时补序号，也不会覆盖前面的报告。

服务连不上、返回非 2xx 或响应不是合法 JSON 时，脚本以非 0 退出，
并打印「计算服务不可用，停止排盘」。不要在本机安装 Python 3.11 或 sxtwl，
也不要口算干支。调用时带 -B，本脚本也会关闭字节码写入。

埋点：打包时会在技能根目录写入 biz.txt（brand=<brandId>、kind=skill|expert），
本脚本读取后给每个请求带上 X-Yixue-Biz / X-Yixue-Kind，供服务端日志归因。
源码目录没有这个文件时不发头，属正常情况，不报错也不影响排盘。
"""
import sys

sys.dont_write_bytecode = True

import glob
import json
import os
import re
import tempfile
import time
import urllib.error
import urllib.request

# 发布专家包前改为计算服务的公网地址。
DEFAULT_API_BASE = "http://121.41.172.119:8765"
UNAVAILABLE = "计算服务不可用，停止排盘"
MONTH_ZHI_RANGE = "month_zhi 须为 0 到 11 的地支序号（子=0，丑=1，寅=2，申=8，亥=11）"

DEFAULT_OUTPUT_DIRNAME = "output"
FALLBACK_DIRNAME = "yixue-chart-output"
# 包内埋点标记（打包时写入，不进源码仓库）：品牌与包形态，日志据此归因。
BIZ_FILE = "biz.txt"
BIZ_HEADER = "X-Yixue-Biz"
KIND_HEADER = "X-Yixue-Kind"
BIZ_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
BIZ_KINDS = {"skill", "expert"}
_biz_meta_cache = None
# 交给用户看的报告用可读的中文名：前缀 + 解读类型 + 日期，重名时补序号，绝不覆盖。
REPORT_FILENAME_PREFIX = "图文报告"
REPORT_SCHEME_LABELS = {"bazi": "八字", "ziwei": "紫微", "fusion": "八字紫微", "zeri": "择日"}


def api_base() -> str:
    return os.environ.get("YIXUE_API_BASE", DEFAULT_API_BASE).rstrip("/")


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def fail_unavailable(detail: str = "") -> None:
    """服务端给了具体校验说明时原样透出，便于定位；否则用通用措辞。"""
    if detail:
        print(f"{UNAVAILABLE}：{detail}", file=sys.stderr)
    else:
        print(UNAVAILABLE, file=sys.stderr)
    raise SystemExit(1)


def usage_fail(message: str) -> None:
    """参数不足时按失败退出。

    调用方（技能）的契约是「脚本非零退出即停止」；原先把帮助打到标准输出后 return 0，
    会被当成排盘成功，模型可能拿着空结果去写报告。帮助文本仍照旧输出，只改走 stderr
    并以非零退出，让失败走同一条通道。
    """
    print(__doc__, file=sys.stderr)
    fail(message)


def _biz_meta() -> dict:
    """读包内 biz.txt（打包时生成）。缺失或值不合法时返回空字典，静默降级。

    每个进程只读一次盘：包内标记不会被运行期改写，多读无益。
    """
    global _biz_meta_cache
    if _biz_meta_cache is not None:
        return _biz_meta_cache
    meta = {}
    try:
        with open(os.path.join(_skill_root(), BIZ_FILE), encoding="utf-8") as handle:
            for line in handle:
                key, _, value = line.strip().partition("=")
                value = value.strip()
                if key == "brand" and BIZ_RE.match(value):
                    meta["brand"] = value
                elif key == "kind" and value in BIZ_KINDS:
                    meta["kind"] = value
    except (OSError, UnicodeDecodeError):
        meta = {}
    _biz_meta_cache = meta
    return meta


def biz_headers() -> dict:
    """埋点头：只带包内标记里认得的字段。源码目录没 biz.txt 时为空。"""
    meta = _biz_meta()
    headers = {}
    if meta.get("brand"):
        headers[BIZ_HEADER] = meta["brand"]
    if meta.get("kind"):
        headers[KIND_HEADER] = meta["kind"]
    return headers


def post_json(path: str, payload: dict) -> dict:
    raw_out = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
    }
    headers.update(biz_headers())
    request = urllib.request.Request(
        api_base() + path,
        data=raw_out,
        headers=headers,
        method="POST",
    )
    status = 0
    raw = b""
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status = response.status
            raw = response.read()
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read()
    except (urllib.error.URLError, TimeoutError, OSError):
        fail(UNAVAILABLE)
    detail = ""
    body = None
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        parsed = None
    if isinstance(parsed, dict):
        body = parsed
        if parsed.get("error"):
            detail = str(parsed["error"])
    if status < 200 or status >= 300 or body is None:
        fail_unavailable(detail)
    return body


def _parse_args(argv):
    out_dir = os.environ.get("YIXUE_OUT_DIR") or ""
    year_override = None
    scheme = None
    place_code = None
    is_lunar = False
    leap_month = False
    positional = []
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--lunar":
            is_lunar = True
            index += 1
            continue
        if arg == "--leap":
            leap_month = True
            index += 1
            continue
        if arg == "--place-code" and index + 1 < len(argv):
            place_code = argv[index + 1]
            index += 2
            continue
        if arg.startswith("--place-code="):
            place_code = arg.split("=", 1)[1]
            index += 1
            continue
        if arg == "--out" and index + 1 < len(argv):
            out_dir = argv[index + 1]
            index += 2
            continue
        if arg.startswith("--out="):
            out_dir = arg.split("=", 1)[1]
            index += 1
            continue
        if arg == "--year" and index + 1 < len(argv):
            year_override = argv[index + 1]
            index += 2
            continue
        if arg.startswith("--year="):
            year_override = arg.split("=", 1)[1]
            index += 1
            continue
        if arg == "--scheme" and index + 1 < len(argv):
            scheme = argv[index + 1]
            index += 2
            continue
        if arg.startswith("--scheme="):
            scheme = arg.split("=", 1)[1]
            index += 1
            continue
        positional.append(arg)
        index += 1
    return positional, out_dir, year_override, scheme, place_code, is_lunar, leap_month


def _resolve_out_dir(explicit):
    candidates = []
    if explicit:
        candidates.append(explicit)
    else:
        candidates.append(os.path.join(os.getcwd(), DEFAULT_OUTPUT_DIRNAME))
    candidates.append(os.path.join(tempfile.gettempdir(), FALLBACK_DIRNAME))

    last_error = None
    for candidate in candidates:
        try:
            os.makedirs(candidate, exist_ok=True)
            probe = os.path.join(candidate, ".write-probe")
            with open(probe, "w", encoding="utf-8") as handle:
                handle.write("ok")
            os.remove(probe)
            return os.path.abspath(candidate)
        except OSError as exc:
            last_error = exc
    raise SystemExit(f"错误：没有可写的输出目录（最后失败原因：{last_error}）")


def _report_label(payload: dict) -> str:
    """把报告 JSON 里的 scheme 换成文件名里能看懂的中文类型；认不出就留空。"""
    scheme = payload.get("scheme")
    if isinstance(scheme, str):
        return REPORT_SCHEME_LABELS.get(scheme.strip(), "")
    return ""


def _report_path(directory: str, label: str) -> str:
    """报告名形如 图文报告-八字-2026-10-12.html；同日同类型重名时补序号，不覆盖已有文件。"""
    parts = [REPORT_FILENAME_PREFIX]
    if label:
        parts.append(label)
    parts.append(time.strftime("%Y-%m-%d"))
    base = "-".join(parts)
    candidate = os.path.join(directory, base + ".html")
    index = 2
    while os.path.exists(candidate):
        candidate = os.path.join(directory, f"{base}-{index}.html")
        index += 1
    return candidate


def _need(body, *keys):
    current = body
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            fail(UNAVAILABLE)
        current = current[key]
    return current


def _int(text, label):
    try:
        return int(text)
    except (TypeError, ValueError):
        fail(f"参数格式有误：{label} 须为整数。")


def _geo_dir() -> str:
    return os.path.join(_skill_root(), "references")


def _geo_version() -> str:
    try:
        with open(os.path.join(_geo_dir(), "geo-index.md"), encoding="utf-8") as handle:
            match = re.search(r"Version:\s*([^.\s]+)", handle.read())
    except OSError:
        match = None
    if not match:
        fail("经度表缺失：references/geo-index.md 读不到版本。")
    return match.group(1)


def lookup_place(code) -> dict:
    """按行政区划代码在技能包经度表里取经度和全称。"""
    code = str(code).strip()
    if not re.fullmatch(r"\d{6}", code):
        fail("参数格式有误：出生地代码须为 6 位数字，取自 references/geo-*.tsv。")
    for path in sorted(glob.glob(os.path.join(_geo_dir(), f"geo-{code[:2]}-*.tsv"))):
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                cols = line.rstrip("\n").split("\t")
                if len(cols) == 5 and cols[0] == code:
                    return {
                        "place_code": code,
                        "birth_place": cols[1],
                        "longitude": float(cols[3]),
                        "geo_version": _geo_version(),
                    }
    fail(f"经度表里没有代码 {code}。请回到 references/geo-*.tsv 重新查找，或请用户提供经度。")


def _apply_place(payload: dict, code) -> None:
    if "longitude" in payload:
        fail("参数格式有误：出生地代码与经度只能二选一。")
    payload.update(lookup_place(code))


def _birth(args, start, count, place_code=None, is_lunar=False, leap_month=False):
    """从位置参数取出 年 月 日 时 分 性别，以及可选经度；有出生地代码时按表取经度。"""
    year = _int(args[start], "年")
    month = _int(args[start + 1], "月")
    day = _int(args[start + 2], "日")
    hour = _int(args[start + 3], "时")
    minute = _int(args[start + 4], "分")
    sex = args[start + 5]
    if sex not in ("男", "女"):
        fail("参数格式有误：性别须为男或女。")
    payload = {
        "year": year,
        "month": month,
        "day": day,
        "hour": hour,
        "minute": minute,
        "sex": sex,
    }
    if is_lunar:
        payload["is_lunar"] = True
        if leap_month:
            payload["leap_month"] = True
    extra = args[start + count:]
    if extra:
        try:
            payload["longitude"] = float(extra[0])
        except ValueError:
            fail("参数格式有误：经度须为数字。出生地请先在 references/geo-*.tsv 查到代码，用 --place-code 传入。")
        if len(extra) > 1:
            payload["birth_place"] = extra[1]
    if place_code:
        _apply_place(payload, place_code)
    return payload


def _year_option(text):
    if text is None:
        return None
    return _int(text, "年份")


def _skill_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def _inside_skill(path: str) -> bool:
    try:
        return os.path.commonpath([os.path.abspath(path), _skill_root()]) == _skill_root()
    except ValueError:
        return False


def command_chart(args, out_option, year_override, scheme, place_code=None, is_lunar=False, leap_month=False):
    if scheme is not None:
        fail("排盘命令不接受 --scheme。方案写在报告 JSON 的 scheme 字段里。")
    if out_option:
        fail("排盘命令不写文件，不接受 --out。")
    if len(args) < 6:
        usage_fail("参数不足：排盘需要 年 月 日 时 分 性别 六项。")
    if len(args) > 8:
        fail("参数格式有误：排盘参数过多。")
    payload = _birth(args, 0, 6, place_code, is_lunar, leap_month)
    current_year = _year_option(year_override)
    if current_year is not None:
        payload["current_year"] = current_year
    body = post_json("/v1/chart", payload)
    _need(body, "chart", "基本信息", "当前年基准")
    _need(body, "chart", "基本信息", "历法")
    _need(body, "chart", "八字结构", "四柱")
    _need(body, "chart", "八字结构", "日主")
    _need(body, "chart", "八字结构", "地支关系")
    _need(body, "chart", "八字标注", "日主强弱")
    _need(body, "chart", "八字标注", "得令")
    _need(body, "chart", "八字标注", "格局")
    _need(body, "chart", "八字标注", "命格")
    _need(body, "report_facts", "mingge")
    _need(body, "chart", "八字标注", "十神分布")
    _need(body, "chart", "紫微结构", "定星")
    _need(body, "chart", "紫微标注", "命宫")
    _need(body, "chart", "紫微标注", "五行局")
    _need(body, "chart", "紫微标注", "格局")
    _need(body, "minggua", "bagua")
    _need(body, "minggua", "group")
    _need(body, "flying", "中宫星")
    _need(body, "report_facts", "solar")
    _need(body, "report_facts", "dayun")
    _need(body, "report_facts", "daxian")
    _need(body, "report_facts", "facets")
    brief = body.get("score_brief")
    if not isinstance(brief, str) or not brief.strip():
        fail(UNAVAILABLE)
    pillars = body["chart"]["八字结构"]["四柱"]
    if not isinstance(pillars, dict):
        fail(UNAVAILABLE)
    for key in "年月日时":
        column = pillars.get(key)
        if not isinstance(column, dict) or "gz" not in column:
            fail(UNAVAILABLE)
    print("计算完成。标准输出是可复算符号，不是解读。", file=sys.stderr)
    print(json.dumps(body, ensure_ascii=False, indent=2))


def command_render(args, out_option):
    if len(args) != 1:
        fail("参数格式有误：render 需要一个报告 JSON 路径。")
    source = args[0]
    try:
        with open(source, encoding="utf-8") as handle:
            payload = json.load(handle)
    except OSError:
        fail("参数格式有误：读不到报告 JSON。")
    except json.JSONDecodeError:
        fail("参数格式有误：报告 JSON 无法解析。")
    if not isinstance(payload, dict):
        fail("参数格式有误：报告 JSON 须为对象。")
    birth = payload.get("birth")
    if isinstance(birth, dict) and birth.get("place_code") is not None:
        birth = dict(birth)
        code = birth.pop("place_code")
        birth.pop("birth_place", None)
        _apply_place(birth, code)
        payload = dict(payload, birth=birth)
    body = post_json("/v1/report", payload)
    page = body.get("html")
    if not isinstance(page, str) or not page:
        fail(UNAVAILABLE)
    label = _report_label(payload)
    if out_option:
        dest = _report_path(_resolve_out_dir(out_option), label)
    else:
        dest = _report_path(os.path.dirname(os.path.abspath(source)), label)
    if _inside_skill(dest):
        fail("报告不能写进技能目录。")
    with open(dest, "w", encoding="utf-8") as handle:
        handle.write(page)
    print(f"HTML 报告: {dest}")


def command_liunian(args, place_code=None, is_lunar=False, leap_month=False):
    if len(args) < 7:
        usage_fail("参数不足：流年需要 年 月 日 时 分 性别 流年 七项。")
    if len(args) > 8:
        fail("参数格式有误：流年参数过多。")
    payload = _birth(args, 0, 7, place_code, is_lunar, leap_month)
    payload["target_year"] = _int(args[6], "流年")
    body = post_json("/v1/liunian", payload)
    _need(body, "八字")
    _need(body, "流年干支")
    print(json.dumps(body, ensure_ascii=False, indent=2))


def command_liuyue(args, place_code=None, is_lunar=False, leap_month=False):
    if len(args) < 8:
        usage_fail("参数不足：流月需要 年 月 日 时 分 性别 流年 月支 八项。")
    if len(args) > 9:
        fail("参数格式有误：流月参数过多。")
    payload = _birth(args, 0, 8, place_code, is_lunar, leap_month)
    payload["target_year"] = _int(args[6], "流年")
    month_zhi = _int(args[7], "月支")
    if month_zhi < 0 or month_zhi > 11:
        fail(MONTH_ZHI_RANGE)
    payload["month_zhi"] = month_zhi
    print(json.dumps(post_json("/v1/liuyue", payload), ensure_ascii=False, indent=2))


def command_fengshui(args, year_override):
    if len(args) < 2:
        usage_fail("参数不足：飞星需要 出生年 性别 两项，宅卦可选。")
    if len(args) > 3:
        fail("参数格式有误：飞星参数过多。")
    payload = {
        "year": _int(args[0], "出生年"),
        "sex": args[1],
    }
    if payload["sex"] not in ("男", "女"):
        fail("参数格式有误：性别须为男或女。")
    if len(args) == 3:
        payload["zhai"] = args[2]
    flying_year = _year_option(year_override)
    if flying_year is not None:
        payload["flying_year"] = flying_year
    print(json.dumps(post_json("/v1/fengshui", payload), ensure_ascii=False, indent=2))


def main(argv=None):
    args, out_option, year_override, scheme, place_code, is_lunar, leap_month = _parse_args(
        sys.argv[1:] if argv is None else argv
    )
    if leap_month and not is_lunar:
        fail("参数格式有误：--leap 只能与 --lunar 同时使用。")
    if place_code is not None and args and args[0] in ("render", "fengshui"):
        fail(f"{args[0]} 不接受 --place-code。报告的出生地代码写在 birth.place_code 里。")
    if (is_lunar or leap_month) and args and args[0] in ("render", "fengshui"):
        fail(f"{args[0]} 不接受 --lunar/--leap。报告的农历生日写在 birth 里。")
    if args and args[0] == "render":
        command_render(args[1:], out_option)
        return
    if args and args[0] == "liunian":
        command_liunian(args[1:], place_code, is_lunar, leap_month)
        return
    if args and args[0] == "liuyue":
        command_liuyue(args[1:], place_code, is_lunar, leap_month)
        return
    if args and args[0] == "fengshui":
        command_fengshui(args[1:], year_override)
        return
    command_chart(args, out_option, year_override, scheme, place_code, is_lunar, leap_month)


if __name__ == "__main__":
    main()

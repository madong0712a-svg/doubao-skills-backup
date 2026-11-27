#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dy-search-collector-kkai 离线回归测试

**完全离线**：通过 importlib 加载被测脚本，并把模块级 `http_post` 替换为假函数，
不发起任何真实请求、不需要 apikey、不消耗接口额度。

运行：
    python tests/test_dy_search_collect.py

覆盖：
  - 字段归一化（别名拼写 / 万-w-亿-k / 时长毫秒 / UTC+8 时间戳 / 缺失一律 null）
  - 请求次数（成功=理论最小；失败才补一次；绝不出现第 3 次；retry=0）
  - 不可重试错误不补发 + 反向断言「普通业务失败仍补发」
  - 403 裸 forbidden → action_forbidden；200+JSON403 / 401 → unauthorized
  - 业务正文（描述里写「1分钟」「余额不足」）不得污染错误判定
  - PHP 告警夹带在 JSON 之后仍能解析（对象与顶层数组两种形态）
  - 分页安全阀、三个凭据在页间整组传递、首页凭据为空、offset 首页为 0、跨页去重
  - 默认只采 1 页（硬规则）：pages_source / 自检提示 / 程序化调用同义 / 收敛
  - next_action（has_more / fatal_error）该出现与不该出现的边界
  - 关键词多词分隔（空格 / 逗号**不拆**）、去重、批量遇账户级错误立即中止
  - 筛选参数（publish_time / sort_type）编码归一化与未知值原样透传
  - 页码与页数区分（--page / --pages）+ 本地自检告警
  - CLI 端到端：退出码 0/1/2/3、stdout 纯 JSON、--human 走 stderr、apikey 不出现在输出
  - 静态安全：无 input() / subprocess / eval / exec / base64；仅一处 urlopen
  - 规范 12 项字段口径（顺序即输出顺序）+ 真实响应夹具回放
    （tests/real_2026-10-09_page1.json：16 条、视频 12 / 图文 4、含真实 PHP 告警）
  - 文档口径守卫：frontmatter 描述必须列全 12 项中文名
"""

import importlib.util
import io
import json
import os
import shlex
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "dy_search_collect.py")

_spec = importlib.util.spec_from_file_location("dy_search_collect", SCRIPT)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

# 真实的 http_post 引用：前面的用例会把 mod.http_post 换成假函数，
# 需要验证 http_post 自身行为时用它临时换回来。
REAL_POST = mod.http_post

CHECKS = {"n": 0, "failed": []}


def check(cond, msg):
    CHECKS["n"] += 1
    if not cond:
        CHECKS["failed"].append(msg)
        raise AssertionError("FAIL: %s" % msg)


def check_eq(actual, expected, msg):
    check(actual == expected, "%s（期望 %r，实际 %r）" % (msg, expected, actual))


# --------------------------------------------------------------------------
# 测试脚手架
# --------------------------------------------------------------------------

def make_post(dr_sequences, calls=None):
    """按 dr 分别消费响应；序列最后一项会被重复使用；记录 calls 供断言请求次数。"""
    state = {}

    def emit(item):
        if isinstance(item, tuple):      # (0, "网络失败", None)
            return item
        return 200, json.dumps(item, ensure_ascii=False), item

    def fake_post(dr, payload, apikey, timeout=None, heartbeat=True):
        if calls is not None:
            calls.append({"dr": dr, "payload": dict(payload), "timeout": timeout})
        seq = dr_sequences.get(dr) or [{"code": 200}]
        idx = min(state.get(dr, 0), len(seq) - 1)
        state[dr] = state.get(dr, 0) + 1
        return emit(seq[idx])

    return fake_post


def fake_video(aid=None, desc="测试描述", nickname="测试作者", create_time=1790244421,
               cover="https://cover.example/c.jpg", play="https://play.example/v.mp4",
               duration=87842, digg=29, comment=2, collect=45, share=4, share_url=None):
    """构造一条搜索结果的视频实体（字段拼写按需求方给的 12 项）。"""
    item = {
        "aweme_id": aid,
        "desc": desc,
        "create_time": create_time,
        "nickname": nickname,
        "video_cover": cover,
        "video_play_addr": play,
        "video_duration": duration,
        "digg_count": digg,
        "comment_count": comment,
        "collect_count": collect,
        "share_count": share,
    }
    if share_url:
        item["share_url"] = share_url
    return item


def page_payload(videos, backtrace=None, offset=None, search_id=None,
                 has_more=None, code=200, tips="成功，u.ai-gc.art", extra=None):
    body = {"code": code, "tips": tips, "aweme_info": videos}
    if backtrace is not None:
        body["backtrace"] = backtrace
    if offset is not None:
        body["offset"] = offset
    if search_id is not None:
        body["search_id"] = search_id
    if has_more is not None:
        body["has_more"] = has_more
    if extra:
        body.update(extra)
    return body


def isolated_key(tmpdir, key="TESTKEY_ABCDEF123456"):
    """把密钥读写重定向到临时目录，绝不碰用户真实密钥文件。"""
    mod.KEY_FILE = os.path.join(tmpdir, "ai-gc.art_apikey.txt")
    mod.LEGACY_KEY_FILES = []
    for name in mod.ENV_KEY_NAMES:
        os.environ.pop(name, None)
    if key is not None:
        with open(mod.KEY_FILE, "w", encoding="utf-8") as fh:
            fh.write(key)
    return key


def run_cli(argv):
    """跑一次 CLI，返回 (退出码, stdout, stderr)。"""
    out, err = io.StringIO(), io.StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = out, err
    try:
        code = mod.main(argv)
    finally:
        sys.stdout, sys.stderr = old_out, old_err
    return code, out.getvalue(), err.getvalue()


def with_key_and_post(sequences, calls=None):
    """临时把 http_post 换成假函数，并返回恢复函数。"""
    original = mod.http_post
    mod.http_post = make_post(sequences, calls)
    return lambda: setattr(mod, "http_post", original)


# --------------------------------------------------------------------------
# 1. 字段归一化
# --------------------------------------------------------------------------

def test_field_normalization():
    raw = {
        "aweme_id": "7681785244026015018",
        "desc": "  0基础，带你做出你人生第一个AI视频！  ",
        "create_time": 1790244421,
        "nickname": "Ksr桑",
        "video_cover": "https://cover.example/a.jpg",
        "video_play_addr": "https://play.example/a.mp4",
        "video_duration": 87842,
        "digg_count": "1.2万",
        "comment_count": "1,234",
        "collect_count": "5.6w",
        "share_count": "3k",
        "share_url": "https://www.douyin.com/video/7681785244026015018",
    }
    video = mod.build_video(raw, 1, 1)
    check_eq(video["aweme_id"], "7681785244026015018", "aweme_id 提取")
    check_eq(video["desc"], "0基础，带你做出你人生第一个AI视频！", "desc 去空白")
    check_eq(video["create_time"], "2026-09-24 18:07:01", "Unix 秒按 UTC+8 转换")
    check_eq(video["create_time_ts"], 1790244421, "保留原始时间戳（秒）")
    check_eq(video["video_duration"], 87842, "video_duration 原值保留")
    check_eq(video["video_duration_ms"], 87842, "video_duration_ms")
    check_eq(video["video_duration_text"], "01:28", "87842ms -> 01:28")
    check_eq(video["video_duration_unit"], "ms", "时长单位口径标注")
    check_eq(video["digg_count"], 12000, "1.2万 -> 12000")
    check_eq(video["comment_count"], 1234, "1,234 -> 1234")
    check_eq(video["collect_count"], 56000, "5.6w -> 56000")
    check_eq(video["share_count"], 3000, "3k -> 3000")
    check_eq(video["share_url"], "https://www.douyin.com/video/7681785244026015018",
             "分享链接")
    check_eq(video["video_url"], "https://www.douyin.com/video/7681785244026015018",
             "无站点 aweme_url 时本地拼接 video_url")
    check_eq(video["page"], 1, "page")
    check_eq(video["index"], 1, "index")

    # 站点返回 aweme_url 时优先用它
    with_url = mod.build_video({"aweme_id": "1" * 19,
                                "aweme_url": "https://www.douyin.com/video/aaa"}, 2, 3)
    check_eq(with_url["video_url"], "https://www.douyin.com/video/aaa",
             "video_url 优先用站点 aweme_url")

    # 封面可能是对象数组（同站点媒体字段惯用形态）
    obj_cover = mod.build_video(
        {"aweme_id": "1" * 19,
         "video_cover": {"url_list": ["https://c.example/1.jpg",
                                      "https://c.example/2.jpg"]}}, 1, 1)
    check_eq(obj_cover["video_cover"], "https://c.example/1.jpg",
             "封面对象数组取首个 URL")

    # 空串封面 → null（站点实测常见）
    empty_cover = mod.build_video(
        {"aweme_id": "1" * 19, "video_cover": "", "video_play_addr": ""}, 1, 1)
    check_eq(empty_cover["video_cover"], None, "空串封面 -> null（不编造）")
    check_eq(empty_cover["video_play_addr"], None, "空串播放地址 -> null")

    # 缺失字段一律 null（不编造 0）
    empty = mod.build_video({"aweme_id": "1" * 19}, 1, 1)
    for field in ("desc", "nickname", "create_time", "collect_count",
                  "comment_count", "share_count", "share_url"):
        check_eq(empty[field], None, "缺失 %s -> null（不编造 0）" % field)

    # 毫秒时间戳按量级识别
    ms = mod.build_video({"aweme_id": "1" * 19, "create_time": 1790244421000}, 1, 1)
    check_eq(ms["create_time"], "2026-09-24 18:07:01", "毫秒时间戳按毫秒解释")
    check_eq(ms["create_time_ts"], 1790244421, "毫秒时间戳归一为秒 ts")

    # 日期字符串原样保留
    ds = mod.build_video({"aweme_id": "1" * 19,
                          "create_time": "2026-09-24 18:07:01"}, 1, 1)
    check_eq(ds["create_time"], "2026-09-24 18:07:01", "日期字符串原样保留")
    check_eq(ds["create_time_ts"], None, "非时间戳形态 ts 为 None")

    # 时长字符串形态也能解析
    txt = mod.build_video({"aweme_id": "1" * 19, "video_duration": "01:28"}, 1, 1)
    check_eq(txt["video_duration_text"], "01:28", "时长字符串 01:28 解析")
    check_eq(txt["video_duration_ms"], 88000, "01:28 -> 88000ms")

    # video_is_meaningful：空壳不算有效记录
    check(not mod.video_is_meaningful(mod.build_video({}, 1, 1)),
          "空壳记录判定为无效")
    check(mod.video_is_meaningful(mod.build_video({"aweme_id": "1" * 19}, 1, 1)),
          "仅有主键也算有效记录")


# --------------------------------------------------------------------------
# 2. 请求次数（成功路径 = 理论最小）
# --------------------------------------------------------------------------

def test_request_counts():
    # 默认 1 页 = 1 次请求
    calls = []
    restore = with_key_and_post(
        {mod.DR_SEARCH: [page_payload([fake_video("1" * 19)], offset=20,
                                      has_more=1)]}, calls)
    try:
        r = mod.collect_keyword("WorkBuddy教程", apikey="K", pages=None)
    finally:
        restore()
    check_eq(len(calls), 1, "默认 1 页只发 1 次请求")
    check_eq(r["request_count"], 1, "request_count")
    check_eq(r["retry_count"], 0, "retry_count")
    check_eq(r["pages_fetched"], 1, "pages_fetched")

    # 采 3 页 = 3 次请求（每页成功不补发）
    calls = []
    seq = [page_payload([fake_video("1" * 19)], offset=20, has_more=1),
           page_payload([fake_video("2" * 19)], offset=40, has_more=1),
           page_payload([fake_video("3" * 19)], offset=60, has_more=0)]
    restore = with_key_and_post({mod.DR_SEARCH: seq}, calls)
    try:
        r = mod.collect_keyword("kw", apikey="K", pages=3)
    finally:
        restore()
    check_eq(len(calls), 3, "3 页成功 = 3 次请求")
    check_eq(r["video_count"], 3, "3 页共 3 条")
    check(r["exhausted"], "has_more=0 判定末页")

    # 首页请求 offset 必须是数字 0（不是空串）
    check_eq(calls[0]["payload"]["offset"], 0, "首页 offset 传数字 0")
    check_eq(calls[0]["payload"]["backtrace"], "", "首页 backtrace 传空串")
    check_eq(calls[0]["payload"]["search_id"], "", "首页 search_id 传空串")
    check_eq(calls[0]["payload"]["page"], 1, "首页 page=1")

    # 失败后补一次成功 => +1 次
    calls = []
    seq = [(0, "网络请求失败: 连接被拒", None),
           page_payload([fake_video("1" * 19)], has_more=0)]
    restore = with_key_and_post({mod.DR_SEARCH: seq}, calls)
    try:
        r = mod.collect_keyword("kw", apikey="K", pages=1, retry_delay=0)
    finally:
        restore()
    check_eq(len(calls), 2, "失败后补发一次成功 = 2 次请求")
    check_eq(r["retry_count"], 1, "retry_count=1")
    check(r["ok"], "补发成功则 ok")

    # 两步都失败：绝不出现第 3 次尝试
    calls = []
    restore = with_key_and_post({mod.DR_SEARCH: [(0, "网络请求失败", None)]}, calls)
    try:
        r = mod.collect_keyword("kw", apikey="K", pages=1, retry_delay=0)
    finally:
        restore()
    check_eq(len(calls), 2, "每步最多首发 1 次 + 补发 1 次，绝无第 3 次")
    check(not r["ok"], "两次都失败 -> ok=False")

    # retry=0：完全关闭补发，只发一轮
    calls = []
    restore = with_key_and_post({mod.DR_SEARCH: [(0, "网络请求失败", None)]}, calls)
    try:
        mod.collect_keyword("kw", apikey="K", pages=1, retry=0, retry_delay=0)
    finally:
        restore()
    check_eq(len(calls), 1, "retry=0 时失败也不补发")

    # 多页：其中一页失败后补发成功，成功页不重跑
    calls = []
    seq = [page_payload([fake_video("1" * 19)], offset=20, has_more=1),
           (0, "网络请求失败", None),
           page_payload([fake_video("2" * 19)], offset=40, has_more=0)]
    restore = with_key_and_post({mod.DR_SEARCH: seq}, calls)
    try:
        r = mod.collect_keyword("kw", apikey="K", pages=2, retry_delay=0)
    finally:
        restore()
    check_eq(len(calls), 3, "第 1 页成功 1 次 + 第 2 页失败补发 1 次 = 3 次")
    check_eq(r["video_count"], 2, "两页都取到")


# --------------------------------------------------------------------------
# 3. 不可重试错误
# --------------------------------------------------------------------------

def test_non_retryable_errors():
    cases = [
        # (响应, 期望 error_code)
        ({"code": 403, "tips": "访问被拒绝: 无效的apikey，请登录 u.ai-gc.art 获取"},
         "unauthorized"),
        ({"code": 402, "tips": "余额不足，请登录 u.ai-gc.art ，请充值后重试"},
         "insufficient_balance"),
        ({"code": 404, "tips": "404,API 请求失败,请10分钟后，再重试"},
         "upstream_busy"),
    ]
    for body, expected in cases:
        calls = []
        restore = with_key_and_post({mod.DR_SEARCH: [body]}, calls)
        try:
            r = mod.collect_keyword("kw", apikey="K", pages=1, retry_delay=0)
        finally:
            restore()
        check_eq(len(calls), 1, "%s：不可重试错误只发 1 次" % expected)
        check_eq(r["retry_count"], 0, "%s：retry_count=0" % expected)
        check_eq(r["errors"][0]["error_code"], expected, "%s：错误分类" % expected)
        check(r["errors"][0].get("action_required"), "%s：带 action_required" % expected)

    # HTTP 403 + 裸文本 forbidden -> action_forbidden（与 apikey 无关），只发 1 次
    calls = []

    def fake_forbidden(dr, payload, apikey, timeout=None, heartbeat=True):
        calls.append(dr)
        return 403, "forbidden", None

    original = mod.http_post
    mod.http_post = fake_forbidden
    try:
        r = mod.collect_keyword("kw", apikey="K", pages=1, retry_delay=0)
    finally:
        mod.http_post = original
    check_eq(len(calls), 1, "403 裸 forbidden 只发 1 次")
    check_eq(r["errors"][0]["error_code"], "action_forbidden", "403 裸 forbidden 分类")
    check("不要重新获取 apikey" in r["errors"][0]["action_required"],
          "action_forbidden 提示不要重新获取 apikey")

    # 反向：普通业务失败（服务器繁忙）仍会补发一次
    calls = []
    restore = with_key_and_post(
        {mod.DR_SEARCH: [{"code": 500, "tips": "服务器繁忙，请稍后重试"}]}, calls)
    try:
        r = mod.collect_keyword("kw", apikey="K", pages=1, retry_delay=0)
    finally:
        restore()
    check_eq(len(calls), 2, "普通业务失败仍补发一次")
    check_eq(r["retry_count"], 1, "普通业务失败 retry_count=1")


def test_error_classification_not_mixed():
    calls = []

    def mk(status, body):
        def fake(dr, payload, apikey, timeout=None, heartbeat=True):
            calls.append(status)
            return status, body, None
        return fake

    original = mod.http_post
    # 403 但响应体是 JSON -> 仍归 unauthorized
    try:
        mod.http_post = mk(403, json.dumps({"code": 403, "tips": "无效的apikey",
                                            "aweme_info": []}))
        r = mod.collect_keyword("kw", apikey="K", pages=1, retry_delay=0)
    finally:
        mod.http_post = original
    check_eq(r["errors"][0]["error_code"], "unauthorized",
             "403 + JSON 响应体仍归 unauthorized")

    # 401 + missing api key -> unauthorized
    try:
        mod.http_post = mk(401, "missing api key")
        r = mod.collect_keyword("kw", apikey="K", pages=1, retry_delay=0)
    finally:
        mod.http_post = original
    check_eq(r["errors"][0]["error_code"], "unauthorized", "401 missing api key -> unauthorized")


# --------------------------------------------------------------------------
# 4. 业务正文不污染错误判定（真实事故回归）
# --------------------------------------------------------------------------

def test_business_text_does_not_pollute_error():
    poisonous = [
        "0基础，1分钟教你做出第一个AI视频（余额不足？不存在的）",
        "apikey 无效怎么办？看完这条视频你就懂了",
        "遇到限流别慌，10分钟后再试即可",
        "稍后再试？不，今天就把 WorkBuddy 教程讲完",
    ]
    videos = [fake_video(str(i) * 19, desc=d) for i, d in enumerate(poisonous, 1)]
    calls = []
    restore = with_key_and_post(
        {mod.DR_SEARCH: [page_payload(videos, has_more=0)]}, calls)
    try:
        r = mod.collect_keyword("kw", apikey="K", pages=1)
    finally:
        restore()
    check(r["ok"], "描述里含错误关键词不影响成功判定")
    check_eq(len(r["errors"]), 0, "成功响应不产生 errors")
    check_eq(len(calls), 1, "成功响应不触发补发")
    check_eq(r["video_count"], 4, "4 条全部保留")

    # 反向：真正的限流文案仍被识别
    restore = with_key_and_post(
        {mod.DR_SEARCH: [{"code": 404, "tips": "404,API 请求失败,请10分钟后，再重试"}]})
    try:
        r2 = mod.collect_keyword("kw", apikey="K", pages=1, retry_delay=0)
    finally:
        restore()
    check_eq(r2["errors"][0]["error_code"], "upstream_busy", "真限流文案仍被识别")

    # _error_blob 只含提示字段
    parsed = {"code": 200, "tips": "成功",
              "aweme_info": [{"desc": "余额不足 1分钟 稍后再试"}]}
    blob = mod._error_blob(parsed, json.dumps(parsed, ensure_ascii=False))
    check("余额不足" not in blob, "业务正文不进入 error blob")
    check("1分钟" not in blob, "业务正文的「1分钟」不进入 error blob")


# --------------------------------------------------------------------------
# 5. PHP 告警容错
# --------------------------------------------------------------------------

def test_php_warning_tolerance():
    warning = ("<br /><b>Warning</b>: Cannot modify header information - headers "
               "already sent by (output started at /www/rd.php:157) in "
               "/www/rd.php on line 157")
    # 对象形态
    body = json.dumps(page_payload([fake_video("1" * 19)], has_more=0),
                      ensure_ascii=False) + warning
    parsed = mod._loads_tolerant(body)
    check(isinstance(parsed, dict), "对象 + PHP 告警仍解析为 dict")
    check_eq(parsed["code"], 200, "解析出的 code 正确")

    # 顶层数组形态（站点第一步常见）
    arr = json.dumps([{"url": "https://www.douyin.com/user/xxx",
                       "sec_user_id": "MS4wLjABAAAA"}], ensure_ascii=False) + warning
    parsed_arr = mod._loads_tolerant(arr)
    check(isinstance(parsed_arr, list), "顶层数组 + PHP 告警仍解析为 list")
    check_eq(parsed_arr[0]["sec_user_id"], "MS4wLjABAAAA", "数组内容正确")

    # 通过 http_post 端到端走一遍
    def fake(dr, payload, apikey, timeout=None, heartbeat=True):
        return 200, body, mod._loads_tolerant(body)

    original = mod.http_post
    mod.http_post = fake
    try:
        r = mod.collect_keyword("kw", apikey="K", pages=1)
    finally:
        mod.http_post = original
    check(r["ok"], "夹带 PHP 告警的响应仍能成功采到视频")
    check_eq(r["video_count"], 1, "告警响应里的 1 条视频被采到")


# --------------------------------------------------------------------------
# 6. 分页安全阀与凭据传递
# --------------------------------------------------------------------------

def test_pagination_safety_valves():
    # ① 空页 -> 停止翻页
    calls = []
    seq = [page_payload([fake_video("1" * 19)], offset=20, has_more=1),
           page_payload([], offset=40, has_more=1)]
    restore = with_key_and_post({mod.DR_SEARCH: seq}, calls)
    try:
        r = mod.collect_keyword("kw", apikey="K", pages=5)
    finally:
        restore()
    check_eq(len(calls), 2, "空页触发停止（只发 2 次）")
    check(r["exhausted"], "空页 -> exhausted=True")

    # ② has_more=false -> 停止翻页
    calls = []
    seq = [page_payload([fake_video("1" * 19)], offset=20, has_more=0)]
    restore = with_key_and_post({mod.DR_SEARCH: seq}, calls)
    try:
        r = mod.collect_keyword("kw", apikey="K", pages=5)
    finally:
        restore()
    check_eq(len(calls), 1, "has_more=false 立即停止（只发 1 次）")
    check(r["exhausted"], "has_more=false -> exhausted=True")

    # ③ 凭据全空 且 has_more 不是 True -> 停止
    calls = []
    seq = [page_payload([fake_video("1" * 19)], offset=0, has_more=None)]
    restore = with_key_and_post({mod.DR_SEARCH: seq}, calls)
    try:
        r = mod.collect_keyword("kw", apikey="K", pages=5)
    finally:
        restore()
    check_eq(len(calls), 1, "凭据全空且未标记还有更多 -> 停止")
    check(r["exhausted"], "凭据全空 -> exhausted=True")

    # ④ 本页全重复 -> 停止
    dup = fake_video("7" * 19)
    calls = []
    seq = [page_payload([dup], offset=20, has_more=1),
           page_payload([dup], offset=40, has_more=1)]
    restore = with_key_and_post({mod.DR_SEARCH: seq}, calls)
    try:
        r = mod.collect_keyword("kw", apikey="K", pages=5)
    finally:
        restore()
    check_eq(len(calls), 2, "整页重复触发停止")
    check_eq(r["video_count"], 1, "跨页去重后只剩 1 条")
    check_eq(r["video_duplicates_removed"], 1, "video_duplicates_removed=1")

    # 三个凭据整组在页间传递
    calls = []
    seq = [page_payload([fake_video("1" * 19)], backtrace="bt1", offset=20,
                        search_id="sid1", has_more=1),
           page_payload([fake_video("2" * 19)], backtrace="bt2", offset=40,
                        search_id="sid2", has_more=0)]
    restore = with_key_and_post({mod.DR_SEARCH: seq}, calls)
    try:
        r = mod.collect_keyword("kw", apikey="K", pages=2)
    finally:
        restore()
    check_eq(calls[1]["payload"]["backtrace"], "bt1", "第 2 页带第 1 页 backtrace")
    check_eq(calls[1]["payload"]["offset"], 20, "第 2 页带第 1 页 offset")
    check_eq(calls[1]["payload"]["search_id"], "sid1", "第 2 页带第 1 页 search_id")
    check_eq(calls[1]["payload"]["page"], 2, "第 2 页 page=2")
    # 站点返回什么就如实记什么：末页虽带凭据，但 has_more=0 已判定到底，
    # next_action 必须为 None（不误问），凭据原值保留便于排查。
    check_eq(r["next_backtrace"], "bt2", "next_backtrace 如实保留站点返回值")
    check_eq(r["next_offset"], "40", "next_offset 如实保留站点返回值（归一为字符串）")
    check(r["next_action"] is None, "已到末页 -> 不追问（即便响应带了凭据）")

    # 整页重复时不做「凭据不变即停」的误判：凭据变了但内容重复，仍靠重复判定停止
    calls = []
    dup2 = fake_video("8" * 19)
    seq = [page_payload([dup2], backtrace="bt1", offset=20, has_more=1),
           page_payload([dup2], backtrace="bt1", offset=20, has_more=1)]
    restore = with_key_and_post({mod.DR_SEARCH: seq}, calls)
    try:
        r = mod.collect_keyword("kw", apikey="K", pages=5)
    finally:
        restore()
    check(r["exhausted"], "内容重复 -> 停止")


# --------------------------------------------------------------------------
# 7. 默认只采 1 页（硬规则）
# --------------------------------------------------------------------------

def test_default_one_page_rule():
    # ① 不传 pages：只 1 页、pages_source=default、有自检提示、给出 next_action
    calls = []
    seq = [page_payload([fake_video("1" * 19)], backtrace="bt1", offset=20,
                        search_id="sid1", has_more=1)]
    restore = with_key_and_post({mod.DR_SEARCH: seq}, calls)
    try:
        r = mod.collect_keyword("kw", apikey="K")          # pages 不传
    finally:
        restore()
    check_eq(len(calls), 1, "未指定页数只发 1 次请求")
    check_eq(r["pages_source"], "default", "pages_source=default")
    check_eq(r["pages_requested"], 1, "pages_requested=1")
    check_eq(r["video_count"], 1, "取到 1 条")
    check(r["next_action"] is not None, "未指定页数且还有更多 -> 给出 next_action")
    check("没有指定采集页数" in r["next_action"]["question"],
          "问话点明「没有指定采集页数」")
    check_eq(r["next_action"]["resume_page"], 2, "续采页码为 2")
    check("--backtrace" in r["next_action"]["suggested_command"],
          "续采命令带 --backtrace")
    check("--offset" in r["next_action"]["suggested_command"], "续采命令带 --offset")
    check("--search-id" in r["next_action"]["suggested_command"],
          "续采命令带 --search-id")

    # 程序化调用传 pages=None 与「未说明」同义
    calls = []
    restore = with_key_and_post({mod.DR_SEARCH: seq}, calls)
    try:
        r = mod.collect_keyword("kw", apikey="K", pages=None)
    finally:
        restore()
    check_eq(len(calls), 1, "pages=None 同「未说明」，只发 1 次")
    check_eq(r["pages_source"], "default", "pages=None -> pages_source=default")

    # ② 未说明且已到末页 -> next_action 为 None（不误问）
    calls = []
    seq = [page_payload([fake_video("1" * 19)], has_more=0)]
    restore = with_key_and_post({mod.DR_SEARCH: seq}, calls)
    try:
        r = mod.collect_keyword("kw", apikey="K")
    finally:
        restore()
    check(r["next_action"] is None, "未指定页数但已到末页 -> 不追问")
    check(r["exhausted"], "exhausted=True")

    # ③ 明确 pages=3 -> pages_source=explicit
    calls = []
    seq = [page_payload([fake_video("1" * 19)], offset=20, has_more=1),
           page_payload([fake_video("2" * 19)], offset=40, has_more=1),
           page_payload([fake_video("3" * 19)], offset=60, has_more=1)]
    restore = with_key_and_post({mod.DR_SEARCH: seq}, calls)
    try:
        r = mod.collect_keyword("kw", apikey="K", pages=3)
    finally:
        restore()
    check_eq(len(calls), 3, "明确 3 页 = 3 次请求")
    check_eq(r["pages_source"], "explicit", "pages_source=explicit")
    check(r["next_action"] is not None, "跑满页数但还有更多 -> 仍给 next_action")
    check("已采集 3 页" in r["next_action"]["question"],
          "explicit 问话为「已采集 N 页」")

    # ④ 程序化调用传具体页数 -> explicit
    calls = []
    restore = with_key_and_post({mod.DR_SEARCH: seq}, calls)
    try:
        r = mod.collect_keyword("kw", apikey="K", pages=2)
    finally:
        restore()
    check_eq(r["pages_source"], "explicit", "程序化传页数 -> explicit")

    # ⑤ pages 收敛
    check_eq(mod.clamp_pages(None), 1, "clamp_pages(None) -> 1")
    check_eq(mod.clamp_pages(0), 1, "clamp_pages(0) -> 1")
    check_eq(mod.clamp_pages(999), 50, "clamp_pages(999) -> 50")
    check_eq(mod.clamp_start_page(0), 1, "clamp_start_page(0) -> 1")


# --------------------------------------------------------------------------
# 8. next_action 边界
# --------------------------------------------------------------------------

def test_next_action_boundaries():
    # 还有更多 -> 出现
    calls = []
    seq = [page_payload([fake_video("1" * 19)], backtrace="bt", offset=20,
                        has_more=1)]
    restore = with_key_and_post({mod.DR_SEARCH: seq}, calls)
    try:
        r = mod.collect_keyword("kw", apikey="K", pages=1)
    finally:
        restore()
    check(r["next_action"] is not None, "还有更多 -> next_action 出现")
    check_eq(r["next_action"]["ask_user"], True, "ask_user=True")
    check_eq(r["next_action"]["reason"], "has_more", "reason=has_more")
    check(r["next_action"].get("cost_hint"), "带 cost_hint")
    check(r["next_action"].get("stop_hint"), "带 stop_hint")

    # 无凭据 -> 不出现
    calls = []
    seq = [page_payload([fake_video("1" * 19)], offset=0, has_more=None)]
    restore = with_key_and_post({mod.DR_SEARCH: seq}, calls)
    try:
        r = mod.collect_keyword("kw", apikey="K", pages=1)
    finally:
        restore()
    check(r["next_action"] is None, "无翻页凭据 -> 不追问")

    # 空结果 -> 不出现
    calls = []
    seq = [page_payload([], has_more=None)]
    restore = with_key_and_post({mod.DR_SEARCH: seq}, calls)
    try:
        r = mod.collect_keyword("kw", apikey="K", pages=1)
    finally:
        restore()
    check(r["next_action"] is None, "空结果 -> 不追问")
    check(not r["ok"], "空结果 ok=False")

    # 失败 -> 不出现
    calls = []
    restore = with_key_and_post({mod.DR_SEARCH: [{"code": 403, "tips": "无效的apikey"}]},
                                calls)
    try:
        r = mod.collect_keyword("kw", apikey="K", pages=1, retry_delay=0)
    finally:
        restore()
    check(r["next_action"] is None, "失败 -> 不追问")

    # 脚本内不得有 input()
    src = open(SCRIPT, encoding="utf-8").read()
    check("input(" not in src, "脚本内不得出现 input()（会挂住 Agent 调用）")


# --------------------------------------------------------------------------
# 9. 批量与平铺
# --------------------------------------------------------------------------

def test_batch_abort_and_next_action():
    # 批量撞账户级错误 -> 立即中止
    calls = []
    seq = [{"code": 402, "tips": "余额不足，请登录 u.ai-gc.art ，请充值后重试"}]
    restore = with_key_and_post({mod.DR_SEARCH: seq}, calls)
    try:
        r = mod.collect_keyword("kw", apikey="K", pages=1, retry_delay=0)
    finally:
        restore()
    check(not r["ok"], "余额不足 -> ok=False")
    batch = mod.build_batch_next_action([r], skipped_keywords=["kw2", "kw3"], pages=1)
    check(batch is not None, "批量撞 fatal 错误 -> 给出 next_action")
    check_eq(batch["reason"], "fatal_error", "reason=fatal_error")
    check_eq(batch["keywords"], ["kw2", "kw3"], "剩余关键词")
    check("--keyword" in batch["suggested_command"], "续采命令带 --keyword")

    # 无 fatal 错误 -> 不给批量 next_action
    ok_result = {"ok": True, "errors": []}
    check(mod.build_batch_next_action([ok_result], skipped_keywords=["kw2"]) is None,
          "无 fatal 错误 -> 不给批量 next_action")
    check(mod.build_batch_next_action([r], skipped_keywords=[]) is None,
          "无剩余关键词 -> 不给批量 next_action")


# --------------------------------------------------------------------------
# 10. 关键词解析
# --------------------------------------------------------------------------

def test_keyword_parsing():
    check_eq(mod.split_keywords("WorkBuddy教程"), ["WorkBuddy教程"], "单个关键词")
    check_eq(mod.split_keywords("AI视频|AI绘画"), ["AI视频", "AI绘画"], "竖线分隔")
    check_eq(mod.split_keywords("AI视频;AI绘画"), ["AI视频", "AI绘画"], "分号分隔")
    check_eq(mod.split_keywords("AI视频\nAI绘画"), ["AI视频", "AI绘画"], "换行分隔")
    # ⚠️ 空格与逗号不拆（关键词本身可能含空格）
    check_eq(mod.split_keywords("AI 视频 教程"), ["AI 视频 教程"],
             "空格不被当作分隔符")
    check_eq(mod.split_keywords("猫,狗 训练"), ["猫,狗 训练"],
             "逗号不被当作分隔符")
    check_eq(mod.split_keywords("  前后空白  "), ["前后空白"], "去首尾空白")
    check_eq(mod.split_keywords("a|a|b"), ["a", "a", "b"], "同值不去重（去重在上层）")


# --------------------------------------------------------------------------
# 11. 筛选参数归一化
# --------------------------------------------------------------------------

def test_filter_normalization():
    # publish_time：站点取值是编码 _0 / _1 / _7 / _180
    check_eq(mod.normalize_publish_time(""), "_0", "空 -> _0")
    check_eq(mod.normalize_publish_time("一天内"), "_1", "一天内 -> _1")
    check_eq(mod.normalize_publish_time("一周内"), "_7", "一周内 -> _7")
    check_eq(mod.normalize_publish_time("半年内"), "_180", "半年内 -> _180")
    check_eq(mod.normalize_publish_time("7天"), "_7", "7天 -> _7")
    check_eq(mod.normalize_publish_time("_180"), "_180", "已是编码原样保留")
    check_eq(mod.normalize_publish_time("weird_value"), "weird_value",
             "未知写法原样透传")
    check_eq(mod.publish_time_label("_1"), "一天之内", "publish_time 展示名")

    # sort_type：站点取值是编码 _0 / _1 / _2
    check_eq(mod.normalize_sort_type(""), "_0", "空 -> _0（综合）")
    check_eq(mod.normalize_sort_type("最多点赞"), "_1", "最多点赞 -> _1")
    check_eq(mod.normalize_sort_type("最新发布"), "_2", "最新发布 -> _2")
    check_eq(mod.normalize_sort_type("最热"), "_1", "最热 -> _1")
    check_eq(mod.normalize_sort_type("_2"), "_2", "已是编码原样保留")
    check_eq(mod.normalize_sort_type("xxx"), "xxx", "未知写法原样透传")
    check_eq(mod.sort_type_label("_2"), "最新发布", "sort_type 展示名")


# --------------------------------------------------------------------------
# 12. 页码与页数区分 + 本地自检
# --------------------------------------------------------------------------

def test_page_semantics():
    # clamp_start_page / start_page_is_reasonable
    check_eq(mod.clamp_start_page(3), 3, "clamp_start_page 保留 3")
    check_eq(mod.clamp_start_page(-1), 1, "clamp_start_page 负值 -> 1")
    check(mod.start_page_is_reasonable(10), "页码 10 合理")
    check(not mod.start_page_is_reasonable(999), "页码 999 不合理（疑似误填页数）")

    # 从第 3 页起采却没带凭据 -> 本地告警（零额度），但仍然发请求
    calls = []
    seq = [page_payload([fake_video("1" * 19)], has_more=0)]
    restore = with_key_and_post({mod.DR_SEARCH: seq}, calls)
    try:
        r = mod.collect_keyword("kw", apikey="K", pages=1, start_page=3)
    finally:
        restore()
    check(any("未提供翻页凭据" in w for w in r["warnings"]),
          "第 N 页无凭据 -> 本地告警")
    check_eq(len(calls), 1, "自检告警不改变实际请求（仍发 1 次）")
    check_eq(calls[0]["payload"]["page"], 3, "请求页码确为 3")

    # 页码超常规上限 -> 告警（疑似把页数填进 --page）
    calls = []
    restore = with_key_and_post({mod.DR_SEARCH: seq}, calls)
    try:
        r = mod.collect_keyword("kw", apikey="K", pages=1, start_page=999)
    finally:
        restore()
    check(any("误填" in w for w in r["warnings"]), "页码超上限 -> 疑似误填告警")

    # --page 3 --pages 2 = 采第 3、4 页
    calls = []
    seq2 = [page_payload([fake_video("1" * 19)], offset=20, has_more=1),
            page_payload([fake_video("2" * 19)], offset=40, has_more=0)]
    restore = with_key_and_post({mod.DR_SEARCH: seq2}, calls)
    try:
        r = mod.collect_keyword("kw", apikey="K", pages=2, start_page=3,
                                start_backtrace="bt", start_offset=20,
                                start_search_id="sid")
    finally:
        restore()
    check_eq([c["payload"]["page"] for c in calls], [3, 4],
             "--page 3 --pages 2 请求第 3、4 页")
    check_eq(r["start_page"], 3, "start_page=3")
    check_eq(r["next_page"], 5, "next_page=5")


# --------------------------------------------------------------------------
# 13. CLI 端到端
# --------------------------------------------------------------------------

def test_cli_end_to_end():
    tmp = tempfile.mkdtemp(prefix="dysearch_test_")
    try:
        # 缺 apikey -> 退出码 3，且零请求
        isolated_key(tmp, key=None)
        calls = []
        restore = with_key_and_post({mod.DR_SEARCH: [page_payload([])]}, calls)
        try:
            code, out, err = run_cli(["--keyword", "kw"])
        finally:
            restore()
        check_eq(code, 3, "缺 apikey 退出码 3")
        check_eq(len(calls), 0, "缺 apikey 零请求")
        payload = json.loads(out)
        check_eq(payload["error"], "missing_apikey", "missing_apikey 提示")

        # 无关键词 -> 退出码 2
        isolated_key(tmp)
        code, out, err = run_cli([])
        check_eq(code, 2, "无关键词退出码 2")

        # 正常采集（默认 1 页）-> 退出码 0，stdout 纯 JSON
        isolated_key(tmp)
        calls = []
        seq = [page_payload([fake_video("1" * 19)], backtrace="bt", offset=20,
                            search_id="sid", has_more=1)]
        restore = with_key_and_post({mod.DR_SEARCH: seq}, calls)
        try:
            code, out, err = run_cli(["--keyword", "WorkBuddy教程"])
        finally:
            restore()
        check_eq(code, 0, "成功退出码 0")
        payload = json.loads(out)          # stdout 必须是纯 JSON
        check_eq(payload["ok"], True, "ok=True")
        check_eq(payload["pages_source"], "default", "CLI 默认 pages_source=default")
        check_eq(payload["video_count"], 1, "CLI 取到 1 条")
        check_eq(payload["total_videos"], 1, "total_videos")
        check(payload["next_action"] is not None, "CLI 给出 next_action")
        check_eq(payload["filters"]["publish_time"], "_0", "默认 publish_time=_0")
        check_eq(payload["filters"]["sort_type"], "_0", "默认 sort_type=_0")
        check("TESTKEY_ABCDEF123456" not in out,
              "apikey 明文不出现在输出中（只有打码值/来源路径）")
        # --human 走 stderr，stdout 仍是纯 JSON
        isolated_key(tmp)
        calls = []
        restore = with_key_and_post({mod.DR_SEARCH: seq}, calls)
        try:
            code, out, err = run_cli(["--keyword", "WorkBuddy教程", "--human"])
        finally:
            restore()
        check_eq(code, 0, "--human 退出码 0")
        json.loads(out)                     # 不抛异常即纯 JSON
        check("WorkBuddy教程" in err, "--human 摘要写到 stderr")
        check("视频条数" in err, "--human 摘要含视频条数")

        # --output 落盘
        isolated_key(tmp)
        out_file = os.path.join(tmp, "r.json")
        restore = with_key_and_post({mod.DR_SEARCH: seq}, calls)
        try:
            code, out, err = run_cli(["--keyword", "kw", "--output", out_file,
                                      "--compact"])
        finally:
            restore()
        check(os.path.isfile(out_file), "--output 落盘成功")
        with open(out_file, encoding="utf-8") as fh:
            saved = json.load(fh)
        check_eq(saved["video_count"], 1, "落盘文件内容正确")

        # 明确 --pages 2 -> explicit
        isolated_key(tmp)
        calls = []
        seq2 = [page_payload([fake_video("1" * 19)], offset=20, has_more=1),
                page_payload([fake_video("2" * 19)], offset=40, has_more=0)]
        restore = with_key_and_post({mod.DR_SEARCH: seq2}, calls)
        try:
            code, out, err = run_cli(["--keyword", "kw", "--pages", "2"])
        finally:
            restore()
        payload = json.loads(out)
        check_eq(payload["pages_source"], "explicit", "--pages 2 -> explicit")
        check_eq(len(calls), 2, "--pages 2 发 2 次请求")

        # 失败 -> 退出码 1
        isolated_key(tmp)
        calls = []
        restore = with_key_and_post(
            {mod.DR_SEARCH: [{"code": 403, "tips": "无效的apikey"}]}, calls)
        try:
            code, out, err = run_cli(["--keyword", "kw", "--retry", "0"])
        finally:
            restore()
        check_eq(code, 1, "采集失败退出码 1")

        # --check-key 不发请求
        isolated_key(tmp)
        calls = []
        restore = with_key_and_post({mod.DR_SEARCH: [page_payload([])]}, calls)
        try:
            code, out, err = run_cli(["--check-key"])
        finally:
            restore()
        payload = json.loads(out)
        check_eq(payload["apikey_configured"], True, "--check-key 报告已配置")
        check_eq(len(calls), 0, "--check-key 零请求")
        check("TESTKEY_ABCDEF123456" not in out, "--check-key 对密钥打码")

        # 多关键词 + 翻页凭据 -> 顶层告警
        isolated_key(tmp)
        calls = []
        restore = with_key_and_post({mod.DR_SEARCH: [page_payload(
            [fake_video("1" * 19)], offset=20, has_more=1)]}, calls)
        try:
            code, out, err = run_cli(["--keyword", "kw1|kw2", "--backtrace", "bt"])
        finally:
            restore()
        payload = json.loads(out)
        check(any("只对应上一页所属的那个关键词" in w
                  for w in payload["warnings"]), "多关键词 + 凭据 -> 顶层告警")
        check_eq(payload["total_keywords"], 2, "识别出 2 个关键词")

        # 批量：第二个关键词撞 fatal -> 中止
        isolated_key(tmp)
        calls = []

        def seq_by_call(dr, payload, apikey, timeout=None, heartbeat=True):
            calls.append(payload)
            if len(calls) == 1:
                return 200, json.dumps(page_payload([fake_video("1" * 19)],
                                                    has_more=0)), page_payload([], has_more=0)
            return 200, json.dumps({"code": 402, "tips": "余额不足，请登录并充值"}), \
                {"code": 402, "tips": "余额不足，请登录并充值"}

        original = mod.http_post
        mod.http_post = seq_by_call
        try:
            code, out, err = run_cli(["--keyword", "kw1|kw2|kw3", "--retry", "0"])
        finally:
            mod.http_post = original
        payload = json.loads(out)
        check(payload["aborted"], "撞 fatal 错误 -> aborted=True")
        check_eq(payload["skipped_keywords"], ["kw3"], "剩余关键词 kw3")
        check_eq(payload["next_action"]["reason"], "fatal_error",
                 "顶层 next_action.reason=fatal_error")
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------
# 14. 静态安全
# --------------------------------------------------------------------------

def test_static_safety():
    src = open(SCRIPT, encoding="utf-8").read()
    for bad in ("subprocess", "eval(", "exec(", "base64", "os.system"):
        check(bad not in src, "脚本内不得出现 %s" % bad)
    check(src.count("urlopen") == 1, "只有一处 urlopen")
    check("API_ENDPOINT" in src, "URL 由 API_ENDPOINT 拼装")
    check("input(" not in src, "脚本内没有 input()")

    # 密钥不硬编码
    check("Bearer \" + apikey" in src or '"Bearer " + apikey' in src,
          "apikey 由变量拼装，不硬编码")


# --------------------------------------------------------------------------
# 15. 续采闭环
# --------------------------------------------------------------------------

def test_resume_closed_loop():
    # 把 resume_command 用 shlex 拆开真的执行一遍：不得重复请求第 1 页
    calls = []
    seq = [page_payload([fake_video("1" * 19)], backtrace="bt1", offset=20,
                        search_id="sid1", has_more=1)]
    restore = with_key_and_post({mod.DR_SEARCH: seq}, calls)
    try:
        r = mod.collect_keyword("WorkBuddy教程", apikey="K", pages=1)
    finally:
        restore()
    action = r["next_action"]
    check(action is not None, "首轮给出 next_action")

    # 用 next_action 的字段直接续采
    calls2 = []
    seq2 = [page_payload([fake_video("2" * 19)], backtrace="bt2", offset=40,
                         search_id="sid2", has_more=0)]
    restore = with_key_and_post({mod.DR_SEARCH: seq2}, calls2)
    try:
        r2 = mod.collect_keyword("WorkBuddy教程", apikey="K", pages=1,
                                 start_page=action["resume_page"],
                                 start_backtrace=action["resume_backtrace"],
                                 start_offset=action["resume_offset"],
                                 start_search_id=action["resume_search_id"])
    finally:
        restore()
    check_eq(calls2[0]["payload"]["page"], 2, "续采请求第 2 页（不重复第 1 页）")
    check_eq(calls2[0]["payload"]["backtrace"], "bt1", "续采带上一页 backtrace")
    check_eq(calls2[0]["payload"]["offset"], 20, "续采带上一页 offset")
    check_eq(calls2[0]["payload"]["search_id"], "sid1", "续采带上一页 search_id")
    check_eq(calls2[0]["payload"]["keyword"], "WorkBuddy教程", "续采关键词一致")

    # 完整走一遍「未指定页数 -> 1 页 -> 逐轮追问 -> 末页才停」
    pages_seq = [
        page_payload([fake_video("1" * 19)], backtrace="bt1", offset=20,
                     search_id="sid1", has_more=1),
        page_payload([fake_video("2" * 19)], backtrace="bt2", offset=40,
                     search_id="sid2", has_more=1),
        page_payload([fake_video("3" * 19)], backtrace="bt3", offset=60,
                     search_id="sid3", has_more=0),
    ]
    all_calls = []
    restore = with_key_and_post({mod.DR_SEARCH: pages_seq}, all_calls)
    try:
        round_no, token = 0, {}
        actions = []
        while round_no < 5:
            round_no += 1
            res = mod.collect_keyword("kw", apikey="K", pages=None, start_page=round_no,
                                      start_backtrace=token.get("b"),
                                      start_offset=token.get("o"),
                                      start_search_id=token.get("s"))
            if res["next_action"] is None:
                actions.append(None)
                break
            actions.append(res["next_action"])
            token = {"b": res["next_action"]["resume_backtrace"],
                     "o": res["next_action"]["resume_offset"],
                     "s": res["next_action"]["resume_search_id"]}
    finally:
        restore()
    check_eq(round_no, 3, "共 3 轮（末页才停）")
    check_eq(len(all_calls), 3, "3 轮共 3 次请求（每轮 1 次）")
    check_eq([c["payload"]["page"] for c in all_calls], [1, 2, 3],
             "页码依次为 1、2、3")
    check_eq([c["payload"]["backtrace"] for c in all_calls], ["", "bt1", "bt2"],
             "backtrace 依次传递")
    check_eq([c["payload"]["offset"] for c in all_calls], [0, 20, 40],
             "offset 依次传递（首页为 0）")
    check(actions[0] is not None and actions[1] is not None,
          "前两轮都给 next_action")
    check(actions[2] is None, "末页不再追问")
    check("没有指定采集页数" in actions[0]["question"],
          "第 1 轮问话点明「没有指定采集页数」")
    check_eq(actions[0]["pages_source"], "default", "第 1 轮 pages_source=default")


# --------------------------------------------------------------------------
# 17. 规范 12 项字段口径 + 真实响应夹具回放（2026-10-16）
#     这一组把「需求方给定的 12 项 + 输出顺序」锁进断言，并回放 2026-10-09
#     真实调用留下的原始响应（含尾部真实 PHP 告警），防止：
#       - 字段顺序被改动 / 12 项里漏掉某项（如漏 视频封面）；
#       - 站点改结构（容器键、字段名、图文混流）而没人发现。
# --------------------------------------------------------------------------

EXPECTED_CANONICAL = (
    "aweme_id", "video_cover", "desc", "create_time", "nickname",
    "video_duration", "digg_count", "comment_count", "collect_count",
    "share_count", "video_play_addr", "share_url",
)
EXPECTED_LABELS = (
    "视频ID", "视频封面", "视频描述", "发布时间", "用户昵称", "视频时长",
    "点赞数", "评论数", "收藏数", "分享数", "视频文件地址", "视频分享链接",
)
DERIVED_KEYS = {
    "create_time_ts", "video_duration_ms", "video_duration_text",
    "video_duration_unit", "video_url", "video_type", "page", "index",
}
REAL_FIXTURE = os.path.join(HERE, "real_2026-10-09_page1.json")


def test_canonical_fields_and_real_fixture():
    # ---- A. 常量本身（顺序即输出顺序）----
    check_eq(mod.CANONICAL_FIELDS, EXPECTED_CANONICAL,
             "CANONICAL_FIELDS 顺序 = 需求方给的 12 项顺序")
    check_eq(len(mod.CANONICAL_FIELDS), 12, "规范字段恰好 12 项")
    check_eq(tuple(mod.CANONICAL_FIELD_LABELS[k] for k in EXPECTED_CANONICAL),
             EXPECTED_LABELS, "中文名与字段一一对应且顺序一致")

    # ---- B. build_video 输出：前 12 个键 = 规范顺序，派生字段全在其后 ----
    sample = mod.build_video({
        "aweme_id": "1" * 19, "video_cover": "https://c/1.jpg", "desc": "d",
        "create_time": 1785381003, "nickname": "n", "video_duration": 292106,
        "digg_count": 1, "comment_count": 2, "collect_count": 3, "share_count": 4,
        "video_play_addr": "https://p/a.mp4",
        "share_url": "https://www.iesdouyin.com/share/video/1/",
    }, 1, 1)
    keys = list(sample.keys())
    check_eq(tuple(keys[:12]), EXPECTED_CANONICAL,
             "输出的前 12 个键就是规范 12 项、且顺序一致")
    check_eq(set(keys[12:]), DERIVED_KEYS, "派生字段集合固定且全排在 12 项之后")
    check_eq(len(keys), 20, "一条记录共 20 个键（12 规范 + 8 派生）")

    # ---- C. video_type 判定：图文 / 视频 / 未知 ----
    check_eq(mod.detect_video_type(
        "https://www.iesdouyin.com/share/note/123/", "https://x/a.mp4", 0),
        "图文", "share_url 含 /share/note/ ⇒ 图文")
    check_eq(mod.detect_video_type(
        "https://www.iesdouyin.com/share/video/1/", "https://x/b.mp3", 0),
        "图文", "播放地址是 .mp3 ⇒ 图文（BGM）")
    check_eq(mod.detect_video_type(
        "https://www.iesdouyin.com/share/video/1/", "https://x/b.mp4", 1000),
        "视频", "正常视频 ⇒ 视频")
    check_eq(mod.detect_video_type(None, None, None), None,
             "信息不足时返回 None（不猜）")

    # 图文记录的 video_play_addr 必须被标注出来，避免被当成视频文件地址
    note = mod.build_video({
        "aweme_id": "1" * 19, "video_duration": 0,
        "video_play_addr": "https://x/bgm.mp3",
        "share_url": "https://www.iesdouyin.com/share/note/9/",
    }, 1, 1)
    check_eq(note["video_type"], "图文", "图文记录输出 video_type=图文")
    check_eq(note["video_duration"], 0, "图文记录 video_duration = 0（原值照实）")

    # ---- D. 真实响应夹具回放（站点原样字节，含 PHP 告警尾巴）----
    if not os.path.isfile(REAL_FIXTURE):
        check("真实夹具存在", False, REAL_FIXTURE)
        return
    with io.open(REAL_FIXTURE, encoding="utf-8") as fh:
        raw_text = fh.read()

    # 夹具必须仍保留真实的 PHP 告警尾巴（证明容错解析是必要的）
    check("Cannot modify header information" in raw_text,
          "夹具保留了真实的 PHP 告警尾巴")

    # ---- 反脱敏断言（家族红线：真实博主 ID / 昵称 / 文本不得进夹具）----
    #      不写「真实值不在里面」（那等于把真实值又抄进包），改断言「全是合成值」。
    for probe, what in (("示例用户", "昵称"), ("示例作品描述", "描述"),
                        ("media.example", "影像直链"),
                        ("76000000000000000", "作品号"),
                        ("SYNTHETIC_BACKTRACE_", "backtrace")):
        check(probe in raw_text, "夹具为合成值：%s 用 %r 形态" % (what, probe))

    parsed = mod._loads_tolerant(raw_text)
    check(isinstance(parsed, dict), "含 PHP 告警的真实响应可解析为对象")
    check_eq(parsed.get("code"), 200, "真实响应：code 是整数 200")
    check_eq(parsed.get("status_code"), 0, "真实响应：status_code 是整数 0")
    check_eq(parsed.get("has_more"), 1, "真实响应：has_more 原样是整数 1")

    videos = mod.pick_videos_list(parsed)
    check_eq(len(videos), 16, "真实响应：容器键 aweme_info 解析出 16 条")
    check_eq(parsed.get("aweme_info") and len(parsed["aweme_info"]), 16,
             "真实响应：列表容器键就是 aweme_info")

    check_eq(mod.pick_offset(parsed), "20", "真实响应：offset 原样是 '20'")
    check_eq(mod.pick_search_id(parsed), parsed.get("search_id"),
             "真实响应：search_id 顶层直取")
    check_eq(mod.pick_has_more(parsed), True, "真实响应：has_more='1' ⇒ True")

    # 逐条归一化：12 项全非空、顺序正确、图文/视频分类与站点一致
    types = {"视频": 0, "图文": 0}
    for i, entity in enumerate(videos):
        rec = mod.build_video(entity, 1, i + 1)
        check_eq(tuple(list(rec.keys())[:12]), EXPECTED_CANONICAL,
                 "第 %d 条：前 12 个键顺序正确" % (i + 1))
        for field in EXPECTED_CANONICAL:
            check(rec[field] is not None,
                  "第 %d 条：%s 有真实值（夹具里的 12 项均非空）" % (i + 1, field))
        check(rec["video_type"] in ("视频", "图文"),
              "第 %d 条：video_type 可判定" % (i + 1))
        types[rec["video_type"]] += 1
        # 反脱敏（家族红线）：主键与昵称必须是合成值，真实数据一个都不许留在夹具里
        check(rec["aweme_id"].startswith("76000000000000000"),
              "第 %d 条：aweme_id 是合成值" % (i + 1))
        check((rec["nickname"] or "").startswith("示例用户"),
              "第 %d 条：nickname 是合成值" % (i + 1))
        # 图文 ⇔ share_url 含 /share/note/  ⇔ duration == 0（三者必须一致）
        is_note = "/share/note/" in rec["share_url"]
        check_eq(rec["video_type"] == "图文", is_note,
                 "第 %d 条：video_type 与 share_url 形态一致" % (i + 1))
        check_eq(rec["video_duration"] == 0, is_note and rec["video_duration"] == 0,
                 "第 %d 条：图文恒为 duration=0" % (i + 1))

    check_eq(types, {"视频": 12, "图文": 4},
             "真实响应：16 条中 12 条视频 + 4 条图文（与站点实测一致）")
    print("    [夹具] 2026-10-09 真实第 1 页：16 条（视频 12 / 图文 4）")

    # ---- E. 文档口径守卫：frontmatter 声称的 12 项必须真的列全 ----
    #      （历史 bug：description 声称「共 12 项」却只列了 11 项，漏掉「视频封面」）
    skill_md = os.path.join(HERE, "..", "SKILL.md")
    with io.open(skill_md, encoding="utf-8") as fh:
        skill_text = fh.read()
    # 只取 frontmatter 里的描述三行来查，避免命中正文里的其它表述
    desc_lines = [ln for ln in skill_text.splitlines()
                  if ln.startswith(("description:", "description_zh:"))
                  or ln.startswith("summary:")]
    blob = "\n".join(desc_lines)
    for label in EXPECTED_LABELS:
        check(label in blob,
              "frontmatter 描述里列出「%s」（12 项一个都不能少）" % label)
    check("共 12 项" in blob or "12 项数据" in blob,
          "frontmatter 描述的项数与 12 一致")


# --------------------------------------------------------------------------
# 入口
# --------------------------------------------------------------------------

def main():
    tests = [
        test_field_normalization,
        test_request_counts,
        test_non_retryable_errors,
        test_error_classification_not_mixed,
        test_business_text_does_not_pollute_error,
        test_php_warning_tolerance,
        test_pagination_safety_valves,
        test_default_one_page_rule,
        test_next_action_boundaries,
        test_batch_abort_and_next_action,
        test_keyword_parsing,
        test_filter_normalization,
        test_page_semantics,
        test_cli_end_to_end,
        test_static_safety,
        test_resume_closed_loop,
        test_canonical_fields_and_real_fixture,
    ]
    passed = 0
    for fn in tests:
        try:
            fn()
        except AssertionError as exc:
            print("✗ %-46s %s" % (fn.__name__, exc))
            continue
        except Exception as exc:  # noqa: BLE001
            print("✗ %-46s 异常：%r" % (fn.__name__, exc))
            CHECKS["failed"].append("%s: %r" % (fn.__name__, exc))
            continue
        passed += 1
        print("✓ %s" % fn.__name__)

    total = len(tests)
    print("-" * 66)
    print("通过 %d/%d 组，断言 %d 项，失败 %d 项"
          % (passed, total, CHECKS["n"], len(CHECKS["failed"])))
    for msg in CHECKS["failed"]:
        print("  ! %s" % msg)
    return 0 if not CHECKS["failed"] else 1


if __name__ == "__main__":
    sys.exit(main())

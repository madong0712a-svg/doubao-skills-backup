#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抖音关键词搜索视频列表数据采集助手_kkAI
==========================================

输入抖音**搜索关键词**，返回该关键词下的视频（作品）列表数据：

  视频ID · 视频封面 · 视频描述 · 发布时间 · 用户昵称 · 视频地址 · 视频时长
  · 点赞数 · 评论数 · 收藏数 · 分享数 · 分享链接

接口：POST https://u.ai-gc.art/mcp/rd.php?dr=dy-search-v5
     body: {
         "keyword":      "<关键词>",   # 必填
         "backtrace":    "",           # 回溯参数（翻页用），首页传空串
         "offset":       0,            # 偏移游标（翻页用），首页传 0
         "page":         1,            # 页码，默认 1
         "search_id":    "",           # 搜索 ID（翻页用），首页传空串
         "publish_time": "_0",         # 发布时间：_0 不限 / _1 一天内 / _7 一周内 / _180 半年内
         "sort_type":    "_0",         # 排序：_0 综合 / _1 最多点赞 / _2 最新发布
     }
     请求头：Content-Type: application/json + Authorization: Bearer <apikey>

分页要点（⚠️ 本接口有 **4 个翻页参数**，必须整组回传，缺一个就可能翻不动）：
     - 第 1 页：page=1，backtrace / search_id 传空串，offset 传 0；
     - 第 N 页：page=N，并把第 N-1 页响应里返回的 backtrace / offset / search_id 原样带回；
     - **默认只采 1 页**，采完若还有更多内容，结果里的 next_action 会给出续采命令，
       由助手询问用户是否继续，而不是一次替用户刷很多页。

     ⚠️ 续采必须带 --page <下一页页码> + --backtrace / --offset / --search-id，
        只传 --keyword 会从第 1 页重新开始，白花一次额度。

apikey 由用户登录 https://u.ai-gc.art/ 获取，遵守以下原则：
     ** apikey 绝不硬编码在本脚本中 **
     读取顺序： --apikey 参数  >  环境变量 AI_GC_ART_API_KEY  >  本地密钥文件
     本地密钥文件路径： ~/.workbuddy/ai-gc.art_apikey.txt （可用 --set-apikey 写入）
     密钥文件按「站点」命名，ai-gc.art 站点下所有接口共用同一份 apikey
     （旧文件名 ai-gc.art_apikey、xhs_apikey.txt 仍可读取，首次读到会自动迁移到新路径）

等待策略：
     该接口为排队型服务，单次请求的返回等待时间在 0-600 秒之间。
     脚本默认超时 600 秒（--timeout 可调，取值 0-600；0 表示不设超时，一直等到返回）。
     等待期间不重发请求，只在 stderr 打印心跳提示。

重试策略（重要）：
     ** 每一步只请求一次；只有当这次返回「失败」，才补一次重试，且最多补一次。**
       正常情况：默认 1 页 = 1 次请求；采集 2 页 = 2 次请求
       最坏情况：每一页各失败一次并各补发一次（2 页 = 4 次请求，绝不会有第 3 次尝试）
     以下错误不重试（重发也不会有不同结果，只会浪费额度）：
       - unauthorized            apikey 无效 / 未携带密钥
       - insufficient_balance    账户余额不足
       - upstream_busy           上游临时故障 / 被限流（服务端要求等 10 分钟）
       - action_forbidden        动作名被站点网关拒绝（HTTP 403 + 裸文本 forbidden）
     --retry 0 可完全关闭重试。

依赖：Python 3.8+ 纯标准库（urllib / json / argparse / re / os / sys / time / threading / datetime）

用法示例：
    # 保存 apikey（推荐，避免终端历史泄露）
    python dy_search_collect.py --set-apikey ak_xxxxxxxx

    # 校验 apikey 是否配置（不发起采集请求）
    python dy_search_collect.py --check-key

    # 搜索「WorkBuddy教程」，默认只采第 1 页
    python dy_search_collect.py --keyword "WorkBuddy教程"

    # 采集 2 页
    python dy_search_collect.py --keyword "WorkBuddy教程" --pages 2

    # 限定发布时间 / 排序方式
    python dy_search_collect.py --keyword "WorkBuddy教程" --publish-time 一周内 --sort-type 最多点赞

    # 继续翻页（用上一次结果里的 next_action 给出的命令，不要重复第 1 页）
    python dy_search_collect.py --keyword "WorkBuddy教程" --page 2 \\
        --backtrace "<上页返回>" --offset "<上页返回>" --search-id "<上页返回>" --pages 1

    # 多个关键词（用竖线或换行分隔；空格与逗号**不会**被当作分隔符）
    python dy_search_collect.py --keyword "WorkBuddy教程|AI视频教程" --pages 1

    # 导出 JSON
    python dy_search_collect.py --keyword "WorkBuddy教程" --pages 2 --output videos.json

输出：标准输出为 JSON，结构见 SKILL.md / references/api_reference.md
"""

import argparse
import datetime
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

# --------------------------------------------------------------------------
# 常量
# --------------------------------------------------------------------------

API_ENDPOINT = "https://u.ai-gc.art/mcp/rd.php"
DR_SEARCH = "dy-search-v5"        # 主接口动作：keyword(+筛选/翻页) -> 一页视频列表

LOGIN_URL = "https://u.ai-gc.art/"

# 本机密钥文件以「站点」命名，而非「技能」命名：
# ai-gc.art 站点下的所有接口（小红书系列、抖音主页/搜索系列、以及后续接入的其它接口）
# 共用同一份 apikey，因此文件名取站点名，便于跨技能复用同一份密钥。
KEY_FILE = os.path.join(os.path.expanduser("~"), ".workbuddy", "ai-gc.art_apikey.txt")

# 历史遗留文件名。读取时作为兜底，读到即自动迁移到 KEY_FILE。
LEGACY_KEY_FILES = [
    # 早期版本：按「站点」命名但无扩展名
    os.path.join(os.path.expanduser("~"), ".workbuddy", "ai-gc.art_apikey"),
    # 最早版本：按「技能」命名
    os.path.join(os.path.expanduser("~"), ".workbuddy", "xhs_apikey.txt"),
]

# 环境变量读取顺序：通用名在前，旧技能专用名在后（保持向后兼容）
ENV_KEY_NAMES = (
    "AI_GC_ART_API_KEY",
    "AI_GC_ART_KEY",
    "DY_API_KEY",
    "DOUYIN_API_KEY",
    "XHS_API_KEY",
    "XHS_APIKEY",
    "XHS_KEY",
)

# 等待策略：接口为排队型服务，单次请求返回等待时间在 0-600 秒之间。
# 客户端必须耐心等待：请求发出后一直等，不轮询、不并发。
MIN_TIMEOUT = 0        # 0 = 不设超时（一直等到服务端返回）
MAX_TIMEOUT = 600      # 上限 600 秒
TIMEOUT = MAX_TIMEOUT  # 默认等待上限

# 重试策略：**每一步只请求一次；若该次返回失败，才补一次，最多一次**。
# 也就是「首发 1 次 + 失败后补 1 次」，绝不出现第三次尝试。
MIN_RETRY = 0
MAX_RETRY = 1          # 硬上限：任何情况下都不允许多次重复请求
DEFAULT_RETRY = 1      # 默认「失败后补一次」
MIN_RETRY_DELAY = 0
RETRY_DELAY = 2.0      # 重试前的短暂等待，避免立刻二次冲击

# 分页：采集页数上限，防止误传超大页数把额度刷光。
MIN_PAGES = 1
MAX_PAGES = 50
# **默认只采集 1 页**：每页都消耗额度，先取第一页给用户看，
# 采集完由调用方询问用户「是否继续采更多页」，用户确认后再续采。
DEFAULT_PAGES = 1

# 续采时建议的页数：一次只往后推一页，让用户逐次决定，避免一次性刷光额度。
CONTINUE_SUGGESTED_PAGES = 1

# 起始页码：接口的 page 是**页码**，即「第几页」，从 1 开始计数（不是偏移量、不是记录数）。
# 首页（第 1 页）的 backtrace / search_id 传空串、offset 传 0；
# 第 N 页传第 N-1 页返回的 backtrace / offset / search_id（**三个都要带回**）。
MIN_START_PAGE = 1
DEFAULT_START_PAGE = 1
# 页码软上限：page 是页码，正常不会超过这个数量级。超过只告警不拦，
# 用来挡住「把采集页数误填到 --page」这类最常见的填错（--pages 与 --page 只差一个字母）。
MAX_REASONABLE_PAGE = 50

# 心跳：等待超过该秒数后，每 HEARTBEAT_INTERVAL 秒向 stderr 打一次提示
HEARTBEAT_AFTER = 15
HEARTBEAT_INTERVAL = 15

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# 实测：接口失败时返回 {"code":403,"tips":"访问被拒绝: 无效的apikey，请登录 u.ai-gc.art 获取"}
# 因此成功态需同时兼容 code=0/1/2xx 与 code="0"/"1"/"ok"/"success" 等写法。
SUCCESS_STR_FLAGS = ("0", "1", "200", "ok", "success", "succeeded", "true", "yes")
SUCCESS_INT_CODES = (0, 1, 200, 10000)
AUTH_ERROR_CODES = (401, 403)

# ---------------------------------------------------------------------------
# 实测（2026-10-01/02，u.ai-gc.art）三种失败形态的严格区分，用于避免误诊：
#
#   | 情形                    | HTTP | 响应体                                             |
#   | ----------------------- | ---- | -------------------------------------------------- |
#   | dr 动作名不被站点接受    | 403  | 裸文本 `forbidden`（**非 JSON**）                   |
#   | apikey 无效/过期         | 200  | JSON {"code":403,"tips":"访问被拒绝: 无效的apikey…"} |
#   | 未携带 apikey            | 401  | 裸文本 `missing api key`                            |
#
# 关键结论：403 + 非 JSON 的 `forbidden` **与 apikey 完全无关**——
# 实测「有效密钥 + 错误动作名」与「无效密钥 + 错误动作名」返回**完全相同**。
# 若把它归入 unauthorized，会提示用户去重新获取 apikey，而这是无效的排查方向。
FORBIDDEN_BODY_HINTS = ("forbidden",)

# 需要用户介入处理、应透传到顶层的错误码。
# upstream_busy：服务端明确要求「请 10 分钟后再试」，立即重试必然同样失败，只会白扣额度。
# action_forbidden：动作名不被站点接受，重发多少次都还是 403。
FATAL_ERROR_CODES = ("unauthorized", "insufficient_balance", "upstream_busy",
                     "action_forbidden")

# 不值得重试的错误：重发一次结果也不会变，只会白白多消耗一次额度
NON_RETRYABLE_ERROR_CODES = FATAL_ERROR_CODES

# 视频实体的候选容器键。搜索结果里视频列表可能放在 aweme_info / aweme_list / data …
# 脚本按候选顺序直取，直取不到时再用「找最像视频列表的那个数组」兜底（见 pick_videos_list）。
# ℹ️ `aweme_info` 是**本动作（dy-search-v5）2026-10-09 实测确认**的容器键
#    （与同站点 dy-uservideos 一致，顶层数组），故置于首位；
#    若日后接口变更导致直取落空，整树兜底仍会接管，也可直接调整本表顺序。
VIDEO_LIST_KEYS = ("aweme_info", "awemeInfo", "aweme_list", "awemeList",
                   "aweme_list_v2", "awemeListV2", "videos", "video_list",
                   "videoList", "search_result", "searchResult",
                   "search_list", "searchList", "items", "list", "listData",
                   "list_data", "data", "result", "records", "rows")

# 翻页凭据的候选键（顶层优先）。
# ⚠️ 本接口有 **3 个**翻页凭据：backtrace / offset / search_id，必须整组回传。
SEARCH_ID_KEYS = ("search_id", "searchId")
BACKTRACE_KEYS = ("backtrace", "back_trace", "backTrace")
OFFSET_KEYS = ("offset", "off_set", "offSet")

# 「还有下一页」的候选键
HAS_MORE_KEYS = ("has_more", "hasMore", "has_next", "hasNext", "is_more",
                 "more_flag", "has_more_data")

# 「该关键词一共有多少条」的候选键。本动作 2026-10-09 实测**不返回**该字段；
# 保留候选表以兼容日后变更，取不到时统一为 None（不编造 0）。
TOTAL_COUNT_KEYS = ("total_count", "totalCount", "total", "aweme_total",
                    "awemeTotal", "total_aweme", "totalAweme")

# `--raw` 时留存的完整原始响应上限（单页）。搜索结果一页约几十 KB，200KB 足够
# 覆盖正常响应，又避免异常大的响应把 JSON 结果撑爆。
RAW_RESPONSE_LIMIT = 200000

# 标志「一条视频实体」的最低字段集，用于从响应里挑出真正的视频数组
VIDEO_MARK_KEYS = ("aweme_id", "awemeid", "aweme_url", "desc", "create_time",
                   "createtime", "nickname", "video_cover", "video_play_addr",
                   "video_duration", "digg_count")

# 北京时间偏移（抖音为国内平台，时间戳统一按 UTC+8 解释）
CN_TZ = datetime.timezone(datetime.timedelta(hours=8))

# 需求方给定的 **12 项规范返回字段**（2026-10-16 与需求方逐项对齐）。
# ⚠️ **元组顺序 = 输出顺序**：`build_video()` 必须让这 12 项**按此顺序排在最前**，
#    派生字段与辅助字段（create_time_ts / video_duration_* / video_url / page / index）
#    一律排在它们**之后**，这样导表、转 CSV、对齐其它 kkAI 技能时列序天然一致。
CANONICAL_FIELDS = (
    "aweme_id",         # 视频ID
    "video_cover",      # 视频封面
    "desc",             # 视频描述
    "create_time",      # 发布时间
    "nickname",         # 用户昵称
    "video_duration",   # 视频时长
    "digg_count",       # 点赞数
    "comment_count",    # 评论数
    "collect_count",    # 收藏数
    "share_count",      # 分享数
    "video_play_addr",  # 视频文件地址
    "share_url",        # 视频分享链接
)

# 12 项规范字段的中文名（文档、展示模板、CSV 表头共用同一份口径，避免各处写法漂移）
CANONICAL_FIELD_LABELS = {
    "aweme_id": "视频ID",
    "video_cover": "视频封面",
    "desc": "视频描述",
    "create_time": "发布时间",
    "nickname": "用户昵称",
    "video_duration": "视频时长",
    "digg_count": "点赞数",
    "comment_count": "评论数",
    "collect_count": "收藏数",
    "share_count": "分享数",
    "video_play_addr": "视频文件地址",
    "share_url": "视频分享链接",
}

# 字段别名表：兼容不同版本 / 文档里的拼写差异，取值时按顺序命中第一个非空值。
# 覆盖范围严格按 CANONICAL_FIELDS 的 12 项（外加 video_url 这一兼容别名，见下）。
FIELD_ALIASES = {
    "aweme_id": ["aweme_id", "awemeId", "awemeid", "item_id", "itemId", "id"],
    "nickname": ["nickname", "nick_name", "nickName", "user_name", "userName",
                 "username", "nick", "author", "author_name"],
    "desc": ["desc", "description", "title", "content", "aweme_desc"],
    "create_time": ["create_time", "createTime", "createtime", "publish_time",
                    "publishTime", "time", "date"],
    "video_cover": ["video_cover", "videoCover", "cover", "cover_url",
                    "coverUrl", "origin_cover", "originCover", "dynamic_cover"],
    # 实测同站点 dy-uservideos 的播放地址字段是 video_play_addr
    "video_play_addr": ["video_play_addr", "videoPlayAddr", "play_addr",
                        "playAddr", "video_url", "vide_url", "videoUrl",
                        "video_link", "play_url", "playUrl"],
    "video_duration": ["video_duration", "videoDuration", "duration"],
    "digg_count": ["digg_count", "diggCount", "like_count", "likeCount",
                   "liked_count", "digg", "like"],
    # 实测拼写就是 comment_count；omment_count 为历史文档差异，保留兼容
    "comment_count": ["comment_count", "omment_count", "comments_count",
                      "commentCount", "comment"],
    "collect_count": ["collect_count", "collectCount", "collected_count",
                      "collectedCount", "collect", "favorite_count"],
    "share_count": ["share_count", "shareCount", "shared_count", "share"],
    # 站点若返回规范网页链接 aweme_url，video_url 优先用它（同站点 dy-uservideos 实测）
    "video_url": ["aweme_url", "awemeUrl", "share_url", "shareUrl"],
    "share_url": ["share_url", "shareUrl", "aweme_url", "awemeUrl",
                  "video_share_url", "share_link"],
}

# 注意：不要放 "desc" —— 视频实体的 desc 是正文描述，会被误当成错误信息
MSG_KEYS = ["msg", "message", "error", "errmsg", "err_msg", "info",
            "reason", "tips"]
CODE_KEYS = ["code", "status", "errno", "error_code", "errorCode", "ret"]
# 注意：不要把 keyword 放进 CODE_KEYS / MSG_KEYS，避免把回显的搜索词当状态码
# 抖音 aweme_id 为纯数字长串（实测 19 位）
AWEME_ID_RE = re.compile(r"^\d{15,25}$")

# 一条记录里不该被当成翻页凭据的字段
CURSOR_BLOCKLIST = ("aweme_id", "awemeid", "item_id", "desc", "title",
                    "nickname", "comment_count", "collect_count",
                    "digg_count", "share_count", "video_cover",
                    "video_play_addr", "video_duration", "create_time")

# 多个关键词的分隔符。
# ⚠️ **刻意不包含逗号与空格**：搜索词经常自带空格（「AI 视频教程」）与逗号，
# 若把它们当分隔符，一个关键词会被拆成两个，白花一倍额度还把结果搞乱。
# 需要一次搜多个词时用 `|` / `;` / 换行，或重复传 --keyword。
KEYWORD_SEP_RE = re.compile(r"[|｜;；\n\r]+")

# 发布时间筛选（publish_time）—— 站点取值是**下划线数字编码**：
#   _0 不限（默认）/ _1 一天之内 / _7 一周之内 / _180 半年之内
# 这里把常见的中英文写法统一到站点取值上；表里没有的写法**原样透传**。
# ⚠️ 归一化方向 = 站点取值的语言（这里是编码），**不能**把中文当目标值。
DEFAULT_PUBLISH_TIME = "_0"
PUBLISH_TIME_ALIASES = {
    "": "_0",
    "不限": "_0", "全部": "_0", "所有": "_0", "默认": "_0",
    "all": "_0", "any": "_0", "_0": "_0", "0": "_0",
    "一天内": "_1", "一天之内": "_1", "1天内": "_1", "一天": "_1", "1天": "_1",
    "日内": "_1", "今天": "_1", "day": "_1", "1d": "_1", "_1": "_1", "1": "_1",
    "一周内": "_7", "一周之内": "_7", "1周内": "_7", "一周": "_7", "7天内": "_7",
    "7天": "_7", "周内": "_7", "week": "_7", "7d": "_7", "_7": "_7", "7": "_7",
    "半年内": "_180", "半年之内": "_180", "6个月内": "_180", "半年": "_180",
    "180天内": "_180", "180天": "_180", "halfyear": "_180", "half_year": "_180",
    "6m": "_180", "_180": "_180", "180": "_180",
}

# 排序方式（sort_type）—— 站点取值同样是**下划线数字编码**：
#   _0 综合（默认）/ _1 最多点赞 / _2 最新发布
DEFAULT_SORT_TYPE = "_0"
SORT_TYPE_ALIASES = {
    "": DEFAULT_SORT_TYPE, "默认": DEFAULT_SORT_TYPE, "默认排序": DEFAULT_SORT_TYPE,
    "综合": DEFAULT_SORT_TYPE, "综合排序": DEFAULT_SORT_TYPE,
    "推荐": DEFAULT_SORT_TYPE, "不限": DEFAULT_SORT_TYPE,
    "全部": DEFAULT_SORT_TYPE, "general": DEFAULT_SORT_TYPE,
    "comprehensive": DEFAULT_SORT_TYPE, "default": DEFAULT_SORT_TYPE,
    "all": DEFAULT_SORT_TYPE, DEFAULT_SORT_TYPE: DEFAULT_SORT_TYPE,
    "0": DEFAULT_SORT_TYPE,
    "最多点赞": "_1", "点赞最多": "_1", "最热": "_1", "最热排序": "_1",
    "热门": "_1", "热度": "_1", "点赞": "_1", "hot": "_1",
    "popularity": "_1", "like": "_1", "_1": "_1", "1": "_1",
    "最新发布": "_2", "最新": "_2", "最新排序": "_2", "发布时间": "_2",
    "时间": "_2", "time": "_2", "latest": "_2", "new": "_2",
    "_2": "_2", "2": "_2",
}

# 取值的展示名（用于人类可读摘要与文档）
PUBLISH_TIME_LABELS = {
    "_0": "不限（默认）", "_1": "一天之内", "_7": "一周之内", "_180": "半年之内",
}
SORT_TYPE_LABELS = {
    "_0": "综合（默认）", "_1": "最多点赞", "_2": "最新发布",
}


# --------------------------------------------------------------------------
# apikey 处理
# --------------------------------------------------------------------------

def mask_key(key):
    """打码显示 apikey，避免日志泄露。"""
    if not key:
        return ""
    if len(key) <= 10:
        return key[:2] + "*" * (len(key) - 2)
    return key[:6] + "*" * 6 + key[-4:]


def save_apikey(key):
    """把 apikey 写入本地密钥文件（仅本机用户可读写）。"""
    key = (key or "").strip()
    if not key:
        raise ValueError("apikey 不能为空")
    os.makedirs(os.path.dirname(KEY_FILE), exist_ok=True)
    with open(KEY_FILE, "w", encoding="utf-8") as fh:
        fh.write(key)
    try:  # 收紧权限（非 Windows 生效）
        os.chmod(KEY_FILE, 0o600)
    except OSError:
        pass
    return KEY_FILE


def load_apikey(cli_key=None):
    """按优先级读取 apikey：命令行 > 环境变量 > 本地密钥文件。

    密钥文件按「站点」存放（~/.workbuddy/ai-gc.art_apikey.txt），
    ai-gc.art 站点下的所有接口共用同一份 apikey。
    若只存在旧版文件名（ai-gc.art_apikey / xhs_apikey.txt），
    会先读取、再自动迁移到新路径。
    """
    if cli_key and cli_key.strip():
        return cli_key.strip(), "--apikey 参数"

    for env_name in ENV_KEY_NAMES:
        val = os.environ.get(env_name)
        if val and val.strip():
            return val.strip(), "环境变量 %s" % env_name

    candidates = [(KEY_FILE, False)] + [(p, True) for p in LEGACY_KEY_FILES]
    for path, is_legacy in candidates:
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                val = fh.read().strip()
        except OSError:
            continue
        if not val:
            continue
        if is_legacy:
            try:
                save_apikey(val)
                return val, "密钥文件 %s（已从旧文件 %s 自动迁移）" % (KEY_FILE, path)
            except (OSError, ValueError):
                return val, "密钥文件 %s（旧路径，迁移失败）" % path
        return val, "密钥文件 %s" % KEY_FILE

    return None, None


# --------------------------------------------------------------------------
# 通用工具
# --------------------------------------------------------------------------

def clamp_timeout(value):
    """把等待秒数收敛到 0-600。0 表示不设超时（一直等到服务端返回）。"""
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        seconds = TIMEOUT
    if seconds != seconds:  # NaN
        seconds = TIMEOUT
    if seconds < MIN_TIMEOUT:
        seconds = MIN_TIMEOUT
    elif seconds > MAX_TIMEOUT:
        seconds = MAX_TIMEOUT
    # 整数值返回 int，避免输出里出现 600.0 这种噪声
    return int(seconds) if float(seconds).is_integer() else seconds


def clamp_retry(value):
    """把重试次数收敛到 0-1：最多只允许「失败后补一次」，不允许更多。"""
    try:
        count = int(float(value))
    except (TypeError, ValueError):
        count = DEFAULT_RETRY
    if count < MIN_RETRY:
        return MIN_RETRY
    if count > MAX_RETRY:
        return MAX_RETRY
    return count


def clamp_retry_delay(value):
    """重试前的等待秒数，不允许为负。"""
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        seconds = RETRY_DELAY
    if seconds != seconds or seconds < MIN_RETRY_DELAY:  # NaN / 负数
        return MIN_RETRY_DELAY
    return seconds


def clamp_pages(value):
    """把采集页数收敛到 1-50，避免误传超大页数把额度刷光。"""
    try:
        pages = int(float(value))
    except (TypeError, ValueError):
        pages = DEFAULT_PAGES
    if pages < MIN_PAGES:
        return MIN_PAGES
    if pages > MAX_PAGES:
        return MAX_PAGES
    return pages


def clamp_start_page(value):
    """把起始页码收敛到 >= 1（接口的 page 是页码，从 1 开始计数）。"""
    try:
        page = int(float(value))
    except (TypeError, ValueError):
        page = DEFAULT_START_PAGE
    return page if page >= MIN_START_PAGE else MIN_START_PAGE


def start_page_is_reasonable(page):
    """页码是否落在常规范围内（超出只告警，不改变实际请求的页码）。"""
    try:
        return int(page) <= MAX_REASONABLE_PAGE
    except (TypeError, ValueError):
        return True


def walk(node):
    """深度优先遍历 dict / list，产出所有 (key, value)。"""
    if isinstance(node, dict):
        for key, val in node.items():
            yield key, val
            for item in walk(val):
                yield item
    elif isinstance(node, list):
        for val in node:
            for item in walk(val):
                yield item


def deep_find(obj, keys):
    """在任意层级查找 keys 中任一字段，返回首个非空值。"""
    key_set = {k.lower() for k in keys}
    for key, val in walk(obj):
        if isinstance(key, str) and key.lower() in key_set:
            if val is None:
                continue
            if isinstance(val, str) and not val.strip():
                continue
            if isinstance(val, (list, dict)) and not val:
                continue
            return val
    return None


def dig(obj, path):
    """按 a.b.c 路径安全取值。"""
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def normalize_keyword(text):
    """清洗关键词：去首尾空白与包裹引号，**保留内部空格**（「AI 生图」是合法关键词）。"""
    if text is None:
        return ""
    cleaned = str(text).replace("\u3000", " ").strip()
    while len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in "\"'“”‘’":
        cleaned = cleaned[1:-1].strip()
    return cleaned


def split_keywords(raw):
    """把一个输入串拆成若干关键词（支持一次搜多个词）。

    只按 `|` / `;` / 换行 拆分，**刻意不拆逗号与空格**：
    搜索词经常自带空格（「AI 生图」）与逗号，拆了反而把关键词切碎。
    需要多个关键词时更推荐重复传 --keyword。
    """
    if raw is None:
        return []
    text = str(raw).strip()
    if not text:
        return []
    parts = [normalize_keyword(p) for p in KEYWORD_SEP_RE.split(text)]
    return [p for p in parts if p]


def normalize_filter(value, aliases):
    """把筛选参数（publish_time）归一化到站点取值；表里没有的写法原样透传。"""
    if value is None:
        return ""
    key = str(value).replace("\u3000", " ").strip().lower()
    if key in aliases:
        return aliases[key]
    # 未知写法：原样透传（便于站点改用别种取值时直接传原值），不做臆造映射
    return normalize_keyword(value)


def normalize_sort_type(value):
    """排序参数（sort_type）归一化到站点编码。

    站点取值：`_0`（综合，默认）、`_1`（最多点赞）、`_2`（最新发布）。
    常见中文写法（最多点赞 / 最新发布 / 综合 …）会被映射到上面 3 个目标值；
    **表里没有的写法原样透传**（站点日后新增排序值时不必改脚本）。
    不传 / 传空时取站点默认 `_0`，让请求体里的排序始终是显式的。
    """
    if value is None:
        return DEFAULT_SORT_TYPE
    key = str(value).replace("\u3000", " ").strip().lower()
    if key in SORT_TYPE_ALIASES:
        return SORT_TYPE_ALIASES[key]
    # 未知写法：原样透传（保留用户原始大小写，不做臆造映射）
    return normalize_keyword(value)


def normalize_publish_time(value):
    """发布时间参数（publish_time）归一化到站点编码。

    站点取值：`_0`（不限，默认）、`_1`（一天之内）、`_7`（一周之内）、`_180`（半年之内）。
    """
    if value is None:
        return "_0"
    key = str(value).replace("\u3000", " ").strip().lower()
    if key in PUBLISH_TIME_ALIASES:
        return PUBLISH_TIME_ALIASES[key]
    return normalize_keyword(value)


def publish_time_label(value):
    """把发布时间取值转成中文展示名；未收录的取值原样返回。"""
    return PUBLISH_TIME_LABELS.get(value or "", value or "")


def sort_type_label(value):
    """把排序取值转成中文展示名；未收录的取值原样返回。"""
    return SORT_TYPE_LABELS.get(value or "", value or "")


def _heartbeat(stop_event, started_at, limit):
    """等待期间向 stderr 打心跳，让用户知道请求仍在排队而不是卡死。"""
    while not stop_event.wait(HEARTBEAT_INTERVAL):
        waited = int(time.time() - started_at)
        limit_text = "不限时" if limit is None else "上限 %d 秒" % int(limit)
        print("[等待中] 接口仍在处理，已等待 %d 秒（%s，等待期间不重发）"
              % (waited, limit_text), file=sys.stderr, flush=True)


def http_post(dr, payload, apikey, timeout=None, heartbeat=True):
    """向 rd.php 发起**一次** POST，返回 (http_status, 原始文本, 解析后的对象)。

    单次调用内部不重试：无论超时、网络错误还是业务失败，都直接把结果返回，
    由调用方（_run_step）决定是否补一次重试。
    """
    timeout = clamp_timeout(TIMEOUT if timeout is None else timeout)
    # urllib 的 timeout=None 表示无限等待；0 在这里按「不设超时」处理
    socket_timeout = None if timeout == 0 else timeout

    url = "%s?dr=%s" % (API_ENDPOINT, urllib.parse.quote(dr))
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer " + apikey)
    req.add_header("Accept", "application/json, text/plain, */*")
    req.add_header("User-Agent", UA)

    stop_event = threading.Event()
    started_at = time.time()
    hb_thread = None
    if heartbeat and (socket_timeout is None or socket_timeout > HEARTBEAT_AFTER):
        hb_thread = threading.Thread(target=_heartbeat,
                                     args=(stop_event, started_at, socket_timeout),
                                     daemon=True)
        hb_thread.start()

    status = 0
    text = ""
    try:
        with urllib.request.urlopen(req, timeout=socket_timeout) as resp:
            status = resp.getcode()
            text = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        try:
            text = exc.read().decode("utf-8", "replace")
        except Exception:
            text = ""
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, Exception) and "timed out" in str(reason).lower():
            return 0, ("等待超时：已等待 %d 秒仍未返回。接口排队时间可能更久，"
                       "该错误会触发一次自动补发；若补发仍超时，"
                       "请把 --timeout 调大（上限 %d 秒）后手动重新发起。"
                       % (int(timeout), MAX_TIMEOUT)), None
        return 0, "网络请求失败: %s" % reason, None
    except Exception as exc:  # noqa: BLE001
        return 0, "请求异常: %s" % exc, None
    finally:
        stop_event.set()
        if hb_thread is not None:
            hb_thread.join(timeout=1)

    parsed = _loads_tolerant(text)
    return status, text, parsed


def _loads_tolerant(text):
    """容错解析响应体：站点会在合法 JSON 之后追加 PHP 告警文本。

    做法：用 `json.JSONDecoder().raw_decode` 从**最靠前的 `{` 或 `[`** 起解析，
    只取第一个完整 JSON 值，尾部告警自动忽略。

    ⚠️ **不要**改成「截最外层花括号再 json.loads」：那样对**顶层数组**响应
    （站点第一步接口就是 `[{...}]` 形态）会把整包截成 `{...}`，
    悄悄丢掉数组外壳。这里两种形态都先按原始起点解析，更稳。
    """
    stripped = (text or "").strip()
    if not stripped:
        return None
    try:
        return json.loads(stripped)
    except ValueError:
        pass
    decoder = json.JSONDecoder()
    for idx, ch in enumerate(stripped):
        if ch in "{[":
            try:
                value, _ = decoder.raw_decode(stripped[idx:])
                return value
            except ValueError:
                continue
    return None


def pick_message(parsed, raw_text):
    """从响应中提取错误/提示信息。"""
    if isinstance(parsed, dict):
        for key in MSG_KEYS:
            val = parsed.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
            if isinstance(val, dict):
                inner = deep_find(val, MSG_KEYS)
                if isinstance(inner, str) and inner.strip():
                    return inner.strip()
    if raw_text and len(raw_text.strip()) <= 300:
        return raw_text.strip()
    return ""


def pick_code(parsed):
    if isinstance(parsed, dict):
        for key in CODE_KEYS:
            if key in parsed:
                return parsed[key]
    return None


def code_is_success(code):
    """判断业务状态码是否代表成功。"""
    if code is None:
        return True
    if isinstance(code, bool):
        return code
    if isinstance(code, (int, float)):
        num = int(code)
        return num in SUCCESS_INT_CODES or (200 <= num < 300)
    text = str(code).strip().lower()
    if not text:
        return True
    if text in SUCCESS_STR_FLAGS:
        return True
    try:
        num = int(float(text))
    except ValueError:
        return False
    return num in SUCCESS_INT_CODES or (200 <= num < 300)


def code_is_auth_error(code):
    """判断业务状态码是否代表鉴权失败。"""
    if isinstance(code, bool) or code is None:
        return False
    try:
        return int(float(str(code).strip())) in AUTH_ERROR_CODES
    except (ValueError, TypeError):
        return False


def is_error_payload(parsed):
    """判断响应是否为业务失败（code 非成功态）。"""
    if not isinstance(parsed, dict):
        return True
    code = pick_code(parsed)
    if code is None:
        return False
    return not code_is_success(code)


AUTH_HINTS = ("apikey", "api key", "api_key", "密钥", "授权", "鉴权", "token")
AUTH_BAD_WORDS = ("无效", "失效", "错误", "不正确", "过期", "拒绝", "未授权",
                  "invalid", "denied", "expired", "unauthorized", "forbidden")

# 实测：额度耗尽时返回 JSON 提示「余额不足，请登录 u.ai-gc.art ，请充值后重试」
BALANCE_HINTS = ("余额不足", "请充值", "充值后", "额度不足", "欠费",
                 "insufficient balance", "insufficient_quota", "quota exceeded",
                 "out of credit", "no credit")
BALANCE_ERROR_CODES = (402, 4029, 4003)

# 实测：上游偶发不可用时会返回
#   {"code":404,"tips":"404,API 请求失败,请10分钟后，再重试"}
# 服务端明确要求「10 分钟后」再试，说明这是**限流 / 上游临时故障**，
# 立即重发（脚本默认只等 2 秒）必然得到完全相同的结果，只会白扣一次额度。
#
# 注意：只把「明确的长等待 / 限流」信号算作 upstream_busy。
# 「服务器繁忙，请稍后重试」这类普通业务失败**仍然按默认策略补发一次**——
# 需求要求「失败才重试一次」，不应把可快速重试的错误也划进不重试的范畴。
TRANSIENT_PATTERNS = (
    r"\d+\s*分钟",              # 「请10分钟后，再重试」——服务端给明确等待时长
    r"稍后再试",
    r"请求过于频繁",
    r"请求频繁",
    r"访问频繁",
    r"too many requests",
    r"rate\s*limit",
    r"try again later",
    r"service unavailable",
    r"temporarily unavailable",
)
TRANSIENT_RETRY_AFTER = 600   # 服务端建议的等待秒数（10 分钟）


def code_is_balance_error(code):
    if isinstance(code, bool) or code is None:
        return False
    try:
        return int(float(str(code).strip())) in BALANCE_ERROR_CODES
    except (ValueError, TypeError):
        return False


def _error_blob(parsed, raw_text=""):
    """构造用于「错误文案启发式判断」的文本。

    ⚠️ 只取**提示信息字段本身**，绝不把整个响应体拼进来。

    2026-10-01 实测教训（真实事故，发生在同站点的 xhs-usernotes 上）：
    成功返回的一页 20 条记录里，有一条标题是「AI工作流**1分钟**生成火爆精美菜谱…」。
    旧实现把整包 43KB 正文拼进 blob，标题里的「1分钟」命中了限流正则 `\\d+分钟`，
    于是**整页成功数据被误判成 upstream_busy 直接丢弃**。

    搜索结果里视频描述同样可能写着「余额不足」「限流」「10分钟后」，
    所以这里只信提示字段；非 JSON 时才退回原文，且**限长**。
    结论：错误诱因只能从「提示字段」里找，**业务正文是数据，不是信号**。
    """
    if isinstance(parsed, dict):
        # 只信提示字段；不做「整包兜底」，避免业务正文污染判断
        return (pick_message(parsed, "") or "").strip().lower()
    # 非 JSON（无 parsed）：只能看原始文本，且**限长**，避免大正文拖慢/误命中
    return (raw_text or "")[:600].strip().lower()


def looks_like_balance_error(parsed, raw_text=""):
    """识别余额/额度不足，便于引导用户充值而不是盲目重发。"""
    if code_is_balance_error(pick_code(parsed)):
        return True
    blob = _error_blob(parsed, raw_text)
    return any(hint in blob for hint in BALANCE_HINTS)


def looks_like_auth_error(parsed, raw_text=""):
    """识别鉴权类失败，便于给出「请重新提供 apikey」的明确指引。"""
    if code_is_auth_error(pick_code(parsed)):
        return True
    # 余额不足的提示里也可能出现「请登录」，必须先排除，避免误判为鉴权失败
    if looks_like_balance_error(parsed, raw_text):
        return False
    blob = _error_blob(parsed, raw_text)
    return any(hint in blob for hint in AUTH_HINTS) and any(bad in blob for bad in AUTH_BAD_WORDS)


def looks_like_transient_error(parsed, raw_text=""):
    """识别「上游临时不可用 / 被限流」类失败（明确的长等待或限流信号）。

    实测文案：「404,API 请求失败,请10分钟后，再重试」。
    这类错误**不做补发**：服务端自己要求等 10 分钟，而脚本的补发只等 2 秒，
    立即重发必然拿到同样的结果，只会白白多消耗一次额度。

    ⚠️ 只扫「提示字段」，**不扫响应正文**——否则某条笔记标题里的「1分钟」
    就会把成功的整页数据误判成限流（2026-10-01 实测事故，见 `_error_blob`）。
    """
    blob = _error_blob(parsed, raw_text)
    if not blob:
        return False
    # 成功态（code 为 200/0/1/10000 等）绝不可能是「上游临时故障」
    if isinstance(parsed, dict) and code_is_success(pick_code(parsed)):
        return False
    return any(re.search(pattern, blob) for pattern in TRANSIENT_PATTERNS)


def looks_like_action_forbidden(parsed, raw_text="", http_status=None):
    """识别「dr 动作名不被站点网关接受」——**与 apikey 无关**。

    实测形态：HTTP 403 + 裸文本 `forbidden`（非 JSON）。
    与「apikey 无效」（HTTP 200 + JSON code:403）严格区分：
    前者换任何密钥结果都一样，让用户去重新获取 apikey 是纯粹的无效劳动。
    """
    if parsed is not None:
        # 能解析成 JSON 就说明不是网关层的裸拒绝，交给后续分支处理
        return False
    if http_status is not None and http_status != 403:
        return False
    body = (raw_text or "").strip().lower()
    if not body:
        return False
    return body.startswith(FORBIDDEN_BODY_HINTS) and len(body) <= 120


def transport_error_payload(step, message, raw_text=""):
    """构造网络 / 等待超时类返回体（可补发）。"""
    return {
        "step": step,
        "error_code": "network_error",
        "error": message or "网络请求失败",
        "http_status": 0,
        "action_required": ("网络或等待问题：脚本会按策略补发一次；仍失败时请检查网络，"
                            "或把 --timeout 调大（上限 %d 秒）后重试。" % MAX_TIMEOUT),
        "raw": (raw_text or "")[:500],
    }


def transient_error_payload(step, parsed, raw_text, http_status):
    """构造统一的上游临时故障返回体。"""
    return {
        "step": step,
        "error_code": "upstream_busy",
        "error": pick_message(parsed, raw_text) or "上游接口暂时不可用",
        "http_status": http_status,
        "retry_after_seconds": TRANSIENT_RETRY_AFTER,
        "action_required": (
            "上游接口暂时不可用（服务端提示见 error 字段）。本次**不自动补发**——"
            "立即重发必然失败且会白扣额度。请等待约 10 分钟后重新执行同一条命令；"
            "已取到的结果无需重做，可从错误信息中的步骤继续。"
        ),
        "raw": (raw_text or "")[:500],
    }


def balance_error_payload(step, parsed, raw_text, http_status):
    """构造统一的余额不足返回体。"""
    return {
        "step": step,
        "error_code": "insufficient_balance",
        "error": pick_message(parsed, raw_text) or "账户余额不足",
        "http_status": http_status,
        "action_required": "请登录 %s 充值后重试（apikey 本身有效，无需重新获取）" % LOGIN_URL,
        "raw": (raw_text or "")[:500],
    }


def action_forbidden_payload(step, raw_text, http_status):
    """构造「接口动作不可用」返回体。"""
    return {
        "step": step,
        "error_code": "action_forbidden",
        "error": "站点网关拒绝了该接口动作（HTTP 403 forbidden）：%s" % step,
        "http_status": http_status,
        "action_required": (
            "站点不接受当前使用的接口动作名（dr 参数）。**这与 apikey 无关**"
            "（实测有效密钥与无效密钥返回完全相同），请不要重新获取 apikey。"
            "请确认动作名与站点实际开放的接口一致；若确认无误，"
            "说明该接口尚未对当前账号开放，需联系站点支持。"
        ),
        "raw": (raw_text or "")[:500],
    }


def auth_error_payload(step, parsed, raw_text, http_status):
    """构造统一的鉴权失败返回体。"""
    return {
        "step": step,
        "error_code": "unauthorized",
        "error": pick_message(parsed, raw_text) or (
            "鉴权失败，请登录 %s 获取有效的 apikey" % LOGIN_URL),
        "http_status": http_status,
        "action_required": "请登录 %s 获取 apikey，然后运行 --set-apikey 保存" % LOGIN_URL,
        "raw": (raw_text or "")[:500],
    }


def api_error_payload(step, parsed, raw_text, http_status):
    """构造「接口返回业务失败」的兜底返回体。"""
    return {
        "step": step,
        "error_code": "api_error",
        "error": pick_message(parsed, raw_text) or ("接口返回失败（HTTP %s）" % http_status),
        "http_status": http_status,
        "code": pick_code(parsed),
        "action_required": ("接口业务失败：脚本会按策略补发一次；若仍失败，"
                            "可加 --raw 查看原始响应，确认关键词与筛选条件是否正确。"),
        "raw": (raw_text or "")[:500],
    }


def empty_result_payload(step, parsed, raw_text=""):
    """接口返回成功、但响应里没有任何视频，也没有翻页凭据。"""
    return {
        "step": step,
        "error_code": "empty_result",
        "error": ("接口返回成功，但响应里没有视频列表（可能该关键词无结果，"
                  "或筛选条件过窄）"),
        "http_status": 200,
        "code": pick_code(parsed),
        "action_required": ("请核对关键词与筛选条件；加 --raw --human 可查看原始响应。"
                            "该情况会按策略补发一次。"),
        "raw": (raw_text or "")[:500],
    }


# --------------------------------------------------------------------------
# 响应结构解析
# --------------------------------------------------------------------------

def looks_like_video(item):
    """判断一个 dict 是否像「一条视频」。"""
    if not isinstance(item, dict):
        return False
    keys = {k.lower() for k in item.keys() if isinstance(k, str)}
    return any(k in keys for k in VIDEO_MARK_KEYS)


def pick_videos_list(parsed):
    """从响应里挑出「视频数组」。

    不同版本 / 不同动作的容器键不一致（aweme_info / aweme_list / search_result / data ...），
    这里先按候选键直取，再遍历整棵响应树，收集所有「像视频列表的数组」，取其中最长的那个。
    这样即便接口把列表挪到别的层级也不会解析失败。
    """
    if isinstance(parsed, dict):
        for key in VIDEO_LIST_KEYS:
            node = parsed.get(key)
            if isinstance(node, list):
                dicts = [x for x in node if isinstance(x, dict)]
                if dicts and any(looks_like_video(d) for d in dicts):
                    return dicts

    candidates = []

    def visit(node, depth):
        if depth > 4:
            return
        if isinstance(node, list):
            dicts = [x for x in node if isinstance(x, dict)]
            if dicts:
                hits = sum(1 for d in dicts if looks_like_video(d))
                if hits and hits >= max(1, len(dicts) // 2):
                    candidates.append(dicts)
            for sub in node:
                visit(sub, depth + 1)
        elif isinstance(node, dict):
            for sub in node.values():
                visit(sub, depth + 1)

    visit(parsed, 0)
    if not candidates:
        return []
    return max(candidates, key=len)


def normalize_token(val):
    """把翻页凭据归一化成字符串；空值/无效值返回 None。

    ℹ️ `offset` 首页传**数字 0**（站点约定），响应里也可能把 0 原样回显；
    这里刻意**不**把 0 归一成 None —— 它的语义是「第 1 页」而非「没有下一页」，
    是否到底由 `has_more` / 本页有无新内容 来判定（见 collect_keyword 的安全阀）。
    """
    if val is None or isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return str(int(val))
    text = str(val).strip()
    return text or None


SEARCH_ID_KEY_SET = {k.lower() for k in SEARCH_ID_KEYS}
BACKTRACE_KEY_SET = {k.lower() for k in BACKTRACE_KEYS}
OFFSET_KEY_SET = {k.lower() for k in OFFSET_KEYS}


def _top_scopes(parsed):
    """常见的一层容器（顶层 + data/result/page/pagination …）。"""
    scopes = []
    if isinstance(parsed, dict):
        scopes.append(parsed)
        for key in ("data", "result", "page", "pageInfo", "page_info",
                    "pagination", "extra", "extraData"):
            node = parsed.get(key)
            if isinstance(node, dict):
                scopes.append(node)
    return scopes


def _pick_scalar(parsed, key_set, blocklist=()):
    """在顶层/常见容器里按已知键名直取一个标量值（命中即返回）。"""
    block = {k.lower() for k in blocklist}
    for scope in _top_scopes(parsed):
        for key, val in scope.items():
            if not isinstance(key, str):
                continue
            low = key.lower()
            if low in key_set and low not in block:
                text = normalize_token(val)
                if text:
                    return text
    return None


def _find_scalar_deep(node, key_set, in_video=False, depth=0):
    """深度查找某个标量字段，但**不深入视频实体内部**。

    视频实体里也可能存在同名/相似的无关字段，若不排除会把记录字段误当成翻页凭据，
    导致翻页错乱。
    """
    if depth > 4:
        return None
    if isinstance(node, dict):
        is_video = looks_like_video(node)
        if not in_video and not is_video:
            for key, val in node.items():
                if isinstance(key, str) and key.lower() in key_set:
                    text = normalize_token(val)
                    if text:
                        return text
        for val in node.values():
            found = _find_scalar_deep(val, key_set, in_video or is_video, depth + 1)
            if found:
                return found
    elif isinstance(node, list):
        for val in node:
            found = _find_scalar_deep(val, key_set, in_video, depth + 1)
            if found:
                return found
    return None


def pick_search_id(parsed):
    """定位下一页的 search_id（顶层直取优先，命中即返回）。"""
    found = _pick_scalar(parsed, SEARCH_ID_KEY_SET, CURSOR_BLOCKLIST)
    if found:
        return found
    return _find_scalar_deep(parsed, SEARCH_ID_KEY_SET)


def pick_backtrace(parsed):
    """定位下一页的 backtrace（顶层直取优先，命中即返回）。"""
    found = _pick_scalar(parsed, BACKTRACE_KEY_SET, CURSOR_BLOCKLIST)
    if found:
        return found
    return _find_scalar_deep(parsed, BACKTRACE_KEY_SET)


def pick_offset(parsed):
    """定位下一页的 offset（顶层直取优先，命中即返回）。"""
    found = _pick_scalar(parsed, OFFSET_KEY_SET, CURSOR_BLOCKLIST)
    if found:
        return found
    return _find_scalar_deep(parsed, OFFSET_KEY_SET)


def pick_has_more(parsed):
    """读取「还有下一页」标记；没有该字段时返回 None（未知）。"""
    key_set = {k.lower() for k in HAS_MORE_KEYS}
    for scope in _top_scopes(parsed):
        for key, val in scope.items():
            if not isinstance(key, str) or key.lower() not in key_set:
                continue
            if isinstance(val, bool):
                return val
            if isinstance(val, (int, float)):
                return int(val) != 0
            text = str(val).strip().lower()
            if text in ("true", "1", "yes", "y"):
                return True
            if text in ("false", "0", "no", "n", ""):
                return False
    return None


def pick_total_count(parsed):
    """读取「该关键词总共有多少条」（站点实测返回 total_count）；没有则 None。

    只在顶层/常见容器里直取，**不做深度查找**：笔记实体内部也有各种 *_count
    （collect_count 等），深挖会把它们误当成总数。
    """
    key_set = {k.lower() for k in TOTAL_COUNT_KEYS}
    found = _pick_scalar(parsed, key_set, CURSOR_BLOCKLIST)
    if found is None:
        return None
    try:
        value = int(float(found))
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def format_time(val):
    """把 create_time 归一化。

    接口返回的是 Unix 秒级时间戳（如 1790244421），需转成可读时间；
    若接口某天改为返回日期字符串则原样保留。
    返回 (可读时间字符串, 原始时间戳或 None)。
    """
    if val is None or isinstance(val, bool):
        return None, None

    ts = None
    if isinstance(val, (int, float)):
        ts = float(val)
    else:
        text = str(val).strip()
        if not text:
            return None, None
        if re.fullmatch(r"\d{10,13}", text):
            ts = float(text)
        else:
            return text, None

    if ts > 1e12:      # 毫秒级时间戳
        ts = ts / 1000.0
    try:
        dt = datetime.datetime.fromtimestamp(ts, CN_TZ)
    except (OverflowError, OSError, ValueError, TypeError):
        return str(val), None
    return dt.strftime("%Y-%m-%d %H:%M:%S"), int(ts)


def to_int(val):
    """把 '1.2万' / '5.6w' / '1,234' / 1234 之类统一转成整数。"""
    if val is None or isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return int(val)
    text = str(val).strip().replace(",", "").replace("，", "")
    if not text:
        return None
    multiplier = 1
    if text.endswith("万") or text.lower().endswith("w"):
        multiplier, text = 10000, text[:-1]
    elif text.endswith("亿"):
        multiplier, text = 100000000, text[:-1]
    elif text.lower().endswith("k"):
        multiplier, text = 1000, text[:-1]
    try:
        return int(float(text) * multiplier)
    except ValueError:
        return None


def normalize_media(val):
    """把图片组/视频链接统一成 URL 列表。"""
    urls = []

    def push(item):
        if item is None:
            return
        if isinstance(item, str):
            text = item.strip()
            if not text:
                return
            if text.startswith("[") or text.startswith("{"):
                try:
                    push(json.loads(text))
                    return
                except ValueError:
                    pass
            for part in re.split(r"[,\n\r\t\s]+", text):
                part = part.strip().strip('"\'')
                if part.startswith("http"):
                    urls.append(part)
            return
        if isinstance(item, dict):
            for key in ("url", "url_default", "urlDefault", "img_url", "imgUrl",
                        "image_url", "imageUrl", "src", "video_url", "link",
                        "master_url", "masterUrl", "backup_url", "backupUrl",
                        "origin_video"):
                if key in item and isinstance(item[key], str):
                    push(item[key])
                    return
            for sub in item.values():
                push(sub)
            return
        if isinstance(item, list):
            for sub in item:
                push(sub)

    push(val)

    seen, out = set(), []
    for url in urls:
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


def _ms_to_text(ms):
    """毫秒 -> `mm:ss` / `h:mm:ss`。"""
    if ms is None:
        return None
    total = int(round(ms / 1000.0))
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours:
        return "%d:%02d:%02d" % (hours, minutes, seconds)
    return "%02d:%02d" % (minutes, seconds)


def format_duration(val):
    """把 video_duration 归一化成 (原值, 毫秒, 可读文本)。

    ℹ️ 本动作 2026-10-09 **实测** `video_duration` 是**毫秒**（292106 → 04:52），
    与同站点 `dy-uservideos` 口径一致；输出里显式给出
    `video_duration_unit: "ms"` 作为口径标注。
    站点若改给 "01:28" 这类字符串，也能解析回毫秒。
    ⚠️ 图文笔记（图文类搜索结果）该字段为 0，属正常，不代表解析失败。
    """
    if val is None or isinstance(val, bool):
        return None, None, None
    if isinstance(val, (int, float)):
        ms = int(val)
        if ms < 0:
            return None, None, None
        return ms, ms, _ms_to_text(ms)
    text = str(val).strip()
    if not text:
        return None, None, None
    if ":" in text:
        try:
            nums = [int(float(p)) for p in text.split(":")]
        except ValueError:
            return text, None, text
        seconds = 0
        for n in nums:
            seconds = seconds * 60 + n
        ms = seconds * 1000
        return text, ms, _ms_to_text(ms)
    try:
        ms = int(float(text))
    except ValueError:
        return text, None, text
    return ms, ms, _ms_to_text(ms)


def _as_text(val):
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return None
    text = str(val).strip()
    return text or None


def detect_video_type(share_url, play_addr, duration):
    """区分「视频」与「图文」（抖音把图文笔记也混在搜索结果里）。

    ⚠️ **为什么必须标出来**：图文条目的 `video_duration` 恒为 `0`，
    而 `video_play_addr` 指向的是**背景音乐 mp3**、**不是视频文件**。
    若不标注，消费方会把「时长 0」误读成短视频，并拿着 mp3 地址去当视频地址用。

    实测依据（2026-10-16，拿 2 页共 34 条真实搜索结果统计）：
        - `share_url` 含 `/share/note/` 的 9 条，**全部** `video_duration = 0` 且播放地址是 `.mp3`；
        - 其余 22 条 `video_duration > 0`，**无一**含 `/note/`。
        ⇒ 两类完全互斥，`/share/note/` 是 100% 可靠的判别式（`/note/` 亦可）。
    信息不足时返回 None，**不猜**。
    """
    su = share_url or ""
    pa = (play_addr or "").lower().split("?")[0]
    if "/share/note/" in su or "/note/" in su:
        return "图文"
    if pa.endswith(".mp3"):
        return "图文"
    if duration or play_addr:
        return "视频"
    return None


def build_video(raw, page_no, index):
    """把一条搜索结果归一化成标准字段（需求方给的 12 项）。"""

    def take(field):
        return deep_find(raw, FIELD_ALIASES[field])

    create_time, create_ts = format_time(take("create_time"))
    duration_val, duration_ms, duration_text = format_duration(take("video_duration"))

    aweme_id = _as_text(take("aweme_id"))
    covers = normalize_media(take("video_cover"))
    plays = normalize_media(take("video_play_addr"))
    site_urls = normalize_media(take("video_url"))
    share_url = take("share_url")
    if isinstance(share_url, dict):
        share_url = deep_find(share_url, ("url", "share_url", "shareUrl", "link"))

    video_cover = covers[0] if covers else None
    video_play_addr = plays[0] if plays else None
    # 站点返回的规范网页链接优先，取不到才按 aweme_id 本地拼接
    # （与同站点 dy-uservideos 的实测口径一致）
    video_url = (site_urls[0] if site_urls else None) or (
        "https://www.douyin.com/video/%s" % aweme_id if aweme_id else None)

    # ⚠️ 字段顺序即列序：前 12 项严格按 CANONICAL_FIELDS（需求方给定顺序），
    #    派生/辅助字段一律排在其后，方便导表与其它 kkAI 技能对齐。
    return {
        # ---------- 需求方给定的 12 项规范字段（顺序不可改）----------
        "aweme_id": aweme_id,
        "video_cover": video_cover,
        "desc": _as_text(take("desc")),
        "create_time": create_time,
        "nickname": _as_text(take("nickname")),
        "video_duration": duration_val,
        "digg_count": to_int(take("digg_count")),
        "comment_count": to_int(take("comment_count")),
        "collect_count": to_int(take("collect_count")),
        "share_count": to_int(take("share_count")),
        "video_play_addr": video_play_addr,
        "share_url": _as_text(share_url),
        # ---------- 以下为派生字段 / 口径标注 / 定位字段（非需求方 12 项）----------
        "create_time_ts": create_ts,
        # 与 video_duration 同值，保留旧名仅为兼容历史消费方
        "video_duration_ms": duration_ms,
        "video_duration_text": duration_text,
        # 口径标注：毫秒（2026-10-09 本动作实测确认，与同站点 dy-uservideos 一致）
        "video_duration_unit": "ms",
        # 兼容别名：规范网页链接（优先站点 aweme_url，缺失才本地拼接）
        "video_url": video_url,
        # 作品类型（视频 / 图文）：图文条目 video_duration=0 且播放地址是 BGM 的 mp3
        "video_type": detect_video_type(_as_text(share_url), video_play_addr,
                                        duration_val),
        "page": page_no,
        "index": index,
    }


def video_is_meaningful(video):
    """判断一条视频是否真的取到了内容（避免把空壳当结果返回）。"""
    if not video:
        return False
    for key in ("aweme_id", "desc", "create_time", "nickname", "digg_count",
                "collect_count", "comment_count", "share_count"):
        if video.get(key) not in (None, "", 0):
            return True
    return bool(video.get("video_play_addr") or video.get("video_cover")
                or video.get("share_url"))


# --------------------------------------------------------------------------
# 业务：搜索一页
# --------------------------------------------------------------------------

def _as_offset(value):
    """offset 首页传**数字 0**（不是空串、也不是字符串 "0"）；后续页按能转数字就转数字。"""
    if value is None or value == "":
        return 0
    text = str(value).strip()
    if not text:
        return 0
    try:
        return int(text)
    except ValueError:
        return text


def build_search_payload(keyword, page, backtrace=None, offset=None,
                         search_id=None, publish_time="",
                         sort_type=DEFAULT_SORT_TYPE):
    """构造 dy-search-v5 的请求体。

    `page` 是**页码**（第几页），默认 1，从 1 开始计数——不是偏移量、不是记录数。
    首页：backtrace / search_id 传空串，offset 传**数字 0**，page=1；
    第 N 页：page=N，并把第 N-1 页返回的 backtrace / offset / search_id **整组**带回。
    ⚠️ 三个翻页凭据缺一不可：漏掉任何一个都可能让站点重新返回第 1 页，白花一次额度。
    """
    payload = {
        "keyword": keyword,
        "backtrace": backtrace or "",
        "offset": _as_offset(offset),
        "page": int(page),
        "search_id": search_id or "",
        # 有站点默认值的参数**显式发送**，让请求体自解释；续采命令也带同样的取值，
        # 避免「首次按最多点赞采、续采悄悄换回综合」的口径漂移。
        "publish_time": publish_time or "_0",
        "sort_type": sort_type or DEFAULT_SORT_TYPE,
    }
    return payload


def step_search_page(keyword, page, apikey, backtrace=None, offset=None,
                     search_id=None, publish_time="", sort_type=DEFAULT_SORT_TYPE,
                     timeout=None, with_raw=False):
    """请求一页搜索结果（**只发一次请求**）。

    返回 (page_data, err)；page_data = {
        "videos": [...], "search_id": 或 None, "backtrace": 或 None,
        "offset": 或 None, "has_more": bool 或 None, "total_count": int 或 None,
        "raw": 原始响应片段, "raw_full": 完整原始响应（仅 with_raw=True 时）
    }
    """
    payload = build_search_payload(keyword, page, backtrace=backtrace,
                                   offset=offset, search_id=search_id,
                                   publish_time=publish_time,
                                   sort_type=sort_type)
    status, text, parsed = http_post(DR_SEARCH, payload, apikey, timeout=timeout)

    step_name = "%s(page=%s)" % (DR_SEARCH, page)

    if status == 0:
        return None, transport_error_payload(step_name, text)

    # 余额不足优先判定：其提示文案里也含「请登录」，否则会被鉴权分支抢走
    if looks_like_balance_error(parsed, text):
        return None, balance_error_payload(step_name, parsed, text, status)

    # 动作名被网关拒绝：与 apikey 无关，必须先于鉴权分支判定，
    # 否则会被 `status in (401, 403)` 抢走并误报「apikey 无效」
    if looks_like_action_forbidden(parsed, text, status):
        return None, action_forbidden_payload(step_name, text, status)

    if status in (401, 403) or looks_like_auth_error(parsed, text):
        return None, auth_error_payload(step_name, parsed, text, status)

    # 上游临时故障 / 被限流：不补发，明确告知稍后再试
    if looks_like_transient_error(parsed, text):
        return None, transient_error_payload(step_name, parsed, text, status)

    if parsed is None:
        return None, {
            "step": step_name,
            "error_code": "api_error",
            "error": "响应不是合法 JSON：%s" % (text or "")[:200],
            "http_status": status,
            "raw": (text or "")[:500],
        }

    if is_error_payload(parsed):
        return None, api_error_payload(step_name, parsed, text, status)

    raw_videos = pick_videos_list(parsed)
    videos = [v for v in raw_videos if looks_like_video(v)]
    aweme_ids = []
    for v in videos:
        aid = deep_find(v, FIELD_ALIASES["aweme_id"])
        if aid is not None:
            aweme_ids.append(str(aid))

    page_data = {
        "videos": videos,
        "search_id": pick_search_id(parsed),
        "backtrace": pick_backtrace(parsed),
        "offset": pick_offset(parsed),
        "has_more": pick_has_more(parsed),
        "total_count": pick_total_count(parsed),
        "aweme_ids": aweme_ids,
        "raw": (text or "")[:500],
        # 完整原始响应：只在 --raw 时留存，便于核对容器键 / 字段结构（切到 200KB 上限）
        "raw_full": (text or "")[:RAW_RESPONSE_LIMIT] if with_raw else None,
    }

    if not videos and not any(page_data[k] for k in ("search_id", "backtrace",
                                                     "offset")) \
            and page_data["has_more"] is None:
        return None, empty_result_payload(step_name, parsed, text)

    return page_data, None


def page_token(page_data):
    """提取一页的翻页凭据（用于判断是否前进 / 是否可用）。

    ⚠️ 本接口有 3 个凭据，**整组**决定下一页；offset 首页是数字 0，所以
    `token_is_empty()` 用「三者都为空/0」来判定，而不是只看真假。
    """
    return {
        "search_id": page_data.get("search_id") or "",
        "backtrace": page_data.get("backtrace") or "",
        "offset": "" if page_data.get("offset") in (None, 0, "0") else
                  str(page_data.get("offset")),
    }


def token_is_empty(token):
    """三个翻页凭据全为空 ⇒ 没有可用的下一页凭据。"""
    return not any(token.get(k) for k in ("search_id", "backtrace", "offset"))


# --------------------------------------------------------------------------
# 编排
# --------------------------------------------------------------------------

def _run_step(step_label, call, retry, retry_delay, result):
    """执行一步接口调用：首发 1 次；**仅当这次返回失败**时才补 1 次。

    严格遵守「每次仅请求一次，不要多次重复请求，直到返回失败再补一次」：
      - 成功 → 立即返回，不补发
      - 失败且错误可补发 → 等 retry_delay 秒后补 1 次，之后再失败也不再发第 3 次
      - 失败但错误不可补发（apikey 失效 / 余额不足 / 上游限流 / 动作被拒）→ 直接返回
      - retry=0 → 完全关闭补发

    返回 (value, err)。统计信息（request_count / retry_count / warnings）写入 result。
    """
    value, err = call()
    result["request_count"] += 1
    if err is None:
        return value, None

    error_code = err.get("error_code")
    if error_code in NON_RETRYABLE_ERROR_CODES:
        return None, err
    if not retry:
        return None, err

    # ---- 仅此处发生补发：失败后补一次 ----
    result["retry_count"] += 1
    first_error = err.get("error")
    if retry_delay > 0:
        time.sleep(retry_delay)
    value, err2 = call()
    result["request_count"] += 1

    if err2 is None:
        result["warnings"].append("%s 首次失败（%s），补发 1 次后成功。"
                                  % (step_label, first_error))
        return value, None

    # 两次都失败：保留第 2 次的错误为主，并把首次错误一并带上，便于判断是否为偶发
    err2 = dict(err2)
    err2["retried"] = True
    err2["first_attempt_error"] = first_error
    result["warnings"].append("%s 补发 1 次后仍失败。" % step_label)
    return None, err2


def collect_keyword(keyword, apikey="", pages=None, pages_specified=None,
                    start_page=DEFAULT_START_PAGE, start_search_id=None,
                    start_backtrace=None, start_offset=None,
                    publish_time="", sort_type=DEFAULT_SORT_TYPE, with_raw=False,
                    timeout=None, retry=DEFAULT_RETRY, retry_delay=RETRY_DELAY,
                    sleep=0.0):
    """采集一个关键词下的视频列表（分页）。

    页码语义：`start_page` 是**起始页码**（第几页，默认 1），`pages` 是**本次要采几页**。
    例如 start_page=1 / pages=2 → 请求第 1、2 页；start_page=3 / pages=1 → 只请求第 3 页。
    结果里每条视频的 `page` 就是它落在第几页。

    `pages` 语义（与 CLI 的 `--pages` 完全一致）：
      · 传 `None` / 不传  = **调用方没有说明采集几页** ⇒ 只采默认的 1 页，
        结果标 `pages_source="default"`，由调用方在采完后追问用户是否续采；
      · 传具体数字       = 用户明确指定 ⇒ `pages_source="explicit"`。
    ⚠️ 签名默认值刻意写 `None` 而不是 `DEFAULT_PAGES`：若写常量，
    「不传」与「明说 1 页」的内部状态完全相同，脚本就无法告诉调用方该不该追问。

    请求次数：每一页首发 1 次；**只有该页失败时才补 1 次**。
      正常情况 = pages 次请求（默认 1 页 = 1 次）；最坏 = pages × (1 + retry)。
    成功过的页不会被重跑，也不存在第 3 次请求。
    """
    # 目的：区分「用户没说」与「用户明说了 1 页」
    if pages is None:
        pages = DEFAULT_PAGES
        if pages_specified is None:
            pages_specified = False
    elif pages_specified is None:
        pages_specified = True

    result = {
        "ok": False,
        "keyword": keyword,
        "videos": [],
        "video_count": 0,
        "pages_requested": clamp_pages(pages),
        "start_page": clamp_start_page(start_page),
        "pages_fetched": 0,
        "has_more": None,
        "next_page": None,
        "next_search_id": None,
        "next_backtrace": None,
        "next_offset": None,
        "exhausted": False,
        # 站点返回的「该关键词总条数」；本动作实测不返回该字段，故恒为 None
        "total_count": None,
        # 跨页重复的视频条数（与顶层的 `duplicates_removed`（关键词去重）不是一回事，
        # 所以单独命名，避免单关键词时顶层字段被这里覆盖）
        "video_duplicates_removed": 0,
        "request_count": 0,
        "retry_count": 0,
        "errors": [],
        "warnings": [],
        "filters": {
            "publish_time": publish_time or "_0",
            "sort_type": sort_type or DEFAULT_SORT_TYPE,
        },
    }

    if not keyword:
        result["errors"].append({"step": DR_SEARCH, "error": "搜索关键词为空"})
        return result

    timeout = clamp_timeout(TIMEOUT if timeout is None else timeout)
    retry = clamp_retry(retry)
    retry_delay = clamp_retry_delay(retry_delay)
    pages = clamp_pages(pages)
    start_page = clamp_start_page(start_page)
    result["pages_requested"] = pages
    result["start_page"] = start_page

    token = {
        "search_id": start_search_id or "",
        "backtrace": start_backtrace or "",
        "offset": "" if start_offset in (None, 0, "0") else str(start_offset),
    }
    seen_ids = set()
    raw_total = 0

    # ---- 页码自检（纯本地判断，不消耗额度） ----
    # ① 从第 N(>1) 页起采，却没有带翻页凭据：接口约定「首页凭据为空，
    #    第 N 页须带第 N-1 页返回的凭据」，缺凭据时这次请求很可能拿不到第 N 页
    #    （返回第 1 页内容或空结果），等于白花 1 次额度。
    if start_page > MIN_START_PAGE and token_is_empty(token):
        result["warnings"].append(
            "起始页码为第 %d 页，但未提供翻页凭据（--backtrace / --offset / --search-id）。"
            "接口约定第 N 页须带第 N-1 页返回的凭据，本次可能取不到第 %d 页的内容。"
            "建议改用「--page 1 --pages %d」从第 1 页开始，"
            "或直接执行 next_action 给出的续采命令。"
            % (start_page, start_page, start_page))
    # ② 页码异常偏大：最常见的原因是把「采集页数」误填进 --page（两者只差一个字母）
    if not start_page_is_reasonable(start_page):
        result["warnings"].append(
            "起始页码 %d 超出常规范围（<=%d），请确认没有把「采集页数」误填到 --page；"
            "要一次采多页请用 --pages 指定页数。" % (start_page, MAX_REASONABLE_PAGE))

    for offset in range(pages):
        page_no = start_page + offset
        if offset > 0 and sleep and sleep > 0:
            time.sleep(sleep)

        # 本页「请求时使用」的凭据快照：用来判断服务端是不是把凭据原样回显了
        used_token = dict(token)
        page_data, err = _run_step(
            "第%d页(%s)" % (page_no, DR_SEARCH),
            lambda p=page_no, t=used_token: step_search_page(
                keyword, p, apikey, backtrace=t["backtrace"],
                offset=t["offset"], search_id=t["search_id"],
                publish_time=publish_time, sort_type=sort_type,
                timeout=timeout, with_raw=with_raw),
            retry, retry_delay, result)

        result["next_page"] = page_no
        if err:
            result["errors"].append(_wrap_step_error(err, with_raw))
            if err.get("error_code") in FATAL_ERROR_CODES:
                result["error_code"] = err["error_code"]
                result["action_required"] = err.get("action_required")
                if err.get("retry_after_seconds"):
                    result["retry_after_seconds"] = err["retry_after_seconds"]
            break

        page_videos = page_data.get("videos") or []
        raw_total += len(page_videos)
        result["pages_fetched"] += 1
        result["next_page"] = page_no + 1

        new_ids = []
        for raw in page_videos:
            video = build_video(raw, page_no, len(result["videos"]) + 1)
            if not video_is_meaningful(video):
                continue
            aid = video.get("aweme_id")
            if aid and aid in seen_ids:
                continue          # 跨页重复，只保留首次出现
            if aid:
                seen_ids.add(aid)
                new_ids.append(aid)
            else:
                # 没有主键的记录无法去重，按「有新内容」处理
                new_ids.append(None)
            result["videos"].append(video)

        result["video_count"] = len(result["videos"])
        result["has_more"] = page_data.get("has_more")
        result["next_search_id"] = page_data.get("search_id")
        result["next_backtrace"] = page_data.get("backtrace")
        result["next_offset"] = page_data.get("offset")
        if page_data.get("total_count") is not None:
            result["total_count"] = page_data["total_count"]
        if with_raw and page_data.get("raw_full"):
            result.setdefault("raw_responses", []).append(
                {"page": page_no, "body": page_data["raw_full"]})

        next_token = page_token(page_data)
        # 本页返回的凭据就是下一页要用的凭据
        token = next_token

        # ---- 安全阀（任一命中立即停止，绝不反复请求同一页） ----
        if not page_videos:
            result["exhausted"] = True
            if offset + 1 < pages:
                result["warnings"].append(
                    "第 %d 页未返回任何视频，判定已到末页，提前结束翻页"
                    "（少发 %d 次请求）。" % (page_no, pages - offset - 1))
            break

        if result["has_more"] is False:
            result["exhausted"] = True
            if offset + 1 < pages:
                result["warnings"].append(
                    "接口标记 has_more=false，判定已到末页，提前结束翻页"
                    "（少发 %d 次请求）。" % (pages - offset - 1))
            break

        if not new_ids:
            result["exhausted"] = True
            result["warnings"].append(
                "第 %d 页返回的视频与已采集的完全重复，判定翻页已失效，"
                "已停止（避免继续白花额度）。" % page_no)
            break

        if token_is_empty(next_token):
            # ⚠️ 「凭据没变」在本接口**不能**当停止条件：接口有页码参数，
            #    服务端可能把凭据原样回显、靠递增的 page 给出下一页
            #    （首页凭据本就是空串）。所以只在**凭据全空**时才判定没有下一页。
            result["warnings"].append(
                "第 %d 页未返回任何翻页凭据（backtrace / offset / search_id），"
                "但本页仍有新内容：若这是最后一页，说明站点就是此约定；"
                "否则请用 --raw 核对原始响应的凭据字段名。" % page_no)
            if result["has_more"] is not True:
                result["exhausted"] = True
                if offset + 1 < pages:
                    result["warnings"].append(
                        "判定已到末页，提前结束翻页（少发 %d 次请求）。"
                        % (pages - offset - 1))
                break

        if next_token == used_token and not token_is_empty(next_token):
            result["warnings"].append(
                "第 %d 页返回的翻页凭据与请求时相同（服务端回显），"
                "但本页仍有新内容，已按 page 继续推进。" % page_no)
    else:
        # 取满页数仍未结束，说明还有更多
        if result["pages_fetched"] and not token_is_empty(token):
            result["has_more"] = True

    result["video_duplicates_removed"] = max(0, raw_total - result["video_count"])
    result["video_count"] = len(result["videos"])
    # 采集页数来源：default = 用户未说明（本次走默认 1 页）/ explicit = 用户明确指定
    result["pages_source"] = "explicit" if pages_specified else "default"
    result["ok"] = not result["errors"] and bool(result["videos"])
    if not result["ok"] and not result["errors"]:
        result["warnings"].append(
            "接口调用成功，但该关键词没有取到任何视频。可能原因：关键词无结果、"
            "筛选条件过窄，或响应结构已变更（可加 --raw 用 --human 查看原始返回）。")
    result["next_action"] = build_next_action(result)
    return result


# --------------------------------------------------------------------------
# 「是否继续采更多页」的询问信息
# --------------------------------------------------------------------------

def _script_invocation():
    """续采命令里回显的脚本路径：优先用本次调用的 argv[0]，方便直接复制执行。"""
    argv0 = (sys.argv[0] or "").strip() if sys.argv else ""
    if argv0 and argv0 not in ("-c", "-m"):
        return argv0
    return os.path.basename(__file__)


def _quote(value):
    return '"%s"' % value


def build_resume_command(script, keyword, page, search_id=None, backtrace=None,
                         offset=None, pages=CONTINUE_SUGGESTED_PAGES,
                         publish_time="", sort_type=""):
    """拼一条可直接执行的续采命令（带 --page + **全部**翻页凭据，不会重复第 1 页）。"""
    parts = ["python", script, "--keyword", _quote(keyword)]
    parts += ["--page", str(page)]
    if search_id:
        parts += ["--search-id", _quote(search_id)]
    if backtrace:
        parts += ["--backtrace", _quote(backtrace)]
    if offset not in (None, "", 0, "0"):
        parts += ["--offset", _quote(str(offset))]
    if publish_time:
        parts += ["--publish-time", _quote(publish_time)]
    if sort_type:
        parts += ["--sort-type", _quote(sort_type)]
    parts += ["--pages", str(pages)]
    return " ".join(parts)


def build_next_action(search_result):
    """生成「采集完成后是否继续采更多页」的询问信息（本函数不发起任何请求）。

    只在「本次采集成功、且还有更多内容」时返回内容，
    其余情况（已到末页 / 没取到视频 / 有错误）返回 None，表示无需询问。

    **脚本自身不做交互式提问**：stdout 必须保持纯 JSON，且一旦阻塞等待 stdin，
    Agent 侧的调用就会挂住。所以这里只把「该不该问、怎么问、怎么续采」
    结构化输出，由调用方（AI 助手）据此向用户确认后再执行续采。
    """
    if search_result.get("errors") or not search_result.get("videos"):
        return None                     # 失败或空结果：不该问「要不要继续」
    if search_result.get("exhausted"):
        return None                     # 已到末页：没有下一页可采

    search_id = search_result.get("next_search_id") or ""
    backtrace = search_result.get("next_backtrace") or ""
    offset = search_result.get("next_offset")
    if not (search_id or backtrace or (offset not in (None, "", 0, "0"))):
        return None                     # 没有任何翻页凭据，续采无从下手

    script = _script_invocation()
    if " " in script:
        script = '"%s"' % script

    keyword = search_result.get("keyword") or ""
    resume_page = search_result.get("next_page") or (
        (search_result.get("start_page") or 1) + (search_result.get("pages_fetched") or 0))
    filters = search_result.get("filters") or {}
    command = build_resume_command(
        script, keyword, resume_page, search_id=search_id, backtrace=backtrace,
        offset=offset, pages=CONTINUE_SUGGESTED_PAGES,
        publish_time=filters.get("publish_time") or "",
        sort_type=filters.get("sort_type") or "")

    fetched = search_result.get("pages_fetched") or 0
    count = search_result.get("video_count") or 0
    total = search_result.get("total_count")
    pages_source = search_result.get("pages_source")
    if pages_source == "default":
        # 用户本来就没说采几页 ⇒ 问话里要把「这是默认只采 1 页」讲明，
        # 免得用户误以为「只采 1 页」是系统能力上限或自己要求过。
        question = ("你这次没有指定采集页数，我先只采了最近 %d 页，共 %d 条视频；"
                    "关键词「%s」还有更多内容。是否继续采集更多页？"
                    % (fetched, count, keyword))
    else:
        question = ("已采集 %d 页，共 %d 条视频，关键词「%s」还有更多内容。"
                    "是否继续采集更多页？" % (fetched, count, keyword))
    if total:
        question += "（站点称该关键词约 %d 条）" % total

    return {
        "ask_user": True,
        "reason": "has_more",
        "question": question,
        "keyword": keyword,
        "total_count": total,
        # 本次页数的来源：default = 用户未说明（走的默认 1 页）/ explicit = 用户指定
        "pages_source": pages_source,
        "pages_fetched": fetched,
        "suggested_pages": CONTINUE_SUGGESTED_PAGES,
        "resume_page": resume_page,
        "resume_search_id": search_id or None,
        "resume_backtrace": backtrace or None,
        "resume_offset": offset,
        "suggested_command": command,
        "cost_hint": ("续采用 --page + backtrace/offset/search_id 直接翻下一页，"
                      "不再重复请求第 1 页；每页消耗 1 次额度，仅当该页失败才会多补 1 次。"),
        "stop_hint": "用户表示不需要时，直接结束当前任务，不要再发任何请求。",
    }


def build_batch_next_action(results, skipped_keywords=None, pages=DEFAULT_PAGES):
    """批量（多关键词）撞上账户级错误时的续采询问信息。"""
    skipped_keywords = [k for k in (skipped_keywords or []) if k]
    fatal_code = None
    for r in results:
        for err in (r.get("errors") or []):
            if err.get("error_code") in FATAL_ERROR_CODES:
                fatal_code = err["error_code"]
                break
        if fatal_code:
            break
    if not (skipped_keywords and fatal_code):
        return None

    script = _script_invocation()
    if " " in script:
        script = '"%s"' % script
    parts = ["python", script]
    for kw in skipped_keywords:
        parts += ["--keyword", _quote(kw)]
    parts += ["--pages", str(clamp_pages(pages))]

    return {
        "ask_user": True,
        "reason": "fatal_error",
        "error_code": fatal_code,
        "question": ("采集遇到账户/接口级错误（%s）后已中止，还有 %d 个关键词没有采集。"
                     "按上面的处理方式解决后，是否继续采集剩余这 %d 个关键词？"
                     % (fatal_code, len(skipped_keywords), len(skipped_keywords))),
        "keywords": skipped_keywords,
        "suggested_command": " ".join(parts),
        "cost_hint": ("继续采集剩余 %d 个关键词；这类错误没解决前重跑仍会失败，请先处理。"
                      % len(skipped_keywords)),
        "stop_hint": "用户表示不需要时，直接结束当前任务，不要再发任何请求。",
    }


def _wrap_step_error(err, with_raw):
    """把步骤错误整理成用户可见的 errors[] 元素。"""
    note = {"step": err.get("step"), "error": err.get("error")}
    for key in ("error_code", "code", "http_status", "retry_after_seconds",
                "action_required", "first_attempt_error"):
        if err.get(key) is not None:
            note[key] = err[key]
    if err.get("retried"):
        note["retried"] = True
    if with_raw:
        note["raw_response"] = err.get("raw")
    return note


def _show_num(value):
    """数值展示：缺失时显示 `-`，**不把 null 显示成 0**（不编造）。"""
    return "-" if value is None else value


def format_duration_text(video):
    """时长的展示形态：`04:52（292106 ms）`；只有可读文本时给文本，都没有则 `-`。"""
    text = video.get("video_duration_text")
    raw = video.get("video_duration")
    if text and raw:
        return "%s（%s ms）" % (text, raw)
    return text or "-"


def build_summary(video):
    """生成便于展示的互动数据摘要行（保留给兼容调用；展示层已改为逐项列出）。"""
    parts = []
    if video.get("digg_count") is not None:
        parts.append("赞 %s" % video["digg_count"])
    if video.get("comment_count") is not None:
        parts.append("评 %s" % video["comment_count"])
    if video.get("collect_count") is not None:
        parts.append("藏 %s" % video["collect_count"])
    if video.get("share_count") is not None:
        parts.append("转 %s" % video["share_count"])
    return " | ".join(parts)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def print_human(results, invalid=None, skipped=None, stream=None,
                warnings=None):
    """人类可读的控制台输出（默认写 stderr，保证 stdout 是纯 JSON）。"""
    out = stream or sys.stderr

    def emit(line):
        out.write(line + "\n")

    if len(results) > 1:
        ok_n = sum(1 for r in results if r.get("ok"))
        emit("批量搜索：共 %d 个关键词，成功 %d 个，失败 %d 个"
             % (len(results), ok_n, len(results) - ok_n))
    for warn in warnings or []:
        emit("[顶层提示] %s" % warn)

    for item in results:
        emit("=" * 62)
        emit("关键词    : %s" % (item.get("keyword") or "-"))
        filters = item.get("filters") or {}
        publish = filters.get("publish_time") or DEFAULT_PUBLISH_TIME
        sort_value = filters.get("sort_type") or DEFAULT_SORT_TYPE
        active = [("%s=%s" % (k, v)) for k, v in
                  (("publish_time", publish_time_label(publish)),
                   ("sort_type", sort_type_label(sort_value))) if v]
        if active:
            emit("筛选      : %s" % " ".join(active))
        # 页码（第几页）与页数（采几页）分开写，避免混淆
        fetched = item.get("pages_fetched") or 0
        start = item.get("start_page") or MIN_START_PAGE
        span = ("第 %s 页" % start if fetched <= 1
                else "第 %s-%s 页" % (start, start + fetched - 1))
        emit("页码/页数 : 起于第 %s 页，本次采 %s 页 → 实际取回 %s 页（%s）"
             % (start, item.get("pages_requested"), fetched, span))
        emit("视频条数  : %s" % item.get("video_count"))
        if item.get("total_count") is not None:
            emit("总计条数  : 该关键词共约 %s 条（站点 total_count）"
                 % item["total_count"])
        if item.get("next_backtrace"):
            emit("下页 backtrace : %s" % item["next_backtrace"])
        if item.get("next_offset") is not None:
            emit("下页 offset    : %s" % item["next_offset"])
        if item.get("next_search_id"):
            emit("下页 search_id : %s" % item["next_search_id"])
        for video in item.get("videos") or []:
            emit("-" * 62)
            emit("  #%s [第%s页]" % (video.get("index"), video.get("page")))
            # 12 项规范字段**按需求方给定顺序**逐条展示，中文名与
            # CANONICAL_FIELD_LABELS 同源，避免展示层与 JSON 层口径漂移。
            lb = CANONICAL_FIELD_LABELS
            emit("  %s : %s" % (lb["aweme_id"], video.get("aweme_id") or "-"))
            emit("  %s : %s" % (lb["video_cover"], video.get("video_cover") or "-"))
            emit("  %s : %s" % (lb["desc"], (video.get("desc") or "-")[:100]))
            emit("  %s : %s" % (lb["create_time"], video.get("create_time") or "-"))
            emit("  %s : %s" % (lb["nickname"], video.get("nickname") or "-"))
            emit("  %s : %s" % (lb["video_duration"], format_duration_text(video)))
            emit("  %s : %s" % (lb["digg_count"], _show_num(video.get("digg_count"))))
            emit("  %s : %s" % (lb["comment_count"],
                                _show_num(video.get("comment_count"))))
            emit("  %s : %s" % (lb["collect_count"],
                                _show_num(video.get("collect_count"))))
            emit("  %s : %s" % (lb["share_count"], _show_num(video.get("share_count"))))
            emit("  %s : %s" % (lb["video_play_addr"],
                                video.get("video_play_addr") or "-"))
            emit("  %s : %s" % (lb["share_url"], video.get("share_url") or "-"))
            # 图文条目额外提示（避免把 BGM 的 mp3 当成视频文件地址）
            if video.get("video_type") == "图文":
                emit("  ⚠️ 作品类型 : 图文（时长恒为 0；上面的「视频文件地址」"
                     "实为 BGM 音频 mp3，不是视频文件）")
        for err in item.get("errors") or []:
            emit("[失败] %s -> %s" % (err.get("step"), err.get("error")))
        for warn in item.get("warnings") or []:
            emit("[提示] %s" % warn)

        action = item.get("next_action")
        if action:
            emit("-" * 62)
            emit("➡️  %s" % action["question"])
            emit("    如需继续，执行：%s" % action["suggested_command"])
            emit("    （%s）" % action["cost_hint"])
        elif item.get("videos") and item.get("exhausted"):
            emit("-" * 62)
            emit("✅ 已到末页，无需继续翻页。")

    if skipped:
        emit("=" * 62)
        emit("⛔ 因账户/接口级错误提前中止，未采集的关键词：%s" % "、".join(skipped))
    if invalid:
        emit("=" * 62)
        emit("⚠️ 空关键词已跳过 %d 个" % len(invalid))
    out.flush()


def build_parser():
    parser = argparse.ArgumentParser(
        prog="dy_search_collect",
        description=("抖音关键词搜索视频数据采集助手_kkAI："
                     "关键词 -> 视频ID / 视频描述 / 发布时间 / 用户昵称 / 视频地址 / 视频时长 / "
                     "点赞数 / 评论数 / 收藏数 / 分享数 / 分享链接"),
        epilog=("页码说明：接口的 page 是页码（第几页），默认 1，从 1 开始计数。\n"
                "  --page  = 从第几页开始（页码）\n"
                "  --pages = 本次采几页（页数）\n"
                "\n"
                "示例：\n"
                "  # 关键词「WorkBuddy教程」，默认只采 1 页\n"
                "  python %(prog)s --keyword \"WorkBuddy教程\"\n"
                "  # 采集 2 页（第 1、2 页）\n"
                "  python %(prog)s --keyword \"WorkBuddy教程\" --pages 2\n"
                "  # 带筛选：一周内 + 最多点赞，采 2 页\n"
                "  python %(prog)s --keyword \"WorkBuddy教程\" --publish-time 一周内 "
                "--sort-type 最多点赞 --pages 2\n"
                "  # 续采：从第 3 页继续（页码 + 上一页返回的三个凭据）\n"
                "  python %(prog)s --keyword \"WorkBuddy教程\" --page 3 "
                "--backtrace <上页返回> --offset <上页返回> --search-id <上页返回> --pages 1\n"),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--keyword", "-k", action="append", default=[],
                        help=("搜索关键词，可重复传入以一次搜多个词；"
                              "一个值内也可用 `|` / `;` / 换行分隔多个关键词"
                              "（空格与逗号不会被当作分隔符，因为关键词本身可能含空格）"))
    parser.add_argument("--file", "-f",
                        help="文本文件，每行一个关键词（批量搜索；`#` 开头为注释）")
    parser.add_argument("--pages", "-p", type=int, default=None, metavar="N",
                        help=("采集页数（本次要采几页，**不是页码**），取值 %d-%d"
                              "（**默认 %d**，即只采第 1 页）。不传就只采 1 页；"
                              "采完若还有更多内容，结果里的 next_action "
                              "会给出续采命令，由助手询问用户是否继续，而不是一次刷很多页。"
                              "例：--pages 2 = 从起始页开始连采 2 页。"
                              % (MIN_PAGES, MAX_PAGES, DEFAULT_PAGES)))
    parser.add_argument("--page", "--start-page", dest="page", type=int,
                        default=DEFAULT_START_PAGE, metavar="N",
                        help=("起始页码，即**从第几页开始**（默认 %d，接口的 page 从 1 开始"
                              "计数，首页 backtrace / search_id 为空、offset 为 0）。"
                              "续采时用 next_action 给出的页码，配合 --backtrace / "
                              "--offset / --search-id 直接翻到下一页，避免重复请求第 1 页。"
                              "注意与 --pages（采几页）区分：--page 3 --pages 2 = 采第 3、4 页。"
                              % DEFAULT_START_PAGE))
    parser.add_argument("--backtrace", default="",
                        help="翻页凭据 backtrace（首页留空，续采用上一页返回的值）")
    parser.add_argument("--offset", default=None,
                        help="翻页偏移游标 offset（首页为 0 或留空，续采用上一页返回的值）")
    parser.add_argument("--search-id", default="",
                        help="搜索ID search_id（首页留空，续采用上一页返回的值）")
    parser.add_argument("--publish-time", default="", metavar="VALUE",
                        help=("发布时间筛选（默认 _0 = 不限）。站点取值：_0 不限 / _1 一天之内 / "
                              "_7 一周之内 / _180 半年之内；"
                              "也接受 一天内 / 一周内 / 半年内 / day / week 等常见写法"))
    parser.add_argument("--sort-type", default="", metavar="VALUE",
                        help=("排序方式，默认 _0（综合）。站点取值：_0 综合（默认）/ "
                              "_1 最多点赞 / _2 最新发布；"
                              "也接受「最多点赞 / 最新发布 / 最热 / hot / latest」等写法"))
    parser.add_argument("--apikey",
                        help="临时指定 apikey（不推荐，优先用环境变量或密钥文件）")
    parser.add_argument("--set-apikey", metavar="KEY",
                        help="把 apikey 写入本地密钥文件 %s" % KEY_FILE)
    parser.add_argument("--check-key", action="store_true",
                        help="检查 apikey 是否已配置（不发起采集请求）")
    parser.add_argument("--output", "-o", help="把 JSON 结果写入指定文件")
    parser.add_argument("--compact", action="store_true", help="JSON 使用紧凑格式")
    parser.add_argument("--human", action="store_true",
                        help="额外在 stderr 打印人类可读摘要（stdout 始终为纯 JSON）")
    parser.add_argument("--raw", action="store_true",
                        help=("保留原始响应：失败步骤的响应片段 + 每页的完整响应"
                              "（结果里为 raw_responses，上限 %d 字符/页），"
                              "便于核对容器键与字段结构" % RAW_RESPONSE_LIMIT))
    parser.add_argument("--timeout", type=float, default=TIMEOUT, metavar="SECONDS",
                        help=("单次请求的等待上限秒数，取值 %d-%d（默认 %d）。"
                              "接口为排队型服务，等待时间可能较长；"
                              "0 表示不设超时、一直等到服务端返回。"
                              % (MIN_TIMEOUT, MAX_TIMEOUT, int(TIMEOUT))))
    parser.add_argument("--retry", type=int, default=DEFAULT_RETRY, metavar="N",
                        help=("失败后的补发次数，取值 %d-%d（默认 %d）。"
                              "脚本先按正常方式请求一次，**只有返回失败时**才补一次；"
                              "成功不补发。传 0 可完全关闭补发。"
                              % (MIN_RETRY, MAX_RETRY, DEFAULT_RETRY)))
    parser.add_argument("--retry-delay", type=float, default=RETRY_DELAY, metavar="SECONDS",
                        help="补发前的等待秒数（默认 %.1f，0 表示立即补发）" % RETRY_DELAY)
    parser.add_argument("--sleep", type=float, default=1.0,
                        help="翻页 / 多关键词之间的间隔秒数（默认 1.0；不影响单页请求次数）")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    # --- 保存 apikey ---
    if args.set_apikey:
        try:
            path = save_apikey(args.set_apikey)
        except ValueError as exc:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
            return 2
        print(json.dumps({
            "ok": True,
            "action": "set-apikey",
            "key_file": path,
            "masked": mask_key(args.set_apikey.strip()),
            "message": "apikey 已保存到本地密钥文件，后续调用无需再传。",
        }, ensure_ascii=False, indent=2))
        return 0

    apikey, source = load_apikey(args.apikey)

    # --- 检查 apikey ---
    if args.check_key:
        print(json.dumps({
            "ok": bool(apikey),
            "apikey_configured": bool(apikey),
            "source": source,
            "masked": mask_key(apikey) if apikey else None,
            "key_file": KEY_FILE,
            "login_url": LOGIN_URL,
            "message": ("apikey 已配置，可以开始采集。" if apikey else
                        "未检测到 apikey。请登录 %s 获取 apikey，"
                        "然后运行：python %s --set-apikey <你的apikey>" % (
                            LOGIN_URL, os.path.basename(__file__))),
        }, ensure_ascii=False, indent=2))
        return 0

    # --- 收集关键词（纯本地解析，不消耗额度） ---
    raw_keywords = []
    for value in args.keyword:
        raw_keywords.extend(split_keywords(value))
    if args.file:
        if not os.path.isfile(args.file):
            print(json.dumps({"ok": False, "error": "找不到目标文件：%s" % args.file},
                             ensure_ascii=False), file=sys.stderr)
            return 2
        with open(args.file, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                raw_keywords.extend(split_keywords(line))

    if not raw_keywords:
        parser.print_help(sys.stderr)
        print(json.dumps({
            "ok": False,
            "error": "invalid_keyword",
            "message": "请通过 --keyword 传入搜索关键词（多个关键词用 `|` 分隔或重复传参），"
                       "或用 --file 指定文件",
        }, ensure_ascii=False), file=sys.stderr)
        return 2

    keywords, duplicates = [], 0
    seen = set()
    for kw in raw_keywords:
        key = kw.lower()
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        keywords.append(kw)

    # --- 缺少 apikey 的友好提示 ---
    if not apikey:
        payload = {
            "ok": False,
            "error": "missing_apikey",
            "message": ("未检测到 apikey，无法调用采集接口。请登录 %s 获取 apikey；"
                        "获取后请提示用户提供，并通过 --set-apikey 保存到本地密钥文件，"
                        "不要把 apikey 写进脚本。" % LOGIN_URL),
            "login_url": LOGIN_URL,
            "key_file": KEY_FILE,
            "hint": "python %s --set-apikey <你的apikey>" % os.path.basename(__file__),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 3

    # --- 逐个关键词采集 ---
    timeout = clamp_timeout(args.timeout)
    retry = clamp_retry(args.retry)
    retry_delay = clamp_retry_delay(args.retry_delay)
    # 采集页数：CLI 的 --pages 默认是 None（**不是** DEFAULT_PAGES），
    # 这样才分得清「用户没说明」与「用户明说了 1 页」——
    # 前者采完必须追问是否续采，后者可以直接收尾。
    pages_specified = args.pages is not None
    pages = clamp_pages(args.pages)
    start_page = clamp_start_page(args.page)
    publish_time = normalize_publish_time(args.publish_time)
    sort_type = normalize_sort_type(args.sort_type)

    results = []
    skipped = []
    batch_warnings = []

    # 翻页凭据是「某一个关键词的某一页」的上下文，跨关键词套用会取到无关结果：
    # 多关键词时同一份 backtrace / offset / search_id 会被反复使用，必须提醒。
    if len(keywords) > 1 and (args.backtrace or args.offset not in (None, "", 0, "0")
                              or args.search_id):
        batch_warnings.append(
            "一次搜索多个关键词时，翻页凭据（--backtrace / --offset / --search-id）"
            "只对应上一页所属的那个关键词，套用到其它关键词会取到与该词无关的结果。"
            "多关键词请先不带凭据采第 1 页，再按各关键词的 next_action 分别续采。")
    # 从第 N(>1) 页起采却没带凭据：接口约定第 N 页须带第 N-1 页的凭据，
    # 否则多半取不回那一页（白花 1 次额度）。纯本地告警，不改变请求。
    if start_page > MIN_START_PAGE and not (args.backtrace or args.search_id
                                            or args.offset not in (None, "", 0, "0")):
        batch_warnings.append(
            "起始页码为第 %d 页，但未提供翻页凭据（--backtrace / --offset / --search-id）："
            "接口约定第 N 页须带第 N-1 页返回的凭据，本次可能取不到第 %d 页的内容。"
            "建议从第 1 页起采，或直接执行 next_action 给出的续采命令。"
            % (start_page, start_page))

    for idx, kw in enumerate(keywords):
        if idx > 0 and args.sleep and args.sleep > 0:
            time.sleep(args.sleep)
        r = collect_keyword(
            kw, apikey=apikey, pages=args.pages, pages_specified=pages_specified,
            start_page=start_page, start_backtrace=args.backtrace,
            start_offset=args.offset, start_search_id=args.search_id,
            publish_time=publish_time, sort_type=sort_type,
            with_raw=args.raw, timeout=timeout, retry=retry,
            retry_delay=retry_delay, sleep=args.sleep)
        results.append(r)
        # 账户/接口级错误（余额不足 / 密钥失效 / 上游限流 / 动作被拒）对后面每个
        # 关键词都会是同样的结果，立刻中止批量，避免对着剩下的关键词白刷额度。
        fatal = next((e for e in (r.get("errors") or [])
                      if e.get("error_code") in FATAL_ERROR_CODES), None)
        if fatal:
            skipped = keywords[idx + 1:]
            break

    succeeded = sum(1 for r in results if r.get("ok"))
    total_keywords = len(results) + len(skipped)

    # 本次实际取到的最后一个页码（页码 = 起始页码 + 已取回页数 - 1）。
    # 与 pages（页数）区分开，避免把「采了几页」和「采到第几页」混为一谈。
    end_page = None
    for r in results:
        fetched = r.get("pages_fetched") or 0
        if fetched:
            last = (r.get("start_page") or MIN_START_PAGE) + fetched - 1
            end_page = last if end_page is None else max(end_page, last)

    output = {
        "ok": succeeded == total_keywords,
        "total_keywords": total_keywords,
        "succeeded": succeeded,
        "failed": total_keywords - succeeded,
        "total_videos": sum(r.get("video_count") or 0 for r in results),
        "apikey_source": source,
        "timeout_seconds": timeout,
        "retry": retry,
        "pages": pages,
        # 页数来源：default = 用户未说明（本次走默认 1 页，采完须追问是否续采）
        #           explicit = 用户明确指定页数
        "pages_source": "explicit" if pages_specified else "default",
        "start_page": start_page,
        "end_page": end_page,
        "filters": {
            "publish_time": publish_time,
            "sort_type": sort_type,
        },
        # 每个关键词每页的请求次数上限：1 次首发 + 最多 retry 次补发
        "max_requests_per_page": 1 + retry,
        "max_requests_per_keyword": pages * (1 + retry),
        "duplicates_removed": duplicates,
        # 顶层提示：批量层面的注意事项（与每个关键词自己的 warnings 区分开，
        # 单关键词时两者会合并，见下方平铺逻辑）
        "warnings": list(batch_warnings),
        "aborted": bool(skipped),
        "skipped_count": len(skipped),
        "skipped_keywords": skipped,
        "total_requests": sum(r.get("request_count") or 0 for r in results),
        "total_retries": sum(r.get("retry_count") or 0 for r in results),
        "next_action": None,
        "results": results,
    }

    # 未指定采集页数时，明确写一条自检提示，让调用方一眼看出「这 1 页是默认值」。
    if not pages_specified:
        output["warnings"] = list(batch_warnings) + [
            "未指定采集页数，已按默认只采 %d 页（DEFAULT_PAGES=%d）："
            "用户没有说明采集几页时不擅自多采；"
            "采完若还有更多内容，结果里的 next_action 会提示是否续采。"
            % (DEFAULT_PAGES, DEFAULT_PAGES)]
        batch_warnings = output["warnings"]

    # next_action：批量中止优先（更需要用户介入），否则是单关键词的「是否续采」
    batch_action = build_batch_next_action(results, skipped_keywords=skipped,
                                          pages=pages)
    if batch_action:
        output["next_action"] = batch_action
    elif len(results) == 1:
        output["next_action"] = results[0].get("next_action")
    else:
        pending = [r for r in results if r.get("next_action")]
        if pending:
            first = pending[0]
            first_action = dict(first["next_action"])
            first_action["per_keyword"] = [
                {
                    "keyword": r["keyword"],
                    "resume_page": r["next_action"]["resume_page"],
                    "resume_backtrace": r["next_action"]["resume_backtrace"],
                    "resume_offset": r["next_action"]["resume_offset"],
                    "resume_search_id": r["next_action"]["resume_search_id"],
                    "suggested_command": r["next_action"]["suggested_command"],
                }
                for r in pending
            ]
            output["next_action"] = first_action

    if len(results) == 1:
        # 单关键词时结果字段平铺到顶层，但**顶层专有字段必须重新写回**，
        # 否则会被单条结果里的同名字段（如两种不同含义的重复计数、warnings）覆盖掉。
        merged_warnings = list(batch_warnings) + list(results[0].get("warnings") or [])
        output.update(results[0])
        output["ok"] = succeeded == total_keywords
        output["duplicates_removed"] = duplicates
        output["warnings"] = merged_warnings
        output["end_page"] = end_page
        output["pages_source"] = "explicit" if pages_specified else "default"
        # 单关键词：顶层 next_action 也统一用这一份
        output["next_action"] = batch_action or results[0].get("next_action")

    text = json.dumps(output, ensure_ascii=False,
                      indent=None if args.compact else 2,
                      separators=(",", ":") if args.compact else None)

    if args.output:
        out_path = os.path.abspath(args.output)
        out_dir = os.path.dirname(out_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("JSON 结果已写入：%s" % out_path, file=sys.stderr)

    if args.human:
        print_human(results, skipped=skipped, warnings=batch_warnings)

    print(text)
    return 0 if (succeeded == total_keywords) else 1


if __name__ == "__main__":
    sys.exit(main())

---
name: dy-search-collector-kkai
slug: dy-search-collector-kkai
display_name: 抖音关键词搜索视频数据采集助手_kkAI
displayName: 抖音关键词搜索视频数据采集助手_kkAI
display_name_en: Douyin Keyword Search Videos Collector Assistant (kkAI)
description: 输入关键词，返回视频列表数据。默认只采集 1 页，采完询问用户是否继续采更多页；输出视频ID、视频封面、视频描述、发布时间、用户昵称、视频时长、点赞数、评论数、收藏数、分享数、视频文件地址与视频分享链接，共 12 项数据（并标注作品类型 视频/图文）；当用户需要按关键词搜索抖音视频、抓取/导出搜索结果、筛选热门或最新内容、分析某话题的爆款视频时使用
description_zh: 输入抖音搜索关键词，逐页采集该关键词下的视频列表：视频ID 视频封面 视频描述 发布时间 用户昵称 视频时长 点赞数 评论数 收藏数 分享数 视频文件地址 视频分享链接，共 12 项数据（另标注作品类型「视频/图文」）；**默认只采 1 页，采完由助手询问用户是否继续采更多页**；支持发布时间筛选（一天/一周/半年）、排序（综合/最多点赞/最新发布）、backtrace+offset+search_id 三凭据翻页续采、跨页去重与 JSON 导出。
description_en: Collect Douyin videos by keyword search. Collects 1 page by default and then asks the user whether to continue with more pages; supports publish-time and sort filters, backtrace/offset/search_id-based pagination, cross-page dedup and JSON export.
summary: 输入关键词，拉取抖音搜索结果的视频列表，输出视频 ID、封面、描述、发布时间、昵称、时长、点赞/评论/收藏/分享、视频文件地址与分享链接共 12 项数据（并标注作品类型 视频/图文）；**默认只采 1 页**，采完若还有更多内容会询问用户是否继续采；支持筛选、排序、三凭据续采与跨页去重。
tags:
  - 抖音
  - 关键词搜索
  - 数据采集
  - 内容运营
  - 爆款分析
category: search
version: 1.3.0
author: WorkBuddy
agent_created: true
dependency:
  python:
    - 无第三方依赖（纯标准库：urllib.request, json, os, sys, re, time, threading, argparse, datetime）
---

# 抖音关键词搜索视频数据采集助手_kkAI

> Skill ID：`dy-search-collector-kkai`（ASCII 标识，便于工具链调用与路径处理）
> 显示名：抖音关键词搜索视频数据采集助手_kkAI

## 1. 简介

输入一个**搜索关键词**，按设定的「采集页数」逐页拉取该关键词下的**视频搜索结果列表**，每条视频返回 12 项数据：

> 视频ID · 视频封面 · 视频描述 · 发布时间 · 用户昵称 · 视频时长
> · 点赞数 · 评论数 · 收藏数 · 分享数 · 视频文件地址 · 视频分享链接

（另附 `video_type` 标注作品类型 `视频` / `图文` —— 图文条目的「视频文件地址」实为 BGM 音频，见 §1.3）

适用于话题盘点、竞品选题拆解、爆款视频筛选、关键词舆情归档与批量导出等场景。

> 与同族技能的区别：本技能对接的是抖音的**关键词搜索**接口（`dr=dy-search-v5`），
> 入参是 `keyword` + 筛选/排序，翻页靠 **3 个凭据**（`backtrace` / `offset` / `search_id`）+ `page`，
> 而不是主页列表的单个 `max_cursor`。

**试试这样使用**

- 关键词：`WorkBuddy教程`
- 采集页数：`1`（**默认只采 1 页**；采完若还有更多内容，助手会先问用户"是否继续采更多页"）
- 可选筛选：发布时间（一天内 / 一周内 / 半年内）、排序（综合 / 最多点赞 / 最新发布）

### 1.1 两条硬性约束（改动前必读）

**约束一：每一步只请求一次；只有失败才补一次重试，且最多补一次。**

```
每一页：
    请求 1 次
    若成功            -> 结束该页（不重试）
    若失败且错误可重试 -> 等 2 秒后重试 1 次，之后无论成败都不再发第 3 次
    若失败且错误不可重试 -> 结束该页（重发也不会有不同结果，只会浪费额度）
       不可重试的错误：unauthorized（apikey 失效 / 未带密钥）、insufficient_balance（余额不足）、
                        upstream_busy（上游临时故障/限流，服务端要求等 10 分钟）、
                        action_forbidden（动作名被站点网关拒绝，重发多少次都一样）
```

由此得到的请求次数：

| 情况 | 请求次数 |
| ---- | -------- |
| 默认 1 页 | **1 次** |
| 采集 N 页（各页均成功） | **N 次** |
| 某一页失败一次后重试成功 | +1 次 |
| 各页都失败一次并各重试一次（最坏） | 页数 × 2（**绝不会有第 3 次尝试**） |

成功过的页不会被重跑；不做轮询、不做并发。`--retry 0` 可完全关闭重试。

**约束二：等待时间为 0-600 秒，请耐心等待。**
该接口是排队型服务，单次请求的返回耗时在 0-600 秒之间浮动，请求发出后长时间无响应属于正常现象。
默认等待上限 **600 秒**，可用 `--timeout` 调整（取值 `0-600`，`0` 表示不设超时、一直等到服务端返回）。
等待期间脚本每 15 秒向 stderr 打印一次心跳（`[等待中] …`），**不会因为"看起来卡住了"就中途重发**。

### 1.2 翻页机制与安全阀（改脚本前必读）

本接口是**「页码 + 三凭据」混合翻页**，比单一游标更容易刷坏额度：

| 参数 | 首页取值 | 第 N 页取值 |
| ---- | -------- | ----------- |
| `page` | `1` | `N`（每次 +1） |
| `backtrace` | 空串 `""` | 上一页响应返回的 `backtrace` |
| `offset` | **数字 `0`** | 上一页响应返回的 `offset` |
| `search_id` | 空串 `""` | 上一页响应返回的 `search_id` |

> ⚠️ **三个凭据必须整组回传**。漏掉任何一个，站点都可能重新返回第 1 页——白花一次额度。
> `offset` 首页是**数字 0**（不是空串，也不是页码）。

**四道安全阀**，任一命中即**立即停止翻页**：

| 安全阀 | 触发条件 | 原因 |
| ------ | -------- | ---- |
| ① 空页 | 本页一条视频都没返回 | 无内容可翻 |
| ② `has_more=false` | 响应里显式标记没有下一页 | 服务端已明确告知到底 |
| ③ 无下一页凭据 | 三个凭据全为空/为 0，且 `has_more` 不是 `true` | 已是最后一页 |
| ④ 本页视频全部重复 | 本页记录全在已采集集合里 | 翻页未生效，再翻也是同一页 |

> ℹ️ **与主页列表技能的关键差异**：主页列表靠**单个游标**翻页，所以「游标不变」可以当作停止条件；
> 本接口有**页码参数**，服务端可能把凭据原样回显、靠递增的 `page` 给出下一页，
> 首页凭据本来就是空的。因此这里**只在「三个凭据全空」时**才判定没有下一页，
> 而不是「凭据没变就停」——后者会在第一页就把翻页误停掉。

> ⚠️ **页数上限 50**（`MAX_PAGES`）。`--pages` 超过 50 会被自动收敛，
> 避免误传一个巨大页数把账户额度一次刷光。

### 1.3 接口事实与实测状态（重要）

> ✅ **本技能已于 2026-10-09 完成首次真实调用**（关键词「WorkBuddy教程」，第 1 + 2 页共 34 条，
> 每页 1 次请求、零重试，两页 ID **零重叠**）。下表分三列：
> ✅ = 已实测确认（本技能真实调用，或同站点 `dy-uservideos` 复用口径）；
> 🔶 = 由**需求方文档**给出、脚本已按此实现但**尚未实测**；遇到不符请回填
> `references/api_reference.md` §7 并调整脚本。
>
> 对接要点：本接口与同站点的 `dy-uservideos`（抖音主页列表）**共用同一套字段命名**，
> 所以字段口径（时长毫秒、时间戳秒、容器键）**优先沿用**同站点实测结论。
> ⚠️ 但**封面口径与主页列表相反**，且**结果是图文/视频混合流**，见下表两行「⚠️」项。

| 要点 | 事实 | 脚本应对 |
| ---- | ---- | -------- |
| 接口动作名 | ✅ 实测 `dr=dy-search-v5`，未触发 `action_forbidden` | `DR_SEARCH = "dy-search-v5"` |
| 请求方法 | ✅ 实测 POST + `Content-Type: application/json` | `http_post()` 固定 POST + JSON |
| 请求字段 | ✅ 实测 `keyword` / `backtrace` / `offset` / `page` / `search_id` / `publish_time` / `sort_type` 均被接受 | `build_search_payload()` **全部显式发送**，请求体自解释 |
| 返回字段（12 项） | ✅ 实测 12 项**全部返回**，且字段名与规格**完全一致**（顶层键：`code` / `tips` / `request_id` / `search_id` / `backtrace` / `status_code` / `offset` / `has_more` / `aweme_info`） | `FIELD_ALIASES` 逐项收录并按别名序取值；**输出顺序严格按下方 §1.3.1 的 12 项规范顺序** |
| **列表容器键** | ✅ 实测就是 **`aweme_info`**（顶层数组，本页 16 / 18 条） | `VIDEO_LIST_KEYS` 以 `aweme_info` 置首，其余候选 + 整树兜底保留 |
| 翻页凭据键名 | ✅ 实测**顶层直取**命中：`backtrace`（str，920–960 字符）/ `offset`（**int**，首页 `0`、逐页 +20）/ `search_id`（str，同一搜索会话内**保持不变**） | 三张候选键表（含 camelCase 变体），顶层直取优先、命中即返回 |
| `create_time` 量级 | ✅ 同站点实测是 **Unix 秒** | 按量级判断：> `1e12` 视为毫秒；另存 `create_time_ts`（秒） |
| `video_duration` 单位 | ✅ 同站点实测是**毫秒**（`87842` → `01:28`） | 原值照实输出，另给 `video_duration_ms` / `video_duration_text`，并标注 `video_duration_unit: "ms"` |
| **`video_cover` 有值**（⚠️ 与主页列表相反） | 主页列表实测每条都是 `video_cover: ""`；但**搜索接口实测每条都有封面 URL**（`*.douyinpic.com/...~noop.webp`） | 空串 → `null`，**不编造**；本接口展示时**不再普遍为 `-`** |
| `aweme_url` 站点直接返回 | ✅ 实测每条都带 `aweme_url`（`https://www.douyin.com/video/<aweme_id>`） | `video_url` **优先用站点返回的 `aweme_url`**，缺失才本地拼接 |
| **结果是图文 / 视频混合流**（⚠️ 重要） | 实测 34 条中 **9 条为图文笔记**：`share_url` 含 `/share/note/`、`video_duration = 0`、`video_play_addr` 实为 BGM 的 **`.mp3` 音频地址**（非视频）；且 `type` 字段全为 `'1'`，**无法据此区分** | 12 项字段照常返回（不丢数据、不影响 `ok`）；**脚本已自动输出 `video_type`（`视频` / `图文`）**，判定式 = `share_url` 含 `/share/note/` 或播放地址以 `.mp3` 结尾（实测 34/34 零误判），**勿把图文的 `video_play_addr` 当视频地址** |
| `offset` 的传递类型 | ✅ 实测服务端返回 **int**（`20`），脚本统一字符串化输出（`"20"`）并原样回传 `--offset "20"`，**服务端接受、第 2 页翻页正确** | 保持字符串化，无需改动 |
| `collect_count` | ✅ 同站点实测确实返回，不存在「抖音无收藏数」问题 | 缺失才为 `null` |
| `has_more` 类型 | ✅ 实测是**整数 `1` / `0`**（本页 `1`） | `pick_has_more()` 兼容 布尔 / 数字 / `"true"/"1"/"yes"` 与 `"false"/"0"/"no"/""` |
| 封面可能是对象数组 | 同站点媒体字段惯用 `{"url_list": [...]}` 形态 | `normalize_media()` 递归提取 `url_list` / `url` / `play_url` 等键，取首个 URL |
| **字段为空属正常** | 无描述的作品 `desc` 为空、`collect_count` 可能不返回 | **不做告警、不影响 `ok` 判定**；缺失字段统一为 `null`（不编造 `0`） |
| 响应体可能夹带 PHP 告警 | ✅ 实测确认：JSON 之后追加 840 字符 `<br /><b>Warning</b>: Cannot modify header information - headers already sent by (output started at C:\wwwroot\u.ai-gc.art\mcp\rd.php:137) …` | `_loads_tolerant()` 用 `json.JSONDecoder().raw_decode` 从最靠前的 `{` 或 `[` 起解析，尾部告警自动忽略 |
| 失败时也可能是 HTTP 200 | 成败看 body 里的 `code`/`tips` | 必须解析响应体，不能只看 HTTP 状态码 |
| 单页条数可能不固定 | ✅ 本接口实测第 1 页 **16** 条、第 2 页 **18** 条 | 不用「固定页大小 × 页数」预估额度或判断末页，一律以响应实际条数为准 |
| 跨页重复 | 相邻页偶有重叠 | 按 `aweme_id` **跨页去重**，重复条数记入 `video_duplicates_removed` |

#### 1.3.1 12 项规范返回字段（口径基准，2026-10-16 对齐）

需求方给定的 12 项返回字段，**顺序即输出顺序**。脚本用常量 `CANONICAL_FIELDS` 固化这份顺序，
`build_video()` 保证这 12 项**排在最前**，派生字段一律在其后（导表 / 转 CSV / 与其它 kkAI
技能对齐时列序天然一致）。

| # | 中文名 | 字段名 | 取值口径 |
| - | ------ | ------ | -------- |
| 1 | 视频ID | `aweme_id` | 纯数字串；缺失为 `null` |
| 2 | 视频封面 | `video_cover` | 本接口**实测每条都有值**（与主页列表相反）；空串 → `null`，不编造 |
| 3 | 视频描述 | `desc` | 去首尾空白；空则 `null` |
| 4 | 发布时间 | `create_time` | 按 **UTC+8** 格式化为 `YYYY-MM-DD HH:MM:SS`；原始秒级时间戳另存 `create_time_ts` |
| 5 | 用户昵称 | `nickname` | 空则 `null` |
| 6 | 视频时长 | `video_duration` | **毫秒原值**；可读值与单位另见 `video_duration_text` / `video_duration_unit`；**图文恒为 `0`** |
| 7 | 点赞数 | `digg_count` | 支持 `1.2万` / `5.6w` / `3k` / `1,234` 归一为整数；缺失 `null`（不编造 `0`） |
| 8 | 评论数 | `comment_count` | 同上 |
| 9 | 收藏数 | `collect_count` | 同上 |
| 10 | 分享数 | `share_count` | 同上 |
| 11 | 视频文件地址 | `video_play_addr` | 直链；⚠️ **图文条目这里是 BGM 的 `.mp3`，不是视频文件** |
| 12 | 视频分享链接 | `share_url` | **站点返回**的分享链接（视频含 `/share/video/`、图文含 `/share/note/`）；未返回则 `null` |

> 由脚本派生、**不属于这 12 项**的字段（排在 12 项之后）：
> `create_time_ts` / `video_duration_ms` / `video_duration_text` / `video_duration_unit` /
> `video_url`（兼容别名）/ `video_type`（`视频` 或 `图文`）/ `page` / `index`。
> 👉 **要「干净 12 列」时，只取上表 12 项即可**（顺序已是规范顺序）。

### 1.4 默认只采 1 页 + 采完询问是否继续（交互约定，改动前必读）

> 🔴 **硬规则：用户没有说明采集几页时，一律只采 1 页**（`DEFAULT_PAGES = 1`）。
> **不许**因为"搜索结果看起来很多"、"用户大概想要全部"之类的猜测就自行加页数。
> 每翻一页都要花额度，所以标准姿势是：
> **先取第一页给用户看，再由助手询问用户是否继续，用户确认后才续采。**

这条规则在代码里有**四处落点**，缺一不可：

| 落点 | 做法 |
| ---- | ---- |
| CLI 默认值 | `--pages` 的 `default=None`（**不是** `DEFAULT_PAGES`）——这样才能区分「用户没说」与「用户明说了 1 页」 |
| 函数签名 | `collect_keyword(..., pages=None, ...)`，签名默认值同样是 `None`（**不是** `DEFAULT_PAGES`）；CLI 与程序化调用两条入口语义完全一致 |
| 收敛函数 | `clamp_pages(None)` → `DEFAULT_PAGES`；页数下限 1、上限 50 |
| 来源标识 | 输出 `pages_source`：`default`（未说明，走的默认）/ `explicit`（用户明确指定）；未说明时还会在顶层 `warnings` 里写一条「未指定采集页数，已按默认只采 1 页」的自检提示 |

> 💡 **为什么 `default` 不能用 `DEFAULT_PAGES` 当 argparse 默认值**：那样传 `--pages 1` 与不传
> 会得到完全一样的内部状态，脚本就无法告诉调用方「这是默认值、采完记得问用户」，
> 也就可能被静默地当成"用户要求就采 1 页"而**跳过追问**。
>
> ⚠️ **同一个坑会在另一个入口重现**：只改 argparse 而不改函数签名，程序化调用
> （`collect_keyword(...)`）不传 `pages` 时仍会拿到 `DEFAULT_PAGES`，
> 于是被误判成 `explicit`。**两条入口都要用 `None` 表示「未说明」。**

分工必须清楚：

| 角色 | 负责什么 |
| ---- | -------- |
| 脚本 | **只负责采集与判断"还有没有更多"**，把询问所需信息结构化放进 `next_action`；用 `pages_source` 告诉调用方"这 1 页是默认值" |
| 助手（调用方） | **负责真正发起询问**：渲染完结果后，问用户「是否继续采更多页」，得到答复再决定要不要续采 |

> ⚠️ **脚本不做交互式提问，也绝不要给它加 `input()`**。两个原因：
> ① stdout 必须保持纯 JSON；② 一旦阻塞等待 stdin，Agent 的工具调用会直接挂住。

**`next_action` 的出现条件**（必须同时满足，否则为 `null`，表示**无需询问**）：

1. 本次采集成功且取到了视频（`videos` 非空）——失败了不该问"要不要继续"；
2. 未到末页（`exhausted=false`）；
3. 至少有一个下一页凭据（`next_backtrace` / `next_offset` / `next_search_id` 不全空）。

> 📌 `pages_source=default` 且 `next_action` 不为 `null` ⇒ **必须追问**，不能直接收尾。

字段含义：

| 字段 | 含义 |
| ---- | ---- |
| `ask_user` | 固定 `true`，表示"应该向用户提问" |
| `reason` | `has_more`（还有下一页）/ `fatal_error`（批量撞账户级错误） |
| `question` | 可直接念给用户的问题，已带页数与条数。**问话会随来源变体**：`pages_source=default` 时开头是「你这次没有指定采集页数，我先只采了最近 N 页…」，把"只采 1 页是默认行为"讲明白；`explicit` 时是「已采集 N 页…」 |
| `pages_source` / `pages_fetched` | 本次页数的来源（`default` / `explicit`）与实际取回页数，供调用方核对 |
| `suggested_pages` | 建议续采页数（固定 1，逐次确认，避免一次刷光额度） |
| `resume_page` | 续采要用的页码（= 下一页页码） |
| `resume_backtrace` / `resume_offset` / `resume_search_id` | 续采要用的三个凭据（= 上一页返回的值） |
| `suggested_command` | **可直接执行**的续采命令（已带全部凭据，不会重复第 1 页） |
| `cost_hint` / `stop_hint` | 给助手看的额度说明与"用户说不用就收工"提示 |

**续采必须带 `--page` + 三个凭据，不要重跑整条命令。** 重跑会重新请求第 1 页，白花 1 次额度：

```bash
# ❌ 浪费：重新从第 1 页开始（每页都要重来）
python scripts/dy_search_collect.py --keyword "WorkBuddy教程" --pages 1

# ✅ 正确：用 next_action.suggested_command 直接续采（1 次/页）
python scripts/dy_search_collect.py --keyword "WorkBuddy教程" --page 2 \
    --backtrace "<上页返回>" --offset "<上页返回>" --search-id "<上页返回>" --pages 1
```

**用户说"不用了/够了"时：直接结束当前任务，不要再发任何请求。**
用户明确要求一次多采（如"帮我采 5 页"）时，按用户说的页数一次传入 `--pages 5` 即可。

### 1.5 「页码」与「页数」的区分（最易填反）

CLI 上两个参数只差一个字母，**填反只白花额度、不报错**：

| 参数 / 字段 | 含义 |
| ----------- | ---- |
| `--pages N` | **采集页数**（本次要采几页），默认 1（不传 = 只采 1 页） |
| `--page N` | **起始页码**（从第几页开始），默认 1 |
| `next_page` | 下一页页码，由脚本按「起始页码 + 已取回页数」算出 |

组合示例：`--page 3 --pages 2` = 采**第 3、4 页**。

输出里 `pages_requested`（期望页数）/ `pages_fetched`（实际取回页数）/ `start_page`（起始页码）/
`end_page`（实际取到的最后一个页码）四者并列，每条记录带自己所在的 `page`。

**本地自检告警**（纯本地、零额度，只写 `warnings`，**绝不改变实际请求**）：

1. `--page N`(N>1) 却没带任何翻页凭据 ⇒ 告警：接口约定第 N 页须带第 N-1 页的凭据，
   多半取不回那一页；
2. `--page` 超过常规上限（50）⇒ 告警：多半是把页数误填进 `--page`；
3. `--page N`(N>1) 且**同时搜索多个关键词** ⇒ 告警：凭据只对应上一页所属的**那一个**关键词，
   套用其它关键词会取到与该词无关的结果。

## 2. 功能特性

- 🔍 **关键词直搜** — 传入关键词即可拉取该关键词下的视频搜索结果
- 📄 **默认只采 1 页（硬规则）** — 不传 `--pages` 就只取第一页，不擅自多花额度；需要更多页时由用户明确要求并显式传 `--pages N`（上限 50）；结果里的 `pages_source` 会标明这 1 页是「默认值」还是「用户指定」
- 🙋 **采完询问是否继续** — 未到末页时结果里会给出 `next_action`（问题文案 + 可直接执行的续采命令），由助手问用户「是否继续采更多页」
- 🎛 **筛选与排序** — 发布时间（`_0` 不限 / `_1` 一天内 / `_7` 一周内 / `_180` 半年内）、排序（`_0` 综合 / `_1` 最多点赞 / `_2` 最新发布），支持中英文写法自动归一
- 🔁 **三凭据续采** — 用 `--page` + `--backtrace` + `--offset` + `--search-id` 整组续采，**每页只花 1 次额度**
- 🛡 **四道翻页安全阀** — 空页 / `has_more=false` / 凭据全空 / 本页全重复，任一命中立即停止
- 🧩 **容器键自适应** — 响应结构变化无需改代码，自动挑出最像视频列表的数组（同站点实测键 `aweme_info` 已在首位，其余候选与兜底保留）
- 🎯 **凭据防误取** — 深度查找凭据时跳过视频实体，避免把记录字段当成翻页凭据
- 1️⃣ **失败才重试一次** — 每页先请求 1 次，**只有返回失败时才补 1 次重试**，最多补一次；成功不重试、不轮询
- 🚫 **不可重试错误不浪费额度** — apikey 失效、余额不足、上游限流、动作名被网关拒绝这四类"重发也不会变"的错误直接返回
- ⏳ **0-600 秒耐心等待** — 默认等待上限 600 秒（`--timeout` 可调，`0` 为不设超时），等待期间每 15 秒打印心跳
- 🧾 **跨页去重** — 按 `aweme_id` 去重，重复条数透明记录在 `video_duplicates_removed`
- 🕐 **时间戳自动转换** — `create_time` 按量级判秒/毫秒并按 UTC+8 转可读时间，同时保留 `create_time_ts`
- 📊 **互动数据标准化** — 兼容 `1.2万` / `5.6w` / `1,234` 等写法并统一转为整数
- ⏱ **时长可读** — 额外输出 `video_duration_text`（`00:15` / `1:02:05`）与单位标注
- 📦 **批量关键词** — 支持一次传入多个关键词，或从文件读取（一行一个，`#` 开头为注释）
- 🔐 **apikey 不落脚本** — 密钥只从环境变量或本机密钥文件读取，绝不硬编码
- 🧯 **错误可诊断** — 区分「apikey 失效」「余额不足」「上游限流」「动作被拒」「等待超时」，分别给出正确的处理指令
- 🖥 **emoji 安全输出** — stdout 做编码防护，视频描述里的 emoji 不会把成功采集崩成失败

## 3. 鉴权（必读）

### 3.1 获取 API Key

请用户登录 **https://u.ai-gc.art/** 获取 apikey。

### 3.2 配置 API Key

**apikey 是密钥，不保存在脚本中。** 三种配置方式，优先级从高到低：

| 优先级 | 方式 | 说明 |
| ------ | ---- | ---- |
| 1 | `--apikey` 参数 | 临时使用，会进入终端历史，仅调试用 |
| 2 | 环境变量 `AI_GC_ART_API_KEY` | 适合 CI / 常驻环境 |
| 3 | 本机密钥文件 `~/.workbuddy/ai-gc.art_apikey.txt` | **推荐**，用 `--set-apikey` 写入 |

> **密钥按「站点」存放，不按技能存放**：文件名取站点名 `ai-gc.art`，因为 `u.ai-gc.art`
> 站点下的所有接口（同站点的小红书系列、抖音主页列表、本搜索接口）共用同一份 apikey。
> **若本机已配置过该站点的其它技能，无需重复配置，直接复用即可。**
> 兼容性：旧文件名 `~/.workbuddy/ai-gc.art_apikey`（无扩展名版）、
> `~/.workbuddy/xhs_apikey.txt`（按技能命名版）仍可读取，首次读到时脚本会**自动迁移**到新路径。
> 环境变量同理：`AI_GC_ART_API_KEY` / `AI_GC_ART_KEY` 优先，`DY_API_KEY` / `DOUYIN_API_KEY`
> 以及同站点小红书技能的 `XHS_API_KEY` / `XHS_APIKEY` / `XHS_KEY` 也作为兼容别名读取。

推荐做法（写入本机密钥文件，一次配置长期有效）：

```bash
python scripts/dy_search_collect.py --set-apikey <用户提供的apikey>
```

校验配置是否生效（不发起采集请求）：

```bash
python scripts/dy_search_collect.py --check-key
```

### 3.3 缺少 apikey 时的处理

当 `--check-key` 返回 `apikey_configured: false`，**必须先向用户索要 apikey**，并按以下话术引导：

```
需要抖音数据采集服务的 apikey 才能继续。
请登录 https://u.ai-gc.art/ 获取 apikey 后发给我，我会保存到本机密钥文件（不会写进脚本）。
```

拿到用户提供的 apikey 后，执行 `--set-apikey` 保存，再继续采集。**禁止**自行编造、猜测或复用其他服务的密钥。

## 4. 使用指南

### 4.1 四步标准流程

**Step 1 — 确认 apikey 已配置**

```bash
python scripts/dy_search_collect.py --check-key
```

若未配置，按 §3.3 向用户索要后 `--set-apikey` 保存。

**Step 2 — 采集搜索结果（默认只采 1 页）**

> 🔴 **用户没有说明采集几页时，不要给它传 `--pages`，也不要在心里替它决定页数**——
> 直接跑下面的默认命令，只采 1 页（`pages` 会是 1、`pages_source` 会是 `default`），
> 采完再按 Step 4 问用户是否继续。

```bash
# 默认采集：只采 1 页（推荐，先取第一页给用户看）
python scripts/dy_search_collect.py --keyword "WorkBuddy教程"

# 用户明确要多页时才传 --pages
python scripts/dy_search_collect.py --keyword "WorkBuddy教程" --pages 2

# 带筛选与排序
python scripts/dy_search_collect.py --keyword "WorkBuddy教程" \
    --publish-time 一周内 --sort-type 最多点赞 --pages 2

# 续采下一页：用上次结果里的 next_action（见 §1.4，别再重跑整条命令）
python scripts/dy_search_collect.py --keyword "WorkBuddy教程" --page 2 \
    --backtrace "<上页返回>" --offset "<上页返回>" --search-id "<上页返回>" --pages 1

# 自定义等待上限（0-600 秒，默认 600）
python scripts/dy_search_collect.py --keyword "WorkBuddy教程" --pages 2 --timeout 300

# 关闭重试（失败也不补发，只请求一轮）
python scripts/dy_search_collect.py --keyword "WorkBuddy教程" --pages 2 --retry 0

# 批量：多个关键词
python scripts/dy_search_collect.py --keyword "WorkBuddy教程|扣子工作流" --pages 2

# 批量：从文件读取（每行一个关键词，# 开头为注释）
python scripts/dy_search_collect.py --file keywords.txt --pages 2

# 导出 JSON 到文件
python scripts/dy_search_collect.py --keyword "WorkBuddy教程" --pages 2 --output videos.json
```

> ⏳ **执行时请留足等待时间**：接口响应可能需要数十秒到 600 秒。采集页数越多、总耗时越长，
> 命令会一直阻塞等待，这是正常现象。等待期间 stderr 会出现 `[等待中] …` 心跳；
> **不要**因为长时间无输出就中断重跑，那会重复消耗额度。

> 💾 **真实采集请一律加 `--output <文件>.json` 落盘，渲染时从文件读**（同族技能实测教训）。
> 单页 20 条视频的 stdout 可达 **80KB+**，直接读 stdout 会**在工具回显层被中间截断**
> （头尾可见、中段丢失），照它渲染就会**缺条**，只能重跑一遍、白花一次额度。
> 落盘后既保证不丢数据，又留一份可复用的原始结果。为省体积可再叠加 `--compact`。

**Step 3 — 按 §4.3 模板渲染结果给用户**

**Step 4 — 若 `next_action` 不为 `null`，询问用户是否继续采更多页（强制）**

采集完**必须**检查结果里的 `next_action`：

- `next_action` 为 `null` → 已到末页 / 没取到内容 / 采集失败，**不要问**，正常收尾即可；
- `next_action` 不为 `null` → **先渲染本页结果，再向用户提问**。默认档（用户没指定页数）的问话形如：

  > 📄 你这次没有指定采集页数，我先只采了最近 1 页，共 20 条视频；关键词「WorkBuddy教程」还有更多内容。是否继续采集更多页？

  用户明确指定过页数时，问话则是：

  > 📄 已采集 1 页，共 20 条视频，关键词「WorkBuddy教程」还有更多内容。是否继续采集更多页？

  （两句都由 `next_action.question` 直接给出，**照念即可，不用自己造句**）

> 🔴 **当 `pages_source == "default"`（用户本来就没说明采几页）而 `next_action` 不为 `null` 时，
> 这一次追问是强制的、不可省略** —— 默认 1 页只是个不带假设的起点，绝不等于"用户只想要 1 页"，
> 也绝不等于"助手可以自己决定继续采"。必须让用户拍板。

  然后**停下等用户答复**：

  | 用户答复 | 助手动作 |
  | -------- | -------- |
  | 继续 | 直接执行 `next_action.suggested_command`（已带 `--page` + 全部凭据），回到 Step 3 渲染新一页，再次检查 `next_action` |
  | 继续，但要多几页 | 把命令里的 `--pages 1` 改成用户要的页数（上限 50），其余不变 |
  | 不用了 / 够了 | **立即结束任务，不再发任何请求** |

> ⚠️ **不要替用户做"继续采"的决定，也不要一次性把很多页刷完。**
> 多关键词批量采集时，逐个关键词都要按上述方式询问一次；用户若在一开始就说了要采几页，
> 则按用户说的页数一次采完，不必再逐页询问。

### 4.2 命令速查表

| 场景 | 命令 |
| ---- | ---- |
| 保存 apikey | `python scripts/dy_search_collect.py --set-apikey <key>` |
| 检查 apikey | `python scripts/dy_search_collect.py --check-key` |
| **搜索关键词（默认 1 页）** | `python scripts/dy_search_collect.py --keyword "WorkBuddy教程"` |
| 采集 2 页 | `python scripts/dy_search_collect.py --keyword "kw" --pages 2` |
| 带筛选排序 | `python scripts/dy_search_collect.py --keyword "kw" --publish-time 一周内 --sort-type 最多点赞` |
| **续采下一页** | `python scripts/dy_search_collect.py --keyword "kw" --page 2 --backtrace "<上页>" --offset "<上页>" --search-id "<上页>" --pages 1` |
| 从第 3 页起采 2 页 | `python scripts/dy_search_collect.py --keyword "kw" --page 3 --pages 2 --backtrace "<上页>" --offset "<上页>" --search-id "<上页>"` |
| 自定义等待上限 | `python scripts/dy_search_collect.py --keyword "kw" --pages 2 --timeout 300` |
| 不设超时（一直等） | `python scripts/dy_search_collect.py --keyword "kw" --pages 2 --timeout 0` |
| 关闭失败重试 | `python scripts/dy_search_collect.py --keyword "kw" --pages 2 --retry 0` |
| 批量关键词 | `python scripts/dy_search_collect.py --file keywords.txt --pages 2` |
| 导出 JSON | `python scripts/dy_search_collect.py --keyword "kw" --pages 2 --output out.json` |
| 排查失败原因 / 回填结构 | `python scripts/dy_search_collect.py --keyword "kw" --pages 2 --raw --human` |

### 4.3 结果展示模板（强制）

stdout 为标准 JSON，**面向用户时必须渲染成结构化卡片，不要直接贴 JSON**。

概览 + 视频列表：

```
🎬 抖音关键词搜索视频列表

🔍 关键词：{keyword}（发布时间：{publish_time_label} ｜ 排序：{sort_type_label}）
📄 采集 {pages_requested} 页，实际取回 {pages_fetched} 页，共 {video_count} 条视频
```

末页 / 续采提示，按下面三者择一追加一行：

| 条件 | 追加内容 |
| ---- | -------- |
| `exhausted` 为 `true` | `✅ 已到末页` |
| `next_action` 不为 `null` | `➡️ 还有更多内容，已为你准备好续采命令（是否继续由用户决定）` |
| 既未到末页、也没有 `next_action` | 不加此行 |

**`next_action` 不为 `null` 时，渲染完视频后必须按 §4.1 Step 4 向用户提问**，
直接念 `next_action.question` 即可（提问等用户答复，不要自己往下采）：

```
➡️ 你这次没有指定采集页数，我先只采了最近 1 页，共 20 条视频；关键词「WorkBuddy教程」还有更多内容。是否继续采集更多页？
   （继续的话我会用 --page + backtrace/offset/search_id 接着采，每页消耗 1 次额度；说"不用了"就到此为止）
```

随后逐条渲染视频，**严格按 §1.3.1 的 12 项规范顺序、同名中文标签**（便于横向对比与转表）：

```
{n}.
    🆔 视频ID：{aweme_id}
    🖼 视频封面：{video_cover}
    📝 视频描述：{desc}
    🕒 发布时间：{create_time}
    👤 用户昵称：{nickname}
    ⏱ 视频时长：{video_duration_text}（{video_duration} ms）
    ❤️ 点赞数：{digg_count}
    💬 评论数：{comment_count}
    ⭐ 收藏数：{collect_count}
    🔁 分享数：{share_count}
    🎬 视频文件地址：{video_play_addr}
    🔗 视频分享链接：{share_url}
```

- 字段为 `null` 时显示 `-`，不要显示 `None` / `null`。
- **封面一般有值**：本接口实测每条都返回封面 URL（⚠️ 与主页列表相反，后者实测为空串）；
  仅当真缺失时才显示 `-`（脚本记 `null`，不编造）。
- **图文条目**：脚本已输出 `video_type`（`视频` / `图文`，实测 34/34 零误判）。
  取到 `图文` 时**在时长后追加标注**，并提醒「视频文件地址实为 BGM 音频」：
  `⏱ 视频时长：图文（无时长）` + `⚠️ 视频文件地址是 BGM 的 mp3，不是视频文件`。
  切勿显示成 `00:00`，也勿让用户拿这个 mp3 当视频地址去下载（详见 §1.3 对应行）。
- 列表较长（> 10 条）时，先给一行汇总表（序号 / 描述 / 点赞 / 评论 / 分享 / 时长），再按需展开明细。
- 批量搜索多个关键词时，先用一行汇总（`共 X 个关键词，成功 Y 个，失败 Z 个`），再逐关键词渲染。
- `video_duration_text` 按毫秒换算（同站点实测口径 `87842` → `01:28`），可直接展示；
  原始值仍在 `video_duration`（毫秒）。
- **实测状态**：本技能已于 2026-10-09 完成首次真实调用，容器键（`aweme_info`）、三凭据字段名、
  单页条数等已回填至 `references/api_reference.md` §7，本文 §1.3 的 🔶 标记已同步为 ✅。
  后续若接口结构变更，请按同法回填。

### 4.4 输出 JSON 结构

单关键词采集时，顶层会直接合并该关键词的结果字段（下图是**默认只采 1 页**、且还有更多内容的典型返回）：

```json
{
  "ok": true,
  "total_keywords": 1,
  "succeeded": 1,
  "failed": 0,
  "total_videos": 20,
  "apikey_source": "密钥文件 C:\\Users\\...\\.workbuddy\\ai-gc.art_apikey.txt",
  "timeout_seconds": 600,
  "retry": 1,
  "pages": 1,
  "pages_source": "default",
  "start_page": 1,
  "end_page": 1,
  "filters": { "publish_time": "_0", "sort_type": "_0" },
  "max_requests_per_page": 2,
  "max_requests_per_keyword": 2,
  "duplicates_removed": 0,
  "warnings": ["未指定采集页数，已按默认只采 1 页（DEFAULT_PAGES=1）：用户没有说明采集几页时不擅自多采；采完若还有更多内容，结果里的 next_action 会提示是否续采。"],
  "aborted": false,
  "skipped_count": 0,
  "skipped_keywords": [],
  "total_requests": 1,
  "total_retries": 0,

  "keyword": "WorkBuddy教程",
  "videos": [ … 见下 … ],
  "video_count": 20,
  "pages_requested": 1,
  "pages_fetched": 1,
  "has_more": 1,
  "next_page": 2,
  "next_backtrace": "bt_xxx",
  "next_offset": "20",
  "next_search_id": "sid_xxx",
  "exhausted": false,
  "total_count": null,
  "video_duplicates_removed": 0,
  "request_count": 1,
  "retry_count": 0,
  "errors": [],
  "next_action": {
    "ask_user": true,
    "reason": "has_more",
    "question": "你这次没有指定采集页数，我先只采了最近 1 页，共 20 条视频；关键词「WorkBuddy教程」还有更多内容。是否继续采集更多页？",
    "keyword": "WorkBuddy教程",
    "total_count": null,
    "pages_source": "default",
    "pages_fetched": 1,
    "suggested_pages": 1,
    "resume_page": 2,
    "resume_search_id": "sid_xxx",
    "resume_backtrace": "bt_xxx",
    "resume_offset": "20",
    "suggested_command": "python scripts/dy_search_collect.py --keyword \"WorkBuddy教程\" --page 2 --search-id \"sid_xxx\" --backtrace \"bt_xxx\" --offset \"20\" --publish-time \"_0\" --sort-type \"_0\" --pages 1",
    "cost_hint": "续采用 --page + backtrace/offset/search_id 直接翻下一页，不再重复请求第 1 页；每页消耗 1 次额度，仅当该页失败才会多补 1 次。",
    "stop_hint": "用户表示不需要时，直接结束当前任务，不要再发任何请求。"
  },

  "videos": [
    {
      "aweme_id": "7681785244026015018",
      "video_cover": null,
      "desc": "0基础，带你做出你人生第一个AI视频！",
      "create_time": "2026-09-24 18:07:01",
      "nickname": "Ksr桑",
      "video_duration": 87842,
      "digg_count": 118659,
      "comment_count": 10217,
      "collect_count": 93086,
      "share_count": 19596,
      "video_play_addr": "https://.../video.mp4",
      "share_url": "https://www.douyin.com/video/7681785244026015018",

      "create_time_ts": 1790244421,
      "video_duration_ms": 87842,
      "video_duration_text": "01:28",
      "video_duration_unit": "ms",
      "video_url": "https://www.douyin.com/video/7681785244026015018",
      "video_type": "视频",
      "page": 1,
      "index": 1
    }
  ],

  "results": [ { "…与上面合并到顶层的字段一致…" } ]
}
```

多关键词采集时**不做顶层合并**（`videos` 只存在于 `results[i].videos`），顶层只给汇总信息。

字段说明：

| 字段 | 含义 |
| ---- | ---- |
| `videos[]` | 该关键词下的视频列表（已跨页去重，保持接口返回顺序） |
| `videos[]` 的前 12 个键 | **§1.3.1 的 12 项规范字段，顺序固定**（`aweme_id` → `share_url`），要「干净 12 列」就取前 12 个键 |
| `videos[].page` | 该视频来自第几页 |
| `videos[].index` | 在 `videos` 中的序号（从 1 开始） |
| `videos[].video_type` | **作品类型**：`视频` / `图文`。图文判定式 = `share_url` 含 `/share/note/` 或播放地址以 `.mp3` 结尾（实测 34/34 零误判）；信息不足为 `null` |
| `videos[].video_duration_unit` | 时长单位口径（同站点实测为 `ms`） |
| `videos[].video_url` | 兼容别名：规范网页链接（优先站点 `aweme_url`，缺失才本地拼接）；与 `share_url` 常同值 |
| `videos[].share_url` | **站点返回**的分享链接；站点未返回则为 `null`（不编造） |
| `keyword` | 本次搜索的关键词 |
| `pages_requested` / `pages_fetched` | 期望采集页数 / 实际取回页数（命中安全阀时会小于期望） |
| `pages` / `pages_source` | **顶层**：本次采集页数 / 其来源。`default` = **用户未说明，已按默认只采 1 页**（采完必须追问是否继续）；`explicit` = 用户明确指定。详见 §1.4 |
| `start_page` / `end_page` / `next_page` | 起始页码 / 实际取到的最后一个页码 / 下一页页码 |
| `filters` | 本次生效的筛选取值（`publish_time` / `sort_type`，均为站点编码） |
| `exhausted` | 是否已确认到达末页（`true` 表示提前停止不是异常） |
| `next_backtrace` / `next_offset` / `next_search_id` | 下一页的三个翻页凭据；`null` 表示该凭据未返回 |
| `next_action` | **「是否继续采更多页」的询问信息**；已到末页 / 无凭据 / 空结果 / 失败时为 `null`（表示**无需询问**）。详见 §1.4 |
| `has_more` | 接口的「还有下一页」标记；接口未返回该字段时为 `null` |
| `total_count` | 站点可能返回的「该关键词总条数」；未返回时为 `null` |
| `duplicates_removed` | **顶层**：输入关键词去重被丢弃的条数 |
| `video_duplicates_removed` | **记录级**：视频跨页去重被丢弃的条数（与上者语义不同，故字段名分开） |
| `request_count` | 该关键词实际发出的请求次数 |
| `retry_count` | 该关键词实际发生的重试次数 |
| `max_requests_per_page` / `max_requests_per_keyword` | 每页上限 `1 + retry` / 每关键词上限 `pages × (1 + retry)`，用于核对「没有多余请求」 |
| `raw_responses` | `--raw` 时留档的每页完整原始响应（单页上限 20 万字符） |
| `warnings` | 顶层提示（含批量级注意事项与「未指定页数」自检） |
| `aborted` / `skipped_keywords` | 批量撞上账户级错误时是否中止、剩余未采关键词 |

## 5. 错误处理与退出码

| 退出码 | 含义 | 处理方式 |
| ------ | ---- | -------- |
| 0 | 全部成功 | 正常渲染 |
| 1 | 部分或全部采集失败 | 读取 `results[].errors[]`，按 `error` 提示用户 |
| 2 | 参数错误（未传关键词 / 文件不存在） | 向用户确认关键词是否填写 |
| 3 | 缺少 apikey | 按 §3.3 向用户索要 |

**鉴权类失败**（`error_code: "unauthorized"`，如 `访问被拒绝: 无效的apikey，请登录 u.ai-gc.art 获取`）：

- 明确告知用户 apikey 无效或已过期，请重新登录 https://u.ai-gc.art/ 获取
- 拿到新 key 后重新 `--set-apikey` 覆盖旧值，再重试
- **不要**反复重试同一个失效的 key（脚本已识别为不可重试，不会自动补发）
- 若响应是「未携带密钥」（HTTP 401 `missing api key`），说明本机还没有密钥，按 §3.3 向用户索要

**动作被拒**（`error_code: "action_forbidden"`，表现为 HTTP 403 + 裸文本 `forbidden`）：

- 这是**站点网关不接受该接口动作名**（`dy-search-v5`），
  **与 apikey 无关**（同站点实测：有效密钥与无效密钥返回完全相同）
- **明确告诉用户不要重新获取 apikey**——那解决不了问题，只会白跑一趟
- 检查脚本内的动作名是否与站点实际开放的接口一致；若确认无误，
  说明该动作尚未对当前账号开放，需联系站点支持

**余额不足**（`error_code: "insufficient_balance"`，如 `余额不足，请登录 u.ai-gc.art ，请充值后重试`）：

- 告知用户**账户额度已耗尽，需去 https://u.ai-gc.art/ 充值**
- 明确区分：**apikey 本身是有效的，不要引导用户重新获取 key**
- 充值后可直接重试，无需重新配置

**上游临时故障 / 限流**（`error_code: "upstream_busy"`，如 `404,API 请求失败,请10分钟后，再重试`）：

- 明确告知用户：**这是上游接口临时不可用，不是关键词或筛选条件的问题、不是 apikey 问题**
- **不要改参数、不要重新获取 apikey、不要立刻重跑**——服务端要求等 10 分钟，立即重发必然同样失败
- 正确做法：**等约 10 分钟后原样重跑同一条命令**
- 若用户已有部分结果（多页采集中途失败），已取到的视频无需重做，可用三个凭据续采

**等待超时**（`error` 含「等待超时：已等待 N 秒仍未返回」）：

- 该错误属于**可重试**：脚本会自动补一次重试；若重试仍超时，把 `--timeout` 调大（上限 600 秒）
  后由用户确认再重新发起，`--timeout 0` 表示一直等待
- 向用户如实说明是"等待超时"而非"数据取不到"

**其他常见失败**：

- `接口返回成功但未取到视频列表，且没有翻页凭据` → 会被当作失败并重试一次；仍失败时加 `--raw --human`
  查看原始返回。常见原因是该关键词确实没有结果，或响应结构已变更（容器键不同）
- `接口调用成功，但该关键词没有取到任何视频`（warning，`ok:false`）→ 关键词确实无结果或筛选过窄，
  如实告知用户，**不要**判定为脚本故障
- `error_code: "missing_apikey"`（`ok:false`，退出码 3）→ 本机配置问题：先跑 `--check-key` 确认，
  再按 §3.3 索要 apikey 并用 `--set-apikey` 重新落盘
- 网络请求失败 → 脚本已自动重试一次；仍失败则提示检查网络后由用户确认再重试

> 💡 **额度提醒**：`dy-search-v5` 每次调用都消耗额度。
> **默认 1 页 = 1 次调用**；每多采 1 页多花 1 次；仅当某页失败时才会补 1 次重试。
> 结果里的 `request_count` / `retry_count` 可直接核对。
> 调试请用离线测试（见 §6），零消耗。
> **想省额度**：① 保持默认只采 1 页、采完问用户；② 续采用 `--page` + 三个凭据，
> **别重跑不带凭据的命令**，否则每次都白多花 1 次；③ 先用 `--publish-time` / `--sort-type` 缩小范围，
> 少翻页就能拿到想要的内容。
>
> ⚠️ **排查问题时先看额度**：账户余额耗尽后所有计费动作都会统一变成 `code:402 余额不足`，
> 此时换关键词、换筛选探测都是白费。先用 `--check-key` 确认密钥。

## 6. 项目架构

```
dy-search-collector-kkai/
├── SKILL.md                          # Skill 定义与使用文档（本文件）
├── _icon.png                         # 技能图标（kkAI logo，450×450）
├── scripts/
│   └── dy_search_collect.py          # 核心采集脚本（关键词搜索 + 三凭据翻页 + 字段归一化 + CLI）
├── references/
│   └── api_reference.md              # 接口明细、字段映射表、筛选编码、错误码、实测事实
└── tests/                            # ⚠️ 夹具直接放这一层，不再套 fixtures/ 子目录
    ├── test_dy_search_collect.py     # 离线回归测试（mock 响应 + 真实夹具回放，零额度）
    └── real_2026-10-09_page1.json    # 实测留档：真实第 1 页原始响应（含真实 PHP 告警尾巴）
```

> ⚠️ **打包红线：Skill 包只支持「根目录 / 二级目录 / 文件」两级结构。**
> 夹具不能放 `tests/fixtures/`（三级目录会被上传校验拒绝），一律直接放 `tests/` 下。

离线回归测试（修改脚本后建议运行，无需 apikey、不发起真实请求）：

```bash
python tests/test_dy_search_collect.py
```

覆盖 **559 项断言**，共 17 组：

- **字段归一化**：别名拼写、`万/w/亿/k` 转整数、时长毫秒换算与单位标注、封面对象数组、
  秒级/毫秒级时间戳、空串封面 → `null`、缺失字段一律 `null`（不编造 `0`）、
  `aweme_url` 优先拼 `video_url`、空壳记录判定为无效
- **请求次数**：默认 1 页 = 1 次；3 页 = 3 次；失败后重试成功 +1；两步均失败时断言
  **绝不出现第 3 次尝试**；`retry=0` 只发一轮；首页 `offset` 必须是数字 `0`
- **不可重试错误**：`unauthorized` / `insufficient_balance` / `upstream_busy` / `action_forbidden`
  均 `retry_count == 0` 且带 `action_required`；反向验证普通业务失败**仍会重试一次**
- **错误分类型不串味**：`403 + 裸 forbidden` → `action_forbidden`；反向验证
  `200 + JSON code:403` 与 `401 + missing api key` **仍归** `unauthorized`
- **业务正文不污染错误判定（真实事故回归）**：视频描述里塞「1分钟」「余额不足」「apikey 无效」
  「稍后再试」，**都不允许**把成功响应判成任何错误；同时反向断言真正的限流文案仍被识别；
  并直接断言 `_error_blob` 只含提示字段
- **PHP 告警容错**：对象形态与**顶层数组**形态都能解析（`raw_decode`，不是截花括号）
- **分页安全阀**：四道安全阀各自触发的请求次数；三凭据在页间**整组**传递；首页凭据为空；
  跨页去重计数；末页即便带凭据也**不追问**
- **默认只采 1 页（硬规则）**：① 不传 `pages` ⇒ 只 1 页 1 次请求、`pages_source=default`、
  给出 `next_action` 且问话点明「没有指定采集页数」；② `pages=None` 同义；③ 已到末页不误问；
  ④ 明确页数 ⇒ `explicit`；⑤ `clamp_pages` 边界（`None`→1、`0`→1、`999`→50）
- **`next_action` 边界**：还有更多 / 无凭据 / 空结果 / 失败四种情形的出现与不出现；
  续采命令带 `--page` 与三个凭据；脚本内**没有 `input()`**
- **批量与平铺**：撞账户级错误 → `build_batch_next_action` 给出 `fatal_error` 询问；
  无 fatal 错误或无剩余关键词时不给
- **关键词解析**：竖线/分号/换行分隔；**空格与逗号不拆**；去首尾空白
- **筛选归一化**：`publish_time`（`_0`/`_1`/`_7`/`_180`）与 `sort_type`（`_0`/`_1`/`_2`）
  中英文别名映射、编码原样透传、未知写法原样透传、展示名
- **页码与页数区分**：`clamp_start_page`、页码超常规上限告警、从第 N 页起采无凭据告警、
  `--page 3 --pages 2` 请求第 3、4 页
- **CLI 端到端**：退出码 0/1/2/3、stdout 纯 JSON、`--human` 走 stderr、`--output` 落盘、
  `--check-key` 零请求且密钥打码、多关键词 + 凭据顶层告警、批量 fatal 中止
- **静态安全**：无 `input()` / `subprocess` / `eval` / `exec` / `base64` / `os.system`；
  只有一处 `urlopen` 且 URL 由 `API_ENDPOINT` 拼装
- **续采闭环**：用 `next_action` 字段续采断言**不重复第 1 页**且带上一页凭据；
  完整走一遍「未指定页数 → 1 页 → 逐轮追问 → 末页才停」（3 轮 3 次请求，
  页码 1→2→3，`backtrace` 空→bt1→bt2，`offset` 0→20→40，前两轮追问、末页不追问）
- **规范 12 项字段 + 真实响应夹具回放（2026-10-16）**：
  ① 断言 `CANONICAL_FIELDS` 的**顺序就是需求方给的 12 项顺序**、中文名一一对应；
  ② 断言 `build_video()` 输出的**前 12 个键就是这 12 项**、派生字段全在其后；
  ③ `detect_video_type` 三分支（`/share/note/` ⇒ 图文、`.mp3` ⇒ 图文、正常 ⇒ 视频、信息不足 ⇒ `null`）；
  ④ **回放 2026-10-09 真实第 1 页原始响应**（含尾部真实 PHP 告警）：容器键 `aweme_info` 解析出
  **16 条**、逐条断言 12 项**全非空**且键序正确、图文 4 条 / 视频 12 条与站点实测一致、
  `video_type` 与 `share_url` 形态互证；
  ⑤ **文档口径守卫**：frontmatter 的描述行里必须**列全 12 项中文名**
  （防「声称 12 项、实际只写了 11 项、漏掉视频封面」这类回归）

| 组件 | 技术 | 说明 |
| ---- | ---- | ---- |
| 运行环境 | Python 3.8+ | 纯标准库，无第三方依赖 |
| 数据接口 | `u.ai-gc.art/mcp/rd.php` | 动作 `dr=dy-search-v5` |
| 鉴权 | `Authorization: Bearer <apikey>` | apikey 来自环境变量或本机密钥文件 |
| 等待策略 | 单次请求最长 600 秒 | `--timeout` 可调（`0-600`，`0` 为不设超时）；等待期间打印心跳，中途不重发 |
| 重试策略 | 每页失败后最多补 1 次 | `--retry` 可调（`0-1`，硬上限 1）；`--retry-delay` 默认 2 秒 |
| 翻页策略 | 默认只采 1 页 | `page` + `backtrace`/`offset`/`search_id` 三凭据；未到末页时给出 `next_action`，由助手问用户是否续采；四道安全阀；页数上限 50 |
| 输出 | JSON（stdout） | 供 Agent 解析后渲染为 Markdown 卡片 |

### 资源索引

- **核心脚本**：`scripts/dy_search_collect.py` — 参数：`--keyword`、`--file`、`--pages`、
  `--page`、`--backtrace`、`--offset`、`--search-id`、`--publish-time`、`--sort-type`、
  `--apikey`、`--set-apikey`、`--check-key`、`--output`、`--compact`、`--human`、`--raw`、
  `--timeout`、`--retry`、`--retry-delay`、`--sleep`
- **参考文档**：`references/api_reference.md` — 何时读取：需要核对接口原始字段名、筛选编码取值、
  查看错误码含义、调整分页/解析/重试逻辑、或**首次实测后回填结构**时

# 抖音关键词搜索接口参考（u.ai-gc.art）

> 对应技能：`dy-search-collector-kkai`（抖音关键词搜索视频数据采集助手_kkAI）
> 对应脚本：`scripts/dy_search_collect.py`
> 文档状态：**接口已实测**（2026-10-09 首次真实调用通过，逐项结论见 §7；下列 ✅ 项为本接口实测或同站点 `dy-uservideos` 结论的沿用）

## 1. 概览

| 项 | 值 |
| -- | -- |
| 站点 | `https://u.ai-gc.art/` |
| 接口 | `https://u.ai-gc.art/mcp/rd.php` |
| 动作 | `dr=dy-search-v5` |
| 方法 | POST |
| 请求头 | `Content-Type: application/json` + `Authorization: Bearer <apikey>` |
| 鉴权 | apikey 由用户登录 https://u.ai-gc.art/ 获取；本机保存于 `~/.workbuddy/ai-gc.art_apikey.txt`（按**站点**命名，同站点所有接口共用） |
| 入参 | `keyword` 关键词（必填）；`backtrace` / `offset` / `page` / `search_id` 翻页；`publish_time` / `sort_type` 筛选排序 |
| 出参 | 每页一批视频实体，**12 项规范字段按此顺序输出**：`aweme_id` / `video_cover` / `desc` / `create_time` / `nickname` / `video_duration` / `digg_count` / `comment_count` / `collect_count` / `share_count` / `video_play_addr` / `share_url` |
| 等待 | 排队型服务，单次请求 0-600 秒 |
| 额度 | 每次调用消耗额度；默认 1 页 = 1 次 |

## 2. 接口：`dr=dy-search-v5`（关键词搜索视频列表）

### 2.1 请求

```http
POST https://u.ai-gc.art/mcp/rd.php?dr=dy-search-v5
Content-Type: application/json
Authorization: Bearer <apikey>

{
  "keyword":      "WorkBuddy教程",
  "backtrace":    "",
  "offset":       0,
  "page":         1,
  "search_id":    "",
  "publish_time": "_0",
  "sort_type":    "_0"
}
```

字段说明：

| 字段 | 类型 | 首页取值 | 说明 |
| ---- | ---- | -------- | ---- |
| `keyword` | string | 必填 | 搜索关键词 |
| `backtrace` | string | `""` | 回溯参数，用于翻页；翻页时使用上次响应返回的 `backtrace` |
| `offset` | number | **`0`** | 偏移游标，用于翻页；翻页时使用上次响应返回的 `offset` |
| `page` | number | `1` | 页码，首次 1，之后每次 +1 |
| `search_id` | string | `""` | 搜索 ID，首次为空，翻页时使用上次响应返回的 `search_id` |
| `publish_time` | string | `"_0"` | 发布时间：`_0` 不限（默认）/ `_1` 一天之内 / `_7` 一周之内 / `_180` 半年之内 |
| `sort_type` | string | `"_0"` | 排序：`_0` 综合（默认）/ `_1` 最多点赞 / `_2` 最新发布 |

> ⚠️ **`offset` 首页必须传数字 `0`**（不是空串、也不是字符串 `"0"`）；脚本由 `_as_offset()` 保证。
> 站点对多余参数是容忍的，但**漏掉真正的翻页参数会让站点重新返回第 1 页**，白花一次额度。

### 2.2 成功响应结构（✅ 2026-10-09 已实测确认）

实测返回（`--raw` 留档；JSON 之后另附 840 字符 PHP 告警，已被容错忽略）：

```json
{
  "code": 200,
  "tips": "成功，u.ai-gc.art",
  "request_id": "603714b9-4f51-40d9-8e1f-79910335d559",
  "search_id": "202610092306271E14E30B1F28D6B39AAC",
  "backtrace": "ChHpCSskKAma...（约 920 字符）",
  "status_code": 0,
  "offset": 20,
  "has_more": 1,
  "aweme_info": [ { …视频实体… }, { … } ]
}
```

| 字段 | 说明 |
| ---- | ---- |
| `code` | ✅ 实测 `200`；成功态兼容 `0` / `1` / `200` / `10000` 等写法（见 §5） |
| `tips` | ✅ 实测 `成功，u.ai-gc.art` |
| `request_id` / `status_code` | ✅ 实测存在（`status_code: 0`）；脚本不依赖，仅留档 |
| `aweme_info` | ✅ 实测确认就是**视频列表容器**（顶层数组，本页 16 / 18 条） |
| `backtrace` / `offset` / `search_id` | ✅ 实测**顶层直取**命中；三个凭据须**整组**回传；`offset` 服务端为 **int**（脚本字符串化后回传被接受） |
| `has_more` | ✅ 实测为整数 `1` / `0`；兼容布尔与 `"true"/"false"` |
| `total_count` | ⚠️ 实测**不返回**该键（脚本记 `null`，不影响 `ok`） |

### 2.3 视频实体的字段（12 项规范字段，**顺序即输出顺序**）

> 2026-10-16 与需求方逐项对齐：脚本用常量 `CANONICAL_FIELDS` 固化下表顺序，
> `build_video()` 保证这 12 项**排在最前**，派生字段一律排在其后。
> 要「干净 12 列」时只取前 12 个键即可。

| # | 需求字段 | 脚本输出键 | 归一化处理 |
| - | -------- | ---------- | ---------- |
| 1 | 视频ID | `aweme_id` | 原样字符串；用于跨页去重 |
| 2 | 视频封面 | `video_cover` | 支持字符串 / 对象数组（`url_list`）；**空串 → `null`**（本接口实测**普遍有值**，与主页列表相反） |
| 3 | 视频描述 | `desc` | 去首尾空白；纯空白 → `null` |
| 4 | 发布时间 | `create_time` | 按量级判秒/毫秒 → UTC+8 可读时间；另存 `create_time_ts`（秒） |
| 5 | 用户昵称 | `nickname` | 原样 |
| 6 | 视频时长 | `video_duration` | 原值（毫秒）+ `video_duration_ms` + `video_duration_text` + `video_duration_unit: "ms"`；**图文恒为 `0`** |
| 7 | 点赞数 | `digg_count` | 兼容 `1.2万` / `5.6w` / `1,234` → 整数 |
| 8 | 评论数 | `comment_count` | 同上 |
| 9 | 收藏数 | `collect_count` | 同上 |
| 10 | 分享数 | `share_count` | 同上 |
| 11 | 视频文件地址 | `video_play_addr` | 支持对象数组；空串 → `null`。⚠️ **图文条目这里是 BGM 的 `.mp3`，不是视频文件** |
| 12 | 视频分享链接 | `share_url` | 原样字符串；含对象形态时取 `url` / `share_url` / `link` |

脚本额外输出（**排在 12 项之后**，不属于需求方 12 项）：

| 输出键 | 说明 |
| ------ | ---- |
| `create_time_ts` | 发布时间原始秒级时间戳 |
| `video_duration_ms` | 与 `video_duration` 同值（兼容历史消费方） |
| `video_duration_text` | 按毫秒换算的可读时长（`01:28`） |
| `video_duration_unit` | 时长单位口径标注，固定 `"ms"` |
| `video_url` | 规范网页链接；站点返回 `aweme_url` 时优先用它，否则按 `aweme_id` 拼 `https://www.douyin.com/video/<aweme_id>` |
| `video_type` | **作品类型**：`视频` / `图文`。判定式 = `share_url` 含 `/share/note/` 或播放地址以 `.mp3` 结尾（实测 34/34 零误判）；信息不足为 `null` |
| `page` / `index` | 该记录来自第几页 / 在结果列表中的序号（从 1 开始） |

> ⚠️ **字段为空属正常**：无描述的作品 `desc` 为空、`collect_count` 可能不返回。
> 这类情况**不做告警、不影响 `ok` 判定**，缺失字段统一为 `null`（**不编造 `0`**）。

### 2.4 字段别名表（脚本 `FIELD_ALIASES`）

脚本取值时按别名顺序命中第一个非空值，用于兼容不同版本的拼写差异。
下表按 **§2.3 的 12 项规范顺序**排列（`video_url` 为兼容别名，列在末尾）：

| 目标键 | 别名（按序） |
| ------ | ------------ |
| `aweme_id` | `aweme_id` / `awemeId` / `awemeid` / `item_id` / `itemId` / `id` |
| `video_cover` | `video_cover` / `videoCover` / `cover` / `cover_url` / `coverUrl` / `origin_cover` / `originCover` / `dynamic_cover` |
| `desc` | `desc` / `description` / `title` / `content` / `aweme_desc` |
| `create_time` | `create_time` / `createTime` / `createtime` / `publish_time` / `publishTime` / `time` / `date` |
| `nickname` | `nickname` / `nick_name` / `nickName` / `user_name` / `userName` / `username` / `nick` / `author` / `author_name` |
| `video_duration` | `video_duration` / `videoDuration` / `duration` |
| `digg_count` | `digg_count` / `diggCount` / `like_count` / `likeCount` / `liked_count` / `digg` / `like` |
| `comment_count` | `comment_count` / `omment_count` / `comments_count` / `commentCount` / `comment` |
| `collect_count` | `collect_count` / `collectCount` / `collected_count` / `collectedCount` / `collect` / `favorite_count` |
| `share_count` | `share_count` / `shareCount` / `shared_count` / `share` |
| `video_play_addr` | `video_play_addr` / `videoPlayAddr` / `play_addr` / `playAddr` / `video_url` / `vide_url` / `videoUrl` / `video_link` / `play_url` / `playUrl` |
| `share_url` | `share_url` / `shareUrl` / `aweme_url` / `awemeUrl` / `video_share_url` / `share_link` |
| `video_url`（兼容别名） | `aweme_url` / `awemeUrl` / `share_url` / `shareUrl` |

> `omment_count` 是历史文档差异拼写，保留兼容。
> **注意**：`desc` 不放进 `MSG_KEYS`——视频正文会被误当成错误信息（见 §5.5）。

### 2.5 响应体夹带 PHP 告警

同站点实测：成功响应在合法 JSON 之后会追加站点自身的 PHP 告警：

```
<br /><b>Warning</b>: Cannot modify header information - headers already sent by
(output started at /www/rd.php:157) in /www/rd.php on line 157
```

脚本用 `_loads_tolerant()` 处理：`json.loads` 失败时，改用
`json.JSONDecoder().raw_decode` 从**最靠前的 `{` 或 `[`** 起解析第一个完整 JSON 值，尾部告警自动忽略。

> ⚠️ **不要改成「截最外层花括号再 json.loads」**：那样对**顶层数组**响应（站点部分动作就是
> `[{...}]` 形态）会把整包截成 `{...}`，悄悄丢掉数组外壳。

## 3. 筛选与排序的取值归一化

站点取值是**下划线数字编码**，所以归一化方向是「中文/英文说法 → 编码」。表里没有的写法**原样透传**。

### 3.1 `publish_time`（发布时间）

| 站点取值 | 展示名 | 接受的常见写法 |
| -------- | ------ | -------------- |
| `_0` | 不限（默认） | 空 / 不限 / 全部 / 所有 / 默认 / all / any / 0 |
| `_1` | 一天之内 | 一天内 / 一天之内 / 1天内 / 一天 / 1天 / 日内 / 今天 / day / 1d / 1 |
| `_7` | 一周之内 | 一周内 / 一周之内 / 1周内 / 一周 / 7天内 / 7天 / 周内 / week / 7d / 7 |
| `_180` | 半年之内 | 半年内 / 半年之内 / 6个月内 / 半年 / 180天内 / 180天 / halfyear / half_year / 6m / 180 |

### 3.2 `sort_type`（排序方式）

| 站点取值 | 展示名 | 接受的常见写法 |
| -------- | ------ | -------------- |
| `_0` | 综合（默认） | 空 / 默认 / 综合 / 推荐 / 不限 / 全部 / general / comprehensive / default / all / 0 |
| `_1` | 最多点赞 | 最多点赞 / 点赞最多 / 最热 / 热门 / 热度 / 点赞 / hot / popularity / like / 1 |
| `_2` | 最新发布 | 最新发布 / 最新 / 时间 / time / latest / new / 2 |

> 💡 **归一化方向取决于站点取值的语言**：本接口两处都是**编码**，因此目标值必须是编码，
> 不能把中文当目标值。若实测发现站点实际接受中文，只需改别名表的「目标值」一列。

## 4. 请求次数、补救与分页

### 4.1 请求次数（可核对）

| 场景 | 请求次数 |
| ---- | -------- |
| 默认 1 页 | **1 次** |
| 采集 N 页，各页均成功 | **N 次** |
| 某一页失败一次后重试成功 | +1 次 |
| 各页都失败一次并各重试一次（最坏） | 页数 × 2（**绝无第 3 次尝试**） |

- `--retry 0` 完全关闭补发，失败也只发一轮。
- 成功过的页不会被重跑；不做轮询、不做并发。
- 结果里的 `request_count` / `retry_count` / `max_requests_per_page` / `max_requests_per_keyword` 可直接核对。

### 4.2 翻页凭据与四道安全阀

**三凭据必须整组回传**（`backtrace` / `offset` / `search_id`），另加递增的 `page`。

四道安全阀，任一命中即立即停止翻页：

| 安全阀 | 触发条件 | 脚本落点 |
| ------ | -------- | -------- |
| ① 空页 | 本页 `videos` 为空 | `collect_keyword()` 翻页循环内 `if not page_videos` |
| ② `has_more=false` | `pick_has_more()` 返回 `False` | `if result["has_more"] is False` |
| ③ 凭据全空 | `token_is_empty(next_token)` 为真，且 `has_more` 不是 `True` | `if token_is_empty(next_token)` |
| ④ 本页全重复 | 本页无任何新 `aweme_id` | `if not new_ids` |

> ⚠️ **与主页列表技能（单游标）的关键差异**：本接口有**页码参数**，服务端可能把凭据原样回显、
> 靠递增的 `page` 给出下一页，且首页凭据本就是空的。因此**只在三凭据全空时**才判定没有下一页，
> **不能**用「凭据没变就停」——那会在第一页就把翻页误停掉。
> 脚本对「凭据与请求时相同」只写一条 warning 并继续按 `page` 推进。

### 4.3 等待策略

- 单次请求等待上限默认 **600 秒**，`--timeout` 可调（`0-600`，`0` = 不设超时）。
- 等待期间每 **15 秒**向 stderr 打印一次心跳 `[等待中] …`。
- **中途不重发**，不会因为"看起来卡住了"就重复消耗额度。
- 超时属于**可重试**错误：脚本自动补一次；仍超时则调大 `--timeout` 后由用户确认再发起。

### 4.4 多关键词与中止规则

- 一个 `--keyword` 值内支持 `|` / `｜` / `;` / `；` / 换行分隔；也支持重复传参；也支持 `--file`。
- ⚠️ **空格与逗号不是分隔符**（关键词本身可能含空格或逗号，如「AI 视频 教程」「猫,狗 训练」）。
- 关键词**自动去重**（不区分大小写），丢弃条数记入顶层 `duplicates_removed`。
- **批量撞上四类账户级错误**（`unauthorized` / `insufficient_balance` / `upstream_busy` /
  `action_forbidden`）**立即中止整批**，剩余关键词记入 `skipped_keywords`，`aborted=true`，
  顶层 `next_action.reason = "fatal_error"`。理由：这类错误对后面每个关键词都是同样结果，
  继续采只会白刷额度。
- **多关键词 + 翻页凭据**同时出现时，写一条顶层告警：凭据只对应上一页所属的**那一个**关键词。

## 5. 状态码与错误

### 5.1 判定顺序（固定，不要调整）

```
余额不足 → 动作被拒 → 鉴权失败 → 上游限流 → 其他
```

原因：余额不足的文案里也含「请登录」，不先判会被鉴权分支抢走；动作被拒是 HTTP 403，
不先判会被 `status in (401, 403)` 抢走并误报「apikey 无效」。

### 5.2 三种失败形态必须分清

| 情形 | HTTP | 响应体 | 分类 |
| ---- | ---- | ------ | ---- |
| 余额不足 | 200 | JSON `{"code":402,"tips":"余额不足，请登录 u.ai-gc.art ，请充值后重试"}` | `insufficient_balance` |
| **dr 动作名不被站点接受** | **403** | **裸文本 `forbidden`（非 JSON）** | `action_forbidden` |
| apikey 无效 / 过期 | 200 | JSON `{"code":403,"tips":"访问被拒绝: 无效的apikey，请登录 u.ai-gc.art 获取"}` | `unauthorized` |
| 未携带 apikey | 401 | 裸文本 `missing api key` | `unauthorized` |
| 上游临时故障 / 限流 | 200 | JSON `{"code":404,"tips":"404,API 请求失败,请10分钟后，再重试"}` | `upstream_busy` |

> 🔑 **关键结论**：`403 + 裸 forbidden` **与 apikey 完全无关**——同站点实测
> 「有效密钥 + 错误动作名」与「无效密钥 + 错误动作名」返回**完全相同**。
> 若把它归入 `unauthorized`，会提示用户去重新获取 apikey，而这是无效的排查方向。
> 因此 `looks_like_action_forbidden()` 必须先于鉴权分支判定，且**要求响应体是非 JSON 的裸文本**；
> 若 403 但响应体是 JSON，仍归 `unauthorized`。

### 5.3 不可补发的错误

| `error_code` | 原因 | 处理 |
| ------------ | ---- | ---- |
| `unauthorized` | apikey 失效 / 未带密钥 | 提示用户重新登录站点获取；**不要反复重试同一个 key** |
| `insufficient_balance` | 余额耗尽 | 提示充值；**apikey 本身有效，不要引导重新获取** |
| `upstream_busy` | 上游临时故障 / 限流 | **等约 10 分钟后原样重跑**；不要改参数、不要重取 apikey、不要立刻重发 |
| `action_forbidden` | 动作名被网关拒绝 | **明确告知不要重新获取 apikey**；核对动作名或联系站点支持 |

四者都会带 `action_required` 字段，可直接作为给用户的话术。
反向约定：形如「服务器繁忙，请稍后重试」这类**普通业务失败仍会补发一次**。

### 5.4 退出码

| 退出码 | 含义 |
| ------ | ---- |
| 0 | 全部成功 |
| 1 | 部分或全部采集失败 |
| 2 | 参数错误（未传关键词 / 文件不存在） |
| 3 | 缺少 apikey |

### 5.5 业务正文不污染错误判定（真实事故回归）

**2026-10-01 实测教训（真实事故，发生在同站点的 `xhs-usernotes` 上）**：

成功返回的一页 20 条记录里，有一条标题是「AI工作流**1分钟**生成火爆精美菜谱…」。
旧实现把整包 43KB 正文拼进「错误文案启发式判断」的 blob，标题里的「1分钟」命中了限流正则
`\d+分钟`，于是**整页成功数据被误判成 `upstream_busy` 直接丢弃**。

**结论：错误诱因只能从「提示字段」里找，业务正文是数据，不是信号。**

脚本落点：`_error_blob()` 只取 `MSG_KEYS`（`msg`/`message`/`error`/`errmsg`/`info`/`reason`/`tips`）
里的提示字段；非 JSON 时才退回原文且**限长 600 字符**。
`desc` **刻意不放进** `MSG_KEYS`，避免视频正文被当成错误信息。

## 6. 排查清单

| 现象 | 可能原因 | 排查动作 |
| ---- | -------- | -------- |
| 拿不到视频列表但接口成功 | 关键词无结果 / 筛选过窄 / 容器键不同 | 加 `--raw --human` 看原始响应；核对容器键并回填 §7 |
| 每页都返回第 1 页的内容 | 翻页凭据没整组带上 / 站点重新起搜 | 核对 `--page` 与三个凭据是否都传了；看 `warnings` |
| 翻页在第一页就停了 | 误用「凭据没变就停」 | 确认用的是本版脚本（只在三凭据全空时才停） |
| `video_cover` 全是 `-` | 站点对每条都返回空串（同站点实测如此） | 属站点侧数据缺口，**不是采集失败**，不要重跑 |
| 所有动作都返回 `code:402 余额不足` | 账户余额耗尽 | 先跑 `--check-key` 确认密钥，再充值。此时换参数探测都是白费 |
| 403 且响应体是裸 `forbidden` | 动作名不被站点接受 | **不要重新获取 apikey**；核对动作名或联系站点支持 |
| 时间显示差 8 小时 | 时间戳被按 UTC 解释 | 本脚本按 UTC+8（`CN_TZ`）解释，国内平台约定 |
| 时长显示差 1000 倍 | 单位口径不符 | 本脚本按**毫秒**解释（同站点实测）；若实测为秒需改 `format_duration()` |
| 部分记录「时长 0」、拿到的「视频文件地址」是 `.mp3` | 该条是**图文笔记**（非视频），`video_play_addr` 是 BGM 音频 | **不是采集失败**：看输出的 `video_type`（应为 `图文`）；呈现时标为「图文」，勿当视频下载 |

## 7. 实测回填记录（2026-10-09 已完成）

> ✅ **本接口已于 2026-10-09 完成首次真实调用**：关键词「WorkBuddy教程」，第 1 + 2 页共 34 条，
> 每页 1 次请求、零重试；两页 `aweme_id` **零重叠**，证明三凭据翻页真实有效。
> 下表逐项记录实测结论（🔶 = 本次尚未覆盖）。

| 待确认项 | 实测结论 | 状态 |
| -------- | -------- | ---- |
| 列表容器键 | 顶层数组 **`aweme_info`**（本页 16 / 18 条），脚本置首候选命中 | ✅ |
| 响应顶层结构 | `{code:200, tips:"成功，u.ai-gc.art", request_id, search_id, backtrace, status_code:0, offset, has_more, aweme_info}` | ✅ |
| 三个凭据的字段名与类型 | **顶层直取**命中：`backtrace`(str, 920–960 字符) / `offset`(**int**, 0→20→40) / `search_id`(str, 同一会话内不变) | ✅ |
| `offset` 首页取值 | 数字 `0`（脚本传 int `0`）；服务端回传 int，脚本字符串化后回传 `--offset "20"` **被接受** | ✅ |
| `has_more` 类型与末页取值 | 整数 `1`（还有下一页） | ✅ |
| `create_time` 量级 | Unix **秒**（`1785381003` → `2026-07-30 11:10:03`，UTC+8） | ✅ |
| `video_duration` 单位 | **毫秒**（`292106` → `04:52`） | ✅ |
| `video_cover` 是否为空串 | ⚠️ **非空**，每条都有封面 URL（与同站点主页列表相反） | ✅ |
| 单页条数 | 不固定：第 1 页 16 条、第 2 页 18 条 | ✅ |
| 是否返回 `total_count` | **不返回**（顶层无该键，记录级与顶层均为 `null`） | ✅ |
| `aweme_url` | 站点**直接返回**每条 `https://www.douyin.com/video/<aweme_id>`，脚本优先采用 | ✅ |
| 结果为图文 / 视频混合流 | ⚠️ 34 条中约 9 条是图文笔记（`share_url` 含 `/share/note/`、`video_duration=0`、`video_play_addr` 为 BGM 的 mp3）；`type` 字段全为 `'1'`，无法据此区分 | ✅ 已同步 SKILL.md §1.3 |
| PHP 告警夹带 | 实测 JSON 后追加 **840 字符** `<br /><b>Warning</b>: Cannot modify header information …`，容错解析正常 | ✅ |
| `publish_time` / `sort_type` 的实际接受值 | 默认 `_0` / `_0` 可用；**其他取值本次未实测** | 🔶 |
| 页数上限 / 是否有额外限流 | 未触及（本次仅翻到第 2 页） | 🔶 |

**原始响应留档**：`--raw` 已把每页完整响应存进 `raw_responses`（本次第 1 页 body **43,222 字符**，
其中 JSON 部分 42,382 字符 + 尾部 840 字符 PHP 告警），日后核对不必再花额度。

**夹具入库（2026-10-16）**：第 1 页原始响应已压成
**`tests/real_2026-10-09_page1.json`**（20.5 KB）—— 只截断超长 CDN 直链（标注 `<truncated N chars>`），
**键名 / 类型 / 短值（`aweme_id` / `code` / `offset` / `has_more` / 计数）/ 尾部真实 PHP 告警全部原样**。
离线测试的第 17 组会**回放这份夹具**：容器键、16 条记录、12 项字段全非空、图文 4 / 视频 12、
字段顺序 —— 站点日后改结构，跑一次测试就能发现（零额度）。

首次实测所用命令（各 1 次额度）：

```bash
# 第 1 页（默认只采 1 页）
python scripts/dy_search_collect.py --keyword "WorkBuddy教程" --output p1.json --raw --human
# 第 2 页（用第 1 页 next_action 的三凭据续采，勿重跑第 1 页）
python scripts/dy_search_collect.py --keyword "WorkBuddy教程" --page 2 \
    --search-id "<上页>" --backtrace "<上页>" --offset "20" --pages 1 --output p2.json --raw --human
```

## 8. 零成本探针与额度纪律

**不花额度的检查**：

```bash
# 检查 apikey 是否配置（不发请求）
python scripts/dy_search_collect.py --check-key

# 只看解析出的关键词与参数，不发请求
python scripts/dy_search_collect.py --keyword "a|b" --pages 2
# （会真实采集；如需纯本地校验，请用离线测试）

# 纯离线回归测试（零额度、无需 apikey）
python tests/test_dy_search_collect.py
```

**额度纪律**：

1. **默认只采 1 页**，采完问用户是否继续（硬规则，见 SKILL.md §1.4）。
2. **续采必须带 `--page` + 三个凭据**，别重跑不带凭据的命令。
3. 先用 `--publish-time` / `--sort-type` 缩小范围，少翻页就拿到想要的内容。
4. **真实采集一律 `--output` 落盘**再渲染（stdout 过大时会在工具回显层被中间截断）。
5. 调试一律用离线测试；改脚本后先跑测试再花钱验证。
6. **排查先看额度**：余额耗尽后所有计费动作都变成 `code:402`，此时换参数探测纯属浪费。

## 9. 与同族技能的对照

| 维度 | `dy-user-collector-kkai`（主页列表） | 本技能（关键词搜索） |
| ---- | ------------------------------------ | -------------------- |
| 动作 | `dr=dy-user-id2` + `dr=dy-uservideos` | `dr=dy-search-v5`（单动作） |
| 入参 | `share_txt` / `sec_user_id` | `keyword` + 筛选排序 |
| 翻页 | 单游标 `max_cursor`（首页传数字 `0`） | 三凭据 `backtrace`/`offset`/`search_id` + 递增 `page` |
| 「凭据不变」可否当停止条件 | **可以**（等价于服务端回显） | **不可以**（有 `page` 参数，会在首页误停） |
| 结果容器键 | `aweme_info`（✅ 实测） | `aweme_info`（✅ 实测） |
| 视频封面 | 实测多为空串 `""`（站点侧缺口） | ✅ 实测**每条都有封面 URL** |
| 字段口径 | 12 项（含封面/分享链接） | 12 项，同口径（时长毫秒、时间戳秒），**顺序按需求方规范固定** |
| 作品类型 | 视频为主 | **图文/视频混合流** ⇒ 输出 `video_type`（`share_url` 含 `/share/note/` 判为图文，实测 34/34） |
| 默认页数 | 1 页 + 追问续采 | 1 页 + 追问续采 |
| 重试 | 每步失败补 1 次，绝无第 3 次 | 同 |
| 等待 | 0-600 秒，心跳 15 秒 | 同 |

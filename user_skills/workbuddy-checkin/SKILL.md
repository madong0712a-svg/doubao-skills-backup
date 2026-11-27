---
name: workbuddy-checkin
slug: workbuddy-auto
displayName: WorkBuddy 积分自动领取
display_name: WorkBuddy 积分自动领取
display_name_en: WorkBuddy Auto Check-in
description_zh: "一个命令领完 WorkBuddy 每日签到积分，顺手把猫猫旅行自动派出并到期领取。走官方 WBIPC 命名管道调用，登录态由宿主注入，报错带可读提示，断线自动重试。"
description_en: "Claim WorkBuddy daily check-in credits and auto-dispatch/collect the buddy travel reward in one command. Calls the official WBIPC named pipe with host-injected login state; friendly error messages and automatic retry on disconnect."
version: "2.1.0"
summary: 一个命令领完 WorkBuddy 每日签到积分，顺手把猫猫旅行自动派出并到期领取。走官方 WBIPC 命名管道调用，登录态由宿主注入。
description: 自动领取 WorkBuddy 桌面端每日签到积分与猫猫旅行奖励。通过官方 WBIPC 协议（命名管道 + 双向 HMAC 鉴权）调用 wb.request 转发器，由宿主自动注入登录态；脚本自身不读取、不存储、不输出 token。
license: MIT
homepage: https://skillhub.cn/skills/user_934b64b5/workbuddy-auto
metadata:
  category: automation
  platform: windows
  version: "2.1.0"
  python: ">=3.10"
  requirements: ["pywin32>=306"]
  trigger:
    - "WorkBuddy 积分"
    - "WorkBuddy 签到"
    - "猫猫旅行"
    - "猫猫派出"
    - "领签到积分"
    - "签到领奖"
    - "WorkBuddy check-in"
    - "wb 签到"
    - "帮我签到"
    - "今天签到了吗"
---

# WorkBuddy 自动签到 + 猫猫旅行

一条命令完成：每日签到 → 猫猫空闲自动派出 → 到期自动领取。脚本幂等，重复跑不会重复领奖。

> **平台限制**：仅支持 Windows（依赖 WBIPC 命名管道 + pywin32）。macOS/Linux 上端点
> 文件路径、管道名、模块依赖全部不同，需重写 `_connect()` 与 `EP_PATH`。

## 快速开始

```bash
# 1) 确认依赖：WorkBuddy 桌面端已启动并登录；Python 装了 pywin32
pip install -r requirements.txt

# 2) 先跑自检（只握手，不产生任何业务请求）
python scripts/main.py selftest

# 3) 一条命令领完
python scripts/main.py all
```

首次使用建议只跑 `selftest`：成功输出说明通道、登录态都正常；失败时按输出里的 `action` 提示操作即可，报错都是大白话。

## 子命令

| 子命令 | 说明 | 副作用 |
| --- | --- | --- |
| `status` | 签到状态 + 猫猫全状态（只读） | 无 |
| `checkin` | 仅签到 | 有（幂等） |
| `travel` | 智能调度：`idle` 派出 / `traveling` 报告到达时间 / `arrived` 领取 | 有（幂等） |
| `all` | 签到 + 智能调度（推荐日常用） | 有（幂等） |
| `selftest` | 健康检查：握手 + 列管道，不发业务请求 | 无 |

可选参数：`--location 1-4` 指定派往地点（**1 咖啡馆 / 2 商场店铺 / 3 健身房 / 4 古镇客栈**，每次 1-4 小时、5-10 积分），不填随机。传了非法值会被拦截并提示正确范围，不会静默忽略。

## 实际运行示例

`python scripts/main.py all` 成功时的输出（节选自真实运行）：

```json
{
  "checkin": {
    "status": 200,
    "body": {
      "code": 0,
      "msg": "OK",
      "data": {
        "today_checked_in": true,
        "streak_days": 39,
        "daily_credit": 100,
        "today_credit": 100
      }
    }
  },
  "travel": {
    "action": "noop",
    "state": "traveling",
    "arrive_at": "2026-11-08T16:42:00+08:00",
    "reward_credit": 8,
    "location": "咖啡馆"
  }
}
```

失败时的输出（可读，不是裸堆栈）：

```json
{
  "ok": false,
  "error": {
    "code": "E_DISCONNECTED",
    "message": "连接在执行途中断开（通常是桌面端正在重启或网络切换）。",
    "action": "重跑一次本命令即可；签到和领取都是幂等的，不会重复扣发。"
  },
  "hint": "脚本可重复运行，不会重复领奖；已自动重试 1 次仍失败。"
}
```

`traveling` / `noop` / 领取 `code:400 msg:"no unclaimed travel"` 都属于**正常现象**，不需要处理——下个调度周期会自动接上。

## 自动化（推荐）

在 WorkBuddy 桌面端配置自动化任务，**建议每 4 小时执行一次** `main.py all`。脚本幂等，随便跑：

**为什么是 4 小时**：猫猫旅行单程 1-4 小时，4 小时的间隔保证每次旅行结束后最多 4 小时内就会被领取， reward 损失窗口最小；签到一天只需成功一次，4 小时频次绰绰有余，也不会对桌面端造成请求压力。

- 已签到 → `code:10001 "今天已签到"`（正常）
- 旅行 `idle` → 自动派出（`action:"depart"`）
- 旅行 `traveling` → 只报告到达时间，到点后下次运行自动领取
- `daily_limit_reached: true` → 不再派发（领取不受影响）

## 常见问题

**Q：会重复领奖吗？** 不会。签到接口幂等（已签返回 10001），领取只在 `arrived` 状态触发，领取后状态即变为 `idle`。

**Q：WorkBuddy 没开时跑会怎样？** 返回 `E_NO_ENDPOINT` / `E_PIPE_GONE`，提示先启动桌面端。不会卡死、不会误发请求。

**Q：断网/桌面端重启会不会把奖励搞丢？** 不会。断线时脚本自动重试 1 次；仍失败则报 `E_DISCONNECTED`，重跑即可。签到与领取都是服务端幂等操作。

**Q：想指定猫猫去哪？** `travel --location 3`（健身房）。传 0、5、-1 等非法值会直接被拦下并提示，不会静默随机。

**Q：不想用 WorkBuddy 自带 Python？** 系统任何 Python ≥3.10 + pywin32 都行。

## 故障排查

先跑 `selftest`，再看下表。每行给出：现象 → 含义 → 你该做什么。

| 错误码 / 现象 | 含义 | 处置 |
| --- | --- | --- |
| `E_NO_ENDPOINT` | 找不到端点文件（桌面端没开） | 启动 WorkBuddy 并登录 |
| `E_SPOOFED_ENDPOINT`（原 `server proof verification failed`） | 端点被抢占或文件过期 | 关掉多余 WorkBuddy 窗口；重启桌面端 |
| `E_PIPE_GONE`（原 `ReadFile err=2/53`） | 桌面端未运行 / 管道不存在 | 启动 WorkBuddy 并登录 |
| `E_DISCONNECTED`（原 `ReadFile err=109`） | 执行途中断开 | 脚本已自动重试 1 次；重跑即可 |
| `E_TIMEOUT` | 桌面端无响应 | 等 10 秒重试；连续失败重启桌面端 |
| `E_NOT_LOGGED_IN` | 宿主未登录 | 去 WorkBuddy 登录一次 |
| `E_BAD_LOCATION` | `--location` 非法 | 用 1-4，或不传 |
| `unknown pipe` | 升级后管道名变化 | 跑 `selftest` 看 `pipes` 列表 |

## 端点清单

| 路径 | 方法 | 含义 |
| --- | --- | --- |
| `/v2/billing/meter/checkin-activity-status` | POST | 签到状态（`today_checked_in` / `streak_days` / `total_credits`） |
| `/v2/billing/meter/daily-checkin` | POST | 每日签到 |
| `/activity/growth/buddy/info` | GET | 猫猫全状态（**不带 `/v2`**，带前缀 404） |
| `/activity/growth/buddy/travel/status` | GET | 旅行状态：`idle` / `traveling` / `arrived` |
| `/activity/growth/buddy/travel/config` | GET | 可派往地点（4 个） |
| `/activity/growth/buddy/travel/depart` | POST | 派出，body `{"location_id": 1-4}` |
| `/activity/growth/buddy/travel/claim` | POST | 领取到达奖励 |

## 工作原理（WBIPC）

| 项 | 值 |
| --- | --- |
| 通道 | Windows 命名管道 `\\.\pipe\wbipc-<uuid>`，端点写入 `%WORKBUDDY_CONFIG_DIR%\wbipc\endpoint.json` |
| 鉴权 | HMAC-SHA256 双向证明（`wbipc-s`/`wbipc-c` transcript），客户端先 verify `server_proof`，失败 fail-closed |
| 暴露管道 | `wb.request`（`http.fetch` 转发器，宿主注入 Authorization / X-User-Id / X-Domain / Turing shield） |
| 请求头白名单 | 仅 `content-type` / `accept` |
| 响应体上限 | 640KB（超限 `E_PAYLOAD_TOO_LARGE`） |
| 协议 | `session_hello → challenge → prove → ack` → JSON-RPC 2.0，newline-delimited JSON |

### 环境变量

| 变量 | 作用 | 默认 |
| --- | --- | --- |
| `WORKBUDDY_CONFIG_DIR` | WBIPC 端点文件所在根目录 | `%USERPROFILE%\.workbuddy` |
| `WBIPC_ENDPOINT_PATH` | 直接指定 endpoint.json 绝对路径（优先级最高） | — |

### 安全边界

- 脚本自身不读取、不存储、不输出 token / ticket / cookie 内容
- 登录态（Authorization 等请求头）由宿主在转发时注入，脚本经 WBIPC 只能访问上述白名单端点
- ticket 仅存在于宿主内存与端点文件（用于握手），随桌面端重启刷新

## 路径与依赖

- 端点：`%WORKBUDDY_CONFIG_DIR%\wbipc\endpoint.json`（可被 `WBIPC_ENDPOINT_PATH` 覆盖）
- 推荐解释器：`%USERPROFILE%\.workbuddy\binaries\python\versions\3.13.12\python.exe`
- Python 包依赖：`pywin32>=306`（见 `requirements.txt`；**未安装时脚本第一步就会报模块缺失，装完即用**）

## 更新日志

### 2.1.0

- **报错全面中文化**：所有底层异常翻译为 `code + message + action` 三段式，含建议动作，不再输出裸堆栈。
- **瞬时故障自动重试**：断线/超时/管道暂时不可用自动重试 1 次。
- **参数前置校验**：`--location` 非法值直接拦截并提示正确范围；启动即自检 pywin32 依赖。
- **补充真实运行示例**（成功 + 失败各一）、FAQ 与错误码对照表。
- 收敛安全表述：明确"脚本不读取/存储/输出 token"，登录态由宿主注入。
- 修正 2.0.0 更新日志中关于 icon/assets 文件的描述（实际未随包发布，已从 frontmatter 移除 `icon` 字段）。

### 2.0.0

- 旅行改为三态智能调度（idle 派出 / traveling 报告 / arrived 领取）。
- 新增 `--location 1-4`。
- 修正 `/activity/growth/buddy/info` 路径（v5.6 起带 `/v2` 会 404）与排错指引。
- Python 要求 `>=3.13` → `>=3.10`；补 `requirements.txt`。

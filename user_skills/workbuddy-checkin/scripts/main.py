#!/usr/bin/env python3
"""workbuddy-checkin skill: claim daily check-in + cat-travel reward.

Uses the official WBIPC pipe `wb.request` (HTTP forwarder) to call WorkBuddy
backend endpoints. The host automatically attaches the session Authorization,
X-User-Id, X-Domain and Turing shield headers; this script itself does not read
or log tokens (the endpoint ticket is supplied by the host and only used for
the pipe handshake).

Endpoints (POST):
  - /v2/billing/meter/daily-checkin       (sign-in, idempotent: already_checked
                                              or success)
  - /v2/billing/meter/checkin-activity-status (current check-in state)
  - /activity/growth/buddy/info           (buddy + travel state; note: NO /v2 prefix)
  - /activity/growth/buddy/travel/status  (idle / traveling / arrived)
  - /activity/growth/buddy/travel/config  (available destinations)
  - /activity/growth/buddy/travel/depart  (send buddy out, body {location_id: 1-4})
  - /activity/growth/buddy/travel/claim   (claim arrived reward)

Subcommands:
  status    read check-in + buddy + travel status, no mutation
  checkin   claim today's check-in only
  travel    smart dispatch: idle -> depart / traveling -> report / arrived -> claim
  all       checkin + smart dispatch (idempotent)
"""
from __future__ import annotations
import argparse, base64, hashlib, hmac, json, os, secrets, struct, sys, threading, time
from pathlib import Path
import win32file, pywintypes

# WBIPC endpoint file: written by WorkBuddy desktop at
# $WORKBUDDY_CONFIG_DIR/wbipc/endpoint.json. Override with the env var
# WORKBUDDY_CONFIG_DIR to relocate; defaults to %USERPROFILE%\.workbuddy on Windows.
_EP_PATH = os.environ.get("WBIPC_ENDPOINT_PATH")
if _EP_PATH:
    EP_PATH = Path(_EP_PATH)
else:
    _base = Path(os.environ.get("WORKBUDDY_CONFIG_DIR")
                 or (Path(os.environ.get("USERPROFILE", str(Path.home())))
                     / ".workbuddy"))
    EP_PATH = _base / "wbipc" / "endpoint.json"
PROTOCOL = 1
HANDSHAKE_TIMEOUT_MS = 5000
RPC_TIMEOUT_S = 20


def ticket_id(ticket: str) -> str:
    return hashlib.sha256(ticket.encode("utf-8")).hexdigest()[:16]


def _encode(role: str, t: dict) -> bytes:
    parts = [
        "wbipc-s" if role == "server" else "wbipc-c",
        str(t["protocol"]),
        t["endpoint"],
        t["clientNonce"],
        t["serverNonce"],
    ]
    chunks = []
    for p in parts:
        b = p.encode("utf-8")
        chunks.append(struct.pack(">I", len(b)))
        chunks.append(b)
    return b"".join(chunks)


def _proof(ticket: str, role: str, t: dict) -> str:
    return base64.urlsafe_b64encode(
        hmac.new(ticket.encode("utf-8"), _encode(role, t), hashlib.sha256).digest()
    ).decode("ascii").rstrip("=")


def _read_chunk_sync(handle, deadline: float) -> bytes:
    box = {"err": None, "data": None}
    def worker():
        try:
            err, data = win32file.ReadFile(handle, 65536, None)
            box["err"], box["data"] = err, data
        except pywintypes.error as e:
            box["err"] = e.winerror
    t = threading.Thread(target=worker, daemon=True)
    t.start()
    remain = deadline - time.time()
    if remain < 0: remain = 0
    t.join(remain)
    if t.is_alive():
        raise TimeoutError("WBIPC read timed out")
    err, data = box["err"], box["data"]
    if err == 109:
        return b""
    if isinstance(err, int) and err == 0:
        return bytes(data) if data else b""
    if err and err != 0:
        raise OSError(f"ReadFile err={err}")
    return bytes(data) if data else b""


def _read_frame(handle, deadline: float) -> dict:
    buf = b""
    while True:
        if time.time() > deadline:
            raise TimeoutError("WBIPC read deadline exceeded")
        i = buf.find(b"\n")
        if i >= 0:
            line = buf[:i]
            buf = buf[i+1:]
            if not line.strip():
                continue
            return json.loads(line.decode("utf-8"))
        chunk = _read_chunk_sync(handle, deadline)
        if not chunk:
            return None
        buf += chunk


def _write_frame(handle, obj: dict):
    data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
    win32file.WriteFile(handle, data, None)


class WbipcClient:
    def __init__(self):
        ep = json.loads(EP_PATH.read_text(encoding="utf-8"))
        self.endpoint = ep["endpoint"]
        self.ticket = ep["ticket"]

    def __enter__(self):
        GENERIC_READ_WRITE = 0xC0000000
        OPEN_EXISTING = 3
        self.handle = win32file.CreateFile(
            self.endpoint, GENERIC_READ_WRITE, 0, None, OPEN_EXISTING, 0, None
        )
        self.chan = None
        return self

    def __exit__(self, *exc):
        try:
            if self.handle:
                win32file.CloseHandle(self.handle)
        except Exception:
            pass

    def handshake(self) -> dict:
        ticket = self.ticket
        cnonce = base64.urlsafe_b64encode(secrets.token_bytes(16)).decode().rstrip("=")
        dl = time.time() + HANDSHAKE_TIMEOUT_MS / 1000.0
        _write_frame(self.handle, {
            "type": "session_hello",
            "protocol_min": PROTOCOL,
            "protocol_max": PROTOCOL,
            "client_nonce": cnonce,
            "ticket_id": ticket_id(ticket),
            "client": {"kind": "python-skill", "id": "workbuddy-checkin", "version": "2.0"},
        })
        msg = _read_frame(self.handle, dl)
        if not msg or msg.get("type") != "session_challenge":
            raise RuntimeError(f"WBIPC: expected session_challenge, got {msg}")
        transcript = {
            "protocol": PROTOCOL,
            "endpoint": self.endpoint,
            "clientNonce": cnonce,
            "serverNonce": msg["server_nonce"],
        }
        expected = _proof(ticket, "server", transcript)
        if not hmac.compare_digest(expected, msg["server_proof"]):
            raise RuntimeError("WBIPC: server proof verification failed (endpoint may be spoofed)")
        _write_frame(self.handle, {
            "type": "session_prove",
            "client_proof": _proof(ticket, "client", transcript),
        })
        msg = _read_frame(self.handle, dl)
        if not msg or msg.get("type") != "session_hello_ack":
            raise RuntimeError(f"WBIPC: expected session_hello_ack, got {msg}")
        return msg

    def get_pipe(self, pipe: str) -> dict:
        return self.invoke("broker/GetPipe", {"pipe": pipe})

    def _bind_pipe(self, pipe: str):
        if self.chan is not None:
            return
        r = self.get_pipe(pipe)
        self.chan = r["channel"]
        self.methods = r["methods"]

    def invoke(self, method: str, params: dict) -> dict:
        cid = secrets.randbelow(2**31)
        req = {
            "jsonrpc": "2.0", "id": cid, "method": method, "params": params, "mode": "call",
        }
        _write_frame(self.handle, req)
        dl = time.time() + RPC_TIMEOUT_S
        while True:
            msg = _read_frame(self.handle, dl)
            if msg is None:
                raise RuntimeError("WBIPC: connection closed during invoke")
            if "jsonrpc" not in msg:
                continue
            if msg.get("id") == cid:
                if "error" in msg:
                    raise RuntimeError(f"WBIPC error: {msg['error']}")
                return msg.get("result")

    def fetch(self, method: str, path: str, body_b64: str | None = None,
              query: dict | None = None) -> dict:
        self._bind_pipe("wb.request")
        params = {"method": method, "path": path}
        if query: params["query"] = query
        if body_b64 is not None: params["body_b64"] = body_b64
        return self.invoke(f"{self.chan}/http.fetch", params)

    def http(self, method: str, path: str, json_body: dict | None = None) -> dict:
        body_b64 = None
        if json_body is not None:
            body_b64 = base64.b64encode(json.dumps(json_body, ensure_ascii=False).encode("utf-8")).decode("ascii")
        r = self.fetch(method, path, body_b64)
        status = r.get("status", 0)
        b64 = r.get("body_b64") or ""
        body_bytes = base64.b64decode(b64) if b64 else b""
        text = body_bytes.decode("utf-8", errors="replace")
        try:
            data = json.loads(text) if text else None
        except Exception:
            data = text
        return {"status": status, "headers": r.get("headers", {}), "body": data}


def cmd_status(c: WbipcClient) -> dict:
    chk = c.http("POST", "/v2/billing/meter/checkin-activity-status")
    buddy = c.http("GET", "/activity/growth/buddy/info")
    trvl = cmd_travel_status(c)
    return {
        "checkin": chk,
        "buddy": buddy,
        "travel": trvl,
    }


def cmd_selftest(c: WbipcClient, ack: dict) -> dict:
    """健康检查：仅列 pipe，不重复握手。调用方负责已经完成握手。"""
    pipes = c.invoke("broker/ListPipes", {})
    return {
        "ok": True,
        "endpoint": c.endpoint,
        "pipes": pipes.get("pipes", []),
        "ack": {k: v for k, v in ack.items() if k in ("type", "protocol", "max_inflight")},
    }


def cmd_checkin(c: WbipcClient) -> dict:
    return c.http("POST", "/v2/billing/meter/daily-checkin")


def cmd_travel_status(c: WbipcClient) -> dict:
    """查询猫猫旅行当前状态（idle / traveling / arrived）。"""
    return c.http("GET", "/activity/growth/buddy/travel/status")


def cmd_travel_config(c: WbipcClient) -> dict:
    """查询可派往的地点列表。"""
    return c.http("GET", "/activity/growth/buddy/travel/config")


def cmd_travel_depart(c: WbipcClient, location_id: int | None = None) -> dict:
    """派出猫猫旅行。location_id 不指定时随机选一个地点（1-4）。"""
    import random
    lid = location_id if location_id in (1, 2, 3, 4) else random.randint(1, 4)
    return c.http("POST", "/activity/growth/buddy/travel/depart", {"location_id": lid})


def cmd_travel_claim(c: WbipcClient) -> dict:
    """领取已到达的旅行奖励。"""
    return c.http("POST", "/activity/growth/buddy/travel/claim", {})


def cmd_travel(c: WbipcClient, location_id: int | None = None) -> dict:
    """智能旅行调度：查状态 → idle则派出 / traveling则报告 / arrived则领取。"""
    status_resp = cmd_travel_status(c)
    data = status_resp.get("body", {}).get("data", {})
    state = data.get("state", "unknown")

    if state == "arrived":
        # 已到达 → 直接领取
        claim_resp = cmd_travel_claim(c)
        return {
            "action": "claim",
            "state": state,
            "status": status_resp,
            "claim": claim_resp,
        }
    elif state == "idle":
        # 空闲 → 尝试派出
        daily_limit = data.get("daily_limit_reached", False)
        if daily_limit:
            return {
                "action": "noop",
                "state": state,
                "reason": "daily_limit_reached",
                "status": status_resp,
            }
        depart_resp = cmd_travel_depart(c, location_id)
        return {
            "action": "depart",
            "state": state,
            "status": status_resp,
            "depart": depart_resp,
        }
    elif state == "traveling":
        return {
            "action": "noop",
            "state": state,
            "arrive_at": data.get("arrive_at"),
            "reward_credit": data.get("reward_credit"),
            "location": data.get("location", {}).get("name"),
            "status": status_resp,
        }
    else:
        return {
            "action": "unknown_state",
            "raw_status": status_resp,
        }


def _friendly_error(e: Exception) -> dict:
    """把底层异常翻译成普通用户能看懂的话 + 建议动作。"""
    s = str(e)
    winerr = getattr(e, "winerror", None)
    if "endpoint.json" in s or isinstance(e, FileNotFoundError):
        return {"code": "E_NO_ENDPOINT",
                "message": "找不到 WorkBuddy 的通信端点文件。",
                "action": "请先启动 WorkBuddy 桌面端并完成登录，再运行本脚本。",
                "detail": s}
    if "server proof" in s:
        return {"code": "E_SPOOFED_ENDPOINT",
                "message": "通信端点校验失败（可能被另一个实例占用或端点文件过期）。",
                "action": "关闭多余的 WorkBuddy 窗口；若仍失败，重启 WorkBuddy 桌面端后重试。",
                "detail": s}
    if isinstance(e, TimeoutError) or "timed out" in s or "deadline" in s:
        return {"code": "E_TIMEOUT",
                "message": "WorkBuddy 响应超时，桌面端可能正忙或已假死。",
                "action": "等 10 秒后重试一次；若连续失败，重启 WorkBuddy 桌面端。",
                "detail": s}
    if winerr in (2, 53) or "CreateFile" in s:
        return {"code": "E_PIPE_GONE",
                "message": "连不上 WorkBuddy 的内部通道（桌面端未运行或已退出）。",
                "action": "启动 WorkBuddy 桌面端并登录后重试。",
                "detail": s}
    if winerr == 109 or "connection closed" in s or "E_NOT_CONNECTED" in s:
        return {"code": "E_DISCONNECTED",
                "message": "连接在执行途中断开（通常是桌面端正在重启或网络切换）。",
                "action": "重跑一次本命令即可；签到和领取都是幂等的，不会重复扣发。",
                "detail": s}
    if "请在 WorkBuddy 中登录" in s:
        return {"code": "E_NOT_LOGGED_IN",
                "message": "WorkBuddy 桌面端尚未登录。",
                "action": "打开 WorkBuddy 完成登录后重试。",
                "detail": s}
    return {"code": "E_UNEXPECTED",
            "message": "发生未知错误。",
            "action": "先跑 selftest 自检；若仍失败，带着下面的 detail 反馈。",
            "detail": s}


def main():
    ap = argparse.ArgumentParser(description="WorkBuddy 签到 & 猫猫旅行助手")
    ap.add_argument("cmd", choices=["status", "checkin", "travel", "all", "selftest"])
    ap.add_argument("--location", type=int, default=None,
                    help="派出旅行的地点 ID：1 咖啡馆 / 2 商场店铺 / 3 健身房 / 4 古镇客栈，不指定则随机")
    args = ap.parse_args()
    loc = args.location
    if loc is not None and loc not in (1, 2, 3, 4):
        print(json.dumps({"ok": False,
                          "error": {"code": "E_BAD_LOCATION",
                                    "message": f"--location 只接受 1-4（1 咖啡馆 / 2 商场店铺 / 3 健身房 / 4 古镇客栈），收到的是 {loc}。",
                                    "action": "改成 1-4 之间的整数，或干脆不传（自动随机）。"}},
                         ensure_ascii=False, indent=2))
        sys.exit(2)
    attempts = 0
    while True:
        try:
            with WbipcClient() as c:
                ack = c.handshake()
                if args.cmd == "selftest":
                    out = cmd_selftest(c, ack)
                elif args.cmd == "status":
                    out = cmd_status(c)
                elif args.cmd == "checkin":
                    out = cmd_checkin(c)
                elif args.cmd == "travel":
                    out = cmd_travel(c, loc)
                elif args.cmd == "all":
                    out = {"checkin": cmd_checkin(c), "travel": cmd_travel(c, loc)}
            print(json.dumps(out, ensure_ascii=False, indent=2))
            return
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            attempts += 1
            fe = _friendly_error(e)
            # 瞬时性错误（断线/超时/pipe 暂时不可用）自动重试一次
            transient = fe["code"] in ("E_DISCONNECTED", "E_TIMEOUT", "E_PIPE_GONE")
            if transient and attempts < 2:
                time.sleep(2)
                continue
            print(json.dumps({"ok": False, "error": fe,
                              "hint": "脚本可重复运行，不会重复领奖；" +
                                      ("已自动重试 1 次仍失败。" if transient else "")},
                             ensure_ascii=False, indent=2))
            sys.exit(1)


if __name__ == "__main__":
    main()
"""aiohttp: /health cho UptimeRobot, / để xem trạng thái, /api/deaths cho tracker."""

from __future__ import annotations

import asyncio
import hmac
import html
import logging
import time

from aiohttp import web

from . import __version__
from .event import DeathEvent, PayloadError
from .notify import Delivery, Notifier
from .store import ConfigStore

log = logging.getLogger(__name__)

TOKEN_HEADER = "X-Tracker-Token"
MAX_BODY = 8 * 1024 * 1024


class WebState:
    def __init__(self, *, api_token: str, notifier: Notifier, store: ConfigStore, bot=None) -> None:
        self.api_token = api_token
        self.notifier = notifier
        self.store = store
        self.bot = bot
        self.started_at = time.time()
        self.received = 0
        self.rejected = 0
        self.last_event: DeathEvent | None = None
        self.last_result: Delivery | None = None
        self._lock = asyncio.Lock()

    @property
    def uptime_s(self) -> float:
        return time.time() - self.started_at

    def status(self) -> dict:
        bot_user = getattr(self.bot, "user", None) if self.bot else None
        return {
            "version": __version__,
            "bot": str(bot_user) if bot_user else None,
            "ready": bool(bot_user),
            "guilds": len(getattr(self.bot, "guilds", []) or []) if self.bot else 0,
            "channels": len(self.store.config.channels),
            "paused": self.store.config.paused,
            "received": self.received,
            "rejected": self.rejected,
            "uptime_s": round(self.uptime_s),
            "config_source": self.store.describe_source(),
        }


def _authorised(request: web.Request) -> bool:
    state: WebState = request.app["state"]
    supplied = request.headers.get(TOKEN_HEADER, "")
    if not supplied:
        return False
    return hmac.compare_digest(supplied, state.api_token)


async def handle_health(request: web.Request) -> web.Response:
    return web.Response(text="ok", content_type="text/plain")


async def handle_root(request: web.Request) -> web.Response:
    state: WebState = request.app["state"]
    status = state.status()
    last = state.last_event
    last_line = "—"
    if last is not None:
        last_line = f"#{last.death_no or '?'} · {last.ts_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC"
    rows = "".join(
        f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>" for k, v in status.items()
    )
    page = f"""<!doctype html>
<html lang="vi"><meta charset="utf-8"><title>氣絕錄 · Khí Tuyệt Lục</title>
<style>
 body{{background:#0d0808;color:#e7d5c9;font-family:Georgia,'Times New Roman',serif;margin:0;padding:48px 20px}}
 main{{max-width:640px;margin:0 auto;border:1px solid #3a1010;padding:32px;background:#120a0a}}
 h1{{font-size:26px;letter-spacing:2px;color:#c62c2c;margin:0 0 4px}}
 p.sub{{color:#8c6f63;margin:0 0 24px;font-size:13px;letter-spacing:3px}}
 table{{width:100%;border-collapse:collapse;font-size:14px}}
 th{{text-align:left;color:#8c6f63;font-weight:400;padding:6px 0;width:40%}}
 td{{padding:6px 0;color:#e7d5c9}}
 hr{{border:0;border-top:1px solid #3a1010;margin:24px 0}}
 .seal{{color:#5c1d1d;letter-spacing:6px;font-size:12px}}
</style>
<main>
 <h1>氣絕錄 · Khí Tuyệt Lục</h1>
 <p class="sub">H U Y Ế T &nbsp; T H Ư</p>
 <table>{rows}<tr><th>lần chết gần nhất</th><td>{html.escape(last_line)}</td></tr></table>
 <hr>
 <div class="seal">乂乂乂乂乂乂乂乂乂乂</div>
</main></html>"""
    return web.Response(text=page, content_type="text/html")


async def handle_death(request: web.Request) -> web.Response:
    state: WebState = request.app["state"]
    if not _authorised(request):
        state.rejected += 1
        return web.json_response({"ok": False, "error": "forbidden"}, status=403)

    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001 - body không phải JSON
        state.rejected += 1
        return web.json_response({"ok": False, "error": "bad_payload", "detail": "JSON không hợp lệ"}, status=400)

    try:
        event = DeathEvent.from_payload(payload)
    except PayloadError as exc:
        state.rejected += 1
        return web.json_response({"ok": False, "error": "bad_payload", "detail": str(exc)}, status=400)

    async with state._lock:
        result = await state.notifier.dispatch(event)

    if result.skip_reason == "no_channels":
        state.rejected += 1
        return web.json_response({"ok": False, "error": "no_channels"}, status=503)

    state.received += 1
    state.last_event = event
    state.last_result = result
    log.info("event %s → %s", event.id, result.summary())

    body = {"ok": True, "delivered": result.delivered, "failed": result.failed}
    if result.skip_reason:
        body["skipped"] = result.skip_reason
    if result.errors:
        body["errors"] = result.errors[:5]
    return web.json_response(body)


def build_app(state: WebState) -> web.Application:
    app = web.Application(client_max_size=MAX_BODY)
    app["state"] = state
    app.router.add_get("/", handle_root)
    app.router.add_get("/health", handle_health)
    app.router.add_post("/api/deaths", handle_death)
    return app


async def start_server(state: WebState, port: int, host: str = "0.0.0.0") -> web.AppRunner:
    runner = web.AppRunner(build_app(state), access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    log.info("HTTP nghe trên %s:%s", host, port)
    return runner

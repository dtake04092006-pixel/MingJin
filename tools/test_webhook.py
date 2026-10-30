"""Test HTTP handler bằng aiohttp TestClient (không cần token Discord). Chạy: python tools/test_webhook.py"""

from __future__ import annotations

import asyncio
import base64
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import MINIMAL_PNG, Checker, make_store  # noqa: E402

from aiohttp.test_utils import TestClient, TestServer  # noqa: E402

from khi_tuyet_luc.notify import Delivery  # noqa: E402
from khi_tuyet_luc.web import WebState, build_app  # noqa: E402

TOKEN = "secret-token"
HEADERS = {"X-Tracker-Token": TOKEN}


class FakeDispatcher:
    def __init__(self, result: Delivery | None = None) -> None:
        self.result = result or Delivery(delivered=2)
        self.events: list = []

    async def dispatch(self, event):
        self.events.append(event)
        return self.result


def payload(**overrides) -> dict:
    base = {
        "id": "evt-42",
        "ts_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "ts_local": "2026-10-30 23:22:41",
        "session_id": "s_20261030_231500",
        "death_no": 3,
        "total_deaths": 47,
        "seconds_since_prev_death": 143.2,
        "session_elapsed_s": 902.4,
        "confidence": 1.0,
        "screenshot": "deaths/2026-10-30/x.jpg",
        "screen": {"width": 1920, "height": 1080, "monitor": 0, "hdr": False},
        "capture_backend": "dxgi",
        "tracker_version": "0.1.0",
    }
    base.update(overrides)
    return base


async def exercise() -> Checker:
    check = Checker("Webhook · xác thực, parse, phản hồi")

    dispatcher = FakeDispatcher()
    store = make_store(Path(__import__("tempfile").mkdtemp(prefix="mt_web_")))
    state = WebState(api_token=TOKEN, notifier=dispatcher, store=store, bot=None)

    async with TestClient(TestServer(build_app(state))) as client:
        # /health
        response = await client.get("/health")
        check.eq("GET /health → 200", response.status, 200)
        check.eq("GET /health body", (await response.text()).strip(), "ok")

        # /
        response = await client.get("/")
        body = await response.text()
        check.eq("GET / → 200", response.status, 200)
        check.ok("trang chủ có tên bot", "Khí Tuyệt Lục" in body)
        check.ok("trang chủ không lộ token", TOKEN not in body)

        # thiếu token
        response = await client.post("/api/deaths", json=payload())
        check.eq("thiếu token → 403", response.status, 403)
        check.eq("403 body", (await response.json())["error"], "forbidden")

        # token sai
        response = await client.post("/api/deaths", json=payload(), headers={"X-Tracker-Token": "sai"})
        check.eq("token sai → 403", response.status, 403)

        # JSON hỏng
        response = await client.post("/api/deaths", data=b"{not json", headers=HEADERS)
        check.eq("JSON hỏng → 400", response.status, 400)
        check.eq("400 error", (await response.json())["error"], "bad_payload")

        # thiếu id
        bad = payload()
        bad.pop("id")
        response = await client.post("/api/deaths", json=bad, headers=HEADERS)
        check.eq("thiếu id → 400", response.status, 400)

        # base64 hỏng
        response = await client.post("/api/deaths", json=payload(screenshot_b64="!!!khong-phai-base64!!!"), headers=HEADERS)
        check.eq("base64 hỏng → 400", response.status, 400)

        # ảnh không phải JPEG/PNG
        response = await client.post(
            "/api/deaths", json=payload(screenshot_b64=base64.b64encode(b"GIF89a....").decode()), headers=HEADERS
        )
        check.eq("ảnh lạ → 400", response.status, 400)

        # hợp lệ, không ảnh
        response = await client.post("/api/deaths", json=payload(), headers=HEADERS)
        body = await response.json()
        check.eq("hợp lệ → 200", response.status, 200)
        check.eq("delivered = 2", body["delivered"], 2)
        check.eq("gọi dispatcher 1 lần", len(dispatcher.events), 1)
        event = dispatcher.events[0]
        check.eq("death_no parse", event.death_no, 3)
        check.eq("total parse", event.total_deaths, 47)
        check.eq("backend parse", event.backend, "dxgi")
        check.ok("không có ảnh", not event.has_image)

        # hợp lệ, có ảnh base64
        encoded = base64.b64encode(MINIMAL_PNG).decode()
        response = await client.post(
            "/api/deaths",
            json=payload(id="evt-43", screenshot_b64=encoded, screenshot_mime="image/png"),
            headers=HEADERS,
        )
        check.eq("có ảnh → 200", response.status, 200)
        check.eq("ảnh được decode", dispatcher.events[1].image, MINIMAL_PNG)
        check.eq("mime dò được", dispatcher.events[1].image_mime, "image/png")

        # chưa cấu hình kênh → 503 để tracker giữ lại
        dispatcher.result = Delivery(skip_reason="no_channels")
        response = await client.post("/api/deaths", json=payload(id="evt-44"), headers=HEADERS)
        check.eq("no_channels → 503", response.status, 503)
        check.eq("503 error", (await response.json())["error"], "no_channels")

        # trùng event
        dispatcher.result = Delivery(skip_reason="duplicate")
        response = await client.post("/api/deaths", json=payload(id="evt-44"), headers=HEADERS)
        body = await response.json()
        check.eq("duplicate → 200", response.status, 200)
        check.eq("duplicate skipped", body.get("skipped"), "duplicate")

        # kênh lỗi một phần
        dispatcher.result = Delivery(delivered=1, failed=1, errors=["111: thiếu quyền"])
        response = await client.post("/api/deaths", json=payload(id="evt-45"), headers=HEADERS)
        body = await response.json()
        check.eq("lỗi một phần → vẫn 200", response.status, 200)
        check.eq("failed = 1", body["failed"], 1)
        check.eq("errors trả về", body["errors"][0], "111: thiếu quyền")

    check.eq("đếm received", state.received, 4)
    check.ok("đếm rejected", state.rejected >= 6, str(state.rejected))
    check.eq("lưu event cuối", state.last_event.id, "evt-45")
    return check


def main() -> int:
    return asyncio.run(exercise()).summary()


if __name__ == "__main__":
    raise SystemExit(main())

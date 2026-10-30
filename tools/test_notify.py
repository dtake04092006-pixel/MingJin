"""Test Notifier: nhiều kênh, chế độ ảnh, chống trùng, liên tử. Chạy: python tools/test_notify.py"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import discord  # noqa: E402

from _common import Checker, FakeBot, FakeChannel, make_event, make_store  # noqa: E402

from khi_tuyet_luc.notify import Notifier  # noqa: E402


def build(channel_specs, **store_kwargs):
    channels = [FakeChannel(cid, fail=fail) for cid, fail in channel_specs]
    bot = FakeBot(channels)
    store = make_store(Path(tempfile.mkdtemp(prefix="mt_notify_")), **store_kwargs)
    return bot, store, channels, Notifier(bot, store)


def main() -> int:
    check = Checker("Notifier · phân phối nhiều kênh")

    # 1. hai kênh, một bật ảnh một tắt
    bot, store, channels, notifier = build([(111, None), (222, None)])
    store.add_channel(111, True)
    store.add_channel(222, False)
    result = asyncio.run(notifier.dispatch(make_event()))
    check.eq("gửi đủ 2 kênh", result.delivered, 2)
    check.eq("không lỗi", result.failed, 0)
    check.eq("kênh 111 có ảnh", len(channels[0].files), 2)
    check.eq("kênh 222 không gửi ảnh chụp", len(channels[1].files), 1)
    check.eq("kênh 222 vẫn có embed", len(channels[1].embeds), 1)
    check.ok("ảnh gửi kèm embed cùng message", bool(channels[0].embeds) and bool(channels[0].files))
    names = [file.filename for file in channels[0].files]
    check.eq("file đầu là số đếm", names[0], "ktl-count.png")
    check.eq("file sau là ảnh chụp", names[1].startswith("khi-tuyet-luc-"), True)
    check.eq("thumbnail trỏ tới số đếm", channels[0].embeds[0].to_dict()["thumbnail"]["url"], "attachment://ktl-count.png")
    check.ok(
        "kênh 222 vẫn có số đếm dù tắt ảnh",
        [file.filename for file in channels[1].files] == ["ktl-count.png"],
        str([file.filename for file in channels[1].files]),
    )

    # 2. event không có ảnh → chỉ embed + số đếm
    bot, store, channels, notifier = build([(333, None)])
    store.add_channel(333, True)
    asyncio.run(notifier.dispatch(make_event(event_id="e2", with_image=False)))
    check.eq("event không ảnh → chỉ còn số đếm", len(channels[0].files), 1)
    check.eq("event không ảnh → 1 embed", len(channels[0].embeds), 1)

    # 3. chống trùng id
    bot, store, channels, notifier = build([(444, None)])
    store.add_channel(444, None)
    first = asyncio.run(notifier.dispatch(make_event(event_id="dup")))
    second = asyncio.run(notifier.dispatch(make_event(event_id="dup")))
    check.eq("lần đầu gửi", first.delivered, 1)
    check.eq("lần hai bị chặn", second.skip_reason, "duplicate")
    check.eq("chỉ gửi 1 message", len(channels[0].sent), 1)

    # 4. tạm ngưng
    bot, store, channels, notifier = build([(555, None)])
    store.add_channel(555, None)
    store.set_paused(True)
    result = asyncio.run(notifier.dispatch(make_event(event_id="e4")))
    check.eq("pause → skipped", result.skip_reason, "paused")
    check.eq("pause → không gửi", len(channels[0].sent), 0)

    # 5. chưa có kênh
    bot, store, channels, notifier = build([(666, None)])
    result = asyncio.run(notifier.dispatch(make_event(event_id="e5")))
    check.eq("chưa cấu hình → no_channels", result.skip_reason, "no_channels")

    # 6. liên tử
    bot, store, channels, notifier = build([(777, None)])
    store.add_channel(777, None)
    asyncio.run(notifier.dispatch(make_event(event_id="s1", since_prev=200)))
    check.eq("lần đầu streak = 1", store.config.streak, 1)
    asyncio.run(notifier.dispatch(make_event(event_id="s2", since_prev=20)))
    check.eq("chết trong 90s → streak 2", store.config.streak, 2)
    asyncio.run(notifier.dispatch(make_event(event_id="s3", since_prev=15)))
    check.eq("tiếp tục → streak 3", store.config.streak, 3)
    asyncio.run(notifier.dispatch(make_event(event_id="s4", since_prev=600)))
    check.eq("cách xa → reset 1", store.config.streak, 1)
    check.eq("streak ≥ 3 có field liên tử", channels[0].embeds[2].to_dict()["fields"][4]["value"], "3 liên")

    # 7. một kênh lỗi quyền, kênh khác vẫn nhận
    forbidden = discord.Forbidden(type("R", (), {"status": 403, "reason": "Forbidden"})(), "missing access")
    bot, store, channels, notifier = build([(888, forbidden), (999, None)])
    store.add_channel(888, None)
    store.add_channel(999, None)
    result = asyncio.run(notifier.dispatch(make_event(event_id="e7")))
    check.eq("kênh lỗi đếm failed", result.failed, 1)
    check.eq("kênh còn lại vẫn nhận", result.delivered, 1)
    check.ok("có thông báo lỗi", any("888" in e for e in result.errors), str(result.errors))
    check.eq("kênh 999 nhận 1", len(channels[1].sent), 1)

    # 8. kênh không tồn tại
    bot, store, channels, notifier = build([(1010, None)])
    store.add_channel(1010, None)
    store.config.channels["2020"] = {"image": None}  # kênh bot không thấy
    result = asyncio.run(notifier.dispatch(make_event(event_id="e8")))
    check.eq("kênh lạ → failed", result.failed, 1)
    check.eq("kênh thật vẫn nhận", result.delivered, 1)

    # 9. thống kê được ghi lại
    check.eq("stats.received", store.config.stats.get("received"), 1)
    check.eq("stats.last_id", store.config.stats.get("last_id"), "e8")

    # 10. gửi thử
    bot, store, channels, notifier = build([(3030, None)])
    store.add_channel(3030, True)
    error = asyncio.run(notifier.send_test(3030))
    check.ok("send_test không lỗi", error is None, str(error))
    check.eq("send_test tạo 1 message", len(channels[0].sent), 1)
    check.ok("send_test không đổi stats", not store.config.stats.get("received"), str(store.config.stats))
    test_embed = channels[0].embeds[0].to_dict()
    check.ok(
        "send_test trông y như thật (không lộ chữ 'thử')",
        "thử" not in test_embed["footer"]["text"] and "test" not in test_embed["footer"]["text"].lower(),
        test_embed["footer"]["text"],
    )

    # 11. tổng kiếp tự tăng, cảnh giới đổi theo số của bot
    bot, store, channels, notifier = build([(4040, None)])
    store.add_channel(4040, None)
    store.set_deaths(39)
    asyncio.run(notifier.dispatch(make_event(event_id="r1", total=1)))
    check.eq("39 → lần chết thứ 40", store.config.deaths_total, 40)
    root = channels[0].embeds[0].to_dict()
    check.eq("embed ghi tổng kiếp #40", root["fields"][1]["value"], "#40")
    check.ok("40 mạng vẫn 未染", "未染" in root["title"], root["title"])
    store.set_deaths(49)
    asyncio.run(notifier.dispatch(make_event(event_id="r2", total=1)))
    top = channels[0].embeds[1].to_dict()
    check.eq("chết lần 50 → màu 染血", top["color"], 0x8A5A2B)
    check.ok("title có 染血", "染血" in top["title"], top["title"])
    check.eq("deaths_total = 50", store.config.deaths_total, 50)

    # 12. người chơi hiện ở author: ảnh tươi từ cache, fallback ảnh đã lưu
    bot, store, channels, notifier = build([(5050, None)])
    store.add_channel(5050, None)
    member = type(
        "U",
        (),
        {
            "id": 7,
            "name": "tanya",
            "display_name": "Tanya",
            "display_avatar": type("A", (), {"url": "https://cdn/luu.png"})(),
        },
    )()
    store.set_player(member)
    asyncio.run(notifier.dispatch(make_event(event_id="p1")))
    author = channels[0].embeds[0].to_dict()["author"]
    check.eq("author name = người chơi", author["name"], "Tanya")
    check.eq("không có cache → avatar đã lưu", author["icon_url"], "https://cdn/luu.png")
    bot.users[7] = type("U2", (), {"display_avatar": type("A", (), {"url": "https://cdn/tuoi.png"})()})()
    asyncio.run(notifier.dispatch(make_event(event_id="p2")))
    check.eq("có cache → avatar tươi", channels[0].embeds[1].to_dict()["author"]["icon_url"], "https://cdn/tuoi.png")
    store.set_player(None)
    asyncio.run(notifier.dispatch(make_event(event_id="p3")))
    check.eq("xoá người chơi → tên bot", channels[0].embeds[2].to_dict()["author"]["name"], "Khí Tuyệt Lục")
    check.ok("set_player(None) xoá sạch", store.config.player is None, str(store.config.player))

    # 13. xem trước: đúng embed sẽ hiện ở lần chết kế tiếp, không gửi gì
    bot, store, channels, notifier = build([(6060, None)])
    store.add_channel(6060, None)
    store.set_deaths(39)
    store.set_player(member)
    bot.users[7] = type("U3", (), {"display_avatar": type("A", (), {"url": "https://cdn/tuoi.png"})()})()
    preview, preview_files = notifier.build_preview()
    root = preview.to_dict()
    check.eq("preview: tổng kiếp = deaths_total + 1", root["fields"][1]["value"], "#40")
    check.ok("preview: vẫn 未染 ở 39 mạng", "未染" in root["title"], root["title"])
    check.eq("preview: author = người chơi", root["author"]["name"], "Tanya")
    check.eq("preview: chỉ có số đếm, không ảnh chụp", [f.filename for f in preview_files], ["ktl-count.png"])
    check.eq("preview: số đếm đúng màu bậc 未染", root["thumbnail"]["url"], "attachment://ktl-count.png")
    check.eq("preview: màu thanh = 未染", root["color"], 0x2E8B6E)
    check.ok("preview: không gửi gì lên kênh", channels[0].sent == [], str(len(channels[0].sent)))
    check.eq("preview: không đụng tổng kiếp thật", store.config.deaths_total, 39)
    check.ok(
        "preview: footer là hiện trạng, không đánh dấu thử",
        "thử" not in root["footer"]["text"] and "test" not in root["footer"]["text"].lower(),
        root["footer"]["text"],
    )

    return check.summary()


if __name__ == "__main__":
    raise SystemExit(main())

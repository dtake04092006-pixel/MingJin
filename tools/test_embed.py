"""Test bộ dựng embed + kho chữ + lưu cấu hình. Chạy: python tools/test_embed.py"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Checker, make_event  # noqa: E402

from khi_tuyet_luc import texts  # noqa: E402
from khi_tuyet_luc.embed import MAX_TOTAL, build_embed, embed_length, validate_embed  # noqa: E402
from khi_tuyet_luc.store import MARKER, BotConfig, parse_message, render_message  # noqa: E402

FIELD_ORDER = ["血 · Tử kỳ", "命 · Tổng kiếp", "時 · Cách kiếp trước", "境 · Cảnh giới", "◈ Phiên", "連 · Liên tử"]


def main() -> int:
    check = Checker("Embed · nội dung và giới hạn")

    # 1. lần chết đầu tiên
    event = make_event(death_no=1, total=1, since_prev=None)
    embed = build_embed(event, verse=texts.VERSES[0])
    data = embed.to_dict()
    check.ok("title chứa 第一", "第一" in data["title"], data["title"])
    check.eq("màu cảnh giới 未染", data["color"], 0x4C7A6B)
    check.ok("title có cảnh giới 未染", "未染" in data["title"], data["title"])
    check.eq("thứ tự 6 field", [f["name"] for f in data["fields"]], FIELD_ORDER)
    check.eq("cách kiếp trước = —", data["fields"][2]["value"], "—")
    check.eq("tử kỳ = #1", data["fields"][0]["value"], "#1")

    # 2. 47 mạng → vẫn 未染, còn 3 mạng tới 染血
    embed = build_embed(make_event(death_no=3, total=47), verse=texts.VERSES[1])
    data = embed.to_dict()
    check.ok("title có 第三", "第三" in data["title"], data["title"])
    check.eq("màu 47 mạng = 未染", data["color"], 0x4C7A6B)
    check.ok("field cảnh giới có 未染 · Vô Nhiễm", "未染 · Vô Nhiễm" in data["fields"][3]["value"], data["fields"][3]["value"])
    check.ok("field cảnh giới có tiến độ 47/50", "47/50" in data["fields"][3]["value"], data["fields"][3]["value"])
    check.ok("còn 3 mạng tới 染血", "còn 3 mạng → 染血" in data["fields"][3]["value"], data["fields"][3]["value"])

    # 3. không có ảnh
    embed = build_embed(make_event(with_image=False), verse=texts.VERSES[2])
    check.ok("footer ghi vô ảnh", "vô ảnh" in embed.to_dict()["footer"]["text"])

    # 4. thông báo thử
    embed = build_embed(make_event(test=True), verse=texts.VERSES[3], test=True)
    check.ok("footer ghi thông báo thử", "thông báo thử" in embed.to_dict()["footer"]["text"])

    # 5. quá 10 lần chết → dùng số thường
    embed = build_embed(make_event(death_no=12, total=12), verse=texts.VERSES[4])
    check.ok("death 12 → '12 Chuyển'", "12 Chuyển" in embed.to_dict()["title"], embed.to_dict()["title"])

    # 6. liên tử
    embed = build_embed(make_event(), verse=texts.VERSES[5], streak=5, streak_line=texts.STREAK_VERSES[0])
    data = embed.to_dict()
    check.eq("màu khi liên tử 5", data["color"], 0xE01B1B)
    check.ok("title có 五連", "五連" in data["title"], data["title"])
    check.eq("field liên tử", data["fields"][5]["value"], "5 liên")
    check.ok("description có câu liên tử", texts.STREAK_VERSES[0] in data["description"])

    # 7. số liệu cực đại vẫn không vượt giới hạn
    huge = make_event(death_no=999999, total=10**9)
    huge.session_id = "s_" + "x" * 300
    huge.confidence = 0.4213
    huge.screen_w, huge.screen_h = 7680, 4320
    embed = build_embed(huge, verse=texts.VERSES[6], streak=42, streak_line=texts.STREAK_VERSES[1])
    try:
        validate_embed(embed)
        check.ok("embed cực đại hợp lệ", True)
    except ValueError as exc:
        check.ok("embed cực đại hợp lệ", False, str(exc))
    check.ok(f"tổng ký tự ≤ {MAX_TOTAL}", embed_length(embed) <= MAX_TOTAL, str(embed_length(embed)))
    check.ok(
        "field phiên bị cắt ≤ 1024",
        all(len(f["value"]) <= 1024 for f in embed.to_dict()["fields"]),
    )

    # 8. không crash khi thiếu mọi số liệu
    blank = make_event(death_no=0, total=0, since_prev=None)
    blank.session_id = None
    blank.backend = None
    blank.screen_w = blank.screen_h = None
    blank.confidence = None
    embed = build_embed(blank, verse=texts.VERSES[7])
    check.ok("event trống vẫn dựng được", "Vô danh chuyển" in embed.to_dict()["title"], embed.to_dict()["title"])

    # 9. người chơi: author = tên hiển thị + avatar
    hero = {"id": 42, "name": "Tanya", "avatar": "https://cdn.discord/old.png"}
    embed = build_embed(
        make_event(total=47), verse=texts.VERSES[8], player=hero, player_avatar="https://cdn.discord/fresh.png"
    )
    data = embed.to_dict()
    check.eq("author = tên người chơi", data["author"]["name"], "Tanya")
    check.eq("author icon = avatar tươi", data["author"]["icon_url"], "https://cdn.discord/fresh.png")
    embed = build_embed(make_event(total=47), verse=texts.VERSES[8], player=hero)
    check.eq("không có avatar tươi → ảnh đã lưu", embed.to_dict()["author"]["icon_url"], "https://cdn.discord/old.png")
    embed = build_embed(make_event(total=47), verse=texts.VERSES[8])
    check.eq("chưa gán người chơi → tên bot", embed.to_dict()["author"]["name"], "Khí Tuyệt Lục")

    # 10. tổng kiếp của bot thắng số của tracker
    embed = build_embed(make_event(death_no=3, total=1), verse=texts.VERSES[9], lifetime=520)
    data = embed.to_dict()
    check.eq("lifetime 520 → màu 無間", data["color"], 0xD60000)
    check.eq("field tổng kiếp = #520", data["fields"][1]["value"], "#520")
    check.ok("bậc cuối ghi 'đã tột cùng'", "đã tột cùng" in data["fields"][3]["value"], data["fields"][3]["value"])

    print("\n=== Kho chữ ===")
    check.eq("turn 1", texts.turn_label(1), ("第一", "Nhất"))
    check.eq("turn 10", texts.turn_label(10), ("第十", "Thập"))
    check.eq("turn 11", texts.turn_label(11), ("", "11"))
    check.eq("turn 0", texts.turn_label(0), ("", ""))
    print("\n=== Cảnh giới (50 mạng/bậc, dừng ở 500) ===")
    check.eq("0 mạng → 未染", texts.realm_for(0).cn, "未染")
    check.eq("39 mạng → 未染", texts.realm_for(39).cn, "未染")
    check.eq("49 mạng → 未染", texts.realm_for(49).cn, "未染")
    check.eq("50 mạng → 染血", texts.realm_for(50).cn, "染血")
    check.eq("99 mạng → 染血", texts.realm_for(99).cn, "染血")
    check.eq("250 mạng → 入魔", texts.realm_for(250).cn, "入魔")
    check.eq("499 mạng → 修羅", texts.realm_for(499).cn, "修羅")
    check.eq("500 mạng → 無間", texts.realm_for(500).cn, "無間")
    check.eq("9999 mạng vẫn 無間", texts.realm_for(9999).cn, "無間")
    check.eq("None → 未染", texts.realm_for(None).cn, "未染")
    check.eq("bậc cuối không có bậc kế", texts.next_realm(500), None)
    check.eq("bậc kế của 39 mạng", texts.next_realm(39).cn, "染血")
    check.eq("tiến độ 39 mạng", texts.realm_progress(39), (39, 50))
    check.eq("tiến độ bậc cuối", texts.realm_progress(520), (0, 0))
    check.eq("thời lượng 161s", texts.format_duration(161.4), "2 phút 41 giây")
    check.eq("thời lượng 60s", texts.format_duration(60), "1 phút")
    check.eq("thời lượng 3725s", texts.format_duration(3725), "1 giờ 2 phút")
    check.eq("thời lượng None", texts.format_duration(None), "—")
    check.eq("elapsed 902s", texts.format_elapsed(902.4), "15:02")
    check.eq("elapsed None", texts.format_elapsed(None), "—")

    picker = texts.VersePicker(random.Random(7))
    picks = [picker.pick() for _ in range(20)]
    check.ok("không lặp câu liền trước", all(a != b for a, b in zip(picks, picks[1:])))
    check.ok("luôn nằm trong kho", all(p in texts.VERSES for p in picks))

    print("\n=== Lưu cấu hình ===")
    cfg = BotConfig(default_image=True)
    cfg.channels["123"] = {"image": None}
    cfg.channels["456"] = {"image": False}
    payload = json.loads(json.dumps(cfg.to_dict()))
    restored = BotConfig.from_dict(payload)
    check.eq("giữ số kênh", len(restored.channels), 2)
    check.eq("kênh 123 theo mặc định", restored.image_for(123), True)
    check.eq("kênh 456 ép tắt ảnh", restored.image_for(456), False)
    check.eq("kênh lạ theo mặc định", restored.image_for(999), True)
    restored.default_image = False
    check.eq("đổi mặc định → kênh 123 tắt", restored.image_for(123), False)
    check.eq("kênh 456 vẫn tắt", restored.image_for(456), False)
    check.ok("serialize kênh thành chuỗi", all(isinstance(k, str) for k in restored.to_dict()["channels"]))

    message = render_message(restored)
    check.ok("message có marker", MARKER in message)
    check.ok("message có khối json", "```json" in message)
    parsed = parse_message(message)
    check.ok("parse lại được", parsed is not None)
    if parsed:
        check.eq("parse giữ kênh", len(parsed.channels), 2)
        check.eq("parse giữ mặc định", parsed.default_image, False)
    check.ok("message không marker → None", parse_message("hello") is None)
    check.ok("message marker hỏng json → None", parse_message(MARKER + "\n```json\n{oops}\n```") is None)

    bad = BotConfig.from_dict({"channels": {"abc": {}, "789": "rác"}, "streak": -5})
    check.eq("bỏ kênh id rác", list(bad.channels), ["789"])
    check.eq("streak âm → 1", bad.streak, 1)

    return check.summary()


if __name__ == "__main__":
    raise SystemExit(main())

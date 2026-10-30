"""Test bộ dựng embed + kho chữ + lưu cấu hình. Chạy: python tools/test_embed.py"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import Checker, make_event  # noqa: E402

from khi_tuyet_luc import badge as badge_art  # noqa: E402
from khi_tuyet_luc import texts  # noqa: E402
from khi_tuyet_luc.badge import lit_colour, render_count_png  # noqa: E402
from khi_tuyet_luc.embed import MAX_TOTAL, build_embed, embed_length, validate_embed  # noqa: E402
from khi_tuyet_luc.event import DeathEvent  # noqa: E402
from khi_tuyet_luc.store import MARKER, BotConfig, parse_message, render_message  # noqa: E402

FIELD_ORDER = ["血 · Tử kỳ", "命 · Tổng kiếp", "時 · Cách kiếp", "境 · Cảnh giới", "連 · Liên tử", "◈ Phiên"]


def main() -> int:
    check = Checker("Embed · nội dung và giới hạn")

    # 1. lần chết đầu tiên
    event = make_event(death_no=1, total=1, since_prev=None)
    embed = build_embed(event, verse=texts.VERSES[0])
    data = embed.to_dict()
    check.ok("title chứa 第一", "第一" in data["title"], data["title"])
    check.eq("màu cảnh giới 未染", data["color"], 0x2E8B6E)
    check.ok("title có cảnh giới 未染", "未染" in data["title"], data["title"])
    check.eq("thứ tự 6 field", [f["name"] for f in data["fields"]], FIELD_ORDER)
    check.eq("cách kiếp trước = —", data["fields"][2]["value"], "—")
    check.eq("tử kỳ = #1", data["fields"][0]["value"], "#1")

    # 2. 47 mạng → vẫn 未染; field cảnh giới chỉ có nhãn bậc, một dòng
    embed = build_embed(make_event(death_no=3, total=47), verse=texts.VERSES[1])
    data = embed.to_dict()
    check.ok("title chứa 第四十七", "第四十七" in data["title"], data["title"])
    check.ok("title không dùng tử kỳ 第三", "第三 ·" not in data["title"], data["title"])
    check.eq("màu 47 mạng = 未染", data["color"], 0x2E8B6E)
    check.eq("field cảnh giới = nhãn bậc", data["fields"][3]["value"], "未染 · Vô Nhiễm")
    check.ok("field cảnh giới KHÔNG có tiến độ 47/50", "47/50" not in data["fields"][3]["value"], data["fields"][3]["value"])
    check.ok("trạng thái bậc nằm ở mô tả (in nghiêng)", "*tay còn sạch*" in data["description"], data["description"])
    check.ok("mọi field 1 dòng → lưới 3×2", all("\n" not in f["value"] for f in data["fields"]), str(data["fields"]))

    # 3. không có ảnh
    embed = build_embed(make_event(with_image=False), verse=texts.VERSES[2])
    check.ok("footer ghi vô ảnh", "vô ảnh" in embed.to_dict()["footer"]["text"])

    # 4. bản mẫu (dùng cho /ktl test và /ktl preview) trông y như thật
    embed = build_embed(DeathEvent.sample(death_no=3, total=47), verse=texts.VERSES[3])
    data = embed.to_dict()
    footer = data["footer"]["text"]
    check.ok("footer không ghi 'thông báo thử'", "thử" not in footer, footer)
    check.ok("footer mẫu không có chữ 'test'", "test" not in footer.lower(), footer)
    check.ok("phiên chỉ còn thời lượng, không lộ id thô", data["fields"][5]["value"] == "15:02", data["fields"][5]["value"])

    # 5. quá 10 lần chết vẫn đánh vần được (không rơi về số Ả Rập)
    embed = build_embed(make_event(death_no=12, total=12), verse=texts.VERSES[4])
    check.ok("death 12 → '第十二 · Thập Nhị'", "第十二 · Thập Nhị Chuyển" in embed.to_dict()["title"], embed.to_dict()["title"])

    # 6. liên tử
    embed = build_embed(make_event(), verse=texts.VERSES[5], streak=5, streak_line=texts.STREAK_VERSES[0])
    data = embed.to_dict()
    check.eq("màu khi liên tử 5", data["color"], 0xE01B1B)
    check.ok("title có 五連", "五連" in data["title"], data["title"])
    check.eq("field liên tử", data["fields"][4]["value"], "5 liên")
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
    embed = build_embed(make_event(death_no=3, total=1), verse=texts.VERSES[9], lifetime=700)
    data = embed.to_dict()
    check.eq("lifetime 700 → màu 無間", data["color"], 0x1E0A11)
    check.eq("field tổng kiếp = #700", data["fields"][1]["value"], "#700")
    check.ok("title theo tổng kiếp: 第七百", "第七百" in data["title"], data["title"])
    check.ok("title KHÔNG lấy tử kỳ 第三", "第三" not in data["title"], data["title"])
    check.eq("field tử kỳ vẫn của tracker = #3", data["fields"][0]["value"], "#3")
    check.ok("title đọc được âm Việt", "Thất Bách Chuyển" in data["title"], data["title"])
    check.eq("bậc cuối vẫn một dòng", len(data["fields"][3]["value"].split("\n")), 1)

    print("\n=== Kho chữ ===")
    check.eq("turn 0", texts.turn_label(0), ("", ""))
    check.eq("turn 1", texts.turn_label(1), ("第一", "Nhất"))
    check.eq("turn 3", texts.turn_label(3), ("第三", "Tam"))
    check.eq("turn 10", texts.turn_label(10), ("第十", "Thập"))
    check.eq("turn 11", texts.turn_label(11), ("第十一", "Thập Nhất"))
    check.eq("turn 20", texts.turn_label(20), ("第二十", "Nhị Thập"))
    check.eq("turn 47", texts.turn_label(47), ("第四十七", "Tứ Thập Thất"))
    check.eq("turn 100", texts.turn_label(100), ("第一百", "Nhất Bách"))
    check.eq("turn 105 → chèn 零", texts.turn_label(105), ("第一百零五", "Nhất Bách Linh Ngũ"))
    check.eq("turn 110 → 一百一十", texts.turn_label(110), ("第一百一十", "Nhất Bách Nhất Thập"))
    check.eq("turn 700", texts.turn_label(700), ("第七百", "Thất Bách"))
    check.eq("turn 9999", texts.turn_label(9999), ("第九千九百九十九", "Cửu Thiên Cửu Bách Cửu Thập Cửu"))
    check.eq("turn quá 9999 → chỉ ghi số", texts.turn_label(10000), ("", "10000"))
    print("\n=== Cảnh giới (50 mạng/bậc, 15 bậc, dừng ở 700) ===")
    check.eq("0 mạng → 未染", texts.realm_for(0).cn, "未染")
    check.eq("39 mạng → 未染", texts.realm_for(39).cn, "未染")
    check.eq("49 mạng → 未染", texts.realm_for(49).cn, "未染")
    check.eq("50 mạng → 染血", texts.realm_for(50).cn, "染血")
    check.eq("99 mạng → 染血", texts.realm_for(99).cn, "染血")
    check.eq("250 mạng → 入魔", texts.realm_for(250).cn, "入魔")
    check.eq("450 mạng → 黃泉", texts.realm_for(450).cn, "黃泉")
    check.eq("499 mạng → 黃泉", texts.realm_for(499).cn, "黃泉")
    check.eq("699 mạng → 阿鼻", texts.realm_for(699).cn, "阿鼻")
    check.eq("700 mạng → 無間", texts.realm_for(700).cn, "無間")
    check.eq("9999 mạng vẫn 無間", texts.realm_for(9999).cn, "無間")
    check.eq("None → 未染", texts.realm_for(None).cn, "未染")
    check.eq("đúng 15 bậc", len(texts.REALMS), 15)
    check.eq("REALM_MAX khớp bậc cuối", texts.REALM_MAX, 700)
    check.eq("bậc cuối không có bậc kế", texts.next_realm(700), None)
    check.eq("bậc kế của 39 mạng", texts.next_realm(39).cn, "染血")

    def _lum(colour: int) -> float:
        return 0.2126 * ((colour >> 16) & 255) + 0.7152 * ((colour >> 8) & 255) + 0.0722 * (colour & 255)

    ladder = [realm.colour for realm in texts.REALMS]
    check.ok(
        "màu tối dần theo bậc",
        all(_lum(a) > _lum(b) for a, b in zip(ladder, ladder[1:])),
        str([f"#{c:06X}" for c in ladder]),
    )
    check.ok("bậc cuối gần đen", _lum(ladder[-1]) < 30, str(_lum(ladder[-1])))
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

    print("\n=== Chữ ngắn gọn ===")
    longest_verse = max(texts.VERSES, key=len)
    longest_streak = max(texts.STREAK_VERSES, key=len)
    longest_status = max((realm.status for realm in texts.REALMS), key=len)
    check.ok("câu thơ một dòng", all("\n" not in v for v in texts.VERSES), repr(longest_verse))
    check.ok("câu thơ ≤ 52 ký tự", len(longest_verse) <= 52, f"{len(longest_verse)}: {longest_verse}")
    check.ok("câu liên tử ≤ 40 ký tự", len(longest_streak) <= 40, f"{len(longest_streak)}: {longest_streak}")
    check.ok("trạng thái bậc ≤ 26 ký tự", len(longest_status) <= 26, f"{len(longest_status)}: {longest_status}")

    print("\n=== Ảnh số đếm ở góc phải ===")
    badge = render_count_png(52, 0x9F632E, 1, "血")
    check.eq("52 kiếp cùng màu 染血 → PNG", badge[:4], b"\x89PNG")
    check.ok("ảnh số đếm có nội dung thật", len(badge) > 2000, str(len(badge)))
    check.ok(
        "số đếm đổi theo bậc (màu + vết máu)",
        badge != render_count_png(52, 0x1E0A11, 14, "無"),
        "hai bậc phải ra hai ảnh khác nhau",
    )
    check.ok(
        "cùng số, bậc cao hơn → vết máu nham nhở hơn",
        render_count_png(400, 0x35111B, 8, "川") != render_count_png(400, 0x35111B, 12, "川"),
        "bậc phải ảnh hưởng tới hình",
    )
    check.ok(
        "bậc cuối vẫn đọc được: vết máu sáng hơn màu thanh",
        _lum(sum(c << s for c, s in zip(lit_colour(0x1E0A11), (16, 8, 0)))) > _lum(0x1E0A11),
        str(lit_colour(0x1E0A11)),
    )

    print("\n=== Ký tự lớn chìm theo cảnh giới ===")
    glyphs = [realm.glyph for realm in texts.REALMS]
    check.eq("đủ ký tự cho 15 bậc", len(glyphs), 15)
    check.eq("mỗi bậc một ký tự riêng", len(set(glyphs)), 15)
    check.ok("ký tự đều là chữ Hán đơn", all(len(g) == 1 and ord(g) > 0x4E00 for g in glyphs), " ".join(glyphs))
    missing = [g for g in glyphs if not (badge_art.GLYPH_DIR / f"{ord(g):x}.png").is_file()]
    check.eq("đủ mặt nạ trong glyphs/", missing, [])
    check.ok(
        "ký tự khác → ảnh khác",
        render_count_png(52, 0x9F632E, 1, "淨") != render_count_png(52, 0x9F632E, 1, "無"),
        "phải đổi ký tự theo bậc",
    )
    check.ok("không có ký tự vẫn ra PNG", (render_count_png(52, 0x9F632E, 1) or b"")[:4] == b"\x89PNG")
    check.ok(
        "ký tự lạ → bỏ chữ chìm, vẫn ra PNG",
        render_count_png(52, 0x9F632E, 1, "A") == render_count_png(52, 0x9F632E, 1),
        "thiếu mặt nạ thì ảnh vẫn phải gửi được",
    )
    check.ok(
        "ký tự chìm tối dần theo bậc",
        _lum(sum(c << s for c, s in zip(badge_art._dim(0x9F632E, badge_art.GLYPH_LIGHT), (16, 8, 0))))
        > _lum(
            sum(
                c << s
                for c, s in zip(badge_art._dim(0x9F632E, badge_art.GLYPH_LIGHT - 14 * badge_art.GLYPH_STEP), (16, 8, 0))
            )
        ),
        "bậc cuối phải chìm hơn bậc đầu",
    )

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

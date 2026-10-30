"""In trước nội dung embed ra console để xem nhanh mà không cần Discord.

Chạy: python tools/preview.py            (mặc định: lần chết thứ 3, tổng 47)
      python tools/preview.py 12 120     (lần chết thứ 12, tổng 120 → 傷痕)
      python tools/preview.py 3 520      (tổng 520 → 無間)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import make_event  # noqa: E402

from khi_tuyet_luc import texts  # noqa: E402
from khi_tuyet_luc.badge import render_count_png  # noqa: E402
from khi_tuyet_luc.embed import build_embed  # noqa: E402


def wrap(text: str, width: int) -> list[str]:
    out: list[str] = []
    for raw_line in text.splitlines():
        line = ""
        for word in raw_line.split(" "):
            candidate = f"{line} {word}".strip()
            if len(candidate) > width and line:
                out.append(line)
                line = word
            else:
                line = candidate
        out.append(line)
    return out


def main() -> int:
    death_no = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    total = int(sys.argv[2]) if len(sys.argv) > 2 else 47
    streak = int(sys.argv[3]) if len(sys.argv) > 3 else 1

    event = make_event(death_no=death_no, total=total)
    hero = {"id": 1, "name": "Tanya · người chơi", "avatar": "https://cdn.discord/avatar.png"}
    embed = build_embed(
        event,
        verse=texts.VERSES[1],
        streak=streak,
        streak_line=texts.STREAK_VERSES[0] if streak >= 3 else None,
        lifetime=total,
        player=hero,
    )
    data = embed.to_dict()
    width = 62
    badge = render_count_png(total, int(data["color"])) or b""
    corner = f"[ số ở góc phải: {total} · ảnh {len(badge)} byte ]"

    print("\n┌" + "─" * (width + 2) + "┐")
    print("│ [ ảnh chụp khoảnh khắc TRƯỚC khi chết — attachment ]".ljust(width + 3) + "│")
    print("├" + "─" * (width + 2) + "┤")
    print("│ " + data["author"]["name"].ljust(width + 1) + "│")
    print("│ " + data["title"].ljust(width + 1) + "│")
    print("│ " + ("màu #%06X" % data["color"]).ljust(width + 1) + "│")
    print("│ " + corner.rjust(width + 1) + "│")
    print("│ " + " " * (width + 1) + "│")
    for line in wrap(data["description"], width):
        print("│ " + line.ljust(width + 1) + "│")
    print("│ " + " " * (width + 1) + "│")
    fields = data["fields"]
    for start in range(0, len(fields), 3):
        row = fields[start : start + 3]
        print("│ " + "".join(f["name"].ljust(21) for f in row).ljust(width + 1) + "│")
        depth = max(len(f["value"].splitlines()) for f in row)
        for index in range(depth):
            cells = []
            for field in row:
                lines = field["value"].splitlines()
                cells.append(lines[index][:20].ljust(21) if index < len(lines) else " " * 21)
            print("│ " + "".join(cells).ljust(width + 1) + "│")
        print("│ " + " " * (width + 1) + "│")
    print("│ " + data["footer"]["text"].ljust(width + 1) + "│")
    print("└" + "─" * (width + 2) + "┘\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

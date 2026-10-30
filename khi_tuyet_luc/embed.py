"""Dựng embed kiếm hiệp / nhập ma cho mỗi lần chết.

Quy ước: ảnh KHÔNG nhét vào embed (`set_image`) — ảnh gửi dạng attachment
thường để Discord render phía trên embed.
"""

from __future__ import annotations

import discord

from . import texts
from .event import DeathEvent

MAX_TITLE = 256
MAX_DESCRIPTION = 4096
MAX_FIELDS = 25
MAX_FIELD_NAME = 256
MAX_FIELD_VALUE = 1024
MAX_FOOTER = 2048
MAX_TOTAL = 6000

STREAK_COLOUR_OVERRIDE = 0xE01B1B
STREAK_COLOUR_THRESHOLD = 5


def _clip(text: str, limit: int) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


def embed_length(embed: discord.Embed) -> int:
    data = embed.to_dict()
    total = len(data.get("title", "")) + len(data.get("description", ""))
    total += len(data.get("author", {}).get("name", ""))
    total += len(data.get("footer", {}).get("text", ""))
    for field in data.get("fields", []):
        total += len(field.get("name", "")) + len(field.get("value", ""))
    return total


def validate_embed(embed: discord.Embed) -> None:
    """Chặn trước khi gửi: Discord trả 400 nếu vượt giới hạn."""
    data = embed.to_dict()
    problems: list[str] = []
    if len(data.get("title", "")) > MAX_TITLE:
        problems.append("title")
    if len(data.get("description", "")) > MAX_DESCRIPTION:
        problems.append("description")
    if len(data.get("footer", {}).get("text", "")) > MAX_FOOTER:
        problems.append("footer")
    fields = data.get("fields", [])
    if len(fields) > MAX_FIELDS:
        problems.append("fields>25")
    for field in fields:
        if len(field.get("name", "")) > MAX_FIELD_NAME or len(field.get("value", "")) > MAX_FIELD_VALUE:
            problems.append(f"field:{field.get('name', '')[:20]}")
    total = embed_length(embed)
    if total > MAX_TOTAL:
        problems.append(f"total={total}")
    if problems:
        raise ValueError("embed vượt giới hạn Discord: " + ", ".join(problems))


def _title(event: DeathEvent, streak: int, realm: texts.Realm) -> str:
    cn, vi = texts.turn_label(event.death_no)
    if cn:
        turn = f"{cn} · {vi} Chuyển"
    elif vi:
        turn = f"{vi} Chuyển"
    else:
        turn = "Vô danh chuyển"
    return _clip(f"氣絕錄 · {turn} · {realm.cn}{texts.streak_suffix(streak)}", MAX_TITLE)


def _realm_value(total: int) -> str:
    """Chỉ nhãn bậc, gọn một dòng — để 3 cột thẳng hàng nhau."""
    return texts.realm_for(total).label


def _description(verse: str, streak_line: str | None, realm: texts.Realm) -> str:
    """Thơ + nhãn emoji + câu trạng thái in nghiêng của bậc hiện tại."""
    lines = [f"{texts.VERSE_MARK} {verse}"]
    if streak_line:
        lines.append(f"{texts.STREAK_MARK} {streak_line}")
    lines.append(f"*{realm.status}*")
    return _clip("\n".join(lines), MAX_DESCRIPTION)


def _footer_text(event: DeathEvent) -> str:
    """Hiện trạng của lần chết: ảnh, backend, độ phân giải, độ tin cậy.

    Không đánh dấu bản thử — embed thử và embed thật phải giống hệt nhau.
    """
    parts = ["氣絕錄 · đã khắc vào huyết thư"]
    if not event.has_image:
        parts.append("vô ảnh")
    if event.backend:
        parts.append(event.backend)
    if event.screen_w and event.screen_h:
        parts.append(f"{event.screen_w}×{event.screen_h}")
    if event.confidence is not None and event.confidence < 0.99:
        parts.append(f"tin cậy {event.confidence:.0%}")
    return _clip(" · ".join(parts), MAX_FOOTER)


def build_embed(
    event: DeathEvent,
    *,
    verse: str,
    streak: int = 1,
    streak_line: str | None = None,
    lifetime: int | None = None,
    player: dict | None = None,
    player_avatar: str | None = None,
    bot_name: str = "Khí Tuyệt Lục",
    bot_avatar: str | None = None,
) -> discord.Embed:
    total = lifetime if lifetime is not None else (event.total_deaths or 0)
    realm = texts.realm_for(total)
    colour = STREAK_COLOUR_OVERRIDE if streak >= STREAK_COLOUR_THRESHOLD else realm.colour

    embed = discord.Embed(
        title=_title(event, streak, realm),
        description=_description(verse, streak_line, realm),
        colour=discord.Colour(colour),
        timestamp=event.ts_utc,
    )
    if player:
        embed.set_author(name=player.get("name") or bot_name, icon_url=player_avatar or player.get("avatar"))
    else:
        embed.set_author(name=bot_name, icon_url=bot_avatar)

    death_label = f"#{event.death_no}" if event.death_no else "—"
    total_label = f"#{total}" if total else "—"
    # 6 field, cả 6 đều inline và đều một dòng → lưới 3×2 thẳng hàng.
    embed.add_field(name="血 · Tử kỳ", value=death_label, inline=True)
    embed.add_field(name="命 · Tổng kiếp", value=total_label, inline=True)
    embed.add_field(
        name="時 · Cách kiếp",
        value=_clip(texts.format_duration(event.seconds_since_prev), MAX_FIELD_VALUE),
        inline=True,
    )
    embed.add_field(name="境 · Cảnh giới", value=_clip(_realm_value(total), MAX_FIELD_VALUE), inline=True)
    streak_value = f"{streak} liên" if streak >= 2 else "—"
    embed.add_field(name="連 · Liên tử", value=streak_value, inline=True)
    embed.add_field(
        name="◈ Phiên",
        value=_clip(texts.format_elapsed(event.session_elapsed_s), MAX_FIELD_VALUE),
        inline=True,
    )

    embed.set_footer(text=_footer_text(event))
    validate_embed(embed)
    return embed

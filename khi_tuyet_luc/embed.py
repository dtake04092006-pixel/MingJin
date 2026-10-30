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
    """'未染 · Vô Nhiễm' + trạng thái + tiến độ tới bậc kế."""
    realm = texts.realm_for(total)
    lines = [realm.label, realm.status]
    nxt = texts.next_realm(total)
    if nxt is None:
        lines.append(f"{total} · đã tột cùng")
    else:
        _done, mark = texts.realm_progress(total)
        lines.append(f"{total}/{mark} · còn {mark - total} mạng → {nxt.cn}")
    return "\n".join(lines)


def _description(verse: str, streak_line: str | None) -> str:
    lines = [texts.SEAL, verse]
    if streak_line:
        lines.append(streak_line)
    lines.append(texts.SEAL)
    return _clip("\n".join(lines), MAX_DESCRIPTION)


def _footer_text(event: DeathEvent, *, test: bool) -> str:
    parts = ["氣絕錄 · đã khắc vào huyết thư"]
    if test:
        parts.append("thông báo thử")
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
    test: bool = False,
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
        description=_description(verse, streak_line),
        colour=discord.Colour(colour),
        timestamp=event.ts_utc,
    )
    if player:
        embed.set_author(name=player.get("name") or bot_name, icon_url=player_avatar or player.get("avatar"))
    else:
        embed.set_author(name=bot_name, icon_url=bot_avatar)

    death_label = f"#{event.death_no}" if event.death_no else "—"
    total_label = f"#{total}" if total else "—"
    embed.add_field(name="血 · Tử kỳ", value=death_label, inline=True)
    embed.add_field(name="命 · Tổng kiếp", value=total_label, inline=True)
    embed.add_field(
        name="時 · Cách kiếp trước",
        value=_clip(texts.format_duration(event.seconds_since_prev), MAX_FIELD_VALUE),
        inline=True,
    )
    embed.add_field(name="境 · Cảnh giới", value=_clip(_realm_value(total), MAX_FIELD_VALUE), inline=True)
    session = texts.format_elapsed(event.session_elapsed_s)
    if event.session_id and session != "—":
        session_value = f"{_clip(event.session_id, 32)} · {session}"
    else:
        session_value = _clip(event.session_id or session, MAX_FIELD_VALUE)
    embed.add_field(name="◈ Phiên", value=session_value, inline=True)
    streak_value = f"{streak} liên" if streak >= 2 else "—"
    embed.add_field(name="連 · Liên tử", value=streak_value, inline=True)

    embed.set_footer(text=_footer_text(event, test=test))
    validate_embed(embed)
    return embed

"""Gửi thông báo tới các kênh đã cấu hình.

Thứ tự trong message: ảnh (attachment thường) ở trên, embed ở dưới — nên ảnh
KHÔNG được nhét vào embed.
"""

from __future__ import annotations

import io
import logging
from collections import OrderedDict
from dataclasses import dataclass, field

import discord

from . import texts
from .embed import build_embed
from .event import DeathEvent
from .store import ConfigStore

log = logging.getLogger(__name__)

STREAK_WINDOW_S = 90.0
SEEN_CACHE = 500


@dataclass
class Delivery:
    delivered: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)
    skip_reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.delivered > 0 or self.skip_reason in ("duplicate", "paused")

    def summary(self) -> str:
        if self.skip_reason:
            return self.skip_reason
        return f"{self.delivered} kênh, {self.failed} lỗi"


class Notifier:
    def __init__(self, bot: discord.Client, store: ConfigStore, picker: texts.VersePicker | None = None) -> None:
        self._bot = bot
        self._store = store
        self._picker = picker or texts.VersePicker()
        self._seen: OrderedDict[str, None] = OrderedDict()

    # --- idempotency ----------------------------------------------------
    def _remember(self, event_id: str) -> None:
        self._seen[event_id] = None
        while len(self._seen) > SEEN_CACHE:
            self._seen.popitem(last=False)

    # --- streak ---------------------------------------------------------
    def _next_streak(self, event: DeathEvent) -> int:
        previous = max(1, int(self._store.config.streak or 1))
        if event.seconds_since_prev is not None and event.seconds_since_prev <= STREAK_WINDOW_S:
            return previous + 1
        return 1

    # --- người chơi -----------------------------------------------------
    def _player_identity(self, player: dict | None) -> tuple[dict | None, str | None]:
        """(player, avatar tươi). Link CDN có chữ ký nên phải lấy lại từ cache."""
        if not player:
            return None, None
        try:
            user = self._bot.get_user(int(player.get("id") or 0))
        except (TypeError, ValueError):
            user = None
        return player, (user.display_avatar.url if user else None)

    # --- dispatch -------------------------------------------------------
    async def dispatch(self, event: DeathEvent) -> Delivery:
        cfg = self._store.config
        if cfg.paused:
            return Delivery(skip_reason="paused")
        if not cfg.channels:
            return Delivery(skip_reason="no_channels")
        # Chỉ đánh dấu "đã gửi" khi thật sự gửi được, để tracker retry còn cứu được
        if event.id in self._seen:
            log.info("bỏ qua event trùng %s", event.id)
            return Delivery(skip_reason="duplicate")

        streak = self._next_streak(event)
        verse = self._picker.pick()
        streak_line = self._picker.streak_line() if streak >= 3 else None
        # +1 vì lần chết này chưa được note_death() ghi vào tổng kiếp
        lifetime = int(cfg.deaths_total or 0) + 1
        player, player_avatar = self._player_identity(cfg.player)
        result = Delivery()

        for channel_id in cfg.channel_ids():
            with_image = self._store.image_for(channel_id)
            error = await self._send_one(
                channel_id, event, with_image, verse, streak, streak_line, lifetime, player, player_avatar
            )
            if error is None:
                result.delivered += 1
            else:
                result.failed += 1
                result.errors.append(f"{channel_id}: {error}")

        if result.delivered:
            self._remember(event.id)
            self._store.note_death(event.id, event.ts_utc.isoformat(), streak)
        return result

    async def _resolve_channel(self, channel_id: int):
        channel = self._bot.get_channel(channel_id)
        if channel is not None:
            return channel
        try:
            return await self._bot.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None

    async def _send_one(
        self,
        channel_id: int,
        event: DeathEvent,
        with_image: bool,
        verse: str,
        streak: int,
        streak_line: str | None,
        lifetime: int | None = None,
        player: dict | None = None,
        player_avatar: str | None = None,
    ) -> str | None:
        channel = await self._resolve_channel(channel_id)
        if channel is None:
            return "kênh không tồn tại hoặc bot không có quyền xem"

        avatar = None
        if self._bot.user is not None:
            avatar = self._bot.user.display_avatar.url
        try:
            embed = build_embed(
                event,
                verse=verse,
                streak=streak,
                streak_line=streak_line,
                test=event.is_test,
                lifetime=lifetime,
                player=player,
                player_avatar=player_avatar,
                bot_avatar=avatar,
            )
        except ValueError as exc:
            return f"embed lỗi: {exc}"

        kwargs: dict = {"embed": embed}
        if with_image and event.image:
            buffer = io.BytesIO(event.image)
            kwargs["file"] = discord.File(buffer, filename=event.filename)

        try:
            await channel.send(**kwargs)
        except discord.Forbidden:
            return "thiếu quyền gửi tin / đính kèm"
        except discord.HTTPException as exc:
            return f"Discord lỗi {exc.status}: {exc.text[:80]}"
        except Exception as exc:  # noqa: BLE001 - một kênh lỗi không được làm sập cả lượt
            log.exception("gửi tới kênh %s thất bại", channel_id)
            return str(exc)[:120]

        log.info("đã gửi tới kênh %s (ảnh=%s)", channel_id, with_image and event.has_image)
        return None

    async def send_test(self, channel_id: int) -> str | None:
        """Gửi 1 thông báo mẫu; không đụng tới streak/thống kê thật."""
        cfg = self._store.config
        event = DeathEvent.sample(death_no=3, total=int(cfg.deaths_total or 0) + 1)
        player, avatar = self._player_identity(cfg.player)
        return await self._send_one(
            channel_id,
            event,
            self._store.image_for(channel_id),
            self._picker.pick(),
            1,
            None,
            int(cfg.deaths_total or 0) + 1,
            player,
            avatar,
        )

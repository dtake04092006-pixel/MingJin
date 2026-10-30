"""Lưu cấu hình bền vững trên Render free.

Đĩa của Render free là ephemeral (mất khi deploy/restart), nên nguồn sự thật là
một message ghim trong Discord. `data/config.json` chỉ là cache cho lần khởi
động nhanh, và biến môi trường `CHANNELS` là nền tảng cuối cùng.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import discord

from .settings import Settings

log = logging.getLogger(__name__)

CONFIG_CHANNEL_NAME = "khi-tuyet-luc-config"
MARKER = "KTL_CONFIG_V1"
MAX_CHANNELS = 10

_JSON_BLOCK = re.compile(r"```json\s*(\{.*?\})\s*```", re.S)


class StoreError(RuntimeError):
    pass


def _parse_player(raw: object) -> dict | None:
    """Chỉ nhận {"id": int, "name": str, "avatar": str|None} — bỏ mọi thứ khác."""
    if not isinstance(raw, dict):
        return None
    try:
        player_id = int(raw.get("id") or 0)
    except (TypeError, ValueError):
        return None
    name = raw.get("name")
    if not player_id or not isinstance(name, str) or not name.strip():
        return None
    avatar = raw.get("avatar")
    return {
        "id": player_id,
        "name": name.strip()[:64],
        "avatar": avatar[:200] if isinstance(avatar, str) else None,
    }


@dataclass
class BotConfig:
    version: int = 1
    default_image: bool = True
    paused: bool = False
    channels: dict[str, dict] = field(default_factory=dict)
    streak: int = 1
    stats: dict = field(default_factory=dict)
    deaths_total: int = 0
    player: dict | None = None

    # --- truy vấn -------------------------------------------------------
    def image_for(self, channel_id: int | str) -> bool:
        entry = self.channels.get(str(channel_id)) or {}
        override = entry.get("image")
        if isinstance(override, bool):
            return override
        return self.default_image

    def channel_ids(self) -> tuple[int, ...]:
        out: list[int] = []
        for raw in self.channels:
            try:
                out.append(int(raw))
            except (TypeError, ValueError):
                continue
        return tuple(out)

    def note_death(self, event_id: str, ts_utc: str, streak: int) -> None:
        self.stats["received"] = int(self.stats.get("received") or 0) + 1
        self.stats["last_id"] = event_id
        self.stats["last_death_utc"] = ts_utc
        self.streak = streak
        self.deaths_total = max(0, int(self.deaths_total or 0)) + 1

    @property
    def player_name(self) -> str | None:
        if not self.player:
            return None
        return self.player.get("name") or None

    # --- (de)serialize --------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "default_image": bool(self.default_image),
            "paused": bool(self.paused),
            "channels": self.channels,
            "streak": int(self.streak),
            "stats": self.stats,
            "deaths_total": int(self.deaths_total),
            "player": self.player,
        }

    @classmethod
    def from_dict(cls, raw: object) -> "BotConfig":
        if not isinstance(raw, dict):
            return cls()
        channels: dict[str, dict] = {}
        source = raw.get("channels")
        if isinstance(source, dict):
            for key, value in source.items():
                try:
                    channel_id = int(key)
                except (TypeError, ValueError):
                    continue
                entry = value if isinstance(value, dict) else {}
                override = entry.get("image")
                channels[str(channel_id)] = {"image": override if isinstance(override, bool) else None}
        stats = raw.get("stats") if isinstance(raw.get("stats"), dict) else {}
        streak = raw.get("streak")
        deaths = raw.get("deaths_total")
        deaths_total = deaths if isinstance(deaths, int) and not isinstance(deaths, bool) and deaths >= 0 else 0
        return cls(
            version=int(raw.get("version") or 1),
            default_image=bool(raw.get("default_image", True)),
            paused=bool(raw.get("paused", False)),
            channels=channels,
            streak=int(streak) if isinstance(streak, int) and streak >= 1 else 1,
            stats=stats,
            deaths_total=int(deaths_total),
            player=_parse_player(raw.get("player")),
        )

    def describe(self) -> str:
        if not self.channels:
            return "chưa có kênh nào"
        rows = []
        for channel_id in self.channel_ids():
            mode = "ảnh" if self.image_for(channel_id) else "không ảnh"
            rows.append(f"<#{channel_id}> ({mode})")
        return ", ".join(rows)


def render_message(cfg: BotConfig) -> str:
    body = json.dumps(cfg.to_dict(), ensure_ascii=False, separators=(",", ":"))
    return f"{MARKER} · 氣絕錄\n```json\n{body}\n```"


def parse_message(content: str) -> BotConfig | None:
    if MARKER not in content:
        return None
    match = _JSON_BLOCK.search(content)
    if not match:
        return None
    try:
        return BotConfig.from_dict(json.loads(match.group(1)))
    except json.JSONDecodeError:
        log.warning("cấu hình ghim trong Discord hỏng — bỏ qua")
        return None


class ConfigStore:
    """Cấu hình runtime + đồng bộ hai chiều với message ghim trên Discord."""

    CACHE_MIN_INTERVAL = 30.0

    def __init__(self, settings: Settings, data_dir: Path) -> None:
        self._settings = settings
        self._data_dir = data_dir
        self._cache_path = data_dir / "config.json"
        self._cfg = BotConfig(default_image=settings.default_image)
        self._channel: discord.TextChannel | None = None
        self._message: discord.Message | None = None
        self._bot_user_id: int = 0
        self._dirty = False
        self._last_save = 0.0
        self.source = "default"

    # --- truy cập -------------------------------------------------------
    @property
    def config(self) -> BotConfig:
        return self._cfg

    def image_for(self, channel_id: int) -> bool:
        return self._cfg.image_for(channel_id)

    def channel_ids(self) -> tuple[int, ...]:
        return self._cfg.channel_ids()

    def add_channel(self, channel_id: int, image: bool | None = None) -> bool:
        key = str(int(channel_id))
        if key in self._cfg.channels:
            if image is not None:
                self._cfg.channels[key]["image"] = image
            return False
        if len(self._cfg.channels) >= MAX_CHANNELS:
            raise StoreError(f"tối đa {MAX_CHANNELS} kênh")
        self._cfg.channels[key] = {"image": image}
        return True

    def remove_channel(self, channel_id: int) -> bool:
        return self._cfg.channels.pop(str(int(channel_id)), None) is not None

    def set_channel_image(self, channel_id: int, image: bool | None) -> bool:
        key = str(int(channel_id))
        if key not in self._cfg.channels:
            return False
        self._cfg.channels[key]["image"] = image
        return True

    def set_default_image(self, value: bool) -> None:
        self._cfg.default_image = value

    def set_paused(self, value: bool) -> None:
        self._cfg.paused = value

    def set_deaths(self, value: int) -> None:
        """Đặt lại tổng kiếp (dùng khi đã chết nhiều lần trước khi có tool)."""
        self._cfg.deaths_total = max(0, int(value))
        self._dirty = True

    def set_player(self, member: discord.abc.User | None) -> None:
        if member is None:
            self._cfg.player = None
        else:
            self._cfg.player = _parse_player(
                {
                    "id": member.id,
                    "name": getattr(member, "display_name", None) or member.name,
                    "avatar": member.display_avatar.url if member.display_avatar else None,
                }
            )
        self._dirty = True

    def note_death(self, event_id: str, ts_utc: str, streak: int) -> None:
        self._cfg.note_death(event_id, ts_utc, streak)
        self._dirty = True

    # --- nạp / lưu ------------------------------------------------------
    def _apply_env(self) -> None:
        if not self._settings.env_channels:
            return
        added = 0
        for channel_id in self._settings.env_channels:
            try:
                if self.add_channel(channel_id):
                    added += 1
            except StoreError:
                log.warning("CHANNELS vượt quá %s kênh — bỏ phần còn lại", MAX_CHANNELS)
                break
        if added:
            self._dirty = True
            log.info("thêm %s kênh từ biến môi trường CHANNELS", added)

    async def load(self, bot: discord.Client) -> None:
        self._bot_user_id = bot.user.id if bot.user else 0
        if self._load_cache():
            self.source = "cache"
        try:
            await self._load_discord(bot)
        except Exception:  # noqa: BLE001 - Discord lỗi thì vẫn chạy bằng cache
            log.exception("không đọc được cấu hình từ Discord, dùng cache")

    def _load_cache(self) -> bool:
        if not self._cache_path.exists():
            return False
        try:
            raw = json.loads(self._cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            log.warning("cache cấu hình hỏng — bỏ qua")
            return False
        self._cfg = BotConfig.from_dict(raw.get("config"))
        log.info("nạp cache cấu hình: %s kênh", len(self._cfg.channels))
        return True

    async def _load_discord(self, bot: discord.Client) -> None:
        channel = self.find_config_channel(bot)
        if channel is None:
            self._apply_env()
            self.source = "cache" if self.source == "cache" else "default"
            return
        self._channel = channel
        self._message = await self._find_message(channel)
        if self._message is not None:
            parsed = parse_message(self._message.content or "")
            if parsed is not None:
                self._cfg = parsed
                self.source = "discord"
                log.info("nạp cấu hình từ Discord: %s kênh", len(self._cfg.channels))
        self._apply_env()

    @staticmethod
    def find_config_channel(bot: discord.Client) -> discord.TextChannel | None:
        for guild in bot.guilds:
            found = discord.utils.get(guild.text_channels, name=CONFIG_CHANNEL_NAME)
            if isinstance(found, discord.TextChannel):
                return found
        return None

    async def _find_message(self, channel: discord.TextChannel) -> discord.Message | None:
        try:
            async for message in channel.pins():
                if message.author.id == self._bot_user_id and MARKER in (message.content or ""):
                    return message
        except (discord.Forbidden, discord.HTTPException):
            log.warning("không đọc được pins của #%s", channel.name)
        try:
            async for message in channel.history(limit=50, oldest_first=False):
                if message.author.id == self._bot_user_id and MARKER in (message.content or ""):
                    return message
        except (discord.Forbidden, discord.HTTPException):
            log.warning("không đọc được lịch sử #%s", channel.name)
        return None

    async def ensure_channel(self, guild: discord.Guild) -> discord.TextChannel:
        """Tạo kênh cấu hình riêng tư nếu chưa có."""
        existing = discord.utils.get(guild.text_channels, name=CONFIG_CHANNEL_NAME)
        if isinstance(existing, discord.TextChannel):
            self._channel = existing
            return existing

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                manage_messages=True,
                read_message_history=True,
                embed_links=True,
                attach_files=True,
            ),
        }
        channel = await guild.create_text_channel(
            CONFIG_CHANNEL_NAME,
            overwrites=overwrites,
            topic="氣絕錄 · cấu hình bot Khí Tuyệt Lục (đừng xoá message ghim)",
            reason="Khí Tuyệt Lục: tạo kênh lưu cấu hình",
        )
        self._channel = channel
        self._message = None
        return channel

    async def save(self) -> bool:
        """Ghi cấu hình: cache luôn ghi, Discord ghi khi có kênh cấu hình."""
        self._write_cache()
        self._dirty = False
        self._last_save = time.monotonic()
        if self._channel is None:
            return False
        content = render_message(self._cfg)
        try:
            if self._message is None:
                self._message = await self._channel.send(content)
                try:
                    await self._message.pin(reason="Khí Tuyệt Lục: ghim cấu hình")
                except (discord.Forbidden, discord.HTTPException):
                    log.warning("không ghim được message cấu hình (thiếu quyền?)")
            else:
                await self._message.edit(content=content)
            self.source = "discord"
            return True
        except (discord.Forbidden, discord.HTTPException):
            log.exception("không ghi được cấu hình lên Discord — đang dùng cache")
            self._dirty = True
            return False

    async def flush(self) -> None:
        """Gọi định kỳ: chỉ ghi khi có thay đổi và đã qua khoảng chờ."""
        if not self._dirty:
            return
        if time.monotonic() - self._last_save < self.CACHE_MIN_INTERVAL:
            return
        await self.save()

    def _write_cache(self) -> None:
        payload = {"config": self._cfg.to_dict(), "saved_at": time.time()}
        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)
            tmp = self._cache_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, self._cache_path)
        except OSError:
            log.warning("không ghi được cache cấu hình %s", self._cache_path)

    def describe_source(self) -> str:
        return {"discord": "message ghim Discord", "cache": "cache cục bộ", "default": "mặc định"}.get(
            self.source, self.source
        )

"""Lớp Bot: nối store, notifier và slash command."""

from __future__ import annotations

import asyncio
import logging

import discord
from discord.ext import commands

from .commands import setup_commands
from .notify import Notifier
from .settings import Settings
from .store import ConfigStore

log = logging.getLogger(__name__)

FLUSH_INTERVAL_S = 60.0


class KhiTuyetLucBot(commands.Bot):
    def __init__(self, settings: Settings, store: ConfigStore) -> None:
        intents = discord.Intents.default()  # không cần message_content
        super().__init__(command_prefix="!", intents=intents, help_command=None)
        self.settings = settings
        self.store = store
        self.notifier: Notifier | None = None
        self.web_state = None
        self._store_loaded = False

    async def setup_hook(self) -> None:
        setup_commands(self)
        try:
            if self.settings.guild_id:
                guild = discord.Object(id=self.settings.guild_id)
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                log.info("đăng ký %s slash command vào guild %s", len(synced), self.settings.guild_id)
            else:
                synced = await self.tree.sync()
                log.info("đăng ký %s slash command toàn cục (có thể mất tới 1 giờ)", len(synced))
        except discord.Forbidden:
            log.error(
                "đăng ký slash command bị chặn (403) — bot thiếu scope 'applications.commands' "
                "hoặc chưa ở trong guild %s. Mời lại bot bằng link có scope "
                "'bot applications.commands' rồi khởi động lại.",
                self.settings.guild_id or "(toàn cục)",
            )
        except discord.HTTPException:
            log.exception("đăng ký slash command thất bại")
        self.loop.create_task(self._flush_loop(), name="config-flush")

    async def on_ready(self) -> None:
        log.info("đã đăng nhập: %s (guild: %s)", self.user, len(self.guilds))
        for guild in self.guilds:
            log.info("  · đang ở server: %s (id %s)", guild.name, guild.id)
        if self.settings.guild_id and all(g.id != self.settings.guild_id for g in self.guilds):
            log.error(
                "GUILD_ID=%s không có trong danh sách trên — bot chưa được mời vào server đó "
                "hoặc ID sai. Sửa biến GUILD_ID hoặc mời bot vào đúng server.",
                self.settings.guild_id,
            )
        if not self._store_loaded:
            self._store_loaded = True
            await self.store.load(self)
            if self.store.config.channels:
                log.info("kênh nhận thông báo: %s", self.store.config.describe())
            else:
                log.warning("chưa cấu hình kênh nào — chạy /ktl add trong server")
            if self.store._channel is not None and self.store._message is None:  # noqa: SLF001
                await self.store.save()  # tạo message cấu hình nếu thiếu

    async def _flush_loop(self) -> None:
        await self.wait_until_ready()
        while not self.is_closed():
            await asyncio.sleep(FLUSH_INTERVAL_S)
            try:
                await self.store.flush()
            except Exception:  # noqa: BLE001 - vòng lặp nền không được chết
                log.exception("flush cấu hình thất bại")

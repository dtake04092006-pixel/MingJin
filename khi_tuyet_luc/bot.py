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

# View Channels + Manage Channels + Manage Messages + Send Messages
# + Embed Links + Attach Files + Read Message History
INVITE_PERMISSIONS = 125968


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
        # setup_hook chạy trước khi nối gateway nên chưa biết bot ở server nào;
        # việc sync phải đợi READY mới quyết định được.
        self.loop.create_task(self._sync_commands(), name="slash-sync")
        self.loop.create_task(self._flush_loop(), name="config-flush")

    def _invite_url(self, guild_id: int | None = None) -> str | None:
        """Link mời bot có sẵn scope `bot` + `applications.commands`."""
        app_id = self.application_id
        if not app_id:
            return None
        url = (
            "https://discord.com/api/oauth2/authorize"
            f"?client_id={app_id}&permissions={INVITE_PERMISSIONS}"
            "&scope=bot%20applications.commands"
        )
        if guild_id:
            url += f"&guild_id={guild_id}&disable_guild_select=true"
        return url

    async def _sync_commands(self, guild_id: int | None = None) -> None:
        await self.wait_until_ready()
        target = guild_id or self.settings.guild_id
        try:
            if target and all(g.id != target for g in self.guilds):
                log.error(
                    "bỏ qua đăng ký lệnh: bot chưa ở trong guild %s. Mời bot vào server: %s",
                    target,
                    self._invite_url(target) or "(không tạo được link mời)",
                )
                return
            if target:
                guild = discord.Object(id=target)
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                log.info("đăng ký %s slash command vào guild %s", len(synced), target)
            else:
                synced = await self.tree.sync()
                log.info("đăng ký %s slash command toàn cục (có thể mất tới 1 giờ)", len(synced))
        except discord.Forbidden:
            log.error(
                "đăng ký slash command bị chặn (403) — thiếu scope 'applications.commands' "
                "trong link mời. Mời lại bot bằng link này: %s",
                self._invite_url(target) or "(không tạo được link)",
            )
        except discord.HTTPException:
            log.exception("đăng ký slash command thất bại")

    async def on_ready(self) -> None:
        log.info("đã đăng nhập: %s (guild: %s)", self.user, len(self.guilds))
        if not self.guilds:
            log.error(
                "BOT CHƯA ĐƯỢC MỜI VÀO SERVER NÀO — mở link này bằng tài khoản admin "
                "của server để thêm bot: %s",
                self._invite_url(self.settings.guild_id) or "(không tạo được link mời)",
            )
        for guild in self.guilds:
            log.info("  · đang ở server: %s (id %s)", guild.name, guild.id)
        if self.guilds and self.settings.guild_id and all(
            g.id != self.settings.guild_id for g in self.guilds
        ):
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

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Vừa được mời vào server → đăng ký lại lệnh ngay, khỏi phải restart."""
        log.info("được thêm vào server: %s (id %s)", guild.name, guild.id)
        if self.settings.guild_id and guild.id != self.settings.guild_id:
            log.warning(
                "server vừa thêm (%s) khác GUILD_ID=%s — lệnh sẽ đăng ký ở server vừa thêm",
                guild.id,
                self.settings.guild_id,
            )
        self.loop.create_task(self._sync_commands(guild.id), name="slash-sync-on-join")

    async def _flush_loop(self) -> None:
        await self.wait_until_ready()
        while not self.is_closed():
            await asyncio.sleep(FLUSH_INTERVAL_S)
            try:
                await self.store.flush()
            except Exception:  # noqa: BLE001 - vòng lặp nền không được chết
                log.exception("flush cấu hình thất bại")

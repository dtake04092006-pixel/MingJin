"""Entrypoint: chạy HTTP server (cho Render/UptimeRobot) và bot Discord cùng lúc.

    python -m khi_tuyet_luc
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

import discord

from . import __version__
from .bot import KhiTuyetLucBot
from .notify import Notifier
from .settings import Settings, SettingsError, load_dotenv
from .store import ConfigStore
from .web import WebState, start_server

log = logging.getLogger("khi_tuyet_luc")


def _configure_logging(level: str) -> None:
    numeric = getattr(logging, level.upper(), logging.INFO)
    discord.utils.setup_logging(level=numeric, root=True)
    for name in ("discord.gateway", "discord.http"):
        logging.getLogger(name).setLevel(max(logging.WARNING, numeric))
    # bot chỉ dùng slash command, cảnh báo thiếu message_content intent là nhiễu
    logging.getLogger("discord.ext.commands.bot").setLevel(logging.ERROR)


def _app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


async def amain(settings: Settings) -> int:
    data_dir = (_app_root() / settings.data_dir).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)

    store = ConfigStore(settings, data_dir)
    bot = KhiTuyetLucBot(settings, store)
    notifier = Notifier(bot, store)
    bot.notifier = notifier

    state = WebState(api_token=settings.api_token, notifier=notifier, store=store, bot=bot)
    bot.web_state = state
    runner = await start_server(state, settings.port)

    stopping = False

    async def _stop() -> None:
        nonlocal stopping
        if stopping:
            return
        stopping = True
        await runner.cleanup()
        await bot.close()

    def _shutdown(signame: str) -> None:
        log.info("nhận %s — đang tắt", signame)
        asyncio.create_task(_stop())

    loop = asyncio.get_running_loop()
    for sig, name in ((signal.SIGTERM, "SIGTERM"), (signal.SIGINT, "SIGINT")):
        try:
            loop.add_signal_handler(sig, _shutdown, name)
        except (NotImplementedError, AttributeError, RuntimeError):
            pass  # Windows: dựa vào KeyboardInterrupt

    try:
        async with bot:
            await bot.start(settings.discord_token)
    finally:
        await _stop()
        log.info("đã dừng")
    return 0


def main() -> int:
    loaded = load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    try:
        settings = Settings.from_env()
    except SettingsError as exc:
        print(f"[khi_tuyet_luc] {exc}", file=sys.stderr)
        print("[khi_tuyet_luc] cần DISCORD_TOKEN và API_TOKEN trong biến môi trường.", file=sys.stderr)
        return 2

    _configure_logging(settings.log_level)
    if loaded:
        log.info("nạp %s biến từ .env (chỉ dùng khi chạy trên máy)", loaded)
    log.info("Khí Tuyệt Lục %s khởi động %s", __version__, settings.redacted())

    try:
        return asyncio.run(amain(settings))
    except discord.LoginFailure:
        log.error("DISCORD_TOKEN không hợp lệ — kiểm tra lại trong Developer Portal → Bot → Reset Token")
    except KeyboardInterrupt:
        log.info("dừng theo yêu cầu")
    return 1


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUTF8", "1")
    raise SystemExit(main())

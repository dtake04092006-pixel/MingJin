"""Test offline: neo cấu hình — ghim vào kênh thông báo thay vì kênh riêng.

Không cần token, không cần mạng: mọi thứ là fake duck-type với ConfigStore thật.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from types import SimpleNamespace

from _common import Checker, make_settings

from khi_tuyet_luc.store import MARKER, ConfigStore, render_message

BOT_ID = 999


class FakeMessage:
    def __init__(self, content: str, msg_id: int = 1, author_id: int = BOT_ID) -> None:
        self.id = msg_id
        self.content = content
        self.author = SimpleNamespace(id=author_id)
        self.pinned = False
        self.edits: list[str] = []

    async def pin(self, reason: str | None = None) -> None:
        self.pinned = True

    async def edit(self, content: str) -> None:
        self.content = content
        self.edits.append(content)


class FakeTextChannel:
    def __init__(self, channel_id: int, name: str = "huyet-thu") -> None:
        self.id = channel_id
        self.name = name
        self.mention = f"<#{channel_id}>"
        self._messages: list[FakeMessage] = []

    async def send(self, content: str | None = None, **kwargs) -> FakeMessage:
        message = FakeMessage(content or "", msg_id=len(self._messages) + 1)
        self._messages.append(message)
        return message

    def pins(self):
        async def gen():
            for message in self._messages:
                if message.pinned:
                    yield message

        return gen()

    def history(self, limit: int = 50, oldest_first: bool = False):
        async def gen():
            for message in self._messages[-limit:]:
                yield message

        return gen()


class FakeGuild:
    def __init__(self, channels: list[FakeTextChannel]) -> None:
        self.id = 1
        self.name = "Trai giao duong"
        self.text_channels = channels
        self.me = None


class FakeBot:
    def __init__(self, channels: list[FakeTextChannel], with_guild: bool = True) -> None:
        self.user = SimpleNamespace(id=BOT_ID)
        self._channels = {channel.id: channel for channel in channels}
        self.guilds = [FakeGuild(channels)] if with_guild else []

    def get_channel(self, channel_id: int):
        return self._channels.get(channel_id)

    async def fetch_channel(self, channel_id: int):
        return self._channels.get(channel_id)


def make_store() -> ConfigStore:
    return ConfigStore(make_settings(), Path(tempfile.mkdtemp(prefix="ktl_store_")))


def main() -> int:
    check = Checker("store: neo cấu hình")

    # 1. ghim vào kênh thông báo có sẵn, không tạo kênh riêng
    channel = FakeTextChannel(1001)
    store = make_store()
    asyncio.run(store.load(FakeBot([channel])))  # để store biết id của bot như lúc khởi động
    check.ok("kênh trống → chưa có message cấu hình", not asyncio.run(store.attach(channel)))
    asyncio.run(store.save())
    check.eq("neo = kênh thông báo", store.config_channel_id, 1001)
    check.ok("is_anchor đúng kênh neo", store.is_anchor(1001))
    check.ok("is_anchor kênh khác = False", not store.is_anchor(2002))
    check.eq("chỉ 1 message được tạo", len(channel._messages), 1)
    check.ok("message có marker cấu hình", MARKER in channel._messages[0].content)
    check.ok("message đã được ghim", channel._messages[0].pinned)

    # 2. setup lại trên cùng kênh: dùng lại message cũ, không tạo thêm
    reused = asyncio.run(store.attach(channel))
    asyncio.run(store.save())
    check.ok("lần 2 dùng lại message ghim", reused)
    check.eq("không sinh message trùng", len(channel._messages), 1)

    # 3. lưu số liệu rồi khởi động lại với cache trắng (giống Render deploy)
    store.set_deaths(39)
    store.add_channel(1001)
    asyncio.run(store.save())

    fresh = make_store()
    check.ok("store mới: cache rỗng", fresh.config.deaths_total == 0)
    asyncio.run(fresh.load(FakeBot([channel])))
    check.eq("khôi phục được tổng kiếp từ pin", fresh.config.deaths_total, 39)
    check.eq("khôi phục được kênh thông báo", fresh.channel_ids(), (1001,))
    check.eq("nguồn cấu hình = discord", fresh.source, "discord")
    check.eq("neo tìm lại được", fresh.config_channel_id, 1001)

    # 4. không có guild nào trong cache → vẫn dò ra nhờ quét pin
    blind = make_store()
    asyncio.run(blind.load(FakeBot([channel], with_guild=True)))
    check.eq("quét pin: tìm được cấu hình", blind.config.deaths_total, 39)

    # 5. đường lui: kênh tên cũ vẫn được nhận
    legacy = FakeTextChannel(3003, name="khi-tuyet-luc-config")
    legacy._messages.append(FakeMessage(render_message(blind.config)))
    legacy._messages[0].pinned = True
    old_style = make_store()
    asyncio.run(old_style.load(FakeBot([legacy])))
    check.eq("cấu hình cũ ở kênh riêng vẫn đọc được", old_style.config_channel_id, 3003)
    check.eq("dữ liệu cũ giữ nguyên", old_style.config.deaths_total, 39)

    return check.summary()


if __name__ == "__main__":
    raise SystemExit(main())

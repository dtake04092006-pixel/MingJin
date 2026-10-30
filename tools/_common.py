"""Tiện ích chung cho test offline của bot (không cần token Discord, không cần mạng)."""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:  # noqa: BLE001 - console cũ không hỗ trợ
        pass

from khi_tuyet_luc.event import DeathEvent  # noqa: E402
from khi_tuyet_luc.settings import Settings  # noqa: E402
from khi_tuyet_luc.store import ConfigStore  # noqa: E402

# JPEG tối thiểu — chỉ cần đúng magic bytes, bot không giải mã ảnh
MINIMAL_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 256 + b"\xff\xd9"
MINIMAL_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


class Checker:
    def __init__(self, title: str) -> None:
        self.title = title
        self.passed = 0
        self.failed: list[str] = []
        print(f"\n=== {self.title} ===")

    def ok(self, label: str, condition: bool, detail: str = "") -> bool:
        if condition:
            self.passed += 1
            print(f"  PASS {label}")
        else:
            self.failed.append(label)
            print(f"  FAIL {label}{('  → ' + detail) if detail else ''}")
        return condition

    def eq(self, label: str, actual: object, expected: object) -> bool:
        return self.ok(label, actual == expected, f"nhận {actual!r}, cần {expected!r}")

    def summary(self) -> int:
        total = self.passed + len(self.failed)
        if self.failed:
            print(f"  → {len(self.failed)}/{total} FAIL: {', '.join(self.failed)}")
            return 1
        print(f"  → {total}/{total} PASS")
        return 0


def make_settings(**overrides) -> Settings:
    base = dict(
        discord_token="test-token",
        api_token="secret-token",
        port=8080,
        guild_id=None,
        env_channels=(),
        default_image=True,
        log_level="WARNING",
        data_dir="data",
    )
    base.update(overrides)
    return Settings(**base)


def make_store(tmpdir: Path | None = None, **settings_overrides) -> ConfigStore:
    data_dir = Path(tmpdir or tempfile.mkdtemp(prefix="mt_store_"))
    return ConfigStore(make_settings(**settings_overrides), data_dir)


def make_event(
    *,
    event_id: str = "evt-1",
    death_no: int = 3,
    total: int = 47,
    since_prev: float | None = 161.4,
    with_image: bool = True,
    confidence: float = 1.0,
    test: bool = False,
) -> DeathEvent:
    now = datetime.now(timezone.utc)
    return DeathEvent(
        id=f"test-{event_id}" if test else event_id,
        ts_utc=now,
        ts_local=now.strftime("%Y-%m-%d %H:%M:%S"),
        session_id="s_20261030_231500",
        death_no=death_no,
        total_deaths=total,
        seconds_since_prev=since_prev,
        session_elapsed_s=902.4,
        confidence=confidence,
        screenshot_path="deaths/2026-10-30/x.jpg" if with_image else None,
        image=MINIMAL_JPEG if with_image else None,
        image_mime="image/jpeg" if with_image else None,
        screen_w=1920,
        screen_h=1080,
        backend="dxgi",
        tracker_version="0.1.0",
    )


class FakeChannel:
    """Ghi lại mọi lần send. `fail=...` để giả lập lỗi Discord."""

    def __init__(self, channel_id: int, fail: Exception | None = None) -> None:
        self.id = channel_id
        self.mention = f"<#{channel_id}>"
        self.fail = fail
        self.sent: list[dict] = []

    async def send(self, **kwargs):
        if self.fail is not None:
            raise self.fail
        self.sent.append(kwargs)
        return SimpleNamespace(id=len(self.sent))

    @property
    def files(self) -> list:
        return [item["file"] for item in self.sent if "file" in item]

    @property
    def embeds(self) -> list:
        return [item["embed"] for item in self.sent if "embed" in item]


class FakeBot:
    def __init__(self, channels: list[FakeChannel]) -> None:
        self._channels = {channel.id: channel for channel in channels}
        self.user = SimpleNamespace(
            id=999, __str__=lambda self: "Khí Tuyệt Lục#0001", display_avatar=SimpleNamespace(url="https://x/y.png")
        )
        self.guilds: list = []
        self.users: dict[int, object] = {}

    def get_channel(self, channel_id: int):
        return self._channels.get(channel_id)

    def get_user(self, user_id: int):
        """Giả lập cache thành viên; rỗng thì bot dùng avatar đã lưu."""
        return self.users.get(user_id)

    async def fetch_channel(self, channel_id: int):
        return None

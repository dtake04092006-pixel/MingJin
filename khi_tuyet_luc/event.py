"""Chuyển payload JSON của tracker thành đối tượng dùng được, kèm giải mã ảnh."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass, field
from datetime import datetime, timezone

MAX_IMAGE_BYTES = 8 * 1024 * 1024

_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class PayloadError(ValueError):
    """Payload không dùng được — trả 400 cho tracker."""


def _as_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_text(value: object, limit: int = 200) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text[:limit] if text else None


def parse_timestamp(raw: object) -> datetime:
    """Nhận ISO8601 có 'Z' hoặc offset. Sai thì dùng giờ hiện tại."""
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
        except ValueError:
            parsed = None
        if parsed is not None:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def decode_image(raw_b64: object, mime: object) -> tuple[bytes | None, str | None]:
    """Giải mã base64, chỉ chấp nhận JPEG/PNG và ≤ 8 MB."""
    if not isinstance(raw_b64, str) or not raw_b64.strip():
        return None, None
    try:
        data = base64.b64decode(raw_b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise PayloadError(f"screenshot_b64 không giải mã được: {exc}") from exc
    if not data:
        return None, None
    if len(data) > MAX_IMAGE_BYTES:
        raise PayloadError(f"ảnh quá lớn: {len(data)} byte > {MAX_IMAGE_BYTES}")

    if data.startswith(_JPEG_MAGIC):
        detected = "image/jpeg"
    elif data.startswith(_PNG_MAGIC):
        detected = "image/png"
    else:
        raise PayloadError("ảnh không phải JPEG/PNG")

    claimed = _as_text(mime, 40)
    if claimed and claimed not in ("image/jpeg", "image/png"):
        raise PayloadError(f"mime không hỗ trợ: {claimed}")
    return data, detected


@dataclass(slots=True)
class DeathEvent:
    id: str
    ts_utc: datetime
    ts_local: str | None = None
    session_id: str | None = None
    death_no: int | None = None
    total_deaths: int | None = None
    seconds_since_prev: float | None = None
    session_elapsed_s: float | None = None
    confidence: float | None = None
    screenshot_path: str | None = None
    image: bytes | None = None
    image_mime: str | None = None
    screen_w: int | None = None
    screen_h: int | None = None
    backend: str | None = None
    tracker_version: str | None = None
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: object) -> "DeathEvent":
        if not isinstance(payload, dict):
            raise PayloadError("body phải là JSON object")

        event_id = _as_text(payload.get("id"), 64)
        if not event_id:
            raise PayloadError("thiếu 'id'")

        image, mime = decode_image(payload.get("screenshot_b64"), payload.get("screenshot_mime"))
        screen = payload.get("screen") if isinstance(payload.get("screen"), dict) else {}

        return cls(
            id=event_id,
            ts_utc=parse_timestamp(payload.get("ts_utc")),
            ts_local=_as_text(payload.get("ts_local"), 32),
            session_id=_as_text(payload.get("session_id"), 64),
            death_no=_as_int(payload.get("death_no")),
            total_deaths=_as_int(payload.get("total_deaths")),
            seconds_since_prev=_as_float(payload.get("seconds_since_prev_death")),
            session_elapsed_s=_as_float(payload.get("session_elapsed_s")),
            confidence=_as_float(payload.get("confidence")),
            screenshot_path=_as_text(payload.get("screenshot"), 200),
            image=image,
            image_mime=mime,
            screen_w=_as_int(screen.get("width")),
            screen_h=_as_int(screen.get("height")),
            backend=_as_text(payload.get("capture_backend"), 24),
            tracker_version=_as_text(payload.get("tracker_version"), 24),
            raw=payload,
        )

    @property
    def epoch(self) -> int:
        return int(self.ts_utc.timestamp())

    @property
    def has_image(self) -> bool:
        return bool(self.image)

    @property
    def filename(self) -> str:
        return f"khi-tuyet-luc-{self.ts_utc.strftime('%Y%m%d-%H%M%S')}.jpg"

    @property
    def is_test(self) -> bool:
        return self.id.startswith("test-")

    @classmethod
    def sample(cls, *, death_no: int = 3, total: int = 47) -> "DeathEvent":
        """Event mẫu cho lệnh /ktl test — không cần tracker."""
        now = datetime.now(timezone.utc)
        return cls(
            id=f"test-{int(now.timestamp())}",
            ts_utc=now,
            ts_local=now.strftime("%Y-%m-%d %H:%M:%S"),
            session_id="s_test",
            death_no=death_no,
            total_deaths=total,
            seconds_since_prev=161.4,
            session_elapsed_s=902.4,
            confidence=1.0,
            backend="test",
            tracker_version="test",
        )

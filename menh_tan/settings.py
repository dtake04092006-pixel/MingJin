"""Đọc và kiểm tra biến môi trường. Không có bí mật nào nằm trong code."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


class SettingsError(RuntimeError):
    pass


def load_dotenv(path: os.PathLike[str] | str = ".env") -> int:
    """Nạp .env cho lúc chạy thử trên máy. Không ghi đè biến đã có sẵn."""
    file_path = os.fspath(path)
    if not os.path.isfile(file_path):
        return 0
    loaded = 0
    with open(file_path, encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.split(" #")[0].strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
                loaded += 1
    return loaded


def _parse_ids(raw: str) -> tuple[int, ...]:
    out: list[int] = []
    for chunk in raw.replace(";", ",").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            out.append(int(chunk))
        except ValueError as exc:
            raise SettingsError(f"CHANNELS có giá trị không phải số: {chunk!r}") from exc
    return tuple(out)


def _parse_bool(raw: str, default: bool) -> bool:
    if not raw:
        return default
    return raw.strip().lower() in ("1", "on", "true", "yes", "bat", "bật")


@dataclass(frozen=True, slots=True)
class Settings:
    discord_token: str
    api_token: str
    port: int = 8080
    guild_id: int | None = None
    env_channels: tuple[int, ...] = field(default_factory=tuple)
    default_image: bool = True
    log_level: str = "INFO"
    data_dir: str = "data"

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Settings":
        env = os.environ if env is None else env
        missing = [name for name in ("DISCORD_TOKEN", "API_TOKEN") if not env.get(name, "").strip()]
        if missing:
            raise SettingsError("thiếu biến môi trường: " + ", ".join(missing))

        raw_guild = env.get("GUILD_ID", "").strip()
        guild_id = None
        if raw_guild:
            try:
                guild_id = int(raw_guild)
            except ValueError as exc:
                raise SettingsError(f"GUILD_ID không phải số: {raw_guild!r}") from exc

        raw_port = env.get("PORT", "").strip() or "8080"
        try:
            port = int(raw_port)
        except ValueError as exc:
            raise SettingsError(f"PORT không phải số: {raw_port!r}") from exc

        return cls(
            discord_token=env["DISCORD_TOKEN"].strip(),
            api_token=env["API_TOKEN"].strip(),
            port=port,
            guild_id=guild_id,
            env_channels=_parse_ids(env.get("CHANNELS", "")),
            default_image=_parse_bool(env.get("IMAGE_MODE", ""), True),
            log_level=(env.get("LOG_LEVEL", "INFO").strip() or "INFO").upper(),
            data_dir=(env.get("DATA_DIR", "data").strip() or "data"),
        )

    def redacted(self) -> dict[str, object]:
        """Bản in ra log — không bao gồm token."""
        return {
            "port": self.port,
            "guild_id": self.guild_id,
            "env_channels": len(self.env_channels),
            "default_image": self.default_image,
            "log_level": self.log_level,
            "discord_token": "***" if self.discord_token else "",
            "api_token": "***" if self.api_token else "",
        }

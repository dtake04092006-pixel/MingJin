"""Các lệnh slash /menhtan — cấu hình kênh, chế độ ảnh, thử nghiệm."""

from __future__ import annotations

import discord
from discord import app_commands

from .store import MAX_CHANNELS, ConfigStore

MODE_ON = "on"
MODE_OFF = "off"
MODE_DEFAULT = "default"

MODE_CHOICES = [
    app_commands.Choice(name="bật ảnh", value=MODE_ON),
    app_commands.Choice(name="tắt ảnh", value=MODE_OFF),
    app_commands.Choice(name="theo mặc định", value=MODE_DEFAULT),
]


def _store(interaction: discord.Interaction) -> ConfigStore:
    return interaction.client.store  # type: ignore[attr-defined]


def _notifier(interaction: discord.Interaction):
    return interaction.client.notifier  # type: ignore[attr-defined]


def _mode_to_image(mode: str) -> bool | None:
    if mode == MODE_ON:
        return True
    if mode == MODE_OFF:
        return False
    return None


def _can_send(channel: discord.abc.GuildChannel, me: discord.Member | None) -> str | None:
    if me is None:
        return "không xác định được thành viên bot trong server"
    perms = channel.permissions_for(me)
    missing = []
    if not perms.send_messages:
        missing.append("Gửi tin nhắn")
    if not perms.embed_links:
        missing.append("Nhúng liên kết")
    if not perms.attach_files:
        missing.append("Đính kèm tệp")
    return "thiếu quyền: " + ", ".join(missing) if missing else None


def build_group() -> app_commands.Group:
    group = app_commands.Group(
        name="menhtan",
        description="命盡 · quản lý thông báo tử vong từ Phantom Blade Zero",
        default_permissions=discord.Permissions(manage_guild=True),
        guild_only=True,
    )

    @group.command(name="setup", description="Tạo kênh cấu hình riêng tư và ghim cấu hình bot")
    async def setup_cmd(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        guild = interaction.guild
        if guild is None:
            await interaction.followup.send("Lệnh này chỉ dùng trong server.", ephemeral=True)
            return
        store = _store(interaction)
        try:
            channel = await store.ensure_channel(guild)
            saved = await store.save(force=True)
        except discord.Forbidden:
            await interaction.followup.send(
                "Bot thiếu quyền **Quản lý kênh** để tạo `#menh-tan-config`.", ephemeral=True
            )
            return
        except discord.HTTPException as exc:
            await interaction.followup.send(f"Discord từ chối: {exc.status} {exc.text[:80]}", ephemeral=True)
            return

        lines = [
            f"Đã sẵn sàng. Cấu hình lưu tại {channel.mention}.",
            "Đừng xoá message ghim ở đó — đó là nơi giữ cấu hình qua các lần deploy.",
            f"Lưu lên Discord: {'thành công' if saved else 'chưa được, đang dùng cache cục bộ'}.",
            "Tiếp theo: `/menhtan add` để chọn kênh nhận thông báo.",
        ]
        await interaction.followup.send("\n".join(lines), ephemeral=True)

    @group.command(name="add", description="Thêm kênh nhận thông báo tử vong")
    @app_commands.describe(channel="Kênh sẽ nhận thông báo", image="Ép chế độ ảnh cho kênh này (bỏ trống = theo mặc định)")
    async def add_cmd(
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        image: bool | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        store = _store(interaction)
        warn = _can_send(channel, interaction.guild.me if interaction.guild else None)
        try:
            added = store.add_channel(channel.id, image)
        except Exception as exc:  # noqa: BLE001 - StoreError: quá số kênh
            await interaction.followup.send(f"Không thêm được: {exc}", ephemeral=True)
            return
        await store.save()
        mode = "ảnh" if store.image_for(channel.id) else "không ảnh"
        head = "Đã thêm" if added else "Đã cập nhật"
        text = f"{head} {channel.mention} → chế độ **{mode}** ({len(store.channel_ids())}/{MAX_CHANNELS} kênh)."
        if warn:
            text += f"\nCảnh báo: {warn}"
        await interaction.followup.send(text, ephemeral=True)

    @group.command(name="remove", description="Bỏ một kênh khỏi danh sách nhận thông báo")
    @app_commands.describe(channel="Kênh cần bỏ")
    async def remove_cmd(interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        store = _store(interaction)
        removed = store.remove_channel(channel.id)
        await store.save()
        if removed:
            await interaction.followup.send(f"Đã bỏ {channel.mention}.", ephemeral=True)
        else:
            await interaction.followup.send(f"{channel.mention} không có trong danh sách.", ephemeral=True)

    @group.command(name="list", description="Xem các kênh đang nhận thông báo")
    async def list_cmd(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        store = _store(interaction)
        cfg = store.config
        if not cfg.channels:
            await interaction.followup.send("Chưa có kênh nào. Dùng `/menhtan add`.", ephemeral=True)
            return
        lines = [f"**命盡 · {len(cfg.channels)}/{MAX_CHANNELS} kênh**"]
        for channel_id in store.channel_ids():
            mode = "ảnh" if store.image_for(channel_id) else "không ảnh"
            lines.append(f"· <#{channel_id}> — {mode}")
        lines.append(f"mặc định: {'ảnh' if cfg.default_image else 'không ảnh'} · trạng thái: {'tạm ngưng' if cfg.paused else 'đang chạy'}")
        await interaction.followup.send("\n".join(lines), ephemeral=True)

    @group.command(name="image", description="Ép chế độ ảnh cho một kênh")
    @app_commands.describe(channel="Kênh cần đổi", mode="Chế độ ảnh")
    @app_commands.choices(mode=MODE_CHOICES)
    async def image_cmd(interaction: discord.Interaction, channel: discord.TextChannel, mode: app_commands.Choice[str]) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        store = _store(interaction)
        if not store.set_channel_image(channel.id, _mode_to_image(mode.value)):
            await interaction.followup.send(f"{channel.mention} chưa có trong danh sách. Dùng `/menhtan add` trước.", ephemeral=True)
            return
        await store.save()
        current = "bật" if store.image_for(channel.id) else "tắt"
        await interaction.followup.send(f"{channel.mention}: **{mode.name}** → hiện tại đang {current} ảnh.", ephemeral=True)

    @group.command(name="default-image", description="Chế độ ảnh mặc định cho mọi kênh")
    @app_commands.describe(mode="Mặc định bật hay tắt ảnh")
    @app_commands.choices(mode=[MODE_CHOICES[0], MODE_CHOICES[1]])
    async def default_image_cmd(interaction: discord.Interaction, mode: app_commands.Choice[str]) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        store = _store(interaction)
        store.set_default_image(mode.value == MODE_ON)
        await store.save()
        text = "Mặc định: **bật ảnh**" if mode.value == MODE_ON else "Mặc định: **tắt ảnh**"
        await interaction.followup.send(text + " (kênh đã ép riêng thì giữ nguyên).", ephemeral=True)

    @group.command(name="test", description="Gửi một thông báo mẫu để xem embed")
    @app_commands.describe(channel="Gửi thử vào kênh này (bỏ trống = kênh đầu tiên)")
    async def test_cmd(interaction: discord.Interaction, channel: discord.TextChannel | None = None) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        store = _store(interaction)
        target = channel
        if target is None:
            ids = store.channel_ids()
            if not ids:
                await interaction.followup.send("Chưa có kênh nào. Dùng `/menhtan add` trước.", ephemeral=True)
                return
            target = interaction.client.get_channel(ids[0])  # type: ignore[attr-defined]
            if target is None:
                await interaction.followup.send("Không tìm thấy kênh đầu tiên — thử truyền `channel`.", ephemeral=True)
                return
        error = await _notifier(interaction).send_test(target.id)
        if error:
            await interaction.followup.send(f"Gửi thất bại tới {target.mention}: {error}", ephemeral=True)
        else:
            await interaction.followup.send(f"Đã gửi thông báo mẫu tới {target.mention}.", ephemeral=True)

    @group.command(name="status", description="Xem trạng thái bot và thống kê")
    async def status_cmd(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        store = _store(interaction)
        cfg = store.config
        state = getattr(interaction.client, "web_state", None)
        lines = [
            "**命盡 · Mệnh Tẫn**",
            f"kênh: {len(cfg.channels)}/{MAX_CHANNELS} · mặc định {'ảnh' if cfg.default_image else 'không ảnh'}",
            f"trạng thái: {'tạm ngưng' if cfg.paused else 'đang chạy'}",
            f"cấu hình đọc từ: {store.describe_source()}",
            f"đã nhận: {cfg.stats.get('received', 0)} lần chết",
            f"lần cuối: {cfg.stats.get('last_death_utc', '—')}",
        ]
        if state is not None:
            lines.append(f"uptime tiến trình: {state.uptime_s / 3600:.1f} giờ · từ chối: {state.rejected}")
        await interaction.followup.send("\n".join(lines), ephemeral=True)

    @group.command(name="pause", description="Tạm ngưng gửi thông báo (tracker vẫn được nhận)")
    async def pause_cmd(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        store = _store(interaction)
        store.set_paused(True)
        await store.save()
        await interaction.followup.send("Đã tạm ngưng. Bật lại bằng `/menhtan resume`.", ephemeral=True)

    @group.command(name="resume", description="Chạy tiếp thông báo")
    async def resume_cmd(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        store = _store(interaction)
        store.set_paused(False)
        await store.save()
        await interaction.followup.send("Đã chạy tiếp.", ephemeral=True)

    return group


def setup_commands(bot) -> None:
    bot.tree.add_command(build_group())

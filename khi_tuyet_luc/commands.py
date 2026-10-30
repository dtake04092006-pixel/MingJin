"""Các lệnh slash /ktl — cấu hình kênh, chế độ ảnh, thử nghiệm."""

from __future__ import annotations

import discord
from discord import app_commands

from . import texts
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


COLOUR_INFO = 0x7A6440
COLOUR_OK = 0x2E8B6E
COLOUR_WARN = 0x8C3A22


def _panel(title: str, body: str, colour: int = COLOUR_INFO, footer: str | None = None) -> discord.Embed:
    """Mọi phản hồi của lệnh đều là embed — thống nhất khung và màu."""
    embed = discord.Embed(title=title, description=body, colour=colour)
    if footer:
        embed.set_footer(text=footer)
    return embed


def build_group() -> app_commands.Group:
    group = app_commands.Group(
        name="ktl",
        description="氣絕錄 · quản lý thông báo tử vong từ Phantom Blade Zero",
        default_permissions=discord.Permissions(manage_guild=True),
        guild_only=True,
    )

    @group.command(name="setup", description="Ghim cấu hình vào kênh thông báo (không cần kênh riêng)")
    @app_commands.describe(channel="Kênh giữ message cấu hình (bỏ trống = kênh thông báo đầu tiên)")
    async def setup_cmd(interaction: discord.Interaction, channel: discord.TextChannel | None = None) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        guild = interaction.guild
        if guild is None:
            await interaction.followup.send(
                embed=_panel("Lỗi", "Lệnh này chỉ dùng trong server.", COLOUR_WARN), ephemeral=True
            )
            return
        store = _store(interaction)
        target = channel
        if target is None:
            ids = store.channel_ids()
            if ids:
                found = interaction.client.get_channel(ids[0])  # type: ignore[attr-defined]
                target = found if isinstance(found, discord.TextChannel) else None
        created = False
        try:
            if target is None:
                target = await store.create_config_channel(guild)
                created = True
            else:
                await store.attach(target)
            if interaction.user is not None:
                store.set_player(interaction.user)
            saved = await store.save()
        except discord.Forbidden:
            await interaction.followup.send(
                embed=_panel(
                    "Thiếu quyền",
                    "Bot cần **Quản lý kênh**, **Quản lý tin nhắn** (ghim) và **Gửi tin nhắn**.",
                    COLOUR_WARN,
                ),
                ephemeral=True,
            )
            return
        except discord.HTTPException as exc:
            await interaction.followup.send(
                embed=_panel("Discord từ chối", f"Mã {exc.status}: {exc.text[:80]}", COLOUR_WARN), ephemeral=True
            )
            return

        cfg = store.config
        realm = texts.realm_for(cfg.deaths_total)
        lines = [
            f"▸ Cấu hình ghim tại {target.mention}" + (" (kênh mới tạo vì chưa có kênh thông báo)" if created else ""),
            "▸ Đừng xoá message ghim đó — nó giữ cấu hình qua mỗi lần deploy.",
            f"▸ Người chơi: **{cfg.player_name or '—'}** · tổng kiếp #{cfg.deaths_total} · cảnh giới {realm.label}",
            f"▸ Lưu lên Discord: {'thành công' if saved else 'chưa được — đang dùng cache cục bộ'}",
            "▸ Đã chết trước khi có tool? `/ktl deaths count:39`",
            "▸ Xem embed mỗi lần chết: `/ktl preview` · thêm kênh: `/ktl add`",
        ]
        await interaction.followup.send(
            embed=_panel("氣絕錄 · đã sẵn sàng", "\n".join(lines), COLOUR_OK), ephemeral=True
        )

    @group.command(name="deaths", description="Đặt tổng kiếp đã có từ trước (cảnh giới tính theo số này)")
    @app_commands.describe(count="Tổng số lần chết tính từ đầu, ví dụ 39")
    async def deaths_cmd(interaction: discord.Interaction, count: app_commands.Range[int, 0, 100000]) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        store = _store(interaction)
        store.set_deaths(int(count))
        await store.save()
        total = store.config.deaths_total
        realm = texts.realm_for(total)
        nxt = texts.next_realm(total)
        if nxt is None:
            tail = "đã ở bậc cuối, không còn bậc nào tệ hơn"
        else:
            tail = f"còn {nxt.index * texts.REALM_STEP - total} mạng → {nxt.cn}"
        body = (
            f"▸ Tổng kiếp: **#{total}**\n"
            f"▸ Cảnh giới: **{realm.label}** — {realm.status}\n"
            f"▸ {tail}"
        )
        await interaction.followup.send(embed=_panel("命 · Tổng kiếp", body, COLOUR_OK), ephemeral=True)

    @group.command(name="player", description="Ghim người đang chơi — tên và avatar hiện trong embed")
    @app_commands.describe(member="Người chơi (bỏ trống = xoá, embed dùng tên bot)")
    async def player_cmd(interaction: discord.Interaction, member: discord.Member | None = None) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        store = _store(interaction)
        store.set_player(member)
        await store.save()
        if member is None:
            await interaction.followup.send(
                embed=_panel("已 · Người chơi", "▸ Đã xoá người chơi — embed dùng tên bot.", COLOUR_OK),
                ephemeral=True,
            )
        else:
            body = (
                f"▸ {member.mention} — **{member.display_name}**\n"
                "▸ Avatar của họ sẽ hiện cạnh tên trong embed."
            )
            await interaction.followup.send(embed=_panel("已 · Người chơi", body, COLOUR_OK), ephemeral=True)

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
            await interaction.followup.send(
                embed=_panel("Không thêm được", f"▸ {exc}", COLOUR_WARN), ephemeral=True
            )
            return
        await store.save()
        mode = "ảnh" if store.image_for(channel.id) else "không ảnh"
        head = "Đã thêm kênh" if added else "Đã cập nhật kênh"
        lines = [
            f"▸ {channel.mention} → chế độ **{mode}**",
            f"▸ {len(store.channel_ids())}/{MAX_CHANNELS} kênh nhận thông báo",
        ]
        if warn:
            lines.append(f"▸ Cảnh báo: {warn}")
        await interaction.followup.send(
            embed=_panel(head, "\n".join(lines), COLOUR_WARN if warn else COLOUR_OK), ephemeral=True
        )

    @group.command(name="remove", description="Bỏ một kênh khỏi danh sách nhận thông báo")
    @app_commands.describe(channel="Kênh cần bỏ")
    async def remove_cmd(interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        store = _store(interaction)
        if store.is_anchor(channel.id):
            await interaction.followup.send(
                embed=_panel(
                    "Không bỏ được",
                    f"▸ {channel.mention} đang giữ message cấu hình.\n"
                    "▸ Chuyển neo trước: `/ktl setup channel:#kênh-khác`, rồi mới bỏ.",
                    COLOUR_WARN,
                ),
                ephemeral=True,
            )
            return
        removed = store.remove_channel(channel.id)
        await store.save()
        if removed:
            await interaction.followup.send(
                embed=_panel(
                    "Đã bỏ kênh",
                    f"▸ {channel.mention} không còn nhận thông báo\n▸ còn {len(store.channel_ids())}/{MAX_CHANNELS} kênh",
                    COLOUR_OK,
                ),
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                embed=_panel("Không có trong danh sách", f"▸ {channel.mention} chưa từng được thêm.", COLOUR_WARN),
                ephemeral=True,
            )

    @group.command(name="list", description="Xem các kênh đang nhận thông báo")
    async def list_cmd(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        store = _store(interaction)
        cfg = store.config
        if not cfg.channels:
            await interaction.followup.send(
                embed=_panel(
                    "Chưa có kênh nào",
                    "▸ Thêm bằng `/ktl add channel:#kênh`\n▸ Rồi `/ktl preview` để xem embed mẫu",
                    COLOUR_WARN,
                ),
                ephemeral=True,
            )
            return
        lines = [f"▸ **{len(cfg.channels)}/{MAX_CHANNELS} kênh nhận thông báo**"]
        for channel_id in store.channel_ids():
            mode = "ảnh" if store.image_for(channel_id) else "không ảnh"
            anchor = " · giữ cấu hình" if store.is_anchor(channel_id) else ""
            lines.append(f"▸ <#{channel_id}> — {mode}{anchor}")
        lines.append(f"▸ mặc định: {'ảnh' if cfg.default_image else 'không ảnh'}")
        lines.append(f"▸ trạng thái: {'tạm ngưng' if cfg.paused else 'đang chạy'}")
        await interaction.followup.send(embed=_panel("列 · Kênh nhận thông báo", "\n".join(lines), COLOUR_INFO), ephemeral=True)

    @group.command(name="image", description="Ép chế độ ảnh cho một kênh")
    @app_commands.describe(channel="Kênh cần đổi", mode="Chế độ ảnh")
    @app_commands.choices(mode=MODE_CHOICES)
    async def image_cmd(interaction: discord.Interaction, channel: discord.TextChannel, mode: app_commands.Choice[str]) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        store = _store(interaction)
        if not store.set_channel_image(channel.id, _mode_to_image(mode.value)):
            await interaction.followup.send(
                embed=_panel(
                    "Chưa có kênh này",
                    f"▸ {channel.mention} chưa có trong danh sách\n▸ Dùng `/ktl add` trước",
                    COLOUR_WARN,
                ),
                ephemeral=True,
            )
            return
        await store.save()
        current = "bật" if store.image_for(channel.id) else "tắt"
        body = f"▸ {channel.mention}: **{mode.name}**\n▸ hiện tại đang {current} ảnh"
        await interaction.followup.send(embed=_panel("圖 · Chế độ ảnh", body, COLOUR_OK), ephemeral=True)

    @group.command(name="default-image", description="Chế độ ảnh mặc định cho mọi kênh")
    @app_commands.describe(mode="Mặc định bật hay tắt ảnh")
    @app_commands.choices(mode=[MODE_CHOICES[0], MODE_CHOICES[1]])
    async def default_image_cmd(interaction: discord.Interaction, mode: app_commands.Choice[str]) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        store = _store(interaction)
        store.set_default_image(mode.value == MODE_ON)
        await store.save()
        text = "▸ Mặc định: **bật ảnh**" if mode.value == MODE_ON else "▸ Mặc định: **tắt ảnh**"
        await interaction.followup.send(
            embed=_panel("圖 · Mặc định", text + "\n▸ Kênh đã ép riêng thì giữ nguyên.", COLOUR_OK), ephemeral=True
        )

    @group.command(name="test", description="Gửi một thông báo mẫu thật vào kênh để xem embed")
    @app_commands.describe(channel="Gửi thử vào kênh này (bỏ trống = kênh đầu tiên)")
    async def test_cmd(interaction: discord.Interaction, channel: discord.TextChannel | None = None) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        store = _store(interaction)
        target = channel
        if target is None:
            ids = store.channel_ids()
            if not ids:
                await interaction.followup.send(
                    embed=_panel(
                        "Chưa có kênh nào",
                        "▸ Thêm bằng `/ktl add channel:#kênh`\n▸ Chỉ muốn xem embed: `/ktl preview`",
                        COLOUR_WARN,
                    ),
                    ephemeral=True,
                )
                return
            target = interaction.client.get_channel(ids[0])  # type: ignore[attr-defined]
            if target is None:
                await interaction.followup.send(
                    embed=_panel("Không tìm thấy kênh", "▸ Thử truyền `channel` cho lệnh này.", COLOUR_WARN),
                    ephemeral=True,
                )
                return
        error = await _notifier(interaction).send_test(target.id)
        if error:
            await interaction.followup.send(
                embed=_panel("Gửi thất bại", f"▸ {target.mention}\n▸ {error}", COLOUR_WARN), ephemeral=True
            )
        else:
            await interaction.followup.send(
                embed=_panel(
                    "Đã gửi thông báo mẫu",
                    f"▸ đã đăng vào {target.mention}\n▸ không đụng tới tổng kiếp hay liên tử",
                    COLOUR_OK,
                ),
                ephemeral=True,
            )

    @group.command(name="preview", description="Xem đúng embed sẽ hiện mỗi lần chết (chỉ mình bạn thấy)")
    @app_commands.describe(image="Bật/tắt ảnh minh hoạ (bỏ trống = theo chế độ mặc định)")
    async def preview_cmd(interaction: discord.Interaction, image: bool | None = None) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        notifier = _notifier(interaction)
        if notifier is None:
            await interaction.followup.send(
                embed=_panel("Chưa sẵn sàng", "▸ Bot chưa khởi động xong, thử lại sau vài giây.", COLOUR_WARN),
                ephemeral=True,
            )
            return
        try:
            embed, files = notifier.build_preview(image)
        except ValueError as exc:
            await interaction.followup.send(
                embed=_panel("Không dựng được embed", f"▸ {exc}", COLOUR_WARN), ephemeral=True
            )
            return
        # Không ghi đè footer: xem trước phải giống hệt bản sẽ đăng lên kênh.
        kwargs: dict = {"embed": embed, "ephemeral": True}
        if files:
            kwargs["files"] = files
        await interaction.followup.send(**kwargs)

    @group.command(name="status", description="Xem trạng thái bot và thống kê")
    async def status_cmd(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        store = _store(interaction)
        cfg = store.config
        state = getattr(interaction.client, "web_state", None)
        realm = texts.realm_for(cfg.deaths_total)
        nxt = texts.next_realm(cfg.deaths_total)
        if nxt is None:
            realm_tail = "bậc cuối"
        else:
            realm_tail = f"còn {nxt.index * texts.REALM_STEP - cfg.deaths_total} mạng → {nxt.cn}"
        lines = [
            f"▸ kênh: {len(cfg.channels)}/{MAX_CHANNELS} · mặc định {'ảnh' if cfg.default_image else 'không ảnh'}",
            f"▸ trạng thái: {'tạm ngưng' if cfg.paused else 'đang chạy'}",
            f"▸ tổng kiếp: #{cfg.deaths_total} · cảnh giới: {realm.label} ({realm_tail})",
            f"▸ người chơi: {cfg.player_name or '—'}",
            f"▸ neo cấu hình: {f'<#{store.config_channel_id}>' if store.config_channel_id else '—'}",
            f"▸ cấu hình đọc từ: {store.describe_source()}",
            f"▸ đã nhận: {cfg.stats.get('received', 0)} lần chết · lần cuối: {cfg.stats.get('last_death_utc', '—')}",
        ]
        if state is not None:
            lines.append(f"▸ uptime tiến trình: {state.uptime_s / 3600:.1f} giờ · từ chối: {state.rejected}")
        await interaction.followup.send(
            embed=_panel("氣絕錄 · Khí Tuyệt Lục", "\n".join(lines), COLOUR_INFO), ephemeral=True
        )

    @group.command(name="pause", description="Tạm ngưng gửi thông báo (tracker vẫn được nhận)")
    async def pause_cmd(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        store = _store(interaction)
        store.set_paused(True)
        await store.save()
        await interaction.followup.send(
            embed=_panel("已 · Tạm ngưng", "▸ Bot không đăng thông báo nữa\n▸ Tracker vẫn gửi được, không mất event\n▸ Bật lại: `/ktl resume`", COLOUR_WARN),
            ephemeral=True,
        )

    @group.command(name="resume", description="Chạy tiếp thông báo")
    async def resume_cmd(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        store = _store(interaction)
        store.set_paused(False)
        await store.save()
        await interaction.followup.send(
            embed=_panel("已 · Chạy tiếp", "▸ Thông báo tử vong đã bật lại.", COLOUR_OK), ephemeral=True
        )

    @group.command(name="help", description="Xem toàn bộ lệnh và cách dùng nhanh")
    async def help_cmd(interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        embed = discord.Embed(
            title="氣絕錄 · Khí Tuyệt Lục",
            description="Bot báo tử vong từ PBZ Death Tracker. Nhóm `/ktl` chỉ admin dùng được.",
            colour=0x7A6440,
        )
        embed.add_field(
            name="▸ Lần đầu cài",
            value=(
                "`/ktl setup` — ghim cấu hình vào kênh thông báo (không tạo kênh riêng), gán bạn là người chơi\n"
                "`/ktl deaths count:39` — nhập số lần chết đã có từ trước khi dùng tool\n"
                "`/ktl add channel:#kênh` — thêm kênh nhận thông báo\n"
                "`/ktl player member:@ai` — đổi người chơi (bỏ trống = xoá)"
            ),
            inline=False,
        )
        embed.add_field(
            name="▸ Kênh & ảnh",
            value=(
                "`/ktl list` — xem kênh đang nhận thông báo\n"
                "`/ktl remove channel:#kênh` — bỏ kênh khỏi danh sách\n"
                "`/ktl image channel:#kênh mode:…` — ép chế độ ảnh cho một kênh\n"
                "`/ktl default-image mode:…` — chế độ ảnh mặc định mọi kênh"
            ),
            inline=False,
        )
        embed.add_field(
            name="▸ Vận hành",
            value=(
                "`/ktl preview` — xem đúng embed sẽ hiện mỗi lần chết (chỉ mình bạn thấy)\n"
                "`/ktl test` — gửi thông báo mẫu thật vào kênh để xem embed\n"
                "`/ktl status` — trạng thái bot, cảnh giới, thống kê\n"
                "`/ktl pause` · `/ktl resume` — tạm ngưng / chạy tiếp\n"
                "`/ktl help` — bảng này"
            ),
            inline=False,
        )
        embed.set_footer(text="Cảnh giới: 15 bậc, mỗi bậc 50 mạng, tối đa 700 (無間)")
        await interaction.followup.send(embed=embed, ephemeral=True)

    return group


def setup_commands(bot) -> None:
    bot.tree.add_command(build_group())

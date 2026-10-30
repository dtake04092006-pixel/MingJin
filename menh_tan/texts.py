"""Kho chữ cho embed: câu thơ, Hán tự, bậc chuyển, tầng ma khí.

Không dùng emoji — chỉ Hán tự và ký tự trang trí, để hiển thị giống nhau trên
mọi thiết bị và giữ đúng chất kiếm hiệp.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

SEAL = "乂乂乂乂乂乂乂乂乂乂乂乂"

# 12 câu, chọn ngẫu nhiên không lặp lại câu vừa dùng
VERSES: tuple[str, ...] = (
    "Ma khí quấn thân, huyết vụ tản ra như khói nhang tàn.\nNgươi ngã xuống — bia đá lạnh khắc thêm một vết.",
    "Đao chưa kịp rút, ánh mắt đã tối.\nGiang hồ không nhớ tên kẻ bại trận, chỉ nhớ vết máu còn ướt.",
    "Khí hải nghịch hành, tâm ma trỗi dậy.\nThân xác này chưa chịu nằm yên.",
    "Âm phong thổi ngược, đèn lồng tắt lịm.\nMột hơi thở cuối rơi xuống như lá úa đầu đông.",
    "Huyết mạch đứt đoạn, chân nguyên tán loạn.\nNgười chết không oán — chỉ có kiếm là còn ngân.",
    "Bóng áo trắng lướt qua, và ngươi đã không còn đứng đó.\nLuân hồi chưa cho phép ngươi đi.",
    "Ngũ tạng như bị xé, tiếng xương vỡ rõ hơn cả tiếng thở.\nNgươi vẫn chưa chịu quỳ.",
    "Một chiêu, một mạng.\nKiếm khí tan rồi, người cũng tan.",
    "Sương độc phủ lên vết thương, sắc mặt trắng như giấy tiền.\nMa đạo đã gọi tên ngươi.",
    "Ngươi chết giữa chợ người, trong im lặng.\nKhông ai quay lại.",
    "Chân khí cạn, hộ thể thân phá.\nNgươi quỳ xuống giữa vũng máu của chính mình.",
    "Mệnh hỏa lụi dần, tàn tro bay lên thành một chữ 命.",
)

# Câu thêm khi chết liên tiếp (≤ 90 giây so với lần trước)
STREAK_VERSES: tuple[str, ...] = (
    "Chết lại quá nhanh — ma khí trong ngươi chưa kịp tản.",
    "Bia đá chưa khô máu, ngươi đã quay lại.",
    "Diêm vương còn chưa kịp ghi tên, ngươi đã nộp mạng lần nữa.",
    "Tâm ma dẫn đường, ngươi lao đầu vào lưỡi đao như thiêu thân.",
)

TURNS_CN: tuple[str, ...] = ("第一", "第二", "第三", "第四", "第五", "第六", "第七", "第八", "第九", "第十")
TURNS_VI: tuple[str, ...] = ("Nhất", "Nhị", "Tam", "Tứ", "Ngũ", "Lục", "Thất", "Bát", "Cửu", "Thập")


@dataclass(frozen=True, slots=True)
class Tier:
    colour: int
    name: str
    suffix: str


TIERS: tuple[Tier, ...] = (
    Tier(0x7B0C0C, "Huyết khí sơ sinh", ""),
    Tier(0x9B0F0F, "Huyết khí dày", ""),
    Tier(0xB81313, "Sát khí quanh thân", ""),
    Tier(0xD41A1A, "Nhập Ma", " · 入魔"),
)

STREAK_TITLES = {3: " · 連死", 5: " · 五連", 7: " · 七連"}


def turn_label(death_no: int | None) -> tuple[str, str]:
    """(Hán tự, âm Việt) cho lần chết thứ n. n>10 thì chỉ trả về số."""
    if not death_no or death_no < 1:
        return "", ""
    if death_no > 10:
        return "", str(death_no)
    index = death_no - 1
    return TURNS_CN[index], TURNS_VI[index]


def tier_for(total_deaths: int | None) -> Tier:
    total = total_deaths or 0
    if total >= 25:
        return TIERS[3]
    if total >= 10:
        return TIERS[2]
    if total >= 5:
        return TIERS[1]
    return TIERS[0]


def streak_suffix(streak: int) -> str:
    if streak >= 7:
        return STREAK_TITLES[7]
    if streak >= 5:
        return STREAK_TITLES[5]
    if streak >= 3:
        return STREAK_TITLES[3]
    return ""


class VersePicker:
    """Chọn câu thơ, tránh lặp lại câu vừa dùng."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self._rng = rng or random.Random()
        self._last: str | None = None

    def pick(self) -> str:
        pool = [v for v in VERSES if v != self._last] or list(VERSES)
        choice = self._rng.choice(pool)
        self._last = choice
        return choice

    def streak_line(self) -> str:
        return self._rng.choice(STREAK_VERSES)


def format_duration(seconds: float | None) -> str:
    """'2 phút 41 giây' / '1 giờ 12 phút' / '—'."""
    if seconds is None:
        return "—"
    total = int(round(seconds))
    if total < 0:
        return "—"
    if total < 1:
        return "sát nút"
    if total < 60:
        return f"{total} giây"
    if total < 3600:
        minutes, sec = divmod(total, 60)
        return f"{minutes} phút {sec} giây" if sec else f"{minutes} phút"
    hours, rest = divmod(total, 3600)
    minutes = rest // 60
    return f"{hours} giờ {minutes} phút" if minutes else f"{hours} giờ"


def format_elapsed(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    total = int(round(seconds))
    minutes, sec = divmod(total, 60)
    if minutes < 60:
        return f"{minutes:02d}:{sec:02d}"
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{sec:02d}"

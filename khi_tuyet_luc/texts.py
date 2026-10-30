"""Kho chữ cho embed: câu thơ, Hán tự, bậc chuyển, tầng ma khí.

Trang trí bằng hai nhãn emoji duy nhất (🩸 câu thơ, ⚡ liên tử), phần còn lại là
Hán tự. Không kẻ khung, không lặp ký tự thành dãy dài — nhìn đỡ rối mắt.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

VERSE_MARK = "🩸"   # nhãn câu thơ (thay cho dãy 乂 dày đặc trước đây)
STREAK_MARK = "⚡"  # nhãn câu liên tử

# 12 câu, mỗi câu một dòng — đọc một nhịp là hiểu, không lan man
VERSES: tuple[str, ...] = (
    "Ma khí quấn thân, huyết vụ tàn như khói nhang.",
    "Đao chưa rút, mắt đã tối.",
    "Khí hải nghịch hành, tâm ma trỗi dậy.",
    "Âm phong thổi ngược, đèn lồng tắt lịm.",
    "Huyết mạch đứt đoạn, chân nguyên tán loạn.",
    "Bóng áo trắng lướt qua, ngươi đã ngã.",
    "Ngũ tạng như xé, ngươi vẫn chưa quỳ.",
    "Một chiêu, một mạng.",
    "Sương độc phủ vết thương, mặt trắng như giấy tiền.",
    "Ngươi chết giữa chợ người, trong im lặng.",
    "Chân khí cạn, hộ thể thân phá.",
    "Mệnh hỏa lụi dần, tàn tro thành chữ 命.",
)

# Câu thêm khi chết liên tiếp (≤ 90 giây so với lần trước)
STREAK_VERSES: tuple[str, ...] = (
    "Ma khí chưa tản, ngươi đã quay lại.",
    "Bia đá chưa khô máu.",
    "Diêm vương chưa kịp ghi tên.",
    "Tâm ma dẫn lối, lao vào lưỡi đao.",
)

TURNS_CN: tuple[str, ...] = ("第一", "第二", "第三", "第四", "第五", "第六", "第七", "第八", "第九", "第十")
TURNS_VI: tuple[str, ...] = ("Nhất", "Nhị", "Tam", "Tứ", "Ngũ", "Lục", "Thất", "Bát", "Cửu", "Thập")


REALM_STEP = 50
REALM_MAX = 500  # mốc 無間 — quá mốc này thì đứng yên


@dataclass(frozen=True, slots=True)
class Realm:
    """Một bậc cảnh giới, tính theo tổng kiếp do bot tự đếm."""

    index: int
    cn: str
    vi: str
    status: str
    colour: int

    @property
    def label(self) -> str:
        return f"{self.cn} · {self.vi}"


REALMS: tuple[Realm, ...] = (
    # Dải màu đi từ ngọc bích (sạch) → đồng thau → son → huyết khô → gần đen.
    # Độ sáng giảm đều mỗi bậc, nên càng chết nhiều embed càng tối.
    Realm(0, "未染", "Vô Nhiễm", "tay còn sạch", 0x2E8B6E),
    Realm(1, "染血", "Nhiễm Huyết", "vết máu đầu đã khô", 0x8A5A2B),
    Realm(2, "傷痕", "Thương Ngân", "thân đầy sẹo, bước đã chậm", 0x8F4526),
    Realm(3, "煞氣", "Sát Khí", "quỷ thần tránh xa", 0x8C3422),
    Realm(4, "血債", "Huyết Trái", "nợ máu chồng nợ máu", 0x87241F),
    Realm(5, "入魔", "Nhập Ma", "ma khí vào gân cốt", 0x7A1A22),
    Realm(6, "業障", "Nghiệp Chướng", "nghiệp cũ quấn cổ chân", 0x6B1623),
    Realm(7, "幽途", "U Đồ", "đường âm chỉ một lối", 0x5C1223),
    Realm(8, "輪迴", "Luân Hồi", "quên cả tên mình", 0x4E0F20),
    Realm(9, "修羅", "Tu La", "sát nghiệp không dứt", 0x420C1B),
    Realm(10, "無間", "Vô Gián", "không còn lối ra", 0x360A15),
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


def realm_for(total_deaths: int | None) -> Realm:
    """Bậc cảnh giới theo tổng kiếp; quá 500 thì đứng ở 無間."""
    total = max(0, int(total_deaths or 0))
    return REALMS[min(total // REALM_STEP, len(REALMS) - 1)]


def next_realm(total_deaths: int | None) -> Realm | None:
    realm = realm_for(total_deaths)
    if realm.index >= len(REALMS) - 1:
        return None
    return REALMS[realm.index + 1]


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

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

HAN_DIGITS: tuple[str, ...] = ("〇", "一", "二", "三", "四", "五", "六", "七", "八", "九")
VI_DIGITS: tuple[str, ...] = ("Không", "Nhất", "Nhị", "Tam", "Tứ", "Ngũ", "Lục", "Thất", "Bát", "Cửu")
HAN_UNITS = ((1000, "千", "Thiên"), (100, "百", "Bách"), (10, "十", "Thập"))
TURN_MAX = 9999  # quá mốc này thì thôi đánh vần, chỉ ghi số


REALM_STEP = 50
REALM_MAX = 700  # mốc 無間 — quá mốc này thì đứng yên


@dataclass(frozen=True, slots=True)
class Realm:
    """Một bậc cảnh giới, tính theo tổng kiếp do bot tự đếm."""

    index: int
    cn: str
    vi: str
    status: str
    colour: int
    glyph: str  # ký tự Hán lớn in chìm ở ảnh số đếm (xem badge.py)

    @property
    def label(self) -> str:
        return f"{self.cn} · {self.vi}"


REALMS: tuple[Realm, ...] = (
    # 15 bậc × 50 mạng → 無間 ở mốc 700. Dải màu đi từ ngọc bích (sạch) → đồng
    # thau → gạch nung → huyết tươi → huyết khô → gần đen; độ sáng giảm đều mỗi
    # bậc nên càng chết nhiều embed càng tối (badge.py cũng tối dần theo bậc).
    Realm(0, "未染", "Vô Nhiễm", "tay còn sạch", 0x2E8B6E, "淨"),
    Realm(1, "染血", "Nhiễm Huyết", "vết máu đầu đã khô", 0x9F632E, "血"),
    Realm(2, "傷痕", "Thương Ngân", "thân đầy sẹo, bước đã chậm", 0xA6562E, "傷"),
    Realm(3, "煞氣", "Sát Khí", "quỷ thần tránh xa", 0xA74A2E, "煞"),
    Realm(4, "血債", "Huyết Trái", "nợ máu chồng nợ máu", 0xA93F2E, "債"),
    Realm(5, "入魔", "Nhập Ma", "ma khí vào gân cốt", 0xA5342F, "魔"),
    Realm(6, "骨寒", "Cốt Hàn", "lạnh buốt tận xương", 0x9A2D30, "骨"),
    Realm(7, "業障", "Nghiệp Chướng", "nghiệp cũ quấn cổ chân", 0x862731, "業"),
    Realm(8, "幽途", "U Đồ", "đường âm một lối", 0x72222E, "幽"),
    Realm(9, "黃泉", "Hoàng Tuyền", "suối vàng đã gọi", 0x601D2A, "泉"),
    Realm(10, "輪迴", "Luân Hồi", "quên cả tên mình", 0x4F1825, "輪"),
    Realm(11, "修羅", "Tu La", "sát nghiệp không dứt", 0x421421, "羅"),
    Realm(12, "忘川", "Vong Xuyên", "uống nước quên kiếp", 0x35111B, "川"),
    Realm(13, "阿鼻", "A Tỳ", "đọa vào a tỳ", 0x290E17, "獄"),
    Realm(14, "無間", "Vô Gián", "không còn lối ra", 0x1E0A11, "無"),
)

STREAK_TITLES = {3: " · 連死", 5: " · 五連", 7: " · 七連"}


def _spell(number: int) -> tuple[str, str]:
    """Đánh vần số 1..9999: 47 → (四十七, Tứ Thập Thất), 105 → (一百零五, Nhất Bách Linh Ngũ)."""
    han: list[str] = []
    vi: list[str] = []
    rest = number
    gap = False  # có chỗ trống giữa hai hàng → phải chèn 零/Linh
    for unit, han_unit, vi_unit in HAN_UNITS:
        if rest < unit:
            continue
        digit, rest = divmod(rest, unit)
        if gap:
            han.append("零")
            vi.append("Linh")
            gap = False
        if not (unit == 10 and digit == 1 and not han):  # 10 = 十, không phải 一十
            han.append(HAN_DIGITS[digit])
            vi.append(VI_DIGITS[digit])
        han.append(han_unit)
        vi.append(vi_unit)
        gap = 0 < rest < unit // 10
    if rest:
        if gap:
            han.append("零")
            vi.append("Linh")
        han.append(HAN_DIGITS[rest])
        vi.append(VI_DIGITS[rest])
    return "".join(han), " ".join(vi)


def turn_label(number: int | None) -> tuple[str, str]:
    """(Hán tự, âm Việt) cho lần thứ n: 3 → (第三, Tam), 47 → (第四十七, Tứ Thập Thất)."""
    if not number or number < 1:
        return "", ""
    if number > TURN_MAX:
        return "", str(number)
    han, vi = _spell(int(number))
    return f"第{han}", vi


def realm_for(total_deaths: int | None) -> Realm:
    """Bậc cảnh giới theo tổng kiếp; quá 700 thì đứng ở 無間."""
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

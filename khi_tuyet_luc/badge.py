"""Vẽ ảnh số đếm tổng kiếp để gắn vào góc phải embed (thumbnail).

Discord không cho tô màu chữ trong embed, nên con số lớn "đúng màu cảnh giới"
phải là ảnh. Ảnh nền trong suốt → đẹp trên cả theme sáng lẫn tối.

Thiếu Pillow thì trả None và embed vẫn gửi bình thường (không có số ở góc).
"""

from __future__ import annotations

import colorsys
import functools
import io

try:  # chỉ cần cho ảnh số đếm
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover - môi trường không cài Pillow
    Image = None  # type: ignore[assignment]

SIZE = 320          # vẽ lớn rồi để Discord thu nhỏ → nét hơn
PAD = 14            # chừa chỗ cho vòng tròn
RING_WIDTH = 7
MAX_TEXT = SIZE - PAD * 2 - 56  # chừa lề để số 3–4 chữ số không chạm vòng tròn
TEXT_LIGHT = 0.52   # giữ đúng sắc cảnh giới nhưng đủ sáng để đọc trên nền tối
SAT_MIN = 0.62      # bậc cuối gần đen → kéo độ no màu lên để vẫn ra màu huyết
RING_LIGHT = 0.34   # vòng tròn trầm hơn số một chút


def _hls_colour(colour: int, lightness: float) -> tuple[int, int, int]:
    """Giữ nguyên sắc độ cảnh giới, chỉ nâng độ sáng — không pha trắng thành xám."""
    r, g, b = (colour >> 16) & 255, (colour >> 8) & 255, colour & 255
    hue, light, sat = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    light = max(light, lightness)
    sat = max(sat, SAT_MIN)
    r2, g2, b2 = colorsys.hls_to_rgb(hue, light, sat)
    return int(r2 * 255), int(g2 * 255), int(b2 * 255)


def lit_colour(colour: int, lightness: float = TEXT_LIGHT) -> tuple[int, int, int]:
    """Màu cho con số: đúng tông cảnh giới, nâng sáng vừa đủ để không chìm vào nền."""
    return _hls_colour(colour, lightness)


def _fit_font(draw, text: str, box: int):
    size = box + 40
    while size > 24:
        try:
            font = ImageFont.load_default(size)
        except TypeError:  # Pillow cũ: font mặc định không phóng được
            font = ImageFont.load_default()
            return font, draw.textbbox((0, 0), text, font=font)
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        if right - left <= box and bottom - top <= box:
            return font, (left, top, right, bottom)
        size -= 10
    font = ImageFont.load_default()
    return font, draw.textbbox((0, 0), text, font=font)


@functools.lru_cache(maxsize=64)
def render_count_png(total: int, colour: int) -> bytes | None:
    """PNG trong suốt: số lần chết ở giữa, vòng tròn mảnh cùng tông bao quanh."""
    if Image is None:
        return None

    text = str(max(0, int(total)))
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    r, g, b = lit_colour(colour)
    ring = _hls_colour(colour, RING_LIGHT)

    draw.ellipse(
        (PAD, PAD, SIZE - PAD, SIZE - PAD),
        outline=(*ring, 140),
        width=RING_WIDTH,
    )

    font, (left, top, right, bottom) = _fit_font(draw, text, MAX_TEXT)
    width, height = right - left, bottom - top
    draw.text(
        ((SIZE - width) / 2 - left, (SIZE - height) / 2 - top),
        text,
        font=font,
        fill=(r, g, b, 255),
    )

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()

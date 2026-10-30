"""Vẽ ảnh số đếm tổng kiếp để gắn vào góc phải embed (thumbnail).

Phong cách: một vết máu bắn ra, con số bị khoét rỗng ở giữa — như ai đó viết số
bằng máu rồi cạo thủng. Bậc càng cao thì vết máu càng nham nhở: nhiều tia bắn,
nhiều vệt rỉ chảy dài, và từ giữa đường còn có vết cào xé.

Discord không cho tô màu chữ, nên con số "đúng màu cảnh giới" phải là ảnh.
Ảnh nền trong suốt → đẹp trên cả theme sáng lẫn tối. Cùng (số, màu, bậc) luôn
ra cùng một ảnh nhờ random có seed; thiếu Pillow thì trả None, embed vẫn gửi.
"""

from __future__ import annotations

import colorsys
import functools
import io
import math
import random

try:  # chỉ cần cho ảnh số đếm
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover - môi trường không cài Pillow
    Image = None  # type: ignore[assignment]

SIZE = 340          # vẽ lớn rồi để Discord thu nhỏ → nét hơn
RADIUS = 112        # bán kính vết máu chính
LIGHT_FLOOR = 0.30  # sàn độ sáng: bậc 無間 gần đen vẫn phải thấy trên nền tối
SAT_FLOOR = 0.48
MAX_LEVEL = 14


def _hls(colour: int, lightness: float) -> tuple[int, int, int]:
    """Giữ đúng sắc cảnh giới, chỉ nâng độ sáng — không pha trắng thành xám."""
    r, g, b = (colour >> 16) & 255, (colour >> 8) & 255, colour & 255
    hue, light, sat = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    r2, g2, b2 = colorsys.hls_to_rgb(hue, max(light, lightness), max(sat, SAT_FLOOR))
    return int(r2 * 255), int(g2 * 255), int(b2 * 255)


def lit_colour(colour: int, lightness: float | None = None) -> tuple[int, int, int]:
    """Màu của vết máu: đúng tông cảnh giới, đủ sáng để không chìm vào nền."""
    return _hls(colour, LIGHT_FLOOR if lightness is None else lightness)


def _digits_layer(text: str, box: int, stroke: int, fill, stroke_fill) -> tuple[object, int]:
    """Lớp chữ cỡ lớn đúng giữa khung. Trả (layer, stroke_width) để dùng lại vị trí."""
    layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    size = box + 80
    while size > 24:
        try:
            font = ImageFont.load_default(size)
        except TypeError:  # Pillow cũ: font mặc định không phóng được
            font = ImageFont.load_default()
            break
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font, stroke_width=stroke)
        if right - left <= box and bottom - top <= box:
            break
        size -= 10
    draw.text(
        (SIZE / 2, SIZE / 2),
        text,
        font=font,
        fill=fill,
        anchor="mm",
        stroke_width=stroke,
        stroke_fill=stroke_fill,
    )
    return layer, stroke


def _splat_mask(rng: random.Random, rough: float, spikes: int, droplets: int):
    """Vết máu: thân méo, vài cục loang, tia bắn nhọn và các giọt li ti."""
    mask = Image.new("L", (SIZE, SIZE), 0)
    draw = ImageDraw.Draw(mask)
    centre = SIZE / 2
    phase_a, phase_b = rng.uniform(0, 6.3), rng.uniform(0, 6.3)

    points = []
    for step in range(160):
        angle = step / 160 * 2 * math.pi
        radius = RADIUS * (
            1
            + rough * math.sin(3 * angle + phase_a)
            + rough * 0.6 * math.sin(9 * angle + phase_b)
            + rough * 0.3 * math.sin(17 * angle + phase_a)
        )
        points.append((centre + radius * math.cos(angle), centre + radius * math.sin(angle)))
    draw.polygon(points, fill=255)

    for _ in range(rng.randint(5, 8)):  # cục loang quanh thân
        angle = rng.uniform(0, 2 * math.pi)
        distance = RADIUS * rng.uniform(0.45, 0.82)
        blob = RADIUS * rng.uniform(0.22, 0.38)
        x, y = centre + distance * math.cos(angle), centre + distance * math.sin(angle)
        draw.ellipse((x - blob, y - blob, x + blob, y + blob), fill=255)

    for _ in range(spikes):  # tia máu bắn ra
        angle = rng.uniform(0, 2 * math.pi)
        near, far = RADIUS * 0.88, RADIUS * rng.uniform(1.10, 1.34)
        spread = rng.uniform(0.03, 0.09)
        draw.polygon(
            [
                (centre + near * math.cos(angle - spread), centre + near * math.sin(angle - spread)),
                (centre + near * math.cos(angle + spread), centre + near * math.sin(angle + spread)),
                (centre + far * math.cos(angle), centre + far * math.sin(angle)),
            ],
            fill=255,
        )

    for _ in range(droplets):  # giọt li ti văng ra
        angle = rng.uniform(0, 2 * math.pi)
        distance = RADIUS * rng.uniform(1.0, 1.34)
        size = rng.uniform(2, 6.5)
        x, y = centre + distance * math.cos(angle), centre + distance * math.sin(angle)
        draw.ellipse((x - size, y - size, x + size, y + size), fill=255)
    return mask


def _drip(draw, x: float, y0: float, length: float, width: float, colour) -> None:
    """Một vệt máu rỉ xuống: thân thuôn + giọt tròn ở đầu."""
    tail = width * 0.45
    draw.polygon(
        [(x - width, y0), (x + width, y0), (x + tail, y0 + length), (x - tail, y0 + length)],
        fill=colour,
    )
    draw.ellipse(
        (x - tail * 1.8, y0 + length - tail * 1.8, x + tail * 1.8, y0 + length + tail * 1.8),
        fill=colour,
    )


def _gashes(mask, rng: random.Random, count: int) -> None:
    """Vết cào xé: xoá hẳn vài đường chéo nham nhở khỏi vết máu."""
    draw = ImageDraw.Draw(mask)
    for _ in range(count):
        angle = rng.uniform(-1.2, 1.2)
        start_x = rng.uniform(RADIUS * 0.2, RADIUS * 1.5)
        start_y = rng.uniform(RADIUS * 0.1, RADIUS * 1.7)
        points = []
        for step in range(9):
            points.append(
                (
                    start_x + math.cos(angle) * step * RADIUS * 0.12 + rng.uniform(-3, 3),
                    start_y + math.sin(angle) * step * RADIUS * 0.12 + rng.uniform(-3, 3),
                )
            )
        draw.line(points, fill=0, width=rng.randint(3, 6))


@functools.lru_cache(maxsize=96)
def render_count_png(total: int, colour: int, level: int = 0) -> bytes | None:
    """PNG trong suốt: vết máu + con số khoét rỗng, càng lên bậc càng nham nhở."""
    if Image is None:
        return None

    total = max(0, int(total))
    level = max(0, min(int(level), MAX_LEVEL))
    text = str(total)
    rng = random.Random(total * 2654435761 + colour * 40503 + level)
    blood = lit_colour(colour)

    mask = _splat_mask(
        rng,
        rough=0.10 + level * 0.004,
        spikes=3 + level // 3,
        droplets=7 + level // 2,
    )
    if level >= 5:
        _gashes(mask, rng, 1 + (level >= 10))

    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    # Bậc càng cao thì vết máu càng chìm vào nền (alpha giảm) — vẫn thấy nhưng tối hơn.
    alpha = 236 - level * 4
    image.paste(Image.new("RGBA", (SIZE, SIZE), (*blood, alpha)), (0, 0), mask)

    draw = ImageDraw.Draw(image)
    for _ in range(2 + level // 4):
        _drip(
            draw,
            x=SIZE / 2 + rng.uniform(-RADIUS * 0.55, RADIUS * 0.55),
            y0=SIZE / 2 + RADIUS * rng.uniform(0.55, 0.75),
            length=rng.uniform(26, 64),
            width=rng.uniform(4, 7),
            colour=(*blood, alpha),
        )

    box = 150 if len(text) <= 2 else 168
    digits, _ = _digits_layer(
        text, box, stroke=9, fill=(255, 255, 255, 255), stroke_fill=(255, 255, 255, 255)
    )
    image.paste(Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0)), (0, 0), digits.split()[3])

    # Viền sáng men theo mép khoét: số vẫn đọc được dù vết máu đã sẫm gần đen.
    rim, _ = _digits_layer(text, box, stroke=5, fill=None, stroke_fill=(*_hls(colour, 0.72), 135))
    image.alpha_composite(rim)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()

"""Vẽ ảnh số đếm tổng kiếp để gắn vào góc phải embed (thumbnail).

Phong cách: một ký tự Hán lớn (đổi theo cảnh giới, càng lên bậc càng tối) nằm chìm
ở nửa trên-trái; dọc mép phải là một **cột** chữ Hán nhỏ (số kiếp đánh vần, cũng tối
dần theo bậc) như dòng đề trên bức khắc; còn vết máu bắn ra — với con số bị khoét
rỗng ở giữa — đóng dấu ở góc dưới bên phải. Bậc càng cao thì vết máu càng nham nhở:
nhiều tia bắn, nhiều vệt rỉ chảy dài, và từ giữa đường còn có vết cào xé.

Discord không cho tô màu chữ, nên con số "đúng màu cảnh giới" phải là ảnh.
Ảnh nền trong suốt → đẹp trên cả theme sáng lẫn tối. Cùng (số, màu, bậc, ký tự) luôn
ra cùng một ảnh nhờ random có seed; thiếu Pillow thì trả None, embed vẫn gửi.
Ký tự Hán nằm sẵn trong `glyphs/*.png` (mặt nạ trắng, tên = mã Unicode) để server
không cần font CJK — gồm cả các chữ số 一二三四五六七八九十百千零 cho cột bên phải.
"""

from __future__ import annotations

import colorsys
import functools
import io
import math
import random
from pathlib import Path

try:  # chỉ cần cho ảnh số đếm
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover - môi trường không cài Pillow
    Image = None  # type: ignore[assignment]

from . import texts

SIZE = 340           # vẽ lớn rồi để Discord thu nhỏ → nét hơn
LIGHT_FLOOR = 0.30   # sàn độ sáng: bậc 無間 gần đen vẫn phải thấy trên nền tối
SAT_FLOOR = 0.48
MAX_LEVEL = 14
GLYPH_LIGHT = 0.34   # ký tự lớn chìm phía sau, bậc đầu còn hơi sáng
GLYPH_STEP = 0.014   # mỗi bậc tối thêm chừng này → bậc cuối gần như chạm đáy
GLYPH_DIR = Path(__file__).with_name("glyphs")

# Bố cục theo tỉ lệ cạnh ảnh: chữ lớn trên-trái, cột chữ dọc mép phải,
# vết máu + số ở dưới-phải.
GLYPH_CX, GLYPH_CY = 0.41, 0.45
GLYPH_SCALE = 0.74
BLOOD_CX, BLOOD_CY = 0.67, 0.68
BLOOD_R = 0.30
BOX_SHORT, BOX_LONG = 144, 162  # khung chữ số (≤2 chữ số / 3–4 chữ số): to như bản cũ
COLUMN_CX = 0.925              # cột chữ dọc sát mép phải, ngang tầm con số
COLUMN_TOP, COLUMN_BOTTOM = 0.46, 0.97
COLUMN_WIDTH = 0.128           # bề rộng tối đa một chữ trong cột
COLUMN_GAP = 0.008
COLUMN_LIGHT = 0.70            # cột chữ vẽ đè lên vết máu → phải sáng mới thấy
COLUMN_STEP = 0.006
COLUMN_ALPHA = 205


def _hls(colour: int, lightness: float) -> tuple[int, int, int]:
    """Giữ đúng sắc cảnh giới, chỉ nâng độ sáng — không pha trắng thành xám."""
    r, g, b = (colour >> 16) & 255, (colour >> 8) & 255, colour & 255
    hue, light, sat = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    r2, g2, b2 = colorsys.hls_to_rgb(hue, max(light, lightness), max(sat, SAT_FLOOR))
    return int(r2 * 255), int(g2 * 255), int(b2 * 255)


def _dim(colour: int, cap: float) -> tuple[int, int, int]:
    """Bản tối của màu cảnh giới: giữ sắc, chỉ hạ độ sáng xuống dưới `cap`."""
    r, g, b = (colour >> 16) & 255, (colour >> 8) & 255, colour & 255
    hue, light, sat = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    r2, g2, b2 = colorsys.hls_to_rgb(hue, min(light, max(cap, 0.05)), max(sat, 0.35))
    return int(r2 * 255), int(g2 * 255), int(b2 * 255)


def lit_colour(colour: int, lightness: float | None = None) -> tuple[int, int, int]:
    """Màu của vết máu: đúng tông cảnh giới, đủ sáng để không chìm vào nền."""
    return _hls(colour, LIGHT_FLOOR if lightness is None else lightness)


def _glyph_mask(char: str):
    """Mặt nạ trắng của một chữ Hán (tên file = mã Unicode); thiếu file thì None."""
    if Image is None or not char:
        return None
    # Mặt nạ có sẵn trong glyphs/ → không cần font CJK trên server.
    try:
        return Image.open(GLYPH_DIR / f"{ord(char[0]):x}.png").convert("L")
    except (OSError, ValueError):
        return None


def _watermark(glyph: str, colour: int, level: int):
    """Ký tự Hán lớn chìm phía sau vết máu. Bậc càng cao càng tối (như khắc sâu vào đá)."""
    mask = _glyph_mask(glyph)
    if mask is None:
        return None
    side = int(SIZE * GLYPH_SCALE)
    mask = mask.resize((side, side), Image.LANCZOS)
    tint = Image.new("RGBA", (side, side), (*_dim(colour, GLYPH_LIGHT - level * GLYPH_STEP), 238))
    layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    layer.paste(
        tint,
        (int(SIZE * GLYPH_CX - side / 2), int(SIZE * GLYPH_CY - side / 2)),
        mask,
    )
    return layer


def _column_layer(text: str, colour: int, level: int):
    """Cột chữ Hán dọc mép phải (số kiếp đánh vần), vẽ đè lên vết máu nên phải sáng.

    Chữ dài (vài nghìn) tự thu nhỏ cho vừa cột; chữ nào thiếu mặt nạ thì bỏ qua.
    """
    masks = [mask for mask in (_glyph_mask(char) for char in text) if mask is not None]
    if not masks:
        return None
    gap = SIZE * COLUMN_GAP
    room = SIZE * (COLUMN_BOTTOM - COLUMN_TOP) - gap * (len(masks) - 1)
    side = int(min(SIZE * COLUMN_WIDTH, room / len(masks)))
    if side < 10:  # quá nhiều chữ → thà bỏ cột còn hơn ra vệt nhòe
        return None
    tint = Image.new(
        "RGBA", (side, side), (*_hls(colour, COLUMN_LIGHT - level * COLUMN_STEP), COLUMN_ALPHA)
    )
    layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    x = int(SIZE * COLUMN_CX - side / 2)
    y = SIZE * COLUMN_TOP + (room - side * len(masks)) / 2
    for mask in masks:
        layer.paste(tint, (x, int(y)), mask.resize((side, side), Image.LANCZOS))
        y += side + gap
    return layer


def _digits_layer(text: str, box: int, stroke: int, fill, stroke_fill) -> object:
    """Lớp chữ số cỡ lớn, đúng tâm vết máu."""
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
        (SIZE * BLOOD_CX, SIZE * BLOOD_CY),
        text,
        font=font,
        fill=fill,
        anchor="mm",
        stroke_width=stroke,
        stroke_fill=stroke_fill,
    )
    return layer


def _splat_mask(rng: random.Random, rough: float, spikes: int, droplets: int):
    """Vết máu: thân méo, vài cục loang, tia bắn nhọn và các giọt li ti."""
    mask = Image.new("L", (SIZE, SIZE), 0)
    draw = ImageDraw.Draw(mask)
    centre_x, centre_y = SIZE * BLOOD_CX, SIZE * BLOOD_CY
    radius = SIZE * BLOOD_R
    phase_a, phase_b = rng.uniform(0, 6.3), rng.uniform(0, 6.3)

    points = []
    for step in range(160):
        angle = step / 160 * 2 * math.pi
        reach = radius * (
            1
            + rough * math.sin(3 * angle + phase_a)
            + rough * 0.6 * math.sin(9 * angle + phase_b)
            + rough * 0.3 * math.sin(17 * angle + phase_a)
        )
        points.append((centre_x + reach * math.cos(angle), centre_y + reach * math.sin(angle)))
    draw.polygon(points, fill=255)

    for _ in range(rng.randint(5, 8)):  # cục loang quanh thân
        angle = rng.uniform(0, 2 * math.pi)
        distance = radius * rng.uniform(0.45, 0.82)
        blob = radius * rng.uniform(0.22, 0.38)
        x, y = centre_x + distance * math.cos(angle), centre_y + distance * math.sin(angle)
        draw.ellipse((x - blob, y - blob, x + blob, y + blob), fill=255)

    for _ in range(spikes):  # tia máu bắn ra
        angle = rng.uniform(0, 2 * math.pi)
        near, far = radius * 0.88, radius * rng.uniform(1.10, 1.34)
        spread = rng.uniform(0.03, 0.09)
        draw.polygon(
            [
                (centre_x + near * math.cos(angle - spread), centre_y + near * math.sin(angle - spread)),
                (centre_x + near * math.cos(angle + spread), centre_y + near * math.sin(angle + spread)),
                (centre_x + far * math.cos(angle), centre_y + far * math.sin(angle)),
            ],
            fill=255,
        )

    for _ in range(droplets):  # giọt li ti văng ra
        angle = rng.uniform(0, 2 * math.pi)
        distance = radius * rng.uniform(1.0, 1.34)
        drop = rng.uniform(2, 6.5)
        x, y = centre_x + distance * math.cos(angle), centre_y + distance * math.sin(angle)
        draw.ellipse((x - drop, y - drop, x + drop, y + drop), fill=255)
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
    radius = SIZE * BLOOD_R
    for _ in range(count):
        angle = rng.uniform(-1.2, 1.2)
        start_x = SIZE * BLOOD_CX + rng.uniform(-radius * 1.5, radius * 1.5)
        start_y = SIZE * BLOOD_CY + rng.uniform(-radius * 1.7, radius * 1.7)
        points = []
        for step in range(9):
            points.append(
                (
                    start_x + math.cos(angle) * step * radius * 0.12 + rng.uniform(-3, 3),
                    start_y + math.sin(angle) * step * radius * 0.12 + rng.uniform(-3, 3),
                )
            )
        draw.line(points, fill=0, width=rng.randint(3, 6))


@functools.lru_cache(maxsize=96)
def render_count_png(total: int, colour: int, level: int = 0, glyph: str = "") -> bytes | None:
    """PNG trong suốt: chữ Hán lớn + cột số dọc mép phải + vết máu khoét số, càng lên bậc càng tối."""
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
    mark = _watermark(glyph, colour, level)
    if mark is not None:  # ký tự lớn nằm dưới cùng, vết máu đóng dấu lên trên
        image.alpha_composite(mark)
    # Bậc càng cao thì vết máu càng chìm vào nền (alpha giảm) — vẫn thấy nhưng tối hơn.
    alpha = 236 - level * 4
    image.paste(Image.new("RGBA", (SIZE, SIZE), (*blood, alpha)), (0, 0), mask)

    draw = ImageDraw.Draw(image)
    radius = SIZE * BLOOD_R
    for _ in range(2 + level // 4):
        _drip(
            draw,
            x=SIZE * BLOOD_CX + rng.uniform(-radius * 0.55, radius * 0.55),
            y0=SIZE * BLOOD_CY + radius * rng.uniform(0.55, 0.75),
            length=rng.uniform(18, 52),
            width=rng.uniform(3, 6),
            colour=(*blood, alpha),
        )

    box = BOX_SHORT if len(text) <= 2 else BOX_LONG
    digits = _digits_layer(text, box, stroke=8, fill=(255, 255, 255, 255), stroke_fill=(255, 255, 255, 255))
    image.paste(Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0)), (0, 0), digits.split()[3])

    # Viền sáng men theo mép khoét: số vẫn đọc được dù vết máu đã sẫm gần đen.
    rim = _digits_layer(text, box, stroke=4, fill=None, stroke_fill=(*_hls(colour, 0.72), 135))
    image.alpha_composite(rim)

    # Cột chữ số dọc mép phải: nằm cạnh con số rồi chạy xuống đáy, vẽ sau cùng để
    # không bị vết máu và vòng khoét nuốt mất.
    han = texts.turn_label(total)[0]
    column = _column_layer(han[1:] if han.startswith("第") else han, colour, level)
    if column is not None:
        image.alpha_composite(column)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()

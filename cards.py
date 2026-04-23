"""
Генерация красивых PNG-карточек для упражнений.
Зависимость: Pillow (pip install Pillow)
"""
from __future__ import annotations

from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

CARD_W, CARD_H = 900, 520

# Цвет фона (от, до) для каждой категории
PALETTE: dict[str, tuple[tuple, tuple]] = {
    "Шея":       ((245, 158,  11), (180,  83,   9)),   # amber
    "Спина":     (( 16, 185, 129), (  4, 120,  87)),   # emerald
    "Глаза":     (( 99, 102, 241), ( 67,  56, 202)),   # indigo
    "Ноги":      ((239,  68,  68), (185,  28,  28)),   # red
    "Плечи":     ((139,  92, 246), (109,  40, 217)),   # violet
    "Запястья":  ((236,  72, 153), (190,  24,  93)),   # pink
    "Грудь":     (( 20, 184, 166), ( 13, 148, 136)),   # teal
    "Дыхание":   (( 59, 130, 246), ( 29,  78, 216)),   # blue
    "Баланс":    ((249, 115,  22), (194,  65,  12)),   # orange
}
DEFAULT_PALETTE = ((107, 114, 128), (55, 65, 81))

_WIN_FONTS = "C:/Windows/Fonts/"


def _load_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    for path in [_WIN_FONTS + name, _WIN_FONTS + name.lower()]:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _gradient(img: Image.Image, c1: tuple, c2: tuple) -> None:
    w, h = img.size
    px = img.load()
    for y in range(h):
        t = y / (h - 1)
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        for x in range(w):
            px[x, y] = (r, g, b, 255)


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur: list[str] = []
    for word in words:
        test = " ".join(cur + [word])
        try:
            w = font.getlength(test)
        except AttributeError:
            w = font.getsize(test)[0]  # type: ignore[attr-defined]
        if w > max_w and cur:
            lines.append(" ".join(cur))
            cur = [word]
        else:
            cur.append(word)
    if cur:
        lines.append(" ".join(cur))
    return lines


def _lighten(c: tuple, f: float = 0.35) -> tuple:
    return tuple(min(255, int(v + (255 - v) * f)) for v in c)  # type: ignore[return-value]


def make_card(exercise: dict) -> BytesIO:
    area = exercise["area"]
    c1, c2 = PALETTE.get(area, DEFAULT_PALETTE)

    img = Image.new("RGBA", (CARD_W, CARD_H))
    _gradient(img, c1, c2)
    draw = ImageDraw.Draw(img)

    # ── декоративные круги ────────────────────────────────────────────────
    light = _lighten(c1, 0.25) + (55,)
    draw.ellipse((-130, -130, 260, 260), fill=light)
    draw.ellipse((CARD_W - 80, CARD_H - 40, CARD_W + 260, CARD_H + 280), fill=light)
    draw.ellipse((CARD_W - 220, -100, CARD_W + 60, 180), fill=_lighten(c1, 0.15) + (35,))

    # ── шрифты ──────────────────────────────────────────────────────────
    f_badge = _load_font("segoeuib.ttf", 22)
    f_title = _load_font("segoeuib.ttf", 52)
    f_body  = _load_font("segoeui.ttf",  27)
    f_water = _load_font("segoeui.ttf",  21)

    WHITE     = (255, 255, 255, 255)
    WHITE_DIM = (255, 255, 255, 190)
    WHITE_LOW = (255, 255, 255, 120)

    # ── бейдж категории ──────────────────────────────────────────────────
    badge = f"● {exercise['emoji']}  {area.upper()}"
    draw.text((52, 42), badge, font=f_badge, fill=WHITE_DIM)

    # ── заголовок ────────────────────────────────────────────────────────
    draw.text((52, 78), exercise["title"], font=f_title, fill=WHITE)

    # ── разделитель ──────────────────────────────────────────────────────
    draw.line([(52, 152), (CARD_W - 52, 152)], fill=WHITE_LOW, width=1)

    # ── текст упражнения ─────────────────────────────────────────────────
    lines = _wrap(exercise["text"], f_body, CARD_W - 110)
    y = 170
    for line in lines:
        draw.text((52, y), line, font=f_body, fill=WHITE_DIM)
        y += 38

    # ── напоминание о воде ───────────────────────────────────────────────
    draw.text((52, CARD_H - 42), "💧  Не забудь попить воды!", font=f_water, fill=WHITE_LOW)

    # ── акцентная полоска снизу ──────────────────────────────────────────
    draw.rectangle([0, CARD_H - 5, CARD_W, CARD_H], fill=(255, 255, 255, 70))

    out = BytesIO()
    img.convert("RGB").save(out, format="PNG", optimize=True)
    out.seek(0)
    return out

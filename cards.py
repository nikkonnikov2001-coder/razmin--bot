"""
Генерация PNG-карточек для упражнений.
Стили: "default" (цветной градиент), "dark" (тёмная тема).
"""
from __future__ import annotations

from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

CARD_W, CARD_H = 900, 520

PALETTE: dict[str, tuple[tuple, tuple]] = {
    "Шея":       ((245, 158,  11), (180,  83,   9)),
    "Спина":     (( 16, 185, 129), (  4, 120,  87)),
    "Глаза":     (( 99, 102, 241), ( 67,  56, 202)),
    "Ноги":      ((239,  68,  68), (185,  28,  28)),
    "Плечи":     ((139,  92, 246), (109,  40, 217)),
    "Запястья":  ((236,  72, 153), (190,  24,  93)),
    "Грудь":     (( 20, 184, 166), ( 13, 148, 136)),
    "Дыхание":   (( 59, 130, 246), ( 29,  78, 216)),
    "Баланс":    ((249, 115,  22), (194,  65,  12)),
}
DEFAULT_PALETTE = ((107, 114, 128), (55, 65, 81))

_WIN = "C:/Windows/Fonts/"


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    for p in [_WIN + name, _WIN + name.lower()]:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _lighten(c: tuple, f: float = 0.35) -> tuple:
    return tuple(min(255, int(v + (255 - v) * f)) for v in c)  # type: ignore


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur: list[str] = []
    for word in words:
        test = " ".join(cur + [word])
        try:
            w = font.getlength(test)
        except AttributeError:
            w = font.getsize(test)[0]  # type: ignore
        if w > max_w and cur:
            lines.append(" ".join(cur))
            cur = [word]
        else:
            cur.append(word)
    if cur:
        lines.append(" ".join(cur))
    return lines


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


# ── Стиль: default ───────────────────────────────────────────────────────────

def _default_card(exercise: dict) -> BytesIO:
    area = exercise["area"]
    c1, c2 = PALETTE.get(area, DEFAULT_PALETTE)

    img = Image.new("RGBA", (CARD_W, CARD_H))
    _gradient(img, c1, c2)
    draw = ImageDraw.Draw(img)

    light = _lighten(c1, 0.25) + (55,)
    draw.ellipse((-130, -130, 260, 260), fill=light)
    draw.ellipse((CARD_W - 80, CARD_H - 40, CARD_W + 260, CARD_H + 280), fill=light)
    draw.ellipse((CARD_W - 220, -100, CARD_W + 60, 180), fill=_lighten(c1, 0.15) + (35,))

    f_badge = _font("segoeuib.ttf", 22)
    f_title = _font("segoeuib.ttf", 52)
    f_body  = _font("segoeui.ttf",  27)
    f_water = _font("segoeui.ttf",  21)

    WHITE     = (255, 255, 255, 255)
    WHITE_DIM = (255, 255, 255, 190)
    WHITE_LOW = (255, 255, 255, 120)

    draw.text((52, 42), f"● {exercise['emoji']}  {area.upper()}", font=f_badge, fill=WHITE_DIM)
    draw.text((52, 78), exercise["title"], font=f_title, fill=WHITE)
    draw.line([(52, 152), (CARD_W - 52, 152)], fill=WHITE_LOW, width=1)

    y = 170
    for line in _wrap(exercise["text"], f_body, CARD_W - 110):
        draw.text((52, y), line, font=f_body, fill=WHITE_DIM)
        y += 38

    draw.text((52, CARD_H - 42), "💧  Не забудь попить воды!", font=f_water, fill=WHITE_LOW)
    draw.rectangle([0, CARD_H - 5, CARD_W, CARD_H], fill=(255, 255, 255, 70))

    out = BytesIO()
    img.convert("RGB").save(out, format="PNG", optimize=True)
    out.seek(0)
    return out


# ── Стиль: dark ──────────────────────────────────────────────────────────────

def _dark_card(exercise: dict) -> BytesIO:
    area = exercise["area"]
    c1, _ = PALETTE.get(area, DEFAULT_PALETTE)

    BG = (13, 13, 23)

    img = Image.new("RGBA", (CARD_W, CARD_H), (*BG, 255))
    draw = ImageDraw.Draw(img)

    # Левая цветная полоска
    draw.rectangle([0, 0, 7, CARD_H], fill=(*c1, 255))

    # Тонкий круг-акцент справа
    draw.ellipse((CARD_W - 180, -120, CARD_W + 120, 180), fill=(*c1, 18))
    draw.ellipse((CARD_W - 80, CARD_H - 80, CARD_W + 180, CARD_H + 180), fill=(*c1, 12))

    f_badge = _font("segoeuib.ttf", 22)
    f_title = _font("segoeuib.ttf", 52)
    f_body  = _font("segoeui.ttf",  27)
    f_water = _font("segoeui.ttf",  21)

    # Бейдж категории
    badge = f"  {exercise['emoji']}  {area}  "
    try:
        bw = int(f_badge.getlength(badge)) + 16
    except AttributeError:
        bw = f_badge.getsize(badge)[0] + 16  # type: ignore
    bh = 34
    draw.rounded_rectangle([28, 36, 28 + bw, 36 + bh], radius=10, fill=(*c1, 200))
    draw.text((36, 41), badge, font=f_badge, fill=(255, 255, 255, 235))

    draw.text((28, 84), exercise["title"], font=f_title, fill=(235, 240, 255, 255))
    draw.line([(28, 152), (CARD_W - 28, 152)], fill=(*c1, 70), width=1)

    y = 170
    for line in _wrap(exercise["text"], f_body, CARD_W - 80):
        draw.text((28, y), line, font=f_body, fill=(180, 188, 210, 220))
        y += 38

    draw.text((28, CARD_H - 42), "💧  Не забудь попить воды!", font=f_water, fill=(*c1, 180))
    draw.rectangle([0, CARD_H - 4, CARD_W, CARD_H], fill=(*c1, 140))

    out = BytesIO()
    img.convert("RGB").save(out, format="PNG", optimize=True)
    out.seek(0)
    return out


# ── Публичный API ─────────────────────────────────────────────────────────────

def make_card(exercise: dict, style: str = "default") -> BytesIO:
    if style == "dark":
        return _dark_card(exercise)
    return _default_card(exercise)

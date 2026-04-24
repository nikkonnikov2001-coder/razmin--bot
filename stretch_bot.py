"""
Stretch Bot — напоминает вставать и разминаться.

Фичи:
  • Индивидуальное расписание: часы, дни недели, часовой пояс
  • Фильтр категорий упражнений
  • Два стиля карточек (default / dark)
  • Геймификация: уровни, стрики, бонусные упражнения
  • Пауза на день/неделю
  • Цитата дня (первое напоминание)
  • Таблица лидеров /top
"""

from __future__ import annotations

import json
import logging
import os
import random
from datetime import date, datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
)

import cards

# ============ CONFIG ============
BOT_TOKEN = ""   # или задай переменную окружения BOT_TOKEN
# ================================

BASE_DIR         = Path(__file__).resolve().parent
SUBSCRIBERS_FILE = BASE_DIR / "subscribers.json"
LOG_FILE         = BASE_DIR / "bot.log"

logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("stretch-bot")

# Состояния диалогов
(PICK_START, PICK_END,
 TOGGLE_DAYS, PICK_TZ,
 TOGGLE_CATS, PICK_STYLE,
 PICK_PAUSE) = range(7)

# ─────────────────────────── Справочники ────────────────────────────────────

TIMEZONES = [
    ("Калининград", "Europe/Kaliningrad", "+2"),
    ("Москва",      "Europe/Moscow",      "+3"),
    ("Самара",      "Europe/Samara",      "+4"),
    ("Екатеринбург","Asia/Yekaterinburg", "+5"),
    ("Омск",        "Asia/Omsk",          "+6"),
    ("Красноярск",  "Asia/Krasnoyarsk",   "+7"),
    ("Иркутск",     "Asia/Irkutsk",       "+8"),
    ("Якутск",      "Asia/Yakutsk",       "+9"),
    ("Владивосток", "Asia/Vladivostok",   "+10"),
    ("Магадан",     "Asia/Magadan",       "+11"),
    ("Камчатка",    "Asia/Kamchatka",     "+12"),
]
TZ_BY_KEY = {tz: name for name, tz, _ in TIMEZONES}

ALL_CATEGORIES = ["Шея", "Спина", "Глаза", "Ноги", "Плечи",
                  "Запястья", "Грудь", "Дыхание", "Баланс"]

DAY_NAMES = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

LEVELS = [
    (0,   "🥚 Яйцо",       "Ещё не начал"),
    (1,   "🌱 Росток",      "Первые шаги"),
    (5,   "🔥 Искра",       "Вхожу в ритм"),
    (15,  "💪 Боец",        "Уже привычка"),
    (30,  "⚡ Динамо",       "Не остановить"),
    (60,  "🏅 Чемпион",     "Уважаю!"),
    (100, "🏆 Легенда",     "Топ 1%"),
    (200, "👑 Бессмертный", "Просто нет слов"),
]

DONE_MILESTONES = {1: "🌱 Первый!", 5: "🔥 Пятёрка!", 10: "⚡ Десятка!",
                   25: "🏅 25!", 50: "🏆 Полтинник!", 100: "👑 Сотня!"}

SKIP_PHRASES = [
    "Окей, пропустили 🙈 В следующий раз!",
    "Бывает 😅 Главное — ты помнишь о себе.",
    "Понял, форс-мажор 🫡 Но шею хотя бы покрути!",
    "Ладно-ладно 😂 Но за тобой должок!",
    "Спишем на обстоятельства 🌪 Следующий зачтётся.",
]

QUOTES = [
    "«Движение — это жизнь.» — Гиппократ",
    "«Заботиться о теле — значит уважать себя.»",
    "«Час упражнений стоит целого дня отдыха.» — Руссо",
    "«Тело — твой лучший инструмент. Береги его.»",
    "«Не надо быть великим, чтобы начать. Надо начать, чтобы стать великим.»",
    "«Маленькие действия каждый день — вот что меняет жизнь.»",
    "«Лучшее упражнение — то, которое ты сделаешь.»",
    "«Твоё тело слышит всё, что говорит твой разум.»",
    "«Регулярность важнее интенсивности.»",
    "«Сделай сегодня то, что завтра скажет тебе спасибо.»",
]

GREETINGS = [
    "Привет, {name}! 👋 Время небольшого перерыва",
    "Эй, {name}! 🌟 Без пяти — идеально, чтобы размяться",
    "Минутка заботы о теле, {name} 💚",
    "{name}, короткий перерыв пойдёт на пользу ⏰",
    "{name}, пора оторваться от экрана ✨",
    "Тук-тук, {name} 🚪 — напоминаю встать",
    "Давай-давай, {name}, потянулись 🤸",
    "Твоё тело говорит спасибо заранее, {name} 🙏",
    "Один раунд — и снова в бой, {name} 💪",
    "Маленький перерыв = большая продуктивность, {name} 🚀",
]

# ─────────────────────────── Упражнения ────────────────────────────────────

EXERCISES = [
    {"emoji": "🦒", "area": "Шея", "title": "Мягкие повороты",
     "text": "Медленно поверни голову вправо — задержись 5 сек, затем влево. "
             "5 повторов. Плечи расслаблены, дыхание ровное."},
    {"emoji": "🦒", "area": "Шея", "title": "Ухо к плечу",
     "text": "Наклони правое ухо к плечу, задержись 10 сек. "
             "Затем влево. По 3 раза в каждую сторону."},
    {"emoji": "🦒", "area": "Шея", "title": "Подбородок — грудь — потолок",
     "text": "Плавно опусти подбородок к груди (5 сек), "
             "затем подними взгляд вверх (5 сек). 5 повторов."},
    {"emoji": "🧘", "area": "Спина", "title": "Кошка-корова стоя",
     "text": "Руки на бёдра. Плавно прогнись назад, "
             "затем округли спину вперёд. 8 повторов."},
    {"emoji": "🧘", "area": "Спина", "title": "Боковые наклоны",
     "text": "Встань прямо. Наклонись вправо, скользя ладонью по бедру, 5 сек. "
             "Затем влево. 5 раз."},
    {"emoji": "🧘", "area": "Спина", "title": "Скрутка стоя",
     "text": "Руки на пояс. Медленно поворачивай корпус вправо-влево, "
             "голова следует за плечами. 10 повторов."},
    {"emoji": "🙆", "area": "Спина", "title": "Потянуться к небу",
     "text": "Сцепи пальцы в замок, выверни ладони вверх и тянись макушкой. "
             "15 сек × 3 раза."},
    {"emoji": "🧘", "area": "Спина", "title": "Настройка осанки",
     "text": "Прижми лопатки к спинке стула, расправь плечи, подними подбородок. "
             "Удерживай 30 секунд — это и есть правильная посадка."},
    {"emoji": "👀", "area": "Глаза", "title": "Правило 20-20-20",
     "text": "Посмотри на объект за 6 метров, держи взгляд 20 секунд. "
             "Потом поморгай 10 раз."},
    {"emoji": "👀", "area": "Глаза", "title": "Фокус близко-далеко",
     "text": "Вытяни палец на 30 см. Смотри 3 сек → дальний объект 3 сек. "
             "10 повторов."},
    {"emoji": "👀", "area": "Глаза", "title": "Глазная восьмёрка",
     "text": "Представь большую цифру 8 и обводи её глазами. "
             "5 раз по часовой стрелке, 5 — против."},
    {"emoji": "🦵", "area": "Ноги", "title": "Мини-приседания",
     "text": "10 приседаний. Пятки не отрывай, спина прямая, колени над носками."},
    {"emoji": "🚶", "area": "Ноги", "title": "Прогулка",
     "text": "Встань и пройдись 2 минуты. По дороге выгляни в окно и налей воды 💧"},
    {"emoji": "🦶", "area": "Ноги", "title": "Подъёмы на носки",
     "text": "15 подъёмов на носки, можно держаться за стол. "
             "Опускайся медленно — чувствуй икры."},
    {"emoji": "🦵", "area": "Ноги", "title": "Маршировка на месте",
     "text": "Шагай на месте 30 секунд, высоко поднимая колени. "
             "Разгоняет кровь лучше кофе ☕"},
    {"emoji": "💪", "area": "Плечи", "title": "Круги плечами",
     "text": "10 кругов плечами назад, 10 — вперёд. Руки расслаблены, амплитуда — максимальная."},
    {"emoji": "💪", "area": "Плечи", "title": "Сведение лопаток",
     "text": "Сведи лопатки вместе — будто зажимаешь карандаш. Удержи 5 сек. 10 повторов."},
    {"emoji": "✋", "area": "Запястья", "title": "Разминка запястий",
     "text": "Сцепи пальцы в замок, 10 круговых движений в каждую сторону. "
             "Потом мягко потяни пальцы на себя."},
    {"emoji": "✋", "area": "Запястья", "title": "Пальчиковая гимнастика",
     "text": "По очереди сгибай каждый палец, начиная с мизинца. "
             "Затем встряхни кисти 15 секунд."},
    {"emoji": "🤲", "area": "Грудь", "title": "Раскрытие грудной клетки",
     "text": "Сцепи руки в замок за спиной, выпрями локти, подними руки, сводя лопатки. "
             "15 сек × 3."},
    {"emoji": "🌬", "area": "Дыхание", "title": "Дыхание 4-7-8",
     "text": "Вдох — 4 счёта, задержка — 7, медленный выдох — 8. "
             "3 цикла. Снижает стресс и возвращает фокус."},
    {"emoji": "🌬", "area": "Дыхание", "title": "Диафрагмальное дыхание",
     "text": "Руку на живот. На вдохе живот выпячивается, на выдохе — втягивается. "
             "8 медленных вдохов."},
    {"emoji": "🌬", "area": "Дыхание", "title": "Бокс-дыхание",
     "text": "Вдох 4 → пауза 4 → выдох 4 → пауза 4. "
             "4 цикла. Используется военными для снятия напряжения."},
    {"emoji": "🦩", "area": "Баланс", "title": "Стойка на одной ноге",
     "text": "Стой на одной ноге 20 секунд, затем смени. "
             "Усложнение — закрой глаза."},
    {"emoji": "🦩", "area": "Баланс", "title": "Алфавит носком",
     "text": "Стоя, рисуй носком поднятой ноги буквы в воздухе. "
             "Укрепляет голеностоп и концентрацию."},
]

# Бонусные упражнения (появляются с шансом 10%)
BONUS_EXERCISES = [
    {"emoji": "🔥", "area": "Ноги", "title": "БОНУС: Берпи × 5",
     "text": "5 берпи: присед → упор лёжа → отжимание → прыжок вверх. "
             "Сложно, но эффективно. Ты справишься! 💪"},
    {"emoji": "🔥", "area": "Спина", "title": "БОНУС: Планка 45 сек",
     "text": "Упор на предплечья или ладони, тело — прямая линия. "
             "Держи 45 секунд. Дыши! Не опускай таз."},
    {"emoji": "🔥", "area": "Ноги", "title": "БОНУС: 20 приседаний",
     "text": "20 глубоких приседаний с паузой внизу (1 сек). "
             "Медленно вверх. Почувствуй каждый мускул."},
    {"emoji": "🔥", "area": "Плечи", "title": "БОНУС: Отжимания × 10",
     "text": "10 отжиманий от стола, стены или пола — на выбор. "
             "Локти чуть к телу. Это бонусный день!"},
]


# ─────────────────────────── Модель данных ──────────────────────────────────

def _default_user() -> dict:
    return {
        "start": 12, "end": 20,
        "done": 0, "skip": 0,
        "streak": 0, "best_streak": 0,
        "last_done": None,
        "timezone": "Asia/Krasnoyarsk",
        "weekdays": [0, 1, 2, 3, 4],
        "categories": ALL_CATEGORIES[:],
        "card_style": "default",
        "paused_until": None,
        "first_name": "друг",
        "quote_date": None,
    }


def load_users() -> dict[int, dict]:
    if SUBSCRIBERS_FILE.exists():
        try:
            raw = json.loads(SUBSCRIBERS_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                return {cid: _default_user() for cid in raw}
            return {int(k): {**_default_user(), **v} for k, v in raw.items()}
        except Exception as e:
            logger.warning("Failed to load users: %s", e)
    return {}


def save_users(users: dict[int, dict]) -> None:
    SUBSCRIBERS_FILE.write_text(
        json.dumps({str(k): v for k, v in users.items()},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ─────────────────────────── Геймификация ───────────────────────────────────

def get_level(done: int) -> tuple[str, str]:
    name, desc = LEVELS[0][1], LEVELS[0][2]
    for threshold, n, d in LEVELS:
        if done >= threshold:
            name, desc = n, d
    return name, desc


def update_streak(u: dict) -> dict:
    today = date.today().isoformat()
    yesterday = date.fromordinal(date.today().toordinal() - 1).isoformat()
    last = u.get("last_done")

    if last == today:
        pass  # уже засчитано сегодня
    elif last == yesterday:
        u["streak"] = u.get("streak", 0) + 1
    else:
        u["streak"] = 1

    u["best_streak"] = max(u.get("best_streak", 0), u.get("streak", 1))
    u["last_done"] = today
    return u


def is_paused(u: dict) -> bool:
    pu = u.get("paused_until")
    return bool(pu and date.today().isoformat() <= pu)


def daily_quote() -> str:
    return QUOTES[date.today().toordinal() % len(QUOTES)]


# ─────────────────────────── Вспомогательное ────────────────────────────────

def _first_name(update: Update) -> str:
    user = update.effective_user
    return (user.first_name or "друг") if user else "друг"


def _ex_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Готово", callback_data="done"),
        InlineKeyboardButton("⏭ Пропустить", callback_data="skip"),
    ]])


def _hours_kb(prefix: str, lo: int = 6, hi: int = 22) -> InlineKeyboardMarkup:
    hours = list(range(lo, hi + 1))
    rows = [
        [InlineKeyboardButton(f"{h:02d}:00", callback_data=f"{prefix}:{h}")
         for h in hours[i:i + 6]]
        for i in range(0, len(hours), 6)
    ]
    return InlineKeyboardMarkup(rows)


def _days_kb(selected: list[int]) -> InlineKeyboardMarkup:
    row = [
        InlineKeyboardButton(
            f"{'✅' if i in selected else '☐'} {DAY_NAMES[i]}",
            callback_data=f"day:{i}"
        )
        for i in range(7)
    ]
    return InlineKeyboardMarkup([row, [InlineKeyboardButton("💾 Сохранить", callback_data="day:save")]])


def _tz_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(f"{name} UTC{offset}", callback_data=f"tz:{tz}")]
        for name, tz, offset in TIMEZONES
    ]
    return InlineKeyboardMarkup(rows)


def _cats_kb(selected: list[str]) -> InlineKeyboardMarkup:
    cats = ALL_CATEGORIES
    rows = [
        [
            InlineKeyboardButton(
                f"{'✅' if c in selected else '☐'} {c}",
                callback_data=f"cat:{c}"
            )
            for c in cats[i:i + 3]
        ]
        for i in range(0, len(cats), 3)
    ]
    rows.append([InlineKeyboardButton("💾 Сохранить", callback_data="cat:save")])
    return InlineKeyboardMarkup(rows)


def _style_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🌈 Цветной (default)", callback_data="style:default"),
        InlineKeyboardButton("🌙 Тёмный (dark)",     callback_data="style:dark"),
    ]])


def _pick_exercise(u: dict) -> dict:
    cats = u.get("categories") or ALL_CATEGORIES
    pool = [e for e in EXERCISES if e["area"] in cats] or EXERCISES
    if random.random() < 0.10:
        return random.choice(BONUS_EXERCISES)
    return random.choice(pool)


def _build_caption(ex: dict, name: str, quote: str | None = None) -> str:
    greet = random.choice(GREETINGS).format(name=name)
    parts = []
    if quote:
        parts.append(f"✨ <i>{quote}</i>\n")
    parts.append(f"{greet}\n\n{ex['emoji']} <b>{ex['area']}: {ex['title']}</b>\n{ex['text']}")
    return "\n".join(parts)


async def _send_exercise(bot_or_msg, chat_id: int, u: dict,
                         name: str, quote: str | None = None, reply=False):
    ex = _pick_exercise(u)
    caption = _build_caption(ex, name, quote)
    photo = cards.make_card(ex, style=u.get("card_style", "default"))
    kwargs = dict(
        photo=InputFile(photo, filename="exercise.png"),
        caption=caption,
        parse_mode="HTML",
        reply_markup=_ex_keyboard(),
    )
    if reply:
        await bot_or_msg.reply_photo(**kwargs)
    else:
        await bot_or_msg.send_photo(chat_id=chat_id, **kwargs)


# ─────────────────────────── Команды ────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    name = _first_name(update)
    users = load_users()

    if chat_id in users:
        u = users[chat_id]
        u["first_name"] = name
        save_users(users)
        level, _ = get_level(u["done"])
        await update.message.reply_text(
            f"С возвращением, {name}! 👋\n\n"
            f"{level}  |  ✅ {u['done']} выполнено  |  🔥 стрик {u.get('streak', 0)} дн.\n"
            f"Диапазон: {u['start']:02d}:55 — {u['end']:02d}:55\n\n"
            "/next — упражнение прямо сейчас\n"
            "/stats — статистика\n"
            "/settings — настройки\n"
            "/top — таблица лидеров\n"
            "/pause — взять паузу\n"
            "/stop — отписаться"
        )
        return

    users[chat_id] = {**_default_user(), "first_name": name}
    save_users(users)
    await update.message.reply_text(
        f"Привет, {name}! 🎉\n\n"
        "Я буду напоминать тебе разминаться без 5 минут каждый час.\n\n"
        "По умолчанию: <b>пн–пт, 12:55 – 20:55, часовой пояс Красноярск</b>.\n"
        "Настрой всё под себя командой /settings\n\n"
        "/next — прислать упражнение прямо сейчас\n"
        "/stats — статистика и уровень\n"
        "/top — таблица лидеров\n"
        "/stop — отписаться\n\n"
        "Спасибо, что заботишься о себе ✨",
        parse_mode="HTML",
    )


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    name = _first_name(update)
    users = load_users()
    if chat_id in users:
        del users[chat_id]
        save_users(users)
        await update.message.reply_text(
            f"Пока-пока, {name} 🫶\n"
            "Напоминания отключены. Напиши /start, когда захочешь вернуться."
        )
    else:
        await update.message.reply_text("Ты не подписан. /start — чтобы включить.")


async def cmd_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    name = _first_name(update)
    users = load_users()
    u = users.get(chat_id, _default_user())
    await _send_exercise(update.message, chat_id, u, name, reply=True)


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    name = _first_name(update)
    users = load_users()
    if chat_id not in users:
        await update.message.reply_text("Ты не подписан. /start — чтобы начать!")
        return

    u = users[chat_id]
    done, skip = u["done"], u["skip"]
    total = done + skip
    pct = round(done / total * 100) if total else 0
    level, ldesc = get_level(done)
    streak = u.get("streak", 0)
    best  = u.get("best_streak", 0)
    streak_icon = "🔥" if streak >= 3 else ("❄️" if streak == 0 else "✨")

    next_level = next(
        ((t, n) for t, n, _ in LEVELS if t > done), None
    )
    next_line = (f"До уровня <b>{next_level[1]}</b> ещё {next_level[0] - done} упр."
                 if next_level else "Ты достиг максимального уровня! 👑")

    await update.message.reply_text(
        f"📊 <b>Статистика, {name}</b>\n\n"
        f"🏅 Уровень: <b>{level}</b> — {ldesc}\n"
        f"{next_line}\n\n"
        f"✅ Выполнено: <b>{done}</b>  |  ⏭ Пропущено: <b>{skip}</b>\n"
        f"📈 Выполнение: <b>{pct}%</b>\n\n"
        f"{streak_icon} Стрик: <b>{streak}</b> дн.  |  🏆 Рекорд: <b>{best}</b> дн.\n\n"
        f"⏰ Диапазон: {u['start']:02d}:55 – {u['end']:02d}:55\n"
        f"📅 Дни: {', '.join(DAY_NAMES[d] for d in sorted(u.get('weekdays', [0,1,2,3,4])))}\n"
        f"🌍 Часовой пояс: {TZ_BY_KEY.get(u.get('timezone', ''), u.get('timezone', ''))}\n"
        f"🎨 Стиль: {u.get('card_style', 'default')}",
        parse_mode="HTML",
    )


async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = load_users()
    if not users:
        await update.message.reply_text("Пока нет участников 🙈")
        return
    top = sorted(users.items(), key=lambda x: x[1].get("done", 0), reverse=True)[:10]
    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
    lines = ["🏆 <b>Таблица лидеров</b>\n"]
    for i, (_, u) in enumerate(top):
        name = u.get("first_name", "Аноним")
        done = u.get("done", 0)
        level, _ = get_level(done)
        streak = u.get("streak", 0)
        streak_str = f" 🔥{streak}" if streak >= 3 else ""
        lines.append(f"{medals[i]} <b>{name}</b> — {done} упр. {level}{streak_str}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏰ Время работы",   callback_data="cfg:time"),
         InlineKeyboardButton("📅 Дни недели",     callback_data="cfg:days")],
        [InlineKeyboardButton("🌍 Часовой пояс",   callback_data="cfg:tz"),
         InlineKeyboardButton("💪 Категории",       callback_data="cfg:cats")],
        [InlineKeyboardButton("🎨 Стиль карточек", callback_data="cfg:style")],
    ])
    await update.message.reply_text(
        "⚙️ <b>Настройки</b>\nВыбери, что хочешь изменить:",
        parse_mode="HTML",
        reply_markup=kb,
    )


# ─────────────────────────── /settime ───────────────────────────────────────

async def cmd_settime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "С какого часа начинать напоминания? ⏰",
        reply_markup=_hours_kb("st", 6, 21),
    )
    return PICK_START


async def settings_dispatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает кнопки из /settings меню."""
    q = update.callback_query
    await q.answer()
    action = q.data.split(":")[1]

    if action == "time":
        await q.edit_message_text("С какого часа начинать напоминания? ⏰",
                                  reply_markup=_hours_kb("st", 6, 21))
        return PICK_START

    if action == "days":
        chat_id = update.effective_chat.id
        users = load_users()
        sel = users.get(chat_id, _default_user()).get("weekdays", [0,1,2,3,4])
        context.user_data["days_sel"] = list(sel)
        await q.edit_message_text("Выбери дни недели 📅\n(нажми для переключения)",
                                  reply_markup=_days_kb(context.user_data["days_sel"]))
        return TOGGLE_DAYS

    if action == "tz":
        await q.edit_message_text("Выбери свой часовой пояс 🌍",
                                  reply_markup=_tz_kb())
        return PICK_TZ

    if action == "cats":
        chat_id = update.effective_chat.id
        users = load_users()
        sel = users.get(chat_id, _default_user()).get("categories", ALL_CATEGORIES[:])
        context.user_data["cats_sel"] = list(sel)
        await q.edit_message_text(
            "Выбери категории упражнений 💪\n(нажми для переключения)",
            reply_markup=_cats_kb(context.user_data["cats_sel"]))
        return TOGGLE_CATS

    if action == "style":
        await q.edit_message_text("Выбери стиль карточек 🎨",
                                  reply_markup=_style_kb())
        return PICK_STYLE

    return ConversationHandler.END


async def picked_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    start_h = int(q.data.split(":")[1])
    context.user_data["start_h"] = start_h
    await q.edit_message_text(
        f"Начало: <b>{start_h:02d}:55</b> 🟢\nДо какого часа присылать?",
        parse_mode="HTML",
        reply_markup=_hours_kb("en", start_h + 1, 22),
    )
    return PICK_END


async def picked_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    end_h = int(q.data.split(":")[1])
    start_h = context.user_data.get("start_h", 12)
    chat_id = update.effective_chat.id
    users = load_users()
    if chat_id not in users:
        users[chat_id] = _default_user()
    users[chat_id]["start"] = start_h
    users[chat_id]["end"] = end_h
    save_users(users)
    count = end_h - start_h + 1
    suf = "е" if count == 1 else ("я" if 2 <= count <= 4 else "й")
    await q.edit_message_text(
        f"✅ Сохранено!\n\n🕐 С <b>{start_h:02d}:55</b> до <b>{end_h:02d}:55</b>\n"
        f"📬 <b>{count}</b> напоминани{suf} в день\n\nХорошей работы! 💪",
        parse_mode="HTML",
    )
    return ConversationHandler.END


# ─────────────────────────── /setdays ───────────────────────────────────────

async def cmd_setdays(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    users = load_users()
    sel = users.get(chat_id, _default_user()).get("weekdays", [0,1,2,3,4])
    context.user_data["days_sel"] = list(sel)
    await update.message.reply_text(
        "Выбери дни недели 📅", reply_markup=_days_kb(context.user_data["days_sel"])
    )
    return TOGGLE_DAYS


async def toggle_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    day = int(q.data.split(":")[1])
    sel: list = context.user_data.setdefault("days_sel", [0,1,2,3,4])
    if day in sel:
        if len(sel) > 1:
            sel.remove(day)
    else:
        sel.append(day)
    await q.edit_message_reply_markup(reply_markup=_days_kb(sel))
    return TOGGLE_DAYS


async def save_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    sel = sorted(context.user_data.get("days_sel", [0,1,2,3,4]))
    chat_id = update.effective_chat.id
    users = load_users()
    if chat_id not in users:
        users[chat_id] = _default_user()
    users[chat_id]["weekdays"] = sel
    save_users(users)
    day_str = ", ".join(DAY_NAMES[d] for d in sel)
    await q.edit_message_text(f"✅ Дни сохранены: <b>{day_str}</b>", parse_mode="HTML")
    return ConversationHandler.END


# ─────────────────────────── /settimezone ───────────────────────────────────

async def cmd_settimezone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Выбери часовой пояс 🌍", reply_markup=_tz_kb())
    return PICK_TZ


async def picked_tz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    tz = q.data.split(":", 1)[1]
    chat_id = update.effective_chat.id
    users = load_users()
    if chat_id not in users:
        users[chat_id] = _default_user()
    users[chat_id]["timezone"] = tz
    save_users(users)
    name = TZ_BY_KEY.get(tz, tz)
    await q.edit_message_text(f"✅ Часовой пояс: <b>{name}</b> ({tz})", parse_mode="HTML")
    return ConversationHandler.END


# ─────────────────────────── /setcategories ─────────────────────────────────

async def cmd_setcategories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    users = load_users()
    sel = users.get(chat_id, _default_user()).get("categories", ALL_CATEGORIES[:])
    context.user_data["cats_sel"] = list(sel)
    await update.message.reply_text(
        "Выбери категории упражнений 💪",
        reply_markup=_cats_kb(context.user_data["cats_sel"])
    )
    return TOGGLE_CATS


async def toggle_cat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cat = q.data.split(":", 1)[1]
    sel: list = context.user_data.setdefault("cats_sel", ALL_CATEGORIES[:])
    if cat in sel:
        if len(sel) > 1:
            sel.remove(cat)
    else:
        sel.append(cat)
    await q.edit_message_reply_markup(reply_markup=_cats_kb(sel))
    return TOGGLE_CATS


async def save_cats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    sel = context.user_data.get("cats_sel", ALL_CATEGORIES[:])
    chat_id = update.effective_chat.id
    users = load_users()
    if chat_id not in users:
        users[chat_id] = _default_user()
    users[chat_id]["categories"] = sel
    save_users(users)
    await q.edit_message_text(
        f"✅ Категории: <b>{', '.join(sel)}</b>", parse_mode="HTML"
    )
    return ConversationHandler.END


# ─────────────────────────── /setstyle ──────────────────────────────────────

async def cmd_setstyle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Выбери стиль карточек 🎨", reply_markup=_style_kb())
    return PICK_STYLE


async def picked_style(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    style = q.data.split(":")[1]
    chat_id = update.effective_chat.id
    users = load_users()
    if chat_id not in users:
        users[chat_id] = _default_user()
    users[chat_id]["card_style"] = style
    save_users(users)
    label = "🌈 Цветной" if style == "default" else "🌙 Тёмный"
    await q.edit_message_text(f"✅ Стиль карточек: <b>{label}</b>", parse_mode="HTML")
    return ConversationHandler.END


# ─────────────────────────── /pause ─────────────────────────────────────────

async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("😴 Сегодня",      callback_data="pause:today"),
        InlineKeyboardButton("😪 До конца недели", callback_data="pause:week"),
        InlineKeyboardButton("🏖 7 дней",        callback_data="pause:7"),
    ]])
    await update.message.reply_text(
        "На сколько поставить паузу? 🔕", reply_markup=kb
    )
    return PICK_PAUSE


async def picked_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    choice = q.data.split(":")[1]
    today = date.today()

    if choice == "today":
        until = today
        label = "на сегодня"
    elif choice == "week":
        days_to_sunday = 6 - today.weekday()
        until = date.fromordinal(today.toordinal() + days_to_sunday)
        label = f"до воскресенья ({until.strftime('%d.%m')})"
    else:
        until = date.fromordinal(today.toordinal() + 7)
        label = f"на 7 дней (до {until.strftime('%d.%m')})"

    chat_id = update.effective_chat.id
    users = load_users()
    if chat_id not in users:
        users[chat_id] = _default_user()
    users[chat_id]["paused_until"] = until.isoformat()
    save_users(users)

    await q.edit_message_text(
        f"🔕 Пауза {label}.\nОтдыхай! Напомню снова {until.strftime('%d.%m')} 😴"
    )
    return ConversationHandler.END


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено. Настройки не изменились.")
    return ConversationHandler.END


# ─────────────────────────── Кнопки упражнения ──────────────────────────────

async def on_exercise_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    chat_id = update.effective_chat.id
    users = load_users()

    if q.data == "done":
        await q.answer("Красавчик! 💚")
        if chat_id in users:
            users[chat_id] = update_streak(users[chat_id])
            users[chat_id]["done"] += 1
            save_users(users)
            done = users[chat_id]["done"]
            milestone = DONE_MILESTONES.get(done, "")
            reaction = f"{milestone} Всего выполнено: {done}" if milestone else f"Всего выполнено: {done} 💪"
        else:
            reaction = "Отлично! 💚"
        status = f"\n\n✅ <i>{reaction}</i>"

    else:
        await q.answer(random.choice(["Ок 🙈", "Бывает! 😅"]))
        if chat_id in users:
            users[chat_id]["skip"] = users[chat_id].get("skip", 0) + 1
            save_users(users)
        status = f"\n\n🙈 <i>{random.choice(SKIP_PHRASES)}</i>"

    try:
        if q.message and q.message.photo:
            caption = q.message.caption_html or q.message.caption or ""
            await q.edit_message_caption(caption=caption + status, parse_mode="HTML")
        else:
            text = (q.message.text_html if q.message else "") or ""
            await q.edit_message_text(text=text + status, parse_mode="HTML")
    except Exception as e:
        logger.warning("edit failed: %s", e)
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass


# ─────────────────────────── Планировщик ────────────────────────────────────

async def reminder_job(context: ContextTypes.DEFAULT_TYPE):
    now_utc = datetime.now(timezone.utc)
    today_str = date.today().isoformat()
    users = load_users()
    changed = False

    for chat_id, u in list(users.items()):
        if is_paused(u):
            continue

        user_tz = ZoneInfo(u.get("timezone", "Asia/Krasnoyarsk"))
        now_local = now_utc.astimezone(user_tz)
        local_hour = now_local.hour
        local_weekday = now_local.weekday()

        if local_weekday not in u.get("weekdays", [0,1,2,3,4]):
            continue
        if not (u["start"] <= local_hour <= u["end"]):
            continue

        # Цитата дня — только при первом напоминании дня
        quote: str | None = None
        if u.get("quote_date") != today_str:
            quote = daily_quote()
            users[chat_id]["quote_date"] = today_str
            changed = True

        try:
            name = u.get("first_name", "друг")
            await _send_exercise(context.bot, chat_id, u, name, quote=quote)
        except Exception as e:
            logger.warning("send failed for %s: %s", chat_id, e)

    if changed:
        save_users(users)


# ─────────────────────────── Запуск ─────────────────────────────────────────

def main():
    token = os.environ.get("BOT_TOKEN") or BOT_TOKEN
    if not token:
        raise SystemExit("Не задан BOT_TOKEN.")

    app = Application.builder().token(token).build()

    # Единый ConversationHandler для всех настроек
    settings_conv = ConversationHandler(
        entry_points=[
            CommandHandler("settime",       cmd_settime),
            CommandHandler("setdays",       cmd_setdays),
            CommandHandler("settimezone",   cmd_settimezone),
            CommandHandler("setcategories", cmd_setcategories),
            CommandHandler("setstyle",      cmd_setstyle),
            CommandHandler("pause",         cmd_pause),
            CommandHandler("settings",      cmd_settings),
            # кнопки из меню /settings
            CallbackQueryHandler(settings_dispatch, pattern=r"^cfg:"),
        ],
        states={
            PICK_START:   [CallbackQueryHandler(picked_start,  pattern=r"^st:\d+$")],
            PICK_END:     [CallbackQueryHandler(picked_end,    pattern=r"^en:\d+$")],
            TOGGLE_DAYS:  [
                CallbackQueryHandler(toggle_day, pattern=r"^day:\d$"),
                CallbackQueryHandler(save_days,  pattern=r"^day:save$"),
            ],
            PICK_TZ:      [CallbackQueryHandler(picked_tz,     pattern=r"^tz:")],
            TOGGLE_CATS:  [
                CallbackQueryHandler(toggle_cat, pattern=r"^cat:(?!save)"),
                CallbackQueryHandler(save_cats,  pattern=r"^cat:save$"),
            ],
            PICK_STYLE:   [CallbackQueryHandler(picked_style,  pattern=r"^style:")],
            PICK_PAUSE:   [CallbackQueryHandler(picked_pause,  pattern=r"^pause:")],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        per_message=False,
    )

    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("stop",   cmd_stop))
    app.add_handler(CommandHandler("next",   cmd_next))
    app.add_handler(CommandHandler("stats",  cmd_stats))
    app.add_handler(CommandHandler("top",    cmd_top))
    app.add_handler(settings_conv)
    app.add_handler(CallbackQueryHandler(on_exercise_button, pattern=r"^(done|skip)$"))

    tz_utc = ZoneInfo("UTC")
    for hour in range(24):
        app.job_queue.run_daily(
            reminder_job,
            time=time(hour=hour, minute=55, tzinfo=tz_utc),
            name=f"stretch-utc-{hour:02d}55",
        )

    logger.info("Bot started. 24 UTC jobs scheduled.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

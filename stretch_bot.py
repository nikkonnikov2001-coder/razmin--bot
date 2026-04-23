"""
Stretch Bot — без 5-ти минут каждый час напоминает встать и размяться.
Отправляет красивую карточку-картинку вместе с описанием упражнения.
"""

from __future__ import annotations

import json
import logging
import os
import random
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

import cards

# ============ CONFIG ============
BOT_TOKEN = ""  # вставь свой токен сюда или задай переменную окружения BOT_TOKEN
TIMEZONE = "Asia/Krasnoyarsk"
WORK_HOURS = list(range(12, 21))         # 12..20 включительно → 12:55 … 20:55
WORK_WEEKDAYS = (0, 1, 2, 3, 4)          # пн..пт. 0=Mon, 6=Sun
# ================================

BASE_DIR = Path(__file__).resolve().parent
SUBSCRIBERS_FILE = BASE_DIR / "subscribers.json"
LOG_FILE = BASE_DIR / "bot.log"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("stretch-bot")


# ─────────────────────────── Упражнения ────────────────────────────────────
EXERCISES = [
    # ── Шея ─────────────────────────────────────────────────────────────
    {"emoji": "🦒", "area": "Шея", "title": "Мягкие повороты",
     "text": "Медленно поверни голову вправо — задержись 5 сек, затем влево. "
             "5 повторов. Плечи расслаблены, дыхание ровное."},
    {"emoji": "🦒", "area": "Шея", "title": "Ухо к плечу",
     "text": "Наклони правое ухо к плечу, задержись 10 сек. "
             "Затем повтори влево. По 3 раза в каждую сторону."},
    {"emoji": "🦒", "area": "Шея", "title": "Подбородок — грудь — потолок",
     "text": "Плавно опусти подбородок к груди (5 сек), "
             "затем подними взгляд вверх (5 сек). 5 повторов."},

    # ── Спина ────────────────────────────────────────────────────────────
    {"emoji": "🧘", "area": "Спина", "title": "Кошка-корова стоя",
     "text": "Руки на бёдра. Плавно прогнись назад, "
             "затем округли спину вперёд. 8 повторов в медленном темпе."},
    {"emoji": "🧘", "area": "Спина", "title": "Боковые наклоны",
     "text": "Встань прямо, руки вдоль тела. Наклонись вправо, "
             "скользя ладонью по бедру, — 5 сек. Затем влево. 5 раз."},
    {"emoji": "🧘", "area": "Спина", "title": "Скрутка стоя",
     "text": "Руки на пояс. Медленно поворачивай корпус вправо и влево, "
             "голова следует за плечами. 10 повторов."},
    {"emoji": "🙆", "area": "Спина", "title": "Потянуться к небу",
     "text": "Сцепи пальцы в замок, выверни ладони вверх и тянись макушкой вверх. "
             "15 секунд × 3 раза."},
    {"emoji": "🧘", "area": "Спина", "title": "Настройка осанки",
     "text": "Прижми лопатки к спинке стула, расправь плечи, подними подбородок. "
             "Удерживай 30 секунд — это и есть правильная посадка."},

    # ── Глаза ────────────────────────────────────────────────────────────
    {"emoji": "👀", "area": "Глаза", "title": "Правило 20-20-20",
     "text": "Посмотри на объект за 6 метров от тебя и держи взгляд 20 секунд. "
             "Потом поморгай быстро 10 раз."},
    {"emoji": "👀", "area": "Глаза", "title": "Фокус близко-далеко",
     "text": "Вытяни палец на 30 см от лица. Смотри на него 3 сек, "
             "затем на дальний объект 3 сек. 10 повторов."},
    {"emoji": "👀", "area": "Глаза", "title": "Глазная восьмёрка",
     "text": "Представь перед собой большую цифру 8 и «обводи» её глазами. "
             "5 раз по часовой стрелке, 5 — против."},

    # ── Ноги ─────────────────────────────────────────────────────────────
    {"emoji": "🦵", "area": "Ноги", "title": "Мини-приседания",
     "text": "10 приседаний в удобном темпе. "
             "Пятки не отрывай, спина прямая, колени над носками."},
    {"emoji": "🚶", "area": "Ноги", "title": "Прогулка",
     "text": "Встань и пройдись 2 минуты. "
             "По дороге выгляни в окно и налей себе воды 💧"},
    {"emoji": "🦶", "area": "Ноги", "title": "Подъёмы на носки",
     "text": "15 подъёмов на носки, можно держаться за стол. "
             "Опускайся медленно — чувствуй работу икр."},
    {"emoji": "🦵", "area": "Ноги", "title": "Маршировка на месте",
     "text": "Шагай на месте 30 секунд, высоко поднимая колени. "
             "Это разгонит кровь лучше, чем кофе ☕"},

    # ── Плечи ────────────────────────────────────────────────────────────
    {"emoji": "💪", "area": "Плечи", "title": "Круги плечами",
     "text": "10 кругов плечами назад, затем 10 вперёд. "
             "Руки расслаблены, амплитуда максимальная."},
    {"emoji": "💪", "area": "Плечи", "title": "Сведение лопаток",
     "text": "Сведи лопатки вместе, будто хочешь зажать карандаш между ними. "
             "Удержи 5 сек. 10 повторов."},

    # ── Запястья ─────────────────────────────────────────────────────────
    {"emoji": "✋", "area": "Запястья", "title": "Разминка запястий",
     "text": "Сцепи пальцы в замок и сделай 10 круговых движений "
             "в каждую сторону. Потом мягко потяни пальцы на себя."},
    {"emoji": "✋", "area": "Запястья", "title": "Пальчиковая гимнастика",
     "text": "По очереди сгибай каждый палец, начиная с мизинца. "
             "Затем резко «встряхни» кисти — 15 секунд."},

    # ── Грудь ────────────────────────────────────────────────────────────
    {"emoji": "🤲", "area": "Грудь", "title": "Раскрытие грудной клетки",
     "text": "Сцепи руки в замок за спиной, выпрями локти и подними руки, "
             "сводя лопатки. 15 сек × 3."},

    # ── Дыхание ──────────────────────────────────────────────────────────
    {"emoji": "🌬", "area": "Дыхание", "title": "Дыхание 4-7-8",
     "text": "Вдох — 4 счёта, задержка — 7, медленный выдох — 8. "
             "3 цикла. Снижает стресс и возвращает фокус."},
    {"emoji": "🌬", "area": "Дыхание", "title": "Диафрагмальное дыхание",
     "text": "Положи руку на живот. На вдохе живот выпячивается вперёд, "
             "на выдохе — втягивается. 8 медленных вдохов."},
    {"emoji": "🌬", "area": "Дыхание", "title": "Бокс-дыхание",
     "text": "Вдох 4 счёта → пауза 4 → выдох 4 → пауза 4. "
             "4 цикла. Используется военными для быстрого снятия напряжения."},

    # ── Баланс ───────────────────────────────────────────────────────────
    {"emoji": "🦩", "area": "Баланс", "title": "Стойка на одной ноге",
     "text": "Встань на одну ногу и удерживай равновесие 20 секунд. "
             "Затем смени ногу. Для усложнения — закрой глаза."},
    {"emoji": "🦩", "area": "Баланс", "title": "Алфавит носком",
     "text": "Стоя, «нарисуй» носком одной ноги буквы А, Б, В в воздухе. "
             "Укрепляет голеностоп и помогает сосредоточиться."},
]

GREETINGS = [
    "Привет! 👋 Время небольшого перерыва",
    "Эй! 🌟 Пять минут до часа — идеально, чтобы размяться",
    "Минутка заботы о теле 💚",
    "Без пяти! ⏰ Короткий перерыв пойдёт на пользу",
    "Пора оторваться от экрана ✨",
    "Тук-тук 🚪 — напоминаю встать",
    "Давай-давай, потянулись 🤸",
    "Твоё тело говорит спасибо заранее 🙏",
    "Один раунд разминки — и снова в бой 💪",
    "Маленький перерыв = большая продуктивность 🚀",
]


# ─────────────────────────── Хранилище ──────────────────────────────────────

def load_subscribers() -> set[int]:
    if SUBSCRIBERS_FILE.exists():
        try:
            return set(json.loads(SUBSCRIBERS_FILE.read_text(encoding="utf-8")))
        except Exception as e:
            logger.warning("Failed to load subscribers: %s", e)
    return set()


def save_subscribers(subs: set[int]) -> None:
    SUBSCRIBERS_FILE.write_text(
        json.dumps(sorted(subs), ensure_ascii=False), encoding="utf-8"
    )


# ─────────────────────────── Сборка сообщения ───────────────────────────────

def _keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Готово", callback_data="done"),
        InlineKeyboardButton("⏭ Пропустить", callback_data="skip"),
    ]])


def build_exercise() -> tuple[dict, str, str]:
    """Возвращает (exercise, greeting, caption)."""
    ex = random.choice(EXERCISES)
    greet = random.choice(GREETINGS)
    caption = (
        f"{greet}\n\n"
        f"{ex['emoji']} <b>{ex['area']}: {ex['title']}</b>\n"
        f"{ex['text']}"
    )
    return ex, greet, caption


# ─────────────────────────── Команды ────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subs = load_subscribers()
    if chat_id in subs:
        await update.message.reply_text(
            "Ты уже подписан 💚\n"
            f"Напоминания: пн–пт, 12:55–20:55 ({TIMEZONE}).\n\n"
            "/next — упражнение прямо сейчас\n"
            "/stop — отключить напоминания"
        )
        return
    subs.add(chat_id)
    save_subscribers(subs)
    await update.message.reply_text(
        "Привет! 👋\n\n"
        "Я буду напоминать тебе вставать и разминаться без 5 минут каждый час.\n"
        f"Расписание: пн–пт, 12:55–20:55 ({TIMEZONE}).\n\n"
        "/next — прислать упражнение сейчас\n"
        "/stop — отключить напоминания\n\n"
        "Спасибо, что заботишься о себе ✨"
    )


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subs = load_subscribers()
    if chat_id in subs:
        subs.remove(chat_id)
        save_subscribers(subs)
        await update.message.reply_text(
            "Окей, напоминания остановлены 🫶\n"
            "Напиши /start, когда захочешь вернуться."
        )
    else:
        await update.message.reply_text(
            "Ты и так не подписан. Напиши /start, чтобы включить напоминания."
        )


async def cmd_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ex, _, caption = build_exercise()
    photo = cards.make_card(ex)
    await update.message.reply_photo(
        photo=InputFile(photo, filename="exercise.png"),
        caption=caption,
        parse_mode="HTML",
        reply_markup=_keyboard(),
    )


# ─────────────────────────── Кнопки ─────────────────────────────────────────

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.data == "done":
        await q.answer("Красавчик! 💚")
        status = "\n\n✅ <i>Готово! Так держать 💪</i>"
    else:
        await q.answer("Ок, пропустили")
        status = "\n\n🙈 <i>Пропустили</i>"

    try:
        if q.message and q.message.photo:
            # сообщение с картинкой — редактируем подпись
            caption = q.message.caption_html or q.message.caption or ""
            await q.edit_message_caption(caption=caption + status, parse_mode="HTML")
        else:
            # текстовое сообщение (запасной вариант)
            text = q.message.text_html if q.message else ""
            await q.edit_message_text(text=text + status, parse_mode="HTML")
    except Exception as e:
        logger.warning("Failed to edit message: %s", e)
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass


# ─────────────────────────── Планировщик ────────────────────────────────────

async def reminder_job(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(ZoneInfo(TIMEZONE))
    if now.weekday() not in WORK_WEEKDAYS:
        return
    subs = load_subscribers()
    if not subs:
        logger.info("No subscribers, skipping reminder.")
        return
    for chat_id in list(subs):
        try:
            ex, _, caption = build_exercise()
            photo = cards.make_card(ex)
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=InputFile(photo, filename="exercise.png"),
                caption=caption,
                parse_mode="HTML",
                reply_markup=_keyboard(),
            )
        except Exception as e:
            logger.warning("Failed to send to %s: %s", chat_id, e)


# ─────────────────────────── Запуск ─────────────────────────────────────────

def main():
    token = os.environ.get("BOT_TOKEN") or BOT_TOKEN
    if not token:
        raise SystemExit(
            "Не задан BOT_TOKEN. Вставь токен в начало файла "
            "или установи переменную окружения BOT_TOKEN."
        )

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("next", cmd_next))
    app.add_handler(CallbackQueryHandler(on_button))

    tz = ZoneInfo(TIMEZONE)
    for hour in WORK_HOURS:
        app.job_queue.run_daily(
            reminder_job,
            time=time(hour=hour, minute=55, tzinfo=tz),
            days=WORK_WEEKDAYS,
            name=f"stretch-{hour:02d}55",
        )

    logger.info(
        "Bot started. TZ=%s hours=%s weekdays=%s", TIMEZONE, WORK_HOURS, WORK_WEEKDAYS
    )
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

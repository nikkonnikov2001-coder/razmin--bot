"""
Stretch Bot — без 5-ти минут каждый час напоминает встать и размяться.
"""

from __future__ import annotations

import json
import logging
import os
import random
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

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


# ---------- Упражнения ----------
EXERCISES = [
    {"emoji": "🦒", "area": "Шея", "title": "Мягкие повороты",
     "text": "Медленно поверни голову вправо, задержись 5 сек → влево, 5 сек. Повтори 5 раз. Плечи расслаблены."},
    {"emoji": "🦒", "area": "Шея", "title": "Наклоны к плечу",
     "text": "Наклони ухо к правому плечу, задержись 10 сек. Затем к левому. 3 раза в каждую сторону."},
    {"emoji": "🦒", "area": "Шея", "title": "Подбородок — грудь — потолок",
     "text": "Плавно опусти подбородок к груди (5 сек), затем подними взгляд к потолку (5 сек). 5 повторов."},
    {"emoji": "🧘", "area": "Спина", "title": "Кошка-корова стоя",
     "text": "Руки на бёдра. Плавно прогнись назад, затем округли спину вперёд. 8 повторов в медленном темпе."},
    {"emoji": "🧘", "area": "Спина", "title": "Наклоны в стороны",
     "text": "Встань прямо, руки вверх. Наклонись вправо, задержись 5 сек, затем влево. По 5 раз."},
    {"emoji": "🧘", "area": "Спина", "title": "Скрутки стоя",
     "text": "Стоя, руки на пояс. Медленно поворачивай корпус вправо-влево. 10 повторов."},
    {"emoji": "🙆", "area": "Спина", "title": "Потянуться в небо",
     "text": "Сцепи пальцы в замок, выверни ладонями вверх и потянись макушкой вверх. 15 секунд. 3 раза."},
    {"emoji": "👀", "area": "Глаза", "title": "Правило 20-20-20",
     "text": "Посмотри на объект за 6 метров от тебя в течение 20 секунд. Затем поморгай быстро 10 раз."},
    {"emoji": "👀", "area": "Глаза", "title": "Фокус близко-далеко",
     "text": "Вытяни палец на 30 см от лица. Смотри на него 3 сек → на дальний объект 3 сек. Повтори 10 раз."},
    {"emoji": "👀", "area": "Глаза", "title": "Глазная восьмёрка",
     "text": "Представь большую цифру 8 перед собой и «обведи» её глазами. 5 раз в одну, 5 — в другую сторону."},
    {"emoji": "🦵", "area": "Ноги", "title": "Мини-приседания",
     "text": "10 приседаний в удобном темпе. Пятки не отрывай, колени не заводи за носки."},
    {"emoji": "🚶", "area": "Ноги", "title": "Прогулка",
     "text": "Встань и пройдись 2 минуты. По дороге попей воды 💧 и, если есть, выгляни в окно."},
    {"emoji": "🦶", "area": "Ноги", "title": "Подъёмы на носки",
     "text": "15 подъёмов на носки. Можно держаться за стол. Чувствуй работу икр."},
    {"emoji": "💪", "area": "Плечи", "title": "Круги плечами",
     "text": "10 кругов плечами назад, затем 10 вперёд. Руки расслаблены вдоль тела."},
    {"emoji": "✋", "area": "Запястья", "title": "Разминка запястий",
     "text": "Сцепи пальцы в замок, сделай 10 круговых движений в каждую сторону. Потом мягко потяни пальцы на себя."},
    {"emoji": "🤲", "area": "Грудь", "title": "Раскрытие грудной клетки",
     "text": "Сцепи руки в замок за спиной, выпрями локти и подними руки, сводя лопатки. 15 сек × 3."},
]

GREETINGS = [
    "Привет! 👋 Время небольшого перерыва",
    "Эй! 🌟 Пять минут до круглого часа — идеально, чтобы размяться",
    "Минутка заботы о теле 💚",
    "Без пяти! ⏰ Короткий перерыв пойдёт на пользу",
    "Пора оторваться от экрана ✨",
    "Тук-тук 🚪 пришёл напомнить встать",
    "Давай-давай, потянулись 🤸",
]

WATER_TIP = "💧 И не забудь сделать глоток воды!"


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


def build_message() -> tuple[str, InlineKeyboardMarkup]:
    ex = random.choice(EXERCISES)
    greet = random.choice(GREETINGS)
    body = (
        f"{greet}\n\n"
        f"{ex['emoji']} <b>{ex['area']}: {ex['title']}</b>\n"
        f"{ex['text']}\n\n"
        f"{WATER_TIP}"
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Готово", callback_data="done"),
        InlineKeyboardButton("⏭ Пропустить", callback_data="skip"),
    ]])
    return body, kb


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    subs = load_subscribers()
    if chat_id in subs:
        await update.message.reply_text(
            "Ты уже подписан 💚\n"
            "Напоминания: пн–пт, 12:55–20:55 по часовому поясу " + TIMEZONE + ".\n\n"
            "Команды:\n"
            "/next — прислать упражнение прямо сейчас\n"
            "/stop — отключить напоминания"
        )
        return
    subs.add(chat_id)
    save_subscribers(subs)
    await update.message.reply_text(
        "Привет! 👋\n\n"
        "Я буду напоминать тебе вставать и разминаться без 5 минут каждый час.\n"
        f"Расписание: пн–пт, 12:55–20:55 (по времени {TIMEZONE}).\n\n"
        "Команды:\n"
        "/next — прислать упражнение сейчас (тест)\n"
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
            "Окей, напоминания остановлены 🫶\nНапиши /start, когда захочешь вернуться."
        )
    else:
        await update.message.reply_text("Ты и так не подписан. Напиши /start, чтобы включить напоминания.")


async def cmd_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    body, kb = build_message()
    await update.message.reply_text(body, parse_mode="HTML", reply_markup=kb)


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.data == "done":
        await q.answer("Красавчик! 💚")
        status = "\n\n✅ <i>Готово! Так держать 💪</i>"
    else:
        await q.answer("Ок, пропустили")
        status = "\n\n🙈 <i>Пропустили</i>"
    try:
        original_html = q.message.text_html if q.message and q.message.text_html else (q.message.text or "")
        await q.edit_message_text(text=original_html + status, parse_mode="HTML")
    except Exception as e:
        logger.warning("Failed to edit message: %s", e)
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass


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
            body, kb = build_message()
            await context.bot.send_message(
                chat_id=chat_id, text=body, parse_mode="HTML", reply_markup=kb
            )
        except Exception as e:
            logger.warning("Failed to send to %s: %s", chat_id, e)


def main():
    token = os.environ.get("BOT_TOKEN") or BOT_TOKEN
    if not token or token == "PASTE_YOUR_TOKEN_HERE":
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

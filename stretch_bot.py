"""
Stretch Bot — без 5-ти минут каждый час напоминает встать и размяться.
Каждый пользователь задаёт свой диапазон рабочего времени.
"""

from __future__ import annotations

import json
import logging
import os
import random
from datetime import date, datetime, time
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
BOT_TOKEN = ""  # вставь свой токен сюда или задай переменную окружения BOT_TOKEN
TIMEZONE   = "Asia/Krasnoyarsk"
ALL_HOURS  = list(range(6, 23))   # 6:55 … 22:55 — максимально возможный диапазон
WORK_WEEKDAYS = (0, 1, 2, 3, 4)   # пн–пт
# ================================

BASE_DIR         = Path(__file__).resolve().parent
SUBSCRIBERS_FILE = BASE_DIR / "subscribers.json"
LOG_FILE         = BASE_DIR / "bot.log"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("stretch-bot")

# Состояния ConversationHandler для /settime
PICK_START, PICK_END = range(2)


# ─────────────────────────── Хранилище ──────────────────────────────────────

def _default_user() -> dict:
    return {"start": 12, "end": 20, "done": 0, "skip": 0, "last_done": None}


def load_users() -> dict[int, dict]:
    if SUBSCRIBERS_FILE.exists():
        try:
            raw = json.loads(SUBSCRIBERS_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                # миграция старого формата (просто список ID)
                return {cid: _default_user() for cid in raw}
            return {int(k): {**_default_user(), **v} for k, v in raw.items()}
        except Exception as e:
            logger.warning("Failed to load users: %s", e)
    return {}


def save_users(users: dict[int, dict]) -> None:
    SUBSCRIBERS_FILE.write_text(
        json.dumps({str(k): v for k, v in users.items()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


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
    "Привет, {name}! 👋 Время небольшого перерыва",
    "Эй, {name}! 🌟 Пять минут до часа — идеально, чтобы размяться",
    "Минутка заботы о теле, {name} 💚",
    "Без пяти! ⏰ {name}, короткий перерыв пойдёт на пользу",
    "{name}, пора оторваться от экрана ✨",
    "Тук-тук, {name} 🚪 — напоминаю встать",
    "Давай-давай, {name}, потянулись 🤸",
    "Твоё тело говорит спасибо заранее, {name} 🙏",
    "Один раунд разминки — и снова в бой, {name} 💪",
    "Маленький перерыв = большая продуктивность, {name} 🚀",
]

DONE_REACTIONS = [
    ("1",   "🌱 Первый шаг сделан! Начало положено."),
    ("5",   "🔥 Пять выполнено! Ты входишь во вкус."),
    ("10",  "⚡ Десятка! Тело уже чувствует разницу."),
    ("25",  "🏅 25 упражнений — это уже привычка!"),
    ("50",  "🏆 Полтинник! Ты настоящий чемпион разминки."),
    ("100", "👑 СТО упражнений! Легенда. Просто легенда."),
]

SKIP_PHRASES = [
    "Окей, пропустили 🙈 В следующий раз обязательно!",
    "Бывает 😅 Главное — ты не забыл про себя.",
    "Понял, не до этого 🫡 Но шею хотя бы покрути!",
    "Ладно-ладно 😂 Но за тобой должок!",
    "Спишем на форс-мажор 🌪 Следующий раз зачтётся.",
]


# ─────────────────────────── Вспомогательное ────────────────────────────────

def _first_name(update: Update) -> str:
    user = update.effective_user
    return user.first_name if user and user.first_name else "друг"


def _exercise_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Готово", callback_data="done"),
        InlineKeyboardButton("⏭ Пропустить", callback_data="skip"),
    ]])


def _hours_keyboard(prefix: str, from_h: int = 6, to_h: int = 22) -> InlineKeyboardMarkup:
    hours = list(range(from_h, to_h + 1))
    rows = []
    for i in range(0, len(hours), 6):
        rows.append([
            InlineKeyboardButton(f"{h:02d}:00", callback_data=f"{prefix}:{h}")
            for h in hours[i:i + 6]
        ])
    return InlineKeyboardMarkup(rows)


def _done_reaction(total_done: int) -> str:
    for threshold, text in reversed(DONE_REACTIONS):
        if total_done >= int(threshold):
            return text
    return "Отлично! 💚"


def build_exercise(name: str) -> tuple[dict, str]:
    ex = random.choice(EXERCISES)
    greet = random.choice(GREETINGS).format(name=name)
    caption = (
        f"{greet}\n\n"
        f"{ex['emoji']} <b>{ex['area']}: {ex['title']}</b>\n"
        f"{ex['text']}"
    )
    return ex, caption


# ─────────────────────────── Команды ────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    name = _first_name(update)
    users = load_users()

    if chat_id in users:
        u = users[chat_id]
        await update.message.reply_text(
            f"Рад тебя видеть снова, {name}! 👋\n\n"
            f"Твой диапазон: {u['start']:02d}:55 — {u['end']:02d}:55, пн–пт.\n"
            f"Упражнений выполнено: {u['done']} 💪  пропущено: {u['skip']}\n\n"
            "/next — упражнение прямо сейчас\n"
            "/settime — изменить время напоминаний\n"
            "/stats — моя статистика\n"
            "/stop — отключить напоминания"
        )
        return

    users[chat_id] = _default_user()
    save_users(users)
    await update.message.reply_text(
        f"Привет, {name}! 🎉\n\n"
        "Я буду напоминать тебе вставать и разминаться без 5 минут каждый час.\n\n"
        "По умолчанию я работаю с <b>12:55 до 20:55</b>, пн–пт.\n"
        "Можешь изменить диапазон командой /settime\n\n"
        "/next — прислать упражнение прямо сейчас\n"
        "/stats — смотреть статистику\n"
        "/stop — отключить напоминания\n\n"
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
        await update.message.reply_text(
            "Ты и так не подписан. Напиши /start, чтобы включить напоминания."
        )


async def cmd_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = _first_name(update)
    ex, caption = build_exercise(name)
    photo = cards.make_card(ex)
    await update.message.reply_photo(
        photo=InputFile(photo, filename="exercise.png"),
        caption=caption,
        parse_mode="HTML",
        reply_markup=_exercise_keyboard(),
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    name = _first_name(update)
    users = load_users()
    if chat_id not in users:
        await update.message.reply_text(
            "Ты ещё не подписан. Напиши /start!"
        )
        return

    u = users[chat_id]
    done, skip = u["done"], u["skip"]
    total = done + skip
    pct = round(done / total * 100) if total else 0

    if done == 0:
        vibe = "Начни сегодня — первое всегда самое трудное 🌱"
    elif done < 5:
        vibe = "Хорошее начало! Главное — не останавливаться 🔥"
    elif done < 20:
        vibe = "Уже входишь в ритм 💪 Продолжай!"
    elif done < 50:
        vibe = "Ты молодец! Тело скажет тебе спасибо 🏅"
    else:
        vibe = "Машина! Настоящая машина здоровья 🏆"

    text = (
        f"📊 <b>Твоя статистика, {name}</b>\n\n"
        f"✅ Выполнено: <b>{done}</b>\n"
        f"⏭ Пропущено: <b>{skip}</b>\n"
        f"📈 Процент выполнения: <b>{pct}%</b>\n\n"
        f"⏰ Диапазон: {u['start']:02d}:55 – {u['end']:02d}:55, пн–пт\n\n"
        f"{vibe}"
    )
    await update.message.reply_text(text, parse_mode="HTML")


# ─────────────────────────── /settime — выбор времени ───────────────────────

async def cmd_settime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = _first_name(update)
    await update.message.reply_text(
        f"Окей, {name}! С какого часа начинать напоминания? ⏰\n"
        "<i>Напоминание придёт без 5 минут выбранного часа.</i>",
        parse_mode="HTML",
        reply_markup=_hours_keyboard("st", 6, 21),
    )
    return PICK_START


async def picked_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    start_h = int(q.data.split(":")[1])
    context.user_data["start_h"] = start_h
    await q.edit_message_text(
        f"Отлично! С <b>{start_h:02d}:55</b> начнём 🟢\n\n"
        "Теперь до какого часа присылать напоминания?",
        parse_mode="HTML",
        reply_markup=_hours_keyboard("en", start_h + 1, 22),
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
    await q.edit_message_text(
        f"✅ Готово! Сохранил твоё расписание:\n\n"
        f"🕐 С <b>{start_h:02d}:55</b> до <b>{end_h:02d}:55</b>, пн–пт\n"
        f"📬 Это <b>{count}</b> напоминани{'е' if count == 1 else 'я' if 2 <= count <= 4 else 'й'} в день\n\n"
        "Хорошей работы! 💪",
        parse_mode="HTML",
    )
    return ConversationHandler.END


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменили. Настройки не изменились.")
    return ConversationHandler.END


# ─────────────────────────── Кнопки упражнения ──────────────────────────────

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query

    # кнопки упражнения
    chat_id = update.effective_chat.id
    users = load_users()

    if q.data == "done":
        await q.answer("Красавчик! 💚")
        if chat_id in users:
            users[chat_id]["done"] += 1
            users[chat_id]["last_done"] = date.today().isoformat()
            save_users(users)
            total_done = users[chat_id]["done"]
            reaction = _done_reaction(total_done)
        else:
            total_done = 1
            reaction = "Отлично! 💚"
        status = f"\n\n✅ <i>{reaction}  (всего выполнено: {total_done})</i>"

    else:
        await q.answer(random.choice(["Ок, пропустили 🙈", "Бывает! 😅"]))
        if chat_id in users:
            users[chat_id]["skip"] += 1
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
        logger.warning("Failed to edit message: %s", e)
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:
            pass


# ─────────────────────────── Планировщик ────────────────────────────────────

async def reminder_job(context: ContextTypes.DEFAULT_TYPE):
    current_hour: int = context.job.data
    now = datetime.now(ZoneInfo(TIMEZONE))
    if now.weekday() not in WORK_WEEKDAYS:
        return

    users = load_users()
    if not users:
        return

    for chat_id, u in list(users.items()):
        if not (u["start"] <= current_hour <= u["end"]):
            continue
        try:
            # имя пользователя неизвестно планировщику — используем заглушку
            ex, caption = build_exercise("друг")
            photo = cards.make_card(ex)
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=InputFile(photo, filename="exercise.png"),
                caption=caption,
                parse_mode="HTML",
                reply_markup=_exercise_keyboard(),
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

    # /settime — диалог выбора времени
    settime_conv = ConversationHandler(
        entry_points=[CommandHandler("settime", cmd_settime)],
        states={
            PICK_START: [CallbackQueryHandler(picked_start, pattern=r"^st:\d+$")],
            PICK_END:   [CallbackQueryHandler(picked_end,   pattern=r"^en:\d+$")],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("stop",  cmd_stop))
    app.add_handler(CommandHandler("next",  cmd_next))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(settime_conv)
    app.add_handler(CallbackQueryHandler(on_button, pattern=r"^(done|skip)$"))

    tz = ZoneInfo(TIMEZONE)
    for hour in ALL_HOURS:
        app.job_queue.run_daily(
            reminder_job,
            time=time(hour=hour, minute=55, tzinfo=tz),
            days=WORK_WEEKDAYS,
            data=hour,
            name=f"stretch-{hour:02d}55",
        )

    logger.info(
        "Bot started. TZ=%s all_hours=%s weekdays=%s",
        TIMEZONE, ALL_HOURS, WORK_WEEKDAYS,
    )
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

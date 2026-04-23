# Stretch Bot — напоминалка размяться

Телеграм-бот, который без 5 минут каждый час (пн–пт, 9:55–18:55) напоминает встать из-за компьютера и прислать короткое упражнение (шея / спина / глаза / ноги / плечи). Есть кнопки «✅ Готово» и «⏭ Пропустить».

## Что тебе нужно

- Windows 10/11 с установленным **Python 3.11+** (`python --version` в PowerShell должен показать версию). Если нет — поставь с [python.org](https://www.python.org/downloads/windows/) и на первом экране установщика галочка **«Add Python to PATH»**.
- **Токен бота** от [@BotFather](https://t.me/BotFather) (у тебя уже есть).

## Файлы в этой папке

- `stretch_bot.py` — сам бот
- `requirements.txt` — зависимости
- `start_bot.bat` — запускает бота фоном (без чёрного окна)
- `README.md` — эта инструкция

## Шаг 1. Установка

Открой PowerShell в папке с этими файлами (Shift+ПКМ в папке → «Открыть окно PowerShell здесь») и выполни:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> Если после `Activate.ps1` ругается на политику безопасности, выполни один раз:
> `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` и подтверди.

## Шаг 2. Вставь токен

Открой `stretch_bot.py` в любом текстовом редакторе и замени:

```python
BOT_TOKEN = "PASTE_YOUR_TOKEN_HERE"
```

на свой токен от BotFather. При желании поправь `TIMEZONE`, `WORK_HOURS`, `WORK_WEEKDAYS`.

## Шаг 3. Первый запуск и подписка

В том же PowerShell (с активным venv):

```powershell
python stretch_bot.py
```

Открой своего бота в Telegram и напиши **`/start`** — так он запомнит твой chat_id. Попробуй **`/next`** — должно прилететь упражнение. Останови скрипт Ctrl+C.

## Шаг 4. Автозапуск через Планировщик задач

Чтобы бот работал фоном после каждого включения компьютера.

1. В `start_bot.bat` раскомментируй строку `call .venv\Scripts\activate.bat` (убери `REM`), если используешь venv.
2. Нажми <kbd>Win</kbd>+<kbd>R</kbd> → `taskschd.msc` → **Enter**.
3. Правая панель → **«Создать задачу…»** (Create Task). Не «простую».
4. Вкладка **General**:
   - Имя: `Stretch Bot`
   - Галочка **«Run only when user is logged on»** (обычный режим, без пароля)
5. Вкладка **Triggers** → **New** → Begin the task: **At log on** → твой пользователь. OK.
6. Вкладка **Actions** → **New**:
   - Action: **Start a program**
   - Program/script: путь к `start_bot.bat` (жми Browse)
   - Start in: путь к этой же папке (без кавычек)
7. Вкладка **Conditions** → сними галочку «Start the task only if the computer is on AC power», если у тебя ноутбук.
8. Вкладка **Settings** → галочка **«If the task fails, restart every: 1 minute», попыток 3**.
9. OK. Выдели задачу в списке → **Run** — проверь, что бот стартовал (в Telegram напиши `/next`).

Логи пишутся в `bot.log` рядом со скриптом.

## Команды бота

| Команда | Что делает |
|---|---|
| `/start` | Подписаться на напоминания |
| `/stop`  | Отписаться |
| `/next`  | Прислать упражнение прямо сейчас |

## Как остановить бота

- Вручную: в Диспетчере задач найди процесс `pythonw.exe` и заверши.
- Через планировщик: `taskschd.msc` → задача **Stretch Bot** → **End**/**Disable**.

## Настройки внутри `stretch_bot.py`

```python
TIMEZONE = "Europe/Moscow"
WORK_HOURS = list(range(9, 19))    # 9..18 → триггеры в 9:55…18:55
WORK_WEEKDAYS = (0, 1, 2, 3, 4)    # 0=Пн, 6=Вс
```

Хочешь добавить свои упражнения — просто допиши словари в список `EXERCISES` вверху файла.

Удачи и не засиживайся 💪

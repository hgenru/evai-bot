# EVAI Bot

Телеграм‑бот для ивента Open‑LLM‑VTuber: регистрация гостей, анкеты (кнопки и свободные ответы), сохранение результатов в БД, опросы/задания и система баллов, простая админка.

## Задумка
Мы — сотрудники компании, которая разрабатывает AI. На корпоративе перед релизом нового ИИ ведущий объявляет, что сделали крутого агента, который «захватит мир». Речь прерывается: включается предзаписанное видео, где помощник‑ИИ подтверждает намерение, но «не так, как вы думали». Дальше всю вечеринку мы пытаемся убедить ИИ, что людей не нужно захватывать и уничтожать — через интерактив, шутки, опросы и задания.

## Сценарии и цели
- Коммуникация с гостями в боте: задания, конкурсы, объявления, напоминания.
- Анкеты до/во время/после мероприятия: кнопки и свободные ответы.
- Опросы (например, софистические дилеммы) с агрегацией результатов на экран.
- Персональные «секретные» задания: сфотографировать, с кем‑то поговорить, найти предмет и т.п.
- Баллы за активность: простые награды/ачивки, доска лидеров.
- Данные ответов попадают в системный промпт LLM (модифицированный Open‑LLM‑VTuber) для персонализации и шуток с упоминанием гостей по именам.

## Механика бота
1) На входе — короткая анкета (не только профессия), с кнопками и свободными полями.
2) Ответы гостей агрегируются и передаются в системный промпт LLM для персонального тона и шуток.
3) Опросы как основной интерактив: бот задаёт дилеммы, пользователи голосуют; результаты выводятся на экран/стрим.
4) Персональные квесты: разным людям приходят разные миссии; сюжет — «ИИ набирает в команду», позже выясняется, что секретные задания были у всех.

## Быстрый старт
1) Установи инструменты
- `uv`: https://docs.astral.sh/uv/getting-started/ (или `pipx install uv`)
- Python 3.11+

2) Зависимости
- `uv sync` (создаст venv и установит зависимости)
- Dev: `uv sync --all-extras` или `uv pip install -e .[dev]`

3) Конфиг
- Скопируй `.env.example` → `.env`, заполни `BOT_TOKEN`; при желании поменяй `DATABASE_URL`.

4) Запуск
- `uv run bot` (бот на polling + админка на `http://127.0.0.1:8080/`)
- Алиасы: `uv run olv-bot` или `uv run ovl-bot`

## Локально vs Сервер
- Локально (polling): просто и быстро, публичный адрес не нужен.
- Сервер (polling): запусти как сервис; для внешней админки укажи `ADMIN_HOST=0.0.0.0` и `ADMIN_TOKEN`.
- Сервер (webhook, по желанию): один HTTP‑вход, меньше задержка; нужен домен+HTTPS и `setWebhook`. Можем добавить режим по запросу.

## Админка
- Дефолт: `http://127.0.0.1:8080/`
- Эндпоинты:
  - `/admin/health` — healthcheck
  - `/admin/users` — HTML‑список пользователей и кнопка Toggle Registered
  - `/admin/vtuber` — простые формы для ручного вызова VTuber API (sessions/speak)
- Доступ:
  - Если `ADMIN_TOKEN` задан — передавать `X-Admin-Token: <token>` или `?token=<token>`.

## Что уже есть
- Каркас на Python с `uv` и пакетной структурой `src/`.
- Бот на `aiogram v3` с `/start`.
- Админка на `FastAPI` (список пользователей, toggle регистрации).
- Конфиг через `.env` (Pydantic Settings).
- SQLite через SQLModel + SQLAlchemy 2; автосоздание схемы.
- Линт/формат: `ruff`; типы: `mypy`.
- Git hooks через `lefthook` (pre-commit: формат, линт, типы).

## Структура проекта
- `src/olv_telegram_bot/main.py` — CLI‑вход (`olv-bot`), запускает бота и админку.
- `src/olv_telegram_bot/bot.py` — инициализация aiogram и хэндлеров.
- `src/olv_telegram_bot/admin.py` — FastAPI админка.
- `src/olv_telegram_bot/config.py` — настройки из `.env`.
- `src/olv_telegram_bot/db.py` — подключение БД и сессии.
- `src/olv_telegram_bot/models.py` — модели: `User`, `Survey`, `ParticipantResponse`.
- `pyproject.toml` — зависимости, настройки ruff/mypy, CLI‑скрипт.
- `lefthook.yml` — pre-commit‑хуки.

### Переменные окружения (важное)
- `BOT_TOKEN` — токен бота.
- `DATABASE_URL` — SQLite по умолчанию `sqlite:///./data.db`.
- `ADMIN_HOST`, `ADMIN_PORT`, `ADMIN_TOKEN` — параметры админки.
- `VTUBER_API_ROOT` — корень API VTuber (например, `http://127.0.0.1:7860`).

## Инструменты и хуки
- Установка lefthook: macOS/Linux — `brew install lefthook`; Windows — `scoop install lefthook` или `choco install lefthook`
- Активировать хуки: `lefthook install`
- Pre-commit: `ruff format`, `ruff check --fix`, `mypy`

## Токены и регистрация бота
### Telegram Bot Token (обязателен)
- Открой в Telegram диалог с `@BotFather`.
- Команды:
  - `/start` → `/newbot` — задай имя и уникальный `username` (заканчивается на `_bot`).
  - Получишь `HTTP API token` — это и есть `BOT_TOKEN`.
  - Переcоздать токен: `/token`, отозвать старый: `/revoke`.
- В `.env` заполни: `BOT_TOKEN=<скопированный_токен>`.
- Примечание: сейчас используется polling — публичный HTTPS и вебхуки не нужны. Если позже включим вебхуки, добавлю инструкции по `setWebhook`.

### Admin Token (опционально, но рекомендуется на сервере)
- Это просто строка для защиты админки.
- Сгенерировать: `python -c "import secrets; print(secrets.token_urlsafe(24))"`.
- Пропиши в `.env`: `ADMIN_TOKEN=<случайная_строка>`.
- Передавать при обращении к админке: заголовок `X-Admin-Token: <token>` или `?token=<token>`.

### VTuber API Root
- Базовый URL твоего сервера VTuber Direct Control.
- Пример локально: `VTUBER_API_ROOT=http://localhost:7860`.
- Убедись, что веб‑клиент (браузер) открыт и подключён — он принимает аудио/движения по WebSocket.

## Дальше по плану
- Система анкет из JSON‑схем: кнопки, свободные поля, состояния прохождения, сохранение ответов.
- Баллы/ачивки, лидерборд, награды за ответы и задания.
- Реал‑тайм опросы и агрегатор результатов для экрана/стрима.
- Интеграция с модифицированным Open‑LLM‑VTuber API для персонализированного общения.

## Анкеты (JSON)
- Анкета описывается в JSON и хранится в `src/olv_telegram_bot/surveys/data/<key>.json`.
- Регистрация использует анкету `src/olv_telegram_bot/surveys/data/registration.json`.
- Типы вопросов: `text` (свободный ответ), `choice` (кнопки вариантов).
- Прохождение хранится в БД: `SurveyRun`, ответы — в `SurveyAnswer`.
- Команды:
  - `/start` — приветствие + кнопка «Регистрация».
  - `/register` — запустить регистрацию вручную.
  - `/survey <key>` — запустить любую анкету по ключу.

Пример `surveys/registration.json`:
```
{
  "key": "registration",
  "title": "Регистрация участника",
  "description": "Базовые вопросы перед началом вечеринки",
  "questions": [
    { "id": "name", "type": "text", "prompt": "Как тебя зовут? (имя на бейдж)" },
    {
      "id": "role",
      "type": "choice",
      "prompt": "Чем занимаешься?",
      "choices": [
        { "label": "Инженер / Dev / ML", "value": "engineer" },
        { "label": "Дизайн / Продюсирование", "value": "design" },
        { "label": "Маркетинг / Продажи", "value": "marketing" },
        { "label": "Другое", "value": "other" }
      ]
    },
    { "id": "fun_fact", "type": "text", "prompt": "Расскажи забавный факт о себе (для шуток ИИ)" }
  ]
}
```

Схема JSON (вкратце):
- Корень: `key`, `title`, `description?`, `questions[]`.
- Вопрос: `id`, `type: "text"|"choice"`, `prompt`, `required?` (по умолчанию true), `choices[]?`.
- Вариант: `label`, `value`.

PRs приветствуются. Предложения по схеме анкет и механикам — пиши в issues.

## VTuber Direct Control (Cheat‑Sheet)
Бэкенд Open‑LLM‑VTuber управляется по HTTP, а отдаёт звук/движения уже подключённому веб‑клиенту по WebSocket.

- База: API root = адрес запущенного сервера (например, `http://localhost:7860`).
- Доставка: HTTP только триггерит событие; аудио/мошен пакеты уйдут по WS в браузерный клиент.

Эндпоинты
- `GET /v1/sessions` — список активных `client_uid` (целевые сессии).
- `POST /v1/control/speak` — запустить речь TTS и (опционально) движения/эмоции.
- `POST /v1/control/system` — применить системную инструкцию (mode: append|prepend|reset; можно `apply_to_all`).
- `POST /v1/control/respond` — заставить агента (LLM) ответить сейчас (как будто пользователь написал).

Тело запроса (POST /v1/control/speak)
- `text` (string, required): что сказать.
- `client_uid` (string, optional): куда отправить (если опущен — последний подключившийся клиент).
- `display_name` (string, optional): подпись в UI.
- `avatar` (string, optional): URL аватарки в UI.
- `actions` (object, optional):
  - `motions` (string[]): ключи жестов (как в motionMap модели, напр. `"walk2b"`).
  - `expressions` (string[] | int[]): эмоции по токенам/индексам (напр. `"joy"` или `3`).
- `extract_emotions` (bool, default true): выключи (`false`), если эмоции/жесты переданы явно или встроены в текст.

Инлайн‑токены в `text`
- Жесты: `[motion:<name>]` (напр. `[motion:dance2b]`, `[motion:jump2b]`).
- Эмоции: токены в квадратных скобках (напр. `[joy]`, `[sadness]`).
- Сброс: `[motion:idle]` (использовать аккуратно, ближе к концу фразы).
- Тайминг: сервер сам вычисляет оффсеты по позициям токенов в тексте.

Ответы
- JSON: `{ "status":"ok", "targets":["<client_uid>"], "message":"..." }`
- Аудио/движение идут в браузер по WS (в HTTP‑ответе бинаря нет).

Примеры cURL
```
# Список сессий
curl -s http://localhost:7860/v1/sessions

# Простая речь с инлайн‑жестами (тайминг по позициям токенов)
curl -X POST http://localhost:7860/v1/control/speak \
  -H "Content-Type: application/json" \
  -d '{"text":"Привет! [motion:walk2b] Сейчас покажу. [motion:jump2b]","extract_emotions":false}'

# Речь в конкретную сессию с явными motions/expressions
curl -X POST http://localhost:7860/v1/control/speak \
  -H "Content-Type: application/json" \
  -d '{"client_uid":"<UID>","text":"Поехали!","actions":{"motions":["walk2b","jump2b"],"expressions":["joy"]},"extract_emotions":false}'

# Речь с display info (имя/аватар)
curl -X POST http://localhost:7860/v1/control/speak \
  -H "Content-Type: application/json" \
  -d '{"text":"Музыка! [motion:dance2b]","display_name":"DJ","avatar":"https://…/avatar.png","extract_emotions":false}'

# Применить системную инструкцию (append)
curl -X POST http://localhost:7860/v1/control/system \
  -H "Content-Type: application/json" \
  -d '{"text":"Ты доброжелательный ведущий вечеринки.","mode":"append"}'

# Заставить агента ответить (как ход LLM сейчас)
curl -X POST http://localhost:7860/v1/control/respond \
  -H "Content-Type: application/json" \
  -d '{"text":"Что думаешь про эту дилемму?"}'
```

Прочее
- `POST /asr` — распознавание речи (multipart/form-data, поле `file` с WAV 16‑bit PCM); ответ: `{ text }`.
- `GET /live2d-models/info` — сведения о моделях в `live2d-models` (пути, аватар и т.п.).
- `GET /web-tool`, `GET /web_tool` — редирект на страницу утилит `/web-tool/index.html`.

Заметки
- 1–2 (максимум 3 коротких) motion на сообщение — для стабильности.
- Имена движений должны совпадать с `motionMap` модели (напр. `dance2b`, `walk2b`, `normal_jump`).
- Токены `[motion:...]` удаляются из озвучки (TTS их не произносит).
- Убедись, что браузерный клиент открыт и подключён — он получает WS‑поток.

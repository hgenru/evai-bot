# OLV Telegram Bot

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
- `uv run olv-bot` (бот на polling + админка на `http://127.0.0.1:8080/`)

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

## Дальше по плану
- Система анкет из JSON‑схем: кнопки, свободные поля, состояния прохождения, сохранение ответов.
- Баллы/ачивки, лидерборд, награды за ответы и задания.
- Реал‑тайм опросы и агрегатор результатов для экрана/стрима.
- Интеграция с модифицированным Open‑LLM‑VTuber API для персонализированного общения.

PRs приветствуются. Предложения по схеме анкет и механикам — пиши в issues.

## VTuber Direct Control (Cheat‑Sheet)
Бэкенд Open‑LLM‑VTuber управляется по HTTP, а отдаёт звук/движения уже подключённому веб‑клиенту по WebSocket.

- База: API root = адрес запущенного сервера (например, `http://localhost:7860`).
- Доставка: HTTP только триггерит событие; аудио/мошен пакеты уйдут по WS в браузерный клиент.

Эндпоинты
- `GET /v1/sessions` — список активных `client_uid` (целевые сессии).
- `POST /v1/direct-control/speak` — запустить речь TTS и (опционально) движения/эмоции.

Тело запроса (POST /v1/direct-control/speak)
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
curl -X POST http://localhost:7860/v1/direct-control/speak \
  -H "Content-Type: application/json" \
  -d '{"text":"Привет! [motion:walk2b] Сейчас покажу. [motion:jump2b]","extract_emotions":false}'

# Речь в конкретную сессию с явными motions/expressions
curl -X POST http://localhost:7860/v1/direct-control/speak \
  -H "Content-Type: application/json" \
  -d '{"client_uid":"<UID>","text":"Поехали!","actions":{"motions":["walk2b","jump2b"],"expressions":["joy"]},"extract_emotions":false}'

# Речь с display info (имя/аватар)
curl -X POST http://localhost:7860/v1/direct-control/speak \
  -H "Content-Type: application/json" \
  -d '{"text":"Музыка! [motion:dance2b]","display_name":"DJ","avatar":"https://…/avatar.png","extract_emotions":false}'
```

Заметки
- 1–2 (максимум 3 коротких) motion на сообщение — для стабильности.
- Имена движений должны совпадать с `motionMap` модели (напр. `dance2b`, `walk2b`, `normal_jump`).
- Токены `[motion:...]` удаляются из озвучки (TTS их не произносит).
- Убедись, что браузерный клиент открыт и подключён — он получает WS‑поток.

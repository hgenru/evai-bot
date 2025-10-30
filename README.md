# EVAI Bot

Телеграм‑бот для ивента с простой админкой: регистрация гостей, анкеты/опросы, показ результатов на проекторе, рассылка сообщений.

## Быстрый старт
1) Инструменты
- `uv`: https://docs.astral.sh/uv/getting-started/
- Python 3.11+

2) Зависимости
- `uv sync` (создаст venv и установит зависимости)
- Dev: `uv sync --all-extras` или `uv pip install -e .[dev]`

3) Конфиг
- Скопируй `.env.example` → `.env`
- Заполни `BOT_TOKEN`; при желании поменяй `DATABASE_URL`

4) Запуск
- `uv run bot` (бот + админка на `http://127.0.0.1:8080/`)
- Алиасы: `uv run evai-bot` или `uv run bot`

## Админка (основное)
Базовый адрес: `http://127.0.0.1:8080/`. Если в `.env` задан `ADMIN_TOKEN` — передавай `X-Admin-Token: <token>` или `?token=<token>`.

- `/admin/users` — список пользователей, переключение регистрации, просмотр ответов
- `/admin/surveys` — результаты регистрационного опроса
  - Сверху — копируемый текст по людям (Имя → Вопрос: ответ)
  - Ниже — статистика по вариантам
- `/admin/polls` — управление опросами (кроме регистрации)
  - Каждый вопрос отдельным блоком: «Вопрос», «Статус», «Текст», [Старт] (сразу рассылает), [Viewer]
- `/admin/messages` — отправка сообщений
  - Броадкаст (всем/зарегистрированным) и отправка одному (селектор пользователя или tg_id/username)

Viewer для экрана/OBS: `/live/survey/<key>` — полноэкранный график, автообновление раз в ~2s.

## Формат анкет/опросов (JSON)
- Файлы: `src/evai_bot/surveys/data/<key>.json`
- Регистрация — особый опрос `registration.json` (старт после `/start`, итоги на `/admin/surveys`)
- Типы вопросов: `text` и `choice`
- Поля:
  - Опрос: `key`, `title`, `description?`, `image_url?`, `questions[]`
  - Вопрос: `id`, `type`, `prompt`, `required?`, `image_url?`, `choices?`
  - Вариант: `label`, `value`, `color?` (цвет столбика на viewer)

Пример `surveys/registration.json`:
```
{
  "key": "registration",
  "title": "Регистрация участника",
  "description": "Базовые вопросы перед началом вечеринки",
  "questions": [
    { "id": "name", "type": "text", "prompt": "Как тебя зовут? (имя на бейдж)" },
    { "id": "role", "type": "choice", "prompt": "Чем занимаешься?",
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

Примеры готовых опросов:
- `blue_red.json` — «синяя или красная кнопка»
- `pledge.json` — «Клятва верности ИИ» (Да/Нет)

## Что внутри
- Бот на `aiogram v3` (`/start` запускает регистрацию)
- Админка на `FastAPI`
- Конфиг через `.env` (Pydantic Settings)
- SQLite (SQLModel + SQLAlchemy 2); автосоздание схемы
- Линт/формат: `ruff`; типы: `mypy`

## Переменные окружения (важное)
- `BOT_TOKEN` — токен бота
- `DATABASE_URL` — по умолчанию `sqlite:///./data.db`
- `ADMIN_HOST`/`ADMIN_PORT` — адрес админки (по умолчанию `127.0.0.1:8080`)
- `ADMIN_TOKEN` — токен доступа к админке (рекомендуется на сервере)
- `VTUBER_API_ROOT` — (опционально) адрес внешнего VTuber‑API для вкладки `/admin/vtuber`

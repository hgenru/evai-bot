# EVAI Bot

Телеграм‑бот для ивента с простой админкой: регистрация гостей, анкеты/опросы, показ результатов на проекторе, рассылка сообщений.

## Быстрый старт
- Инструменты: `uv` (https://docs.astral.sh/uv/getting-started/), Python 3.11+
- Установка зависимостей: `uv sync`
- Dev‑режим: `uv sync --all-extras` или `uv pip install -e .[dev]`
- Конфиг: скопируй `.env.example` → `.env`, заполни `BOT_TOKEN` (при желании поменяй `DATABASE_URL`)
- Запуск: `uv run bot` (админка на `http://127.0.0.1:8080/`)

## Админка
- Базовый адрес: `http://127.0.0.1:8080/`
- Доступ: если в `.env` задан `ADMIN_TOKEN` — передавай `X-Admin-Token: <token>` или `?token=<token>`

### Users
- Список пользователей, переключение регистрации, просмотр ответов.

### Surveys (Регистрация)
- Итоги регистрационного опроса.
- Текст для копирования по людям + статистика по вариантам.

### Polls
- Управление опросами (кроме регистрации).
- Каждый вопрос — отдельный блок: «Вопрос», «Статус», «Текст», кнопки [Старт] (сразу рассылает) и [Viewer].

### Messages
- Броадкаст (всем/зарегистрированным) и отправка одному (выбор из списка или по tg_id/username).

### Viewer
- `/live/survey/<key>` — полноэкранный график с автообновлением (~2s), адаптивный под экран.

## Формат анкет/опросов (JSON)
- Файлы: `src/evai_bot/surveys/data/<key>.json`
- Регистрация — особый опрос `registration.json` (старт после `/start`, итоги на `/admin/surveys`)
- Типы: `text` и `choice`
- Поля опроса: `key`, `title`, `description?`, `image_url?`, `questions[]`
- Поля вопроса: `id`, `type`, `prompt`, `required?`, `image_url?`, `choices?`
- Поля варианта: `label`, `value`, `color?` (цвет столбика на viewer)

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

Примеры опросов: `blue_red.json` (синяя/красная кнопка), `pledge.json` (клятва ИИ — Да/Нет).

## Что внутри
- Бот: `aiogram v3` (`/start` запускает регистрацию)
- Админка: `FastAPI`
- Конфиг: `.env` (Pydantic Settings)
- Хранилище: SQLite (SQLModel + SQLAlchemy 2); автосоздание схемы
- Качество: `ruff` (формат/линт), `mypy` (типы)

## Переменные окружения
- `BOT_TOKEN` — токен бота
- `DATABASE_URL` — по умолчанию `sqlite:///./data.db`
- `ADMIN_HOST`/`ADMIN_PORT` — адрес админки (по умолчанию `127.0.0.1:8080`)
- `ADMIN_TOKEN` — токен доступа к админке (рекомендуется на сервере)
- `VTUBER_API_ROOT` — (опционально) адрес внешнего VTuber‑API для вкладки `/admin/vtuber`

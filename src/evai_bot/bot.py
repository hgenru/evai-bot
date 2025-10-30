from __future__ import annotations

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from .config import Settings
from .db import get_session, init_db
from .models import SurveyRun, User, LivePollVote
from .surveys.engine import (
    complete_run,
    get_current_question,
    get_or_create_user,
    load_survey,
    record_answer_and_advance,
    start_survey_run,
)


router = Router()


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    tg_user = message.from_user
    if not tg_user:
        return
    if getattr(tg_user, "is_bot", False):
        return
    _ = get_or_create_user(
        tg_id=tg_user.id,
        username=tg_user.username,
        first_name=tg_user.first_name,
        last_name=tg_user.last_name,
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Заполнить анкету", callback_data="survey:start:registration")]]
    )
    await message.answer(
        "Привет! Добро пожаловать на EVAI Internal Pre‑Launch Party. Нажми, чтобы пройти регистрацию.",
        reply_markup=kb,
    )


@router.message(Command("register"))
async def cmd_register(message: Message) -> None:
    await start_survey_flow(message, survey_key="registration")


@router.message(Command("survey"))
async def cmd_survey(message: Message) -> None:
    # Usage: /survey <key>
    text = message.text or ""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Формат: /survey <key> (напр., /survey registration)")
        return
    key = parts[1].strip()
    try:
        # probe load to validate key
        _ = load_survey(key)
    except Exception:
        await message.answer("Анкета не найдена")
        return
    await start_survey_flow(message, survey_key=key)


async def start_survey_flow(message: Message, *, survey_key: str, tg_user_override=None) -> None:
    tg_user = tg_user_override or message.from_user
    if not tg_user:
        return
    if getattr(tg_user, "is_bot", False):
        return
    user = get_or_create_user(
        tg_id=tg_user.id,
        username=tg_user.username,
        first_name=tg_user.first_name,
        last_name=tg_user.last_name,
    )
    spec = load_survey(survey_key)
    run = start_survey_run(user_id=user.id or 0, survey_key=spec.key)
    await present_current_question(message, run, spec)


async def present_current_question(message_or_cb: Message | CallbackQuery, run: SurveyRun, spec):
    q = get_current_question(run, spec)
    if not q:
        complete_run(run.id or 0)
        text = "Готово! Регистрация завершена."
        if isinstance(message_or_cb, CallbackQuery):
            await message_or_cb.message.edit_text(text)
            await message_or_cb.answer()
        else:
            await message_or_cb.answer(text)
        # Mark user as registered (best-effort)
        with get_session() as session:
            u = session.get(User, run.user_id)
            if u:
                u.is_registered = True
                session.add(u)
                session.commit()
        return
    if q.type == "choice" and q.choices:
        rows = [
            [
                InlineKeyboardButton(
                    text=c.label,
                    callback_data=f"survey:answer:{run.id}:{q.id}:{c.value}",
                )
            ]
            for c in q.choices
        ]
        kb = InlineKeyboardMarkup(inline_keyboard=rows)
        text = q.prompt
        if isinstance(message_or_cb, CallbackQuery):
            await message_or_cb.message.edit_text(text, reply_markup=kb)
            await message_or_cb.answer()
        else:
            await message_or_cb.answer(text, reply_markup=kb)
    else:
        # text question: prompt and expect next message
        text = q.prompt + "\n(введите текст и отправьте)"
        if isinstance(message_or_cb, CallbackQuery):
            await message_or_cb.message.edit_text(text)
            await message_or_cb.answer()
        else:
            await message_or_cb.answer(text)


@router.callback_query(F.data.startswith("survey:start:"))
async def cb_start_survey(cb: CallbackQuery) -> None:
    survey_key = cb.data.split(":", 2)[2]
    # Use the user who clicked the button, not the bot (message author)
    await start_survey_flow(cb.message, survey_key=survey_key, tg_user_override=cb.from_user)
    await cb.answer()


@router.callback_query(F.data.startswith("survey:answer:"))
async def cb_choice_answer(cb: CallbackQuery) -> None:
    try:
        _, _, run_id_s, question_id, value = cb.data.split(":", 4)
        run_id = int(run_id_s)
    except Exception:
        await cb.answer("Некорректные данные кнопки", show_alert=True)
        return
    # Persist and advance
    run = record_answer_and_advance(run_id, question_id, choice=value)
    spec = load_survey(run.survey_key)
    await present_current_question(cb, run, spec)


@router.callback_query(F.data.startswith("livepoll:"))
async def cb_livepoll(cb: CallbackQuery) -> None:
    try:
        _, survey_key, question_id, value = cb.data.split(":", 3)
    except Exception:
        await cb.answer("Некорректные данные кнопки", show_alert=True)
        return
    tg_user = cb.from_user
    if not tg_user:
        await cb.answer()
        return
    user = get_or_create_user(
        tg_id=tg_user.id,
        username=tg_user.username,
        first_name=tg_user.first_name,
        last_name=tg_user.last_name,
    )
    from sqlmodel import select
    with get_session() as session:
        existing = session.exec(
            select(LivePollVote).where(
                (LivePollVote.user_id == (user.id or 0))
                & (LivePollVote.survey_key == survey_key)
                & (LivePollVote.question_id == question_id)
            )
        ).first()
        if existing:
            existing.value = value
            session.add(existing)
        else:
            v = LivePollVote(user_id=user.id or 0, survey_key=survey_key, question_id=question_id, value=value)
            session.add(v)
        session.commit()
    await cb.answer("Голос учтён")


@router.message()
async def on_any_message(message: Message) -> None:
    tg_user = message.from_user
    if not tg_user or getattr(tg_user, "is_bot", False) or not message.text:
        return
    # Find active run for this user
    from sqlmodel import select

    with get_session() as session:
        user = session.exec(select(User).where(User.tg_id == tg_user.id)).first()
        if not user:
            return
        run = session.exec(
            select(SurveyRun).where(
                (SurveyRun.completed_at.is_(None)) & (SurveyRun.user_id == user.id)
            )
        ).first()
        if not run:
            return
        spec = load_survey(run.survey_key)
        q = get_current_question(run, spec)
        if not q or q.type != "text":
            return
    # Record answer and present next
    run = record_answer_and_advance(run.id or 0, q.id, text=message.text.strip())
    spec = load_survey(run.survey_key)
    await present_current_question(message, run, spec)


async def run_bot() -> None:
    settings = Settings()
    init_db()

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()
    dp.include_router(router)

    await dp.start_polling(bot)

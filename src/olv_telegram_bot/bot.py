from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from .config import Settings
from .db import init_db


router = Router()


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    await message.answer(
        "Привет! Добро пожаловать на OLV party. "
        "Скоро запустим регистрацию и анкеты."
    )


async def run_bot() -> None:
    settings = Settings()
    init_db()

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()
    dp.include_router(router)

    await dp.start_polling(bot)


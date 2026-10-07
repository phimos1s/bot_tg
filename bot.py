import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

# --- Конфигурация ---
# Токен берём из переменной окружения BOT_TOKEN (задаётся на Render)
TOKEN = os.getenv("BOT_TOKEN")

# Render автоматически подставляет URL вашего сервиса в RENDER_EXTERNAL_URL
WEBHOOK_HOST = os.getenv("RENDER_EXTERNAL_URL")

# Проверка, чтобы не запустился с пустыми значениями
if not TOKEN:
    raise ValueError("Не задана переменная окружения BOT_TOKEN!")
if not WEBHOOK_HOST:
    raise ValueError("Не задана переменная окружения RENDER_EXTERNAL_URL! (Render обычно делает это сам)")

WEBHOOK_PATH = f"/webhook/{TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# --- Инициализация ---
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- Обработчики ---
@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    await message.answer(f"Привет, {html.bold(message.from_user.full_name)}! Бот работает через Webhook на Render.")

@dp.message()
async def echo_handler(message: Message) -> None:
    if message.text:
        await message.answer(message.text)
    else:
        await message.answer("Я понимаю только текст :)")

# --- Настройка Webhook ---
async def on_startup(bot: Bot):
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook установлен на {WEBHOOK_URL}")

async def on_shutdown(bot: Bot):
    await bot.delete_webhook()
    logging.warning("Завершение работы...")

# --- Создание Aiohttp приложения ---
def main() -> web.Application:
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    return app

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # ВАЖНО: Render требует порт 10000 по умолчанию.
    # Если не указать его явно, Render будет постоянно перезапускать бота.
    web.run_app(main(), host="0.0.0.0", port=10000)

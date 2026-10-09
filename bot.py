import asyncio
import logging
import os
import traceback
from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

# --- Конфигурация ---
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_HOST = os.getenv("RENDER_EXTERNAL_URL")

if not TOKEN:
    raise ValueError("Не задана переменная окружения BOT_TOKEN!")
if not WEBHOOK_HOST:
    raise ValueError("Не задана переменная окружения RENDER_EXTERNAL_URL!")

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
def build_app() -> web.Application:
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    return app

# --- Супервизор: бесконечный перезапуск при сбоях ---
def run_forever():
    while True:
        try:
            logging.info("Запуск веб-сервера...")
            web.run_app(build_app(), host="0.0.0.0", port=10000, handle_signals=False)
            # Если сервер завершился нормально (без исключения) — тоже перезапускаем
            logging.warning("Сервер остановился. Перезапуск через 5 секунд...")
        except KeyboardInterrupt:
            logging.info("Получен сигнал остановки. Выход.")
            break
        except Exception as e:
            logging.error(f"Сервер упал с ошибкой: {e}")
            logging.error(traceback.format_exc())
            logging.warning("Перезапуск через 5 секунд...")
        # Небольшая пауза, чтобы не спамить в логи при мгновенных падениях
        import time
        time.sleep(5)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_forever()

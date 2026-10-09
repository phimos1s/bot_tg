import asyncio
import logging
import os
import traceback
from aiogram import Bot, Dispatcher, html, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
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

# --- Настройки товаров и оплаты ---
# ⚠️ ЗАМЕНИТЕ эти ссылки на свои реальные ссылки на оплату
STAR_PACKAGES = {
    "100": {
        "stars": 100,
        "price": "100 ₽",
        "pay_url": "https://example.com/pay/100",  # ← ЗАМЕНИТЕ
    },
    "180": {
        "stars": 180,
        "price": "180 ₽",
        "pay_url": "https://example.com/pay/180",  # ← ЗАМЕНИТЕ
    },
    "500": {
        "stars": 500,
        "price": "500 ₽",
        "pay_url": "https://example.com/pay/500",  # ← ЗАМЕНИТЕ
    },
}


# --- Клавиатуры ---
def get_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👤 Личный кабинет", callback_data="personal_cabinet")],
            [InlineKeyboardButton(text="⭐ Купить звёзды", callback_data="buy_stars")],
            [InlineKeyboardButton(text="🤝 Реферальная система", callback_data="referral_system")],
        ]
    )


def get_stars_menu() -> InlineKeyboardMarkup:
    buttons = []
    for key, pkg in STAR_PACKAGES.items():
        buttons.append([
            InlineKeyboardButton(
                text=f"⭐ {pkg['stars']} звёзд — {pkg['price']}",
                callback_data=f"buy_pkg_{key}",
            )
        ])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_back_to_stars_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ К выбору пакета", callback_data="buy_stars")],
            [InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_menu")],
        ]
    )


# --- Главное меню ---
@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    user_name = html.bold(message.from_user.full_name) if message.from_user else "друг"
    await message.answer(
        f"Привет, {user_name}! 👋\n\n"
        f"Я бот-магазин. Выбери, что тебя интересует, с помощью кнопок ниже 👇",
        reply_markup=get_main_menu(),
    )


@dp.message(Command("menu"))
async def menu_handler(message: Message) -> None:
    await message.answer("Главное меню:", reply_markup=get_main_menu())


@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu_handler(callback: CallbackQuery) -> None:
    await callback.answer()
    user_name = html.bold(callback.from_user.full_name) if callback.from_user else "друг"
    await callback.message.edit_text(
        f"Привет, {user_name}! 👋\n\n"
        f"Я бот-магазин. Выбери, что тебя интересует, с помощью кнопок ниже 👇",
        reply_markup=get_main_menu(),
    )


# --- Личный кабинет ---
@dp.callback_query(F.data == "personal_cabinet")
async def personal_cabinet_handler(callback: CallbackQuery) -> None:
    await callback.answer()
    user_id = callback.from_user.id
    text = (
        f"👤 <b>Личный кабинет</b>\n\n"
        f"🆔 Ваш ID: <code>{user_id}</code>\n"
        f"⭐ Баланс звёзд: <b>0</b>\n"
        f"💎 Статус: <b>Обычный пользователь</b>\n\n"
        f"Пополнить баланс можно в разделе «Купить звёзды»."
    )
    await callback.message.edit_text(text, reply_markup=get_main_menu())


# --- Купить звёзды ---
@dp.callback_query(F.data == "buy_stars")
async def buy_stars_handler(callback: CallbackQuery) -> None:
    await callback.answer()
    text = (
        "⭐ <b>Купить звёзды</b>\n\n"
        "Выбери подходящий пакет 👇\n\n"
        "💡 Чем больше пакет — тем выгоднее цена за звезду."
    )
    await callback.message.edit_text(text, reply_markup=get_stars_menu())


@dp.callback_query(F.data.startswith("buy_pkg_"))
async def buy_package_handler(callback: CallbackQuery) -> None:
    await callback.answer()
    key = callback.data.replace("buy_pkg_", "")
    pkg = STAR_PACKAGES.get(key)

    if not pkg:
        await callback.message.edit_text(
            "❌ Такого пакета не существует.",
            reply_markup=get_back_to_stars_kb(),
        )
        return

    text = (
        f"⭐ <b>Пакет: {pkg['stars']} звёзд</b>\n\n"
        f"💰 Стоимость: <b>{pkg['price']}</b>\n\n"
        f"Нажми на кнопку ниже, чтобы перейти к оплате 👇\n\n"
        f"После оплаты звёзды будут автоматически начислены на твой счёт."
    )

    pay_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"💳 Оплатить {pkg['price']}", url=pkg["pay_url"])],
            [InlineKeyboardButton(text="⬅️ К выбору пакета", callback_data="buy_stars")],
            [InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_menu")],
        ]
    )

    await callback.message.edit_text(text, reply_markup=pay_kb)


# --- Реферальная система ---
@dp.callback_query(F.data == "referral_system")
async def referral_handler(callback: CallbackQuery) -> None:
    await callback.answer()
    user_id = callback.from_user.id
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
    text = (
        "🤝 <b>Реферальная система</b>\n\n"
        "Приглашай друзей и получай бонусы!\n\n"
        f"🔗 Твоя ссылка:\n<code>{ref_link}</code>\n\n"
        "За каждого приглашённого друга — <b>10 звёзд</b> на твой счёт. 🌟"
    )
    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]]
    )
    await callback.message.edit_text(text, reply_markup=back_kb)


# --- Эхо-хэндлер (заглушка) ---
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
    app = web.Application()

    # СНАЧАЛА health-check с запретом кэширования,
    # чтобы CDN Cloudflare не отдавал старый 404.
    async def health_check(request):
        return web.Response(
            text="OK",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    app.router.add_route('GET', '/health', health_check)
    app.router.add_route('HEAD', '/health', health_check)

    # ПОТОМ всё, что нужно для aiogram
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    return app


# --- Супервизор: бесконечный перезапуск при сбоях ---
def run_forever():
    import time
    port = int(os.getenv("PORT", 10000))
    logging.info(f"Запускаю на порту: {port}")
    while True:
        try:
            logging.info("Запуск веб-сервера...")
            web.run_app(build_app(), host="0.0.0.0", port=port, handle_signals=False)
            logging.warning("Сервер остановился. Перезапуск через 5 секунд...")
        except KeyboardInterrupt:
            logging.info("Получен сигнал остановки. Выход.")
            break
        except Exception as e:
            logging.error(f"Сервер упал с ошибкой: {e}")
            logging.error(traceback.format_exc())
            logging.warning("Перезапуск через 5 секунд...")
        time.sleep(5)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_forever()

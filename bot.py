import asyncio
import logging
import os
import traceback
import hashlib
import hmac
from aiohttp import web
from aiogram import Bot, Dispatcher, html, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiocryptopay import AioCryptoPay, Networks
from aiocryptopay.models.update import Update as CryptoUpdate

# --- Конфигурация ---
TOKEN = os.getenv("8717747702:AAEVSzoUdkJA8opDiwlkh1LmiAhYygFvqvo")
WEBHOOK_HOST = os.getenv("https://bot-tg-141n.onrender.com")
CRYPTO_PAY_TOKEN = os.getenv("646017:AAZ36CYHM1ZLSRfn1lpCk4vyr6yDiy8SVAz")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "fgopf7879")

if not TOKEN:
    raise ValueError("Не задана переменная окружения BOT_TOKEN!")
if not WEBHOOK_HOST:
    raise ValueError("Не задана переменная окружения RENDER_EXTERNAL_URL!")
if not CRYPTO_PAY_TOKEN:
    raise ValueError("Не задана переменная окружения CRYPTO_PAY_TOKEN!")

WEBHOOK_PATH = f"/webhook/{TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
CRYPTO_WEBHOOK_PATH = f"/crypto/{WEBHOOK_SECRET}"

# --- Инициализация ---
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Клиент CryptoPay. Для тестов используйте Networks.TEST_NET и @CryptoTestnetBot
crypto = AioCryptoPay(token=CRYPTO_PAY_TOKEN, network=Networks.MAIN_NET)

# --- Настройки товаров ---
# Курс: сколько звёзд выдаём за 1 USDT (меняйте под себя)
STARS_PER_USDT = 100

# Пакеты: key -> (количество звёзд, цена в USDT, описание)
STAR_PACKAGES = {
    "100": {"stars": 100, "price_usdt": 1.0, "title": "100 звёзд"},
    "180": {"stars": 180, "price_usdt": 1.8, "title": "180 звёзд"},
    "500": {"stars": 500, "price_usdt": 5.0, "title": "500 звёзд"},
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
                text=f"⭐ {pkg['stars']} звёзд — {pkg['price_usdt']} USDT",
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


# --- Купить звёзды: список пакетов ---
@dp.callback_query(F.data == "buy_stars")
async def buy_stars_handler(callback: CallbackQuery) -> None:
    await callback.answer()
    text = (
        "⭐ <b>Купить звёзды</b>\n\n"
        "Выбери подходящий пакет 👇\n\n"
        "💡 Оплата принимается в криптовалюте (USDT, TON и др.)."
    )
    await callback.message.edit_text(text, reply_markup=get_stars_menu())


# --- Выбор пакета: создание счёта в CryptoBot ---
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

    user_id = callback.from_user.id

    try:
        # Создаём счёт в CryptoBot
        invoice = await crypto.create_invoice(
            asset="USDT",
            amount=pkg["price_usdt"],
            description=f"Покупка {pkg['title']}",
            payload=f"user_{user_id}_pkg_{key}",
            paid_btn_name="callback",
            paid_btn_url=WEBHOOK_HOST,
        )
    except Exception as e:
        logging.error(f"Ошибка создания счёта: {e}")
        await callback.message.edit_text(
            "❌ Не удалось создать счёт. Попробуйте позже.",
            reply_markup=get_back_to_stars_kb(),
        )
        return

    text = (
        f"⭐ <b>Пакет: {pkg['stars']} звёзд</b>\n\n"
        f"💰 Стоимость: <b>{pkg['price_usdt']} USDT</b>\n\n"
        f"Нажми на кнопку ниже, чтобы перейти к оплате 👇\n\n"
        f"После оплаты звёзды будут автоматически начислены на твой счёт."
    )

    pay_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"💳 Оплатить {pkg['price_usdt']} USDT", url=invoice.bot_invoice_url)],
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


# --- Обработчик оплаты от CryptoBot ---
@crypto.pay_handler()
async def invoice_paid_handler(update: CryptoUpdate, app=None) -> None:
    """Вызывается, когда счёт оплачен."""
    logging.info(f"Получено обновление от CryptoPay: {update}")
    payload = update.payload or ""

    if update.status == "paid":
        # Парсим payload: user_123_pkg_100
        try:
            parts = payload.split("_")
            user_id = int(parts[1])
            pkg_key = parts[3]
            stars_to_add = STAR_PACKAGES.get(pkg_key, {}).get("stars", 0)

            # TODO: здесь нужно начислить звёзды в вашей БД
            logging.info(f"Пользователь {user_id} оплатил пакет {pkg_key}. Начислено {stars_to_add} звёзд.")

            # Уведомляем пользователя
            await bot.send_message(
                user_id,
                f"✅ Оплата получена!\n\n"
                f"⭐ Вам начислено <b>{stars_to_add} звёзд</b>.\n"
                f"Спасибо за покупку! 🙌"
            )
        except Exception as e:
            logging.error(f"Ошибка обработки payload '{payload}': {e}")


# --- Настройка Webhook ---
async def on_startup(bot: Bot):
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook установлен на {WEBHOOK_URL}")


async def on_shutdown(bot: Bot):
    await bot.delete_webhook()
    await crypto.close()
    logging.warning("Завершение работы...")


# --- Создание Aiohttp приложения ---
def build_app() -> web.Application:
    app = web.Application()

    # 1. Health-check с запретом кэширования
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

    # 2. Маршрут для вебхуков от CryptoBot
    app.router.add_post(CRYPTO_WEBHOOK_PATH, crypto.get_updates)

    # 3. Обработчики aiogram
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

import asyncio
import logging
import os
import traceback
import hashlib
import hmac
from aiohttp import web, ClientSession
from aiogram import Bot, Dispatcher, html, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
)
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

print(">>> 1. Все импорты загружены", flush=True)

# --- Конфигурация ---
TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_HOST = os.getenv("RENDER_EXTERNAL_URL")
PAYPALYCH_SHOP_ID = os.getenv("PAYPALYCH_SHOP_ID")
PAYPALYCH_TOKEN = os.getenv("PAYPALYCH_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "fgopf7879")

print(f">>> 2. Переменные прочитаны. BOT_TOKEN={bool(TOKEN)}, "
      f"WEBHOOK_HOST={bool(WEBHOOK_HOST)}, "
      f"PAYPALYCH_SHOP_ID={bool(PAYPALYCH_SHOP_ID)}, "
      f"PAYPALYCH_TOKEN={bool(PAYPALYCH_TOKEN)}", flush=True)

if not TOKEN:
    raise ValueError("Не задана переменная окружения BOT_TOKEN!")
if not WEBHOOK_HOST:
    raise ValueError("Не задана переменная окружения RENDER_EXTERNAL_URL!")
if not PAYPALYCH_SHOP_ID:
    raise ValueError("Не задана переменная окружения PAYPALYCH_SHOP_ID!")
if not PAYPALYCH_TOKEN:
    raise ValueError("Не задана переменная окружения PAYPALYCH_TOKEN!")

WEBHOOK_PATH = f"/webhook/{TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
PAYPALYCH_WEBHOOK_PATH = f"/paypalych/{WEBHOOK_SECRET}"

# --- Инициализация ---
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

print(">>> 3. Bot и Dispatcher созданы", flush=True)

# --- Настройки товаров ---
# Цены в рублях (RUB)
STAR_PACKAGES = {
    "100": {"stars": 100, "price_rub": 170, "title": "100 звёзд"},
    "150": {"stars": 150, "price_rub": 240, "title": "150 звёзд"},
    "200": {"stars": 200, "price_rub": 340, "title": "200 звёзд"},
    "300": {"stars": 300, "price_rub": 500, "title": "300 звёзд"},
    "400": {"stars": 400, "price_rub": 650, "title": "400 звёзд"},
    "500": {"stars": 500, "price_rub": 815, "title": "500 звёзд"},
}

# --- Клавиатуры ---
def get_reply_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⭐ Купить Звезды")],
            [
                KeyboardButton(text="🎁 Telegram Премиум"),
                KeyboardButton(text="💳 Пополнить Steam"),
            ],
            [KeyboardButton(text="🤝 Партнерская Программа")],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Выберите действие 👇",
    )


def get_stars_menu() -> InlineKeyboardMarkup:
    buttons = []
    for key, pkg in STAR_PACKAGES.items():
        buttons.append([
            InlineKeyboardButton(
                text=f"⭐ {pkg['stars']} звёзд — {pkg['price_rub']} ₽",
                callback_data=f"buy_pkg_{key}",
            )
        ])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_back_to_stars_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ К выбору пакета", callback_data="open_stars")],
            [InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_menu")],
        ]
    )


# --- /start ---
@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    user_name = html.bold(message.from_user.full_name) if message.from_user else "друг"
    await message.answer(
        f"Привет, {user_name}! 👋\n\n"
        f"Я бот-магазин. Выбери, что тебя интересует 👇",
        reply_markup=get_reply_menu(),
    )


@dp.message(Command("menu"))
async def menu_handler(message: Message) -> None:
    await message.answer("Главное меню 👇", reply_markup=get_reply_menu())


# --- Обработчики reply-кнопок ---
@dp.message(F.text == "⭐ Купить Звезды")
async def menu_buy_stars(message: Message) -> None:
    await message.answer(
        "⭐ <b>Купить звёзды</b>\n\n"
        "Выбери подходящий пакет 👇\n\n"
        "💡 Оплата принимается банковскими картами и СБП.",
        reply_markup=get_stars_menu(),
    )


@dp.message(F.text == "🎁 Telegram Премиум")
async def menu_premium(message: Message) -> None:
    await message.answer(
        "🎁 <b>Telegram Премиум</b>\n\n"
        "Раздел в разработке. Скоро здесь можно будет купить Telegram Premium."
    )


@dp.message(F.text == "💳 Пополнить Steam")
async def menu_steam(message: Message) -> None:
    await message.answer(
        "💳 <b>Пополнение Steam</b>\n\n"
        "Раздел в разработке. Скоро здесь можно будет пополнить баланс Steam."
    )


@dp.message(F.text == "🤝 Партнерская Программа")
async def menu_referral(message: Message) -> None:
    user_id = message.from_user.id
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
    await message.answer(
        "🤝 <b>Партнёрская программа</b>\n\n"
        "Приглашай друзей и получай бонусы!\n\n"
        f"🔗 Твоя ссылка:\n<code>{ref_link}</code>\n\n"
        "За каждого приглашённого друга — <b>10 звёзд</b> на твой счёт. 🌟"
    )


# --- Inline-обработчики ---
@dp.callback_query(F.data == "open_stars")
async def open_stars_handler(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.edit_text(
        "⭐ <b>Купить звёзды</b>\n\n"
        "Выбери подходящий пакет 👇",
        reply_markup=get_stars_menu(),
    )


@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu_handler(callback: CallbackQuery) -> None:
    await callback.answer()
    user_name = html.bold(callback.from_user.full_name) if callback.from_user else "друг"
    await callback.message.edit_text(
        f"Привет, {user_name}! 👋\n\n"
        f"Используй кнопки меню внизу экрана 👇",
    )


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
        invoice_url = await create_paypalych_invoice(user_id, pkg, key)
    except Exception as e:
        logging.error(f"Ошибка создания счёта PayPalych: {e}")
        await callback.message.edit_text(
            "❌ Не удалось создать счёт. Попробуйте позже.",
            reply_markup=get_back_to_stars_kb(),
        )
        return

    text = (
        f"⭐ <b>Пакет: {pkg['stars']} звёзд</b>\n\n"
        f"💰 Стоимость: <b>{pkg['price_rub']} ₽</b>\n\n"
        f"Нажми на кнопку ниже, чтобы перейти к оплате 👇\n\n"
        f"После оплаты звёзды будут автоматически начислены на твой счёт."
    )

    pay_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"💳 Оплатить {pkg['price_rub']} ₽", url=invoice_url)],
            [InlineKeyboardButton(text="⬅️ К выбору пакета", callback_data="open_stars")],
            [InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_menu")],
        ]
    )

    await callback.message.edit_text(text, reply_markup=pay_kb)


# --- Функция создания счёта в PayPalych ---
async def create_paypalych_invoice(user_id: int, pkg: dict, key: str) -> str:
    """
    Создаёт счёт в PayPalych и возвращает ссылку на оплату.
    ВАЖНО: Уточните точные параметры и URL в личном кабинете PayPalych.
    """
    api_url = "https://api.paypalych.com/v1/create"  # Проверьте URL в ЛК

    headers = {
        "Authorization": f"Bearer {PAYPALYCH_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "shop_id": PAYPALYCH_SHOP_ID,
        "amount": pkg["price_rub"],
        "currency": "RUB",
        "order_id": f"user_{user_id}_pkg_{key}",
        "description": f"Покупка {pkg['title']}",
        "result_url": f"{WEBHOOK_HOST}{PAYPALYCH_WEBHOOK_PATH}",
        "success_url": WEBHOOK_HOST,
        "fail_url": WEBHOOK_HOST,
    }

    async with ClientSession() as session:
        async with session.post(api_url, json=payload, headers=headers) as resp:
            data = await resp.json()
            logging.info(f"Ответ от PayPalych: {data}")

            if resp.status != 200 or not data.get("success"):
                raise Exception(f"PayPalych error: {data}")

            # Проверьте поле с ссылкой на оплату (может быть 'url', 'payment_url', 'redirect_url')
            return data.get("url") or data.get("payment_url") or data.get("redirect_url")


# --- Обработка вебхука от PayPalych ---
async def handle_paypalych_webhook(request: web.Request) -> web.Response:
    """
    Принимает POST-запросы от PayPalych об успешной оплате.
    ВАЖНО: Проверьте способ подписи/верификации в личном кабинете PayPalych.
    """
    try:
        data = await request.json()
    except Exception as e:
        logging.error(f"Не удалось прочитать JSON от PayPalych: {e}")
        return web.Response(status=400, text="Bad Request")

    logging.info(f"Получен вебхук от PayPalych: {data}")

    # Примерная проверка статуса. Уточните в документации PayPalych.
    status = data.get("status")
    if status not in ("success", "paid", "completed"):
        return web.Response(text="OK")

    order_id = data.get("order_id", "")
    try:
        parts = order_id.split("_")
        user_id = int(parts[1])
        pkg_key = parts[3]
        stars_to_add = STAR_PACKAGES.get(pkg_key, {}).get("stars", 0)

        # TODO: начислить звёзды в БД
        logging.info(f"Пользователь {user_id} оплатил пакет {pkg_key}. Начислено {stars_to_add} звёзд.")

        await bot.send_message(
            user_id,
            f"✅ Оплата получена!\n\n"
            f"⭐ Вам начислено <b>{stars_to_add} звёзд</b>.\n"
            f"Спасибо за покупку! 🙌"
        )
    except Exception as e:
        logging.error(f"Ошибка обработки order_id '{order_id}': {e}")

    return web.Response(text="OK")


# --- Эхо-хэндлер ---
@dp.message()
async def echo_handler(message: Message) -> None:
    if message.text:
        await message.answer(message.text)
    else:
        await message.answer("Я понимаю только текст :)")


# --- Webhook startup / shutdown ---
async def on_startup(bot: Bot):
    print(">>> 4. on_startup запущен", flush=True)
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook установлен на {WEBHOOK_URL}")
    print(">>> 5. on_startup завершён", flush=True)


async def on_shutdown(bot: Bot):
    await bot.delete_webhook()
    logging.warning("Завершение работы...")


# --- Создание Aiohttp приложения ---
def build_app() -> web.Application:
    print(">>> 6. build_app вызван", flush=True)
    app = web.Application()

    async def health_check(request):
        return web.Response(text="OK", headers={"Cache-Control": "no-store"})

    app.router.add_route('GET', '/health', health_check)
    app.router.add_route('HEAD', '/health', health_check)
    app.router.add_post(PAYPALYCH_WEBHOOK_PATH, handle_paypalych_webhook)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    print(">>> 7. build_app завершён", flush=True)
    return app


# --- Супервизор ---
def run_forever():
    import time
    port = int(os.getenv("PORT", 10000))
    print(f">>> 8. run_forever стартовал. Порт: {port}", flush=True)
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
    print(">>> 0. Старт bot.py", flush=True)
    run_forever()

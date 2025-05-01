from aiogram import Bot, Dispatcher, F
from aiogram.client.session import aiohttp
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Message, InlineKeyboardButton, KeyboardButton, InlineKeyboardMarkup, PreCheckoutQuery, LabeledPrice, ReplyKeyboardMarkup
from aiogram.enums import ParseMode, ContentType
from aiogram.utils.keyboard import InlineKeyboardBuilder
# from config import BOT_TOKEN
from catalog import catalog
from loguru import logger
import asyncio
from database import init_db, async_session
from models import User
from sqlalchemy import select
from aiohttp import web
import bitrix24
from pyngrok import ngrok
bot = Bot(token='8159987482:AAE_9BNu9Wa7N-KoYtK2fZroQySDc5a-JRY')
dp = Dispatcher()

@dp.message(F.text.lower() == "/start")
async def start(message: Message):
        user = message.from_user
        phone = user.phone_number if hasattr(user, "phone_number") else "неизвестен"

        async with async_session() as session:
            stmt = select(User).where(User.tg_id == user.id)
            result = await session.execute(stmt)
            existing_user = result.scalar_one_or_none()
            if existing_user:
                await message.answer(f"🔹 С возвращением, {user.full_name}!")
            else:
                new_user = User(
                    tg_id=user.id,
                    phone=phone,
                    username=user.username,
                    full_name=user.full_name
                )
                session.add(new_user)

                await bitrix24.add_contact_to_bitrix(message.from_user)

                await session.commit()
                await message.answer(f"✅ Привет, {user.full_name}!\nТы зарегистрирован.")

            kb = InlineKeyboardBuilder()
            for product_id, item in catalog.items():
                button = InlineKeyboardButton(
                    text=f"{item['title']} — {item['price']}⭐",
                    callback_data=f"{product_id}",
                    pay=True
                )
                kb.row(button)
        await message.answer("Добро пожаловать в наш магазин! Выберите товар:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("product_"))
async def process_buy(callback_query):
    product_id = callback_query.data
    item = catalog.get(product_id)

    if not item:
        logger.warning(f"Товар {product_id} не найден")
        await callback_query.answer("Товар не найден.")
        return

    logger.info(f"Пользователь {callback_query.from_user.id} выбирает {item['title']}")

    try:
        await bot.send_invoice(
            chat_id=callback_query.from_user.id,
            title=item["title"],
            description=item["description"],
            payload="test_payload",
            provider_token="",  # Обязательно укажите ваш токен провайдера
            currency="XTR",  # Валюта Stars
            prices=[
                LabeledPrice(
                    label=item["title"],
                    amount= 1  # Конвертируем Stars в минимальные единицы
                )
            ],
            need_name=True,
            need_email=False,
            is_flexible=False,

        )
        await callback_query.answer()
    except TelegramAPIError as e:
        logger.error(f"Ошибка при отправке счёта: {e}")
        await callback_query.answer("Ошибка при создании счёта.")


@dp.pre_checkout_query()
async def pre_checkout_query(pre_checkout_q: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)


@dp.message(F.successful_payment)
async def successful_payment(message: Message):
    await message.answer("✅ Оплата прошла успешно! Спасибо за покупку.")




async def main():
    app = web.Application()
    app.router.add_post('/webhook/bitrix', bitrix24.bitrix_webhook_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8080)
    await site.start()

    print("Webhook сервер запущен на http://localhost:8080")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())

from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, PreCheckoutQuery, LabeledPrice
from aiogram.enums import ParseMode, ContentType
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import BOT_TOKEN, PROVIDER_TOKEN
from catalog import catalog
from loguru import logger
import asyncio

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(F.text.lower() == "/start")
async def start(message: Message):
    kb = InlineKeyboardBuilder()
    for product_id, item in catalog.items():
        kb.add(
            InlineKeyboardButton(
                text=f"{item['title']} — {item['price']}⭐",
                callback_data=f"{product_id}",
                pay=True
            )
        )
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
            payload=f"order_{product_id}_item_{item['price']}",
            provider_token=PROVIDER_TOKEN,  # Обязательно укажите ваш токен провайдера
            currency="XTR",  # Валюта Stars
            prices=[
                LabeledPrice(
                    label=item["title"],
                    amount=100  # Конвертируем Stars в минимальные единицы
                )
            ],
            need_name=True,
            need_email=False,
            is_flexible=False,
            max_tip_amount=100000,  # Максимальная сумма чаевых (10 Stars)
            suggested_tip_amounts=[10000, 20000, 30000, 40000]  # Варианты чаевых (1-4 Stars)
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


if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))

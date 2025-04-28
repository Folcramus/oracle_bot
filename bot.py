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
bot = Bot(token='')
dp = Dispatcher()
import ssl
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE
BITRIX_WEBHOOK_BASE = 'https://b24-mwcobf.bitrix24.ru/rest/1/7ili29rp79a2sq66/'
@dp.message(F.text.lower() == "/start")
async def start(message: Message):
        user = message.from_user
        #phone = user.phone_number if hasattr(user, "phone_number") else "неизвестен"  # ← этот атрибут обычно отсутствует
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


# Получить название стадии сделки по STAGE_ID
async def get_stage_name(stage_id):
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"https://b24-mwcobf.bitrix24.ru/rest/1/yv1u9k02uz1cp5xe/crm.status.list.json",
            params={"filter[ENTITY_ID]": "DEAL_STAGE"},
            ssl=ssl_context
        ) as resp:
            status_response = await resp.json()
            for status in status_response.get("result", []):
                if status["STATUS_ID"] == stage_id:
                    return status["NAME"]
    return f"Неизвестная стадия ({stage_id})"

# Основной обработчик вебхуков Bitrix
async def bitrix_webhook_handler(request):
    try:
        data = await request.post()
        event = data.get('event')

        if event == 'ONCRMDEALUPDATE':
            deal_id = data.get('data[FIELDS][ID]')

            # Получаем полные данные о сделке
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{BITRIX_WEBHOOK_BASE}/crm.deal.get.json",
                    params={"id": deal_id},
                    ssl=ssl_context
                ) as resp:
                    deal_response = await resp.json()

            deal_info = deal_response.get("result")
            if not deal_info:
                await bot.send_message(482460555, f"❌ Не удалось получить сделку #{deal_id}")
                return web.json_response({'status': 'no deal'})

            # Получаем название стадии
            stage_id = deal_info.get("STAGE_ID")
            stage_name = await get_stage_name(stage_id)

            # Формируем сообщение
            message_lines = [f"🧾 Сделка #{deal_id} обновлена:"]
            message_lines.append(f"• Стадия: {stage_name} ({stage_id})")

            for key, value in deal_info.items():
                if key != "STAGE_ID":
                    message_lines.append(f"• {key}: {value}")

            message_text = "\n".join(message_lines)

            # Отправляем в Telegram
            await bot.send_message(482460555, message_text)

        return web.json_response({'status': 'ok'})

    except Exception as e:
        print("❌ Ошибка:", str(e))
        return web.json_response({'status': 'error', 'details': str(e)}, status=500)

async def main():
    app = web.Application()
    app.router.add_post('/webhook/bitrix', bitrix_webhook_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8080)
    await site.start()

    print("Webhook сервер запущен на http://0.0.0.0:8080")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())

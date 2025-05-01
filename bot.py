from aiogram import Bot, Dispatcher, F
from aiogram.client.session import aiohttp
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Message, InlineKeyboardButton, KeyboardButton, InlineKeyboardMarkup, PreCheckoutQuery, \
    LabeledPrice, ReplyKeyboardMarkup, CallbackQuery
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
from aiogram.fsm.context import FSMContext
from aiogram.types import LabeledPrice
import uuid  # Для генерации уникального payload

from pyngrok import ngrok

from state import RegisterState, router, CartState, OrderState
import os
from dotenv import load_dotenv

load_dotenv()
bot = Bot(token=os.getenv("TOKEN"))
dp = Dispatcher()


#Старт и регистрация пользователя
@dp.message(F.text.lower() == "/start")
async def start(message: Message, state: FSMContext):
    user = message.from_user

    async with async_session() as session:
        stmt = select(User).where(User.tg_id == user.id)
        result = await session.execute(stmt)
        existing_user = result.scalar_one_or_none()
        if existing_user:
            await message.answer(f"🔹 С возвращением, {user.full_name}!")
            await show_catalog(message, state)
        else:
            # Запрос номера телефона
            kb = ReplyKeyboardMarkup(
                keyboard=[[
                    KeyboardButton(text="📱 Отправить номер", request_contact=True)
                ]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            await message.answer("Пожалуйста, отправь свой номер телефона:", reply_markup=kb)
            await state.set_state(RegisterState.waiting_for_phone)

@dp.message(RegisterState.waiting_for_phone, F.contact)
async def handle_phone(message: Message, state: FSMContext):
    contact = message.contact
    user = message.from_user

    async with async_session() as session:
        new_user = User(
            tg_id=user.id,
            phone=contact.phone_number,
            username=user.username,
            full_name=user.full_name
        )
        session.add(new_user)
        print(user)
        await bitrix24.add_contact_to_bitrix(user, contact)
        await session.commit()

    await message.answer(f"✅ Привет, {user.full_name}!\nТы зарегистрирован.")
    await show_catalog(message)
    await state.clear()

#Показ каталога
async def show_catalog(message: Message, state: FSMContext):
    await state.set_state(CartState.managing_cart)

    kb = InlineKeyboardBuilder()
    for product_id, item in catalog.items():
        kb.row(
            InlineKeyboardButton(
                text=f"➕ {item['title']} — {item['price']}⭐",
                callback_data=f"add_{product_id}"
            )
        )
    kb.row(
        InlineKeyboardButton(text="🛒 Перейти в корзину", callback_data="go_to_cart")
    )
    await message.answer("Выберите товар для добавления в корзину:", reply_markup=kb.as_markup())


#Добавление товара в корзину
@dp.callback_query(F.data.startswith("add_"))
async def add_to_cart(callback_query: CallbackQuery, state: FSMContext):
    product_id = callback_query.data.split("_", 1)[1]
    cart = (await state.get_data()).get("cart", {})

    cart[product_id] = cart.get(product_id, 0) + 1
    await state.update_data(cart=cart)

    item = catalog[product_id]
    await callback_query.answer(f"{item['title']} — добавлен в корзину!")


#Обратно в корзину
@dp.callback_query(F.data == "go_to_cart")
async def go_to_cart(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cart = data.get("cart", {})

    if not cart:
        await callback_query.answer("Корзина пуста.", show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    text_lines = ["🛒 *Ваша корзина:*"]
    total = 0
    print("test")
    for product_id, quantity in cart.items():
        item = catalog.get(product_id)
        if not item:
            continue
        price = item['price'] * quantity
        total += price
        text_lines.append(f"{item['title']} x{quantity} — {price}⭐")

        kb.row(
            InlineKeyboardButton(text="➖", callback_data=f"decrease_{product_id}"),
            InlineKeyboardButton(text="➕", callback_data=f"increase_{product_id}"),
            InlineKeyboardButton(text="❌", callback_data=f"remove_{product_id}")

        )

    text_lines.append(f"\n💰 *Итоговая сумма:* {total}⭐")
    kb.row(InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data="confirm_payment"))
    kb.row(InlineKeyboardButton(text="🔙 Выйти из корзины", callback_data="exit_cart"))

    await callback_query.message.edit_text("\n".join(text_lines), reply_markup=kb.as_markup(), parse_mode="Markdown")




#Добавление и удаление товара
@dp.callback_query(F.data.startswith("increase_"))
async def increase_quantity(callback: CallbackQuery, state: FSMContext):
    product_id = callback.data.split("_", 1)[1]
    data = await state.get_data()
    cart = data.get("cart", {})
    cart[product_id] = cart.get(product_id, 0) + 1
    await state.update_data(cart=cart)
    await go_to_cart(callback, state)

@dp.callback_query(F.data.startswith("decrease_"))
async def decrease_quantity(callback: CallbackQuery, state: FSMContext):
    product_id = callback.data.split("_", 1)[1]
    data = await state.get_data()
    cart = data.get("cart", {})
    if product_id in cart:
        if cart[product_id] > 1:
            cart[product_id] -= 1
        else:
            del cart[product_id]
    await state.update_data(cart=cart)
    await go_to_cart(callback, state)

@dp.callback_query(F.data.startswith("remove_"))
async def remove_item(callback: CallbackQuery, state: FSMContext):
    product_id = callback.data.split("_", 1)[1]
    data = await state.get_data()
    cart = data.get("cart", {})
    cart.pop(product_id, None)
    await state.update_data(cart=cart)
    await go_to_cart(callback, state)



#Подтверждение оплаты
@dp.callback_query(F.data == "confirm_payment")
async def confirm_payment(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cart = data.get("cart", {})

    if not cart:
        await callback_query.answer("🛒 Корзина пуста.", show_alert=True)
        return

    total = 0
    summary_lines = []
    for product_id, quantity in cart.items():
        item = catalog.get(product_id)
        if not item:
            continue

        line_total = item["price"] * quantity
        total += line_total
        summary_lines.append(f"{item['title']} x{quantity} — {line_total}⭐")

    summary_text = "\n".join(summary_lines)
    summary_text += f"\n\n💰 *Итого: {total}⭐*\n\nПодтвердите оплату."

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data="simulate_payment")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_payment")]
    ])

    await callback_query.message.answer(summary_text, reply_markup=keyboard, parse_mode="Markdown")
    await callback_query.answer()

#Симуляция оплаты
@dp.callback_query(F.data == "simulate_payment")
async def simulate_payment(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.message.answer("📦 Введите адрес доставки:")
    await state.set_state(OrderState.waiting_for_address)
    await callback_query.answer()

@dp.message(OrderState.waiting_for_address)
async def process_address(message: Message, state: FSMContext):
    address = message.text.strip()
    data = await state.get_data()

    # (можно здесь сохранить адрес в базу, если нужно)
    await message.answer(
        f"✅ *Оплата прошла успешно!*\n"
        f"Ваш заказ будет доставлен по адресу:\n📍 {address}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Вернуться в магазин", callback_data="back_to_shop")]
        ])
    )

    # Очистим корзину и сбросим состояние
    await state.clear()
@dp.callback_query(F.data == "cancel_payment")
async def cancel_payment(callback_query: CallbackQuery):
    await callback_query.message.answer("❌ Оплата отменена. Вы можете вернуться к выбору товаров.")
    await callback_query.answer()



# @dp.pre_checkout_query()
# async def pre_checkout_query(pre_checkout_q: PreCheckoutQuery):
#     await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)
#
# @dp.message(F.successful_payment)
# async def successful_payment(message: Message, state: FSMContext):
#     await message.answer("✅ Оплата прошла успешно! Спасибо за покупку.")
#     await state.clear()  # Очищаем корзину


#Обратно в магазин
@dp.callback_query(F.data == "back_to_shop")
async def back_to_shop(callback_query: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"{item['title']} — {item['price']}⭐",
                callback_data=f"product_{product_id}"
            )
        ]
        for product_id, item in catalog.items()
    ])
    await callback_query.message.answer("🛍️ Выберите товар из каталога:", reply_markup=kb)
    await callback_query.answer()

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

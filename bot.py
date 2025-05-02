# Импорт библиотек и зависимостей
from aiogram import Bot, Dispatcher, F  # Основные классы для работы с Telegram API
from aiogram.types import Message, InlineKeyboardButton, KeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder  # Удобный билдер клавиатур
from loguru import logger  # Логирование
import asyncio  # Асинхронность
from database import init_db, async_session  # Инициализация базы данных и сессия
from models import User  # Модель пользователя
from sqlalchemy import select  # Запросы SQLAlchemy
from aiohttp import web  # Веб-сервер для обработки вебхуков
import bitrix24  # Интеграция с Bitrix24 (API)
from aiogram.fsm.context import FSMContext  # Контекст состояний FSM (машина состояний)
import os
from dotenv import load_dotenv  # Загрузка переменных окружения
from catalog import catalog  # Каталог товаров
from state import OrderState, RegisterState  # Определенные состояния FSM

# Загрузка .env переменных и инициализация бота и диспетчера
load_dotenv()
bot = Bot(token=os.getenv("TOKEN"))
dp = Dispatcher()


# Главное меню с кнопкой корзины
async def show_main_menu(message: Message, cart_items_count: int = 0):
    kb = InlineKeyboardBuilder()

    # Кнопки категорий
    for category_id, category_data in catalog.items():
        kb.add(InlineKeyboardButton(
            text=category_data["name"],
            callback_data=f"category_{category_id}"
        ))

    # Кнопка корзины с количеством товаров
    kb.row(InlineKeyboardButton(
        text=f"🛒 Корзина ({cart_items_count})",
        callback_data="go_to_cart"
    ))
    kb.row(InlineKeyboardButton(
        text=f"История заказов ",
        callback_data="go_to_orders_history"
    ))
    kb.adjust(1)
    await message.answer(
        "🏠 Главное меню. Выберите категорию:",
        reply_markup=kb.as_markup()
    )


# Старт и регистрация пользователя
@dp.message(F.text.lower() == "/start")
async def start(message: Message, state: FSMContext):
    user = message.from_user

    async with async_session() as session:
        stmt = select(User).where(User.tg_id == user.id)
        result = await session.execute(stmt)
        existing_user = result.scalar_one_or_none()
        if existing_user:
            await message.answer(f"🔹 С возвращением, {user.full_name}!")
            # Показываем главное меню с количеством товаров в корзине
            cart = (await state.get_data()).get("cart", {})
            await show_main_menu(message, len(cart))
        else:
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
    await show_main_menu(message)
    await state.clear()


# Показ товаров в категории
@dp.callback_query(F.data.startswith("category_"))
async def show_category_items(callback: CallbackQuery):
    category_id = callback.data.split("_")[1]
    category = catalog.get(category_id)

    if not category:
        await callback.answer("Категория не найдена")
        return

    kb = InlineKeyboardBuilder()
    for product_id, product in category["items"].items():
        kb.add(InlineKeyboardButton(
            text=f"{product['title']} — {product['price']}⭐",
            callback_data=f"product_{category_id}_{product_id}"
        ))

    # Кнопки навигации
    kb.row(InlineKeyboardButton(
        text="🔙 Назад",
        callback_data="back_to_main_menu"
    ))
    kb.row(InlineKeyboardButton(
        text="🛒 Корзина",
        callback_data="go_to_cart"
    ))

    await callback.message.edit_text(
        f"Товары в категории {category['name']}:",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


# Просмотр информации о товаре
@dp.callback_query(F.data.startswith("product_"))
async def show_product(callback: CallbackQuery):
    parts = callback.data.split("_")
    if len(parts) != 3:
        await callback.answer("Ошибка запроса")
        return

    category_id = parts[1]
    product_id = parts[2]

    category = catalog.get(category_id)
    if not category:
        await callback.answer("Категория не найдена")
        return

    product = category["items"].get(product_id)
    if not product:
        await callback.answer("Товар не найден")
        return

    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(
        text="➕ Добавить в корзину",
        callback_data=f"add_{category_id}_{product_id}"
    ))
    kb.row(InlineKeyboardButton(
        text="🔙 Назад к товарам",
        callback_data=f"category_{category_id}"
    ))
    kb.row(InlineKeyboardButton(
        text="🛒 Корзина",
        callback_data="go_to_cart"
    ))

    await callback.message.edit_text(
        f"<b>{product['title']}</b>\n\n"
        f"<i>{product['description']}</i>\n\n"
        f"Цена: {product['price']}⭐",
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )
    await callback.answer()


# Добавление товара в корзину
@dp.callback_query(F.data.startswith("add_"))
async def add_to_cart(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    if len(parts) != 3:
        await callback.answer("Ошибка запроса")
        return

    category_id = parts[1]
    product_id = parts[2]

    category = catalog.get(category_id)
    if not category:
        await callback.answer("Категория не найдена")
        return

    product = category["items"].get(product_id)
    if not product:
        await callback.answer("Товар не найден")
        return

    cart = (await state.get_data()).get("cart", {})
    cart_key = f"{category_id}_{product_id}"
    cart[cart_key] = cart.get(cart_key, 0) + 1
    await state.update_data(cart=cart)

    # Обновляем счетчик в главном меню
    await callback.answer(f"{product['title']} добавлен в корзину!")



# Возврат в главное меню
@dp.callback_query(F.data == "back_to_main_menu")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    cart = (await state.get_data()).get("cart", {})
    await show_main_menu(callback.message, len(cart))
    await callback.answer()


# Переход в корзину
@dp.callback_query(F.data == "go_to_cart")
async def go_to_cart(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cart = data.get("cart", {})

    if not cart:
        await callback.answer("Корзина пуста.", show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    text_lines = ["🛒 *Ваша корзина:*"]
    total = 0

    for product_key, quantity in cart.items():
        category_id, product_id = product_key.split("_")
        item = catalog.get(category_id, {}).get("items", {}).get(product_id)
        if not item:
            continue

        price = item['price'] * quantity
        total += price
        text_lines.append(f"{item['title']} x{quantity} — {price}⭐")

        kb.row(
            InlineKeyboardButton(text="➖", callback_data=f"decrease_{product_key}"),
            InlineKeyboardButton(text="➕", callback_data=f"increase_{product_key}"),
            InlineKeyboardButton(text="❌", callback_data=f"remove_{product_key}")
        )

    text_lines.append(f"\n💰 *Итоговая сумма:* {total}⭐")
    kb.row(InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data="confirm_payment"))
    kb.row(InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main_menu"))

    await callback.message.edit_text("\n".join(text_lines), reply_markup=kb.as_markup(), parse_mode="Markdown")
    await callback.answer()


# Управление количеством товаров в корзине
@dp.callback_query(F.data.startswith("increase_"))
async def increase_quantity(callback: CallbackQuery, state: FSMContext):
    product_key = callback.data.split("_", 1)[1]
    data = await state.get_data()
    cart = data.get("cart", {})
    cart[product_key] = cart.get(product_key, 0) + 1
    await state.update_data(cart=cart)
    await go_to_cart(callback, state)


@dp.callback_query(F.data.startswith("decrease_"))
async def decrease_quantity(callback: CallbackQuery, state: FSMContext):
    product_key = callback.data.split("_", 1)[1]
    data = await state.get_data()
    cart = data.get("cart", {})
    if product_key in cart:
        if cart[product_key] > 1:
            cart[product_key] -= 1
        else:
            del cart[product_key]
    await state.update_data(cart=cart)
    await go_to_cart(callback, state)

#Удаление из корзины
@dp.callback_query(F.data.startswith("remove_"))
async def remove_item(callback: CallbackQuery, state: FSMContext):
    product_key = callback.data.split("_", 1)[1]
    data = await state.get_data()
    cart = data.get("cart", {})
    cart.pop(product_key, None)
    await state.update_data(cart=cart)
    await go_to_cart(callback, state)


# Оформление заказа
@dp.callback_query(F.data == "confirm_payment")
async def confirm_payment(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    cart = data.get("cart", {})

    if not cart:
        await callback.answer("🛒 Корзина пуста.", show_alert=True)
        return

    total = 0
    summary_lines = []
    for product_key, quantity in cart.items():
        category_id, product_id = product_key.split("_")
        item = catalog.get(category_id, {}).get("items", {}).get(product_id)
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

    await callback.message.answer(summary_text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()


# Симуляция оплаты
@dp.callback_query(F.data == "simulate_payment")
async def simulate_payment(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("📦 Введите адрес доставки:")
    await state.set_state(OrderState.waiting_for_address)
    await callback.answer()


# Модифицируем обработчик оформления заказа
@dp.message(OrderState.waiting_for_address)
async def process_address(message: Message, state: FSMContext):
    address = message.text.strip()
    data = await state.get_data()
    cart = data.get("cart", {})

    if not cart:
        await message.answer("Корзина пуста!")
        await state.clear()
        return

    # Получаем данные пользователя из БД
    async with async_session() as session:
        stmt = select(User).where(User.tg_id == message.from_user.id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            await message.answer("Ошибка: пользователь не найден")
            await state.clear()
            return

        user_data = {
            "full_name": user.full_name,
            "phone": user.phone,
            "tg_id": message.from_user.id,

        }

    # Создаем сделку в Bitrix24
    deal_result = await bitrix24.create_bitrix_deal(user_data, cart, address)

    if deal_result:
        print(deal_result.get('deal_id'))
        await message.answer(
            f"✅ *Оплата прошла успешно!*\n"
            f"Номер вашего заказа: {deal_result.get('deal_id')}\n"
            f"Адрес доставки: {address}\n\n"
            f"С вами свяжется наш менеджер для уточнения деталей.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_main_menu")]
            ])
        )

        # Логируем успешное создание сделки
        logger.info(f"Создана сделка в Bitrix24: ID {deal_result.get} для пользователя {user.tg_id}")
    else:
        await message.answer(
            "⚠️ Заказ оформлен, но возникла ошибка при создании сделки. "
            "Наш менеджер свяжется с вами для уточнения деталей."
        )
        logger.error(f"Ошибка при создании сделки для пользователя {user.tg_id}")

    # Очищаем корзину
    await state.update_data(cart={})
    await state.clear()

#История заказов
@dp.callback_query(F.data == "go_to_orders_history")
async def go_to_orders_history(callback: CallbackQuery):
    tg_id = callback.from_user.id

    # Получаем сделки через API Bitrix24
    deals = await bitrix24.show_user_deals(str(tg_id))

    if deals:

        await callback.message.answer(deals)
    else:
        await callback.message.answer("🔹 У вас нет сделок.")


@dp.callback_query(F.data == "cancel_payment")
async def cancel_payment(callback: CallbackQuery):
    await callback.message.answer("❌ Оплата отменена. Вы можете вернуться к выбору товаров.")
    await callback.answer()


async def main():
    await init_db()
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
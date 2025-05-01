import os
from asyncio.log import logger
from typing import Optional

import requests
from aiogram.client.session import aiohttp
import ssl
from aiohttp import web
from aiogram import Bot
from dotenv import load_dotenv

from catalog import catalog  # Каталог товаров


# Загрузка переменных окружения из .env файла
load_dotenv()

# Настройка SSL-контекста (отключена проверка сертификатов — не рекомендуется для продакшн)
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Вебхуки Bitrix24
BITRIX_WEBHOOK_BASE = 'https://b24-mwcobf.bitrix24.ru/rest/1/7ili29rp79a2sq66/'
BITRIX_WEBHOOK = "https://b24-mwcobf.bitrix24.ru/rest/12/9mv0ulk31p44kbxv/"
BITRIX_PRODUCT_ADD_WEBHOOK = 'https://b24-mwcobf.bitrix24.ru/rest/1/tgo0yqf0ypvc3s8c'

# Инициализация Telegram-бота
bot = Bot(token=os.getenv("TOKEN"))




# Функция для поиска сделок по tg_id
async def find_deals_by_tg_id(tg_id: str):
    try:
        result = await call(
            'crm.deal.list',
            'https://b24-mwcobf.bitrix24.ru/rest/1/oou0i0wx1ml7kfdg',
            {'filter': {'UF_CRM_1746104614683': tg_id}, 'select': ['ID', 'TITLE', 'STAGE_ID']}
        )

        deals = result.get('result', [])
        if not deals:
            logger.info(f"Нет сделок для tg_id: {tg_id}")
            return None

        logger.info(f"Найдено {len(deals)} сделок для tg_id: {tg_id}")
        return deals

    except Exception as e:
        logger.error(f"❌ Ошибка при поиске сделок по tg_id {tg_id}: {e}")
        return None

# Обработка команды для просмотра сделок по tg_id
async def show_user_deals(tg_id: str):
    deals = await find_deals_by_tg_id(tg_id)
    if not deals:
        return "❌ У вас нет заказов в "

    message = "Ваши заказы:\n"
    for deal in deals:
        deal_id = deal['ID']
        deal_title = deal['TITLE']
        stage_id = deal['STAGE_ID']
        message += f"• Заказ #{deal_id} - {deal_title} (Стадия: {stage_id})\n"

    return message


# Поиск товара в локальном каталоге
def find_item(category_id, item_id):
    category = catalog.get(category_id)
    if category is None:
        return None
    return category["items"].get(item_id)


# Универсальная функция вызова методов Bitrix24 через API
async def call(method: str, webhookurl: str, params=None):
    url = f"{webhookurl}/{method}"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=params, ssl=ssl_context) as response:
            if response.status == 200:
                return await response.json()
            else:
                error = await response.text()
                raise Exception(f"Bitrix24 API error: {error}")


# Создание товара в Bitrix24
async def create_bitrix_product(product_data: dict) -> Optional[int]:
    title = product_data.get('title')
    price = product_data.get('price', 0)
    currency = product_data.get('currency', 'RUB')
    description = product_data.get('description', '')
    active = product_data.get('active', 'Y')

    if not title:
        logger.error("❌ Не указано название товара для создания в Bitrix24")
        return None

    product_params = {
        "NAME": title,
        "PRICE": price,
        "CURRENCY_ID": currency,
        "DESCRIPTION": description,
        "ACTIVE": active
    }

    try:
        result = await call('crm.product.add', BITRIX_PRODUCT_ADD_WEBHOOK, {"fields": product_params})
        product_id = result.get('result')
        if product_id:
            logger.info(f"✅ Товар '{title}' успешно создан в Bitrix24. ID: {product_id}")
            return product_id
        else:
            logger.warning(f"⚠️ Товар '{title}' не удалось создать. Ответ: {result}")
            return None
    except Exception as e:
        logger.error(f"❌ Ошибка при создании товара в Bitrix24: {e}")
        return None


# Добавление контакта в Bitrix24
async def add_contact_to_bitrix(user, contact):
    contact_data = {
        "fields": {
            "NAME": user.first_name,
            "LAST_NAME": user.last_name or "",
            "PHONE": [{"VALUE": str(contact.phone_number), "VALUE_TYPE": "WORK"}],
            "OPENED": "Y",
            "TYPE_ID": "CLIENT",
            "SOURCE_ID": "SELF",
            "UF_CRM_1746084153598": user.id,
            "UF_CRM_1746084215487": user.username,
        }
    }

    try:
        response = requests.post(BITRIX_WEBHOOK + "crm.contact.add.json", json=contact_data)
        result = response.json()

        if "result" in result:
            print(f"Контакт создан в Bitrix24: ID {result['result']}")
        else:
            print("❌ Ошибка при создании контакта:", result)

    except Exception as e:
        print(f"Ошибка при запросе к Bitrix24: {e}")


# Поиск товара по названию или создание, если не найден
async def find_or_create_product_by_name(product_data: str, data: dict) -> Optional[int]:
    if not product_data:
        logger.error("❌ Не указано название товара для поиска/создания")
        return None

    try:
        result = await call(
            'crm.product.list',
            'https://b24-mwcobf.bitrix24.ru/rest/1/al3jruylxn04pp75',
            {'filter': {'%NAME': product_data}, 'select': ['ID', 'NAME']}
        )

        matches = result.get('result', [])
        logger.info(f"🔍 Найдено {len(matches)} совпадений по названию '{product_data}'")

        for product in matches:
            if product_data.strip().lower() == product.get('NAME', '').strip().lower():
                return product['ID']

        if matches:
            logger.warning("⚠️ Точное совпадение не найдено, используем первое частичное.")
            return matches[0].get('ID')

        return await create_bitrix_product(data)

    except Exception as e:
        logger.error(f"❌ Ошибка при поиске/создании товара в Bitrix24: {e}")
        return None


# Получение или создание товара
async def get_or_create_bitrix_product(product_data: dict) -> Optional[int]:
    title = product_data.get("title")
    if not title:
        logger.error("❌ В product_data отсутствует поле 'title'")
        return None

    return await find_or_create_product_by_name(title, product_data)


# Получение названия стадии сделки по её ID
async def get_stage_name(stage_id):
    async with aiohttp.ClientSession() as session:
        async with session.get(
                "https://b24-mwcobf.bitrix24.ru/rest/1/yv1u9k02uz1cp5xe/crm.status.list.json",
                params={"filter[ENTITY_ID]": "DEAL_STAGE"},
                ssl=ssl_context
        ) as resp:
            status_response = await resp.json()
            for status in status_response.get("result", []):
                if status["STATUS_ID"] == stage_id:
                    return status["NAME"]
    return f"Неизвестная стадия ({stage_id})"


# Обработка входящих вебхуков от Bitrix24
async def bitrix_webhook_handler(request):
    try:
        data = await request.post()
        event = data.get('event')

        if event == 'ONCRMDEALUPDATE':
            deal_id = data.get('data[FIELDS][ID]')

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

            stage_id = deal_info.get("STAGE_ID")
            stage_name = await get_stage_name(stage_id)
            tg_id = ''
            # Формируем сообщение о сделке
            message_lines = [f"🧾 Сделка #{deal_id} обновлена:"]
            message_lines.append(f"• Стадия: {stage_name} ({stage_id})")
            for key, value in deal_info.items():
                if value == 'NEW' or value == 'WON':
                    return web.json_response({'status': '<UNK> <UNK>'})
                if key == 'UF_CRM_1746104614683':
                    tg_id = value

            message_text = "\n".join(message_lines)
            await bot.send_message(tg_id, message_text)

        return web.json_response({'status': 'ok'})

    except Exception as e:
        print("❌ Ошибка:", str(e))
        return web.json_response({'status': 'error', 'details': str(e)}, status=500)


# Создание сделки в Bitrix24 с товарами из корзины
async def create_bitrix_deal(user_data: dict, cart_items: dict, address: str):
    product_rows = []
    total = 0

    for product_key, quantity in cart_items.items():
        category_id, product_id = product_key.split("_")
        item = find_item(category_id, product_id)
        if not item:
            logger.warning(f"⛔ Товар не найден в каталоге: {product_key}")
            continue

        bitrix_product_id = await get_or_create_bitrix_product(item)
        if not bitrix_product_id:
            logger.warning(f"⚠️ Не удалось создать/получить товар в Bitrix: {item['title']}")
            continue

        item['bitrix_product_id'] = bitrix_product_id
        price = item['price']
        total += price * quantity

        product_rows.append({
            "PRODUCT_ID": bitrix_product_id,
            "PRICE": price,
            "QUANTITY": quantity,
            "CUSTOMIZED": "Y",
            "DISCOUNT_RATE": 0,
            "TAX_RATE": 0,
        })

    deal_data = {
        "TITLE": f"Заказ от {user_data.get('full_name')}",
        "UF_CRM_1746090729665": address,
        "TYPE_ID": "SALE",
        "STAGE_ID": "NEW",
        "OPPORTUNITY": total,
        "CURRENCY_ID": "RUB",
        "ASSIGNED_BY_ID": 1,
        "UF_CRM_1746104614683": user_data.get('tg_id'),
    }

    try:
        deal_result = await call('crm.deal.add', 'https://b24-mwcobf.bitrix24.ru/rest/1/d8l4vrh162o8kmmk', {"fields": deal_data})
        deal_id = deal_result.get("result")

        if not deal_id:
            logger.error("❌ Сделка не создана. Нет ID.")
            return None

        logger.info(f"✅ Сделка создана: ID {deal_id}")

        # Добавление товаров к сделке
        if product_rows:
            set_result = await call('crm.deal.productrows.set', 'https://b24-mwcobf.bitrix24.ru/rest/1/duq9ee50zjzeh680', {
                "ID": deal_id,
                "rows": product_rows
            })
            logger.info(f"📦 Товары добавлены к сделке {deal_id}: {set_result}")
        else:
            logger.warning(f"⚠️ Нет товаров для добавления к сделке {deal_id}")

        return {
            "deal_id": deal_id,
            "products": [p['PRODUCT_ID'] for p in product_rows],
            "total": total
        }

    except Exception as e:
        logger.error(f"❌ Ошибка при создании сделки или добавлении товаров: {e}")
        return None

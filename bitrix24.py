import requests
from aiogram.client.session import aiohttp
import ssl
from aiohttp import web
from aiogram import Bot, Dispatcher, F

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE
BITRIX_WEBHOOK_BASE = 'https://b24-mwcobf.bitrix24.ru/rest/1/7ili29rp79a2sq66/'
BITRIX_WEBHOOK = "https://b24-mwcobf.bitrix24.ru/rest/12/9mv0ulk31p44kbxv/"  # Вебхук из Bitrix24
bot = Bot(token='8159987482:AAE_9BNu9Wa7N-KoYtK2fZroQySDc5a-JRY')


async def add_contact_to_bitrix(user):
    contact_data = {
        "fields": {
            "NAME": user.first_name,
            "LAST_NAME": user.last_name or "",
            "SECOND_NAME": "",
            "OPENED": "Y",
            "TYPE_ID": "CLIENT",  # Тип контакта
            "SOURCE_ID": "SELF",  # Источник
            "COMMENTS": f"Telegram username: @{user.username}\nTelegram ID: {user.id}",
            "PHONE": [
                {"VALUE": "неизвестен", "VALUE_TYPE": "WORK"}
            ]
        }
    }

    try:
        response = requests.post(BITRIX_WEBHOOK + "crm.contact.add.json", json=contact_data)
        result = response.json()

        if "result" in result:
            print(f"Контакт создан в Bitrix24: ID {result['result']}")
        else:
            print("❌ Ошибка при создании контакта:")
            print(result)

    except Exception as e:
        print(f"Ошибка при запросе к Bitrix24: {e}")


async def add_deal_to_bitrix(user, deal_data):
    pass


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


#  обработчик исходещего вебхука Б24
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

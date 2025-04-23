import requests

BITRIX_WEBHOOK = "https://b24-mwcobf.bitrix24.ru/rest/12/9mv0ulk31p44kbxv/"  # Вебхук из Bitrix24

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
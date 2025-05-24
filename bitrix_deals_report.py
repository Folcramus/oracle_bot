import requests
from fpdf import FPDF
from datetime import datetime

# 🔧 ВСТАВЬ СВОЙ WEBHOOK
WEBHOOK_URL = "https://b24-mwcobf.bitrix24.ru/rest/1/671oflp23zoilljq/crm.deal.list.json"

def get_deals():
    params = {
        "select": ["ID", "TITLE", "STAGE_ID", "OPPORTUNITY", "CURRENCY_ID", "DATE_CREATE", "DATE_CLOSE"]
    }
    response = requests.get(WEBHOOK_URL, params=params)
    response.raise_for_status()
    return response.json().get("result", [])

def generate_pdf_report(deals, filename="bitrix_deals_report.pdf"):
    pdf = FPDF()
    pdf.add_page()
    
    # ✅ Подключаем кириллический шрифт
    pdf.add_font("DejaVu", "", "fonts/DejaVuSans.ttf", uni=True)
    pdf.set_font("DejaVu", size=9)

    pdf.cell(200, 10, txt="Отчет по сделкам Bitrix24", ln=True, align="C")
    pdf.cell(200, 10, txt=f"Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}", ln=True, align="C")
    pdf.ln(10)

    # 🧾 Заголовки таблицы
    headers = ["ID", "Название", "Сумма", "Валюта", "Дата создания", "Дата закрытия", "Финальная стадия"]
    col_widths = [15, 50, 20, 20, 30, 30, 30]

    for i, header in enumerate(headers):
        pdf.cell(col_widths[i], 10, header, 1)
    pdf.ln()

    # 📊 Сводка
    total_sum = 0
    total_count = 0
    success_count = 0

    for deal in deals:
        total_count += 1
        amount = float(deal.get("OPPORTUNITY", 0) or 0)
        total_sum += amount

        stage = deal.get("STAGE_ID", "-")
        if stage == "WON":  # ⚠️ Настрой это под свою стадию "успешно"
            success_count += 1

        pdf.cell(col_widths[0], 10, str(deal.get("ID", "-")), 1)
        pdf.cell(col_widths[1], 10, str(deal.get("TITLE", "-")), 1)
        pdf.cell(col_widths[2], 10, str(amount), 1)
        pdf.cell(col_widths[3], 10, str(deal.get("CURRENCY_ID", "-")), 1)

        date_create = deal.get("DATE_CREATE", "-").split("T")[0] if deal.get("DATE_CREATE") else "-"
        date_close = deal.get("DATE_CLOSE", "-").split("T")[0] if deal.get("DATE_CLOSE") else "-"
        pdf.cell(col_widths[4], 10, date_create, 1)
        pdf.cell(col_widths[5], 10, date_close, 1)
        pdf.cell(col_widths[6], 10, stage, 1)
        pdf.ln()

    # 📌 Итоговая строка
    pdf.ln(10)
    pdf.set_font("DejaVu", size=10)
    pdf.cell(200, 10, f"Сводка за {datetime.now().year} год:", ln=True)
    pdf.cell(200, 10, f"Всего сделок: {total_count}", ln=True)
    pdf.cell(200, 10, f"Суммарная сумма: {total_sum}", ln=True)
    pdf.cell(200, 10, f"Успешно завершено: {success_count}", ln=True)
    pdf.cell(200, 10, f"Налог в 6%: {total_sum * 0.06}", ln=True)

    pdf.output(filename)
    print(f"✅ PDF сохранён как {filename}")

if __name__ == "__main__":
    print("📡 Получение сделок из Bitrix24...")
    deals = get_deals()
    print(f"🔍 Получено сделок: {len(deals)}")
    generate_pdf_report(deals)

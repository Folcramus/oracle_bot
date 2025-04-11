from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import date

# Регистрация кириллического шрифта
pdfmetrics.registerFont(TTFont('DejaVu', 'DejaVuSans.ttf'))

def generate_official_usn_declaration(
    taxpayer_name,
    inn,
    kpp,
    year,
    income,
    tax_rate,
    output_file="usn_official_declaration.pdf"
):
    tax = round(income * (tax_rate / 100), 2)
    c = canvas.Canvas(output_file, pagesize=A4)
    width, height = A4
    line_height = 18

    c.setFont("DejaVu", 12)

    y = height - 40
    def draw_line(label, value=""):
        nonlocal y
        c.drawString(40, y, f"{label}: {value}")
        y -= line_height

    # Шапка
    c.setFont("DejaVu", 14)
    c.drawCentredString(width / 2, y, "Налоговая декларация по налогу, уплачиваемому в связи с применением УСН")
    y -= 2 * line_height

    c.setFont("DejaVu", 12)
    draw_line("ИНН", inn)
    draw_line("КПП", kpp)
    draw_line("Налоговый период (год)", year)
    draw_line("ФИО / Наименование", taxpayer_name)
    draw_line("Система налогообложения", "УСН (объект: доходы)")
    draw_line("Общий доход за год", f"{income} руб.")
    draw_line("Ставка налога", f"{tax_rate}%")
    draw_line("Налог к уплате", f"{tax} руб.")
    draw_line("Дата формирования", date.today().strftime("%d.%m.%Y"))
    draw_line("Подпись", "________________________")

    c.save()
    print(f"✅ Официальная декларация УСН сгенерирована: {output_file}")

# Пример использования
generate_official_usn_declaration(
    taxpayer_name="ИП Петров Пётр Петрович",
    inn="123456789012",
    kpp="123456789",
    year=2024,
    income=2000000,
    tax_rate=6.0
)

from fpdf import FPDF
from datetime import datetime

class USNDeclarationForm(FPDF):
    def __init__(self, bg_path):
        super().__init__()
        self.bg_path = bg_path

    def header(self):
        self.image(self.bg_path, x=0, y=0, w=210, h=297)  # A4 формат

    def fill_fields(self, inn, year, income, tax, fio="Иванов Иван Иванович"):
        self.set_font("Arial", size=10)
        self.set_text_color(0)

        # ИНН — верхняя строка
        self.set_xy(36, 13.5)
        self.cell(40, 5, inn)

        # Отчётный год — в правом верхнем углу
        self.set_xy(170, 34)
        self.cell(20, 5, year)

        # Объект налогообложения: "1" — Доходы
        self.set_xy(29.5, 102.5)
        self.cell(5, 5, "1")

        # Доход — нижний блок, левый столбец (примерное размещение)
        self.set_xy(40, 150)
        self.cell(50, 5, f"{income:,.2f}".replace(",", " "))

        # Налог
        self.set_xy(40, 160)
        self.cell(50, 5, f"{tax:,.2f}".replace(",", " "))

        # Подпись (ФИО)
        self.set_xy(28, 246.5)
        self.cell(80, 5, fio)

        # Дата
        self.set_xy(130, 246.5)
        self.cell(30, 5, datetime.today().strftime("%d.%m.%Y"))

def generate_declaration_pdf():
    inn = input("Введите ИНН ИП: ").strip()
    year = input("Введите год декларации (например, 2024): ").strip()
    income = float(input("Введите сумму дохода за год: ").strip())
    fio = input("Введите ФИО (например: Иванов Иван Иванович): ").strip()
    tax = round(income * 0.06, 2)

    template_path = "929d3d7a-ba8d-4158-aff7-9cb6e5165876.png"
    pdf = USNDeclarationForm(template_path)
    pdf.add_page()
    pdf.fill_fields(inn, year, income, tax, fio)

    filename = f"usn_declaration_{inn}_{year}.pdf"
    pdf.output(filename)
    print(f"\n✅ Декларация сохранена как: {filename}")

generate_declaration_pdf()

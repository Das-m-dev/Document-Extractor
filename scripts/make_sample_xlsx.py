from openpyxl import Workbook

wb = Workbook()
ws = wb.active
ws.title = "請求書"
rows = [
    ["請求書"],
    ["請求書番号", "INV-2026-205"],
    ["発行日", "2026-11-12"],
    ["株式会社サンプル製作所"],
    ["登録番号", "T1234567890123"],
    [],
    ["品名", "数量", "単価", "金額"],
    ["ナット M8", 50, 30, 1500],
    ["ワッシャー M8", 100, 5, 500],
    [],
    ["小計", 2000],
    ["消費税(10%)", 200],
    ["合計", 2200],
]
for r in rows:
    ws.append(r)
wb.save("sample_invoice.xlsx")
print("saved sample_invoice.xlsx")
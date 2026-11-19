import fitz  # PyMuPDF

lines = [
    "INVOICE",
    "Invoice No: INV-2026-101",
    "Vendor: Test Manufacturing Co.",
    "Registration No: T9876543210123",
    "Date: 2026-11-05",
    "Nuts M8  50 x 30 JPY",
    "Subtotal: 1,500 JPY",
    "Tax (10%): 150 JPY",
    "Total: 1,650 JPY",
]

doc = fitz.open()
page = doc.new_page()
y = 72
for line in lines:
    page.insert_text((72, y), line, fontsize=12)
    y += 20
doc.save("sample_invoice.pdf")
print("saved sample_invoice.pdf")
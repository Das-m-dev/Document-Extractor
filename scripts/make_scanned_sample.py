import fitz

src = fitz.open("sample_invoice.pdf")
pix = src[0].get_pixmap(dpi=150)
pix.save("sample_invoice.png")

out = fitz.open()
page = out.new_page(width=src[0].rect.width, height=src[0].rect.height)
page.insert_image(page.rect, pixmap=pix)
out.save("sample_scanned.pdf")
print("saved sample_invoice.png and sample_scanned.pdf")

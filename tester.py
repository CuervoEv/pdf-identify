import fitz
doc = fitz.open(r"C:\Users\CMJCUERVO\Desktop\JulianC\Cursor\proyecto-llenado-formulario-automatico\Prueba-1.pdf")
page = doc[0]
print("rotation:", page.rotation)
print("rect:", page.rect)
print("cropbox:", page.cropbox)
print("mediabox:", page.mediabox)
doc.close()
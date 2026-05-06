from PIL import Image, ImageDraw, ImageFont

def agregar_grilla(image_pil):
    img = image_pil.copy().convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size

    for i in range(0, 1001, 100):
        x = int((i / 1000) * w)
        y = int((i / 1000) * h)

        # Línea vertical gris
        draw.line([(x, 0), (x, h)], fill=(180, 180, 180), width=1)
        # Línea horizontal gris
        draw.line([(0, y), (w, y)], fill=(180, 180, 180), width=1)
        # Número eje X (arriba)
        draw.text((x + 2, 2), str(i), fill=(220, 50, 50))
        # Número eje Y (izquierda)
        draw.text((2, y + 2), str(i), fill=(220, 50, 50))

    return img

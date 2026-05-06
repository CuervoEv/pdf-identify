import fitz  # PyMuPDF
import os

def generar_radiografia_rudimentaria(ruta_entrada, ruta_salida):
    print(f"🔍 Abriendo documento para radiografía rudimentaria: {ruta_entrada}")
    
    try:
        doc = fitz.open(ruta_entrada)
        
        for num_pagina in range(len(doc)):
            pagina = doc[num_pagina]
            print(f"\n" + "="*40)
            print(f"📄 Analizando Página {num_pagina + 1}")
            print(f"📐 Dimensiones visuales reales: {pagina.rect}")
            print("="*40)

            # --- 1. PROCESAR TEXTO (AZUL) ---
            bloques_texto = pagina.get_text("blocks")
            print(f"\n[TEXTO] Se encontraron {len(bloques_texto)} bloques de texto.")
            
            for i, bloque in enumerate(bloques_texto):
                rect_texto = fitz.Rect(bloque[:4])
                
                # Usamos add_rect_annot: Dibuja un comentario cuadrado sobre la hoja (infalible)
                anotacion = pagina.add_rect_annot(rect_texto)
                anotacion.set_colors(stroke=(0, 0, 1)) # RGB: Azul
                anotacion.update()
                
            # --- 2. PROCESAR VECTORES (ROJO Y VERDE) ---
            dibujos = pagina.get_drawings()
            print(f"\n[VECTORES] Se encontraron {len(dibujos)} elementos dibujados.")
            
            for j, dibujo in enumerate(dibujos):
                rect_vector = fitz.Rect(dibujo["rect"])
                ancho = rect_vector.width
                alto = rect_vector.height

                # Filtro rudimentario: Ignorar "basura" microscópica (puntos perdidos menores a 0.5 pixeles)
                if ancho < 0.5 and alto < 0.5:
                    continue

                # Si es muy delgado (ancho o alto casi cero), es una línea
                if ancho < 2 or alto < 2:
                    anotacion = pagina.add_rect_annot(rect_vector)
                    anotacion.set_colors(stroke=(0, 1, 0)) # RGB: Verde
                    anotacion.update()
                
                # Si tiene cuerpo en ambas dimensiones, es un rectángulo/checkbox
                else:
                    anotacion = pagina.add_rect_annot(rect_vector)
                    anotacion.set_colors(stroke=(1, 0, 0)) # RGB: Rojo
                    anotacion.update()
                    
                    # Print detallado solo de los rectángulos (posibles checkboxes)
                    print(f"  -> Checkbox/Recuadro {j+1} detectado: x={rect_vector.x0:.1f}, y={rect_vector.y0:.1f}, w={ancho:.1f}, h={alto:.1f}")

        # Guardar y cerrar
        doc.save(ruta_salida)
        doc.close()
        print(f"\n✅ Radiografía rudimentaria completada.")
        print(f"📂 Archivo guardado en: {ruta_salida}")

    except Exception as e:
        print(f"\n❌ Error crítico procesando el PDF: {e}")

if __name__ == "__main__":
    archivo_entrada = "Prueba.pdf"  # Revisa que coincida con tu archivo
    archivo_salida = "Prueba_Radiografia.pdf"
    
    if os.path.exists(archivo_entrada):
        generar_radiografia_rudimentaria(archivo_entrada, archivo_salida)
    else:
        print(f"⚠️ No se encontró el archivo: {archivo_entrada}")
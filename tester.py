import fitz  # PyMuPDF
from collections import Counter
import os

def detect_and_add_text(pdf_path, output_path="output.pdf"):
    """
    Lee un PDF, detecta el tamaño de letra más común y agrega "Hola" en la esquina.
    """
    # Verificar que el archivo existe
    if not os.path.exists(pdf_path):
        print(f"❌ Error: No se encuentra el archivo '{pdf_path}'")
        return False
    
    # Abrir el PDF
    print(f"📄 Abriendo PDF: {pdf_path}")
    doc = fitz.open(pdf_path)
    print(f"✓ PDF abierto correctamente. Número de páginas: {len(doc)}")
    
    # Lista para almacenar todos los tamaños de fuente encontrados
    all_font_sizes = []
    
    # PRIMER MÉTODO: get_text("dict") - El original
    print("\n🔍 Método 1: get_text('dict')")
    for page_num in range(len(doc)):
        page = doc[page_num]
        text_dict = page.get_text("dict")
        
        blocks_found = 0
        for block in text_dict.get("blocks", []):
            if block.get("type", 0) == 1:  # Bloque de texto
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        font_size = span.get("size", 0)
                        font_name = span.get("font", "unknown")
                        text = span.get("text", "")
                        if font_size > 0 and text.strip():
                            all_font_sizes.append(round(font_size, 1))
                            blocks_found += 1
                            if blocks_found <= 5:  # Mostrar primeros 5 ejemplos
                                print(f"  Pág{page_num+1}: Texto='{text[:30]}...' Tamaño={font_size} Fuente={font_name}")
        
        print(f"  Página {page_num+1}: Encontrados {blocks_found} spans de texto")
    
    # SEGUNDO MÉTODO: get_text("rawdict") - Más detallado
    print("\n🔍 Método 2: get_text('rawdict')")
    for page_num in range(len(doc)):
        page = doc[page_num]
        text_rawdict = page.get_text("rawdict")
        
        blocks_found = 0
        for block in text_rawdict.get("blocks", []):
            if block.get("type", 0) == 1:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        font_size = span.get("size", 0)
                        text = span.get("text", "")
                        if font_size > 0 and text.strip():
                            if blocks_found < 3:  # Mostrar primeros 3
                                print(f"  Pág{page_num+1}: '{text[:30]}' - Tamaño:{font_size}")
                            blocks_found += 1
        print(f"  Página {page_num+1}: Encontrados {blocks_found} spans")
    
    # TERCER MÉTODO: Extraer caracter por caracter con get_text_words()
    print("\n🔍 Método 3: get_text_words() - Palabras individuales")
    for page_num in range(len(doc)):
        page = doc[page_num]
        words = page.get_text_words()
        print(f"  Página {page_num+1}: {len(words)} palabras encontradas")
        
        # Mostrar primeras 5 palabras como ejemplo
        for i, word in enumerate(words[:5]):
            # word = (x0, y0, x1, y1, word, block_no, line_no, word_no, font_size, font_flags, font_name)
            if len(word) > 8:
                text = word[4]  # El texto está en índice 4
                font_size = word[8] if len(word) > 8 else 0
                print(f"    Palabra: '{text}', Tamaño: {font_size}")
                if font_size > 0:
                    all_font_sizes.append(round(font_size, 1))
    
    # CUARTO MÉTODO: get_text("html") para ver estructura
    print("\n🔍 Método 4: Verificando estructura del texto")
    for page_num in range(min(2, len(doc))):  # Solo primeras 2 páginas
        page = doc[page_num]
        html_text = page.get_text("html")
        print(f"  Página {page_num+1}: HTML obtenido ({len(html_text)} caracteres)")
        
        # Buscar tamaños de fuente en el HTML
        import re
        font_sizes_html = re.findall(r'font-size:\s*([\d.]+)pt', html_text)
        if font_sizes_html:
            print(f"    Tamaños encontrados en HTML: {set([round(float(s),1) for s in font_sizes_html[:10]])}")
            for size in font_sizes_html:
                all_font_sizes.append(round(float(size), 1))
    
    # Determinar el tamaño de letra más común
    print("\n" + "="*50)
    if all_font_sizes:
        print(f"📊 TOTAL de tamaños detectados: {len(all_font_sizes)}")
        print(f"📊 Todos los tamaños encontrados: {sorted(set(all_font_sizes))}")
        
        # Contar frecuencias
        size_counter = Counter(all_font_sizes)
        most_common_size = size_counter.most_common(1)[0][0]
        
        print(f"📊 Distribución de tamaños:")
        for size, count in sorted(size_counter.items())[:10]:
            print(f"    {size} puntos: {count} veces")
        
        print(f"\n✅ Tamaño más común detectado: {most_common_size} puntos")
        text_size = most_common_size
    else:
        print("⚠️ NO se detectaron tamaños de letra con ningún método")
        print("⚠️ Posibles causas:")
        print("    - El PDF puede ser un escaneo (imagen) sin texto real")
        print("    - El texto puede estar codificado de manera no estándar")
        print("    - Puede faltar la librería de extracción de texto")
        print("\n💡 Usando tamaño por defecto: 12 puntos")
        text_size = 12
    
    # Agregar "Hola" en cada página
    print("\n" + "="*50)
    print("✍️ Agregando texto 'Hola' a cada página...")
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        
        # Obtener dimensiones
        page_rect = page.rect
        page_width = page_rect.width
        page_height = page_rect.height
        
        print(f"\n  Página {page_num+1}:")
        print(f"    Dimensiones: {page_width:.1f} x {page_height:.1f} puntos")
        
        # Posición: esquina superior derecha
        margin = 20
        # Calcular posición X ajustada por ancho del texto
        text_width = fitz.get_text_length("Hola", fontsize=text_size, fontname="helv")
        x_position = page_width - margin - text_width
        y_position = margin + text_size
        
        # USAR EL TAMAÑO DETECTADO (sin forzar mínimo de 10)
        final_size = text_size
        print(f"    Tamaño de texto a usar: {final_size} puntos (EL MÁS COMÚN DETECTADO)")
        print(f"    Ancho del texto: {text_width:.1f} puntos")
        print(f"    Posición: ({x_position:.1f}, {y_position:.1f})")
        
        # Insertar texto
        page.insert_text(
            (x_position, y_position),
            "Hola",
            fontsize=final_size,
            color=(0, 0, 0),
            fontname="helv",
            rotate=0
        )
    
    # Guardar el PDF
    doc.save(output_path)
    doc.close()
    print(f"\n✅ PDF guardado como: {output_path}")
    print(f"✅ Se usó el tamaño más común: {text_size} puntos")
    return True

def main():
    """Función principal"""
    import sys
    
    # Verificar argumentos
    if len(sys.argv) > 1:
        input_pdf = sys.argv[1]
    else:
        input_pdf = "prueba-1.pdf"
    
    print(f"🎯 Procesando archivo: {input_pdf}")
    print("="*50)
    
    # Verificar PyMuPDF version
    print(f"📚 PyMuPDF versión: {fitz.__doc__}")
    
    # Ejecutar
    success = detect_and_add_text(input_pdf, f"{os.path.splitext(input_pdf)[0]}_con_hola.pdf")
    
    if not success:
        print("\n❌ El proceso falló. Verifica que el archivo existe y no está corrupto.")
        sys.exit(1)

if __name__ == "__main__":
    main()
import fitz  # PyMuPDF
from collections import Counter
import os
import tempfile
import pythoncom
import win32com.client
from win32com.client import constants
import time

def convert_pdf_to_word_temp(pdf_path):
    """
    Convierte PDF a Word temporalmente para extraer información de formato
    """
    try:
        pythoncom.CoInitialize()
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        
        # Crear documento temporal
        temp_doc = tempfile.NamedTemporaryFile(suffix=".docx", delete=False)
        temp_doc.close()
        
        # Abrir PDF en Word (Word puede abrir PDFs directamente)
        doc = word.Documents.Open(os.path.abspath(pdf_path))
        
        # Guardar como Word
        doc.SaveAs2(temp_doc.name, FileFormat=constants.wdFormatXMLDocument)
        
        # Extraer información de formato
        font_info = extract_font_info_from_word(word, doc)
        
        # Cerrar sin guardar cambios
        doc.Close(SaveChanges=False)
        word.Quit()
        
        # Limpiar
        del word
        pythoncom.CoUninitialize()
        
        # Eliminar archivo temporal
        try:
            os.unlink(temp_doc.name)
        except:
            pass
        
        return font_info
        
    except Exception as e:
        print(f"  Error con conversión Word: {e}")
        try:
            word.Quit()
        except:
            pass
        pythoncom.CoUninitialize()
        return None

def extract_font_info_from_word(word, doc):
    """
    Extrae información de fuente del documento de Word
    """
    try:
        # Analizar primeros párrafos
        fonts = []
        font_sizes = []
        
        for paragraph in doc.Paragraphs:
            if paragraph.Range.Text.strip():
                # Obtener fuente del párrafo
                try:
                    font_name = paragraph.Range.Font.Name
                    font_size = paragraph.Range.Font.Size
                    
                    if font_name and font_name != "":
                        fonts.append(font_name)
                    if font_size and font_size > 0:
                        font_sizes.append(font_size)
                except:
                    pass
        
        # También revisar caracteres individuales para más precisión
        for char in doc.Range().Characters:
            if char.Text.strip():
                try:
                    font_name = char.Font.Name
                    font_size = char.Font.Size
                    
                    if font_name and font_name != "":
                        fonts.append(font_name)
                    if font_size and font_size > 0:
                        font_sizes.append(font_size)
                except:
                    pass
        
        if fonts and font_sizes:
            # Fuente más común
            most_common_font = Counter(fonts).most_common(1)[0][0]
            # Tamaño más pequeño (excluyendo 0)
            smallest_size = min([s for s in font_sizes if s > 0])
            
            return {
                'font': most_common_font,
                'smallest_size': smallest_size,
                'all_sizes': list(set(font_sizes)),
                'all_fonts': list(set(fonts))
            }
        
    except Exception as e:
        print(f"  Error extrayendo formato: {e}")
    
    return None

def detect_font_and_size_from_pdf(pdf_path):
    """
    Detecta fuente y tamaño directamente del PDF
    """
    doc = fitz.open(pdf_path)
    
    fonts = []
    font_sizes = []
    
    print("\n🔍 Detectando fuentes y tamaños del PDF...")
    
    for page_num in range(min(3, len(doc))):  # Primeras 3 páginas
        page = doc[page_num]
        words = page.get_text_words()
        
        for word in words:
            if len(word) > 8:
                font_size = word[8]
                font_name = word[10] if len(word) > 10 else "unknown"
                
                if font_size > 0:
                    font_sizes.append(round(font_size, 1))
                if font_name and font_name != "unknown":
                    fonts.append(font_name)
    
    doc.close()
    
    if fonts and font_sizes:
        # Fuente más común
        most_common_font = Counter(fonts).most_common(1)[0][0]
        # Tamaño más pequeño (excluyendo tamaños extremadamente pequeños)
        smallest_size = min([s for s in font_sizes if s > 3])
        
        return {
            'font': most_common_font,
            'smallest_size': smallest_size,
            'all_sizes': sorted(set(font_sizes)),
            'all_fonts': list(set(fonts))
        }
    
    return None

def add_hola_to_pdf(pdf_path, font_info, output_path="output.pdf"):
    """
    Agrega "Hola" al PDF usando la fuente y tamaño detectados
    """
    doc = fitz.open(pdf_path)
    
    # Mapear nombres de fuentes de Word a fuentes de PyMuPDF
    font_mapping = {
        'Arial': 'helv',
        'Calibri': 'helv',
        'Times New Roman': 'times',
        'Times': 'times',
        'Courier New': 'cour',
        'Courier': 'cour',
        'Helvetica': 'helv',
        'Verdana': 'helv'
    }
    
    # Seleccionar fuente
    detected_font = font_info.get('font', 'helv')
    pdf_font = font_mapping.get(detected_font, 'helv')
    
    # Usar el tamaño más pequeño detectado
    font_size = font_info.get('smallest_size', 8)
    
    # Ajustar tamaño (a veces Word da tamaños diferentes)
    # Si el tamaño es muy pequeño (< 5) o muy grande (> 20), ajustar
    if font_size < 5:
        font_size = 8
    elif font_size > 20:
        font_size = 12
    
    print(f"\n✍️ Agregando 'Hola' con:")
    print(f"  Fuente detectada: {detected_font} -> usando: {pdf_font}")
    print(f"  Tamaño más pequeño: {font_size} puntos")
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        
        # Obtener dimensiones
        page_rect = page.rect
        page_width = page_rect.width
        page_height = page_rect.height
        
        # Margen de la esquina
        margin = 20
        
        # Calcular posición X ajustada
        text_width = fitz.get_text_length("Hola", fontsize=font_size, fontname=pdf_font)
        x_position = page_width - margin - text_width
        y_position = margin + font_size
        
        print(f"\n  Página {page_num+1}:")
        print(f"    Posición: ({x_position:.1f}, {y_position:.1f})")
        print(f"    Tamaño: {font_size} puntos")
        
        # Insertar texto con la fuente detectada
        page.insert_text(
            (x_position, y_position),
            "Hola",
            fontsize=font_size,
            color=(0, 0, 0),
            fontname=pdf_font,
            rotate=0
        )
    
    doc.save(output_path)
    doc.close()
    print(f"\n✅ PDF guardado como: {output_path}")

def main():
    """Función principal"""
    import sys
    
    # Configurar PDF de entrada
    if len(sys.argv) > 1:
        input_pdf = sys.argv[1]
    else:
        input_pdf = "prueba-1.pdf"
    
    if not os.path.exists(input_pdf):
        print(f"❌ Error: No se encuentra '{input_pdf}'")
        sys.exit(1)
    
    print("="*60)
    print("🎯 DETECTANDO FUENTE Y TAMAÑO DE LETRA")
    print("="*60)
    
    # Método 1: Detectar directamente del PDF
    pdf_info = detect_font_and_size_from_pdf(input_pdf)
    
    if pdf_info:
        print(f"\n📊 Detección desde PDF:")
        print(f"  Fuente más común: {pdf_info['font']}")
        print(f"  Tamaño más pequeño: {pdf_info['smallest_size']} puntos")
        print(f"  Todos los tamaños: {pdf_info['all_sizes']}")
        
        font_info = pdf_info
    else:
        print("\n⚠️ No se pudo detectar desde PDF, intentando con Word...")
        
        # Método 2: Convertir a Word temporalmente
        word_info = convert_pdf_to_word_temp(input_pdf)
        
        if word_info:
            print(f"\n📊 Detección desde Word:")
            print(f"  Fuente más común: {word_info['font']}")
            print(f"  Tamaño más pequeño: {word_info['smallest_size']} puntos")
            print(f"  Todos los tamaños: {word_info['all_sizes']}")
            
            font_info = word_info
        else:
            print("\n⚠️ Usando valores por defecto")
            font_info = {
                'font': 'helv',
                'smallest_size': 8
            }
    
    # Agregar "Hola" al PDF
    print("\n" + "="*60)
    base_name = os.path.splitext(input_pdf)[0]
    output_pdf = f"{base_name}_con_hola.pdf"
    
    add_hola_to_pdf(input_pdf, font_info, output_pdf)
    
    print("\n" + "="*60)
    print("✅ PROCESO COMPLETADO")
    print("="*60)

if __name__ == "__main__":
    main()